import random
import re
import unittest

from builder.config import LEVELS, Config
from builder.questions import question_functions
from tests.mcsim import Sim

OPS = {0: lambda x, y: x + y, 1: lambda x, y: x - y}


def partials(s):
    """式を左から計算した途中の値の列（最初の数、2 項目まで、3 項目まで）。"""
    acc = s["#a"]
    out = [acc]
    acc = OPS[s["#op1"]](acc, s["#b"])
    out.append(acc)
    if s["#terms"] == 3:
        acc = OPS[s["#op2"]](acc, s["#c"])
        out.append(acc)
    return out


def operands(s):
    return [s["#a"], s["#b"]] + ([s["#c"]] if s["#terms"] == 3 else [])


class QuestionTest(unittest.TestCase):
    def setUp(self):
        self.fns = question_functions(Config())

    def trials(self, level, n=3000):
        lv = LEVELS[level]
        sim = Sim(self.fns, random.Random(1))
        for _ in range(n):
            sim.scores.update({"#max": lv.max, "#lo": lv.lo, "#terms": lv.terms, "#sub": lv.sub, "#mul": lv.mul})
            sim.run("gen")
            yield dict(sim.scores)

    def check_expr(self, s, lv):
        self.assertEqual(partials(s)[-1], s["#ans"])
        for v in partials(s):
            self.assertTrue(0 <= v <= lv.max, s)
        for v in operands(s):
            self.assertTrue(lv.lo <= v <= lv.max, s)

    def test_g1_easy_is_three_term_addition_only(self):
        lv = LEVELS["g1_easy"]
        for s in self.trials("g1_easy"):
            self.assertEqual((s["#op1"], s["#op2"]), (0, 0))
            self.check_expr(s, lv)

    def test_g1_normal_mixes_plus_and_minus_and_never_multiplies(self):
        lv = LEVELS["g1_normal"]
        seen = set()
        for s in self.trials("g1_normal"):
            self.assertIn(s["#op1"], (0, 1))
            seen.add((s["#op1"], s["#op2"]))
            self.check_expr(s, lv)
        self.assertEqual(seen, {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_g1_hard_reaches_twenty(self):
        self.assertEqual(max(s["#ans"] for s in self.trials("g1_hard")), 20)

    def test_wrong_answers_near_the_edges_stay_in_range(self):
        # 正解が 0 や上限のとき、誤答は片側にしか取れない（上限 10 なら {1,2,3} / {7,8,9}）
        sim = Sim(self.fns, random.Random(2))
        for ans, expected in ((0, {1, 2, 3}), (10, {7, 8, 9}), (1, {0, 2, 3, 4})):
            seen = set()
            for _ in range(300):
                sim.scores.update({"#max": 10, "#ans": ans})
                sim.run("gen/wrong")
                self.assertNotEqual(sim.scores["#w1"], sim.scores["#w2"])
                seen |= {sim.scores["#w1"], sim.scores["#w2"]}
            self.assertEqual(seen, expected)

    def test_g2_easy_is_two_digit_two_term(self):
        lv = LEVELS["g2_easy"]
        ops = set()
        for s in self.trials("g2_easy"):
            ops.add(s["#op1"])
            self.assertEqual(s["#terms"], 2)
            self.check_expr(s, lv)
        self.assertEqual(ops, {0, 1})

    def test_g2_normal_mixes_kuku_about_half(self):
        lv = LEVELS["g2_normal"]
        kuku = 0
        for s in self.trials("g2_normal"):
            if s["#op1"] == 2:
                kuku += 1
                self.assertTrue(1 <= s["#a"] <= 9 and 1 <= s["#b"] <= 9)
                self.assertEqual(s["#ans"], s["#a"] * s["#b"])
            else:
                self.check_expr(s, lv)
        self.assertTrue(1200 <= kuku <= 1800, kuku)

    def test_g2_hard_has_three_terms_and_kuku(self):
        lv = LEVELS["g2_hard"]
        seen = set()
        for s in self.trials("g2_hard"):
            if s["#op1"] == 2:
                seen.add("kuku")
            else:
                seen.add((s["#op1"], s["#op2"]))
                self.check_expr(s, lv)
        self.assertEqual(seen, {"kuku", (0, 0), (0, 1), (1, 0), (1, 1)})

    def test_kuku_wrong_answers_are_neighbours_in_the_table(self):
        for s in self.trials("g2_normal"):
            if s["#op1"] != 2:
                continue
            a, b = s["#a"], s["#b"]
            wrong = {s["#c1"], s["#c2"], s["#c3"]} - {s["#ans"]}
            allowed = {(a + 1) * b, (a - 1) * b, a * (b + 1), a * (b - 1), a * (b + 2), a * (b - 2)}
            self.assertEqual(len(wrong), 2, s)
            self.assertTrue(wrong <= allowed, s)

    def test_choices_distinct_nonnegative_with_one_correct(self):
        for level in LEVELS:
            positions = set()
            for s in self.trials(level):
                c = [s["#c1"], s["#c2"], s["#c3"]]
                self.assertEqual(len(set(c)), 3, s)
                self.assertEqual(c.count(s["#ans"]), 1, s)
                self.assertTrue(all(v >= 0 for v in c), s)
                if s["#op1"] != 2:
                    self.assertTrue(all(abs(v - s["#ans"]) <= 3 for v in c), s)
                self.assertTrue(all(v <= LEVELS[level].max for v in c), s)
                positions.add(c.index(s["#ans"]))
            self.assertEqual(positions, {0, 1, 2}, level)

    def test_random_ranges_are_wide(self):
        for body in self.fns.values():
            for a, b in re.findall(r"random value (-?\d+)\.\.(-?\d+)", body):
                self.assertGreaterEqual(int(b) - int(a) + 1, 2)

    def test_show_covers_every_shape(self):
        show = self.fns["show"]
        for tag in ("mq_q", "mq_c1", "mq_c2", "mq_c3"):
            self.assertIn(f"tag={tag},limit=1] text set value", show)
        self.assertIn("execute if score #op1 mq matches 2 run ", show)
        self.assertIn('{text:" × "}', show)
        self.assertEqual(show.count("execute if score #terms mq matches 2 if score #op1 mq matches "), 2)
        self.assertEqual(show.count("execute if score #terms mq matches 3 if score #op1 mq matches "), 4)
        self.assertIn('{score:{name:"#c",objective:"mq"}}', show)
        self.assertIn('{score:{name:"#c1",objective:"mq"}}', show)
