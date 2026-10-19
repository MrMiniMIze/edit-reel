import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.fixtures import make_black_then_white, make_clip
import ingest
import screen
import sheets


def mean_luma(png):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    return sum(raw) / len(raw)


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

    def test_extract_frames_picks_the_right_moments(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "bw.mp4")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=320x568:r=30:d=1[a];color=c=white:s=320x568:r=30:d=1[b];[a][b]concat",
                            "-pix_fmt", "yuv420p", src], check=True)
            paths = sheets.extract_frames(src, [0.0, 0.4, 0.8, 1.2, 1.6], d)
            self.assertEqual([mean_luma(p) > 128 for p in paths], [False, False, False, True, True])

    def test_tile_shows_the_moment_on_its_label(self):
        with tempfile.TemporaryDirectory() as d:
            src = make_black_then_white(os.path.join(d, "cut.mp4"), 0.6, 1.4)
            paths = sheets.extract_frames(src, [0.0, 0.5, 1.0, 1.5], d)
            self.assertEqual([mean_luma(p) > 128 for p in paths], [False, False, True, True])

    def test_long_clip_decodes_once(self):
        with tempfile.TemporaryDirectory() as d:
            src = make_clip(os.path.join(d, "long.mp4"), 60.0, size=(144, 256))
            times = sheets.sample_times({"items": [{"file": "long.mp4", "kind": "video", "duration": 60.0}]},
                                        600, 2.0)["long.mp4"]
            real = subprocess.run
            with mock.patch("sheets.subprocess.run", side_effect=real) as run:
                paths = sheets.extract_frames(src, times, d)
            self.assertEqual(len(paths), len(times))
            self.assertEqual(run.call_count, 1)
            self.assertTrue(all(os.path.getsize(p) > 0 for p in paths))

    def test_one_decode_per_clip_not_per_frame(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            make_clip(os.path.join(media, "a.mp4"), 3.0)
            make_clip(os.path.join(media, "b.mp4"), 3.0)
            inv = ingest.build_inventory(media)
            times = sheets.sample_times(inv, 600, 2.0)  # 12 frames -> 1 sheet
            real = subprocess.run
            with mock.patch("sheets.subprocess.run", side_effect=real) as run:
                idx = sheets.make_sheets(inv, times, os.path.join(d, "s"), cols=4, rows=4)
            self.assertEqual(len(idx), 1)
            self.assertLessEqual(run.call_count, 2 + 1)

    def test_clip_ending_just_after_a_sample_decodes_once(self):
        with tempfile.TemporaryDirectory() as d:
            src = make_clip(os.path.join(d, "c.mp4"), 3.1, size=(144, 256))  # last sample 3.0, clip ends 3.1
            times = sheets.sample_times({"items": [{"file": "c.mp4", "kind": "video", "duration": 3.1}]},
                                        600, 2.0)["c.mp4"]
            real = subprocess.run
            with mock.patch("sheets.subprocess.run", side_effect=real) as run:
                paths = sheets.extract_frames(src, times, d)
            self.assertEqual((len(paths), run.call_count), (len(times), 1))

    def test_odd_filename_labels_render(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            make_clip(os.path.join(media, "Sam's clip: 1%.mp4"), 1.0)
            inv = ingest.build_inventory(media)
            idx = sheets.make_sheets(inv, sheets.sample_times(inv, 600, 2.0), os.path.join(d, "s"), cols=4, rows=4)
            self.assertEqual(idx[0]["frames"][0]["file"], "Sam's clip: 1%.mp4")


if __name__ == "__main__":
    unittest.main()
