import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.fixtures import SKILL_DIR, make_clip
import common
import render
import speech
from cutlist import Shot, fit, snap, validate

SCRIPTS = os.path.join(SKILL_DIR, "scripts")
STYLE = json.load(open(os.path.join(SKILL_DIR, "style.json")))
FILLERS = set(STYLE["speech"]["fillers"])


def tok(text, t0, t1, p=0.9):
    return {"text": text, "offsets": {"from": int(t0 * 1000), "to": int(t1 * 1000)}, "p": p}


def seg(text, t0, t1, toks):
    return {"text": text, "offsets": {"from": int(t0 * 1000), "to": int(t1 * 1000)}, "tokens": toks}


class ParseTests(unittest.TestCase):
    def test_tokens_become_words_and_markers_are_dropped(self):
        doc = {"transcription": [seg(" I'm here", 0.0, 1.0, [tok("[_BEG_]", 0, 0), tok(" I", 0.0, 0.2),
                                                              tok("'m", 0.2, 0.4), tok(" here", 0.4, 1.0)])]}
        (line,) = speech.parse_whisper(doc)
        self.assertEqual([w["w"] for w in line["words"]], ["I'm", "here"])
        self.assertEqual((line["words"][0]["t0"], line["words"][0]["t1"]), (0.0, 0.4))
        self.assertEqual(line["text"], "I'm here")

    def test_lines_without_words_are_skipped(self):
        doc = {"transcription": [seg(" -", 0, 5, [tok(" -", 0, 5)]), seg(" *laughs*", 5, 6, [tok(" *laughs*", 5, 6)])]}
        self.assertEqual([ln["text"] for ln in speech.parse_whisper(doc)], ["*laughs*"])


class PauseTests(unittest.TestCase):
    def test_pauses_are_relative_to_the_clips_own_noise(self):
        # A noisy street: the floor is -30 dB, speech -20 dB. A fixed -40 dB silence level would find nothing.
        env = [-20.0] * 50 + [-30.0] * 25 + [-20.0] * 50 + [-30.0] * 5 + [-20.0] * 20
        self.assertEqual(speech.find_pauses(env, 0.02, frac=0.3, min_pause=0.3), [[1.0, 1.5]])

    def test_a_breath_does_not_split_a_pause(self):
        env = [-20.0] * 20 + [-60.0] * 10 + [-30.0] * 2 + [-60.0] * 11 + [-20.0] * 20
        self.assertEqual(speech.find_pauses(env, 0.02), [[0.4, 0.86]])

    def test_short_dips_are_not_pauses(self):
        self.assertEqual(speech.find_pauses([-20.0] * 20 + [-60.0] * 10 + [-20.0] * 20, 0.02), [])


class TightenTests(unittest.TestCase):
    def test_cuts_pauses_but_leaves_air(self):
        spans = speech.tighten(0.0, 5.0, [[2.0, 3.0]], [], FILLERS, pad=0.1)
        self.assertEqual(spans, [(0.0, 2.1), (2.9, 5.0)])

    def test_cuts_filler_words(self):
        words = [{"w": "so", "t0": 0.0, "t1": 0.5}, {"w": "Um,", "t0": 0.5, "t1": 1.0}, {"w": "yes", "t0": 1.0, "t1": 2.0}]
        self.assertEqual(speech.tighten(0.0, 2.0, [], words, FILLERS), [(0.0, 0.5), (1.0, 2.0)])

    def test_drops_slivers(self):
        spans = speech.tighten(0.0, 3.0, [[0.1, 1.5]], [], FILLERS, pad=0.0, min_keep=0.15)
        self.assertEqual(spans, [(1.5, 3.0)])

    def test_expand_splits_talk_only(self):
        sp = {"a.mp4": {"pauses": [[2.0, 3.0]], "words": [], "lines": []}}
        shots = [Shot("a.mp4", 0.0, 1.0, "opener", 1, 0), Shot("a.mp4", 0.0, 5.0, "talk", 1, 0, "why")]
        out = speech.expand_talk(shots, sp, STYLE)
        self.assertEqual(out[0], shots[0])
        self.assertEqual([(s.src_in, s.dur) for s in out[1:]], [(0.0, 2.08), (2.92, 2.08)])
        self.assertTrue(all(s.role == "talk" and not s.tight for s in out[1:]))

    def test_untight_talk_is_kept_whole(self):
        sp = {"a.mp4": {"pauses": [[2.0, 3.0]], "words": [], "lines": []}}
        s = Shot("a.mp4", 0.0, 5.0, "talk", 1, 0, tight=False)
        self.assertEqual(speech.expand_talk([s], sp, STYLE), [s])


def inv(items):
    return {"media_dir": "/x", "order_source": "filename", "items": items}


def vid(name, dur, unusable=()):
    samples = [{"t": k / 2, "blur": 0, "luma": 50, "usable": (k / 2) not in unusable} for k in range(int(dur * 2) + 1)]
    return {"file": name, "kind": "video", "duration": dur, "samples": samples}


class TalkCutlistTests(unittest.TestCase):
    def test_talk_needs_a_stop(self):
        errs = validate([Shot("a.mp4", 0, 1, "talk", 0, 0)], inv([vid("a.mp4", 10)]))
        self.assertTrue(any("talk" in e for e in errs))

    def test_fit_never_drops_talk(self):
        shots = [Shot("a.mp4", 0, 1.0, "opener", 1, 0), Shot("a.mp4", 1, 1.0, "action", 1, 1),
                 Shot("a.mp4", 2, 1.0, "action", 1, 2), Shot("a.mp4", 3, 70.0, "talk", 1, 0)]
        kept, warns = fit(shots, target=60, lo=30, hi=90, tolerance=5)
        self.assertIn(shots[3], kept)
        self.assertNotIn(shots[2], kept)
        self.assertTrue(any("talking" in w for w in warns))

    def test_blurry_talk_edges_are_flagged(self):
        from cutlist import shaky_talk_edges
        items = inv([vid("a.mp4", 10.0, unusable=(1.0, 6.0))])
        warns = shaky_talk_edges([Shot("a.mp4", 1.0, 3.0, "talk", 1, 0), Shot("a.mp4", 5.0, 0.8, "action", 1, 1),
                                  Shot("a.mp4", 7.0, 2.0, "talk", 1, 0)], items)
        self.assertEqual(len(warns), 1)
        self.assertIn("1.00", warns[0])

    def test_snap_does_not_slide_talk(self):
        s = snap([Shot("a.mp4", 0.9, 0.4, "talk", 1, 0)], inv([vid("a.mp4", 3.0, unusable=(1.0,))]))[0]
        self.assertAlmostEqual(s.src_in, 0.9, delta=1 / 30)


def say_clip(path, words, seconds):
    """A clip whose audio is real speech (macOS say), so Whisper and the pause finder have something to find."""
    aiff = path + ".aiff"
    subprocess.run(["say", "-o", aiff, words], check=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc2=size=360x640:rate=30:duration={seconds}", "-i", aiff, "-af", "apad",
                    "-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", path], check=True)
    os.remove(aiff)


class TalkRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_talk_keeps_sound_and_broll_is_silent(self):
        make_clip(os.path.join(self.dir, "a.mp4"), 3.0)
        shots = [Shot("a.mp4", 0.0, 0.5, "hook", 0, 0), Shot("a.mp4", 1.0, 1.0, "talk", 1, 0),
                 Shot("a.mp4", 2.0, 0.5, "action", 1, 1)]
        out = os.path.join(self.dir, "reel.mp4")
        render.render(shots, self.dir, out, (720, 1280))
        info = common.probe(out)
        self.assertTrue(info["has_audio"])
        self.assertAlmostEqual(info["duration"], 2.0, delta=0.06)
        # Silent hook, the clip's tone during the talk shot, silent again after.
        quiet = subprocess.run(["ffmpeg", "-hide_banner", "-i", out, "-af", "silencedetect=noise=-50dB:d=0.3",
                                "-f", "null", "-"], capture_output=True, text=True).stderr
        self.assertIn("silence_start: 0", quiet)
        self.assertEqual(quiet.count("silence_start"), 2, quiet)

    def test_talk_from_a_clip_without_sound_is_silent_not_an_error(self):
        p = os.path.join(self.dir, "mute.mp4")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=360x640:rate=30:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", p],
                       check=True)
        out = os.path.join(self.dir, "reel.mp4")
        render.render([Shot("mute.mp4", 0.0, 1.0, "talk", 1, 0)], self.dir, out, (360, 640))
        self.assertTrue(common.probe(out)["has_audio"])


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("say") and speech.problem() is None,
                     "needs macOS say, whisper-cli and the speech model")
class SpeechE2ETests(unittest.TestCase):
    def test_prepare_finds_speech_and_build_tightens_it(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            say_clip(os.path.join(media, "talk.mp4"), "Today we are going to the vet. [[slnc 1500]] He is not happy.", 8)
            make_clip(os.path.join(media, "broll.mp4"), 3.0)
            out = os.path.join(d, "out")
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "prepare.py"), media, "--out", out],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            sp = json.load(open(os.path.join(out, "speech.json")))
            text = " ".join(ln["text"] for ln in sp["talk.mp4"]["lines"]).lower()
            self.assertIn("vet", text)
            self.assertTrue(any(b - a >= 1.0 for a, b in sp["talk.mp4"]["pauses"]), sp["talk.mp4"]["pauses"])
            self.assertTrue(os.path.exists(os.path.join(out, "speech_sheets", "sheets.json")))
            words = sp["talk.mp4"]["words"]
            t0, t1 = max(0.0, words[0]["t0"] - 0.1), words[-1]["t1"]
            cut = {"target": 60, "shots": [
                {"src": "broll.mp4", "src_in": 0.0, "dur": 1.0, "role": "opener", "stop": 1, "rank": 0},
                {"src": "talk.mp4", "src_in": t0, "dur": t1 - t0, "role": "talk", "stop": 1, "rank": 0},
                {"src": "broll.mp4", "src_in": 1.0, "dur": 1.0, "role": "action", "stop": 1, "rank": 1}]}
            json.dump(cut, open(os.path.join(out, "cutlist.json"), "w"))
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build.py"), out, "--no-capcut"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            final = json.load(open(os.path.join(out, "cutlist.final.json")))["shots"]
            talk = [s for s in final if s["role"] == "talk"]
            self.assertGreaterEqual(len(talk), 2, "the pause should split the line into jump cuts")
            # The end may move out by up to reach + tail to finish a word Whisper ended early.
            self.assertLess(sum(s["dur"] for s in talk), t1 - t0 + 0.45 - 1.0)
            info = common.probe(os.path.join(out, "reel.mp4"))
            self.assertTrue(info["has_audio"])
            self.assertIn("talking:", r.stdout)


if __name__ == "__main__":
    unittest.main()
