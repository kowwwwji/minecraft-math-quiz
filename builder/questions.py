"""出題ロジックの mcfunction 生成。

計算はすべてゲーム内のスコアボードで行う。乱数は常に広い固定範囲を引いてから `%=` で
縮める（`random value N..N` のように範囲幅が 1 になるとコマンドが失敗して問題が出ないため）。
`#t` は一時変数・定数置き場として使い回す。
"""

from builder.cmd import score_text, set_display_text
from builder.config import Config

DISPLAY_TAGS = ("mq_q", "mq_c1", "mq_c2", "mq_c3")

RAND = "random value 0..999999"


def _rand_mod(target: str, mod: str) -> list[str]:
    """target = 乱数 % mod。mod はスコア名。"""
    return [
        f"execute store result score {target} mq run {RAND}",
        f"scoreboard players operation {target} mq %= {mod} mq",
    ]


def _rand_below(target: str, n: int) -> list[str]:
    """target = 乱数 % n（0..n-1）。n は定数。"""
    return [f"scoreboard players set #t mq {n}", *_rand_mod(target, "#t")]


def _gen() -> list[str]:
    return [
        *_rand_below("#r", 2),
        "execute if score #sub mq matches 0 run scoreboard players set #r mq 0",
        "execute if score #r mq matches 0 run function mathquiz:gen/add",
        "execute if score #r mq matches 1 run function mathquiz:gen/sub",
        "function mathquiz:gen/wrong",
        "function mathquiz:gen/shuffle",
    ]


def _gen_add() -> list[str]:
    # ans は 1..max（a = b = 0 を避ける）、a は 0..ans、b = ans - a
    return [
        *_rand_mod("#ans", "#max"),
        "scoreboard players add #ans mq 1",
        "scoreboard players operation #t mq = #ans mq",
        "scoreboard players add #t mq 1",
        *_rand_mod("#a", "#t"),
        "scoreboard players operation #b mq = #ans mq",
        "scoreboard players operation #b mq -= #a mq",
        "scoreboard players set #op mq 0",
    ]


def _gen_sub() -> list[str]:
    # a は 1..max（a = 0 を避ける）、b は 0..a、ans = a - b
    return [
        *_rand_mod("#a", "#max"),
        "scoreboard players add #a mq 1",
        "scoreboard players operation #t mq = #a mq",
        "scoreboard players add #t mq 1",
        *_rand_mod("#b", "#t"),
        "scoreboard players operation #ans mq = #a mq",
        "scoreboard players operation #ans mq -= #b mq",
        "scoreboard players set #op mq 1",
    ]


def _wrong_one(w: str) -> list[str]:
    # w = ans ± d（d は 1..3）。負になったら ans + d に折り返す（w + 2d）
    return [
        *_rand_below("#d", 3),
        "scoreboard players add #d mq 1",
        *_rand_below("#s", 2),
        f"scoreboard players operation {w} mq = #ans mq",
        f"execute if score #s mq matches 0 run scoreboard players operation {w} mq += #d mq",
        f"execute if score #s mq matches 1 run scoreboard players operation {w} mq -= #d mq",
        "scoreboard players operation #t mq = #d mq",
        "scoreboard players operation #t mq += #d mq",
        f"execute if score {w} mq matches ..-1 run scoreboard players operation {w} mq += #t mq",
    ]


def _gen_wrong() -> list[str]:
    return [
        *_wrong_one("#w1"),
        *_wrong_one("#w2"),
        # w2 が w1 と重なったら反対側へ（w2 = 2*ans - w1）。それも負なら ans + 4
        "scoreboard players set #s mq 0",
        "execute if score #w2 mq = #w1 mq run scoreboard players set #s mq 1",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq = #ans mq",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq += #ans mq",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq -= #w1 mq",
        "execute if score #w2 mq matches ..-1 run scoreboard players set #s mq 2",
        "execute if score #s mq matches 2 run scoreboard players operation #w2 mq = #ans mq",
        "execute if score #s mq matches 2 run scoreboard players add #w2 mq 4",
    ]


def _gen_shuffle() -> list[str]:
    # 3 つの並び順 6 通りを #p で選ぶ（ループを持たないため全列挙）
    perms = [
        ("#ans", "#w1", "#w2"), ("#ans", "#w2", "#w1"),
        ("#w1", "#ans", "#w2"), ("#w1", "#w2", "#ans"),
        ("#w2", "#ans", "#w1"), ("#w2", "#w1", "#ans"),
    ]
    lines = _rand_below("#p", 6)
    for k, perm in enumerate(perms):
        for c, src in zip(("#c1", "#c2", "#c3"), perm):
            lines.append(
                f"execute if score #p mq matches {k} run scoreboard players operation {c} mq = {src} mq"
            )
    return lines


def _show() -> list[str]:
    def question(op: str):
        return [
            {"text": "", "color": "yellow", "bold": True},
            score_text("#a"), {"text": op}, score_text("#b"), {"text": " = ?"},
        ]

    lines = [
        f"execute if score #op mq matches 0 run {set_display_text('mq_q', question(' + '))}",
        f"execute if score #op mq matches 1 run {set_display_text('mq_q', question(' - '))}",
    ]
    for k, tag in enumerate(DISPLAY_TAGS[1:], start=1):
        lines.append(set_display_text(tag, [{"text": "", "color": "white", "bold": True}, score_text(f"#c{k}")]))
    return lines


def question_functions(cfg: Config) -> dict[str, str]:
    fns = {
        "gen": _gen(),
        "gen/add": _gen_add(),
        "gen/sub": _gen_sub(),
        "gen/wrong": _gen_wrong(),
        "gen/shuffle": _gen_shuffle(),
        "show": _show(),
    }
    return {name: "\n".join(lines) + "\n" for name, lines in fns.items()}
