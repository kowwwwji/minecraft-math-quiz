"""出題ロジック検証用の最小スコアボード・シミュレータ。

gen 系の mcfunction が使う構文だけを解釈する。未対応の構文は NotImplementedError にして、
生成側がサポート外の書き方をしたらテストが落ちるようにする（ゲーム内で初めて壊れるのを防ぐ）。
"""

import random

NAMESPACE = "mathquiz:"


class Sim:
    def __init__(self, functions: dict[str, str], rng: random.Random):
        self.functions = functions
        self.rng = rng
        self.scores: dict[str, int] = {}  # "#a" → 値（objective は mq 固定）

    def run(self, name: str) -> None:
        for line in self.functions[name].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self._exec(line.split())

    # --- コマンド ---

    def _exec(self, tokens: list[str]) -> int | None:
        head = tokens[0]
        if head == "execute":
            return self._execute(tokens[1:])
        if head == "scoreboard":
            return self._scoreboard(tokens[1:])
        if head == "random":
            return self._random(tokens[1:])
        if head == "function":
            if len(tokens) != 2 or not tokens[1].startswith(NAMESPACE):
                raise NotImplementedError(" ".join(tokens))
            self.run(tokens[1][len(NAMESPACE):])
            return None
        raise NotImplementedError(" ".join(tokens))

    def _execute(self, tokens: list[str]) -> int | None:
        store = None
        i = 0
        while tokens[i] != "run":
            t = tokens[i]
            if t in ("if", "unless"):
                self._expect(tokens, i + 1, "score")
                self._expect(tokens, i + 3, "mq")
                a = tokens[i + 2]
                if tokens[i + 4] == "matches":
                    ok = self._matches(a, tokens[i + 5])
                    i += 6
                else:
                    self._expect(tokens, i + 6, "mq")
                    ok = self._compare(a, tokens[i + 4], tokens[i + 5])
                    i += 7
                if (t == "if") != ok:
                    return None
            elif t == "store":
                self._expect(tokens, i + 1, "result")
                self._expect(tokens, i + 2, "score")
                self._expect(tokens, i + 4, "mq")
                store = tokens[i + 3]
                i += 5
            else:
                raise NotImplementedError(" ".join(tokens))
        result = self._exec(tokens[i + 1:])
        if store is not None:
            if result is None:
                raise NotImplementedError("store result: 結果を返さないコマンド " + " ".join(tokens))
            self.scores[store] = result
        return result

    def _scoreboard(self, tokens: list[str]) -> int | None:
        self._expect(tokens, 0, "players")
        sub = tokens[1]
        name = tokens[2]
        self._expect(tokens, 3, "mq")
        if sub == "set":
            self.scores[name] = int(tokens[4])
            return self.scores[name]
        if sub == "add":
            self.scores[name] = self.scores.get(name, 0) + int(tokens[4])
            return self.scores[name]
        if sub == "remove":
            self.scores[name] = self.scores.get(name, 0) - int(tokens[4])
            return self.scores[name]
        if sub == "operation":
            op, other = tokens[4], tokens[5]
            self._expect(tokens, 6, "mq")
            a = self.scores.get(name, 0)
            b = self.scores.get(other, 0)
            if op == "=":
                a = b
            elif op == "+=":
                a += b
            elif op == "-=":
                a -= b
            elif op == "*=":
                a *= b
            elif op == "/=":
                a //= b  # Java の floorDiv と同じ
            elif op == "%=":
                a %= b  # Java の floorMod と同じ
            else:
                raise NotImplementedError(" ".join(tokens))
            self.scores[name] = a
            return a
        raise NotImplementedError(" ".join(tokens))

    def _random(self, tokens: list[str]) -> int:
        if len(tokens) != 2 or tokens[0] != "value":
            raise NotImplementedError(" ".join(tokens))
        lo, hi = (int(v) for v in tokens[1].split(".."))
        if hi - lo + 1 < 2:
            raise ValueError(f"random value の範囲幅が 2 未満: {tokens[1]}")
        return self.rng.randint(lo, hi)

    # --- 条件 ---

    def _matches(self, name: str, rng: str) -> bool:
        if name not in self.scores:
            return False
        v = self.scores[name]
        if ".." in rng:
            lo, hi = rng.split("..")
            return (lo == "" or int(lo) <= v) and (hi == "" or v <= int(hi))
        return v == int(rng)

    def _compare(self, a: str, op: str, b: str) -> bool:
        if a not in self.scores or b not in self.scores:
            return False
        x, y = self.scores[a], self.scores[b]
        ops = {"<": x < y, "<=": x <= y, "=": x == y, ">=": x >= y, ">": x > y}
        if op not in ops:
            raise NotImplementedError(op)
        return ops[op]

    @staticmethod
    def _expect(tokens: list[str], i: int, word: str) -> None:
        if i >= len(tokens) or tokens[i] != word:
            raise NotImplementedError(" ".join(tokens))
