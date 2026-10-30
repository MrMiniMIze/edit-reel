"""Render a cut list to a vertical mp4 with ffmpeg: silent, except talking-to-camera shots keep their sound."""
import os
import subprocess
from collections import Counter

import common
import speech


def output_size(inv):
    sizes = Counter((i["width"], i["height"]) for i in inv["items"] if i["kind"] == "video")
    w, h = sizes.most_common(1)[0][0]
    if w > h:
        w, h = h, w
    return w - w % 2, h - h % 2


VIDEO_ARGS = ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]


def _inputs(shots, media_dir):
    args = []
    for s in shots:
        args += ["-ss", f"{s.src_in:.4f}", "-t", f"{s.dur:.4f}", "-i", os.path.join(media_dir, s.src)]
    return args


def _audio_chains(shots, media_dir):
    chains = []
    for n, s in enumerate(shots):
        if s.role == "talk" and common.probe(os.path.join(media_dir, s.src))["has_audio"]:
            # Short fades at each jump cut keep the splices from clicking.
            fade = min(0.01, s.dur / 4)
            chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={s.dur:.4f},"
                          f"asetpts=PTS-STARTPTS,apad=whole_dur={s.dur:.4f},afade=t=in:d={fade:.4f},"
                          f"afade=t=out:st={s.dur - fade:.4f}:d={fade:.4f}[a{n}];")
        else:
            chains.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={s.dur:.4f}[a{n}];")
    return chains


def render(shots, media_dir, out_path, size, fps=30, text=()):
    """Silent unless there are talk shots; then talk keeps its sound and everything else is silence.
    text: ffmpeg filters (captions, a title) drawn over the finished cut."""
    w, h = size
    talk = any(s.role == "talk" for s in shots)
    chains = [f"[{n}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},"
              f"setsar=1,trim=duration={s.dur:.4f},setpts=PTS-STARTPTS[v{n}];" for n, s in enumerate(shots)]
    over = "," + ",".join(text) if text else ""
    if talk:
        chains += _audio_chains(shots, media_dir)
        pairs = "".join(f"[v{n}][a{n}]" for n in range(len(shots)))
        graph = "".join(chains) + pairs + f"concat=n={len(shots)}:v=1:a=1[c][a];[c]null{over}[v]"
        outs = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        graph = "".join(chains) + "".join(f"[v{n}]" for n in range(len(shots))) + \
            f"concat=n={len(shots)}:v=1:a=0[c];[c]null{over}[v]"
        outs = ["-map", "[v]", "-an"]
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *_inputs(shots, media_dir),
            "-filter_complex", graph, *outs, *VIDEO_ARGS, out_path]
    subprocess.run(args, check=True)


def render_audio(shots, media_dir, out_path):
    """Just the reel's sound, as 16 kHz mono wav: what Whisper reads to caption the reel."""
    chains = _audio_chains(shots, media_dir)
    graph = "".join(chains) + "".join(f"[a{n}]" for n in range(len(shots))) + \
        f"concat=n={len(shots)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *_inputs(shots, media_dir),
                    "-filter_complex", graph, "-map", "[a]", "-ac", "1", "-ar", str(speech.RATE),
                    "-c:a", "pcm_s16le", out_path], check=True)
