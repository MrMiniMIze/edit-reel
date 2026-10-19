"""Build inventory.json: every usable media file in a folder, in shooting order."""
import json
import os
import subprocess
import sys
from datetime import datetime

import common


def _sort_key(captured):
    # Normalize mixed offsets ("Z", "-0700") to comparable UTC timestamps.
    s = captured.replace("Z", "+00:00")
    if len(s) > 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s).timestamp()


def build_inventory(media_dir):
    media_dir = os.path.abspath(media_dir)
    items, skipped = [], []
    for name in sorted(os.listdir(media_dir)):
        path = os.path.join(media_dir, name)
        kind = common.media_kind(name)
        if name.startswith(".") or kind is None or not os.path.isfile(path):
            continue
        try:
            info = common.probe(path)
            captured = common.capture_time(path)
        except (subprocess.CalledProcessError, StopIteration, KeyError, ValueError):
            skipped.append(name)  # unreadable or unsupported; don't let one bad file sink the run
            continue
        items.append({"file": name, "kind": kind, "duration": info["duration"], "width": info["width"],
                      "height": info["height"], "fps": info["fps"], "captured": captured})
    videos = [i for i in items if i["kind"] == "video"]
    if videos and all(i["captured"] for i in videos):
        order_source = "capture_time"
        items.sort(key=lambda i: (_sort_key(i["captured"]) if i["captured"] else float("inf"), i["file"]))
    else:
        order_source = "filename"
    return {"media_dir": media_dir, "order_source": order_source, "items": items, "skipped": skipped}


if __name__ == "__main__":
    media_dir, workdir = sys.argv[1], sys.argv[2]
    os.makedirs(workdir, exist_ok=True)
    inv = build_inventory(media_dir)
    with open(os.path.join(workdir, "inventory.json"), "w") as f:
        json.dump(inv, f, indent=1)
    v = sum(i["kind"] == "video" for i in inv["items"])
    print(f"{v} videos, {len(inv['items']) - v} photos, order: {inv['order_source']}")
