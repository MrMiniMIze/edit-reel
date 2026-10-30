"""Find what was said in each clip (Whisper) and tighten talking shots by cutting pauses and fillers.

Whisper's word times run back to back, so they place a line but can't see the pauses inside it. Pauses come
from the clip's own loudness in the voice band, measured against that clip's noise floor (street noise and
wind sit far above any fixed silence level).
"""
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401  (puts ffmpeg-full on PATH)
import sheets  # noqa: E402

MODEL_NAME = "ggml-large-v3-turbo.bin"
MODEL_URL = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{MODEL_NAME}"
MODEL_BYTES = 1_624_555_275
MODEL_DIR = os.path.expanduser("~/Library/Application Support/edit-reel/models")
RATE = 16000


def model_path():
    return os.path.join(MODEL_DIR, MODEL_NAME)


def whisper_bin():
    return shutil.which("whisper-cli") or next(
        (p for p in ("/opt/homebrew/bin/whisper-cli", "/usr/local/bin/whisper-cli") if os.path.exists(p)), None)


def problem():
    """Why talking can't be found on this Mac, with the fix, or None."""
    if not whisper_bin():
        return "whisper-cli not found. Install it: brew install whisper-cpp"
    if not os.path.exists(model_path()):
        return (f"the speech model isn't downloaded yet (1.6 GB, one time). Run: "
                f"python3 \"{os.path.abspath(__file__)}\" --download")
    return None


def download_model(tries=8):
    """Download the model with resume, since a 1.6 GB file often outlives one connection."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    part = model_path() + ".part"
    for _ in range(tries):
        r = subprocess.run(["curl", "-L", "--fail", "-C", "-", "--speed-limit", "10000", "--speed-time", "60",
                            "-o", part, MODEL_URL])
        if r.returncode == 0 and os.path.getsize(part) == MODEL_BYTES:
            os.rename(part, model_path())
            return model_path()
    raise RuntimeError("the speech model download kept failing; check the connection and run --download again")


def extract_audio(src, wav, voice_band=False):
    af = ["-af", "highpass=f=300,lowpass=f=3400"] if voice_band else []
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vn", "-ac", "1",
                    "-ar", str(RATE), *af, "-c:a", "pcm_s16le", wav], check=True)


def parse_whisper(doc):
    """whisper-cli -ojf output -> [{t0, t1, text, p, words: [{w, t0, t1}]}], times in seconds."""
    lines = []
    for seg in doc.get("transcription", []):
        text = seg["text"].strip()
        words, ps = [], []
        for tok in seg.get("tokens", []):
            t = tok["text"]
            if t.startswith("[_") or not t.strip():
                continue
            ps.append(tok.get("p", 1.0))
            t0, t1 = tok["offsets"]["from"] / 1000, tok["offsets"]["to"] / 1000
            t1 = max(t0, t1)  # Whisper occasionally ends a token before it starts
            if t.startswith(" ") or not words:
                words.append({"w": t.strip(), "t0": t0, "t1": t1})
            else:  # a word continued over several tokens
                words[-1]["w"] += t
                words[-1]["t1"] = t1
        if not re.search(r"[A-Za-z]", text):
            continue
        lines.append({"t0": seg["offsets"]["from"] / 1000, "t1": seg["offsets"]["to"] / 1000, "text": text,
                      "p": round(sum(ps) / len(ps), 3) if ps else 0.0, "words": words})
    return lines


def transcribe(wav, tmp):
    base = os.path.join(tmp, os.path.splitext(os.path.basename(wav))[0])
    subprocess.run([whisper_bin(), "-m", model_path(), "-f", wav, "-l", "en", "-ojf", "-of", base, "-np"],
                   check=True, capture_output=True)
    return parse_whisper(json.load(open(base + ".json")))


def envelope(wav, win=0.02):
    """Loudness in dB per window of a 16-bit mono wav."""
    w = wave.open(wav)
    a = array.array("h", w.readframes(w.getnframes()))
    n = max(1, int(w.getframerate() * win))
    return [10 * math.log10(sum(x * x for x in a[i:i + n]) / n / 32768 ** 2 + 1e-12)
            for i in range(0, len(a) - n + 1, n)]


def find_pauses(env, win, frac=0.25, min_pause=0.45, min_sound=0.06):
    """Quiet stretches of at least min_pause seconds, relative to this clip's own noise floor and voice level.

    A sound shorter than min_sound (a breath, a click) doesn't end a pause."""
    if not env:
        return []
    srt = sorted(env)
    floor, loud = srt[int(len(srt) * 0.1)], srt[int(len(srt) * 0.95)]
    thr = floor + frac * (loud - floor)
    quiet, start = [], None
    for i, db in enumerate(env + [float("inf")]):
        if db < thr and start is None:
            start = i
        elif db >= thr and start is not None:
            quiet.append([start, i])
            start = None
    merged = []
    for a, b in quiet:
        if merged and (a - merged[-1][1]) * win < min_sound:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [[round(a * win, 3), round(b * win, 3)] for a, b in merged if (b - a) * win >= min_pause]


def tighten(t0, t1, pauses, words, fillers, pad=0.08, min_keep=0.15):
    """The parts of [t0, t1] worth keeping: pauses and filler words cut out, a little air left at each cut."""
    cuts = [(a + pad, b - pad) for a, b in pauses if b - a > 2 * pad]
    cuts += [(w["t0"], w["t1"]) for w in words
             if re.sub(r"[^a-z]", "", w["w"].lower()) in fillers and t0 <= w["t0"] < t1]
    spans = [[t0, t1]]
    for a, b in sorted(cuts):
        nxt = []
        for s, e in spans:
            if b <= s or a >= e:
                nxt.append([s, e])
                continue
            if a > s:
                nxt.append([s, a])
            if b < e:
                nxt.append([b, e])
        spans = nxt
    return [(round(s, 3), round(e, 3)) for s, e in spans if e - s >= min_keep]


def trim_edges(env, win, t0, t1, style, reach=0.3, gap=0.12, near=0.15, tail=0.15):
    """Snap a talk line's ends to her voice, by loudness: Whisper's word times are often a few tenths off.

    Leading and trailing quiet is cut down to pad. An end within near s of sound may be inside the last word,
    so it is pushed out to the next quiet gap (at least gap s long) within reach s, plus tail s: the loudness
    is measured in the voice band, which barely hears a closing "s". With no gap that close, the end stays
    where it was (she kept talking, and the cut was meant)."""
    pad = style["pad"]
    a, b = int(t0 / win), int(math.ceil(t1 / win))
    stretch = env[a:b]
    if not stretch:
        return t0, t1
    srt = sorted(stretch)
    floor, loud = srt[int(len(srt) * 0.1)], srt[int(len(srt) * 0.95)]
    thr = floor + style["pause_frac"] * (loud - floor)
    loud_at = [i for i, db in enumerate(stretch) if db >= thr]
    if not loud_at:
        return t0, t1
    start = max(t0, (a + loud_at[0]) * win - pad)
    end = min(t1, (a + loud_at[-1] + 1) * win + pad)
    if (len(stretch) - loud_at[-1]) * win <= near:  # cut lands in or right after sound: find the quiet after it
        need, run = int(round(gap / win)), 0
        for i in range(a + loud_at[-1] + 1, min(len(env), b + int(reach / win))):
            run = run + 1 if env[i] < thr else 0
            if run >= need:
                end = max(end, (i - run + 1) * win + tail)
                break
    return round(start, 3), round(end, 3)


def line_pauses(clip, t0, t1, style):
    """Pauses inside [t0, t1], judged against that stretch's own loudness: a long clip's loud moments
    (a shout, a laugh) would otherwise make quiet narration look like silence."""
    win = clip.get("win")
    if not clip.get("env") or not win:
        return clip["pauses"]
    a, b = int(t0 / win), int(math.ceil(t1 / win))
    local = find_pauses(clip["env"][a:b], win, style["pause_frac"], style["min_pause"], style["min_sound"])
    return [[round(p + a * win, 3), round(q + a * win, 3)] for p, q in local]


def expand_talk(shots, speech, style):
    """Split each talk shot into its tightened pieces; other shots pass through."""
    from cutlist import Shot
    sp = style["speech"]
    out = []
    for s in shots:
        clip = speech.get(s.src)
        if s.role != "talk" or not s.tight or not clip:
            out.append(s)
            continue
        t0, t1 = s.src_in, s.src_in + s.dur
        if clip.get("env") and clip.get("win"):
            t0, t1 = trim_edges(clip["env"], clip["win"], t0, t1, sp)
        pauses = line_pauses(clip, t0, t1, sp)
        spans = tighten(t0, t1, pauses, clip["words"], set(sp["fillers"]), sp["pad"], sp["min_keep"])
        for a, b in spans or [(s.src_in, s.src_in + s.dur)]:
            out.append(Shot(s.src, a, round(b - a, 3), "talk", s.stop, s.rank, s.why, s.speed, tight=False))
    return out


def _analyze_clip(media_dir, item, tmp, style):
    src = os.path.join(media_dir, item["file"])
    stem = os.path.join(tmp, os.path.splitext(item["file"])[0])
    extract_audio(src, stem + ".wav")
    extract_audio(src, stem + ".vb.wav", voice_band=True)
    lines = transcribe(stem + ".wav", tmp)
    win = 0.02
    env = envelope(stem + ".vb.wav", win)
    pauses = find_pauses(env, win, style["pause_frac"], style["min_pause"], style["min_sound"])
    words = [w for ln in lines for w in ln["words"]]
    return item["file"], {"lines": [{k: v for k, v in ln.items() if k != "words"} for ln in lines],
                          "words": words, "pauses": pauses, "win": win, "env": [round(x, 1) for x in env]}


def analyze(inv, out, style):
    """Write speech.json, speech.txt and speech sheets; returns the speech dict."""
    sp = style["speech"]
    vids = [i for i in inv["items"] if i["kind"] == "video" and i.get("has_audio", True)]
    tmp = tempfile.mkdtemp()
    try:
        # Whisper uses every core itself, so transcribe one clip at a time.
        speech = dict(_analyze_clip(inv["media_dir"], v, tmp, sp) for v in vids)
    finally:
        shutil.rmtree(tmp)
    with open(os.path.join(out, "speech.json"), "w") as f:
        json.dump(speech, f, indent=1)

    times, rows, n = {}, [], 0
    for item in inv["items"]:
        clip = speech.get(item["file"])
        for ln in (clip["lines"] if clip else []):
            n += 1
            dur = ln["t1"] - ln["t0"]
            k = max(2, min(4, round(dur)))  # a few frames across each line: where is she looking?
            ts = [round(ln["t0"] + dur * (j + 0.5) / k, 2) for j in range(k)]
            times.setdefault(item["file"], []).extend(t for t in ts if t < item["duration"] - 0.05)
            rows.append(f"#{n} {os.path.splitext(item['file'])[0]} {ln['t0']:.1f}-{ln['t1']:.1f} "
                        f"(p={ln['p']:.2f}): {ln['text']}")
    with open(os.path.join(out, "speech.txt"), "w") as f:
        f.write("\n".join(rows) + "\n")
    if times:
        sh = style["sheets"]
        times = {k: sorted(set(v)) for k, v in times.items()}
        sheets.make_sheets(inv, times, os.path.join(out, "speech_sheets"), sh["cols"], sh["rows"])
    return speech, len(rows)


if __name__ == "__main__":
    if sys.argv[1:] == ["--download"]:
        print(f"downloading the speech model to {MODEL_DIR} ...")
        print(f"done: {download_model()}")
    else:
        workdir = sys.argv[1]
        style = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "style.json")))
        inv = json.load(open(os.path.join(workdir, "inventory.json")))
        _, n = analyze(inv, workdir, style)
        print(f"{n} spoken lines: {os.path.join(workdir, 'speech.txt')}")
