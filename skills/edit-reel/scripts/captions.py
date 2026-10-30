"""Captions and a title for talking reels, styled like the creator's own (one short line at a time).

Words come from transcribing the finished talk audio, line by line, so their times are on the reel's own
timeline and match what's actually kept. The pages are written to captions.txt for proofreading; spelling
fixes (brand names) go in cutlist.json's "caption_fixes" and are applied on the next build."""
import json
import os
import re
import shutil
import subprocess
import tempfile

import render
import speech

SENTENCE_END = re.compile(r"[.?!]$")
CLAUSE_END = re.compile(r"[,;:]$")
# A page shouldn't end on a word that leans on the next one ("in my basket for / the Sephora sale").
LEANS = {"a", "an", "the", "my", "your", "his", "her", "our", "their", "this", "that", "for", "to", "in", "of",
         "on", "at", "with", "from", "and", "but", "or", "so", "because", "cause", "if", "as"}
COMMON = {"it", "it's", "is", "was", "one", "oh", "okay", "yeah", "also", "then", "there", "these", "those",
          "we", "you", "he", "she", "they", "what", "how", "when", "why", "fun", "another", "last", "first"}


def _clean(w):
    """Captions carry no punctuation except inside a word (I've, 24/7)."""
    return re.sub(r"^[^\w']+|[^\w'/]+$", "", w)


def _lines(shots):
    """Where each talking line sits on the reel, as [start, end]: a line's tightened pieces run back to back
    and share its why."""
    out, t, prev = [], 0.0, None
    for s in shots:
        if s.role == "talk":
            if prev is not None and prev.role == "talk" and prev.why == s.why and prev.stop == s.stop:
                out[-1][1] = t + s.dur
            else:
                out.append([t, t + s.dur])
        t += s.dur
        prev = s
    return out


def transcribe_reel(shots, media_dir, tmp):
    """Words spoken in the reel, with reel times. Each line is transcribed alone: on a whole long reel
    Whisper's word times drift and bunch up."""
    full = os.path.join(tmp, "reel.wav")
    render.render_audio(shots, media_dir, full)
    words = []
    for n, (a, b) in enumerate(_lines(shots)):
        part = os.path.join(tmp, f"line{n:03d}.wav")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.3f}", "-t",
                        f"{b - a:.3f}", "-i", full, part], check=True)
        for ln in speech.transcribe(part, tmp):
            for w in ln["words"]:
                words.append({"w": w["w"], "t0": round(min(a + w["t0"], b), 3), "t1": round(min(a + w["t1"], b), 3)})
    return words


def apply_fixes(words, fixes):
    """Replace words or phrases, matched case-insensitively without punctuation, keeping their timing.
    {"Edem": "eadem", "Hoss Labs": "Haus Labs", "de influence": "deinfluence"}"""
    for wrong, right in sorted((fixes or {}).items(), key=lambda kv: -len(kv[0].split())):
        pat = [p.lower() for p in wrong.split()]
        rep = right.split()
        out, i = [], 0
        while i < len(words):
            seg = words[i:i + len(pat)]
            if len(seg) == len(pat) and [_clean(w["w"]).lower() for w in seg] == pat:
                trail = re.search(r"[^\w']*$", seg[-1]["w"]).group()  # keep the sentence break it carried
                t0, t1 = seg[0]["t0"], seg[-1]["t1"]
                step = (t1 - t0) / max(len(rep), 1)
                out += [{"w": r + (trail if k == len(rep) - 1 else ""), "t0": round(t0 + k * step, 3),
                         "t1": round(t0 + (k + 1) * step, 3)} for k, r in enumerate(rep)]
                i += len(pat)
            else:
                out.append(words[i])
                i += 1
        words = out
    return words


def pages(words, fillers, max_chars=20, max_words=4, max_gap=0.6, hold=0.3, lowercase=False):
    """Short one-line pages: a page never spans a sentence, clause or long pause, and longer runs are split
    evenly. Sentence-initial capitals are dropped unless the word is capitalized mid-sentence too (a name);
    with lowercase, every word is lowercase except I."""
    words = [w for w in words if _clean(w["w"]) and _clean(w["w"]).lower() not in fillers]
    if not words:
        return []
    proper = {_clean(w["w"]) for i, w in enumerate(words)
              if i and not SENTENCE_END.search(words[i - 1]["w"]) and _clean(w["w"])[:1].isupper()
              and _clean(w["w"]).lower() not in LEANS | COMMON}  # "The Ordinary" doesn't make "The" a name
    runs, run = [], []
    for i, w in enumerate(words):
        if run and w["t0"] - run[-1]["t1"] > max_gap:
            runs.append(run)
            run = []
        first = not run or SENTENCE_END.search(run[-1]["w"])
        text = _clean(w["w"])
        if re.match(r"[iI]('|$)", text):
            text = "I" + text[1:]
        elif lowercase:
            text = text.lower()
        elif first and text not in proper and not re.match(r"I('|$)", text):
            text = text[:1].lower() + text[1:]
        run.append(dict(w, text=text))
        if SENTENCE_END.search(w["w"]) or (CLAUSE_END.search(w["w"]) and len(run) > 1):
            runs.append(run)
            run = []
    if run:
        runs.append(run)

    out = []
    for run in runs:
        out += [{"text": " ".join(x["text"] for x in c), "t0": c[0]["t0"], "t1": c[-1]["t1"]}
                for c in _split(run, max_chars, max_words)]
    for a, b in zip(out, out[1:]):  # stay up until the next page, unless she pauses
        a["t1"] = b["t0"] if b["t0"] - a["t1"] <= max_gap else a["t1"] + hold
    out[-1]["t1"] += hold
    return [dict(p, t0=round(p["t0"], 3), t1=round(p["t1"], 3)) for p in out]


def _split(run, max_chars, max_words):
    """The fewest pages that fit, then the fewest pages ending on a word that leans on the next, then as even
    as possible (least sum of squared page lengths), so no word is left alone."""
    def fits(c):
        return len(c) == 1 or (len(c) <= max_words and len(" ".join(x["text"] for x in c)) <= max_chars)
    best = [(0, 0, 0, 0)] + [None] * len(run)  # (pages, leaning ends, sum of squares, previous break)
    for i in range(1, len(run) + 1):
        for j in range(i - 1, -1, -1):
            if not fits(run[j:i]):
                break
            pages, leans, sq, _ = best[j]
            lean = i < len(run) and run[i - 1]["text"].lower() in LEANS
            cand = (pages + 1, leans + lean, sq + len(" ".join(x["text"] for x in run[j:i])) ** 2, j)
            if best[i] is None or cand[:3] < best[i][:3]:
                best[i] = cand
    cuts, i = [], len(run)
    while i:
        cuts.append(i)
        i = best[i][3]
    bounds = [0] + cuts[::-1]
    return [run[a:b] for a, b in zip(bounds, bounds[1:])]


def make(shots, media_dir, out_dir, fixes, style):
    """Caption pages for the reel; the transcript is cached by the cut so a fix-only rebuild skips Whisper."""
    cache = os.path.join(out_dir, "captions.json")
    key = [[s.src, s.src_in, s.dur] for s in shots if s.role == "talk"]
    words = None
    if os.path.exists(cache):
        saved = json.load(open(cache))
        if saved.get("key") == key:
            words = saved["words"]
    if words is None:
        tmp = tempfile.mkdtemp()
        try:
            words = transcribe_reel(shots, media_dir, tmp)
        finally:
            shutil.rmtree(tmp)
        with open(cache, "w") as f:
            json.dump({"key": key, "words": words}, f)
    cs = style["captions"]
    pg = pages(apply_fixes(words, fixes), set(style["speech"]["fillers"]), cs["max_chars"], cs["max_words"],
               lowercase=cs.get("lowercase", False))
    end = round(sum(s.dur for s in shots), 3)
    pg = [dict(p, t1=min(p["t1"], end)) for p in pg if p["t0"] < end]
    with open(os.path.join(out_dir, "captions.txt"), "w") as f:
        f.write("".join(f"{p['t0']:7.2f}-{p['t1']:7.2f}  {p['text']}\n" for p in pg))
    return pg


def _escape(text):
    return text.replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace("%", "\\%")


def _font_px(look, width):
    """CapCut text size in pixels: font size x scale x canvas width / 170 (measured on the creator's posts)."""
    return look["size"] * look["clip"]["scale"]["x"] * width / 170


def _font_file(look):
    path = os.path.expanduser(look["font_path"])
    return path if os.path.exists(path) else "/System/Library/Fonts/Helvetica.ttc"


def drawtext(items, looks, size):
    """ffmpeg drawtext filters burning the title and captions into the preview mp4."""
    w, _ = size
    out = []
    for it in items:
        look = looks[it["kind"]]
        cy = (1 - look["clip"]["transform"]["y"]) / 2  # CapCut: y runs -1 (bottom) to 1 (top), at the centre
        out.append(f"drawtext=fontfile='{_font_file(look)}':text='{_escape(it['text'])}':"
                   f"fontsize={_font_px(look, w):.1f}:fontcolor=white:x=(w-tw)/2:y=h*{cy:.4f}-th/2:y_align=font:"
                   f"enable='between(t,{it['t0']:.3f},{it['t1']:.3f})'")
    return out


def place(look, y):
    """The look with its captions centred y of the way down the frame (CapCut runs 1 at the top to -1)."""
    if y is None or not look.get("caption"):
        return look
    look = json.loads(json.dumps(look))
    look["caption"]["clip"]["transform"]["y"] = round(1 - 2 * y, 4)
    return look


def opening_line_end(shots):
    """When the reel's first talking line ends, if the reel opens on one: how long the title stays up."""
    lines = _lines(shots)
    return lines[0][1] if lines and lines[0][0] == 0 else None


def items(title, title_dur, pg):
    """Everything to draw: the title (if any) and the caption pages, in reel time."""
    out = [{"kind": "title", "text": title, "t0": 0.0, "t1": title_dur}] if title else []
    return out + [dict(p, kind="caption") for p in pg]
