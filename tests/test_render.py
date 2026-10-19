import os
import tempfile
import unittest

from tests.fixtures import make_clip
import common
import render
from cutlist import Shot


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_render_duration_and_silence(self):
        make_clip(os.path.join(self.dir, "a.mp4"), 3.0, fps=30)
        make_clip(os.path.join(self.dir, "b.mp4"), 3.0, fps=24)
        shots = [Shot("a.mp4", 0.0, 0.4, "hook", 0, 0), Shot("b.mp4", 1.0, 1.0, "opener", 1, 0),
                 Shot("a.mp4", 2.0, 0.6, "action", 1, 1)]
        out = os.path.join(self.dir, "reel.mp4")
        render.render(shots, self.dir, out, (720, 1280))
        info = common.probe(out)
        self.assertAlmostEqual(info["duration"], 2.0, delta=0.04)
        self.assertFalse(info["has_audio"])
        self.assertEqual((info["width"], info["height"]), (720, 1280))

    def test_render_crops_landscape(self):
        make_clip(os.path.join(self.dir, "w.mp4"), 1.0, size=(1280, 720))
        out = os.path.join(self.dir, "reel.mp4")
        render.render([Shot("w.mp4", 0.0, 0.5, "opener", 1, 0)], self.dir, out, (720, 1280))
        info = common.probe(out)
        self.assertEqual((info["width"], info["height"]), (720, 1280))

    def test_output_size_picks_common_vertical(self):
        inv = {"items": [{"file": "a", "kind": "video", "width": 720, "height": 1280},
                         {"file": "b", "kind": "video", "width": 720, "height": 1280},
                         {"file": "c", "kind": "video", "width": 1920, "height": 1080}]}
        self.assertEqual(render.output_size(inv), (720, 1280))
        self.assertEqual(render.output_size({"items": [inv["items"][2]]}), (1080, 1920))


if __name__ == "__main__":
    unittest.main()
