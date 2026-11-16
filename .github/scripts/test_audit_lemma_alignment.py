"""Regression tests for read-only lexical lemma triage."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

path = Path(__file__).with_name("audit_lemma_alignment.py")
spec = importlib.util.spec_from_file_location("acai_lemma_audit", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LemmaAuditTests(unittest.TestCase):
    def test_unicode_normalization_is_comparison_only(self):
        self.assertEqual(module.normalize("בָּנִי"), module.normalize("בָנִי"))
        self.assertEqual(module.normalize("Ἰάκωβος"), module.normalize("ιακωβοσ"))
        self.assertEqual(module.normalize("עֵין־דֹּר"), module.normalize("עין דר"))

    def test_mismatched_partial_matching_and_unanchored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ("places", "groups", "people"):
                (root / folder / "json").mkdir(parents=True)
            items = (
                ("places", "Wrong", ["עֵין־דֹּר"], [["o1"]]),
                ("groups", "Mixed", ["פֶּלֶת", "פְּלִשְׁתִּי"], [["o2"]]),
                ("groups", "Correct", ["בָּנִי"], [["o3"]]),
                ("people", "Unanchored", ["יעקב"], []),
            )
            for folder, name, lemmas, groups in items:
                record = {"id": folder + ":" + name,
                          "lemmas": {"he": lemmas},
                          "explicit_instances": {"wlc": groups}}
                (root / folder / "json" / (name + ".json")).write_text(
                    json.dumps(record, ensure_ascii=False), encoding="utf-8")
            hebrew = root / "wlc.tsv"
            hebrew.write_text("xml:id\tref\tlemma\ttext\n"
                              "o1\tJOS 15:34!1\tעֵין גַּנִּים\tעֵין־גנים\n"
                              "o2\tGEN 10:14!8\tפְּלִשְׁתִּי\tפלשתים\n"
                              "o3\tNEH 9:4!6\tבָּנִי\tבני\n", encoding="utf-8")
            greek = root / "greek.tsv"
            greek.write_text("xml:id\tref\tlemma\n", encoding="utf-8")
            result = module.audit(root, hebrew, greek)
            counts = result["summary"]
            self.assertEqual(counts["records_scanned"], 4)
            self.assertEqual(counts["without_explicit_source_ids"], 1)
            self.assertEqual(counts["zero_exact_lemma_overlap"], 1)
            self.assertEqual(counts["partial_exact_lemma_overlap"], 1)
            self.assertEqual(counts["all_declared_lemmas_found"], 1)
            finding = next(x for x in result["findings"] if x["id"] == "groups:Mixed")
            self.assertEqual(finding["unmatched_declared_lemmas"], ["פֶּלֶת"])

    def test_missing_source_token_does_not_create_false_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "people" / "json").mkdir(parents=True)
            data = {"id": "person:A", "lemmas": {"el": ["Ἰάκωβος"]},
                    "explicit_instances": {"SBLGNT": [["n1"]]}}
            (root / "people" / "json" / "A.json").write_text(json.dumps(data))
            (root / "he.tsv").write_text("xml:id\tref\tlemma\n")
            (root / "gr.tsv").write_text("xml:id\tref\tlemma\nn2\tACT 1:13!1\tἸάκωβος\n")
            result = module.audit(root, root / "he.tsv", root / "gr.tsv")
            self.assertEqual(result["summary"]["without_matching_source_ids"], 1)
            self.assertEqual(result["findings"], [])


if __name__ == "__main__":
    unittest.main()
