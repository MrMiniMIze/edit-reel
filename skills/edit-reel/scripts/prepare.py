"""Step 1 of /edit-reel: inventory the media folder, screen quality, and draw contact sheets."""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402
import ingest  # noqa: E402
import screen  # noqa: E402
import sheets  # noqa: E402
import speech  # noqa: E402

STYLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "style.json")


def default_out(media_dir):
    base = os.path.join(os.path.dirname(os.path.abspath(media_dir)), f"edit-{datetime.date.today().isoformat()}")
    out, n = base, 1
    while os.path.exists(out):
        n += 1
        out = f"{base}-{n}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media_dir")
    ap.add_argument("--out")
    ap.add_argument("--no-speech", action="store_true", help="skip finding talking to camera")
    args = ap.parse_args()
    found = check.problems()
    if found:
        print("This Mac isn't ready for edit-reel yet:")
        for p in found:
            print(f"  - {p}")
        sys.exit(1)
    out = args.out or default_out(args.media_dir)
    os.makedirs(out, exist_ok=True)
    style = json.load(open(STYLE))

    inv = screen.screen_inventory(ingest.build_inventory(args.media_dir), style)
    with open(os.path.join(out, "inventory.json"), "w") as f:
        json.dump(inv, f, indent=1)
    sh = style["sheets"]
    idx = sheets.make_sheets(inv, sheets.sample_times(inv, sh["max_frames"], sh["base_fps"]),
                             os.path.join(out, "sheets"), sh["cols"], sh["rows"])

    talk_note = None
    if args.no_speech:
        talk_note = "skipped (--no-speech)"
    elif speech.problem():
        talk_note = f"off: {speech.problem()}"
    else:
        _, lines = speech.analyze(inv, out, style)
        talk_note = f"{lines} spoken lines in {os.path.join(out, 'speech.txt')}, sheets in " \
                    f"{os.path.join(out, 'speech_sheets')}"

    videos = [i for i in inv["items"] if i["kind"] == "video"]
    print(f"output dir: {out}")
    print(f"clips: {len(videos)} videos ({sum(i['duration'] for i in videos):.0f}s), "
          f"{len(inv['items']) - len(videos)} photos skipped")
    print(f"order: {inv['order_source']}" + ("  (no capture times — using filename order)"
                                             if inv["order_source"] == "filename" else ""))
    if inv["skipped"]:
        print(f"skipped (unreadable): {', '.join(inv['skipped'])}")
    print(f"sheets: {len(idx)} in {os.path.join(out, 'sheets')}")
    print(f"speech: {talk_note}")


if __name__ == "__main__":
    main()
