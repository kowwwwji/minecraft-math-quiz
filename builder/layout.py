"""部屋・ゴール部屋・建物外形の座標計算。

Config から全ブロック座標を決め、以降のモジュールはこの結果だけを使う。
"""

from dataclasses import dataclass

from builder.config import Config

Pos = tuple[int, int, int]
FPos = tuple[float, float, float]


@dataclass(frozen=True)
class Box:
    """両端を含む直方体。コンストラクタで x1<=x2 等に正規化する。"""

    x1: int
    y1: int
    z1: int
    x2: int
    y2: int
    z2: int

    def __post_init__(self):
        for a, b in (("x1", "x2"), ("y1", "y2"), ("z1", "z2")):
            lo, hi = getattr(self, a), getattr(self, b)
            if lo > hi:
                object.__setattr__(self, a, hi)
                object.__setattr__(self, b, lo)

    @property
    def volume(self) -> int:
        return (self.x2 - self.x1 + 1) * (self.y2 - self.y1 + 1) * (self.z2 - self.z1 + 1)

    def coords(self) -> str:
        return f"{self.x1} {self.y1} {self.z1} {self.x2} {self.y2} {self.z2}"

    def selector(self) -> str:
        return (
            f"x={self.x1},y={self.y1},z={self.z1},"
            f"dx={self.x2 - self.x1},dy={self.y2 - self.y1},dz={self.z2 - self.z1}"
        )

    def contains(self, x: int, y: int, z: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2 and self.z1 <= z <= self.z2


@dataclass(frozen=True)
class Room:
    number: int  # 1 始まり
    interior: Box  # 空気にする内側
    ceiling: Box  # interior の 1 段上（シーランタン）
    door: Box  # +X 側の壁の鉄格子 2×2
    pit_floor: tuple[Box, Box]  # 落とし穴になる床（はしご列を除くため 2 箱）
    pit_shaft: Box  # 床下の縦穴（水の層を含む）
    water: Box
    ladder: Box  # はしご列（常に開いた縦穴。穴の底から部屋へ戻る経路）
    pit_bottom: FPos  # 床復帰前の退避 tp 先（水の中央）
    buttons: tuple[Pos, Pos, Pos]
    question_pos: FPos
    choice_pos: tuple[FPos, FPos, FPos]
    entry: FPos  # 入口の立ち位置（tp 先）


@dataclass(frozen=True)
class GoalRoom:
    number: int  # room_count + 1
    interior: Box
    ceiling: Box
    chest: Pos
    fireworks: tuple[FPos, FPos, FPos]
    banner_pos: FPos  # 「ゴール！」表示の位置


def _pitch(cfg: Config) -> int:
    # 隣の部屋と壁を 1 枚共有する
    return cfg.room_dx + 1


def _interior(cfg: Config, number: int) -> Box:
    x1 = cfg.origin_x + _pitch(cfg) * (number - 1) + 1
    return Box(
        x1, cfg.floor_y + 1, cfg.origin_z + 1,
        x1 + cfg.room_dx - 1, cfg.floor_y + cfg.room_h, cfg.origin_z + cfg.room_dz,
    )


def _ceiling(interior: Box) -> Box:
    return Box(interior.x1, interior.y2 + 1, interior.z1, interior.x2, interior.y2 + 1, interior.z2)


def _display_pos(interior: Box, x: int, y: float) -> FPos:
    # ボタン壁（+Z）の面から少し手前に浮かせる
    return (x + 0.5, float(y), interior.z2 + 0.4)


def _room(cfg: Config, number: int) -> Room:
    fy = cfg.floor_y
    i = _interior(cfg, number)
    zp1 = i.z2 - cfg.pit_rows + 1
    cx = i.x1 + cfg.room_dx // 2
    buttons = ((cx - 2, fy + 2, i.z2), (cx, fy + 2, i.z2), (cx + 2, fy + 2, i.z2))
    shaft = Box(i.x1, fy - cfg.pit_depth, zp1, i.x2, fy - 1, i.z2)
    return Room(
        number=number,
        interior=i,
        ceiling=_ceiling(i),
        door=Box(i.x2 + 1, fy + 1, cfg.origin_z + 1, i.x2 + 1, fy + 2, cfg.origin_z + 2),
        pit_floor=(
            Box(i.x1 + 1, fy, zp1, i.x2, fy, i.z2),
            Box(i.x1, fy, zp1, i.x1, fy, i.z2 - 1),
        ),
        pit_shaft=shaft,
        water=Box(shaft.x1, shaft.y1, shaft.z1, shaft.x2, shaft.y1 + cfg.water_depth - 1, shaft.z2),
        ladder=Box(i.x1, fy - cfg.pit_depth, i.z2, i.x1, fy + 1, i.z2),
        pit_bottom=((shaft.x1 + shaft.x2) // 2 + 0.5, fy - cfg.pit_depth + 1, (shaft.z1 + shaft.z2) // 2 + 0.5),
        buttons=buttons,
        question_pos=_display_pos(i, cx, fy + 4.0),
        choice_pos=tuple(_display_pos(i, bx, fy + 3.0) for bx, _, _ in buttons),
        entry=(i.x1 + 0.5, fy + 1, cfg.origin_z + 1.5),
    )


def rooms(cfg: Config) -> list[Room]:
    return [_room(cfg, n) for n in range(1, cfg.room_count + 1)]


def goal_room(cfg: Config) -> GoalRoom:
    fy = cfg.floor_y
    number = cfg.room_count + 1
    i = _interior(cfg, number)
    cx = i.x1 + cfg.room_dx // 2
    cz = (i.z1 + i.z2) // 2
    return GoalRoom(
        number=number,
        interior=i,
        ceiling=_ceiling(i),
        chest=(cx, fy + 1, cz),
        fireworks=tuple((x + 0.5, float(fy + 2), cz + 0.5) for x in (cx - 2, cx, cx + 2)),
        banner_pos=_display_pos(i, cx, fy + 4.0),
    )


def building(cfg: Config) -> Box:
    """壁・天井・縦穴を含む石レンガの外形。"""
    return Box(
        cfg.origin_x, cfg.floor_y - cfg.pit_depth - 1, cfg.origin_z,
        cfg.origin_x + _pitch(cfg) * (cfg.room_count + 1), cfg.floor_y + cfg.room_h + 1, cfg.origin_z + cfg.room_dz + 1,
    )


def clear_area(cfg: Config) -> Box:
    """building を各方向 1 広げた範囲。地形と重なっても建てられるよう先に空気で埋める。"""
    b = building(cfg)
    return Box(b.x1 - 1, b.y1 - 1, b.z1 - 1, b.x2 + 1, b.y2 + 1, b.z2 + 1)
