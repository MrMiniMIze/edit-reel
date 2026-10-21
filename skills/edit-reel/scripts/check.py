"""Preflight: is this Mac ready for /edit-reel? Prints each problem with its fix."""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capcut  # noqa: E402
import common  # noqa: E402,F401  (puts ffmpeg-full on PATH)
import sheets  # noqa: E402
import speech  # noqa: E402

FILTERS = ["blurdetect", "signalstats", "drawtext", "drawbox", "tile"]


def _filters():
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return {line.split()[1] for line in out.splitlines() if len(line.split()) > 2}


def problems():
    out = []
    if sys.platform != "darwin":
        out.append("edit-reel runs on macOS only")
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        out.append(f"{' and '.join(missing)} not found. Install it: brew install ffmpeg-full")
    else:
        lacking = [f for f in FILTERS if f not in _filters()]
        if lacking:
            out.append(f"your ffmpeg lacks the {', '.join(lacking)} filter(s). "
                       "Install the full build: brew install ffmpeg-full")
    if not os.path.exists(sheets.FONT):
        out.append(f"font not found: {sheets.FONT}")
    return out


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(f"PROBLEM: {p}")
    cc = capcut.draft_problem(capcut.drafts_root())
    if cc:
        print(f"note: {cc}")
    if speech.problem():
        print(f"note: finding talking to camera is off: {speech.problem()}")
    print("ready" if not found else "not ready")
    sys.exit(1 if found else 0)
