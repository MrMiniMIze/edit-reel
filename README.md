# edit-reel

Give Claude a folder of raw phone clips from a day out, and get back a ready-to-voice-over vertical reel:

- **`reel.mp4`**: a ~60s 9:16 video. It opens with a fast hook of the day's best moments, then gives each food, drink or place its own short section, cutting about once a second. The parts where you **talk to the camera** keep their sound; everything else is silent, ready for your voiceover.
- **A CapCut desktop project** with the same edit, so you can fine-tune it, add your voiceover, music and text, and export.

Claude picks every shot by **looking** at the footage (bites, sips, reactions, the food itself) and skips the blurry, dark and dead moments. It also listens for the parts where you talk to viewers: it keeps every line (the best take if you said it more than once), cuts out the pauses and "um"s, and places it in the order you filmed it. Talking to your pet, a friend or staff stays silent B-roll.

> Built for a food and day-out vlog style. It works best when one folder holds one outing, filmed in order.

---

## What you need

| | |
|---|---|
| **A Mac** | macOS only (CapCut projects are written in the Mac app's format). |
| **Claude Code** | Install it from [claude.com/claude-code](https://claude.com/claude-code). |
| **ffmpeg-full** | The video engine. The regular `ffmpeg` package is **not** enough (it can't draw text). |
| **whisper-cpp** *(for talking to camera)* | Transcribes your clips on your Mac (nothing is uploaded). Without it, every shot is silent B-roll. |
| **CapCut desktop** *(optional)* | Needed only for the editable project. Tested with **CapCut 9.6.0**. Without it you still get the mp4. |
| **CapCut Pro** *(optional)* | The CapCut project has CapCut's **Retouch** (Auto styles, "Native") on every clip by default, and that's a Pro feature. No Pro? Just say **"no retouch"**. |

## Install (one time, about 5 minutes)

1. **Install Homebrew**, if you don't have it. Open **Terminal** and paste the command from [brew.sh](https://brew.sh).
2. **Install ffmpeg-full.** In Terminal:
   ```
   brew install ffmpeg-full
   ```
3. **Install whisper-cpp and its speech model**, for talking to camera. In Terminal:
   ```
   brew install whisper-cpp
   ```
   The first time you make a reel, Claude offers to download the speech model (1.6 GB, one time).
4. **Install CapCut desktop** from [capcut.com](https://www.capcut.com). Open it once, then quit it with **Cmd+Q**.
5. **Install the skill.** Start Claude Code by typing `claude` in Terminal, then run these two commands inside it:
   ```
   /plugin marketplace add MrMiniMIze/edit-reel
   /plugin install edit-reel@edit-reel
   ```
6. **Restart Claude Code**: type `/exit`, then `claude` again.

## Make a reel

1. Put one outing's clips (straight off the phone, as `.MOV` or `.MP4`) in a folder, for example `~/Desktop/sunday-clips`. Photos in the folder are ignored.
2. **Quit CapCut** with **Cmd+Q**. The project can't be written while CapCut is open.
3. In Terminal, start Claude Code with `claude` and say:
   ```
   make a food reel from ~/Desktop/sunday-clips
   ```
   Say **food** or **lifestyle** each time. They use the same format; on lifestyle, each section is a place or activity instead of a food. If it's mostly you talking to the camera, say so ("it's a talking vlog").
   For a different length, say so: `make a 45 second lifestyle reel from ~/Desktop/sunday-clips`. Anything from 30s to 90s works. Talking is never cut to fit, so a reel with a lot of talking can run longer.
4. Wait. Claude prepares contact sheets (under a minute for a typical day's footage), looks through every frame, picks the shots, and renders.
5. When it's done, Claude tells you what it found and gives you numbered steps:
   - **Watch it:** the mp4 is in a new folder next to your clips, called `edit-<date>/reel.mp4`.
   - **Edit it:** open CapCut and click the project named `<folder> <date>`. Talking clips play at full volume; every other clip is turned down to 0 (not deleted), so you can raise it if you need it.
   - **Export from CapCut** for the final video: only the CapCut project has the retouch. The mp4 is a quick preview without it.

## Ask for changes

Just say what you want, in the same Claude Code session:

- "swap the drink shot at the second stop for the laughing moment"
- "make it 45 seconds"
- "the hook is too long, cut it to 4 shots"
- "drop the parking-lot clip"
- "keep the line where I talk about the menu" or "that wasn't to the camera, mute it"
- "use the other take of the intro"
- "no retouch" (for when you don't have CapCut Pro)
- "use a different retouch look": Claude has you set it up once on one clip in CapCut, and every reel after that uses it.

Claude edits the cut list and rebuilds. Each rebuild becomes a new CapCut project with ` (2)`, ` (3)` and so on added to the name, so earlier versions are kept.

## Tips for better results

- **One outing per folder.** Clips are put in the order they were filmed, using the phone's capture time. AirDrop keeps that time. If it's missing (some apps strip it), filename order is used instead.
- **Film the food on its own for a second** before eating. That makes the best opener for each stop.
- **Bright beats dark.** Very dark or shaky moments are skipped automatically.
- **Talking to the camera:** say each line in one go if you can. Retakes are fine; the most energetic one is used. Wind and street noise are handled, but a closer phone always sounds better.
- Vertical clips look best. Clips straight off an iPhone are handled upright; horizontal clips are center-cropped to 9:16.

## Troubleshooting

| You see | Do this |
|---|---|
| "This Mac isn't ready" | Follow the fix it prints. Usually it's `brew install ffmpeg-full`. |
| "CapCut project not written: CapCut is running" | Quit CapCut with **Cmd+Q**, then say "rebuild". |
| "CapCut project not written: never opened" | Open CapCut once, quit it, then say "rebuild". |
| The CapCut project won't open, or a version warning appears | CapCut has updated since the template was made. Say **"CapCut updated, refresh the template"**: Claude has you make a one-clip project in CapCut and rebuilds the template from it (takes a minute). The mp4 is unaffected. If that doesn't fix it, please [open an issue](https://github.com/MrMiniMIze/edit-reel/issues) with your CapCut version. |
| The project isn't on CapCut's home screen | Quit and reopen CapCut. |

To check your setup at any time, ask Claude Code: "run the edit-reel setup check".

---

## How it works

```
clips/ ──prepare.py──▶ inventory + quality screen + labeled contact sheets
                           │
                     Claude looks at every sheet, groups clips into stops,
                     picks hook / opener / action shots ──▶ cutlist.json
                           │
         build.py ──▶ snap to clean frames ─▶ fit to length ─▶ reel.mp4 + CapCut project
```

- **Scripts handle the mechanics**: probing, blur and darkness screening, contact sheets, rendering and CapCut's project format. They are plain Python 3 (standard library only) driving ffmpeg.
- **Claude makes the taste calls**: which moments, in what order, and for how long. The rules it follows are in [`skills/edit-reel/SKILL.md`](skills/edit-reel/SKILL.md).
- **`cutlist.json`** in the output folder is the single source of truth. Every shot has a `why`, so you can read (or hand-edit) the edit.
- The style numbers (length, hook shot length, pace, blur limits) live in [`skills/edit-reel/style.json`](skills/edit-reel/style.json). Change them to suit a different style.

The CapCut project is written by cloning a small template project made by CapCut itself. CapCut's project format isn't officially documented, so a CapCut update can break that part. When it does, the template can be rebuilt from your own CapCut in a minute (see Troubleshooting). The mp4 never depends on it.

## Development

```
git clone https://github.com/MrMiniMIze/edit-reel && cd edit-reel
python3 -m unittest discover -s tests -t .
```

The tests generate synthetic clips with ffmpeg (about 2 minutes, with no real footage needed). The CapCut tests write into a temporary folder, not your real CapCut library.

To try local changes in Claude Code without installing: `claude --plugin-dir /path/to/edit-reel`.

## License

[MIT](LICENSE). Not affiliated with CapCut or ByteDance.
