import json
import re
import tempfile
import unittest
from pathlib import Path

from builder.config import Config
from builder.pack import all_functions, write_pack


class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = write_pack(Config(), Path(self.tmp.name) / "mathquiz")

    def tearDown(self):
        self.tmp.cleanup()

    def test_mcmeta_and_tags(self):
        meta = json.loads((self.out / "pack.mcmeta").read_text())
        self.assertEqual(meta["pack"]["min_format"], 121)
        self.assertEqual(meta["pack"]["max_format"], 121)
        tags = self.out / "data/minecraft/tags/function"
        self.assertEqual(json.loads((tags / "load.json").read_text()), {"values": ["mathquiz:load"]})
        self.assertEqual(json.loads((tags / "tick.json").read_text()), {"values": ["mathquiz:tick"]})

    def test_every_function_reference_resolves(self):
        fn_dir = self.out / "data/mathquiz/function"
        existing = {p.relative_to(fn_dir).with_suffix("").as_posix() for p in fn_dir.rglob("*.mcfunction")}
        self.assertEqual(existing, set(all_functions(Config())))
        for p in fn_dir.rglob("*.mcfunction"):
            for ref in re.findall(r"function mathquiz:([\w/]+)", p.read_text()):
                self.assertIn(ref, existing, msg=f"{p.name} -> {ref}")

    def test_no_leading_slash_and_no_blank_functions(self):
        for p in (self.out / "data/mathquiz/function").rglob("*.mcfunction"):
            body = p.read_text()
            self.assertTrue(body.startswith("# "), p.name)
            self.assertNotRegex(body, r"(?m)^/")
            self.assertTrue(any(l and not l.startswith("#") for l in body.splitlines()), p.name)

    def test_rewrite_replaces_old_files(self):
        stale = self.out / "data/mathquiz/function/old.mcfunction"
        stale.write_text("say x")
        write_pack(Config(), self.out)
        self.assertFalse(stale.exists())
