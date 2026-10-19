"""Labeled contact sheets of sampled frames, for Claude to look at when picking moments."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import common

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


PAD = (f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=decrease,"
       f"pad={TILE_W}:{TILE_H}:(ow-iw)/2:(oh-ih)/2")


def _seek_frame(src, t, out):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", src,
                    "-frames:v", "1", "-vf", PAD, out], check=True)


def _grid_step(times):
    """The spacing if times are an even grid from 0 (what sample_times makes), else None."""
    if len(times) < 2 or times[0] != 0:
        return None
    step = times[-1] / (len(times) - 1)
    if step <= 0 or any(abs(x - k * step) > 0.011 for k, x in enumerate(times)):  # times are rounded to 0.01
        return None
    return step


def extract_frames(src, times, outdir):
    """Unlabeled tiles of src at each time, decoding the clip once; returns PNG paths in order."""
    paths = []
    step = _grid_step(times)
    if step:
        # One pass over the clip picks every grid frame; drop any picked past our last time.
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-an",
                        "-vf", f"{common.grid_select(step)},{PAD}", "-fps_mode", "passthrough",
                        os.path.join(outdir, "f%04d.png")], check=True)
        paths = sorted(os.path.join(outdir, f) for f in os.listdir(outdir) if f.startswith("f") and f.endswith(".png"))
        for extra in paths[len(times):]:
            os.remove(extra)
        paths = paths[:len(times)]
    if len(paths) != len(times):  # irregular times or a short read: one seek per frame instead
        for f in paths:
            os.remove(f)
        paths = [os.path.join(outdir, f"f{k + 1:04d}.png") for k in range(len(times))]
        for x, out in zip(times, paths):
            _seek_frame(src, x, out)
    return paths


def _tile_sheet(tiles, labels, usable, out, cols, rows, tmp):
    """Label every tile and lay them out in one ffmpeg run."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    chains = []
    for k, (tile, label, ok) in enumerate(zip(tiles, labels, usable)):
        # textfile= with expansion=none draws quotes, colons and % in filenames literally.
        label_file = os.path.join(tmp, f"label{k}.txt")
        with open(label_file, "w") as f:
            f.write(label)
        cmd += ["-i", tile]
        box = "" if ok else "drawbox=c=red:t=8,"
        chains.append(f"[{k}:v]{box}drawtext=fontfile={FONT}:textfile={label_file}:expansion=none:x=6:y=h-th-8:"
                      f"fontsize=18:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4[v{k}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{k}]" for k in range(len(tiles))) + \
        f"concat=n={len(tiles)}:v=1:a=0,tile={cols}x{rows}:padding=4"
    subprocess.run(cmd + ["-filter_complex", graph, "-frames:v", "1", "-q:v", "3", out], check=True)


def make_sheets(inv, times, outdir, cols, rows):
    os.makedirs(outdir, exist_ok=True)
    by_file = {i["file"]: i for i in inv["items"]}
    order = [i["file"] for i in inv["items"] if i["file"] in times]
    frames = [{"file": f, "t": t, "usable": _usable_at(by_file[f], t)} for f in order for t in times[f]]
    per = cols * rows
    index = []
    tmp = tempfile.mkdtemp()
    try:
        dirs = [os.path.join(tmp, f"clip{n}") for n in range(len(order))]
        for d in dirs:
            os.makedirs(d)
        # Each ffmpeg run is mostly single-threaded work on small frames, so run several at once.
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
            tiles = [p for ps in pool.map(lambda fd: extract_frames(os.path.join(inv["media_dir"], fd[0]),
                                                                   times[fd[0]], fd[1]), zip(order, dirs))
                     for p in ps]
            jobs = []
            for n in range(0, len(frames), per):
                chunk = frames[n:n + per]
                name = f"sheet_{n // per + 1:03d}.jpg"
                labels = [f"{os.path.splitext(fr['file'])[0]} @ {fr['t']:.1f}" + ("" if fr["usable"] else " X")
                          for fr in chunk]
                sheet_tmp = os.path.join(tmp, f"sheet{n // per}")
                os.makedirs(sheet_tmp)
                jobs.append(pool.submit(_tile_sheet, tiles[n:n + per], labels, [fr["usable"] for fr in chunk],
                                        os.path.join(outdir, name), cols, rows, sheet_tmp))
                index.append({"sheet": name, "frames": chunk})
            for j in jobs:
                j.result()
    finally:
        shutil.rmtree(tmp)
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
