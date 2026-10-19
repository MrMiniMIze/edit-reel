import json
import os
import tempfile
import unittest

from tests.fixtures import make_clip
import ingest
import screen
import sheets


def fake_inv(durations):
    return {"media_dir": "/x", "order_source": "filename",
            "items": [{"file": f"c{i}.mp4", "kind": "video", "duration": d} for i, d in enumerate(durations)]}


class SheetsTests(unittest.TestCase):
    def test_sample_times_respects_cap(self):
        times = sheets.sample_times(fake_inv([100, 100, 100]), max_frames=60, base_fps=2.0)
        self.assertLessEqual(sum(len(v) for v in times.values()), 60)
        self.assertTrue(all(len(v) >= 2 for v in times.values()))

    def test_short_clip_gets_two_frames(self):
        times = sheets.sample_times(fake_inv([0.6]), max_frames=600, base_fps=2.0)
        t = times["c0.mp4"]
        self.assertEqual(len(t), 2)
        self.assertTrue(all(x < 0.6 for x in t))

    def test_make_sheets_writes_index(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            make_clip(os.path.join(media, "a.mp4"), 3.0)
            make_clip(os.path.join(media, "b.mp4"), 3.0)
            inv = screen.screen_inventory(ingest.build_inventory(media),
                                          {"screen": {"fps": 2.0, "blur_max": 9.49, "luma_min": 25}})
            out = os.path.join(d, "sheets")
            idx = sheets.make_sheets(inv, sheets.sample_times(inv, 600, 2.0), out, cols=4, rows=4)
            self.assertTrue(os.path.exists(os.path.join(out, "sheets.json")))
            for sh in idx:
                p = os.path.join(out, sh["sheet"])
                self.assertTrue(os.path.getsize(p) > 0)
                for fr in sh["frames"]:
                    self.assertTrue({"file", "t", "usable"} <= set(fr))

    def test_odd_filename_labels_render(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            make_clip(os.path.join(media, "Sam's clip: 1%.mp4"), 1.0)
            inv = ingest.build_inventory(media)
            idx = sheets.make_sheets(inv, sheets.sample_times(inv, 600, 2.0), os.path.join(d, "s"), cols=4, rows=4)
            self.assertEqual(idx[0]["frames"][0]["file"], "Sam's clip: 1%.mp4")


if __name__ == "__main__":
    unittest.main()
