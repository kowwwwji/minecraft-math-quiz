# 算数ダンジョン データパック生成 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python3 build.py` で Minecraft Java 26.3 用データパック `dist/mathquiz/` を生成し、`install.sh` でワールドへ入れれば `/function mathquiz:setup` → `start` で算数ダンジョンが遊べる状態にする。

**Architecture:** Python パッケージ `builder/` が「設定 → 座標（layout）→ mcfunction 文字列（questions / rooms / game）→ ファイル書き出し（pack）」の一方向で生成する。mcfunction は絶対座標のみ（`schedule` 実行はワールドスポーン基準で `@s` が無いため）。出題ロジックはゲーム内のスコアボード演算で行い、Python 側はそれを「生成した mcfunction を小さなシミュレータで実行する」テストで検証する。

**Tech Stack:** Python 3.11（標準ライブラリのみ）、`unittest`。Minecraft Java 26.3 / データパック形式 121。

**Spec:** `docs/superpowers/specs/2026-11-06-math-dungeon-design.md`

## Global Constraints

- 外部ライブラリを入れない。テストは `python3 -m unittest`。
- Minecraft Java **26.3**、データパック形式 **121**。`pack.mcmeta` は `"min_format": 121, "max_format": 121`（26.3 の jar 同梱パックで確認済み）。
- 関数は `data/mathquiz/function/<name>.mcfunction`、タグは `data/minecraft/tags/function/{load,tick}.json`（単数形）。
- mcfunction は**絶対座標のみ**。相対座標 `~` は `execute ... at @s run` の行でだけ許す（`schedule` された関数はワールドスポーンで実行され `@s` が無い）。
- テキストは SNBT 形式（`{text:"せいかい！",color:"green"}`）。text_display の `text` に入れた `score` 成分は**書き込み時に一度だけ解決**されるので、値が変わるたびに `data modify` し直す。
- `random value a..b` は両端含む。範囲の大きさ（b−a+1）は 2 以上でなければならない（`5..5` は失敗）。
- 1 回の `fill` は 32768 ブロック以下。
- スコアボード objective は `mq` 1 つ。ダミープレイヤーは `#` 始まり（`#room #lock #active #max #sub #a #b #ans #op #w1 #w2 #d #s #t #p #c1 #c2 #c3 #r`）。
- 子どもがダメージを受けない・閉じ込められない（anti-goal）。
- 説明・コメントは日本語。「何を」より「なぜ」。コミットは `type(scope) 日本語説明`。

## Review Focus

- 床復帰のとき子どもが床の高さ（縦穴の上端〜はしご付近）にいると石に埋まる → 復帰前に穴の中へ `tp` してから `fill`。Task 3 のテストで「tp 行が fill 行より前」を固定。
- ボタンのパルス（20 tick）中に `tick` が毎回反応し、1 回の押下で何度も処理される → `#lock` で 1 回だけ処理。Task 4 のテストで `check` の全行に `#lock mq matches 0` があることを固定。
- 前回の遊びで `schedule` した床復帰が残ったまま `start` すると、新しい部屋の状態を壊す → `start` の先頭で `schedule clear`。Task 4 のテストで固定。
- `random value N..N`（レベル設定で範囲が 1 になる等）はコマンドが失敗して問題が出ない → 乱数は常に広い固定範囲（`0..999999`）を引き `%=` で縮める。Task 2 のテストで全 `random value` の範囲幅 ≥ 2 を固定。
- `setup` 実行者が y=120 の空中へ tp されて床ができる前に落ちる → 先に `gamemode creative`、建築後にもう一度 tp。Task 4 のテストで順序を固定。

---

## ファイル構成

```
build.py                 # CLI。builder.pack.write_pack(Config(), "dist/mathquiz")
builder/__init__.py
builder/config.py        # Config（原点・部屋サイズ・落とし穴・難易度表）
builder/layout.py        # Box / Room / GoalRoom と座標計算
builder/cmd.py           # SNBT エンコードとコマンド文字列の小さなヘルパ
builder/questions.py     # gen / gen/add / gen/sub / gen/wrong / gen/shuffle / show
builder/rooms.py         # 部屋ごとの関数（room/N/activate|open|drop|restore）と建築コマンド
builder/game.py          # load / setup / start / quit / tick / check / press / correct / wrong / restore / activate / question / goal / level/*
builder/pack.py          # 全関数をまとめて dist に書き出す（pack.mcmeta・タグ）
install.sh
README.md
tests/mcsim.py           # 出題ロジック検証用の最小スコアボード・シミュレータ
tests/test_layout.py  tests/test_questions.py  tests/test_rooms.py  tests/test_game.py  tests/test_pack.py
```

各 `builder/*.py` の生成関数は `dict[str, str]`（キーは名前空間なしの関数名 `gen/add`、値は mcfunction 本文）を返す。`pack.py` がそれを連結する。

---

### Task 1: 設定と座標計算（config / layout）

**Files:**
- Create: `builder/__init__.py`（空）, `builder/config.py`, `builder/layout.py`
- Test: `tests/__init__.py`（空）, `tests/test_layout.py`

**Interfaces:**
- Produces:
  ```python
  # builder/config.py
  @dataclass(frozen=True)
  class Config:
      origin_x: int = 0
      origin_z: int = 0
      floor_y: int = 119        # 床ブロックの y。プレイヤーは floor_y+1 に立つ
      room_count: int = 5       # 問題部屋の数（ゴール部屋を除く）
      room_dx: int = 7          # 内寸: 進行方向 X
      room_dz: int = 9          # 内寸: 幅 Z
      room_h: int = 5           # 内寸: 高さ
      pit_rows: int = 5         # ボタン壁から何列が落とし穴か
      pit_depth: int = 6        # 床下の縦穴の深さ
      water_depth: int = 2
      restore_ticks: int = 60
      question_scale: float = 4.0
      choice_scale: float = 3.0
  LEVELS: dict[str, tuple[int, int]] = {"easy": (5, 0), "normal": (10, 1), "hard": (20, 1)}  # (答えの上限 #max, 引き算あり #sub)

  # builder/layout.py
  Pos = tuple[int, int, int]
  FPos = tuple[float, float, float]
  @dataclass(frozen=True)
  class Box:  # 両端を含む。コンストラクタで x1<=x2 等に正規化する
      x1: int; y1: int; z1: int; x2: int; y2: int; z2: int
      @property
      def volume(self) -> int
      def coords(self) -> str      # "x1 y1 z1 x2 y2 z2"
      def selector(self) -> str    # "x=x1,y=y1,z=z1,dx=x2-x1,dy=y2-y1,dz=z2-z1"
      def contains(self, x: int, y: int, z: int) -> bool
  @dataclass(frozen=True)
  class Room:
      number: int                  # 1 始まり
      interior: Box                # 空気にする内側
      ceiling: Box                 # interior の 1 段上（シーランタン）
      door: Box                    # +X 側の壁の鉄格子 2×2
      pit_floor: tuple[Box, Box]   # 落とし穴になる床（はしご列を除くため 2 箱）
      pit_shaft: Box               # 床下の縦穴（水の層を含む）
      water: Box
      ladder: Box                  # はしご列（x1 列・z2 行、y floor_y-pit_depth .. floor_y+1）
      pit_bottom: FPos             # 床復帰前の退避 tp 先（水の中央）
      buttons: tuple[Pos, Pos, Pos]
      question_pos: FPos
      choice_pos: tuple[FPos, FPos, FPos]
      entry: FPos                  # 入口の立ち位置（tp 先）
  @dataclass(frozen=True)
  class GoalRoom:
      number: int                  # room_count + 1
      interior: Box
      ceiling: Box
      chest: Pos
      fireworks: tuple[FPos, FPos, FPos]
      banner_pos: FPos             # 「ゴール！」表示の位置
  def rooms(cfg: Config) -> list[Room]
  def goal_room(cfg: Config) -> GoalRoom
  def building(cfg: Config) -> Box     # 壁・天井・縦穴を含む石レンガの外形
  def clear_area(cfg: Config) -> Box   # building を各方向 1 広げた範囲（先に空気で埋める）
  ```
- 座標の決め方（部屋 N、`ox=origin_x, oz=origin_z, fy=floor_y, pitch=room_dx+1`）:
  - 壁の X 列は `ox + pitch*(N-1)`。`interior = Box(ox+pitch*(N-1)+1, fy+1, oz+1, ox+pitch*(N-1)+room_dx, fy+room_h, oz+room_dz)`。
  - `door = Box(interior.x2+1, fy+1, oz+1, interior.x2+1, fy+2, oz+2)`（−Z 側の 2 幅通路）。
  - 落とし穴の行は `zp1 = interior.z2 - pit_rows + 1 .. interior.z2`（+Z のボタン壁側）。
  - `ladder = Box(interior.x1, fy-pit_depth, interior.z2, interior.x1, fy+1, interior.z2)`（−X の壁に付ける。穴の上端が常に開いた縦穴）。
  - `pit_floor = (Box(interior.x1+1, fy, zp1, interior.x2, fy, interior.z2), Box(interior.x1, fy, zp1, interior.x1, fy, interior.z2-1))`。
  - `pit_shaft = Box(interior.x1, fy-pit_depth, zp1, interior.x2, fy-1, interior.z2)`、`water` はその下 `water_depth` 段。`pit_bottom = (中央x+0.5, fy-pit_depth+1, 中央z+0.5)`。
  - ボタンは `cx = interior.x1 + room_dx//2` として `((cx-2, fy+2, interior.z2), (cx, fy+2, interior.z2), (cx+2, fy+2, interior.z2))`（+Z 壁に付く。`face=wall,facing=north`）。
  - `choice_pos[k] = (bx+0.5, fy+3.0, interior.z2+0.4)`、`question_pos = (cx+0.5, fy+4.0, interior.z2+0.4)`。
  - `entry = (interior.x1+0.5, fy+1, oz+1.5)`。
  - ゴール部屋は N = room_count+1、`chest` は内部中央の床上、`fireworks` は中央と ±2 の X、y = fy+2、`banner_pos` は question_pos と同じ規則。
  - `building = Box(ox, fy-pit_depth-1, oz, ox+pitch*(room_count+1), fy+room_h+1, oz+room_dz+1)`。

- [ ] **Step 1: テストを書く**

```python
# tests/test_layout.py
import unittest
from builder.config import Config
from builder.layout import Box, rooms, goal_room, building, clear_area

class BoxTest(unittest.TestCase):
    def test_normalizes_and_formats(self):
        b = Box(3, 5, 9, 1, 2, 4)
        self.assertEqual(b.coords(), "1 2 4 3 5 9")
        self.assertEqual(b.selector(), "x=1,y=2,z=4,dx=2,dy=3,dz=5")
        self.assertEqual(b.volume, 3 * 4 * 6)
        self.assertTrue(b.contains(2, 3, 6)); self.assertFalse(b.contains(4, 3, 6))

class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(); self.rooms = rooms(self.cfg)
    def test_room_count_and_sizes(self):
        self.assertEqual(len(self.rooms), 5)
        for r in self.rooms:
            i = r.interior
            self.assertEqual((i.x2 - i.x1 + 1, i.z2 - i.z1 + 1, i.y2 - i.y1 + 1), (7, 9, 5))
    def test_rooms_share_one_wall(self):
        for a, b in zip(self.rooms, self.rooms[1:]):
            self.assertEqual(b.interior.x1, a.interior.x2 + 2)
            self.assertEqual(a.door.x1, a.interior.x2 + 1)
    def test_first_room_origin(self):
        r = self.rooms[0]
        self.assertEqual((r.interior.x1, r.interior.y1, r.interior.z1), (1, 120, 1))
        self.assertEqual(r.door.coords(), "8 120 1 8 121 2")
    def test_pit_floor_covers_five_rows_except_ladder(self):
        r = self.rooms[0]
        cells = {(x, z) for b in r.pit_floor for x in range(b.x1, b.x2 + 1) for z in range(b.z1, b.z2 + 1)}
        self.assertEqual(len(cells), 7 * 5 - 1)
        self.assertNotIn((r.ladder.x1, r.ladder.z1), cells)
        self.assertEqual({b.y1 for b in r.pit_floor}, {119})
        self.assertEqual(min(z for _, z in cells), 5)
    def test_pit_shaft_and_water(self):
        r = self.rooms[0]
        self.assertEqual(r.pit_shaft.coords(), "1 113 5 7 118 9")
        self.assertEqual(r.water.coords(), "1 113 5 7 114 9")
        self.assertEqual(r.ladder.coords(), "1 113 9 1 120 9")
        self.assertEqual(r.pit_bottom[1], 114)
    def test_buttons_on_plus_z_wall(self):
        r = self.rooms[0]
        self.assertEqual(r.buttons, ((2, 121, 9), (4, 121, 9), (6, 121, 9)))
        self.assertEqual(r.question_pos, (4.5, 123.0, 9.4))
        self.assertEqual(r.entry, (1.5, 120, 1.5))
    def test_goal_room_follows_last(self):
        g = goal_room(self.cfg)
        self.assertEqual(g.number, 6)
        self.assertEqual(g.interior.x1, self.rooms[-1].interior.x2 + 2)
        self.assertTrue(g.interior.contains(*g.chest))
    def test_building_fits_one_fill(self):
        self.assertLessEqual(building(self.cfg).volume, 32768)
        self.assertLessEqual(clear_area(self.cfg).volume, 32768)
        self.assertEqual(building(self.cfg).coords(), "0 112 0 48 125 10")
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_layout -v`
Expected: FAIL（`ModuleNotFoundError: builder`）

- [ ] **Step 3: `builder/config.py` と `builder/layout.py` を Interfaces どおりに実装する**

`Box` は `__post_init__` で `object.__setattr__` を使って正規化する（frozen のため）。

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest tests.test_layout -v`
Expected: PASS（9 tests）

- [ ] **Step 5: Commit**

```bash
git add builder/__init__.py builder/config.py builder/layout.py tests/__init__.py tests/test_layout.py
git commit -m "add(builder) 設定と部屋の座標計算を追加"
```

---

### Task 2: 出題ロジックの mcfunction とシミュレータ（questions / cmd）

**Files:**
- Create: `builder/cmd.py`, `builder/questions.py`, `tests/mcsim.py`
- Test: `tests/test_questions.py`

**Interfaces:**
- Consumes: `Config`, `LEVELS`（Task 1）
- Produces:
  ```python
  # builder/cmd.py
  class Raw(str): ...                       # SNBT にそのまま埋める（例 Raw("0b"), Raw("[I;16711680]")）
  def snbt(value) -> str                    # dict→{k:v}, list→[..], str→"..."(エスケープ), bool→true/false, int→n, float→f"{v:g}f"（4.0→4f）, Raw→そのまま
  # 座標（Pos/FPos）はコマンド中で " ".join(str(v) ...) で出す（123.0→"123.0"、120→"120"）
  def fill(box: Box, block: str, mode: str = "") -> str          # "fill x1 y1 z1 x2 y2 z2 block[ mode]"
  def setblock(pos: Pos, block: str) -> str
  def tp_display(tag: str, pos: FPos) -> str                       # "tp @e[type=minecraft:text_display,tag=TAG,limit=1] x y z"
  def set_display_text(tag: str, component) -> str                 # "data modify entity @e[type=minecraft:text_display,tag=TAG,limit=1] text set value <snbt>"
  def score_text(name: str) -> dict                                # {"score": {"name": name, "objective": "mq"}}
  def title(kind: str, component) -> str                           # "title @a <kind> <snbt>"
  def sound(sound_id: str, pitch: float = 1.0) -> str              # "execute as @a at @s run playsound <id> master @s ~ ~ ~ 1 <pitch>"

  # builder/questions.py
  DISPLAY_TAGS = ("mq_q", "mq_c1", "mq_c2", "mq_c3")
  def question_functions(cfg: Config) -> dict[str, str]   # キー: "gen", "gen/add", "gen/sub", "gen/wrong", "gen/shuffle", "show"
  ```
- 出題アルゴリズム（スコアボードのみで書く。乱数は常に `random value 0..999999` を引いて `%=` で縮める）:
  - `gen`: `#r = random 0..1`; `#sub` が 0 なら `#r = 0`; `#r` で `gen/add` / `gen/sub` を呼び、続けて `gen/wrong`, `gen/shuffle`。
  - `gen/add`: `#ans = rand % #max + 1`（1..max）, `#t = #ans + 1`, `#a = rand % #t`（0..ans）, `#b = #ans - #a`, `#op = 0`。
  - `gen/sub`: `#a = rand % #max + 1`（1..max）, `#t = #a + 1`, `#b = rand % #t`（0..a）, `#ans = #a - #b`, `#op = 1`。
  - `gen/wrong`（誤答 2 つ、ループなし）: 各 i∈{1,2} で `#d = rand % 3 + 1`, `#s = rand % 2`, `#wi = #ans ± #d`（`#s` で符号）, `#wi < 0` なら `#wi = #ans + #d`。最後に `#w2 == #w1` なら `#w2 = 2*#ans - #w1`（`#w2 = #ans; #w2 += #ans; #w2 -= #w1`）、それでも `#w2 < 0` なら `#w2 = #ans + 4`。
  - `gen/shuffle`: `#p = rand % 6`、6 通りの `execute if score #p mq matches k run scoreboard players operation #c1 mq = ...` で (`#ans`,`#w1`,`#w2`) を並べ替えて `#c1 #c2 #c3` に入れる。
  - `show`: `#op` が 0 なら `mq_q` に `[{text:"",color:"yellow",bold:true},{score #a},{text:" + "},{score #b},{text:" = ?"}]`、1 なら `" - "`。`mq_c1..3` に `[{text:"",color:"white",bold:true},{score #ck}]`。

- `tests/mcsim.py` は次だけを解釈する最小インタプリタ。未対応のコマンドは `NotImplementedError` にして、gen 系がサポート外の構文を使ったらテストが落ちるようにする:
  ```python
  class Sim:
      def __init__(self, functions: dict[str, str], rng: random.Random): ...
      scores: dict[str, int]                       # "#a" → 値（objective は mq 固定）
      def run(self, name: str) -> None             # "gen" を実行（"function mathquiz:x" を再帰で解決）
      # 対応: scoreboard players set|add|remove|operation(= += -= *= /= %= ※ Java の floorMod/floorDiv),
      #       execute [if|unless score A mq matches R] [if|unless score A mq <op> B mq] [store result score A mq] ... run CMD,
      #       random value a..b（両端含む。a..b の幅が 2 未満なら ValueError）, function mathquiz:NAME, 空行と # コメント
  ```

- [ ] **Step 1: テストを書く**

```python
# tests/test_questions.py
import random, re, unittest
from builder.config import Config, LEVELS
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
        self.assertIn('{text:" + "}', show); self.assertIn('{text:" - "}', show)
        self.assertIn('{score:{name:"#c1",objective:"mq"}}', show)
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_questions -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `tests/mcsim.py` → `builder/cmd.py` → `builder/questions.py` の順に実装する**

`snbt` のキーは引用符なし、文字列値は `"` で囲み `\` と `"` をエスケープする。

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest tests.test_questions -v`
Expected: PASS（5 tests）

- [ ] **Step 5: Commit**

```bash
git add builder/cmd.py builder/questions.py tests/mcsim.py tests/test_questions.py
git commit -m "add(builder) 出題ロジックの mcfunction 生成とシミュレータによる検証を追加"
```

---

### Task 3: 部屋ごとの関数と建築コマンド（rooms）

**Files:**
- Create: `builder/rooms.py`
- Test: `tests/test_rooms.py`

**Interfaces:**
- Consumes: `Room`, `GoalRoom`, `rooms()`, `goal_room()`, `building()`, `clear_area()`（Task 1）、`cmd.*`、`DISPLAY_TAGS`（Task 2）
- Produces:
  ```python
  # builder/rooms.py
  BLOCK_WALL = "minecraft:stone_bricks"; BLOCK_LIGHT = "minecraft:sea_lantern"
  BLOCK_DOOR = "minecraft:iron_bars"; BLOCK_BUTTON = "minecraft:stone_button[face=wall,facing=north]"
  BLOCK_LADDER = "minecraft:ladder[facing=east]"
  def build_commands(cfg: Config) -> list[str]        # setup/build の本体（空気 → 外形 → 各部屋のくり抜き → 縦穴・水・はしご・扉・ボタン・天井 → ゴール部屋・宝箱）
  def reset_commands(cfg: Config) -> list[str]        # start 用: 全部屋の扉を鉄格子に、落とし穴の床を石レンガに戻す
  def room_functions(cfg: Config) -> dict[str, str]   # "room/N/activate", "room/N/open", "room/N/drop", "room/N/restore"（N=1..room_count）
  ```
  - `room/N/activate`: `DISPLAY_TAGS` の 4 体を `question_pos` / `choice_pos` へ `tp`。
  - `room/N/open`: `fill door air`。
  - `room/N/drop`: `pit_floor` の 2 箱を `air`。
  - `room/N/restore`: `pit_floor` の各箱について `tp @a[<箱を y-1..y+1 に広げた selector>] <pit_bottom>` を **先に** 出し、その後で 2 箱を `BLOCK_WALL` で `fill`。
  - 宝箱: `minecraft:chest[facing=west]{Items:[{Slot:0b,id:"minecraft:diamond",count:5},{Slot:1b,id:"minecraft:cake",count:1},{Slot:2b,id:"minecraft:golden_apple",count:3}]}`。

- [ ] **Step 1: テストを書く**

```python
# tests/test_rooms.py
import re, unittest
from builder.config import Config
from builder.layout import rooms, building, clear_area
from builder.rooms import build_commands, reset_commands, room_functions

class RoomsTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(); self.fns = room_functions(self.cfg); self.r1 = rooms(self.cfg)[0]

    def test_all_room_functions_exist(self):
        for n in range(1, 6):
            for k in ("activate", "open", "drop", "restore"):
                self.assertIn(f"room/{n}/{k}", self.fns)

    def test_restore_moves_player_before_filling(self):
        lines = self.fns["room/1/restore"].splitlines()
        tp = [i for i, l in enumerate(lines) if l.startswith("tp @a[")]
        fill = [i for i, l in enumerate(lines) if l.startswith("fill ")]
        self.assertEqual(len(tp), 2); self.assertEqual(len(fill), 2)
        self.assertLess(max(tp), min(fill))
        self.assertIn("tp @a[x=2,y=118,z=5,dx=5,dy=2,dz=4] 4.5 114 7.5", lines[0])

    def test_drop_and_open(self):
        self.assertIn("fill 2 119 5 7 119 9 minecraft:air", self.fns["room/1/drop"])
        self.assertIn("fill 1 119 5 1 119 8 minecraft:air", self.fns["room/1/drop"])
        self.assertEqual(self.fns["room/1/open"].strip(), "fill 8 120 1 8 121 2 minecraft:air")

    def test_activate_moves_four_displays(self):
        body = self.fns["room/2/activate"]
        self.assertEqual(body.count("tp @e[type=minecraft:text_display,tag=mq_"), 4)
        self.assertIn("tag=mq_q,limit=1] 12.5 123.0 9.4", body)

    def test_build_order_and_contents(self):
        cmds = build_commands(self.cfg)
        self.assertEqual(cmds[0], f"fill {clear_area(self.cfg).coords()} minecraft:air")
        self.assertEqual(cmds[1], f"fill {building(self.cfg).coords()} minecraft:stone_bricks")
        joined = "\n".join(cmds)
        self.assertEqual(joined.count("minecraft:stone_button[face=wall,facing=north]"), 15)
        self.assertEqual(joined.count("minecraft:ladder[facing=east]"), 5)
        self.assertEqual(joined.count("minecraft:iron_bars"), 5)
        self.assertEqual(joined.count("minecraft:sea_lantern"), 6)
        self.assertIn("minecraft:chest[facing=west]{Items:[{Slot:0b,id:\"minecraft:diamond\",count:5}", joined)
        self.assertIn("fill 1 113 5 7 114 9 minecraft:water", joined)
        self.assertLess(joined.index("minecraft:water"), joined.index("minecraft:ladder"))

    def test_reset_restores_doors_and_floors(self):
        joined = "\n".join(reset_commands(self.cfg))
        self.assertEqual(joined.count("minecraft:iron_bars"), 5)
        self.assertEqual(joined.count("119"), 10 * 2)  # 床 2 箱 × 5 部屋、各 fill に y が 2 回

    def test_no_relative_coords(self):
        for body in list(self.fns.values()) + ["\n".join(build_commands(self.cfg))]:
            self.assertNotRegex(body, r"(^|\s)~")
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_rooms -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `builder/rooms.py` を実装する**

建築順は「空気 → 外形の石レンガ → 各部屋: 内側を空気、天井をシーランタン、縦穴を空気、水、はしご、扉、ボタン → ゴール部屋: 内側・天井・宝箱」。水をはしごより先に置く（はしご列の水をはしごで置き換えるため）。

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest tests.test_rooms -v`
Expected: PASS（7 tests）

- [ ] **Step 5: Commit**

```bash
git add builder/rooms.py tests/test_rooms.py
git commit -m "add(builder) 部屋ごとの建築・扉・落とし穴の関数生成を追加"
```

---

### Task 4: ゲーム進行の関数（game）

**Files:**
- Create: `builder/game.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: Task 1〜3 の全て
- Produces:
  ```python
  # builder/game.py
  def game_functions(cfg: Config) -> dict[str, str]
  # キー: "load", "setup", "setup/build", "start", "quit", "tick", "check", "press/1", "press/2", "press/3",
  #       "correct", "wrong", "restore", "activate", "question", "goal", "level/easy", "level/normal", "level/hard"
  ```
  各関数の中身（絶対座標・SNBT。`sound()` ヘルパは `execute as @a at @s run playsound ...`）:
  - `load`: `scoreboard objectives add mq dummy`; `execute unless score #max mq = #max mq run function mathquiz:level/normal`; `#active 0`, `#lock 0`。
  - `setup`: `gamemode creative @a` → `tp @a <room1.entry> -90 0` → `tellraw @a {text:"ダンジョンを たてています…"}` → `schedule function mathquiz:setup/build 20t`（tp 後にチャンクが読み込まれるのを待つ）。
  - `setup/build`: `build_commands()` の全行 → `tp @a <room1.entry> -90 0` → `tellraw @a {text:"できました。/function mathquiz:start で はじめます"}`。
  - `start`: `#active 0` → `schedule clear mathquiz:restore` → `kill @e[type=minecraft:marker,tag=mq_return]` → `execute at @a run summon minecraft:marker ~ ~ ~ {Tags:["mq","mq_return"]}`（quit の戻り先。ワールドスポーンへ tp するコマンドは無いため）→ `reset_commands()` → `kill @e[type=minecraft:text_display,tag=mq]` → 4 体を `summon`（下記）→ `gamemode adventure @a` → `tp @a <room1.entry> -90 0` → `#room 1` → `#active 1` → `function mathquiz:activate`。
  - text_display の summon: `summon minecraft:text_display x y z {Tags:["mq","<tag>"],billboard:"vertical",alignment:"center",background:-16777216,brightness:{sky:15,block:15},text:{text:""},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[Sf,Sf,Sf]}}`（S は `question_scale` / `choice_scale`。位置は room1 の `question_pos` / `choice_pos`）。
  - `quit`: `#active 0` → `schedule clear mathquiz:restore` → `gamemode creative @a` → `tp @a @e[type=minecraft:marker,tag=mq_return,limit=1]` → `kill @e[type=minecraft:marker,tag=mq_return]`。
  - `tick`: `execute if score #active mq matches 1 if score #lock mq matches 0 run function mathquiz:check`。
  - `check`: 部屋 N・ボタン k ごとに `execute if score #lock mq matches 0 if score #room mq matches N if block <buttons[k]> minecraft:stone_button[powered=true] run function mathquiz:press/<k+1>`。
  - `press/k`: `#lock 1` → `execute if score #ck mq = #ans mq run function mathquiz:correct` → `execute unless score #ck mq = #ans mq run function mathquiz:wrong`。
  - `correct`: `title("title", {text:"せいかい！",color:"green"})` → `sound("minecraft:entity.player.levelup")` → 部屋ごとに `execute if score #room mq matches N run function mathquiz:room/N/open` → `scoreboard players add #room mq 1` → `function mathquiz:activate`。
  - `wrong`: `title("title", {text:"ざんねん…",color:"red"})` → `sound("minecraft:entity.villager.no", 0.8)` → 部屋ごとに `... run function mathquiz:room/N/drop` → `schedule function mathquiz:restore <restore_ticks>t`。
  - `restore`: 部屋ごとに `... run function mathquiz:room/N/restore` → `function mathquiz:activate`。
  - `activate`: `execute if score #room mq matches <room_count+1> run function mathquiz:goal` → `execute if score #room mq matches 1..<room_count> run function mathquiz:question`。
  - `question`: `function mathquiz:gen` → `function mathquiz:show` → 部屋ごとに `... run function mathquiz:room/N/activate` → `#lock 0`。
  - `goal`: `#active 0` → `title("title", {text:"ゴール！",color:"gold"})` → `title("subtitle", {text:"ぜんぶ せいかい！"})` → `sound("minecraft:entity.player.levelup", 1.2)` → 花火 3 発（`summon minecraft:firework_rocket x y z {LifeTime:20,FireworksItem:{id:"minecraft:firework_rocket",count:1,components:{"minecraft:fireworks":{flight_duration:1b,explosions:[{shape:"large_ball",colors:[I;<色>],has_twinkle:true}]}}}}`、色は 16711680 / 65280 / 255）→ `set_display_text("mq_q", {text:"ゴール！",color:"gold",bold:true})` → `tp_display("mq_q", goal.banner_pos)` → `mq_c1..3` を `{text:""}`。
  - `level/<name>`: `scoreboard players set #max mq <max>` → `#sub <sub>` → `tellraw @a {text:"レベル: <name>（こたえは 0〜<max>）"}`。

- [ ] **Step 1: テストを書く**

```python
# tests/test_game.py
import unittest
from builder.config import Config
from builder.game import game_functions

class GameTest(unittest.TestCase):
    def setUp(self):
        self.fns = game_functions(Config())

    def test_expected_functions(self):
        for k in ("load", "setup", "setup/build", "start", "quit", "tick", "check", "press/1", "press/2", "press/3",
                  "correct", "wrong", "restore", "activate", "question", "goal", "level/easy", "level/normal", "level/hard"):
            self.assertIn(k, self.fns)

    def test_levels(self):
        self.assertIn("scoreboard players set #max mq 5\nscoreboard players set #sub mq 0", self.fns["level/easy"])
        self.assertIn("scoreboard players set #max mq 20\nscoreboard players set #sub mq 1", self.fns["level/hard"])
        self.assertIn("unless score #max mq = #max mq run function mathquiz:level/normal", self.fns["load"])

    def test_check_is_gated_by_lock_and_room(self):
        lines = [l for l in self.fns["check"].splitlines() if l.strip()]
        self.assertEqual(len(lines), 15)
        for l in lines:
            self.assertTrue(l.startswith("execute if score #lock mq matches 0 if score #room mq matches "))
            self.assertIn("minecraft:stone_button[powered=true] run function mathquiz:press/", l)
        self.assertIn("if block 2 121 9 ", lines[0])

    def test_press_sets_lock_then_branches(self):
        lines = self.fns["press/2"].splitlines()
        self.assertEqual(lines[0], "scoreboard players set #lock mq 1")
        self.assertIn("execute if score #c2 mq = #ans mq run function mathquiz:correct", lines)
        self.assertIn("execute unless score #c2 mq = #ans mq run function mathquiz:wrong", lines)

    def test_start_clears_schedule_and_resets(self):
        body = self.fns["start"]
        self.assertLess(body.index("schedule clear mathquiz:restore"), body.index("gamemode adventure @a"))
        self.assertEqual(body.count("summon minecraft:text_display"), 4)
        self.assertIn('scale:[4f,4f,4f]', body); self.assertIn('scale:[3f,3f,3f]', body)
        self.assertIn("tp @a 1.5 120 1.5 -90 0", body)
        self.assertTrue(body.rstrip().endswith("function mathquiz:activate"))

    def test_setup_is_safe_for_the_parent(self):
        body = self.fns["setup"]
        self.assertLess(body.index("gamemode creative @a"), body.index("tp @a "))
        self.assertIn("schedule function mathquiz:setup/build 20t", body)
        self.assertTrue(self.fns["setup/build"].count("tp @a 1.5 120 1.5") == 1)

    def test_wrong_schedules_restore(self):
        self.assertIn("schedule function mathquiz:restore 60t", self.fns["wrong"])
        self.assertIn("execute if score #room mq matches 3 run function mathquiz:room/3/drop", self.fns["wrong"])
        self.assertIn("entity.villager.no", self.fns["wrong"])

    def test_goal_dispatch_and_quit(self):
        self.assertIn("execute if score #room mq matches 6 run function mathquiz:goal", self.fns["activate"])
        self.assertIn("execute if score #room mq matches 1..5 run function mathquiz:question", self.fns["activate"])
        self.assertEqual(self.fns["goal"].count("summon minecraft:firework_rocket"), 3)
        self.assertIn("tp @a @e[type=minecraft:marker,tag=mq_return,limit=1]", self.fns["quit"])

    def test_relative_coords_only_with_at(self):
        for name, body in self.fns.items():
            for l in body.splitlines():
                if "~" in l:
                    self.assertIn(" at @", l, msg=f"{name}: {l}")
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_game -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `builder/game.py` を実装する**

「部屋ごとに dispatch」は `for r in rooms(cfg)` で `execute if score #room mq matches {r.number} run function mathquiz:room/{r.number}/<x>` を並べる小さなヘルパ `_dispatch(cfg, suffix)` にまとめる。

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest tests.test_game -v`
Expected: PASS（9 tests）

- [ ] **Step 5: Commit**

```bash
git add builder/game.py tests/test_game.py
git commit -m "add(builder) ゲーム進行（setup/start/tick/正解/不正解/ゴール）の関数生成を追加"
```

---

### Task 5: データパックの書き出しと CLI（pack / build.py）

**Files:**
- Create: `builder/pack.py`, `build.py`
- Test: `tests/test_pack.py`

**Interfaces:**
- Consumes: `question_functions`, `room_functions`, `game_functions`
- Produces:
  ```python
  # builder/pack.py
  def all_functions(cfg: Config) -> dict[str, str]          # 3 つの dict を結合。キー重複は ValueError
  def write_pack(cfg: Config, out_dir: str | Path) -> Path   # out_dir を作り直して書き出し、out_dir を返す
  # 書き出すもの: pack.mcmeta = {"pack": {"description": "さんすうダンジョン", "min_format": 121, "max_format": 121}}
  #   data/mathquiz/function/<name>.mcfunction（各ファイル先頭に "# <name>: <日本語の役割 1 行>" コメント）
  #   data/minecraft/tags/function/load.json = {"values": ["mathquiz:load"]}, tick.json = {"values": ["mathquiz:tick"]}
  ```
  `build.py`: `python3 build.py [--out dist/mathquiz]`。`argparse` で `--out` のみ。終了時に書いたパスと関数数を表示。

- [ ] **Step 1: テストを書く**

```python
# tests/test_pack.py
import json, re, tempfile, unittest
from pathlib import Path
from builder.config import Config
from builder.pack import all_functions, write_pack

class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = write_pack(Config(), Path(self.tmp.name) / "mathquiz")
    def tearDown(self):
        self.tmp.cleanup()

    def test_mcmeta_and_tags(self):
        meta = json.loads((self.out / "pack.mcmeta").read_text())
        self.assertEqual(meta["pack"]["min_format"], 121); self.assertEqual(meta["pack"]["max_format"], 121)
        tags = self.out / "data/minecraft/tags/function"
        self.assertEqual(json.loads((tags / "load.json").read_text()), {"values": ["mathquiz:load"]})
        self.assertEqual(json.loads((tags / "tick.json").read_text()), {"values": ["mathquiz:tick"]})

    def test_every_function_reference_resolves(self):
        fn_dir = self.out / "data/mathquiz/function"
        existing = {p.relative_to(fn_dir).with_suffix("").as_posix() for p in fn_dir.rglob("*.mcfunction")}
        self.assertEqual(existing, set(all_functions(Config())))
        for p in fn_dir.rglob("*.mcfunction"):
            for ref in re.findall(r"function mathquiz:([\w/]+)", p.read_text()):
                self.assertIn(ref, existing, msg=f"{p.name} -> {ref}")

    def test_no_leading_slash_and_no_blank_functions(self):
        for p in (self.out / "data/mathquiz/function").rglob("*.mcfunction"):
            body = p.read_text()
            self.assertTrue(body.startswith("# "), p.name)
            self.assertNotRegex(body, r"(?m)^/")
            self.assertTrue(any(l and not l.startswith("#") for l in body.splitlines()), p.name)

    def test_rewrite_replaces_old_files(self):
        stale = self.out / "data/mathquiz/function/old.mcfunction"; stale.write_text("say x")
        write_pack(Config(), self.out)
        self.assertFalse(stale.exists())
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_pack -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `builder/pack.py` と `build.py` を実装する**

- [ ] **Step 4: 全テストと実ビルドを確認する**

Run: `python3 -m unittest -v && python3 build.py && find dist/mathquiz -type f | wc -l`
Expected: 全テスト PASS。`dist/mathquiz` に pack.mcmeta + タグ 2 + 関数ファイル（19 + 20 + 6 = 45）。

- [ ] **Step 5: Commit**

```bash
git add builder/pack.py build.py tests/test_pack.py
git commit -m "add(build) データパック一式を dist に書き出す CLI を追加"
```

---

### Task 6: install.sh と README、ゲーム内確認の引き渡し

**Files:**
- Create: `install.sh`, `README.md`
- Modify: `tasks/todo.md`（git 管理外。確認待ちの項目を更新）

**Interfaces:**
- `install.sh`: 冒頭に `WORLD="${WORLD:-$HOME/Library/Application Support/minecraft/saves/さんすう}"`。`python3 build.py` を実行してから `rsync -a --delete dist/mathquiz/ "$WORLD/datapacks/mathquiz/"`。`set -euo pipefail`。ワールドディレクトリが無ければエラー終了。

- [ ] **Step 1: `install.sh` を書き、実行して配置を確認する**

Run: `chmod +x install.sh && ./install.sh && ls "$HOME/Library/Application Support/minecraft/saves/さんすう/datapacks/mathquiz"`
Expected: `data  pack.mcmeta`

- [ ] **Step 2: `README.md` を書く**

内容（恒常的なものだけ。`~/.claude/guides/docs-style.md` に従う）:
1. 何を作るか（設計書へのリンク）。
2. 使い方: `./install.sh` → ワールドを開く → `/reload` → `/function mathquiz:setup` → `/function mathquiz:start` → `/function mathquiz:quit`。難易度 `level/easy|normal|hard`。
3. 動作確認の手順: `/reload` の後 `setup`、1 秒待って建物ができること → `start` で部屋 1 に入り問題と 3 つの数字が見えること → 正解で扉が消えること → 不正解で落ちて水に着水、はしごで戻れ、3 秒後に床と新しい問題が出ること → 5 部屋クリアで「ゴール！」と花火。
4. 開発: `python3 -m unittest`、`python3 build.py`、座標や部屋数は `builder/config.py`。

- [ ] **Step 3: Commit**

```bash
git add install.sh README.md
git commit -m "add(docs) install.sh と遊び方・確認手順の README を追加"
```

- [ ] **Step 4: ゲーム内確認をユーザーへ依頼する**

`tasks/todo.md` に「ユーザー確認待ち」を記し、README の確認手順をそのまま提示する。設計書で「ゲーム内テストで確認」としている箇所（text_display の見え方・向き、`score` 成分の解決、花火、ボタンの反応）は、ここで初めて検証されることを明記する。

---

## 自己レビュー記録

- 仕様カバレッジ: 遊び方（setup/start/quit/level）→ Task 4・6。部屋の体験（表示・扉・落とし穴・はしご・復帰・ゴール）→ Task 3・4。構造（y=120・原点・一直線・内寸・縦穴・水・光源）→ Task 1・3。出題ロジック → Task 2。状態の持ち方（`mq`・`#lock`・`schedule`）→ Task 4。生成の仕方（build.py / install.sh / テスト / README）→ Task 5・6。
- 設計書との差: 部屋 1 の「入口」は開口にせず壁にする（空中 y=120 の建物から外へ出ると落下するため。`start` が tp で中へ入れる）。`quit` の戻り先は `start` 時の位置に置いた marker（ワールドスポーンへ座標なしで tp するコマンドが無いため）。
- 型の整合: `Room.pit_floor` は 2 箱固定、`DISPLAY_TAGS` の順序は (`mq_q`,`mq_c1`,`mq_c2`,`mq_c3`)、関数 dict のキーは名前空間なし。Task 3〜5 はこれを前提にしている。
