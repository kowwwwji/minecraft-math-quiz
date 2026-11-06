"""部屋ごとの関数（activate / open / drop / restore）と建築コマンドの生成。"""

from builder.cmd import Raw, fill, pos_str, setblock, snbt, tp_display
from builder.config import Config
from builder.layout import Box, GoalRoom, Room, building, clear_area, goal_room, rooms
from builder.questions import DISPLAY_TAGS

BLOCK_WALL = "minecraft:stone_bricks"
BLOCK_LIGHT = "minecraft:sea_lantern"
BLOCK_DOOR = "minecraft:iron_bars"
BLOCK_BUTTON = "minecraft:stone_button[face=wall,facing=north]"  # +Z の壁に付き -Z を向く
BLOCK_BUTTON_OFF = "minecraft:stone_button[face=wall,facing=north,powered=false]"
BLOCK_LADDER = "minecraft:ladder[facing=east]"  # -X の壁に付き +X を向く
BLOCK_AIR = "minecraft:air"
BLOCK_WATER = "minecraft:water"

CHEST_ITEMS = [
    {"Slot": Raw("0b"), "id": "minecraft:diamond", "count": 5},
    {"Slot": Raw("1b"), "id": "minecraft:cake", "count": 1},
    {"Slot": Raw("2b"), "id": "minecraft:golden_apple", "count": 3},
]
BLOCK_CHEST = "minecraft:chest[facing=west]" + snbt({"Items": CHEST_ITEMS})


def _build_room(r: Room) -> list[str]:
    # 水をはしごより先に置く（はしご列の水をはしごで置き換えるため）
    return [
        fill(r.interior, BLOCK_AIR),
        fill(r.ceiling, BLOCK_LIGHT),
        fill(r.pit_shaft, BLOCK_AIR),
        fill(r.water, BLOCK_WATER),
        fill(r.ladder, BLOCK_LADDER),
        fill(r.door, BLOCK_DOOR),
        *(setblock(b, BLOCK_BUTTON) for b in r.buttons),
    ]


def _build_goal(g: GoalRoom) -> list[str]:
    return [
        fill(g.interior, BLOCK_AIR),
        fill(g.ceiling, BLOCK_LIGHT),
        setblock(g.chest, BLOCK_CHEST),
    ]


def build_commands(cfg: Config) -> list[str]:
    """setup/build の本体。地形と重なっても建てられるよう、先に空気で埋めてから外形を作る。"""
    cmds = [fill(clear_area(cfg), BLOCK_AIR), fill(building(cfg), BLOCK_WALL)]
    for r in rooms(cfg):
        cmds += _build_room(r)
    cmds += _build_goal(goal_room(cfg))
    return cmds


def _unpower_buttons(r: Room) -> list[str]:
    # 連打で powered のまま #lock が解除されると、次の問題が勝手に「押された」ことになるため消灯する
    return [setblock(b, BLOCK_BUTTON_OFF) for b in r.buttons]


def reset_commands(cfg: Config) -> list[str]:
    """start 用。前回の遊びで開いた扉と抜けた床を元に戻し、ボタンを消灯する。"""
    cmds = []
    for r in rooms(cfg):
        cmds.append(fill(r.door, BLOCK_DOOR))
        cmds += [fill(b, BLOCK_WALL) for b in r.pit_floor]
        cmds += _unpower_buttons(r)
    return cmds


def _restore(r: Room) -> list[str]:
    # 床の高さにいる子どもを石に埋めないよう、先に穴の底へ退避させてから塞ぐ
    lines = []
    for b in r.pit_floor:
        area = Box(b.x1, b.y1 - 1, b.z1, b.x2, b.y2 + 1, b.z2)
        lines.append(f"tp @a[{area.selector()}] {pos_str(r.pit_bottom)}")
    lines += [fill(b, BLOCK_WALL) for b in r.pit_floor]
    lines += _unpower_buttons(r)
    return lines


def _activate(r: Room) -> list[str]:
    positions = (r.question_pos, *r.choice_pos)
    return [tp_display(tag, pos) for tag, pos in zip(DISPLAY_TAGS, positions)]


def room_functions(cfg: Config) -> dict[str, str]:
    fns: dict[str, list[str]] = {}
    for r in rooms(cfg):
        fns[f"room/{r.number}/activate"] = _activate(r)
        fns[f"room/{r.number}/open"] = [fill(r.door, BLOCK_AIR)]
        fns[f"room/{r.number}/drop"] = [fill(b, BLOCK_AIR) for b in r.pit_floor]
        fns[f"room/{r.number}/restore"] = _restore(r)
    return {name: "\n".join(lines) + "\n" for name, lines in fns.items()}
