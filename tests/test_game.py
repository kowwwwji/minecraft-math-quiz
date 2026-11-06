import unittest

from builder.config import Config
from builder.game import game_functions


class GameTest(unittest.TestCase):
    def setUp(self):
        self.fns = game_functions(Config())

    def test_expected_functions(self):
        for k in (
            "load", "setup", "setup/build", "start", "quit", "tick", "check",
            "press/1", "press/2", "press/3", "correct", "wrong", "restore", "activate",
            "question", "goal", "level/easy", "level/normal", "level/hard",
            "wrong/drop", "boom", "boom/kill", "gameover", "goal/enter", "goal/fireworks",
        ):
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
            self.assertIn("minecraft:oak_button[powered=true] run function mathquiz:press/", l)
        self.assertIn("if block 2 121 9 ", lines[0])

    def test_press_sets_lock_then_branches(self):
        lines = self.fns["press/2"].splitlines()
        self.assertEqual(lines[0], "scoreboard players set #lock mq 1")
        self.assertIn("execute if score #c2 mq = #ans mq run scoreboard players set #hit mq 1", lines)
        self.assertIn("execute if score #hit mq matches 1 run function mathquiz:correct", lines)
        self.assertIn("execute if score #hit mq matches 0 run function mathquiz:wrong", lines)

    def test_start_refuses_without_building(self):
        # setup 前に start すると空中へ tp されて落ちるので、建物が無ければ何もしない
        body = self.fns["start"]
        guard = "execute unless block 0 112 0 minecraft:stone_bricks run return fail"
        self.assertIn(guard, body)
        self.assertLess(body.index(guard), body.index("gamemode adventure @a"))
        self.assertLess(body.index("execute unless block 0 112 0 minecraft:stone_bricks run tellraw @a "), body.index(guard))

    def test_start_clears_schedule_and_resets(self):
        body = self.fns["start"]
        self.assertLess(body.index("schedule clear mathquiz:restore"), body.index("gamemode adventure @a"))
        self.assertEqual(body.count("summon minecraft:text_display"), 4)
        self.assertIn("scale:[4f,4f,4f]", body)
        self.assertIn("scale:[3f,3f,3f]", body)
        self.assertIn("tp @a 1.5 120 1.5 -90 0", body)
        self.assertTrue(body.rstrip().endswith("function mathquiz:activate"))

    def test_setup_is_safe_for_the_parent(self):
        body = self.fns["setup"]
        self.assertLess(body.index("gamemode creative @a"), body.index("tp @a "))
        # quit の戻り先は「setup を打った場所」。空中へ tp する前に記録する
        marker = "execute unless entity @e[type=minecraft:marker,tag=mq_return] at @a run summon minecraft:marker ~ ~ ~"
        self.assertIn(marker, body)
        self.assertLess(body.index(marker), body.index("tp @a "))
        self.assertIn("schedule function mathquiz:setup/build 20t", body)
        self.assertTrue(self.fns["setup/build"].count("tp @a 1.5 120 1.5") == 1)

    def test_wrong_schedules_restore(self):
        self.assertIn("schedule function mathquiz:restore 60t", self.fns["wrong/drop"])
        self.assertIn("execute if score #room mq matches 3 run function mathquiz:room/3/drop", self.fns["wrong/drop"])
        self.assertIn("entity.villager.no", self.fns["wrong/drop"])

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
        self.assertIn('summon minecraft:tnt ~ ~ ~ {fuse:40,explosion_power:0f,Tags:["mq","mq_tnt"]}', body)
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

    def test_goal_dispatch_and_quit(self):
        self.assertIn("execute if score #room mq matches 6 run function mathquiz:goal", self.fns["activate"])
        self.assertIn("execute if score #room mq matches 1..5 run function mathquiz:question", self.fns["activate"])
        self.assertEqual(self.fns["goal/fireworks"].count("summon minecraft:firework_rocket"), 3)
        # コロンを含むキーは引用しないと SNBT として不正
        self.assertIn('components:{"minecraft:fireworks":{flight_duration:1b', self.fns["goal/fireworks"])
        self.assertIn("tp @a @e[type=minecraft:marker,tag=mq_return,limit=1]", self.fns["quit"])

    def test_goal_waits_for_the_child_to_enter(self):
        self.assertNotIn("firework", self.fns["goal"])
        self.assertNotIn("#active", self.fns["goal"])
        self.assertIn(
            "execute if score #active mq matches 1 if score #room mq matches 6 "
            "if entity @a[x=41,y=120,z=1,dx=6,dy=4,dz=8] run function mathquiz:goal/enter",
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

    def test_relative_coords_only_with_at(self):
        for name, body in self.fns.items():
            for l in body.splitlines():
                if "~" in l:
                    self.assertIn(" at @", l, msg=f"{name}: {l}")


class PressFlowTest(unittest.TestCase):
    """press/k の分岐を、正解処理が問題を作り直す状況でシミュレータ実行する。"""

    def run_press(self, k, hit, seed=7):
        import random

        from builder.questions import question_functions
        from tests.mcsim import Sim

        fns = dict(question_functions(Config()))
        fns[f"press/{k}"] = self.fns[f"press/{k}"]
        # correct は次の問題を生成して #ans / #c1..3 を書き換える。wrong は呼ばれた印だけ残す
        fns["correct"] = "scoreboard players set #correct_called mq 1\nfunction mathquiz:gen\n"
        fns["wrong"] = "scoreboard players set #wrong_called mq 1\n"
        sim = Sim(fns, random.Random(seed))
        sim.scores.update({"#max": 10, "#sub": 1, "#ans": 5, "#c1": 5, "#c2": 6, "#c3": 4})
        if not hit:
            sim.scores["#ans"] = 3
        sim.run(f"press/{k}")
        return sim.scores

    def setUp(self):
        self.fns = game_functions(Config())

    def test_correct_press_never_also_runs_wrong(self):
        for seed in range(30):  # gen の乱数に関わらず wrong が走らないこと
            s = self.run_press(1, hit=True, seed=seed)
            self.assertEqual(s.get("#correct_called"), 1)
            self.assertNotIn("#wrong_called", s)

    def test_wrong_press_runs_only_wrong(self):
        s = self.run_press(1, hit=False)
        self.assertEqual(s.get("#wrong_called"), 1)
        self.assertNotIn("#correct_called", s)
