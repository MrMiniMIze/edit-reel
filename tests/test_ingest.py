import os
import tempfile
import unittest

from tests.fixtures import make_clip
import common
import ingest


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_probe_reads_basic_fields(self):
        p = make_clip(os.path.join(self.dir, "a.mp4"), 2.0)
        info = common.probe(p)
        self.assertAlmostEqual(info["duration"], 2.0, delta=0.05)
        self.assertEqual(info["width"], 720)
        self.assertEqual(info["fps"], 30)
        self.assertIs(info["has_audio"], True)

    def test_probe_reports_upright_size_for_rotated_clip(self):
        p = make_clip(os.path.join(self.dir, "portrait.mov"), 0.5, size=(1280, 720), rotation=90)
        info = common.probe(p)
        self.assertEqual((info["width"], info["height"]), (720, 1280))
        self.assertEqual(info["rotation"], 90)

    def test_inventory_sorts_by_capture_time(self):
        make_clip(os.path.join(self.dir, "b.mp4"), 0.5, creation="2026-10-01T10:00:00Z")
        make_clip(os.path.join(self.dir, "a.mp4"), 0.5, creation="2026-10-01T11:00:00Z")
        inv = ingest.build_inventory(self.dir)
        self.assertEqual([i["file"] for i in inv["items"]], ["b.mp4", "a.mp4"])
        self.assertEqual(inv["order_source"], "capture_time")

    def test_inventory_skips_junk_and_accepts_case(self):
        open(os.path.join(self.dir, ".DS_Store"), "w").write("x")
        open(os.path.join(self.dir, "notes.txt"), "w").write("x")
        make_clip(os.path.join(self.dir, "clip one.MOV"), 0.5)
        inv = ingest.build_inventory(self.dir)
        self.assertEqual(len(inv["items"]), 1)
        self.assertEqual(inv["items"][0]["kind"], "video")

    def test_missing_capture_time_falls_back_to_filename(self):
        make_clip(os.path.join(self.dir, "2.mp4"), 0.5)
        make_clip(os.path.join(self.dir, "1.mp4"), 0.5)
        inv = ingest.build_inventory(self.dir)
        self.assertEqual([i["file"] for i in inv["items"]], ["1.mp4", "2.mp4"])
        self.assertEqual(inv["order_source"], "filename")

    def test_unreadable_file_is_skipped_not_fatal(self):
        make_clip(os.path.join(self.dir, "good.mp4"), 0.5)
        open(os.path.join(self.dir, "broken.mp4"), "wb").write(b"not a video")
        open(os.path.join(self.dir, "photo.heic"), "wb").write(b"garbage")
        inv = ingest.build_inventory(self.dir)
        self.assertEqual([i["file"] for i in inv["items"]], ["good.mp4"])
        self.assertEqual(sorted(inv["skipped"]), ["broken.mp4", "photo.heic"])


if __name__ == "__main__":
    unittest.main()
