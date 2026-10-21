# Changelog

## 0.4.0

- **Talking to camera keeps its sound.** Prepare transcribes every clip on your Mac (Whisper, nothing is uploaded) and makes speech sheets, so Claude can tell when you're talking to viewers, even with the phone propped up and you looking away. Talking to your pet, a friend or staff stays silent B-roll, and talk about the filming itself ("I don't know how this angle's gonna work") is cut.
- **Best take wins.** When you say a line more than once, the most energetic take is used, finished from your last take if it trails off.
- **Every talking line is kept**, in the order you filmed it, with B-roll cut in between. The reel runs past the target length rather than losing a line.
- **Pauses are tightened automatically.** Long pauses, "um"s and breaths inside a talking line become jump cuts. Pauses are measured against each line's own background noise, so it works on a windy street too. Tuned on real footage so that no words are lost.
- **Food or lifestyle.** Say "make a food reel" or "make a lifestyle reel": same format, and on lifestyle a stop is a place or activity instead of a food.
- **B-roll tells the story.** Shots follow what happened in order, with the lead-in before the action (reaching for him before the lift) and a move right before where it lands (the jump, then the table he jumped to). Each shot is trimmed to the action: no wind-ups, still moments at most 2s, nothing over 3s except the biggest moment, and no reaching for the camera unless you're talking.
- **Camera moves are trimmed off talking clips.** The build warns when a talking clip starts or ends on a blurry frame (the phone being picked up or turned). A little swing on the opening line is kept.
- Talking clips play at full volume in the CapCut project and in the mp4; everything else stays at 0 for your voiceover.
- One-time setup for talking: `brew install whisper-cpp` and a 1.6 GB speech model (`speech.py --download`). Without them, reels are made as before, all silent.

## 0.3.0

- **CapCut Retouch by default.** Every clip in the CapCut project gets Retouch > Auto styles ("Native"), captured from a real CapCut project. CapCut runs its own face detection when the project opens, so faces get retouched and food shots are left alone. It's a CapCut Pro feature: say "no retouch" (`--no-retouch`) without Pro. The mp4 preview has no retouch.
- **Your own retouch look:** set it once on one clip in CapCut and run `capture_retouch.py`; every reel after that uses it.

## 0.2.0

- **Faster contact sheets**, about 8x: each clip is decoded once instead of once per frame, and sheets are drawn in parallel. A typical day's footage now takes seconds, not minutes.
- **Frames line up with their labels.** Sheet tiles and the blur/darkness screening showed the moment up to ~0.25s after the time printed on them, so shots could be cut slightly late or flagged at the wrong spot. Both now show exactly the labeled moment.
- **Clips straight off an iPhone** (stored sideways with a rotation tag) are measured upright, so the reel size and the CapCut project match how they look.
- **Refresh the CapCut template** after a CapCut update: make a one-clip project in CapCut and run `refresh_template.py` (Claude walks you through it). The refreshed template is kept outside the plugin, so updates don't overwrite it. Works whether CapCut copies clips into its projects or links them in place.
- **No broken projects after a failed write.** If writing a CapCut project fails partway, the half-made project is removed and CapCut's project list is restored.

## 0.1.0

- First public release.
