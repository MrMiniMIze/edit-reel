import json
import os
import re
import unittest

from tests.fixtures import SKILL_DIR
import captions
import speech
from cutlist import Shot

STYLE = json.load(open(os.path.join(SKILL_DIR, "style.json")))
FILLERS = set(STYLE["speech"]["fillers"])
LOOK = json.load(open(os.path.join(SKILL_DIR, "assets", "text_style.json")))


def words(text, t0=0.0, step=0.3):
    return [{"w": w, "t0": round(t0 + i * step, 3), "t1": round(t0 + (i + 1) * step - 0.05, 3)}
            for i, w in enumerate(text.split())]


class PagesTests(unittest.TestCase):
    def test_short_one_line_pages_without_punctuation(self):
        pg = captions.pages(words("This is everything in my basket for the Sephora sale, and it is a lot."), FILLERS)
        self.assertEqual([p["text"] for p in pg][:3], ["this is everything", "in my basket", "for the Sephora sale"])
        self.assertEqual(" ".join(p["text"] for p in pg[3:]), "and it is a lot")  # its own sentence's pages
        self.assertTrue(all(len(p["text"]) <= 20 for p in pg))

    def test_names_keep_their_capitals_and_I_stays_upper(self):
        pg = captions.pages(words("I love Rhode. Rhode is great. So I wanna try it."), FILLERS)
        text = " | ".join(p["text"] for p in pg)
        self.assertIn("I love Rhode", text)
        self.assertIn("Rhode is great", text)  # capitalized mid-sentence too, so a name
        self.assertIn("so I wanna", text)

    def test_common_words_at_a_sentence_start_lose_their_capital_and_i_is_upper(self):
        pg = captions.pages(words("The first one. I love The Ordinary and i think it works."), FILLERS)
        text = " | ".join(p["text"] for p in pg)
        self.assertTrue(text.startswith("the first one"), text)
        self.assertIn("The Ordinary", text)
        self.assertIn("I think", text)

    def test_a_comma_after_one_word_doesnt_make_a_page(self):
        pg = captions.pages(words("Oh, and for that one I don't know."), FILLERS)
        self.assertNotEqual(pg[0]["text"], "oh")

    def test_fillers_are_left_out(self):
        pg = captions.pages(words("Um, this is the brow wiz."), FILLERS)
        self.assertEqual(" ".join(p["text"] for p in pg), "this is the brow wiz")

    def test_pages_hold_until_the_next_one_but_not_across_a_pause(self):
        w = words("one two three four five six") + words("seven eight", t0=5.0)
        pg = captions.pages(w, FILLERS, max_words=3)
        self.assertEqual(pg[0]["t1"], pg[1]["t0"])
        self.assertLess(pg[1]["t1"], 5.0)

    def test_fixes_replace_phrases_and_keep_the_break(self):
        w = captions.apply_fixes(words("I have the Hoss Labs, by Lady Gaga."), {"Hoss Labs": "Haus Labs"})
        self.assertEqual([x["w"] for x in w], ["I", "have", "the", "Haus", "Labs,", "by", "Lady", "Gaga."])
        self.assertEqual(w[3]["t0"], 0.9)


class LowercaseTests(unittest.TestCase):
    def test_everything_lowercase_but_I(self):
        pg = captions.pages(words("I love The Ordinary and Rhode, i'm sure."), FILLERS, lowercase=True)
        self.assertEqual(" ".join(p["text"] for p in pg), "I love the ordinary and rhode I'm sure")


class LinesTests(unittest.TestCase):
    def test_tightened_pieces_of_one_line_are_one_line(self):
        shots = [Shot("a.mov", 0, 2, "talk", 1, 0, "intro"), Shot("a.mov", 3, 1, "talk", 1, 0, "intro"),
                 Shot("a.mov", 9, 2, "talk", 2, 0, "lip liner")]
        self.assertEqual(captions._lines(shots), [[0.0, 3.0], [3.0, 5.0]])
        self.assertEqual(captions.opening_line_end(shots), 3.0)
        self.assertIsNone(captions.opening_line_end([Shot("b.mov", 0, 1, "opener", 1, 0)] + shots))


class DrawtextTests(unittest.TestCase):
    def test_sizes_and_positions_match_the_creators_post(self):
        items = captions.items("What's in my basket", 3.0, [{"text": "a: 50%", "t0": 0.5, "t1": 1.0}])
        title, cap = captions.drawtext(items, LOOK, (2160, 3840))
        size = float(re.search(r"fontsize=([\d.]+)", cap).group(1))
        self.assertTrue(80 <= size <= 84, size)  # measured 80-83 px at 2160 wide
        self.assertIn("y=h*0.6332", cap)
        self.assertTrue(112 <= float(re.search(r"fontsize=([\d.]+)", title).group(1)) <= 120)  # measured 118
        self.assertIn("between(t,0.000,3.000)", title)
        self.assertIn("a\\: 50\\%", cap)
        self.assertIn("What’s", title)


class PlaceTests(unittest.TestCase):
    def test_captions_move_to_the_given_height_in_both_outputs(self):
        look = captions.place(LOOK, 0.54)
        self.assertAlmostEqual(look["caption"]["clip"]["transform"]["y"], -0.08)
        self.assertIn("y=h*0.5400", captions.drawtext([{"kind": "caption", "text": "a", "t0": 0, "t1": 1}],
                                                      look, (2160, 3840))[0])
        self.assertAlmostEqual(LOOK["caption"]["clip"]["transform"]["y"], -0.2665, places=3)  # unchanged


class EdgeTests(unittest.TestCase):
    def test_edges_snap_to_the_voice(self):
        win = 0.02
        env = [-60.0] * 50 + [-20.0] * 100 + [-60.0] * 50  # quiet 0-1s, voice 1-3s, quiet 3-4s
        t0, t1 = speech.trim_edges(env, win, 0.5, 3.8, STYLE["speech"])
        self.assertAlmostEqual(t0, 1.0 - STYLE["speech"]["pad"], places=2)
        self.assertAlmostEqual(t1, 3.0 + STYLE["speech"]["pad"], places=2)

    def test_an_end_inside_the_last_word_is_pushed_past_it(self):
        win = 0.02
        env = [-60.0] * 50 + [-20.0] * 100 + [-60.0] * 50
        _, t1 = speech.trim_edges(env, win, 1.0, 2.9, STYLE["speech"])
        self.assertGreater(t1, 3.0)

    def test_an_end_mid_speech_with_no_gap_nearby_stays(self):
        win = 0.02
        env = [-60.0] * 50 + [-20.0] * 150
        _, t1 = speech.trim_edges(env, win, 1.0, 2.0, STYLE["speech"])
        self.assertEqual(t1, 2.0)


if __name__ == "__main__":
    unittest.main()
