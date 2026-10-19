"""Shared helpers: ffprobe wrapper, capture time, media type."""
import json
import os
import subprocess
from fractions import Fraction

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
PHOTO_EXTS = {".jpg", ".jpeg", ".heic", ".png"}
# Homebrew's ffmpeg-full is keg-only (not on PATH); plain ffmpeg lacks drawtext, which the sheets need.
FULL_FFMPEG_DIRS = ["/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"]


def prefer_full_ffmpeg(dirs=FULL_FFMPEG_DIRS):
    """Put the first installed ffmpeg-full ahead of anything else on PATH, for us and our subprocesses."""
    path = os.environ.get("PATH", "").split(os.pathsep)
    for d in dirs:
        if os.path.isdir(d):
            os.environ["PATH"] = os.pathsep.join([d] + [p for p in path if p != d])
            return


prefer_full_ffmpeg()


def grid_select(step):
    """ffmpeg select= that keeps the first frame at or after every multiple of step, as seeking there would.

    (fps= is not a substitute: it keeps the last frame of each slot, up to step/2 after the time it reports.)
    """
    slot = f"floor((t+1e-6)/{step:.6f})"
    return f"select='isnan(prev_t)+gt({slot},{slot.replace('(t+', '(prev_t+')})'"


def media_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in PHOTO_EXTS:
        return "photo"
    return None


def _ffprobe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-of", "json", "-show_streams", "-show_format", path])
    return json.loads(out)


def probe(path):
    d = _ffprobe(path)
    video = next(s for s in d["streams"] if s["codec_type"] == "video")
    rate = Fraction(video.get("r_frame_rate", "0/1"))
    fps = round(float(rate), 3) if rate else 0.0
    # Phones store portrait video sideways plus a rotation tag; ffmpeg decodes it upright, so report that size.
    rotation = next((int(s.get("rotation", 0)) for s in video.get("side_data_list", [])
                     if s.get("side_data_type") == "Display Matrix"), 0) % 360
    w, h = int(video["width"]), int(video["height"])
    if rotation in (90, 270):
        w, h = h, w
    return {
        "duration": float(d["format"].get("duration", 0.0)),
        "width": w,
        "height": h,
        "rotation": rotation,
        "fps": int(fps) if fps == int(fps) else fps,
        "has_audio": any(s["codec_type"] == "audio" for s in d["streams"]),
    }


def capture_time(path):
    """ISO 8601 capture time from container tags, or None."""
    tags = _ffprobe(path)["format"].get("tags", {})
    for key in ("com.apple.quicktime.creationdate", "creation_time", "DateTimeOriginal"):
        if tags.get(key):
            return tags[key]
    return None
