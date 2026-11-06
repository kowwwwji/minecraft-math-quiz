"""全関数をまとめてデータパックとして書き出す。"""

import json
import re
import shutil
from pathlib import Path

from builder.config import Config
from builder.game import game_functions
from builder.questions import question_functions
from builder.rooms import room_functions

PACK_FORMAT = 121  # Minecraft Java 26.3
PACK_MCMETA = {"pack": {"description": "さんすうダンジョン", "min_format": PACK_FORMAT, "max_format": PACK_FORMAT}}

# 各 mcfunction の先頭コメント（ゲーム内でファイルを開いた親が役割を分かるように）
DESCRIPTIONS = {
    "load": "リロード時の初期化（スコアボードと既定レベル）",
    "setup": "ダンジョンを建てる（親が実行）",
    "setup/build": "建築の本体。setup から 1 秒後に呼ばれる",
    "start": "遊びはじめる（親が実行）。状態を戻して部屋 1 へ",
    "quit": "遊びをやめる（親が実行）。クリエイティブに戻して start 時の位置へ",
    "tick": "毎ティック。遊んでいる間だけボタンを見張る",
    "check": "現在の部屋の 3 つのボタンが押されたか調べる",
    "correct": "正解。扉を開けて次の部屋へ",
    "wrong": "不正解。命が残っていれば床抜き、無ければ爆発",
    "wrong/drop": "不正解（まだ命がある）。床を抜いて 3 秒後に restore",
    "boom": "3 回目の不正解。足元に TNT を出す",
    "boom/kill": "TNT の爆発。煙と音を出して子どもを倒す",
    "gameover": "リスポーン後にクリエイティブへ戻して遊びを終える",
    "restore": "床を戻して同じ部屋に新しい問題を出す",
    "activate": "現在の部屋を有効にする（問題を出すかゴールか）",
    "question": "問題を作って表示し、入力を受け付ける",
    "goal": "ゴール部屋が有効になった。表示をゴール用に切り替える",
    "goal/enter": "ゴール部屋に入った。演出を始める（1 回だけ）",
    "goal/fireworks": "花火を 1 回ぶん上げ、残りがあれば次を予約する",
    "gen": "問題を作る（足し算か引き算を選ぶ）",
    "gen/add": "足し算の問題を作る",
    "gen/sub": "引き算の問題を作る",
    "gen/wrong": "誤答を 2 つ作る（正解と重ならず 0 以上）",
    "gen/shuffle": "3 つの選択肢の並び順を決める",
    "show": "問題と選択肢を text_display に書き込む",
}
PATTERNS = [
    (re.compile(r"press/(\d+)"), "ボタン {0} が押された"),
    (re.compile(r"level/(\w+)"), "難易度を {0} にする"),
    (re.compile(r"room/(\d+)/activate"), "部屋 {0} に表示を移動する"),
    (re.compile(r"room/(\d+)/open"), "部屋 {0} の扉を開ける"),
    (re.compile(r"room/(\d+)/drop"), "部屋 {0} の床を抜く"),
    (re.compile(r"room/(\d+)/restore"), "部屋 {0} の床を戻す（先に穴の底へ退避）"),
]


def describe(name: str) -> str:
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name]
    for pattern, fmt in PATTERNS:
        m = pattern.fullmatch(name)
        if m:
            return fmt.format(*m.groups())
    raise KeyError(f"説明が無い関数: {name}")


def all_functions(cfg: Config) -> dict[str, str]:
    merged: dict[str, str] = {}
    for fns in (question_functions(cfg), room_functions(cfg), game_functions(cfg)):
        dup = merged.keys() & fns.keys()
        if dup:
            raise ValueError(f"関数名が重複: {sorted(dup)}")
        merged.update(fns)
    return merged


def write_pack(cfg: Config, out_dir: str | Path) -> Path:
    """out_dir を作り直して書き出す（古い関数ファイルを残さないため）。"""
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    fn_dir = out / "data/mathquiz/function"
    tag_dir = out / "data/minecraft/tags/function"
    fn_dir.mkdir(parents=True)
    tag_dir.mkdir(parents=True)

    (out / "pack.mcmeta").write_text(json.dumps(PACK_MCMETA, ensure_ascii=False, indent=2) + "\n")
    for tag in ("load", "tick"):
        (tag_dir / f"{tag}.json").write_text(json.dumps({"values": [f"mathquiz:{tag}"]}) + "\n")
    for name, body in all_functions(cfg).items():
        path = fn_dir / f"{name}.mcfunction"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {name}: {describe(name)}\n{body}")
    return out
