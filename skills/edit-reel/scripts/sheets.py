"""Labeled contact sheets of sampled frames, for Claude to look at when picking moments."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
TILE_W, TILE_H = 240, 426


def _clip_times(dur, fps):
    times = [round(k / fps, 2) for k in range(int(dur * fps) + 1) if k / fps < dur - 0.05]
    if len(times) < 2:
        times = [0.0, round(dur / 2, 2)]
    return times


def sample_times(inv, max_frames, base_fps):
    videos = [i for i in inv["items"] if i["kind"] == "video"]
    fps = base_fps
    while True:
        times = {v["file"]: _clip_times(v["duration"], fps) for v in videos}
        total = sum(len(t) for t in times.values())
        if total <= max_frames or fps < 0.05:
            return times
        fps *= max(0.5, min(0.95, max_frames / total))


def _usable_at(item, t):
    samples = item.get("samples") or []
    if not samples:
        return True
    return min(samples, key=lambda s: abs(s["t"] - t))["usable"]


def _frame(src, t, label, usable, out):
    # textfile= sidesteps filter escaping, so quotes, colons and % in filenames are safe.
    label_file = out + ".txt"
    with open(label_file, "w") as f:
        f.write(label)
    vf = (f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=decrease,"
          f"pad={TILE_W}:{TILE_H}:(ow-iw)/2:(oh-ih)/2,")
    if not usable:
        vf += "drawbox=c=red:t=8,"
    vf += (f"drawtext=fontfile={FONT}:textfile={label_file}:expansion=none:x=6:y=h-th-8:fontsize=18:"
           f"fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", src,
                    "-frames:v", "1", "-vf", vf, out], check=True)
    os.remove(label_file)


def make_sheets(inv, times, outdir, cols, rows):
    os.makedirs(outdir, exist_ok=True)
    by_file = {i["file"]: i for i in inv["items"]}
    frames = [{"file": f, "t": t, "usable": _usable_at(by_file[f], t)}
              for f in [i["file"] for i in inv["items"] if i["file"] in times] for t in times[f]]
    per = cols * rows
    index = []
    for n in range(0, len(frames), per):
        chunk = frames[n:n + per]
        name = f"sheet_{n // per + 1:03d}.jpg"
        tmp = tempfile.mkdtemp()
        try:
            for k, fr in enumerate(chunk):
                label = f"{os.path.splitext(fr['file'])[0]} @ {fr['t']:.1f}" + ("" if fr["usable"] else " X")
                _frame(os.path.join(inv["media_dir"], fr["file"]), fr["t"], label, fr["usable"],
                       os.path.join(tmp, f"{k:04d}.png"))
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "1",
                            "-i", os.path.join(tmp, "%04d.png"), "-vf", f"tile={cols}x{rows}:padding=4",
                            "-frames:v", "1", "-q:v", "3", os.path.join(outdir, name)], check=True)
        finally:
            shutil.rmtree(tmp)
        index.append({"sheet": name, "frames": chunk})
    with open(os.path.join(outdir, "sheets.json"), "w") as f:
        json.dump(index, f, indent=1)
    return index


if __name__ == "__main__":
    workdir, style_path = sys.argv[1], sys.argv[2]
    sh = json.load(open(style_path))["sheets"]
    inv = json.load(open(os.path.join(workdir, "inventory.json")))
    idx = make_sheets(inv, sample_times(inv, sh["max_frames"], sh["base_fps"]),
                      os.path.join(workdir, "sheets"), sh["cols"], sh["rows"])
    print(f"{len(idx)} sheets, {sum(len(s['frames']) for s in idx)} frames")
