import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests.fixtures import make_clip, SKILL_DIR
import common
from cutlist import Shot, save

SCRIPTS = os.path.join(SKILL_DIR, "scripts")


class E2ETests(unittest.TestCase):
    def test_pipeline_on_synthetic_folder(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            for n in range(4):
                make_clip(os.path.join(media, f"c{n}.mp4"), 3.0, creation=f"2026-10-01T1{n}:00:00Z")
            out = os.path.join(d, "out")
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "prepare.py"), media, "--out", out],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.exists(os.path.join(out, "sheets", "sheets.json")))
            shots = [Shot("c3.mp4", 1.0, 0.4, "hook", 0, 0)]
            for stop, src in ((1, "c0.mp4"), (2, "c2.mp4")):
                shots += [Shot(src, 0.0, 1.0, "opener", stop, 0), Shot(src, 1.0, 0.8, "action", stop, 1),
                          Shot(src, 2.0, 0.6, "action", stop, 2)]
            save(shots, os.path.join(out, "cutlist.json"), target=60)
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build.py"), out, "--no-capcut"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            info = common.probe(os.path.join(out, "reel.mp4"))
            self.assertFalse(info["has_audio"])
            self.assertAlmostEqual(info["duration"], sum(s.dur for s in shots), delta=0.05)
            self.assertTrue(os.path.exists(os.path.join(out, "cutlist.final.json")))

    def test_build_rejects_invalid_cutlist(self):
        with tempfile.TemporaryDirectory() as d:
            media = os.path.join(d, "media"); os.makedirs(media)
            make_clip(os.path.join(media, "c0.mp4"), 1.0)
            out = os.path.join(d, "out")
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "prepare.py"), media, "--out", out], check=True,
                           capture_output=True)
            save([Shot("missing.mp4", 0, 1, "opener", 1, 0)], os.path.join(out, "cutlist.json"))
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build.py"), out, "--no-capcut"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("unknown src", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
