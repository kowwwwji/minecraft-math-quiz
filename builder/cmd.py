"""SNBT エンコードとコマンド文字列の小さなヘルパ。

座標は Python 側で確定した絶対座標だけを受け取る。
"""

from builder.layout import Box, FPos, Pos

OBJECTIVE = "mq"


class Raw(str):
    """SNBT にそのまま埋める断片（例 Raw("0b"), Raw("[I;16711680]")）。"""


def snbt(value) -> str:
    if isinstance(value, Raw):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}f"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{snbt(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(snbt(v) for v in value) + "]"
    raise TypeError(f"SNBT にできない値: {value!r}")


def pos_str(pos: Pos | FPos) -> str:
    return " ".join(str(v) for v in pos)


def fill(box: Box, block: str, mode: str = "") -> str:
    return f"fill {box.coords()} {block}" + (f" {mode}" if mode else "")


def setblock(pos: Pos, block: str) -> str:
    return f"setblock {pos_str(pos)} {block}"


def display_selector(tag: str) -> str:
    return f"@e[type=minecraft:text_display,tag={tag},limit=1]"


def tp_display(tag: str, pos: FPos) -> str:
    return f"tp {display_selector(tag)} {pos_str(pos)}"


def set_display_text(tag: str, component) -> str:
    return f"data modify entity {display_selector(tag)} text set value {snbt(component)}"


def score_text(name: str) -> dict:
    return {"score": {"name": name, "objective": OBJECTIVE}}


def title(kind: str, component) -> str:
    return f"title @a {kind} {snbt(component)}"


def sound(sound_id: str, pitch: float = 1.0) -> str:
    # 各プレイヤーの位置で鳴らす（schedule 実行時は実行者が無いため @s は使えない）
    return f"execute as @a at @s run playsound {sound_id} master @s ~ ~ ~ 1 {pitch:g}"
