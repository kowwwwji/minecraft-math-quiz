# 命 3 つ・TNT 爆発・色付きボタン・ゴール入室時の花火 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 設計書の 2026-11-07 改訂（命 3 つと 3 回目の TNT 爆発、木のボタンと色付きの的、ゴール部屋に入った瞬間の花火）を、既存の `builder/` に載せて `python3 build.py` で生成できるようにする。

**Architecture:** 既存の一方向依存（config → layout → cmd → questions / rooms / game → pack）を保ち、座標の追加は `layout.py`、ブロックの変更は `rooms.py`、状態機械の変更は `game.py` に閉じる。新しい状態は `#active 2`（爆発待ち〜リスポーン待ち）と `#miss`（通算の不正解数）だけ。時間差は既存どおり `schedule`、死亡検出は `deathCount` 基準の objective `mq_deaths` を `tick` で見る。

**Tech Stack:** Python 3.11（標準ライブラリのみ）、`unittest`。Minecraft Java 26.3 / データパック形式 121。

**Spec:** `docs/superpowers/specs/2026-11-06-math-dungeon-design.md`（2026-11-07 改訂分）

## Global Constraints

- 前計画 `docs/superpowers/plans/2026-11-06-math-dungeon-datapack.md` の Global Constraints をすべて引き継ぐ（絶対座標、SNBT、`random` の範囲幅、`fill` 上限、objective `mq`、日本語コメント、コミット規約）。
- 分岐先が条件の値を変えうる `execute if` / `unless` の対は、比較結果をフラグに固定してから分岐する（`tasks/lessons.md`）。
- 26.3 の jar で確認済み: TNT エンティティの `fuse` / `explosion_power`、`spawnpoint`、`damage`、`return`、`deathCount` 基準、`oak_button`、`*_concrete`、`glass`、`particle minecraft:explosion_emitter`。
- 子どもがダメージを受ける・死ぬのは 3 回目の不正解だけ。花火は子どもと同じ部屋で爆発させない。
- 新しい関数には `builder/pack.py` の `DESCRIPTIONS` / `PATTERNS` に説明を足す（無いと `describe()` が KeyError で生成が止まる）。

## Review Focus

- 導火線の 2 秒間に `quit`（または `start`）を打たれると、TNT が残り `boom/kill` が後から走って死ぬ → 両方で `schedule clear mathquiz:boom/kill` と TNT の `kill`。Task 3 のテストで固定。
- 遊んでいる最中に落下など別の理由で死んでも「ゲームオーバー処理」が走ってはいけない → `tick` のリスポーン検出は `#active mq matches 2` で門番。Task 3 のテストで固定。
- `start` のやり直しで前回の不正解数や死亡回数が残る → `start` で `#miss 0` と `mq_deaths` のリセット。Task 3 のテストで固定。
- ゴール部屋に立ち続けると花火が毎ティック上がる → `goal/enter` の先頭で `#active 0`。Task 4 のテストで固定。
- 花火が子どもと同じ高さで爆発する → 発射位置は屋根の 1 段上（`building().y2 + 1`）。Task 1 のテストで固定。

---

## ファイル構成

```
builder/config.py     # Modify: lives / tnt_fuse_ticks / firework_volleys / firework_interval_ticks
builder/layout.py     # Modify: Room.button_backs、GoalRoom.floor、GoalRoom.fireworks を屋根の上へ
builder/rooms.py      # Modify: 木のボタン・色付きの的・ゴール部屋の天井ガラスと光る床
builder/game.py       # Modify: 命と TNT（wrong / wrong/drop / boom / boom/kill / gameover / tick / start / setup / quit / load）、ゴール入室（goal / goal/enter / goal/fireworks / tick）
builder/pack.py       # Modify: 新しい関数の説明
README.md             # Modify: 遊び方と確認手順
tests/test_layout.py  tests/test_rooms.py  tests/test_game.py  # Modify
```

---

### Task 1: 設定と座標（config / layout）

**Files:**
- Modify: `builder/config.py`, `builder/layout.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Produces:
  ```python
  # builder/config.py  Config に追加
  lives: int = 3                    # 不正解できる回数（通算）
  tnt_fuse_ticks: int = 40          # TNT の導火線（2 秒）
  firework_volleys: int = 3         # 花火を何回上げるか
  firework_interval_ticks: int = 15 # 花火の間隔
  # builder/layout.py
  Room.button_backs: tuple[Pos, Pos, Pos]   # ボタンの裏の壁ブロック（z = interior.z2 + 1、x/y はボタンと同じ）
  GoalRoom.floor: Box                       # 内側の床 1 段（y = floor_y）。光るブロックにする
  GoalRoom.fireworks                        # y を building(cfg).y2 + 1（屋根の 1 段上）に変更。x/z は従来どおり
  ```

- [ ] **Step 1: テストを書く**

`tests/test_layout.py` に追加:

```python
    def test_button_backs_are_in_the_wall_behind_buttons(self):
        r = self.rooms[0]
        self.assertEqual(r.button_backs, ((2, 121, 10), (4, 121, 10), (6, 121, 10)))

    def test_goal_floor_and_fireworks_above_roof(self):
        g = goal_room(self.cfg)
        self.assertEqual(g.floor.coords(), "41 119 1 47 119 9")
        self.assertEqual(g.fireworks, ((42.5, 126.0, 5.5), (44.5, 126.0, 5.5), (46.5, 126.0, 5.5)))
        self.assertGreater(min(y for _, y, _ in g.fireworks), building(self.cfg).y2)

    def test_config_defaults_for_lives_and_fireworks(self):
        self.assertEqual((self.cfg.lives, self.cfg.tnt_fuse_ticks), (3, 40))
        self.assertEqual((self.cfg.firework_volleys, self.cfg.firework_interval_ticks), (3, 15))
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_layout -v`
Expected: FAIL 3 件（`AttributeError: button_backs` / `floor` / `lives`）

- [ ] **Step 3: `Config` のフィールドと `Room.button_backs` / `GoalRoom.floor` を追加し、`GoalRoom.fireworks` の y を `building(cfg).y2 + 1` にする**

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest -v`
Expected: 全テスト PASS（test_layout 12 件）

- [ ] **Step 5: Commit**

```bash
git add builder/config.py builder/layout.py tests/test_layout.py
git commit -m "add(builder) 命・TNT・花火の設定と、的の裏ブロック・ゴール部屋の床・屋根上の花火位置を追加"
```

---

### Task 2: 木のボタン・色付きの的・ゴール部屋の天井と床（rooms）

**Files:**
- Modify: `builder/rooms.py`
- Test: `tests/test_rooms.py`

**Interfaces:**
- Consumes: `Room.button_backs`, `GoalRoom.floor`（Task 1）
- Produces:
  ```python
  BLOCK_BUTTON = "minecraft:oak_button[face=wall,facing=north]"
  BLOCK_BUTTON_OFF = "minecraft:oak_button[face=wall,facing=north,powered=false]"
  BLOCK_BUTTON_ON = "minecraft:oak_button[powered=true]"        # check の if block 用（Task 3 が使う）
  BLOCK_BUTTON_BACKS = ("minecraft:red_concrete", "minecraft:yellow_concrete", "minecraft:light_blue_concrete")
  BLOCK_GLASS = "minecraft:glass"
  ```
  - `_build_room`: ボタンの前に `button_backs` を `BLOCK_BUTTON_BACKS` で `setblock`（左から赤・黄・青）。
  - `_build_goal`: 内側を空気 → 天井を `BLOCK_GLASS` → `floor` を `BLOCK_LIGHT` → 宝箱。

- [ ] **Step 1: テストを書く（既存の期待値も更新）**

`tests/test_rooms.py` の `test_build_order_and_contents` を次に差し替え、`test_restore_unpowers_buttons_before_lock_release` の `unpowered` を `oak_button` に変える:

```python
    def test_build_order_and_contents(self):
        cmds = build_commands(self.cfg)
        self.assertEqual(cmds[0], f"fill {clear_area(self.cfg).coords()} minecraft:air")
        self.assertEqual(cmds[1], f"fill {building(self.cfg).coords()} minecraft:stone_bricks")
        joined = "\n".join(cmds)
        self.assertEqual(joined.count("minecraft:oak_button[face=wall,facing=north]"), 15)
        self.assertNotIn("stone_button", joined)
        for block in ("minecraft:red_concrete", "minecraft:yellow_concrete", "minecraft:light_blue_concrete"):
            self.assertEqual(joined.count(block), 5)
        self.assertIn("setblock 2 121 10 minecraft:red_concrete", joined)
        self.assertEqual(joined.count("minecraft:ladder[facing=east]"), 5)
        self.assertEqual(joined.count("minecraft:iron_bars"), 5)
        self.assertEqual(joined.count("minecraft:sea_lantern"), 6)  # 部屋 5 つの天井 + ゴール部屋の床
        self.assertIn("fill 41 125 1 47 125 9 minecraft:glass", joined)
        self.assertIn("fill 41 119 1 47 119 9 minecraft:sea_lantern", joined)
        self.assertIn('minecraft:chest[facing=west]{Items:[{Slot:0b,id:"minecraft:diamond",count:5}', joined)
        self.assertIn("fill 1 113 5 7 114 9 minecraft:water", joined)
        self.assertLess(joined.index("minecraft:water"), joined.index("minecraft:ladder"))
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_rooms -v`
Expected: FAIL（`oak_button` の数が 0、`glass` が無い）

- [ ] **Step 3: `builder/rooms.py` の定数と `_build_room` / `_build_goal` を Interfaces どおりに変える**

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest -v`
Expected: test_rooms PASS。test_game の `test_check_is_gated_by_lock_and_room` は `stone_button` を期待したまま FAIL（Task 3 で直す）。

- [ ] **Step 5: Commit**

```bash
git add builder/rooms.py tests/test_rooms.py
git commit -m "update(builder) ボタンを木製にして裏を色付きブロックに、ゴール部屋は天井ガラス・光る床に変更"
```

---

### Task 3: 命 3 つと TNT 爆発（game）

**Files:**
- Modify: `builder/game.py`, `builder/pack.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: `Config.lives / tnt_fuse_ticks`（Task 1）、`BLOCK_BUTTON_ON`（Task 2）
- Produces: 関数キー追加 `"wrong/drop"`, `"boom"`, `"boom/kill"`, `"gameover"`。
  ```
  load     : 既存 + `scoreboard objectives add mq_deaths deathCount`
  setup    : 先頭に `gamerule keepInventory true`
  start    : `#active 0` の後に `_cancel_timers()`（下記）、`scoreboard players set #miss mq 0`、`scoreboard players reset @a mq_deaths`
  quit     : `#active 0` の後に `_cancel_timers()`
  tick     : 既存行 + `execute if score #active mq matches 2 as @e[type=minecraft:player,scores={mq_deaths=1..}] run function mathquiz:gameover`
  wrong    : `scoreboard players add #miss mq 1`
             `scoreboard players set #left mq <lives>` → `scoreboard players operation #left mq -= #miss mq`
             `execute if score #left mq matches ..0 run function mathquiz:boom`
             `execute if score #left mq matches 1.. run function mathquiz:wrong/drop`   （boom は #left を変えない）
  wrong/drop: 旧 wrong の本体。title の前に `title @a subtitle [{text:"あと "},{score:{name:"#left",objective:"mq"}},{text:" かい"}]`
  boom     : `scoreboard players set #active mq 2`
             `title @a title {text:"ばくはつ！",color:"red"}` → `sound("minecraft:entity.tnt.primed")`
             `execute at @e[type=minecraft:marker,tag=mq_return,limit=1] run spawnpoint @a ~ ~ ~`
             `scoreboard players set @a mq_deaths 0`
             `execute at @a run summon minecraft:tnt ~ ~ ~ {fuse:<tnt_fuse_ticks>,explosion_power:0f,Tags:["mq","mq_tnt"]}`
             `schedule function mathquiz:boom/kill <tnt_fuse_ticks>t`
  boom/kill: `execute at @a run particle minecraft:explosion_emitter ~ ~1 ~` → `sound("minecraft:entity.generic.explode")`
             `damage @a 1000 minecraft:explosion`
  gameover : （as プレイヤーで実行）`scoreboard players set #active mq 0` → `scoreboard players reset @s mq_deaths`
             `gamemode creative @s` → `tp @s @e[type=minecraft:marker,tag=mq_return,limit=1]`
             `tellraw @s {text:"もういちど あそぶなら /function mathquiz:start"}`
  _cancel_timers(): ["schedule clear mathquiz:restore", "schedule clear mathquiz:boom/kill", "kill @e[type=minecraft:tnt,tag=mq]"]
  check    : `if block ... BLOCK_BUTTON_ON run ...`
  ```
  `pack.py` の説明: `wrong/drop` 「不正解（まだ命がある）。床を抜いて 3 秒後に restore」、`boom` 「3 回目の不正解。足元に TNT を出す」、`boom/kill` 「TNT の爆発。煙と音を出して子どもを倒す」、`gameover` 「リスポーン後にクリエイティブへ戻して遊びを終える」。`wrong` の説明は「不正解。命が残っていれば床抜き、無ければ爆発」に変える。

- [ ] **Step 1: テストを書く（既存の期待値も更新）**

`tests/test_game.py`: `test_expected_functions` のキー一覧に `"wrong/drop", "boom", "boom/kill", "gameover"` を足し、`test_check_is_gated_by_lock_and_room` の `stone_button` を `oak_button` に変え、`test_wrong_schedules_restore` の対象を `self.fns["wrong/drop"]` に変える。追加:

```python
    def test_wrong_counts_misses_and_branches_on_lives_left(self):
        lines = self.fns["wrong"].splitlines()
        self.assertEqual(lines[0], "scoreboard players add #miss mq 1")
        self.assertIn("scoreboard players set #left mq 3", lines)
        self.assertIn("scoreboard players operation #left mq -= #miss mq", lines)
        self.assertIn("execute if score #left mq matches ..0 run function mathquiz:boom", lines)
        self.assertIn("execute if score #left mq matches 1.. run function mathquiz:wrong/drop", lines)
        self.assertNotIn("#left", self.fns["boom"])  # 分岐のあとに条件の値を変えない

    def test_wrong_drop_shows_lives_left(self):
        body = self.fns["wrong/drop"]
        self.assertIn('title @a subtitle [{text:"あと "},{score:{name:"#left",objective:"mq"}},{text:" かい"}]', body)
        self.assertLess(body.index("title @a subtitle"), body.index("title @a title"))

    def test_boom_is_harmless_to_the_room_and_sets_respawn_first(self):
        body = self.fns["boom"]
        self.assertEqual(body.splitlines()[0], "scoreboard players set #active mq 2")
        self.assertIn("run spawnpoint @a ~ ~ ~", body)
        self.assertIn("summon minecraft:tnt ~ ~ ~ {fuse:40,explosion_power:0f,Tags:[\"mq\",\"mq_tnt\"]}", body)
        self.assertLess(body.index("spawnpoint"), body.index("summon minecraft:tnt"))
        self.assertIn("schedule function mathquiz:boom/kill 40t", body)
        self.assertIn("damage @a 1000 minecraft:explosion", self.fns["boom/kill"])
        self.assertIn("minecraft:explosion_emitter", self.fns["boom/kill"])

    def test_gameover_only_after_boom(self):
        self.assertIn(
            "execute if score #active mq matches 2 as @e[type=minecraft:player,scores={mq_deaths=1..}] run function mathquiz:gameover",
            self.fns["tick"],
        )
        body = self.fns["gameover"]
        self.assertIn("gamemode creative @s", body)
        self.assertIn("tp @s @e[type=minecraft:marker,tag=mq_return,limit=1]", body)
        self.assertIn("scoreboard players set #active mq 0", body)

    def test_start_and_quit_cancel_tnt(self):
        for name in ("start", "quit"):
            body = self.fns[name]
            self.assertIn("schedule clear mathquiz:boom/kill", body, name)
            self.assertIn("kill @e[type=minecraft:tnt,tag=mq]", body, name)
        self.assertIn("scoreboard players set #miss mq 0", self.fns["start"])
        self.assertIn("scoreboard players reset @a mq_deaths", self.fns["start"])
        self.assertIn("scoreboard objectives add mq_deaths deathCount", self.fns["load"])
        self.assertEqual(self.fns["setup"].splitlines()[0], "gamerule keepInventory true")
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_game -v`
Expected: FAIL（新しい関数キーが無い、`wrong` の 1 行目が違う 等）

- [ ] **Step 3: `builder/game.py` を Interfaces どおりに変え、`builder/pack.py` に説明を足す**

`wrong/drop` は旧 `_wrong` の本体をそのまま移し、subtitle 行を先頭に足す。`_tellraw` 等の既存ヘルパを使う。

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest -v && python3 build.py`
Expected: 全テスト PASS、`dist/mathquiz: 49 functions`

- [ ] **Step 5: Commit**

```bash
git add builder/game.py builder/pack.py tests/test_game.py
git commit -m "add(builder) 命 3 つと、3 回目の不正解で TNT が爆発して setup の場所に戻る流れを追加"
```

---

### Task 4: ゴール部屋に入った瞬間の花火（game）

**Files:**
- Modify: `builder/game.py`, `builder/pack.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: `GoalRoom.fireworks`（Task 1、屋根の上）、`Config.firework_volleys / firework_interval_ticks`、`_cancel_timers()`（Task 3）
- Produces: 関数キー追加 `"goal/enter"`, `"goal/fireworks"`。
  ```
  goal          : `#active` は触らない。表示だけ: `mq_q` を「ゴール！」にして banner_pos へ、`mq_c1..3` を空に
  tick          : 既存行 + `execute if score #active mq matches 1 if score #room mq matches <room_count+1> if entity @a[<goal.interior.selector()>] run function mathquiz:goal/enter`
  goal/enter    : `scoreboard players set #active mq 0`（先頭。1 回だけ処理するため）
                  `title @a subtitle {text:"ぜんぶ せいかい！"}` → `title @a title {text:"ゴール！",color:"gold"}` → `sound("minecraft:entity.player.levelup", 1.2)`
                  `scoreboard players set #fw mq <firework_volleys>` → `function mathquiz:goal/fireworks`
  goal/fireworks: 花火 3 発（旧 goal の summon 行。位置は屋根の上）→ `scoreboard players remove #fw mq 1`
                  `execute if score #fw mq matches 1.. run schedule function mathquiz:goal/fireworks <firework_interval_ticks>t`
  _cancel_timers(): "schedule clear mathquiz:goal/fireworks" を追加
  ```
  `pack.py` の説明: `goal` 「ゴール部屋が有効になった。表示をゴール用に切り替える」、`goal/enter` 「ゴール部屋に入った。演出を始める（1 回だけ）」、`goal/fireworks` 「花火を 1 回ぶん上げ、残りがあれば次を予約する」。

- [ ] **Step 1: テストを書く（既存の期待値も更新）**

`test_goal_dispatch_and_quit` の `self.fns["goal"].count("summon minecraft:firework_rocket") == 3` と `"minecraft:fireworks"` の行を `self.fns["goal/fireworks"]` に向ける。`test_expected_functions` に `"goal/enter", "goal/fireworks"` を足す。追加:

```python
    def test_goal_waits_for_the_child_to_enter(self):
        self.assertNotIn("firework", self.fns["goal"])
        self.assertNotIn("#active", self.fns["goal"])
        self.assertIn(
            "execute if score #active mq matches 1 if score #room mq matches 6 if entity @a[x=41,y=120,z=1,dx=6,dy=4,dz=8] run function mathquiz:goal/enter",
            self.fns["tick"],
        )
        enter = self.fns["goal/enter"].splitlines()
        self.assertEqual(enter[0], "scoreboard players set #active mq 0")
        self.assertIn("scoreboard players set #fw mq 3", enter)
        self.assertEqual(enter[-1], "function mathquiz:goal/fireworks")

    def test_fireworks_launch_above_roof_in_volleys(self):
        body = self.fns["goal/fireworks"]
        self.assertEqual(body.count("summon minecraft:firework_rocket"), 3)
        self.assertIn("summon minecraft:firework_rocket 42.5 126.0 5.5 ", body)
        self.assertIn("scoreboard players remove #fw mq 1", body)
        self.assertIn("execute if score #fw mq matches 1.. run schedule function mathquiz:goal/fireworks 15t", body)
        for name in ("start", "quit"):
            self.assertIn("schedule clear mathquiz:goal/fireworks", self.fns[name], name)
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m unittest tests.test_game -v`
Expected: FAIL（`goal/enter` が無い、`goal` に firework が含まれる）

- [ ] **Step 3: `builder/game.py` を Interfaces どおりに変え、`builder/pack.py` に説明を足す**

- [ ] **Step 4: 成功を確認する**

Run: `python3 -m unittest -v && python3 build.py`
Expected: 全テスト PASS、`dist/mathquiz: 51 functions`

- [ ] **Step 5: Commit**

```bash
git add builder/game.py builder/pack.py tests/test_game.py
git commit -m "update(builder) 花火をゴール部屋に入った瞬間に屋根の上から上げるように変更"
```

---

### Task 5: README と配置、ゲーム内確認の引き渡し

**Files:**
- Modify: `README.md`, `tasks/todo.md`（git 管理外）

- [ ] **Step 1: README を更新する**

「使い方」に「不正解はダンジョン全体で 3 回まで。3 回目は爆発して `setup` を打った場所に戻る（遊び直すなら `start`）」と「`setup` が `keepInventory` を有効にする」を足す。「動作確認の手順」に次を足す:
- 不正解を 3 回：「ばくはつ！」→ 足元の TNT が点滅 → 2 秒後に爆発音と煙で死ぬ。部屋が壊れていないこと。リスポーンで `setup` を打った場所に立ち、クリエイティブに戻り、案内が出ること。
- 5 部屋クリアで扉が開く。ゴール部屋に入った瞬間に「ゴール！」と音、頭上のガラス越しに花火が 3 回上がり、ダメージが無いこと。
- ボタンが赤・黄・青の的の上に木のボタンとして見えること。

- [ ] **Step 2: 配置して確認する**

Run: `./install.sh && ls "$HOME/Library/Application Support/minecraft/saves/さんすう/datapacks/mathquiz/data/mathquiz/function/boom"`
Expected: `kill.mcfunction`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme) 命 3 つと爆発、ゴール入室時の花火の遊び方と確認手順を追加"
```

- [ ] **Step 4: `tasks/todo.md` に確認待ち項目を足し、ゲーム内確認を依頼する**

ゲーム内でしか検証できない点: `explosion_power:0f` の TNT が壁を壊さず音と煙だけ出すか、`damage` で死んで `spawnpoint` の場所にリスポーンするか、`@e[type=player,scores={mq_deaths=1..}]` がリスポーン後だけ拾うか、ガラス天井越しに花火が見えるか。

---

## 自己レビュー記録

- 仕様カバレッジ: 命 3 つ・残り回数表示・3 回目の TNT・部屋が壊れない・リスポーン地点・自動クリエイティブ・keepInventory → Task 3。木のボタン・色付きの的 → Task 2。ゴール入室で花火・ガラス天井・光る床・屋根上で爆発・回数設定 → Task 1・2・4。quit の戻り先 → 既存。
- 型の整合: `Room.button_backs` / `GoalRoom.floor` は Task 1 が作り Task 2 が使う。`BLOCK_BUTTON_ON` は Task 2 が作り Task 3 の `check` が使う。`_cancel_timers()` は Task 3 が作り Task 4 が 1 行足す。関数数は 45 → 49（Task 3）→ 51（Task 4）。
- Review Focus の 5 行はそれぞれ Task 3（3 行）・Task 4・Task 1 のテストに置いた。
