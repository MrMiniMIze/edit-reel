---
name: edit-reel
description: Auto-edit a folder of raw phone clips from one outing (food, drinks, a day out) into a ~60s vertical reel with fast hook cuts, as a silent mp4 plus an editable CapCut desktop project. Use when the user says "/edit-reel", "edit these clips", "make a reel from this folder", or asks to revise a reel made this way ("swap the drink shot", "make it 45s").
---

# Edit Reel

You are the editor. Scripts handle the mechanics; you make every taste call by **looking at the footage**. The output is silent, because a voiceover is added later. Never choose moments by audio.

`SKILL_DIR` below means this skill's base directory (shown when the skill loads).

## 1. Inputs

- A media folder (required). Ask only if none was given.
- A length, if the user said one ("make it 45s"). Otherwise the target is 60s. Anything from 30–90s is acceptable.

## 2. Prepare

```bash
python3 "$SKILL_DIR/scripts/prepare.py" "<media folder>"
```

It first checks the Mac is ready (ffmpeg with the needed filters, macOS). If it prints **"This Mac isn't ready"**, show the user each problem and its fix exactly as printed, as numbered steps, and stop until they've fixed it. `python3 "$SKILL_DIR/scripts/check.py"` reruns just the check.

Then it prints the output dir (`edit-<date>` next to the media folder), the clip count, the ordering, and the sheet count. It takes well under a minute for a typical day's footage. Photos are skipped.

## 3. Look at every sheet

Read **every** `sheets/sheet_*.jpg` in order, and don't skip any. Each tile is labeled `CLIP @ seconds`. A red border with an `X` means blurry or dark: never place a shot over those times. `sheets/sheets.json` lists every tile's file, time and usable flag.

While reading, keep one note line per clip: what's happening, and its best moments with times. For example: `IMG_7565: two drinks on yellow ledge 0–1.5; sips green drink 10.5–12; cheers 16–17; laughs 23–25`.

## 4. Group into stops

A **stop** is one food, drink or place. Clips are already in shooting order.
- Consecutive clips showing the same food, table or place form one stop.
- Keep shooting order. You may move a stop only when the footage clearly belongs earlier, for example a drink being finished that was bought before the previous clip.
- Leave out a clip with nothing usable, or a clip under ~1s with no clear subject. Such a clip can still supply a hook shot.

## 5. Pick shots (visual judgment)

This style is fast, bright and food-first, with hard cuts at about one per second.

**Budget first:** roughly `hook ≈ 2–3s`, and the rest split across the stops. Fewer stops means more actions per stop; more stops means fewer.

**Per stop, in this order:**
1. **Opener**, about 1.0s: the food or drink itself, presented clearly (on the table, held up, the tray). Usually near the start of the stop's first clip.
2. **Actions**, 2–7 of them, 0.4–2.0s each, averaging about 1s. These are the moments where something *happens*:
   - a bite, a sip, a chug, cheers, holding the food up to the camera, an expressive reaction (eyes closed, laughing, surprise), a close-up of the food mid-eating, dipping or stirring.
   - Take several jump-cuts from the same clip, generally in source order, skipping the dead time between them.
   - Make a shot long enough to read the action (a bite plus its reaction is about 1.5s) and short when it's a quick gesture (about 0.5s).
   - Skip: camera setup and adjusting, the phone being put down, someone's back, strangers walking through the frame, frames with no food and no face, and anything near a red-X tile.
3. **Rank** the actions within the stop: 1 is the strongest. If the reel runs long, the highest numbers get dropped first, so rank honestly.

**Hook** (the very start): standout moments from across the whole day, about **0.4s each**, in day order.
- Use as many as the footage deserves (usually 4–7, within 3–8). The best picks are visually striking: vivid drinks, a big bite, a full tray, a night or neon shot, a great reaction.
- At most one per stop, so the hook previews the variety of the day.
- Hook moments may reuse body moments.

**Don't:** use speed changes, text, music, transitions or photos, or trim mechanically ("first second of every clip"). Every shot should be a moment you chose by looking at it.

## 6. Write `cutlist.json` in the output dir

```json
{"target": 60, "shots": [
  {"src": "IMG_7568.MP4", "src_in": 0.0, "dur": 0.4, "role": "hook", "stop": 0, "rank": 0, "why": "full tray, bright"},
  {"src": "IMG_7565.MP4", "src_in": 0.0, "dur": 1.2, "role": "opener", "stop": 1, "rank": 0, "why": "two drinks on ledge"},
  {"src": "IMG_7565.MP4", "src_in": 10.6, "dur": 1.4, "role": "action", "stop": 1, "rank": 1, "why": "first sip, eyes up"}
]}
```

- Hook shots come first (`stop` 0). Body shots follow with `stop` 1, 2, 3, … in playback order.
- `src_in` and `dur` are in seconds; read the times off the tile labels. Shots snap automatically to clean frames and clip bounds.
- `speed` is always 1.0 (it can be omitted).
- Write a `why` for every shot, so revisions can refer to it.

## 7. Build

CapCut must be **fully quit** before the project can be written. If it's running, ask the user to press **Cmd+Q** in CapCut, then build.

```bash
python3 "$SKILL_DIR/scripts/build.py" "<output dir>" [--target 45]
```

It validates the cut list (fix any errors it lists and rerun), snaps shots to clean frames, drops the weakest actions if the reel runs long, renders `reel.mp4` (silent), and writes the CapCut project. If CapCut isn't installed, has never been opened, or is still running, it skips the project with a warning and the mp4 is still made: relay the warning, and after the user fixes it, rerun build.

## 8. Report

Tell the user, briefly:
- the stops you found, one line each,
- the shot count, the length and the hook count, anything dropped to fit, and any warnings,
- numbered steps:
  1. Watch the reel: `! open "<output dir>/reel.mp4"`
  2. Open **CapCut**, click the project named **`<folder> <date>`** on the home screen.
  3. Clip audio is set to volume 0 (not deleted). Raise it in CapCut if it's needed.
  4. Reply with what to change.

## 9. Revisions

Edit `cutlist.json` for the requested change, for example swapping a shot (go back to the sheets for the alternative), shortening a stop, or changing the length with `--target`. Then rerun build. Don't re-pick everything unless asked. Each build writes a new CapCut project named with a ` (2)`, ` (3)` suffix, so earlier versions are kept.

## CapCut updated (the project won't open)

If build warns that CapCut's version differs from the template's, or the user says the CapCut project won't open, rebuild the template from their own CapCut:

1. Give the user these steps: open **CapCut**, click **New project**, import any one video, drag it onto the timeline, wait a few seconds, then quit with **Cmd+Q**. Ask what the project is called on CapCut's home screen (usually a date).
2. Run `python3 "$SKILL_DIR/scripts/refresh_template.py" "<project name>"`. If it refuses, relay its message; it says what to fix.
3. Rebuild. Every later build uses the refreshed template automatically. It's kept in `~/Library/Application Support/edit-reel/`, so it survives plugin updates. The user can delete the one-clip project afterwards.

## Never

Use audio or transcripts to pick moments, change speed, add text or music, modify the media folder, or modify an existing CapCut project.
