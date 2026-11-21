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
    # 問題の text_display の拡大率。最長の式（23 + 45 - 18 = ?、88 px）が 0.025 × 3 = 6.6 ブロックで
    # ボタン壁の幅 7 ブロックに収まる値（4 だとはみ出て壁に埋まる）
    question_scale: float = 3.0
    choice_scale: float = 3.0
    lives: int = 3  # 不正解できる回数（ダンジョン全体の通算）
    tnt_fuse_ticks: int = 40  # 3 回目の不正解で出る TNT の導火線（2 秒）
    firework_volleys: int = 3  # ゴール部屋に入ったときの花火の回数
    firework_interval_ticks: int = 15


@dataclass(frozen=True)
class Level:
    """難易度。問題の種類ごとに関数を分けず、この 5 つの値で同じ生成手順を振り分ける。"""

    max: int  # 答えと途中の計算の上限（#max）
    lo: int  # 式に出る数の下限（#lo）。2 桁なら 10
    terms: int  # 足し算・引き算の式の項数 2 か 3（#terms）
    sub: int  # 引き算を混ぜるか 0/1（#sub）
    mul: int  # 九九を 1/2 で混ぜるか 0/1（#mul）
    label: str  # tellraw 用の説明（ひらがな）


# 名前は「学年_段階」。値は設計書の難易度表どおり
LEVELS: dict[str, Level] = {
    "g1_easy": Level(10, 1, 3, 0, 0, "3つの かずの たしざん"),
    "g1_normal": Level(10, 1, 3, 1, 0, "3つの かずの たしざん・ひきざん"),
    "g1_hard": Level(20, 1, 3, 1, 0, "3つの かずの たしざん・ひきざん"),
    "g2_easy": Level(99, 10, 2, 1, 0, "2けたの たしざん・ひきざん"),
    "g2_normal": Level(99, 10, 2, 1, 1, "2けたの たしざん・ひきざん と くく"),
    "g2_hard": Level(99, 10, 3, 1, 1, "2けた 3つの かずの たしざん・ひきざん と くく"),
}
DEFAULT_LEVEL = "g1_normal"
