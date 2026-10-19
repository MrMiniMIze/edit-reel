"""Per-sample quality screening: blur and brightness, so unusable frames can be avoided."""
import json
import os
import re
import subprocess
import sys

import common


def sample_quality(path, fps):
    """One ffmpeg pass; returns [{t, blur, luma}] for frames sampled at `fps`."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-an",
         "-vf", f"{common.grid_select(1 / fps)},scale=360:-2,blurdetect,signalstats,metadata=print:file=-",
         "-fps_mode", "passthrough", "-f", "null", "-"],
        capture_output=True, text=True, check=True).stdout
    samples, cur = [], None
    for line in out.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            cur = {"t": round(float(m.group(1)), 3), "blur": 0.0, "luma": 0.0}
            samples.append(cur)
        elif cur is not None and line.startswith("lavfi.blur="):
            cur["blur"] = round(float(line.split("=")[1]), 3)
        elif cur is not None and line.startswith("lavfi.signalstats.YAVG="):
            cur["luma"] = round(float(line.split("=")[1]), 2)
    return samples


def mark_usable(samples, blur_max, luma_min):
    for s in samples:
        s["usable"] = s["blur"] <= blur_max and s["luma"] >= luma_min
    return samples


def screen_inventory(inv, style):
    sc = style["screen"]
    for item in inv["items"]:
        if item["kind"] != "video":
            continue
        path = os.path.join(inv["media_dir"], item["file"])
        item["samples"] = mark_usable(sample_quality(path, sc["fps"]), sc["blur_max"], sc["luma_min"])
    return inv


if __name__ == "__main__":
    workdir, style_path = sys.argv[1], sys.argv[2]
    inv_path = os.path.join(workdir, "inventory.json")
    inv = screen_inventory(json.load(open(inv_path)), json.load(open(style_path)))
    with open(inv_path, "w") as f:
        json.dump(inv, f, indent=1)
    bad = sum(not s["usable"] for i in inv["items"] for s in i.get("samples", []))
    print(f"screened; {bad} unusable samples")
