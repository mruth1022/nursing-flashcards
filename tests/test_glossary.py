import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_glossary as bg  # noqa: E402

MD = """# Guide

## Units
- **Not a glossary entry**: ignored because it is above the glossary.

## Glossary of Key Terms (A–Z)

### A
- **Akathisia**: Restlessness from **antipsychotics**; *often* missed. See Part 2: EPS. (Boyd 7e Ch 12, p.469; Unit 5)
- **ADHD agents**: See Part 1D for stimulants (ATI ch 25).
- **Mood**: The sustained emotional state. (Boyd 7e Ch 10; Unit 3)
- **Tardive dyskinesia (TD)**: Late movement disorder. *(general knowledge; Unit 6)*
- **Scaling questions (SFBT)**: Rate 0 to 10. (Unit 4)

## Sources & Caveats
- **After**: ignored because it is below the glossary.
"""


class NameRuleTests(unittest.TestCase):
    def test_trailing_acronym_kept_when_initial_matches(self):
        self.assertEqual(bg.names_for("Tardive dyskinesia (TD)"), ["Tardive dyskinesia", "TD"])
        self.assertEqual(bg.names_for("Compliments (SFBT)"), ["Compliments"])

    def test_acronym_term_gets_its_expansion(self):
        self.assertEqual(bg.names_for("MMSE (Mini-Mental State Examination, Folstein)"), ["MMSE", "Mini-Mental State Examination"])

    def test_qualifier_is_dropped(self):
        self.assertEqual(bg.names_for("Autonomy (ethical principle)"), ["Autonomy"])
        self.assertEqual(bg.names_for("Binge-eating/purging type (anorexia nervosa)"), ["Binge-eating/purging type"])
        self.assertEqual(bg.names_for("Chaos (vs. crisis)"), ["Chaos"])

    def test_slash_and_middle_parenthetical(self):
        self.assertEqual(bg.names_for("Duty to warn / duty to protect"), ["Duty to warn", "duty to protect"])
        self.assertEqual(bg.names_for("Developmental (maturational) crisis"), ["Developmental crisis", "maturational crisis"])

    def test_two_letter_names_only_when_acronyms(self):
        self.assertEqual(bg.names_for("Anorexia nervosa (AN)"), ["Anorexia nervosa", "AN"])
        self.assertEqual(bg.names_for("Go"), [])


class BuildTests(unittest.TestCase):
    def test_only_the_glossary_section_and_cleanups(self):
        entries = bg.build(MD, {})
        terms = [e["term"] for e in entries]
        self.assertEqual(terms, ["Akathisia", "Mood", "Tardive dyskinesia (TD)", "Scaling questions (SFBT)"])  # ADHD agents was only a pointer
        ak = entries[0]
        self.assertEqual(ak["html"], "Restlessness from <b>antipsychotics</b>; <i>often</i> missed.")
        self.assertEqual(ak["source"], "Boyd 7e Ch 12, p.469; Unit 5")
        self.assertEqual(entries[2]["source"], "general knowledge; Unit 6")

    def test_overrides(self):
        ov = {"excludeNames": ["Mood"], "dropNames": {"Scaling questions (SFBT)": ["SFBT"]},
              "aliases": {"Akathisia": ["restless legs (EPS)"]}, "exclude": ["Tardive dyskinesia (TD)"]}
        by = {e["term"]: e["names"] for e in bg.build(MD, ov)}
        self.assertEqual(by["Mood"], [])                       # kept as an entry, never matched
        self.assertEqual(by["Scaling questions (SFBT)"], ["Scaling questions"])
        self.assertEqual(by["Akathisia"], ["Akathisia", "restless legs (EPS)"])
        self.assertNotIn("Tardive dyskinesia (TD)", by)

    def test_main_writes_glossary_and_index_for_named_tests(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "g.md").write_text(MD, encoding="utf-8")
            (td / "index.json").write_text(json.dumps({"decks": [{"key": "k1", "title": "Psych A"}, {"key": "k2", "title": "OB"}]}), encoding="utf-8")
            (td / "glossary").mkdir()
            (td / "glossary" / "index.json").write_text(json.dumps({"glossaries": [{"name": "ob", "file": "ob.json", "decks": ["k2"]}]}))
            args = [str(td / "g.md"), "--name", "psych", "--decks", "Psych A", "--index", str(td / "index.json"),
                    "--out-dir", str(td / "glossary"), "--overrides", str(td / "none.json")]
            self.assertEqual(bg.main(args), 0)
            idx = json.loads((td / "glossary" / "index.json").read_text())
            self.assertEqual([(g["name"], g["decks"]) for g in idx["glossaries"]], [("ob", ["k2"]), ("psych", ["k1"])])
            self.assertEqual(len(json.loads((td / "glossary" / "psych.json").read_text())["terms"]), 4)
            with self.assertRaises(SystemExit):
                bg.main(args[:3] + ["No such test"] + args[4:])


if __name__ == "__main__":
    unittest.main()
