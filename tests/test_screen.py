import json
import os
import tempfile
import unittest

from tests.fixtures import make_black_then_white, make_clip, SKILL_DIR
import screen

STYLE = json.load(open(os.path.join(SKILL_DIR, "style.json")))


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_sample_measures_the_moment_at_its_time(self):
        p = make_black_then_white(os.path.join(self.tmp.name, "cut.mp4"), 0.6, 1.4)
        samples = screen.sample_quality(p, 2.0)
        self.assertEqual([round(s["t"], 2) for s in samples], [0.0, 0.5, 1.0, 1.5])
        self.assertEqual([s["luma"] > 128 for s in samples], [False, False, True, True])

    def test_dark_frames_unusable(self):
        p = make_clip(os.path.join(self.tmp.name, "dark.mp4"), 2.0, color="black")
        samples = screen.mark_usable(screen.sample_quality(p, 2.0), blur_max=1e9, luma_min=25)
        self.assertTrue(samples)
        self.assertTrue(all(s["usable"] is False for s in samples))

    def test_sharp_testsrc_usable(self):
        p = make_clip(os.path.join(self.tmp.name, "sharp.mp4"), 2.0)
        sc = STYLE["screen"]
        samples = screen.mark_usable(screen.sample_quality(p, 2.0), blur_max=sc["blur_max"], luma_min=sc["luma_min"])
        self.assertTrue(all(s["usable"] is True for s in samples))

    def test_sample_count_matches_fps(self):
        p = make_clip(os.path.join(self.tmp.name, "c.mp4"), 3.0)
        samples = screen.sample_quality(p, 2.0)
        self.assertLessEqual(abs(len(samples) - 6), 1)
        ts = [s["t"] for s in samples]
        self.assertEqual(ts, sorted(ts))


if __name__ == "__main__":
    unittest.main()
