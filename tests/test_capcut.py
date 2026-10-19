import json
import os
import tempfile
import unittest
from unittest import mock

from tests.fixtures import make_clip, SKILL_DIR
import capcut
from cutlist import Shot

TEMPLATE = os.path.join(SKILL_DIR, "assets", "capcut_template")


class CapcutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.media = os.path.join(d, "media"); os.makedirs(self.media)
        self.root = os.path.join(d, "drafts"); os.makedirs(self.root)
        json.dump({"all_draft_store": [], "draft_ids": 0, "root_path": self.root},
                  open(os.path.join(self.root, "root_meta_info.json"), "w"))
        make_clip(os.path.join(self.media, "a.mp4"), 3.0)
        make_clip(os.path.join(self.media, "b.mp4"), 2.0, fps=24)
        self.shots = [Shot("a.mp4", 0.0, 0.4, "hook", 0, 0), Shot("b.mp4", 0.5, 1.0, "opener", 1, 0),
                      Shot("a.mp4", 1.0, 1.5, "action", 1, 1)]

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name="Test Reel"):
        return capcut.write_draft(self.shots, self.media, TEMPLATE, self.root, name, size=(720, 1280),
                                  check_running=False)

    def test_draft_references_resolve(self):
        path = self.write()
        d = json.load(open(os.path.join(path, "draft_info.json")))
        ids = {m["id"] for v in d["materials"].values() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
        segs = d["tracks"][0]["segments"]
        self.assertEqual(len(segs), 3)
        for s in segs:
            self.assertIn(s["material_id"], ids)
            for r in s["extra_material_refs"]:
                self.assertIn(r, ids)
        for a, b in zip(segs, segs[1:]):
            self.assertEqual(b["target_timerange"]["start"], a["target_timerange"]["start"] + a["target_timerange"]["duration"])
        for v in d["materials"]["videos"]:
            self.assertTrue(os.path.exists(os.path.join(path, "Resources", "local", v["material_name"])))
        tl = d["id"]
        raw = open(os.path.join(path, "draft_info.json")).read()
        self.assertEqual(raw, open(os.path.join(path, "template-2.tmp")).read())
        self.assertEqual(raw, open(os.path.join(path, "Timelines", tl, "draft_info.json")).read())

    def test_draft_is_muted(self):
        d = json.load(open(os.path.join(self.write(), "draft_info.json")))
        self.assertTrue(all(s["volume"] == 0.0 for s in d["tracks"][0]["segments"]))

    def test_name_collision_suffix(self):
        self.write("Same")
        second = self.write("Same")
        self.assertTrue(second.endswith("Same (2)"))
        names = [e["draft_name"] for e in json.load(open(os.path.join(self.root, "root_meta_info.json")))["all_draft_store"]]
        self.assertEqual(sorted(names), ["Same", "Same (2)"])

    def test_refuses_when_running(self):
        with mock.patch.object(capcut, "capcut_running", return_value=True):
            with self.assertRaises(RuntimeError):
                capcut.write_draft(self.shots, self.media, TEMPLATE, self.root, "X", size=(720, 1280))

    def test_root_meta_backed_up(self):
        self.write()
        self.assertTrue(os.path.exists(os.path.join(self.root, "root_meta_info.json.bak-edit-reel")))


if __name__ == "__main__":
    unittest.main()
