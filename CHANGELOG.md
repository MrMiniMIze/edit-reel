# Changelog

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
