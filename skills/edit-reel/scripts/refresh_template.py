"""Rebuild the CapCut template from a one-clip project made in CapCut, after a CapCut update breaks the old one."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capcut  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="name of the CapCut project, as shown on CapCut's home screen")
    ap.add_argument("--to", default=capcut.USER_TEMPLATE)
    args = ap.parse_args()
    if capcut.capcut_running():
        sys.exit("CapCut is running: quit it (Cmd+Q) so the project is fully saved, then retry")
    root = capcut.drafts_root()
    project = os.path.join(root, args.project)
    if not os.path.isdir(project):
        names = sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))) if os.path.isdir(root) else []
        sys.exit(f"No CapCut project named '{args.project}'. Projects: {', '.join(names) or 'none'}")
    try:
        dst = capcut.refresh_template(project, args.to)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Template refreshed from '{args.project}' (CapCut {capcut.capcut_version()}): {dst}")
    print("New reels will use it. The project itself is untouched; you can delete it in CapCut.")


if __name__ == "__main__":
    main()
