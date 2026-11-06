#!/usr/bin/env bash
# データパックを生成してワールドの datapacks/ へコピーする。
# コピー先は WORLD 環境変数で変えられる。
set -euo pipefail

WORLD="${WORLD:-$HOME/Library/Application Support/minecraft/saves/さんすう}"
cd "$(dirname "$0")"

if [ ! -d "$WORLD" ]; then
  echo "ワールドが見つかりません: $WORLD" >&2
  exit 1
fi

python3 build.py
mkdir -p "$WORLD/datapacks"
# --delete で古い関数ファイルを残さない（名前を変えた関数が二重に読まれるのを防ぐ）
rsync -a --delete dist/mathquiz/ "$WORLD/datapacks/mathquiz/"
echo "installed: $WORLD/datapacks/mathquiz"
