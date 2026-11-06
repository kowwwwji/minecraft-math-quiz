import unittest

from builder.config import Config
from builder.layout import Box, building, clear_area, goal_room, rooms


class BoxTest(unittest.TestCase):
    def test_normalizes_and_formats(self):
        b = Box(3, 5, 9, 1, 2, 4)
        self.assertEqual(b.coords(), "1 2 4 3 5 9")
        self.assertEqual(b.selector(), "x=1,y=2,z=4,dx=2,dy=3,dz=5")
        self.assertEqual(b.volume, 3 * 4 * 6)
        self.assertTrue(b.contains(2, 3, 6))
        self.assertFalse(b.contains(4, 3, 6))


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.rooms = rooms(self.cfg)

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
        cells = {
            (x, z)
            for b in r.pit_floor
            for x in range(b.x1, b.x2 + 1)
            for z in range(b.z1, b.z2 + 1)
        }
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
