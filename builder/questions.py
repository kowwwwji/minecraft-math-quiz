"""出題ロジックの mcfunction 生成。

計算はすべてゲーム内のスコアボードで行う。乱数は常に広い固定範囲を引いてから `%=` で
縮める（`random value N..N` のように範囲幅が 1 になるとコマンドが失敗して問題が出ないため）。
`#t` は一時変数・定数置き場として使い回す。

出題は「足し算・引き算の式（gen/expr）」と「九九（gen/mul）」の 2 系統だけ。式は左から 1 項ずつ
gen/term で決め、途中の値 `#acc` を見て `+` `-` の選べる側だけを選ぶので、途中計算と答えが
必ず 0〜上限に収まる（再試行ループを持たない）。
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
    # #r: 0 = 足し算・引き算の式、1 = 九九。九九なしの難易度では常に式
    return [
        *_rand_below("#r", 2),
        "execute if score #mul mq matches 0 run scoreboard players set #r mq 0",
        "execute if score #r mq matches 0 run function mathquiz:gen/expr",
        "execute if score #r mq matches 1 run function mathquiz:gen/mul",
        "execute if score #r mq matches 0 run function mathquiz:gen/wrong",
        "execute if score #r mq matches 1 run function mathquiz:gen/mul_wrong",
        "function mathquiz:gen/shuffle",
    ]


def _gen_expr() -> list[str]:
    # #hold は「後ろの項のために上限から取り置く量」。引き算なしの難易度で a が上限近くになると
    # 後ろの項が下限以上で取れなくなるので、下限 × 残り項数を先に取り置いて + を必ず選べるようにする。
    # 引き算ありなら - に倒せるので取り置かない。
    # （名前が #room でないのは、#room が「現在の部屋番号」としてゲーム側で使われているため）
    return [
        "scoreboard players operation #hold mq = #terms mq",
        "scoreboard players remove #hold mq 1",
        "scoreboard players operation #hold mq *= #lo mq",
        "execute if score #sub mq matches 1 run scoreboard players set #hold mq 0",
        # a = 下限 + 乱数 % (上限 − 取り置き − 下限 + 1)
        "scoreboard players operation #t mq = #max mq",
        "scoreboard players operation #t mq -= #hold mq",
        "scoreboard players operation #t mq -= #lo mq",
        "scoreboard players add #t mq 1",
        *_rand_mod("#a", "#t"),
        "scoreboard players operation #a mq += #lo mq",
        "scoreboard players operation #acc mq = #a mq",
        # 2 項目: 3 項・引き算なしのときだけ 3 項目ぶんを取り置く
        "scoreboard players operation #hold mq = #lo mq",
        "execute if score #terms mq matches 2 run scoreboard players set #hold mq 0",
        "execute if score #sub mq matches 1 run scoreboard players set #hold mq 0",
        "function mathquiz:gen/term",
        "scoreboard players operation #b mq = #n mq",
        "scoreboard players operation #op1 mq = #o mq",
        # 3 項目: 最後なので取り置きなし
        "scoreboard players set #hold mq 0",
        "execute if score #terms mq matches 3 run function mathquiz:gen/term",
        "execute if score #terms mq matches 3 run scoreboard players operation #c mq = #n mq",
        "execute if score #terms mq matches 3 run scoreboard players operation #op2 mq = #o mq",
        "scoreboard players operation #ans mq = #acc mq",
    ]


def _gen_term() -> list[str]:
    # #acc（ここまでの値）と #hold（取り置き）から、+ と - のどちらが選べるかをフラグに固定してから選ぶ。
    # + は「残り（上限 − #acc − 取り置き）が下限以上」、- は「引き算ありで #acc が下限以上」のとき選べる。
    # 上限 ≥ 下限 × 2 なので両方選べないことはない
    return [
        "scoreboard players operation #t mq = #max mq",
        "scoreboard players operation #t mq -= #acc mq",
        "scoreboard players operation #t mq -= #hold mq",
        "scoreboard players set #plus mq 0",
        "execute if score #t mq >= #lo mq run scoreboard players set #plus mq 1",
        "scoreboard players set #minus mq 0",
        "execute if score #sub mq matches 1 if score #acc mq >= #lo mq run scoreboard players set #minus mq 1",
        *_rand_below("#o", 2),
        "execute if score #plus mq matches 0 run scoreboard players set #o mq 1",
        "execute if score #minus mq matches 0 run scoreboard players set #o mq 0",
        "execute if score #o mq matches 0 run function mathquiz:gen/term/add",
        "execute if score #o mq matches 1 run function mathquiz:gen/term/sub",
    ]


def _gen_term_add() -> list[str]:
    # n = 下限 + 乱数 % (上限 − #acc − 取り置き − 下限 + 1)。gen/term が + を選べると判定済みなので法は 1 以上
    return [
        "scoreboard players operation #t mq = #max mq",
        "scoreboard players operation #t mq -= #acc mq",
        "scoreboard players operation #t mq -= #hold mq",
        "scoreboard players operation #t mq -= #lo mq",
        "scoreboard players add #t mq 1",
        *_rand_mod("#n", "#t"),
        "scoreboard players operation #n mq += #lo mq",
        "scoreboard players operation #acc mq += #n mq",
    ]


def _gen_term_sub() -> list[str]:
    # n = 下限 + 乱数 % (#acc − 下限 + 1)。引いた後も 0 以上
    return [
        "scoreboard players operation #t mq = #acc mq",
        "scoreboard players operation #t mq -= #lo mq",
        "scoreboard players add #t mq 1",
        *_rand_mod("#n", "#t"),
        "scoreboard players operation #n mq += #lo mq",
        "scoreboard players operation #acc mq -= #n mq",
    ]


def _gen_mul() -> list[str]:
    # a × b（1〜9）。#op1 = 2 が九九の印（show で × を出し、誤答は gen/mul_wrong で作る）
    return [
        *_rand_below("#a", 9),
        "scoreboard players add #a mq 1",
        *_rand_below("#b", 9),
        "scoreboard players add #b mq 1",
        "scoreboard players operation #ans mq = #a mq",
        "scoreboard players operation #ans mq *= #b mq",
        "scoreboard players set #op1 mq 2",
    ]


def _sign(target: str, limit_var: str) -> list[str]:
    # target = ±1（乱数）。掛ける数が 1〜9 を外れる向きは逆にする
    return [
        *_rand_below(target, 2),
        f"scoreboard players operation {target} mq += {target} mq",
        f"scoreboard players remove {target} mq 1",
        f"execute if score {limit_var} mq matches 9 run scoreboard players set {target} mq -1",
        f"execute if score {limit_var} mq matches 1 run scoreboard players set {target} mq 1",
    ]


def _gen_mul_wrong() -> list[str]:
    # 正解 ±1〜3 は九九の表にない数ですぐ見抜かれるので、表の隣 (a ± 1) × b と a × (b ± 1) を誤答にする。
    # a = b で同じ向きだと 2 つが一致するので、一致したら後者を a × (b ± 2) にする（2 × 2 で 0 になるのは許容）
    return [
        *_sign("#d", "#a"),
        "scoreboard players operation #w1 mq = #a mq",
        "scoreboard players operation #w1 mq += #d mq",
        "scoreboard players operation #w1 mq *= #b mq",
        *_sign("#e", "#b"),
        "scoreboard players operation #w2 mq = #b mq",
        "scoreboard players operation #w2 mq += #e mq",
        "scoreboard players operation #w2 mq *= #a mq",
        # 一致の判定を #s に固定してから分岐する（分岐先が #w2 を変えるため）
        "scoreboard players set #s mq 0",
        "execute if score #w2 mq = #w1 mq run scoreboard players set #s mq 1",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq = #b mq",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq += #e mq",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq += #e mq",
        "execute if score #s mq matches 1 run scoreboard players operation #w2 mq *= #a mq",
    ]


def _gen_wrong() -> list[str]:
    # 候補は [max(ans−3, 0), min(ans+3, 上限)] から正解を除いた数（上限 ≥ 10 なので常に 3 つ以上）。
    # 「候補の個数で乱数を引き、正解（と 1 つ目の誤答）を小さい方から順に飛ばす」ことで重複なく選ぶ
    return [
        "scoreboard players operation #lo2 mq = #ans mq",
        "scoreboard players remove #lo2 mq 3",
        "execute if score #lo2 mq matches ..-1 run scoreboard players set #lo2 mq 0",
        "scoreboard players operation #hi2 mq = #ans mq",
        "scoreboard players add #hi2 mq 3",
        "execute if score #hi2 mq > #max mq run scoreboard players operation #hi2 mq = #max mq",
        # 候補の個数（#ans ぶんを除く）
        "scoreboard players operation #t mq = #hi2 mq",
        "scoreboard players operation #t mq -= #lo2 mq",
        *_rand_mod("#w1", "#t"),
        "scoreboard players operation #w1 mq += #lo2 mq",
        "execute if score #w1 mq >= #ans mq run scoreboard players add #w1 mq 1",
        "scoreboard players remove #t mq 1",
        *_rand_mod("#w2", "#t"),
        "scoreboard players operation #w2 mq += #lo2 mq",
        # 飛ばす 2 つを小さい順に #m1 ≤ #m2 へ並べ、小さい方から順に飛ばす（順番を守ること）
        "scoreboard players operation #m1 mq = #ans mq",
        "execute if score #w1 mq < #ans mq run scoreboard players operation #m1 mq = #w1 mq",
        "scoreboard players operation #m2 mq = #ans mq",
        "execute if score #w1 mq > #ans mq run scoreboard players operation #m2 mq = #w1 mq",
        "execute if score #w2 mq >= #m1 mq run scoreboard players add #w2 mq 1",
        "execute if score #w2 mq >= #m2 mq run scoreboard players add #w2 mq 1",
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
    def question(*parts):
        # parts は score 名と演算子の文字列を交互に並べたもの
        out = [{"text": "", "color": "yellow", "bold": True}]
        for part in parts:
            out.append(score_text(part) if part.startswith("#") else {"text": part})
        out.append({"text": " = ?"})
        return out

    sym = {0: " + ", 1: " - "}
    lines = [
        f"execute if score #op1 mq matches 2 run {set_display_text('mq_q', question('#a', ' × ', '#b'))}",
    ]
    for op1 in (0, 1):
        lines.append(
            f"execute if score #terms mq matches 2 if score #op1 mq matches {op1} run "
            f"{set_display_text('mq_q', question('#a', sym[op1], '#b'))}"
        )
    for op1 in (0, 1):
        for op2 in (0, 1):
            lines.append(
                f"execute if score #terms mq matches 3 if score #op1 mq matches {op1} if score #op2 mq matches {op2} run "
                f"{set_display_text('mq_q', question('#a', sym[op1], '#b', sym[op2], '#c'))}"
            )
    for k, tag in enumerate(DISPLAY_TAGS[1:], start=1):
        lines.append(set_display_text(tag, [{"text": "", "color": "white", "bold": True}, score_text(f"#c{k}")]))
    return lines


def question_functions(cfg: Config) -> dict[str, str]:
    fns = {
        "gen": _gen(),
        "gen/expr": _gen_expr(),
        "gen/term": _gen_term(),
        "gen/term/add": _gen_term_add(),
        "gen/term/sub": _gen_term_sub(),
        "gen/mul": _gen_mul(),
        "gen/mul_wrong": _gen_mul_wrong(),
        "gen/wrong": _gen_wrong(),
        "gen/shuffle": _gen_shuffle(),
        "show": _show(),
    }
    return {name: "\n".join(lines) + "\n" for name, lines in fns.items()}
