"""Write a cut list as a CapCut desktop draft by cloning a CapCut-made template draft.

CapCut 9.6 drafts are plaintext JSON. Times are microseconds. Each segment needs its own
copies of six helper materials, and the same timeline JSON lives in several files.
"""
import copy
import datetime
import json
import os
import plistlib
import re
import shutil
import subprocess
import time
import uuid

import common

US = 1_000_000
HELPERS = ["speeds", "placeholder_infos", "canvases", "sound_channel_mappings", "material_colors", "vocal_separations"]


def capcut_running():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def capcut_version():
    try:
        with open("/Applications/CapCut.app/Contents/Info.plist", "rb") as f:
            return plistlib.load(f).get("CFBundleShortVersionString")
    except OSError:
        return None


def drafts_root():
    return os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")


def draft_problem(root):
    """Why a CapCut project can't be written right now, or None if it can."""
    if capcut_version() is None:
        return "CapCut desktop is not installed (get it from capcut.com); only the mp4 was made"
    if not os.path.exists(os.path.join(root, "root_meta_info.json")):
        return "CapCut has never saved a project here: open CapCut once, then rebuild"
    if capcut_running():
        return "CapCut is running: quit it (Cmd+Q), then rebuild"
    return None


RETOUCH_FLAG = 1 << 26  # set in a clip's check_flag when Retouch > Auto styles is on
RETOUCH_VIDEO_KEYS = ("beauty_face_auto_preset", "beauty_face_auto_preset_infos")
USER_RETOUCH = os.path.expanduser("~/Library/Application Support/edit-reel/retouch.json")
USER_TEMPLATE = os.path.expanduser("~/Library/Application Support/edit-reel/capcut_template")


def template_dir(skill_dir):
    """A template refreshed on this Mac beats the shipped one: it matches the installed CapCut."""
    if os.path.exists(os.path.join(USER_TEMPLATE, "draft_info.json")):
        return USER_TEMPLATE
    return os.path.join(skill_dir, "assets", "capcut_template")


def retouch_path(skill_dir):
    """A retouch style captured on this Mac beats the shipped one."""
    if os.path.exists(USER_RETOUCH):
        return USER_RETOUCH
    return os.path.join(skill_dir, "assets", "retouch_native.json")


def capture_retouch(project_dir):
    """Read the Retouch > Auto styles look off a one-clip CapCut project, minus anything tied to this Mac."""
    info = json.load(open(os.path.join(project_dir, "draft_info.json")))
    videos = info["materials"].get("videos") or []
    effects = info["materials"].get("effects") or []
    if not videos or not effects or not (videos[0].get("beauty_face_auto_preset") or {}).get("name"):
        raise ValueError(f"'{os.path.basename(project_dir)}' has no Retouch auto style. In CapCut, select the clip, "
                         "open Video > Retouch, pick a look under Auto styles, quit CapCut (Cmd+Q), and try again.")
    clean, placeholder = [], ""
    for e in effects:
        e = copy.deepcopy(e)
        e.pop("id", None)
        e["request_id"] = ""
        # The downloaded effect lives in CapCut's cache under the user's home; keep it home-relative.
        cache = e.get("path", "").find("/Movies/CapCut/")
        e["path"] = "~" + e["path"][cache:] if cache >= 0 else ""
        algo = e.get("algorithm_artifact_path", "")
        if "_draftpath_placeholder_" in algo:
            placeholder = algo.split("/video/")[0]
        e["algorithm_artifact_path"] = ""  # CapCut's face data for one clip; rebuilt per clip
        clean.append(e)
    v = videos[0]
    return {"name": v["beauty_face_auto_preset"]["name"], "capcut_version": capcut_version(),
            "draft_placeholder": placeholder,
            "video": {k: copy.deepcopy(v[k]) for k in RETOUCH_VIDEO_KEYS if k in v}, "effects": clean}


def _template_problem(project_dir):
    try:
        info = json.load(open(os.path.join(project_dir, "draft_info.json")))
        meta = json.load(open(os.path.join(project_dir, "draft_meta_info.json")))
    except (OSError, ValueError) as e:
        return f"its project files can't be read ({e})"
    videos = info.get("materials", {}).get("videos") or []
    tracks = info.get("tracks") or []
    if len(videos) != 1 or not tracks or not tracks[0].get("segments"):
        return "it needs exactly one video clip on the timeline"
    if not os.path.isdir(os.path.join(project_dir, "Timelines", info.get("id", ""))):
        return "its timeline folder is missing"
    if "draft_id" not in meta or not meta.get("draft_materials"):
        return "its project info is incomplete"
    return None


def refresh_template(project_dir, dst):
    """Turn a one-clip project made by the installed CapCut into a clean template at dst."""
    problem = _template_problem(project_dir)
    if problem:
        raise ValueError(f"'{os.path.basename(project_dir)}' can't be used as a template: {problem}. In CapCut, "
                         "make a new project, add one video clip to the timeline, quit CapCut (Cmd+Q), and try again.")
    tmp = dst + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(project_dir, tmp, ignore=shutil.ignore_patterns("*.bak", "TEMPLATE_INFO.json"))
    local = os.path.join(tmp, "Resources", "local")
    for f in os.listdir(local) if os.path.isdir(local) else []:
        os.remove(os.path.join(local, f))
    clip = json.load(open(os.path.join(tmp, "draft_info.json")))["materials"]["videos"][0]["material_name"]
    # Keep nothing that identifies the Mac, its user, or the clip.
    subs = [(re.compile(r'"(device_id|hard_disk_id|mac_address)":"[^"]*"'), r'"\1":""'),
            (re.compile(r'"/Users/[^"]*"'), '""'),
            (re.compile(r'"draft_name":"[^"]*"'), '"draft_name":"template"'),
            (re.compile(re.escape(json.dumps(clip))), json.dumps("clip" + os.path.splitext(clip)[1]))]
    for dp, _, fs in os.walk(tmp):
        for f in fs:
            p = os.path.join(dp, f)
            if f == "mini_draft.json":  # cached patches would replay the old timeline
                os.remove(p)
                continue
            if f == "draft_cover.jpg":
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                                "color=c=black:s=1080x1920", "-frames:v", "1", p], check=True)
                continue
            try:
                text = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            new = text
            for pattern, repl in subs:
                new = pattern.sub(repl, new)
            if new != text:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(new)
    _write_json(os.path.join(tmp, "TEMPLATE_INFO.json"),
                {"capcut_version": capcut_version(), "made": datetime.date.today().isoformat(),
                 "source": "refreshed from a one-clip CapCut project; machine IDs, paths and media removed"})
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    os.rename(tmp, dst)
    return dst


def _uid():
    return str(uuid.uuid4()).upper()


def _free_name(root, name):
    candidate, n = name, 1
    while os.path.exists(os.path.join(root, candidate)):
        n += 1
        candidate = f"{name} ({n})"
    return candidate


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def _build_timeline(info, shots, media_dir, size, dst, retouch=None):
    tvid = info["materials"]["videos"][0]
    if "_draftpath_placeholder_" in tvid["path"]:
        draft_ref = tvid["path"].split("/Resources/")[0]
    else:
        draft_ref = (retouch or {}).get("draft_placeholder") or dst
    # CapCut either copies clips into the project (a "##_draftpath_placeholder_<id>_##/Resources/..." path)
    # or links them in place (an absolute path). Follow the template; clips are copied into dst either way.
    if "_draftpath_placeholder_" in tvid["path"]:
        local = tvid["path"].split("/Resources/")[0] + "/Resources/local"
    else:
        local = os.path.join(dst, "Resources", "local")
    # Clone only the helper kinds this CapCut version actually uses.
    tmpl_help = {k: info["materials"][k][0] for k in HELPERS if info["materials"].get(k)}
    tseg = info["tracks"][0]["segments"][0]

    videos, by_src = [], {}
    for src in dict.fromkeys(s.src for s in shots):
        p = common.probe(os.path.join(media_dir, src))
        v = copy.deepcopy(tvid)
        v.update(id=_uid(), unique_id=uuid.uuid4().hex, duration=int(p["duration"] * US), width=p["width"],
                 height=p["height"], has_audio=p["has_audio"], material_name=src,
                 path=f"{local}/{src}", local_material_id=str(uuid.uuid4()))
        if retouch:
            v.update(copy.deepcopy(retouch["video"]))
            v["check_flag"] = v.get("check_flag", 0) | RETOUCH_FLAG
        videos.append(v)
        by_src[src] = v

    helpers = {k: [] for k in tmpl_help}
    segments, t, effects = [], 0, []
    for s in shots:
        refs = []
        for k in tmpl_help:
            m = copy.deepcopy(tmpl_help[k])
            m["id"] = _uid()
            if k == "speeds":
                m["speed"] = s.speed
            helpers[k].append(m)
            refs.append(m["id"])
        v = by_src[s.src]
        if retouch:  # each cut gets its own copies, placed after the first three helpers as CapCut does
            mine = []
            for e in retouch["effects"]:
                e = copy.deepcopy(e)
                e.update(id=_uid(), path=os.path.expanduser(e["path"]) if e["path"] else "",
                         algorithm_artifact_path=f"{draft_ref}/video/figure_algorithm/{v['id']}")
                mine.append(e)
            effects += mine
            refs = refs[:3] + [e["id"] for e in mine] + refs[3:]
        src_in = int(round(s.src_in * US))
        dur = min(int(round(s.dur * US)), v["duration"] - src_in)
        vol = 1.0 if s.role == "talk" else 0.0  # talking to camera keeps its sound; the rest waits for voiceover
        seg = copy.deepcopy(tseg)
        seg.update(id=_uid(), material_id=v["id"], extra_material_refs=refs, speed=s.speed,
                   volume=vol, last_nonzero_volume=vol,
                   source_timerange={"start": src_in, "duration": int(dur * s.speed)},
                   target_timerange={"start": t, "duration": dur})
        segments.append(seg)
        t += dur

    info["id"] = _uid()
    info["duration"] = t
    info["canvas_config"].update(ratio="original", width=size[0], height=size[1])
    info["materials"]["videos"] = videos
    info["materials"].update(helpers)
    info["materials"]["effects"] = effects
    info["tracks"] = [dict(info["tracks"][0], segments=segments)]
    return info, videos


def write_draft(shots, media_dir, template_dir, root, name, size, check_running=True, retouch=None):
    if check_running and capcut_running():
        raise RuntimeError("CapCut is running — quit it (Cmd+Q) and retry")
    name = _free_name(root, name)
    dst = os.path.join(root, name)
    root_meta_path = os.path.join(root, "root_meta_info.json")
    with open(root_meta_path, "rb") as f:
        original_root_meta = f.read()
    try:
        return _write(shots, media_dir, template_dir, root, name, dst, size, root_meta_path, retouch)
    except BaseException:
        # A half-written project shows up in CapCut as broken, so undo everything.
        shutil.rmtree(dst, ignore_errors=True)
        with open(root_meta_path, "rb") as f:
            changed = f.read() != original_root_meta
        if changed:
            with open(root_meta_path, "wb") as f:
                f.write(original_root_meta)
        raise


def _write(shots, media_dir, template_dir, root, name, dst, size, root_meta_path, retouch):
    shutil.copytree(template_dir, dst, ignore=shutil.ignore_patterns("TEMPLATE_INFO.json", "*.bak"))

    info = json.load(open(os.path.join(template_dir, "draft_info.json")))
    meta = json.load(open(os.path.join(template_dir, "draft_meta_info.json")))
    old_tl, old_draft = info["id"], meta["draft_id"]
    info, videos = _build_timeline(info, shots, media_dir, size, dst, retouch)
    new_tl, new_draft = info["id"], _uid()

    os.rename(os.path.join(dst, "Timelines", old_tl), os.path.join(dst, "Timelines", new_tl))
    for rel in ["", f"Timelines/{new_tl}/"]:  # cached patches would replay the template's timeline
        if os.path.exists(os.path.join(dst, rel, "attachment/patch/mini_draft.json")):
            os.remove(os.path.join(dst, rel, "attachment/patch/mini_draft.json"))
    os.makedirs(os.path.join(dst, "Resources", "local"), exist_ok=True)
    for src in dict.fromkeys(s.src for s in shots):
        shutil.copy2(os.path.join(media_dir, src), os.path.join(dst, "Resources", "local", src))

    blob = json.dumps(info, ensure_ascii=False, separators=(",", ":"))
    for rel in ["draft_info.json", "template-2.tmp", f"Timelines/{new_tl}/draft_info.json",
                f"Timelines/{new_tl}/template-2.tmp"]:
        with open(os.path.join(dst, rel), "w") as f:
            f.write(blob)
    for rel in ["Timelines/project.json", "timeline_layout.json"]:
        p = os.path.join(dst, rel)
        if os.path.exists(p):
            text = open(p).read().replace(old_tl, new_tl).replace(old_draft, new_draft)
            with open(p, "w") as f:
                f.write(text)

    now, now_us = int(time.time()), int(time.time() * US)
    mats = [{"ai_group_type": "", "create_time": now, "duration": v["duration"], "enter_from": 0,
             "extra_info": v["material_name"], "file_Path": f"./Resources/local/{v['material_name']}",
             "height": v["height"], "id": v["local_material_id"], "import_time": now, "import_time_ms": now_us,
             "item_source": 1, "material_color_tag": "", "md5": "", "metetype": "video",
             "roughcut_time_range": {"duration": v["duration"], "start": 0},
             "sub_time_range": {"duration": -1, "start": -1}, "type": 0, "width": v["width"]} for v in videos]
    meta.update(draft_id=new_draft, draft_name=name, draft_fold_path=dst, draft_root_path=root,
                tm_duration=info["duration"], tm_draft_create=now_us, tm_draft_modified=now_us,
                draft_materials_copied_info=[{"dst_path": f"Resources/local/{v['material_name']}",
                                              "src_path": os.path.abspath(os.path.join(media_dir, v["material_name"]))}
                                             for v in videos])
    meta["draft_materials"][0]["value"] = mats
    _write_json(os.path.join(dst, "draft_meta_info.json"), meta)

    shutil.copy2(root_meta_path, root_meta_path + ".bak-edit-reel")
    root_meta = json.load(open(root_meta_path))
    entry = {k: meta.get(k, "") for k in ("cloud_draft_cover", "cloud_draft_sync", "draft_cloud_last_action_download",
                                          "draft_cloud_purchase_info", "draft_cloud_template_id",
                                          "draft_cloud_tutorial_info", "draft_cloud_videocut_purchase_info",
                                          "draft_is_ai_shorts", "draft_is_cloud_temp_draft",
                                          "draft_is_invisible", "draft_type", "tm_draft_cloud_completed",
                                          "tm_draft_cloud_entry_id", "tm_draft_cloud_modified",
                                          "tm_draft_cloud_parent_entry_id", "tm_draft_cloud_space_id",
                                          "tm_draft_cloud_user_id", "tm_draft_removed")}
    entry.update(draft_cover=os.path.join(dst, "draft_cover.jpg"), draft_fold_path=dst, draft_id=new_draft,
                 draft_json_file=os.path.join(dst, "draft_info.json"), draft_name=name, draft_new_version="",
                 draft_root_path=root, draft_timeline_materials_size=0, streaming_edit_draft_ready=True,
                 tm_draft_create=now_us, tm_draft_modified=now_us, tm_duration=info["duration"])
    root_meta["all_draft_store"].insert(0, entry)
    root_meta["draft_ids"] = len(root_meta["all_draft_store"])
    _write_json(root_meta_path, root_meta)
    return dst
