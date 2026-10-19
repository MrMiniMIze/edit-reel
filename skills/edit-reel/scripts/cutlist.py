"""The cut list: the single source of truth both renderers consume."""
import json
import math
from dataclasses import asdict, dataclass

ROLES = ("hook", "opener", "action")
FPS = 30


@dataclass
class Shot:
    src: str
    src_in: float
    dur: float
    role: str      # "hook" | "opener" | "action"
    stop: int      # 0 for hook shots
    rank: int      # 1 = strongest action in its stop; 0 for hook/opener
    why: str = ""
    speed: float = 1.0


def load(path):
    return [Shot(**s) for s in json.load(open(path))["shots"]]


def load_target(path):
    return json.load(open(path)).get("target")


def save(shots, path, target=None):
    with open(path, "w") as f:
        json.dump({"target": target, "shots": [asdict(s) for s in shots]}, f, indent=1)


def validate(shots, inv):
    items = {i["file"]: i for i in inv["items"]}
    errors = []
    seen_body = False
    last_stop = 0
    for n, s in enumerate(shots, 1):
        where = f"shot {n} ({s.src} @ {s.src_in})"
        item = items.get(s.src)
        if item is None:
            errors.append(f"{where}: unknown src")
        elif item["kind"] == "photo":
            errors.append(f"{where}: photo shots are not supported")
        if s.role not in ROLES:
            errors.append(f"{where}: role must be one of {ROLES}")
        if s.dur <= 0:
            errors.append(f"{where}: dur must be > 0")
        if s.src_in < 0:
            errors.append(f"{where}: src_in must be >= 0")
        if s.speed != 1.0:
            errors.append(f"{where}: speed must be 1.0")
        if s.role == "hook":
            if seen_body:
                errors.append(f"{where}: hook shots must all come before the body")
        else:
            seen_body = True
            if s.stop < last_stop:
                errors.append(f"{where}: stop {s.stop} comes after stop {last_stop}")
            last_stop = s.stop
    return errors


def _frames(x):
    return math.floor(x * FPS + 1e-6) / FPS


def _clean(item, start, dur):
    end = start + dur
    return not any(not smp["usable"] and start <= smp["t"] <= end for smp in item.get("samples") or [])


def snap(shots, inv):
    items = {i["file"]: i for i in inv["items"]}
    out = []
    for s in shots:
        item = items[s.src]
        clip = _frames(item["duration"])
        dur = _frames(min(s.dur, clip))
        start = _frames(min(max(s.src_in, 0.0), clip - dur))
        if not _clean(item, start, dur):
            offsets = sorted((k / FPS for k in range(-15, 16)), key=abs)
            for off in offsets:
                cand = _frames(start + off)
                if 0 <= cand and cand + dur <= clip and _clean(item, cand, dur):
                    start = cand
                    break
        out.append(Shot(s.src, round(start, 4), round(dur, 4), s.role, s.stop, s.rank, s.why, s.speed))
    return out


def fit(shots, target, lo, hi, tolerance):
    """Drop the weakest actions until the reel is within target + tolerance. Never lengthens."""
    kept = list(shots)
    total = lambda: sum(s.dur for s in kept)
    while total() > target + tolerance:
        per_stop = {}
        for s in kept:
            if s.role == "action":
                per_stop[s.stop] = per_stop.get(s.stop, 0) + 1
        droppable = [s for s in kept if s.role == "action" and per_stop[s.stop] > 1]
        if not droppable:
            break
        worst = max(droppable, key=lambda s: (s.rank, kept.index(s)))
        kept.remove(worst)
    warnings = []
    if total() < lo:
        warnings.append(f"reel is {total():.1f}s, under the {lo}s minimum: not enough usable footage")
    if total() > hi:
        warnings.append(f"reel is {total():.1f}s, over the {hi}s maximum even after dropping actions")
    return kept, warnings
