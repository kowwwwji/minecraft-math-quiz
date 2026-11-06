#!/usr/bin/env python3
"""算数ダンジョンのデータパックを dist/mathquiz/ に書き出す。"""

import argparse

from builder.config import Config
from builder.pack import all_functions, write_pack


def main() -> None:
    parser = argparse.ArgumentParser(description="算数ダンジョンのデータパックを生成する")
    parser.add_argument("--out", default="dist/mathquiz", help="書き出し先（既定: dist/mathquiz）")
    args = parser.parse_args()
    cfg = Config()
    out = write_pack(cfg, args.out)
    print(f"{out}: {len(all_functions(cfg))} functions")


if __name__ == "__main__":
    main()
