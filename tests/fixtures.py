"""Synthetic media for tests, generated with ffmpeg."""
import os
import subprocess
import sys

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills", "edit-reel", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPTS, ".."))


def make_clip(path, seconds, fps=30, size=(720, 1280), creation=None, color="testsrc"):
    """color: "testsrc" for a sharp pattern, or an ffmpeg color name like "black"."""
    w, h = size
    if color == "testsrc":
        src = f"testsrc2=size={w}x{h}:rate={fps}:duration={seconds}"
    else:
        src = f"color=c={color}:size={w}x{h}:rate={fps}:duration={seconds}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src,
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"]
    if creation:
        cmd += ["-metadata", f"creation_time={creation}"]
    subprocess.run(cmd + [path], check=True)
    return path
