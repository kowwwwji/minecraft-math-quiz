"""ダンジョンの設定。

座標・部屋サイズ・難易度表をここに集め、mcfunction 側には絶対座標だけを書く
（schedule で実行される関数は実行者が無く相対座標が使えないため）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    origin_x: int = 0
    origin_z: int = 0
    floor_y: int = 119  # 床ブロックの y。プレイヤーは floor_y+1 に立つ
    room_count: int = 5  # 問題部屋の数（ゴール部屋を除く）
    room_dx: int = 7  # 内寸: 進行方向 X
    room_dz: int = 9  # 内寸: 幅 Z
    room_h: int = 5  # 内寸: 高さ
    pit_rows: int = 5  # ボタン壁から何列が落とし穴か（ボタンが届く範囲を全部覆う）
    pit_depth: int = 6  # 床下の縦穴の深さ
    water_depth: int = 2  # 底の水。落下ダメージを消すため
    restore_ticks: int = 60  # 不正解から床復帰までの時間（3 秒）
    question_scale: float = 4.0  # text_display の拡大率（遠くからでも読めるように）
    choice_scale: float = 3.0


# レベル名 → (答えの上限 #max, 引き算あり #sub)
LEVELS: dict[str, tuple[int, int]] = {
    "easy": (5, 0),
    "normal": (10, 1),
    "hard": (20, 1),
}
