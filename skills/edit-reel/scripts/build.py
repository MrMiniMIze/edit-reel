"""Step 2 of /edit-reel: validate the cut list, fit it to length, render the mp4 and the CapCut draft."""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capcut  # noqa: E402
import cutlist  # noqa: E402
import render  # noqa: E402

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--target", type=float)
    ap.add_argument("--no-capcut", action="store_true")
    ap.add_argument("--no-retouch", action="store_true", help="skip CapCut Retouch (a CapCut Pro feature)")
    args = ap.parse_args()
    out = args.outdir
    style = json.load(open(os.path.join(SKILL, "style.json")))
    inv = json.load(open(os.path.join(out, "inventory.json")))
    path = os.path.join(out, "cutlist.json")

    shots = cutlist.load(path)
    errors = cutlist.validate(shots, inv)
    if errors:
        print("cutlist.json has errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    ln = style["length"]
    target = args.target or cutlist.load_target(path) or ln["target"]
    before = cutlist.snap(shots, inv)
    shots, warnings = cutlist.fit(before, target, ln["min"], ln["max"], ln["tolerance"])
    dropped = [s for s in before if s not in shots]
    cutlist.save(shots, os.path.join(out, "cutlist.final.json"), target=target)

    size = render.output_size(inv)
    reel = os.path.join(out, "reel.mp4")
    render.render(shots, inv["media_dir"], reel, size, fps=style["fps"])

    draft = None
    problem = None if args.no_capcut else capcut.draft_problem(capcut.drafts_root())
    if problem:
        warnings.append(f"CapCut project not written: {problem}")
    elif not args.no_capcut:
        template = capcut.template_dir(SKILL)
        want = json.load(open(os.path.join(template, "TEMPLATE_INFO.json")))["capcut_version"]
        have = capcut.capcut_version()
        if have != want:
            warnings.append(f"CapCut is {have}, template was made with {want}: if the project won't open, "
                            "refresh the template (see SKILL.md, \"CapCut updated\")")
        name = f"{os.path.basename(inv['media_dir'].rstrip('/'))} {datetime.date.today().isoformat()}"
        retouch = None
        if style.get("retouch") and not args.no_retouch:
            retouch = json.load(open(capcut.retouch_path(SKILL)))
        try:
            draft = capcut.write_draft(shots, inv["media_dir"], template, capcut.drafts_root(), name, size,
                                       retouch=retouch)
        except RuntimeError as e:
            warnings.append(f"CapCut project not written: {e}")

    hooks = sum(s.role == "hook" for s in shots)
    stops = len({s.stop for s in shots if s.role != "hook"})
    body = [s.dur for s in shots if s.role != "hook"]
    print(f"stops: {stops} | shots: {len(shots)} ({hooks} hook) | length: {sum(s.dur for s in shots):.1f}s "
          f"(target {target:g}s) | mean body shot: {sum(body) / max(len(body), 1):.2f}s")
    for s in dropped:
        print(f"dropped to fit length: stop {s.stop} {s.src} @ {s.src_in} (rank {s.rank})")
    for w in warnings:
        print(f"WARNING: {w}")
    print(f"mp4: {reel}")
    if draft:
        print(f"CapCut project: {os.path.basename(draft)}" +
              (f" (Retouch: {retouch['name']}, needs CapCut Pro to export)" if retouch else ""))


if __name__ == "__main__":
    main()
