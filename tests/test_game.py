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
        self.assertIn("scale:[4f,4f,4f]", body)
        self.assertIn("scale:[3f,3f,3f]", body)
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
        # コロンを含むキーは引用しないと SNBT として不正
        self.assertIn('components:{"minecraft:fireworks":{flight_duration:1b', self.fns["goal"])
        self.assertIn("tp @a @e[type=minecraft:marker,tag=mq_return,limit=1]", self.fns["quit"])

    def test_relative_coords_only_with_at(self):
        for name, body in self.fns.items():
            for l in body.splitlines():
                if "~" in l:
                    self.assertIn(" at @", l, msg=f"{name}: {l}")
