"""The app's "Download as HTML" (core.js exportHtml) must import back with tools/import_doc.py."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import import_doc  # noqa: E402


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ExportRoundTripTests(unittest.TestCase):
    def roundtrip(self, deck_path: Path):
        deck = json.loads(deck_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            html = Path(td) / "export.html"
            js = "const C=require(process.argv[1]);const fs=require('fs');fs.writeFileSync(process.argv[3],C.exportHtml(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))))"
            subprocess.run(["node", "-e", js, str(ROOT / "docs" / "core.js"), str(deck_path), str(html)], check=True)
            back, warnings = import_doc.extract(html.read_text(encoding="utf-8"), img_dir=Path(td) / "img", deck_key="x")
        return deck, back, warnings

    def test_every_test_survives_export_and_reimport(self):
        index = json.loads((ROOT / "docs" / "decks" / "index.json").read_text())
        for e in index["decks"]:
            with self.subTest(test=e["title"]):
                deck, back, _ = self.roundtrip(ROOT / "docs" / "decks" / e["file"])
                shape = lambda d: [((s.get("group") or ""), s["name"], [(c["prompt"], c.get("label")) for c in s["cards"]]) for s in d["sections"]]
                self.assertEqual(shape(back), shape(deck))
                # images are exported as full site URLs; without a site to fetch from, compare everything else
                # empty paragraphs are dropped on import, which doesn't change how a card looks
                no_img = lambda h: re.sub(r"<p>\s*</p>", "", re.sub(r"<img [^>]*>", "", h or ""))
                fields = lambda d: [(no_img(c.get("promptHtml")), no_img(c["answerHtml"])) for s in d["sections"] for c in s["cards"]]
                diffs = [(a, b) for a, b in zip(fields(back), fields(deck)) if a != b]
                self.assertEqual(diffs[:3], [], f"{len(diffs)} cards came back different")


if __name__ == "__main__":
    unittest.main()
