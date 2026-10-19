"""Save the Retouch > Auto styles look from a one-clip CapCut project as the style every reel gets."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capcut  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="name of the CapCut project, as shown on CapCut's home screen")
    ap.add_argument("--to", default=capcut.USER_RETOUCH)
    args = ap.parse_args()
    if capcut.capcut_running():
        sys.exit("CapCut is running: quit it (Cmd+Q) so the project is fully saved, then retry")
    project = os.path.join(capcut.drafts_root(), args.project)
    if not os.path.isdir(project):
        sys.exit(f"No CapCut project named '{args.project}'")
    try:
        preset = capcut.capture_retouch(project)
    except ValueError as e:
        sys.exit(str(e))
    os.makedirs(os.path.dirname(os.path.abspath(args.to)), exist_ok=True)
    with open(args.to, "w") as f:
        json.dump(preset, f, indent=1, ensure_ascii=False)
    print(f"Saved retouch style '{preset['name']}' ({len(preset['effects'])} effects): {args.to}")
    print("New reels will use it. The project itself is untouched; you can delete it in CapCut.")


if __name__ == "__main__":
    main()
