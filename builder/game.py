"""ゲーム進行の関数生成（load / setup / start / quit / tick / 正解 / 不正解 / ゴール / レベル）。

押下の多重処理を防ぐため、`check` の各行と `tick` を `#lock` で門番し、
`press/*` の先頭で立てて次の問題が出る `question` の最後で下ろす。
"""

from builder.cmd import Raw, pos_str, score_text, set_display_text, snbt, sound, title, tp_display
from builder.config import LEVELS, Config
from builder.layout import FPos, building, goal_room, rooms
from builder.questions import DISPLAY_TAGS
from builder.rooms import BLOCK_BUTTON_ON, build_commands, reset_commands

MARKER = "@e[type=minecraft:marker,tag=mq_return]"
TNT = "@e[type=minecraft:tnt,tag=mq]"
FIREWORK_COLORS = (16711680, 65280, 255)  # 赤・緑・青


def _tellraw(text: str) -> str:
    return f"tellraw @a {snbt({'text': text})}"


def _remember_return_point() -> str:
    """quit の戻り先を marker で記録する。既にあれば（やり直し）最初の位置を保つ。"""
    return f"execute unless entity {MARKER} at @a run summon minecraft:marker ~ ~ ~ {snbt({'Tags': ['mq', 'mq_return']})}"


def _tp_entry(cfg: Config) -> str:
    # 入口で +X（進行方向）を向かせる
    return f"tp @a {pos_str(rooms(cfg)[0].entry)} -90 0"


def _dispatch(cfg: Config, suffix: str) -> list[str]:
    """現在の部屋 #room に対応する room/N/<suffix> を呼ぶ行を並べる。"""
    return [
        f"execute if score #room mq matches {r.number} run function mathquiz:room/{r.number}/{suffix}"
        for r in rooms(cfg)
    ]


def _summon_display(tag: str, pos: FPos, scale: float) -> str:
    nbt = {
        "Tags": ["mq", tag],
        "billboard": "vertical",  # 子どもがどこに立っても正面を向く
        "alignment": "center",
        "background": -16777216,  # 不透明の黒。文字を読みやすくする
        "brightness": {"sky": 15, "block": 15},
        "text": {"text": ""},
        "transformation": {
            "left_rotation": [0.0, 0.0, 0.0, 1.0],
            "right_rotation": [0.0, 0.0, 0.0, 1.0],
            "translation": [0.0, 0.0, 0.0],
            "scale": [scale, scale, scale],
        },
    }
    return f"summon minecraft:text_display {pos_str(pos)} {snbt(nbt)}"


def _firework(pos: FPos, color: int) -> str:
    nbt = {
        "LifeTime": 20,
        "FireworksItem": {
            "id": "minecraft:firework_rocket",
            "count": 1,
            "components": {
                "minecraft:fireworks": {
                    "flight_duration": Raw("1b"),
                    "explosions": [
                        {"shape": "large_ball", "colors": Raw(f"[I;{color}]"), "has_twinkle": True}
                    ],
                }
            },
        },
    }
    return f"summon minecraft:firework_rocket {pos_str(pos)} {snbt(nbt)}"


def _load() -> list[str]:
    return [
        "scoreboard objectives add mq dummy",
        "scoreboard objectives add mq_deaths deathCount",  # 爆発後のリスポーン検出用
        # 未設定（自分自身との比較が失敗する）のときだけ既定レベルにする
        "execute unless score #max mq = #max mq run function mathquiz:level/normal",
        "scoreboard players set #active mq 0",
        "scoreboard players set #lock mq 0",
    ]


def _setup(cfg: Config) -> list[str]:
    # 空中へ tp する前にクリエイティブにして落下ダメージを防ぎ、チャンク読み込みを待ってから建てる
    return [
        # 3 回目の不正解で死んでも宝箱の中身が散らばらないように
        "gamerule keepInventory true",
        "gamemode creative @a",
        # 空中へ tp する前に、親が立っていた場所を quit の戻り先として記録する
        _remember_return_point(),
        _tp_entry(cfg),
        _tellraw("ダンジョンを たてています…"),
        "schedule function mathquiz:setup/build 20t",
    ]


def _setup_build(cfg: Config) -> list[str]:
    return [
        *build_commands(cfg),
        _tp_entry(cfg),
        _tellraw("できました。/function mathquiz:start で はじめます"),
    ]


def _start(cfg: Config) -> list[str]:
    r1 = rooms(cfg)[0]
    displays = [_summon_display(DISPLAY_TAGS[0], r1.question_pos, cfg.question_scale)]
    displays += [
        _summon_display(tag, pos, cfg.choice_scale) for tag, pos in zip(DISPLAY_TAGS[1:], r1.choice_pos)
    ]
    corner = pos_str((building(cfg).x1, building(cfg).y1, building(cfg).z1))
    return [
        # 建物が無いまま空中へ tp すると落ちるので、setup 前なら何もしない
        f"execute unless block {corner} minecraft:stone_bricks run {_tellraw('さきに /function mathquiz:setup を じっこうしてください')}",
        f"execute unless block {corner} minecraft:stone_bricks run return fail",
        "scoreboard players set #active mq 0",
        *_cancel_timers(),
        "scoreboard players set #miss mq 0",
        "scoreboard players reset @a mq_deaths",
        # setup を経ずに marker が無い場合の保険
        _remember_return_point(),
        *reset_commands(cfg),
        "kill @e[type=minecraft:text_display,tag=mq]",
        *displays,
        "gamemode adventure @a",
        _tp_entry(cfg),
        "scoreboard players set #room mq 1",
        "scoreboard players set #active mq 1",
        "function mathquiz:activate",
    ]


def _quit() -> list[str]:
    return [
        "scoreboard players set #active mq 0",
        *_cancel_timers(),
        "gamemode creative @a",
        f"tp @a {MARKER[:-1]},limit=1]",
        f"kill {MARKER}",
    ]


def _check(cfg: Config) -> list[str]:
    lines = []
    for r in rooms(cfg):
        for k, b in enumerate(r.buttons, start=1):
            lines.append(
                f"execute if score #lock mq matches 0 if score #room mq matches {r.number} "
                f"if block {pos_str(b)} {BLOCK_BUTTON_ON} run function mathquiz:press/{k}"
            )
    return lines


def _press(k: int) -> list[str]:
    # correct は次の問題を作って #ans / #c1..3 を書き換えるので、if/unless を直接並べると
    # 正解のあと unless 側も新しい問題で評価されて wrong が走る。比較結果を #hit に固定してから分岐する
    return [
        "scoreboard players set #lock mq 1",
        "scoreboard players set #hit mq 0",
        f"execute if score #c{k} mq = #ans mq run scoreboard players set #hit mq 1",
        "execute if score #hit mq matches 1 run function mathquiz:correct",
        "execute if score #hit mq matches 0 run function mathquiz:wrong",
    ]


def _correct(cfg: Config) -> list[str]:
    return [
        title("title", {"text": "せいかい！", "color": "green"}),
        sound("minecraft:entity.player.levelup"),
        *_dispatch(cfg, "open"),
        "scoreboard players add #room mq 1",
        "function mathquiz:activate",
    ]


def _wrong(cfg: Config) -> list[str]:
    # 残り回数 #left を先に確定してから分岐する（boom / wrong/drop は #left を変えない）
    return [
        "scoreboard players add #miss mq 1",
        f"scoreboard players set #left mq {cfg.lives}",
        "scoreboard players operation #left mq -= #miss mq",
        "execute if score #left mq matches ..0 run function mathquiz:boom",
        "execute if score #left mq matches 1.. run function mathquiz:wrong/drop",
    ]


def _wrong_drop(cfg: Config) -> list[str]:
    return [
        title("subtitle", [{"text": "あと "}, score_text("#left"), {"text": " かい"}]),
        title("title", {"text": "ざんねん…", "color": "red"}),
        sound("minecraft:entity.villager.no", 0.8),
        *_dispatch(cfg, "drop"),
        f"schedule function mathquiz:restore {cfg.restore_ticks}t",
    ]


def _boom(cfg: Config) -> list[str]:
    # #active 2 = 爆発待ち〜リスポーン待ち。ボタンは見ず、リスポーンだけ tick で拾う
    tnt = snbt({"fuse": cfg.tnt_fuse_ticks, "explosion_power": 0.0, "Tags": ["mq", "mq_tnt"]})
    return [
        "scoreboard players set #active mq 2",
        title("title", {"text": "ばくはつ！", "color": "red"}),
        sound("minecraft:entity.tnt.primed"),
        # リスポーン先は setup を打った場所（quit の戻り先と同じ marker）
        f"execute at {MARKER[:-1]},limit=1] run spawnpoint @a ~ ~ ~",
        "scoreboard players set @a mq_deaths 0",
        # 威力 0 の TNT: 点滅と音は本物、部屋は壊れない。ダメージは boom/kill で与える
        f"execute at @a run summon minecraft:tnt ~ ~ ~ {tnt}",
        f"schedule function mathquiz:boom/kill {cfg.tnt_fuse_ticks}t",
    ]


def _boom_kill() -> list[str]:
    return [
        "execute at @a run particle minecraft:explosion_emitter ~ ~1 ~",
        sound("minecraft:entity.generic.explode"),
        "damage @a 1000 minecraft:explosion",
    ]


def _gameover() -> list[str]:
    # tick から「リスポーン後の生きているプレイヤー」として as で呼ばれる
    return [
        "scoreboard players set #active mq 0",
        "scoreboard players reset @s mq_deaths",
        "gamemode creative @s",
        f"tp @s {MARKER[:-1]},limit=1]",
        f"tellraw @s {snbt({'text': 'もういちど あそぶなら /function mathquiz:start'})}",
    ]


def _cancel_timers() -> list[str]:
    """前回の遊びで予約した処理が、新しい状態を壊さないように取り消す。"""
    return [
        "schedule clear mathquiz:restore",
        "schedule clear mathquiz:boom/kill",
        "schedule clear mathquiz:goal/fireworks",
        f"kill {TNT}",
    ]


def _restore(cfg: Config) -> list[str]:
    return [*_dispatch(cfg, "restore"), "function mathquiz:activate"]


def _activate(cfg: Config) -> list[str]:
    return [
        f"execute if score #room mq matches {cfg.room_count + 1} run function mathquiz:goal",
        f"execute if score #room mq matches 1..{cfg.room_count} run function mathquiz:question",
    ]


def _question(cfg: Config) -> list[str]:
    return [
        "function mathquiz:gen",
        "function mathquiz:show",
        *_dispatch(cfg, "activate"),
        "scoreboard players set #lock mq 0",
    ]


def _goal(cfg: Config) -> list[str]:
    # 部屋 5 の正解で呼ばれる。表示を切り替えるだけで、演出は子どもが入ってから（goal/enter）
    g = goal_room(cfg)
    return [
        set_display_text(DISPLAY_TAGS[0], {"text": "ゴール！", "color": "gold", "bold": True}),
        tp_display(DISPLAY_TAGS[0], g.banner_pos),
        *(set_display_text(tag, {"text": ""}) for tag in DISPLAY_TAGS[1:]),
    ]


def _goal_enter(cfg: Config) -> list[str]:
    return [
        "scoreboard players set #active mq 0",  # 先頭で止めて、tick が毎回呼ばないようにする
        # subtitle は title の表示時に出るので先に設定する
        title("subtitle", {"text": "ぜんぶ せいかい！"}),
        title("title", {"text": "ゴール！", "color": "gold"}),
        sound("minecraft:entity.player.levelup", 1.2),
        f"scoreboard players set #fw mq {cfg.firework_volleys}",
        "function mathquiz:goal/fireworks",
    ]


def _goal_fireworks(cfg: Config) -> list[str]:
    # 屋根の上で上げる（花火は近くの生物にダメージを与えるので、ガラス越しに見せる）
    g = goal_room(cfg)
    return [
        *(_firework(pos, color) for pos, color in zip(g.fireworks, FIREWORK_COLORS)),
        "scoreboard players remove #fw mq 1",
        f"execute if score #fw mq matches 1.. run schedule function mathquiz:goal/fireworks {cfg.firework_interval_ticks}t",
    ]


def _level(name: str, mx: int, sub: int) -> list[str]:
    return [
        f"scoreboard players set #max mq {mx}",
        f"scoreboard players set #sub mq {sub}",
        _tellraw(f"レベル: {name}（こたえは 0〜{mx}）"),
    ]


def game_functions(cfg: Config) -> dict[str, str]:
    fns = {
        "load": _load(),
        "setup": _setup(cfg),
        "setup/build": _setup_build(cfg),
        "start": _start(cfg),
        "quit": _quit(),
        "tick": [
            "execute if score #active mq matches 1 if score #lock mq matches 0 run function mathquiz:check",
            # 爆発で死んだ子がリスポーンしたら（@e は生きているプレイヤーだけ拾う）遊びを終える
            "execute if score #active mq matches 2 as @e[type=minecraft:player,scores={mq_deaths=1..}] "
            "run function mathquiz:gameover",
            # ゴール部屋に入った瞬間に演出を始める
            f"execute if score #active mq matches 1 if score #room mq matches {cfg.room_count + 1} "
            f"if entity @a[{goal_room(cfg).interior.selector()}] run function mathquiz:goal/enter",
        ],
        "check": _check(cfg),
        **{f"press/{k}": _press(k) for k in (1, 2, 3)},
        "correct": _correct(cfg),
        "wrong": _wrong(cfg),
        "wrong/drop": _wrong_drop(cfg),
        "boom": _boom(cfg),
        "boom/kill": _boom_kill(),
        "gameover": _gameover(),
        "restore": _restore(cfg),
        "activate": _activate(cfg),
        "question": _question(cfg),
        "goal": _goal(cfg),
        "goal/enter": _goal_enter(cfg),
        "goal/fireworks": _goal_fireworks(cfg),
        **{f"level/{name}": _level(name, mx, sub) for name, (mx, sub) in LEVELS.items()},
    }
    return {name: "\n".join(lines) + "\n" for name, lines in fns.items()}
