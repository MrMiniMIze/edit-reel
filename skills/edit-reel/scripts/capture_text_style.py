"""Save the caption and title look from a finished CapCut project as the look every talking reel gets."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capcut  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="name of the CapCut project, as shown on CapCut's home screen")
    ap.add_argument("--to", default=capcut.USER_TEXT_STYLE)
    args = ap.parse_args()
    if capcut.capcut_running():
        sys.exit("CapCut is running: quit it (Cmd+Q) so the project is fully saved, then retry")
    project = os.path.join(capcut.drafts_root(), args.project)
    if not os.path.isdir(project):
        sys.exit(f"No CapCut project named '{args.project}'")
    try:
        look = capcut.capture_text_style(project)
    except ValueError as e:
        sys.exit(str(e))
    os.makedirs(os.path.dirname(os.path.abspath(args.to)), exist_ok=True)
    with open(args.to, "w") as f:
        json.dump(look, f, indent=1, ensure_ascii=False)
    font = lambda k: os.path.basename(look[k]["font_path"]) if look[k] else "none"
    print(f"Saved captions ({font('caption')}) and title ({font('title')}): {args.to}")
    print("New talking reels will use it. The project itself is untouched.")


if __name__ == "__main__":
    main()
