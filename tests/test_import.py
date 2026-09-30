import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import import_doc  # noqa: E402

SAMPLE_PATH = ROOT / "tools" / "sample" / "sample_export.html"
SAMPLE = SAMPLE_PATH.read_text(encoding="utf-8")


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.img_dir = Path(cls.tmp.name) / "img"
        cls.deck, cls.warnings = import_doc.extract(SAMPLE, img_dir=cls.img_dir)
        cls.by_prompt = {c["prompt"]: c for s in cls.deck["sections"] for c in s["cards"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_title_and_sections(self):
        self.assertEqual(self.deck["title"], "Sample Nursing Deck")
        names = [s["name"] for s in self.deck["sections"]]
        self.assertEqual(names, ["Vital Signs (Adult)", "Electrolytes & Labs", "Arterial Blood Gases"])

    def test_header_row_skipped_and_counts(self):
        counts = [len(s["cards"]) for s in self.deck["sections"]]
        self.assertEqual(counts, [5, 6, 2])
        self.assertNotIn("Term", self.by_prompt)
        self.assertEqual(self.deck["cardCount"], 13)

    def test_bold_from_css_class(self):
        hr = self.by_prompt["Normal adult heart rate"]["answerHtml"]
        self.assertIn("<p><b>60–100 bpm</b></p>", hr)

    def test_lists_merged_by_level_and_nested_levels(self):
        hr = self.by_prompt["Normal adult heart rate"]["answerHtml"]
        self.assertIn('<ul class="l0"><li>Bradycardia: &lt; 60 bpm</li><li>Tachycardia: &gt; 100 bpm</li></ul>', hr)
        self.assertIn('<ul class="l1"><li>Check apical pulse for a full minute before giving <i>digoxin</i></li></ul>', hr)

    def test_ordered_list_merged_and_bold_labels(self):
        bp = self.by_prompt["Blood pressure categories (ACC/AHA 2017)"]["answerHtml"]
        self.assertEqual(bp.count("<ol"), 1)
        self.assertIn("<li><b>Normal:</b> &lt; 120 / &lt; 80 mmHg</li>", bp)
        self.assertIn("<li><b>Stage 2:</b> ≥ 140 / ≥ 90</li>", bp)

    def test_links_unwrapped(self):
        bp = self.by_prompt["Blood pressure categories (ACC/AHA 2017)"]["answerHtml"]
        self.assertIn('<a href="https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065" target="_blank" rel="noopener">AHA guideline</a>', bp)
        self.assertNotIn("google.com/url", bp)

    def test_br_and_empty_paragraphs(self):
        rr = self.by_prompt["Normal adult respiratory rate"]["answerHtml"]
        self.assertIn("if regular;<br>a full minute", rr)
        self.assertNotIn("<p></p>", rr)

    def test_unreadable_image_dropped_with_warning(self):
        # the sample references a relative file that does not exist -> dropped, warned
        t = self.by_prompt["Normal oral temperature"]["answerHtml"]
        self.assertNotIn("<img", t)
        self.assertTrue(any("image" in w for w in self.warnings))

    def test_underline_and_unicode(self):
        spo2 = self.by_prompt["Normal SpO₂"]["answerHtml"]
        self.assertIn("<u>88–92%</u>", spo2)

    def test_empty_prompt_row_merges_into_previous(self):
        aptt = self.by_prompt["aPTT"]["answerHtml"]
        self.assertIn("warfarin is monitored with PT/INR", aptt)

    def test_third_column_label(self):
        self.assertEqual(self.by_prompt["Normal ABG values"].get("label"), "high-yield")
        self.assertNotIn("label", self.by_prompt["ROME mnemonic"])

    def test_ids_stable_and_deck_scoped(self):
        self.assertEqual(import_doc.card_id("  Sodium (Na⁺) "), import_doc.card_id("sodium (na⁺)"))
        self.assertEqual(len(self.by_prompt["INR"]["id"]), 10)
        other, _ = import_doc.extract(SAMPLE, deck_key="other-doc")
        other_ids = {c["prompt"]: c["id"] for s in other["sections"] for c in s["cards"]}
        self.assertNotEqual(other_ids["INR"], self.by_prompt["INR"]["id"])

    def test_header_modes(self):
        keep, _ = import_doc.extract(SAMPLE, header_mode="keep")
        self.assertEqual(keep["cardCount"], 14)
        skip, _ = import_doc.extract(SAMPLE, header_mode="skip")
        self.assertEqual(skip["cardCount"], 11)

    def test_section_names_override_per_table(self):
        deck, _ = import_doc.extract(SAMPLE, section_names=["Vitals", "", "ABG"])
        self.assertEqual([s["name"] for s in deck["sections"]], ["Vitals", "Electrolytes & Labs", "ABG"])

    def test_no_style_block_plain_html(self):
        html = "<html><body><h2>Sec</h2><table><tr><td><b>Q1</b></td><td>A1<br>line2</td></tr><tr><td>Q2</td><td><ul><li>x</li></ul></td></tr></table></body></html>"
        deck, w = import_doc.extract(html)
        self.assertEqual(deck["cardCount"], 2)
        self.assertEqual(deck["sections"][0]["name"], "Sec")
        self.assertEqual(deck["sections"][0]["cards"][0]["answerHtml"], "A1<br>line2")
        self.assertEqual(deck["sections"][0]["cards"][1]["answerHtml"], '<ul class="l0"><li>x</li></ul>')

    def test_json_roundtrip(self):
        json.loads(json.dumps(self.deck))


PNG_1x1 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
JPG_STUB = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

REAL_STYLE_DOC = f"""
<html><head><style type="text/css">
.c2{{background-color:#ffff00}} .c49{{background-color:#ff0000;color:#ffffff}} .c5{{color:#ff0000}} .c3{{font-weight:700}}
.c9{{text-decoration:line-through}} .c12{{vertical-align:super;font-size:8pt}}
</style></head><body>
<table><tbody>
<tr><td><p><span>PT</span></p></td><td><p><span class="c2">11 - 12.5</span><span> seconds</span></p></td></tr>
<tr><td><p><span></span></p></td><td><p><span></span></p></td></tr>
<tr><td><h2><span>Pulmonary Embolism</span></h2></td><td><p><span class="c5">Sudden dyspnea</span></p></td></tr>
<tr><td><p><span>Treatment</span></p></td><td><p><span class="c49">Heparin</span><span class="c9"> old</span><span>x</span><span class="c12">2</span><img src="data:image/png;base64,{PNG_1x1}"></p></td></tr>
<tr><td><h2><span>Tuberculosis</span></h2></td><td><p><span>Granuloma</span></p></td></tr>
<tr><td><p><span> </span><img src="data:image/jpeg;base64,{JPG_STUB}"></p></td><td><p><span class="c3">Sinus Bradycardia</span></p><ul class="lst-kix_a-0"><li><span>Rate &lt; 60</span></li></ul></td></tr>
</tbody></table>
<table><tbody>
<tr><td><p><span>Na</span></p></td><td><p><span>135 - 145</span></p></td></tr>
</tbody></table>
</body></html>
"""


class RealStyleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.img_dir = Path(self.tmp.name) / "img"
        self.deck, self.warnings = import_doc.extract(REAL_STYLE_DOC, img_dir=self.img_dir, section_names=["Coag"])
        self.secs = {s["name"]: s for s in self.deck["sections"]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_heading_rows_start_sections_until_table_end(self):
        self.assertEqual([s["name"] for s in self.deck["sections"]], ["Coag", "Pulmonary Embolism", "Tuberculosis", "Part 2"])
        self.assertEqual([c["prompt"] for c in self.secs["Coag"]["cards"]], ["PT"])
        self.assertEqual([c["prompt"] for c in self.secs["Pulmonary Embolism"]["cards"]], ["Pulmonary Embolism", "Treatment"])
        self.assertEqual([c["prompt"] for c in self.secs["Part 2"]["cards"]], ["Na"])

    def test_blank_row_skipped_silently(self):
        self.assertEqual(self.deck["cardCount"], 6)
        self.assertFalse(any("empty prompt" in w for w in self.warnings))

    def test_highlight_colour_strike_and_sup(self):
        pt = self.secs["Coag"]["cards"][0]["answerHtml"]
        self.assertEqual(pt, '<p><mark style="background-color:#ffff00">11 - 12.5</mark> seconds</p>')
        pe = self.secs["Pulmonary Embolism"]["cards"]
        self.assertEqual(pe[0]["answerHtml"], '<p><span style="color:#ff0000">Sudden dyspnea</span></p>')
        tx = pe[1]["answerHtml"]
        self.assertIn('<mark style="background-color:#ff0000;color:#ffffff">Heparin</mark>', tx)
        self.assertIn("<s> old</s>", tx)
        self.assertIn("x<sup>2</sup>", tx)

    def test_images_written_and_referenced(self):
        tx = self.secs["Pulmonary Embolism"]["cards"][1]
        self.assertIn('<img src="img/', tx["answerHtml"])
        self.assertEqual(tx["images"], 1)
        files = sorted(p.name for p in self.img_dir.iterdir())
        self.assertEqual(len(files), 2)
        self.assertTrue(any(f.endswith(".png") for f in files))
        self.assertTrue(any(f.endswith(".jpg") for f in files))

    def test_image_only_prompt_becomes_card(self):
        tb = self.secs["Tuberculosis"]["cards"]
        self.assertEqual([c["prompt"] for c in tb], ["Tuberculosis", "[Image] Sinus Bradycardia"])
        img = tb[1]
        self.assertTrue(img["imagePrompt"])
        self.assertTrue(img["id"].startswith("i"))
        self.assertIn("<img", img["promptHtml"])
        self.assertIn("Rate &lt; 60", img["answerHtml"])


UNIT_DOC = """
<html><body>
<table><tbody>
<tr><td><h1>Dosage Calculation</h1></td><td></td></tr>
<tr><td>Round to?</td><td>Tenths</td></tr>
</tbody></table>
<table><tbody>
<tr><td><h1>Unit 1</h1></td><td></td></tr>
<tr><td><h2>Heart Failure</h2></td><td></td></tr>
<tr><td>Cardiac Output</td><td>4-8 L/min</td></tr>
<tr><td><h2>EKG</h2></td><td></td></tr>
<tr><td>P wave</td><td>Atrial depolarization</td></tr>
</tbody></table>
<table><tbody>
<tr><td><h1>Unit 2</h1></td><td></td></tr>
<tr><td>PT</td><td>11-12.5 s</td></tr>
<tr><td><h2>Pulmonary Embolism</h2></td><td>Sudden dyspnea</td></tr>
<tr><td>Treatment</td><td>Heparin</td></tr>
<tr><td><h2>EKG</h2></td><td></td></tr>
<tr><td>QRS</td><td>Ventricular depolarization</td></tr>
</tbody></table>
</body></html>
"""


class UnitGroupingTests(unittest.TestCase):
    def setUp(self):
        self.deck, self.warnings = import_doc.extract(UNIT_DOC)
        self.secs = [(s.get("group"), s["name"], [c["prompt"] for c in s["cards"]]) for s in self.deck["sections"]]

    def test_two_levels_make_groups_and_sections(self):
        self.assertEqual(self.secs, [
            ("Dosage Calculation", "Dosage Calculation", ["Round to?"]),
            ("Unit 1", "Heart Failure", ["Cardiac Output"]),
            ("Unit 1", "EKG", ["P wave"]),
            ("Unit 2", "Unit 2", ["PT"]),
            ("Unit 2", "Pulmonary Embolism", ["Pulmonary Embolism", "Treatment"]),
            ("Unit 2", "EKG", ["QRS"]),
        ])

    def test_label_only_heading_rows_are_not_cards_and_not_warned(self):
        self.assertEqual(self.deck["cardCount"], 7)
        self.assertFalse(any("empty answer" in w for w in self.warnings))

    def test_heading_row_with_answer_is_still_a_card(self):
        pe = next(s for s in self.deck["sections"] if s["name"] == "Pulmonary Embolism")
        self.assertEqual(pe["cards"][0]["answerHtml"], "Sudden dyspnea")

    def test_single_level_has_no_groups(self):
        deck, _ = import_doc.extract(REAL_STYLE_DOC, section_names=["Coag"])
        self.assertTrue(all("group" not in s for s in deck["sections"]))


class MainMergeTests(unittest.TestCase):
    def test_reimport_replaces_same_doc_and_keeps_others(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "cards.json"
            a = Path(td) / "a.html"; a.write_text(SAMPLE, encoding="utf-8")
            b = Path(td) / "b.html"; b.write_text(REAL_STYLE_DOC, encoding="utf-8")
            self.assertEqual(import_doc.main([str(a), "--out", str(out), "--title", "Test A"]), 0)
            self.assertEqual(import_doc.main([str(b), "--out", str(out), "--title", "Test B"]), 0)
            bundle = json.loads(out.read_text())
            self.assertEqual([d["title"] for d in bundle["decks"]], ["Test A", "Test B"])
            self.assertEqual(bundle["cardCount"], 13 + 6)
            # re-import A: replaces, does not duplicate
            self.assertEqual(import_doc.main([str(a), "--out", str(out), "--title", "Test A2"]), 0)
            bundle = json.loads(out.read_text())
            self.assertEqual([d["title"] for d in bundle["decks"]], ["Test B", "Test A2"])
            # --fresh drops the others
            self.assertEqual(import_doc.main([str(a), "--out", str(out), "--fresh"]), 0)
            bundle = json.loads(out.read_text())
            self.assertEqual(len(bundle["decks"]), 1)
            self.assertTrue((Path(td) / "img").exists())

    def test_title_suffix_stripped(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "cards.json"
            a = Path(td) / "a.html"; a.write_text(SAMPLE, encoding="utf-8")
            import_doc.main([str(a), "--out", str(out), "--title", "NS30A Final - Flashcards"])
            self.assertEqual(json.loads(out.read_text())["decks"][0]["title"], "NS30A Final")


if __name__ == "__main__":
    unittest.main()
