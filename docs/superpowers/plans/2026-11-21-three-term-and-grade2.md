# 3 つの数の式・2 年生向け難易度 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 設計書の 2026-11-21 改訂（1 年生向けは 3 つの数の式、2 年生向けに 2 桁の足し算・引き算と九九。難易度は `g1_easy` 〜 `g2_hard` の 6 段階）を `builder/` に載せて `python3 build.py` で生成できるようにする。

**Architecture:** 難易度は 5 つのスコア（`#max` `#lo` `#terms` `#sub` `#mul`）で表し、出題は「足し算・引き算の式（`gen/expr`）」と「九九（`gen/mul`）」の 2 系統だけにする。式は左から 1 項ずつ `gen/term` で決め、途中の値 `#acc` を見て `+` `-` の選べる側だけを選ぶので、途中計算と答えが必ず 0〜上限に収まる（再試行ループを持たない）。表示は `#terms` `#op1` `#op2` の組み合わせで 7 通りの `data modify` を並べる。状態機械（`game.py`）は難易度関数と `load` の既定値判定だけ変える。

**Tech Stack:** Python 3.11（標準ライブラリのみ）、`unittest`、`tests/mcsim.py`（スコアボード・シミュレータ）。Minecraft Java 26.3 / データパック形式 121。

**Spec:** `docs/superpowers/specs/2026-11-06-math-dungeon-design.md`（2026-11-21 改訂分: 難易度表、出題ロジック、状態の持ち方）

## Global Constraints

- 前計画 `docs/superpowers/plans/2026-11-06-math-dungeon-datapack.md` の Global Constraints をすべて引き継ぐ（絶対座標、SNBT、`random` の範囲幅 2 以上、objective `mq`、日本語コメント、コミット規約 `type(scope) 日本語説明`）。
- 乱数は既存の `_rand_mod` / `_rand_below`（`random value 0..999999` を `%=` で縮める）だけで引く。`%=` の右辺は必ず 1 以上にする（範囲が空になる引き方をしない）。
- 分岐先が条件の値を変えうる `execute if` / `unless` の対は、比較結果をフラグに固定してから分岐する（`press/*` の `#hit` と同じ理由）。
- `gen/*` が使う構文は `tests/mcsim.py` が解釈できるものだけ（`scoreboard players set/add/remove/operation`、`execute if/unless score ... matches|<比較> ... run`、`execute store result score`、`random value`、`function`）。シミュレータに手を入れる必要が出たら、その理由をコメントに残す。
- 新しい関数には `builder/pack.py` の `DESCRIPTIONS` に説明を足す（無いと `describe()` が `KeyError` で生成が止まる）。消した関数の説明も消す。
- 難易度名は `g1_easy` `g1_normal` `g1_hard` `g2_easy` `g2_normal` `g2_hard`。旧 `easy` `normal` `hard` は残さない。既定は `g1_normal`。
- 設計書の難易度表の値（上限 / 下限 / 項数 / 引き算 / 九九）をそのまま `LEVELS` に写す。

## Review Focus

- 古い版で遊んだワールドには `#max` だけが残っている。`load` の既定値判定を `#max` のままにすると `#terms` 等が入らず `gen/expr` が `%= 0` 等で壊れる → 判定は `#terms` で行う。Task 1 のテストで固定。
- 引き算なし（`g1_easy`）で `a` が上限近くになると、後ろの項が下限以上で取れない → 取り置き `#room` を `a` と 2 項目に効かせる。Task 2 のテスト（3000 回の試行で全項が下限以上）で固定。
- 2 桁の引き算で途中の値が 10 未満になった直後（`15 - 12`）は `-` が選べないので `+` に倒す。その `+` も上限を超えてはいけない → `#plus` / `#minus` のフラグで両方を見る。Task 2 のテスト（途中計算が 0〜上限）で固定。
- 答えが上限付近（`97 + 2`）のとき、旧 `gen/wrong` の「正解 ±1〜3」は 100〜102 の 3 桁を選択肢に出す → 誤答は `[max(ans−3, 0), min(ans+3, 上限)]` の候補から正解を除いて選ぶ。Task 2 のテスト（選択肢が 0〜上限）で固定。
- 九九で `a = b` かつ同じ向きにずらすと誤答 2 つが一致する（`3 × 3` → `4 × 3` と `3 × 4`）→ 一致したら `a × (b ± 2)`。Task 2 のテストで固定。
- 式が長くなり（最長 `23 + 45 - 18 = ?`）、拡大率 4 のままだとボタン壁（幅 7 ブロック）からはみ出て壁に埋まる → 問題の拡大率を 3 にする。Task 3 のテストで固定。

---

## ファイル構成

```
builder/config.py     # Modify: Level dataclass、LEVELS を 6 段階に、DEFAULT_LEVEL、question_scale 3.0
builder/game.py       # Modify: _load の既定値判定、_level が 5 つのスコアを入れる
builder/questions.py  # Modify: gen / gen/expr / gen/term / gen/term/add / gen/term/sub / gen/mul / gen/mul_wrong / show（gen/add, gen/sub は削除）
builder/pack.py       # Modify: 関数の説明
README.md             # Modify: 対象学年、難易度表、確認手順
CLAUDE.md             # Modify: 冒頭の対象学年
tests/test_game.py  tests/test_questions.py  # Modify
```

---

### Task 1: 難易度の定義と切り替え（config / game / pack）

**Files:**
- Modify: `builder/config.py`（`LEVELS` 付近）, `builder/game.py`（`_load`, `_level`, `game_functions`）, `builder/pack.py`（`PATTERNS` はそのまま。`level/(\w+)` が新名にも合う）
- Test: `tests/test_game.py`

**Interfaces:**
- Produces:
  ```python
  # builder/config.py
  @dataclass(frozen=True)
  class Level:
      max: int    # 答えと途中の計算の上限（#max）
      lo: int     # 式に出る数の下限（#lo）
      terms: int  # 足し算・引き算の式の項数 2 か 3（#terms）
      sub: int    # 引き算を混ぜるか 0/1（#sub）
      mul: int    # 九九を 1/2 で混ぜるか 0/1（#mul）
      label: str  # tellraw 用の説明（ひらがな）

  LEVELS: dict[str, Level]  # 設計書の表の順に g1_easy, g1_normal, g1_hard, g2_easy, g2_normal, g2_hard
  DEFAULT_LEVEL = "g1_normal"
  ```
  `label` は順に `3つの かずの たしざん` / `3つの かずの たしざん・ひきざん` / 同 / `2けたの たしざん・ひきざん` / `2けたの たしざん・ひきざん と くく` / `2けた 3つの かずの たしざん・ひきざん と くく`。
- `game.py` の `_level(name: str, lv: Level) -> list[str]` は `#max` `#lo` `#terms` `#sub` `#mul` をこの順に `scoreboard players set` し、最後に `tellraw`（`レベル: {name}（{label}、こたえは 0〜{max}）`）。
- `_load` の既定値行は `execute unless score #terms mq = #terms mq run function mathquiz:level/g1_normal`。

- [ ] **Step 1: テストを書き換える**

`tests/test_game.py` の `test_expected_functions` の `"level/easy", "level/normal", "level/hard"` を 6 つの新名に置き換え、`test_levels` を次にする:

```python
    def test_levels(self):
        self.assertEqual(
            self.fns["level/g1_easy"].splitlines()[:5],
            [
                "scoreboard players set #max mq 10",
                "scoreboard players set #lo mq 1",
                "scoreboard players set #terms mq 3",
                "scoreboard players set #sub mq 0",
                "scoreboard players set #mul mq 0",
            ],
        )
        self.assertIn("scoreboard players set #max mq 99\nscoreboard players set #lo mq 10\nscoreboard players set #terms mq 3\nscoreboard players set #sub mq 1\nscoreboard players set #mul mq 1", self.fns["level/g2_hard"])
        self.assertIn("scoreboard players set #terms mq 2", self.fns["level/g2_easy"])
        self.assertNotIn("level/easy", self.fns)
        # 古いワールドには #max だけ残っているので、この改訂で増えた #terms で未設定を判定する
        self.assertIn("unless score #terms mq = #terms mq run function mathquiz:level/g1_normal", self.fns["load"])
        self.assertNotIn("unless score #max mq", self.fns["load"])
        self.assertIn("こたえは 0〜99", self.fns["level/g2_normal"])
```

- [ ] **Step 2: 落ちることを確認する**

Run: `python3 -m unittest tests.test_game -v`
Expected: `test_expected_functions` と `test_levels` が FAIL（`level/g1_easy` が無い）。

- [ ] **Step 3: `builder/config.py` に `Level` と 6 段階の `LEVELS`、`DEFAULT_LEVEL` を定義する**

旧 `LEVELS: dict[str, tuple[int, int]]` を置き換える。値は設計書の表どおり。

- [ ] **Step 4: `builder/game.py` の `_load` / `_level` / `game_functions` を `Level` に合わせる**

`from builder.config import DEFAULT_LEVEL, LEVELS, Level, Config`。`game_functions` は `{f"level/{name}": _level(name, lv) for name, lv in LEVELS.items()}`。

- [ ] **Step 5: 全テストを通す**

Run: `python3 -m unittest`
Expected: `test_game` は PASS。`test_questions` は旧 `LEVELS[level]` のタプル展開で ERROR になるが、Task 2 で書き換えるのでここでは `tests.test_game tests.test_pack tests.test_layout tests.test_rooms` が PASS していればよい。

- [ ] **Step 6: コミット**

```bash
git add builder/config.py builder/game.py tests/test_game.py
git commit -m "update(builder) 難易度を学年×3段階の 6 つにし、5 つのスコアで出題条件を表す"
```

---

### Task 2: 出題ロジック（questions / pack）

**Files:**
- Modify: `builder/questions.py`（`_gen` 以降を書き換え）, `builder/pack.py`（`DESCRIPTIONS`）
- Test: `tests/test_questions.py`（全面書き換え）

**Interfaces:**
- Consumes: Task 1 の `LEVELS: dict[str, Level]`、スコア `#max` `#lo` `#terms` `#sub` `#mul`。
- Produces: 関数名と、各関数が書くスコア
  ```
  gen            : #r（0 = 式, 1 = 九九。#mul が 0 なら常に 0）を決めて gen/expr か gen/mul、gen/wrong か gen/mul_wrong を呼び、最後に gen/shuffle
  gen/expr       : #a #op1 #b（#terms が 3 なら #op2 #c も）#ans。#op は 0 = +, 1 = -
  gen/term       : #acc と #room を見て 1 項ぶん #n（数）と #o（演算）を決め、#acc を更新する
  gen/term/add   : #n = #lo + 乱数 % (#max - #acc - #room - #lo + 1)、#acc += #n
  gen/term/sub   : #n = #lo + 乱数 % (#acc - #lo + 1)、#acc -= #n
  gen/mul        : #a #b（1〜9）#ans = #a × #b、#op1 = 2
  gen/wrong      : #w1 #w2 を [max(#ans−3, 0), min(#ans+3, #max)] の候補（#ans を除く）から重複なく選ぶ
  gen/mul_wrong  : #w1 = (#a ± 1) × #b、#w2 = #a × (#b ± 1)。一致したら #w2 = #a × (#b ± 2)
  gen/shuffle    : 既存のまま
  show           : #op1 が 2 なら「a × b = ?」、#terms が 2 なら「a ± b = ?」、3 なら「a ± b ± c = ?」
  ```
  一時スコアは `#t` `#r` `#s` `#d` `#e` `#p` `#n` `#o` `#acc` `#room` `#plus` `#minus` `#lo2` `#hi2` `#m1` `#m2`。`#terms` は難易度の値なので出題中に書き換えない。

- [ ] **Step 1: テストを書く**

`tests/test_questions.py` を次の内容に書き換える（`trials` は `Level` の 5 値をスコアに入れて `gen` を回す）:

```python
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
```

- [ ] **Step 2: 落ちることを確認する**

Run: `python3 -m unittest tests.test_questions -v`
Expected: `#lo` 等を見ない旧 `gen` が `#terms` / `#op2` を書かないため `KeyError` で ERROR、`test_show_covers_every_shape` が FAIL。

- [ ] **Step 3: `builder/questions.py` を書き換える**

`_gen` / `_gen_add` / `_gen_sub` を `_gen` / `_gen_expr` / `_gen_term` / `_gen_term_add` / `_gen_term_sub` / `_gen_mul` / `_gen_mul_wrong` に置き換え、`_show` を 7 通りにする。`_gen_wrong`（と `_wrong_one`）は下の手順に書き換える。`_gen_shuffle` はそのまま。`question_functions` の辞書を新しい関数名にする。

`gen/expr` の手順（スコア演算だけで書く。乱数は `_rand_mod(target, "#t")` で `#t` を法にする）:

```
#room = #lo × (#terms − 1)。#sub が 1 なら 0          （引き算なしのときだけ後ろの項ぶんを取り置く）
#t = #max − #room − #lo + 1 ; #a = 乱数 % #t + #lo ; #acc = #a
#room = #lo。#terms が 2 または #sub が 1 なら 0       （3 項・引き算なしのときだけ 3 項目ぶんを取り置く）
function gen/term ; #b = #n ; #op1 = #o
#room = 0
#terms が 3 なら function gen/term ; #c = #n ; #op2 = #o   （3 行とも execute if score #terms mq matches 3 で門番）
#ans = #acc
```

`gen/term` の手順:

```
#t = #max − #acc − #room ; #plus = (#t >= #lo) ? 1 : 0        （execute if score #t mq >= #lo mq run set #plus 1）
#minus = (#sub == 1 かつ #acc >= #lo) ? 1 : 0
#o = 乱数 % 2 ; #plus が 0 なら #o = 1 ; #minus が 0 なら #o = 0
#o が 0 なら function gen/term/add、1 なら function gen/term/sub
```

`gen/mul_wrong` の手順（向き `#d` `#e` は ±1。`#w2 = #w1` の判定は先に `#s` へ固定してから分岐する）:

```
#d = ±1（乱数）。#a が 9 なら −1、1 なら +1 ; #w1 = (#a + #d) × #b
#e = ±1（乱数）。#b が 9 なら −1、1 なら +1 ; #w2 = #a × (#b + #e)
#s = (#w2 == #w1) ? 1 : 0 ; #s が 1 なら #w2 = #a × (#b + 2 × #e)
```

`gen/wrong` の手順（候補の範囲 `[#lo2, #hi2]` から正解と `#w1` を飛ばして選ぶ。乱数の法 `#t` は常に 3 以上になる）:

```
#lo2 = #ans − 3。0 未満なら 0 ; #hi2 = #ans + 3。#max を超えたら #max
#t = #hi2 − #lo2                                  （候補の数。#ans ぶんを除いた個数）
#w1 = 乱数 % #t + #lo2 ; #w1 >= #ans なら #w1 += 1   （#ans を飛ばす）
#t −= 1
#w2 = 乱数 % #t + #lo2
#m1 = min(#ans, #w1) ; #m2 = max(#ans, #w1)
#w2 >= #m1 なら #w2 += 1 ; 続けて #w2 >= #m2 なら #w2 += 1   （小さい方から順に飛ばす。順番を守ること）
```

`2 × 2` で両方 −1 を引くと `#w2 = 2 × 0 = 0` になるが、0 以上・重複なしは満たすので許容する（設計書どおり）。

- [ ] **Step 4: `builder/pack.py` の `DESCRIPTIONS` を更新する**

`gen` `gen/add` `gen/sub` の項目を消し、`gen` `gen/expr` `gen/term` `gen/term/add` `gen/term/sub` `gen/mul` `gen/mul_wrong` の説明（日本語、役割を一行）を足す。

- [ ] **Step 5: 全テストを通す**

Run: `python3 -m unittest`
Expected: すべて PASS（`test_pack` の参照解決で新関数名が揃っていることも確認される）。

- [ ] **Step 6: 生成して目で確認する**

Run: `python3 build.py && cat dist/mathquiz/data/mathquiz/function/gen/expr.mcfunction dist/mathquiz/data/mathquiz/function/show.mcfunction`
Expected: 相対座標や未定義スコアが無く、`show` に 7 行の `data modify` がある。

- [ ] **Step 7: コミット**

```bash
git add builder/questions.py builder/pack.py tests/test_questions.py
git commit -m "add(builder) 3 つの数の式と 2 桁の足し引き、九九の出題を追加"
```

---

### Task 3: 表示の拡大率と文書（config / README / CLAUDE.md）

**Files:**
- Modify: `builder/config.py`（`question_scale`）, `README.md`, `CLAUDE.md`（冒頭 1 行）
- Test: `tests/test_game.py`（`test_start_clears_schedule_and_resets`）

**Interfaces:**
- Consumes: Task 1 の難易度名と `label`。
- Produces: `Config.question_scale = 3.0`（最長の式 `23 + 45 - 18 = ?` は 88 px × 0.025 × 3 = 6.6 ブロックで、ボタン壁の幅 7 に収まる）。

- [ ] **Step 1: テストを直す**

`tests/test_game.py` の `test_start_clears_schedule_and_resets` の `scale:[4f,4f,4f]` の行を次にする:

```python
        # 最長の式（23 + 45 - 18 = ?）がボタン壁の幅 7 ブロックに収まる拡大率
        self.assertEqual(body.count("scale:[3f,3f,3f]"), 4)
        self.assertNotIn("scale:[4f,4f,4f]", body)
```

- [ ] **Step 2: 落ちることを確認する**

Run: `python3 -m unittest tests.test_game -v`
Expected: `test_start_clears_schedule_and_resets` が FAIL。

- [ ] **Step 3: `builder/config.py` の `question_scale` を `3.0` にする**

コメントに「最長の式がボタン壁の幅に収まる値」と理由を書く。

- [ ] **Step 4: テストを通す**

Run: `python3 -m unittest`
Expected: すべて PASS。

- [ ] **Step 5: README と CLAUDE.md を更新する**

- `README.md`: 冒頭の「小学一年生向け」を「小学 1〜2 年生向け」に、例を `3 + 4 + 2 = ?` に。難易度の箇条書きを設計書と同じ 6 行の表に置き換える（関数名・内容・答えの範囲）。「動作確認の手順」に 7 として「`/function mathquiz:level/g2_hard` に切り替え、次の問題から 2 桁の 3 つの数の式か九九（`7 × 8 = ?`）が出ること。3 桁の数が式にも選択肢にも出ないこと。式が壁の幅に収まって読めること。九九の選択肢が `56` `48` `63` のように表の隣の数になっていること」を足す。
- `CLAUDE.md`: 1 行目の「小学一年生向け」を「小学 1〜2 年生向け」に。

- [ ] **Step 6: コミット**

```bash
git add builder/config.py tests/test_game.py README.md CLAUDE.md
git commit -m "docs(readme) 学年別の難易度 6 段階と 2 年生向けの確認手順を追加し、問題の拡大率を壁幅に合わせる"
```

---

### 完了後（実装者がやること）

- `python3 -m unittest` が全件 PASS、`./install.sh` でワールドへコピー。
- コミットで止め、ブランチ `add/three-term-and-grade2` と worktree パスを報告する。マージはしない。
- 親に伝えるゲーム内確認手順: `/reload` → `/function mathquiz:setup` → `/function mathquiz:start`（既定 `g1_normal` で 3 つの数の式が出ること）→ 正解・不正解を 1 回ずつ → `/function mathquiz:level/g2_normal` で次の問題に九九か 2 桁の式が出ること → `/function mathquiz:level/g2_hard` で 2 桁の 3 つの数の式が壁に収まること。
