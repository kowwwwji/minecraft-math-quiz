import random
import re
import unittest

from builder.config import LEVELS, Config
from builder.questions import question_functions
from tests.mcsim import Sim


class QuestionTest(unittest.TestCase):
    def setUp(self):
        self.fns = question_functions(Config())

    def trials(self, level, n=3000):
        mx, sub = LEVELS[level]
        sim = Sim(self.fns, random.Random(1))
        for _ in range(n):
            sim.scores.update({"#max": mx, "#sub": sub})
            sim.run("gen")
            yield dict(sim.scores)

    def test_add_within_limit(self):
        for s in self.trials("easy"):
            self.assertEqual(s["#op"], 0)
            self.assertEqual(s["#a"] + s["#b"], s["#ans"])
            self.assertTrue(1 <= s["#ans"] <= 5 and s["#a"] >= 0 and s["#b"] >= 0)

    def test_sub_when_enabled(self):
        ops = set()
        for s in self.trials("normal"):
            ops.add(s["#op"])
            if s["#op"] == 1:
                self.assertEqual(s["#a"] - s["#b"], s["#ans"])
                self.assertTrue(1 <= s["#a"] <= 10 and 0 <= s["#b"] <= s["#a"])
        self.assertEqual(ops, {0, 1})

    def test_choices_distinct_nonnegative_with_one_correct(self):
        positions = set()
        for s in self.trials("hard"):
            c = [s["#c1"], s["#c2"], s["#c3"]]
            self.assertEqual(len(set(c)), 3)
            self.assertEqual(c.count(s["#ans"]), 1)
            self.assertTrue(all(v >= 0 for v in c))
            self.assertTrue(all(abs(v - s["#ans"]) <= 4 for v in c))
            positions.add(c.index(s["#ans"]))
        self.assertEqual(positions, {0, 1, 2})

    def test_random_ranges_are_wide(self):
        for body in self.fns.values():
            for a, b in re.findall(r"random value (-?\d+)\.\.(-?\d+)", body):
                self.assertGreaterEqual(int(b) - int(a) + 1, 2)

    def test_show_rewrites_all_displays(self):
        show = self.fns["show"]
        for tag in ("mq_q", "mq_c1", "mq_c2", "mq_c3"):
            self.assertIn(f"tag={tag},limit=1] text set value", show)
        self.assertIn('{text:" + "}', show)
        self.assertIn('{text:" - "}', show)
        self.assertIn('{score:{name:"#c1",objective:"mq"}}', show)
