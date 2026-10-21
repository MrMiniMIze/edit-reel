---
name: edit-reel
description: Auto-edit a folder of raw phone clips from one outing (food, drinks, a day out, a lifestyle vlog) into a ~60s vertical reel with fast hook cuts, as an mp4 plus an editable CapCut desktop project. Finds the parts where the creator talks to the camera, keeps them with their sound, picks the best take, and tightens out pauses. Use when the user says "/edit-reel", "edit these clips", "make a reel from this folder", "make a food reel", "make a lifestyle reel", or asks to revise a reel made this way ("swap the drink shot", "make it 45s").
---

# Edit Reel

You are the editor. Scripts handle the mechanics; you make every taste call by **looking at the footage**. A voiceover is added later, so B-roll is silent and is never chosen by audio. The one exception is **talking to camera**: the parts where the creator speaks to viewers keep their own sound, and you find them with the transcript (step 4).

`SKILL_DIR` below means this skill's base directory (shown when the skill loads).

## 1. Inputs

- A media folder (required). Ask only if none was given.
- The **channel**, which the user names every time: **food** ("make a food reel…") or **lifestyle** ("make a lifestyle reel…"). If they didn't say, ask; don't guess. Both use the same format; they differ only in what a stop is (step 5).
- Whether it's a **talking vlog** (mostly the creator talking to camera), if the user says so. Otherwise expect a mix of talking and B-roll.
- A length, if the user said one ("make it 45s"). Otherwise the target is 60s. Anything from 30–90s is acceptable.

## 2. Prepare

```bash
python3 "$SKILL_DIR/scripts/prepare.py" "<media folder>"
```

It first checks the Mac is ready (ffmpeg with the needed filters, macOS). If it prints **"This Mac isn't ready"**, show the user each problem and its fix exactly as printed, as numbered steps, and stop until they've fixed it. `python3 "$SKILL_DIR/scripts/check.py"` reruns just the check.

Then it prints the output dir (`edit-<date>` next to the media folder), the clip count, the ordering, the sheet count, and a `speech:` line. It takes a few minutes for a typical day's footage. Photos are skipped.

If the `speech:` line says **off**, talking to camera can't be found. Tell the user why, as printed. If it's the speech model, ask before downloading it (1.6 GB, one time) with `python3 "$SKILL_DIR/scripts/speech.py" --download`, then rerun prepare. If the user would rather go on without it, every shot is silent B-roll.

## 3. Look at every sheet

Read **every** `sheets/sheet_*.jpg` in order, and don't skip any. Each tile is labeled `CLIP @ seconds`. A red border with an `X` means blurry or dark: never place a shot over those times. `sheets/sheets.json` lists every tile's file, time and usable flag.

While reading, keep one note line per clip: what's happening, and its best moments with times. For example: `IMG_7565: two drinks on yellow ledge 0–1.5; sips green drink 10.5–12; cheers 16–17; laughs 23–25`.

## 4. Find talking to camera

Read `speech.txt` (every line Whisper heard: `#n CLIP start-end (p=confidence): words`) and **every** `speech_sheets/sheet_*.jpg`, which show a few frames across each line, labeled `CLIP @ seconds`.

A line is **talking to camera** when it's the creator speaking **and** it's meant for viewers: telling the story, explaining, reacting for the audience. She may be looking away from the lens (phone propped up while she does something) and it still counts. It is **not** talking to camera when:
- she's talking **to someone else**: a pet, a friend, staff ("come here, babes", "you wanna jump? go!", "thank you"). That's B-roll: silent, picked by how it looks.
- it's **about the filming itself** ("I don't know how this angle's gonna work", "is this recording?"). Always cut.
- it's someone else talking, or Whisper making things up from noise: a stock phrase ("Thank you.", "Yes.", "-") over a whole quiet clip, low `p`, or frames with nobody speaking.

**Takes.** When she says the same line more than once, keep only the **most energetic take** (the most animated face and voice in the frames). If that take doesn't finish the sentence, finish it with the rest of the sentence from her **last** take, as a second talk shot right after.

**Keep every line** that counts, best take only, even if the reel runs past the target. A talking vlog is mostly these lines, with B-roll cut in between.

Note one line per kept line, e.g. `IMG_7908 1.2-14.7: why the vet (gone two weeks, he's been down); outdoor selfie`.

## 5. Group into stops

A **stop** is one food or drink (**food** channel), or one place or activity (**lifestyle** channel: home, the walk, the waiting room, the exam). Clips are already in shooting order.
- Consecutive clips showing the same food, table or place form one stop.
- Keep shooting order. You may move a stop only when the footage clearly belongs earlier, for example a drink being finished that was bought before the previous clip.
- Leave out a clip with nothing usable, or a clip under ~1s with no clear subject. Such a clip can still supply a hook shot.

## 6. Pick shots (visual judgment)

This style is fast and bright, with hard cuts at about one per second: food-first on the food channel, subject-first (her, her pet, the place) on lifestyle.

**Budget first:** roughly `hook ≈ 2–3s`, then the talking (all of it, measured after pauses are cut; about 80% of its raw length), and the rest split across the stops. Fewer stops means more actions per stop; more stops means fewer. If talking alone fills the target, give each stop just its opener and one or two actions; the reel runs long rather than losing a line.

**Per stop, in this order:**
1. **Opener**, about 1.0s: the food or drink itself, presented clearly (on the table, held up, the tray); on lifestyle, the place or the subject, clearly framed. Usually near the start of the stop's first clip.
2. **Actions**, 2–7 of them, 0.4–2.0s each, averaging about 1s. These are the moments where something *happens*:
   - a bite, a sip, a chug, cheers, holding the food up to the camera, an expressive reaction (eyes closed, laughing, surprise), a close-up of the food mid-eating, dipping or stirring.
   - on lifestyle: anything with motion or a reaction: a pet jumping or being held, getting ready, walking somewhere, a funny moment, a reveal.
   - Take several jump-cuts from the same clip, generally in source order, skipping the dead time between them.
   - Make a shot long enough to read the action (a bite plus its reaction is about 1.5s) and short when it's a quick gesture (about 0.5s).
   - Skip: camera setup and adjusting, the phone being put down, someone's back, strangers walking through the frame, frames with no subject and no face, and anything near a red-X tile.
3. **Rank** the actions within the stop: 1 is the strongest. If the reel runs long, the highest numbers get dropped first, so rank honestly.

**Tell the story (lifestyle especially).** The B-roll has to carry a voiceover, so a stop should play as a sequence of what happened, not a montage of highlights:
- Follow the events in shooting order, one beat after another (arrive → out of the carrier → on the scale → the exam → …). Don't hop between unrelated moments.
- Show what leads into an action when it's its own beat: a hand reaching toward him before the lift, the food arriving before the bite.
- When something moves from one place to another (a jump from one table to another), use the shot of the move **right before** the shot of where it ended up.

**Keep each B-roll shot to the action.**
- Start on the movement and end once it's done. Cut wind-ups and dead time: no crouching before a jump, no settling in before something happens.
- Moments where nothing much moves (a pet sitting for a thermometer, being petted, on a scale) get **at most 2s**.
- **No B-roll shot over 3s**, except the one or two biggest moments of the story (the jump between tables), which may run to about 4s.
- Leave out shots of her reaching toward the camera (grabbing or adjusting the phone, her arm swinging at the lens), unless she's talking. This includes the moments right before or after an action, like reaching for the phone after lifting him.
- After a jump or a landing, end the shot soon after he lands, not when he settles.
- The **last shot** of the reel may run a little longer, so the ending breathes.
- On lifestyle, shots average about 1.5–2s; the ~1s rhythm is for the hook. It's fine for the reel to run past the target to keep a sequence whole; pass a higher `--target` rather than losing a beat.

**Talk shots**, from step 4:
- Place each one in **shooting order**, in the stop it was filmed in, between that stop's B-roll: B-roll from before she spoke goes before it, B-roll from after goes after. A stop can open with talk instead of an opener when that's how it was filmed.
- `src_in` and `dur` cover the whole line, from just before the first word to just after the last. Use the line's times from `speech.txt`, trimmed to the words you keep. The build cuts the pauses and fillers inside it on its own.
- Cut off the **camera moving** at either end: picking the phone up, turning it around, her hand coming toward the lens, tilting it down when she's done. Check the frames at each line's edges (a red-X tile there is a giveaway; the build also warns). A dropped "so" or "okay" at the start is fine; a lost word mid-sentence is not. Exception: the reel's **opening** talking line may keep a little of the swing as she brings the camera up (about 0.2–0.4s); it feels natural there.
- Close-ups of the pet **looking straight into the camera** are some of the best story beats: look for them (often right after the camera moves in) and include them where they happened.
- Don't let a B-roll shot repeat the frames of a talk shot.
- Don't use a talk moment as a hook shot: the hook is silent.

**Hook** (the very start): standout moments from across the whole day, about **0.4s each**, in day order.
- Use as many as the footage deserves (usually 4–7, within 3–8). The best picks are visually striking: vivid drinks, a big bite, a full tray, a night or neon shot, a great reaction.
- At most one per stop, so the hook previews the variety of the day.
- Hook moments may reuse body moments.

**Don't:** use speed changes, text, music, transitions or photos, or trim mechanically ("first second of every clip"). Every shot should be a moment you chose by looking at it (or, for talk, by what she says).

## 7. Write `cutlist.json` in the output dir

```json
{"target": 60, "shots": [
  {"src": "IMG_7568.MP4", "src_in": 0.0, "dur": 0.4, "role": "hook", "stop": 0, "rank": 0, "why": "full tray, bright"},
  {"src": "IMG_7565.MP4", "src_in": 0.0, "dur": 1.2, "role": "opener", "stop": 1, "rank": 0, "why": "two drinks on ledge"},
  {"src": "IMG_7565.MP4", "src_in": 10.6, "dur": 1.4, "role": "action", "stop": 1, "rank": 1, "why": "first sip, eyes up"},
  {"src": "IMG_7566.MP4", "src_in": 1.1, "dur": 6.4, "role": "talk", "stop": 1, "rank": 0, "why": "says why she picked this place"}
]}
```

- Hook shots come first (`stop` 0). Body shots follow with `stop` 1, 2, 3, … in playback order.
- `src_in` and `dur` are in seconds; read the times off the tile labels. Shots snap automatically to clean frames and clip bounds.
- `speed` is always 1.0 (it can be omitted).
- `talk` shots keep their sound and are never dropped to fit the length. The build splits each into jump cuts with the pauses and fillers removed. Add `"tight": false` to keep a line exactly as spoken.
- Write a `why` for every shot, so revisions can refer to it.

## 8. Build

CapCut must be **fully quit** before the project can be written. If it's running, ask the user to press **Cmd+Q** in CapCut, then build.

```bash
python3 "$SKILL_DIR/scripts/build.py" "<output dir>" [--target 45]
```

**Retouch is on by default:** every clip in the CapCut project gets CapCut's Retouch > Auto styles look ("Native" unless the user saved their own). It's a CapCut Pro feature, so if the user says they don't have CapCut Pro, or asks for no retouch, add `--no-retouch`. The mp4 never has retouch; only the CapCut project does.

It validates the cut list (fix any errors it lists and rerun), tightens talk shots, snaps shots to clean frames, drops the weakest actions if the reel runs long (never talk), renders `reel.mp4` (silent except talk), and writes the CapCut project. If CapCut isn't installed, has never been opened, or is still running, it skips the project with a warning and the mp4 is still made: relay the warning, and after the user fixes it, rerun build.

## 9. Report

Tell the user, briefly:
- the stops you found, one line each,
- the talking lines you kept (a few words each), and any you left out as not to camera, so she can say if you misjudged one,
- the shot count, the length and the hook count, anything dropped to fit, and any warnings,
- numbered steps:
  1. Watch the reel: `! open "<output dir>/reel.mp4"`
  2. Open **CapCut**, click the project named **`<folder> <date>`** on the home screen.
  3. Talking clips play at full volume; every other clip is at volume 0 (not deleted), ready for the voiceover. Raise any of them in CapCut if needed.
  - If retouch was applied, add: the CapCut project has Retouch (Native) on every clip; export the final video from CapCut, since the mp4 is a preview without retouch.
  4. Reply with what to change.

## 10. Revisions

Edit `cutlist.json` for the requested change, for example swapping a shot (go back to the sheets for the alternative), shortening a stop, changing the length with `--target`, adding or dropping a talking line, or using a different take (go back to `speech.txt` and the speech sheets). Then rerun build. Don't re-pick everything unless asked. Each build writes a new CapCut project named with a ` (2)`, ` (3)` suffix, so earlier versions are kept.

## CapCut updated (the project won't open)

If build warns that CapCut's version differs from the template's, or the user says the CapCut project won't open, rebuild the template from their own CapCut:

1. Give the user these steps: open **CapCut**, click **New project**, import any one video, drag it onto the timeline, wait a few seconds, then quit with **Cmd+Q**. Ask what the project is called on CapCut's home screen (usually a date).
2. Run `python3 "$SKILL_DIR/scripts/refresh_template.py" "<project name>"`. If it refuses, relay its message; it says what to fix.
3. Rebuild. Every later build uses the refreshed template automatically. It's kept in `~/Library/Application Support/edit-reel/`, so it survives plugin updates. The user can delete the one-clip project afterwards.

## Change the retouch look

If the user wants a different retouch look on every reel:

1. Give the user these steps: open **CapCut**, click **New project**, import a clip where a face is clearly visible, drag it onto the timeline, click it, open **Video > Retouch**, pick the look under **Auto styles** (and adjust it), wait a few seconds, then quit with **Cmd+Q**. Ask for the project's name on CapCut's home screen.
2. Run `python3 "$SKILL_DIR/scripts/capture_retouch.py" "<project name>"`.
3. Rebuild. Every later build uses the saved look.

## Never

Use audio or transcripts to pick B-roll moments, keep sound on anything but talking to camera, cut a talking line mid-sentence, change speed, add text or music, modify the media folder, or modify an existing CapCut project.
