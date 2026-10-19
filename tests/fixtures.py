"""Synthetic media for tests, generated with ffmpeg."""
import os
import subprocess
import sys

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills", "edit-reel", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPTS, ".."))


def make_clip(path, seconds, fps=30, size=(720, 1280), creation=None, color="testsrc", rotation=0):
    """color: "testsrc" for a sharp pattern, or an ffmpeg color name like "black".
    rotation: tag the file to display rotated, the way phones store portrait video."""
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
    if not rotation:
        subprocess.run(cmd + [path], check=True)
        return path
    raw = path + ".raw" + os.path.splitext(path)[1]
    subprocess.run(cmd + [raw], check=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-display_rotation", str(rotation),
                    "-i", raw, "-c", "copy", path], check=True)
    os.remove(raw)
    return path


def make_black_then_white(path, black_s, white_s, size=(320, 568)):
    """A clip that cuts from black to white at black_s seconds: checks which moment a sample really shows."""
    w, h = size
    graph = (f"color=c=black:s={w}x{h}:r=30:d={black_s}[a];color=c=white:s={w}x{h}:r=30:d={white_s}[b];"
             "[a][b]concat")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", graph,
                    "-pix_fmt", "yuv420p", path], check=True)
    return path
