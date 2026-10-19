"""Render a cut list to a silent vertical mp4 with ffmpeg."""
import os
import subprocess
from collections import Counter


def output_size(inv):
    sizes = Counter((i["width"], i["height"]) for i in inv["items"] if i["kind"] == "video")
    w, h = sizes.most_common(1)[0][0]
    if w > h:
        w, h = h, w
    return w - w % 2, h - h % 2


def render(shots, media_dir, out_path, size, fps=30):
    w, h = size
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    chains = []
    for n, s in enumerate(shots):
        args += ["-ss", f"{s.src_in:.4f}", "-t", f"{s.dur:.4f}", "-i", os.path.join(media_dir, s.src)]
        chains.append(f"[{n}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},"
                      f"setsar=1,trim=duration={s.dur:.4f},setpts=PTS-STARTPTS[v{n}];")
    graph = "".join(chains) + "".join(f"[v{n}]" for n in range(len(shots))) + f"concat=n={len(shots)}:v=1:a=0[v]"
    args += ["-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-crf", "18", "-preset", "fast",
             "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", out_path]
    subprocess.run(args, check=True)
