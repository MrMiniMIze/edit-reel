import os
import tempfile
import unittest

import tests.fixtures  # noqa: F401  (sets sys.path)
from cutlist import Shot, load, save, validate, snap, fit


def inv(items):
    return {"media_dir": "/x", "order_source": "filename", "items": items}


def vid(name, dur, unusable=()):
    samples = [{"t": k / 2, "blur": 0, "luma": 50, "usable": (k / 2) not in unusable} for k in range(int(dur * 2) + 1)]
    return {"file": name, "kind": "video", "duration": dur, "samples": samples}


def body(stop, n, rank_start=1, src="a.mp4"):
    out = [Shot(src, 0.0, 1.0, "opener", stop, 0)]
    out += [Shot(src, 1.0 + k, 1.0, "action", stop, rank_start + k) for k in range(n)]
    return out


class CutlistTests(unittest.TestCase):
    def test_validate_flags_unknown_src_and_bad_speed(self):
        shots = [Shot("nope.mp4", 0, 1, "opener", 1, 0), Shot("a.mp4", 0, 1, "action", 1, 1, speed=1.5)]
        self.assertEqual(len(validate(shots, inv([vid("a.mp4", 10)]))), 2)

    def test_validate_hook_must_lead(self):
        shots = [Shot("a.mp4", 0, 1, "action", 1, 1), Shot("a.mp4", 2, 0.4, "hook", 0, 0)]
        errs = validate(shots, inv([vid("a.mp4", 10)]))
        self.assertTrue(any("hook" in e for e in errs))

    def test_validate_rejects_photo(self):
        items = [vid("a.mp4", 10), {"file": "p.jpg", "kind": "photo", "duration": 0.04}]
        errs = validate([Shot("p.jpg", 0, 1, "opener", 1, 0)], inv(items))
        self.assertTrue(any("photo" in e for e in errs))

    def test_snap_clamps_past_end(self):
        s = snap([Shot("a.mp4", 0.5, 1.0, "action", 1, 1)], inv([vid("a.mp4", 0.67)]))[0]
        self.assertLessEqual(s.src_in + s.dur, 0.67 + 1e-6)
        self.assertGreater(s.dur, 0)

    def test_snap_moves_off_unusable(self):
        s = snap([Shot("a.mp4", 0.9, 0.4, "action", 1, 1)], inv([vid("a.mp4", 3.0, unusable=(1.0,))]))[0]
        self.assertFalse(s.src_in <= 1.0 <= s.src_in + s.dur)
        self.assertLessEqual(abs(s.src_in - 0.9), 0.5 + 1e-6)

    def test_fit_drops_weakest_actions_first(self):
        shots = [Shot("a.mp4", 0, 0.4, "hook", 0, 0)]
        for stop in range(1, 11):
            shots += body(stop, 6, rank_start=1)  # 10 stops x 7s = 70s + 0.4
        kept, _ = fit(shots, target=60, lo=30, hi=90, tolerance=5)
        total = sum(s.dur for s in kept)
        self.assertLessEqual(total, 65 + 1e-6)
        dropped = [s for s in shots if s not in kept]
        self.assertTrue(dropped)
        self.assertTrue(all(s.rank >= max(k.rank for k in kept if k.stop == s.stop and k.role == "action") for s in dropped))
        for stop in range(1, 11):
            self.assertGreaterEqual(sum(1 for k in kept if k.stop == stop and k.role == "action"), 1)

    def test_fit_never_drops_hook_or_opener(self):
        shots = [Shot("a.mp4", 0, 0.4, "hook", 0, 0)] + body(1, 1) + [Shot("a.mp4", 0, 80, "opener", 2, 0)]
        kept, _ = fit(shots, target=60, lo=30, hi=90, tolerance=5)
        self.assertEqual([s for s in kept if s.role != "action"], [s for s in shots if s.role != "action"])

    def test_fit_warns_when_too_short(self):
        _, warns = fit(body(1, 2) * 1, target=60, lo=30, hi=90, tolerance=5)
        self.assertTrue(any("30" in w for w in warns))

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            save(body(1, 2), p, target=45)
            self.assertEqual(load(p), body(1, 2))


if __name__ == "__main__":
    unittest.main()
