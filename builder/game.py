"""ゲーム進行の関数生成（load / setup / start / quit / tick / 正解 / 不正解 / ゴール / レベル）。

押下の多重処理を防ぐため、`check` の各行と `tick` を `#lock` で門番し、
`press/*` の先頭で立てて次の問題が出る `question` の最後で下ろす。
"""

from builder.cmd import Raw, pos_str, set_display_text, snbt, sound, title, tp_display
from builder.config import LEVELS, Config
from builder.layout import FPos, goal_room, rooms
from builder.questions import DISPLAY_TAGS
from builder.rooms import build_commands, reset_commands

MARKER = "@e[type=minecraft:marker,tag=mq_return]"
FIREWORK_COLORS = (16711680, 65280, 255)  # 赤・緑・青


def _tellraw(text: str) -> str:
    return f"tellraw @a {snbt({'text': text})}"


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
        # 未設定（自分自身との比較が失敗する）のときだけ既定レベルにする
        "execute unless score #max mq = #max mq run function mathquiz:level/normal",
        "scoreboard players set #active mq 0",
        "scoreboard players set #lock mq 0",
    ]


def _setup(cfg: Config) -> list[str]:
    # 空中へ tp する前にクリエイティブにして落下ダメージを防ぎ、チャンク読み込みを待ってから建てる
    return [
        "gamemode creative @a",
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
    return [
        "scoreboard players set #active mq 0",
        # 前回の遊びで残った床復帰が新しい部屋の状態を壊さないように
        "schedule clear mathquiz:restore",
        # quit の戻り先。既にあれば（start のやり直し）最初の位置を保つ
        f"execute unless entity {MARKER} at @a run summon minecraft:marker ~ ~ ~ {snbt({'Tags': ['mq', 'mq_return']})}",
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
        "schedule clear mathquiz:restore",
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
                f"if block {pos_str(b)} minecraft:stone_button[powered=true] run function mathquiz:press/{k}"
            )
    return lines


def _press(k: int) -> list[str]:
    return [
        "scoreboard players set #lock mq 1",
        f"execute if score #c{k} mq = #ans mq run function mathquiz:correct",
        f"execute unless score #c{k} mq = #ans mq run function mathquiz:wrong",
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
    return [
        title("title", {"text": "ざんねん…", "color": "red"}),
        sound("minecraft:entity.villager.no", 0.8),
        *_dispatch(cfg, "drop"),
        f"schedule function mathquiz:restore {cfg.restore_ticks}t",
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
    g = goal_room(cfg)
    return [
        "scoreboard players set #active mq 0",
        # subtitle は title の表示時に出るので先に設定する
        title("subtitle", {"text": "ぜんぶ せいかい！"}),
        title("title", {"text": "ゴール！", "color": "gold"}),
        sound("minecraft:entity.player.levelup", 1.2),
        *(_firework(pos, color) for pos, color in zip(g.fireworks, FIREWORK_COLORS)),
        set_display_text(DISPLAY_TAGS[0], {"text": "ゴール！", "color": "gold", "bold": True}),
        tp_display(DISPLAY_TAGS[0], g.banner_pos),
        *(set_display_text(tag, {"text": ""}) for tag in DISPLAY_TAGS[1:]),
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
        "tick": ["execute if score #active mq matches 1 if score #lock mq matches 0 run function mathquiz:check"],
        "check": _check(cfg),
        **{f"press/{k}": _press(k) for k in (1, 2, 3)},
        "correct": _correct(cfg),
        "wrong": _wrong(cfg),
        "restore": _restore(cfg),
        "activate": _activate(cfg),
        "question": _question(cfg),
        "goal": _goal(cfg),
        **{f"level/{name}": _level(name, mx, sub) for name, (mx, sub) in LEVELS.items()},
    }
    return {name: "\n".join(lines) + "\n" for name, lines in fns.items()}
