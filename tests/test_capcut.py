import json
import os
import shutil
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

    def test_talk_keeps_its_sound(self):
        self.shots.append(Shot("b.mp4", 0.0, 1.0, "talk", 1, 0))
        segs = json.load(open(os.path.join(self.write(), "draft_info.json")))["tracks"][0]["segments"]
        self.assertEqual([s["volume"] for s in segs], [0.0, 0.0, 0.0, 1.0])

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

    def test_failed_write_leaves_nothing_behind(self):
        root_meta = open(os.path.join(self.root, "root_meta_info.json")).read()
        real_copy = capcut.shutil.copy2

        def disk_full(src, dst, *a, **k):
            if src.endswith("b.mp4"):
                raise OSError(28, "No space left on device")
            return real_copy(src, dst, *a, **k)

        with mock.patch("capcut.shutil.copy2", side_effect=disk_full):
            with self.assertRaises(OSError):
                self.write("Broken")
        self.assertEqual(sorted(os.listdir(self.root)), ["root_meta_info.json"])
        self.assertEqual(open(os.path.join(self.root, "root_meta_info.json")).read(), root_meta)

    def test_failed_root_meta_write_is_restored(self):
        root_meta = open(os.path.join(self.root, "root_meta_info.json")).read()
        real_write = capcut._write_json

        def fail_on_root(path, data):
            if path.endswith("root_meta_info.json"):
                with open(path, "w") as f:
                    f.write("{trunc")
                raise OSError(28, "No space left on device")
            return real_write(path, data)

        with mock.patch("capcut._write_json", side_effect=fail_on_root):
            with self.assertRaises(OSError):
                self.write("Broken")
        self.assertEqual(open(os.path.join(self.root, "root_meta_info.json")).read(), root_meta)
        self.assertFalse(os.path.exists(os.path.join(self.root, "Broken")))

    def test_root_meta_backed_up(self):
        self.write()
        self.assertTrue(os.path.exists(os.path.join(self.root, "root_meta_info.json.bak-edit-reel")))


class RefreshTemplateTests(unittest.TestCase):
    """A CapCut update can break the shipped template; anyone can rebuild it from a fresh one-clip project."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.project = os.path.join(d, "drafts", "My Project")
        shutil.copytree(TEMPLATE, self.project)
        os.remove(os.path.join(self.project, "TEMPLATE_INFO.json"))
        # What CapCut leaves in a real project: the clip, backups, this Mac's IDs and paths.
        os.makedirs(os.path.join(self.project, "Resources", "local"), exist_ok=True)  # git drops empty folders
        open(os.path.join(self.project, "Resources", "local", "IMG_0001.MOV"), "wb").write(b"video")
        open(os.path.join(self.project, "draft_info.json.bak"), "w").write("{}")
        info_path = os.path.join(self.project, "draft_info.json")
        raw = open(info_path).read().replace('"device_id":""', '"device_id":"0123abcd"', 1)
        raw = raw.replace('"material_name":"clip.MP4"', '"material_name":"IMG_0001.MOV"')
        open(info_path, "w").write(raw)
        meta_path = os.path.join(self.project, "draft_meta_info.json")
        meta = json.load(open(meta_path))
        meta["draft_fold_path"] = "/Users/someone/Movies/CapCut/My Project"
        json.dump(meta, open(meta_path, "w"))
        self.out = os.path.join(d, "template")

    def tearDown(self):
        self.tmp.cleanup()

    def refresh(self):
        with mock.patch("capcut.capcut_version", return_value="9.9.9"):
            return capcut.refresh_template(self.project, self.out)

    def test_refreshed_template_is_clean_and_versioned(self):
        self.refresh()
        self.assertEqual(json.load(open(os.path.join(self.out, "TEMPLATE_INFO.json")))["capcut_version"], "9.9.9")
        self.assertEqual(os.listdir(os.path.join(self.out, "Resources", "local")), [])
        for dp, _, fs in os.walk(self.out):
            for f in fs:
                self.assertFalse(f.endswith(".bak"), f)
                if f.endswith((".json", ".tmp")):
                    text = open(os.path.join(dp, f)).read()
                    for leak in ("/Users/", "0123abcd", "IMG_0001"):
                        self.assertNotIn(leak, text, f"{leak} in {f}")

    def test_refreshed_template_builds_a_draft(self):
        self.refresh()
        media = os.path.join(self.tmp.name, "media"); os.makedirs(media)
        make_clip(os.path.join(media, "a.mp4"), 2.0)
        root = os.path.join(self.tmp.name, "drafts")
        json.dump({"all_draft_store": [], "draft_ids": 0}, open(os.path.join(root, "root_meta_info.json"), "w"))
        path = capcut.write_draft([Shot("a.mp4", 0.0, 1.0, "opener", 1, 0)], media, self.out, root, "R",
                                  size=(720, 1280), check_running=False)
        d = json.load(open(os.path.join(path, "draft_info.json")))
        self.assertEqual(d["materials"]["videos"][0]["material_name"], "a.mp4")

    def test_project_linking_its_clip_in_place_works(self):
        # CapCut can link the original file instead of copying it into the project.
        info_path = os.path.join(self.project, "draft_info.json")
        info = json.load(open(info_path))
        info["materials"]["videos"][0]["path"] = "/Users/someone/Desktop/IMG_0001.MOV"
        json.dump(info, open(info_path, "w"))
        shutil.rmtree(os.path.join(self.project, "Resources", "local"))  # such projects have no local folder
        self.refresh()
        media = os.path.join(self.tmp.name, "media"); os.makedirs(media)
        make_clip(os.path.join(media, "a.mp4"), 2.0)
        root = os.path.join(self.tmp.name, "drafts")
        json.dump({"all_draft_store": [], "draft_ids": 0}, open(os.path.join(root, "root_meta_info.json"), "w"))
        path = capcut.write_draft([Shot("a.mp4", 0.0, 1.0, "opener", 1, 0)], media, self.out, root, "R",
                                  size=(720, 1280), check_running=False)
        v = json.load(open(os.path.join(path, "draft_info.json")))["materials"]["videos"][0]
        self.assertEqual(v["path"], os.path.join(path, "Resources", "local", "a.mp4"))
        self.assertTrue(os.path.exists(v["path"]))

    def test_project_without_a_clip_is_refused(self):
        info_path = os.path.join(self.project, "draft_info.json")
        info = json.load(open(info_path))
        info["materials"]["videos"] = []
        json.dump(info, open(info_path, "w"))
        with self.assertRaises(ValueError) as e:
            self.refresh()
        self.assertIn("one video clip", str(e.exception))
        self.assertFalse(os.path.exists(self.out))

    def test_build_prefers_a_refreshed_template(self):
        with mock.patch("capcut.USER_TEMPLATE", self.out):
            self.assertEqual(capcut.template_dir(SKILL_DIR), os.path.join(SKILL_DIR, "assets", "capcut_template"))
            self.refresh()
            self.assertEqual(capcut.template_dir(SKILL_DIR), self.out)


def fake_retouched_project(dst):
    """A one-clip project as CapCut leaves it after Retouch > Auto styles (two effects stand in for 19)."""
    shutil.copytree(TEMPLATE, dst)
    info_path = os.path.join(dst, "draft_info.json")
    info = json.load(open(info_path))
    v = info["materials"]["videos"][0]
    v["beauty_face_auto_preset"] = {"preset_id": "747", "name": "Native", "rate_map": "{}", "scene": ""}
    v["beauty_face_auto_preset_infos"] = [{"face_id": "0", "preset_id": "747", "rate_map": "", "resources_id_list": []}]
    v["check_flag"] = v["check_flag"] | capcut.RETOUCH_FLAG
    placeholder = v["path"].split("/Resources/")[0]
    effects = [{"id": f"E{k}", "resource_id": str(k), "name": n, "type": "figure", "value": 0.0,
                "path": f"/Users/someone/Movies/CapCut/User Data/Cache/effect/{k}/abc",
                "algorithm_artifact_path": f"{placeholder}/video/figure_algorithm/{v['id']}",
                "request_id": "req", "beauty_face_auto_preset_id": "747"} for k, n in enumerate(["Smooth", "Slim"])]
    info["materials"]["effects"] = effects
    seg = info["tracks"][0]["segments"][0]
    seg["extra_material_refs"] = seg["extra_material_refs"][:3] + [e["id"] for e in effects] + seg["extra_material_refs"][3:]
    json.dump(info, open(info_path, "w"))
    return dst


class RetouchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.media = os.path.join(d, "media"); os.makedirs(self.media)
        self.root = os.path.join(d, "drafts"); os.makedirs(self.root)
        json.dump({"all_draft_store": [], "draft_ids": 0}, open(os.path.join(self.root, "root_meta_info.json"), "w"))
        make_clip(os.path.join(self.media, "a.mp4"), 3.0)
        make_clip(os.path.join(self.media, "b.mp4"), 2.0)
        self.shots = [Shot("a.mp4", 0.0, 0.4, "hook", 0, 0), Shot("b.mp4", 0.5, 1.0, "opener", 1, 0),
                      Shot("a.mp4", 1.0, 1.5, "action", 1, 1)]

    def tearDown(self):
        self.tmp.cleanup()

    def test_capture_keeps_the_style_and_drops_this_mac(self):
        project = fake_retouched_project(os.path.join(self.tmp.name, "proj"))
        preset = capcut.capture_retouch(project)
        self.assertEqual(preset["name"], "Native")
        self.assertEqual([e["name"] for e in preset["effects"]], ["Smooth", "Slim"])
        raw = json.dumps(preset)
        for leak in ("/Users/", "someone", '"req"', '"E0"'):
            self.assertNotIn(leak, raw)
        self.assertTrue(preset["effects"][0]["path"].startswith("~/Movies/CapCut/"))

    def test_capture_refuses_a_project_without_retouch(self):
        with self.assertRaises(ValueError) as e:
            capcut.capture_retouch(TEMPLATE)
        self.assertIn("Retouch", str(e.exception))

    def write(self, retouch):
        return capcut.write_draft(self.shots, self.media, TEMPLATE, self.root, "R", size=(720, 1280),
                                  check_running=False, retouch=retouch)

    def test_retouch_goes_on_every_cut(self):
        preset = capcut.capture_retouch(fake_retouched_project(os.path.join(self.tmp.name, "proj")))
        d = json.load(open(os.path.join(self.write(preset), "draft_info.json")))
        effects = {e["id"]: e for e in d["materials"]["effects"]}
        self.assertEqual(len(effects), 2 * len(self.shots))  # each cut gets its own copies
        videos = {v["id"]: v for v in d["materials"]["videos"]}
        for v in videos.values():
            self.assertEqual(v["beauty_face_auto_preset"]["name"], "Native")
            self.assertTrue(v["check_flag"] & capcut.RETOUCH_FLAG)
        for seg in d["tracks"][0]["segments"]:
            mine = [effects[r] for r in seg["extra_material_refs"] if r in effects]
            self.assertEqual([e["name"] for e in mine], ["Smooth", "Slim"])
            for e in mine:
                self.assertTrue(e["algorithm_artifact_path"].endswith(f"/video/figure_algorithm/{seg['material_id']}"))
                self.assertEqual(e["path"], os.path.expanduser(
                    f"~/Movies/CapCut/User Data/Cache/effect/{e['resource_id']}/abc"))

    def test_no_retouch_means_no_effects(self):
        d = json.load(open(os.path.join(self.write(None), "draft_info.json")))
        self.assertEqual(d["materials"].get("effects", []), [])
        self.assertTrue(all(not v["check_flag"] & capcut.RETOUCH_FLAG for v in d["materials"]["videos"]))


if __name__ == "__main__":
    unittest.main()
