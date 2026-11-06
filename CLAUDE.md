# CLAUDE.md — minecraft-math-quiz

小学一年生向けの「算数ダンジョン」を Minecraft Java 版のデータパックとして作るリポジトリ。
Python スクリプトでデータパックを生成し、ワールドへコピーして遊ぶ。

## まず読むもの

- 設計書: `docs/superpowers/specs/2026-11-06-math-dungeon-design.md`（仕様の正。ここに無いことは作る側の判断）
- 進捗と次の手: `tasks/todo.md`（git 管理外）

## 環境

- Minecraft Java 版 **26.3**、データパック形式 **121**。執筆時点の AI の知識より新しいので、
  コマンド構文は minecraft.wiki とゲーム内テストで確認する（特に `text_display`・`random`・`schedule`）。
- 手元の `~/Library/Application Support/minecraft/versions/26.3/26.3.jar` でも確認できる:
  `version.json`（pack 形式）、`assets/minecraft/blockstates/*.json`（ブロック状態）、
  `assets/minecraft/lang/en_us.json`（エンティティ・音・コマンドの ID の有無）。
- 対象ワールド: `~/Library/Application Support/minecraft/saves/さんすう/`（シングル・コマンド許可済み）。
  datapacks の配置先は `saves/さんすう/datapacks/mathquiz/`。
- Python 3.11（mise）。外部ライブラリを入れない。テストは `python3 -m unittest`。
- ゲーム内の動作確認はユーザーが行う。確認してほしい手順を具体的に伝える
  （`/reload` → `/function mathquiz:setup` → `/function mathquiz:start` → 正解・不正解を 1 回ずつ）。

## 構成

- `build.py` が `dist/mathquiz/` にデータパックを書き出す（座標計算は Python 側で済ませ、mcfunction は絶対座標）。
- `install.sh` が `dist/mathquiz/` をワールドの `datapacks/` へコピーする。
- `dist/` は git 管理外。

## 規約

- 説明・コメントは日本語。「何を」より「なぜ」を残す。
- コミットメッセージ: `type(scope) 日本語説明`（type: add / fix / refactor / docs / update / delete）。
