# minecraft-math-quiz

小学一年生向けの「算数ダンジョン」を Minecraft Java 版のデータパックとして作る。
部屋に浮かぶ問題（例 `3 + 4 = ?`）に 3 つのボタンで答え、正解なら扉が開き、
不正解なら足元が抜けて水の穴に落ちる。問題は毎回ランダム。

仕様は設計書 `docs/superpowers/specs/2026-11-06-math-dungeon-design.md` が正。

## 使い方（親の操作）

1. `./install.sh` でデータパックを生成し、ワールド `さんすう` の `datapacks/` へコピーする
   （別のワールドに入れるときは `WORLD=/path/to/world ./install.sh`）。
2. ワールドを開いて `/reload`。
3. `/function mathquiz:setup` でダンジョンを建てる（一度だけ。再実行で建て直し）。
4. `/function mathquiz:start` で子どもを 1 部屋目に送り、問題を出す。
5. 遊び終わったら `/function mathquiz:quit`。クリエイティブに戻し、`setup` を打った場所へ戻る。

難易度は `start` の前後どちらで切り替えてもよい（次の問題から反映）。

- `/function mathquiz:level/easy` … 足し算だけ、答え 0〜5
- `/function mathquiz:level/normal` … 足し算と引き算、答え 0〜10（既定）
- `/function mathquiz:level/hard` … 足し算と引き算、答え 0〜20

## 動作確認の手順

データパックを変えたら、この順に確認する。

1. `/reload` のあと `/function mathquiz:setup`。1 秒ほどで空中（y=120）に石レンガの建物ができ、
   入口に立っていること。
2. `/function mathquiz:start` で部屋 1 に入り、正面の壁の上に問題、3 つのボタンの上に数字が
   大きく見えること。
3. 正解のボタンを押す。「せいかい！」が出て音が鳴り、右（+X）側の鉄格子が消えること。
4. 次の部屋で不正解のボタンを押す。「ざんねん…」が出て落ち、水に着水してダメージが無いこと。
   はしごで部屋に戻れ、3 秒後に床が戻って新しい問題が出ていること。
   はしごを登り切った場所からボタンを連打しても、新しい問題が勝手に答えられないこと。
5. 5 部屋クリアで「ゴール！」と花火、宝箱があること。

## 開発

- テスト: `python3 -m unittest`
- 生成のみ: `python3 build.py`（`dist/mathquiz/` に書き出す。`--out` で変更可）
- 座標・部屋数・難易度は `builder/config.py`
