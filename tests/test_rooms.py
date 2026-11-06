import unittest

from builder.config import Config
from builder.layout import building, clear_area, rooms
from builder.rooms import build_commands, reset_commands, room_functions


class RoomsTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.fns = room_functions(self.cfg)
        self.r1 = rooms(self.cfg)[0]

    def test_all_room_functions_exist(self):
        for n in range(1, 6):
            for k in ("activate", "open", "drop", "restore"):
                self.assertIn(f"room/{n}/{k}", self.fns)

    def test_restore_moves_player_before_filling(self):
        lines = self.fns["room/1/restore"].splitlines()
        tp = [i for i, l in enumerate(lines) if l.startswith("tp @a[")]
        fill = [i for i, l in enumerate(lines) if l.startswith("fill ")]
        self.assertEqual(len(tp), 2)
        self.assertEqual(len(fill), 2)
        self.assertLess(max(tp), min(fill))
        self.assertIn("tp @a[x=2,y=118,z=5,dx=5,dy=2,dz=4] 4.5 114 7.5", lines[0])

    def test_restore_unpowers_buttons_before_lock_release(self):
        # 連打で powered のまま #lock が解除されると新しい問題が勝手に押されるので、復帰時に消灯する
        body = self.fns["room/1/restore"]
        unpowered = "minecraft:oak_button[face=wall,facing=north,powered=false]"
        self.assertEqual(body.count(unpowered), 3)
        self.assertIn(f"setblock 2 121 9 {unpowered}", body)

    def test_reset_unpowers_all_buttons(self):
        joined = "\n".join(reset_commands(self.cfg))
        self.assertEqual(joined.count("powered=false"), 15)

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

    def test_reset_restores_doors_and_floors(self):
        joined = "\n".join(reset_commands(self.cfg))
        self.assertEqual(joined.count("minecraft:iron_bars"), 5)
        self.assertEqual(joined.count("119"), 10 * 2)  # 床 2 箱 × 5 部屋、各 fill に y が 2 回

    def test_no_relative_coords(self):
        for body in list(self.fns.values()) + ["\n".join(build_commands(self.cfg))]:
            self.assertNotRegex(body, r"(^|\s)~")
