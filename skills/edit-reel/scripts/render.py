"""Render a cut list to a vertical mp4 with ffmpeg: silent, except talking-to-camera shots keep their sound."""
import os
import subprocess
from collections import Counter

import common


def output_size(inv):
    sizes = Counter((i["width"], i["height"]) for i in inv["items"] if i["kind"] == "video")
    w, h = sizes.most_common(1)[0][0]
    if w > h:
        w, h = h, w
    return w - w % 2, h - h % 2


def render(shots, media_dir, out_path, size, fps=30):
    """Silent unless there are talk shots; then talk keeps its sound and everything else is silence."""
    w, h = size
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    talk = any(s.role == "talk" for s in shots)
    chains = []
    for n, s in enumerate(shots):
        src = os.path.join(media_dir, s.src)
        args += ["-ss", f"{s.src_in:.4f}", "-t", f"{s.dur:.4f}", "-i", src]
        chains.append(f"[{n}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},"
                      f"setsar=1,trim=duration={s.dur:.4f},setpts=PTS-STARTPTS[v{n}];")
        if not talk:
            continue
        if s.role == "talk" and common.probe(src)["has_audio"]:
            # Short fades at each jump cut keep the splices from clicking.
            fade = min(0.01, s.dur / 4)
            chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={s.dur:.4f},"
                          f"asetpts=PTS-STARTPTS,apad=whole_dur={s.dur:.4f},afade=t=in:d={fade:.4f},"
                          f"afade=t=out:st={s.dur - fade:.4f}:d={fade:.4f}[a{n}];")
        else:
            chains.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={s.dur:.4f}[a{n}];")
    if talk:
        pairs = "".join(f"[v{n}][a{n}]" for n in range(len(shots)))
        graph = "".join(chains) + pairs + f"concat=n={len(shots)}:v=1:a=1[v][a]"
        outs = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        graph = "".join(chains) + "".join(f"[v{n}]" for n in range(len(shots))) + \
            f"concat=n={len(shots)}:v=1:a=0[v]"
        outs = ["-map", "[v]", "-an"]
    args += ["-filter_complex", graph, *outs, "-c:v", "libx264", "-crf", "18", "-preset", "fast",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    subprocess.run(args, check=True)
