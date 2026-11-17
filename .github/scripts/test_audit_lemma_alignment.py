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
                ("places", "Compound", ["עֵין תַּפּוּחַ"], [["o4", "o5"]]),
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
                              "o3\tNEH 9:4!6\tבָּנִי\tבני\n"
                              "o4\tJOS 17:7!16\tעַיִן\tעין\n"
                              "o5\tJOS 17:7!17\tתַּפּוּחַ\tתפוח\n", encoding="utf-8")
            greek = root / "greek.tsv"
            greek.write_text("xml:id\tref\tlemma\n", encoding="utf-8")
            result = module.audit(root, hebrew, greek)
            counts = result["summary"]
            self.assertEqual(counts["records_scanned"], 5)
            self.assertEqual(counts["without_explicit_source_ids"], 1)
            self.assertEqual(counts["zero_exact_lemma_overlap"], 1)
            self.assertEqual(counts["partial_exact_lemma_overlap"], 1)
            self.assertEqual(counts["all_declared_lemmas_found"], 2)
            finding = next(x for x in result["findings"] if x["id"] == "groups:Mixed")
            self.assertEqual(finding["unmatched_declared_lemmas"], ["פֶּלֶת"])

    def test_distinct_lemma_evidence_includes_rare_eighth_word(self):
        # The old six first-word examples cannot identify a later source typo.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "keyterms" / "json").mkdir(parents=True)
            ids = [f"o{i}" for i in range(1, 9)]
            data = {"id": "keyterm:Phrase",
                    "lemmas": {"he": ["דְּבַר־יהוה"]},
                    "explicit_instances": {"wlc": [[id_] for id_ in ids]}}
            (root / "keyterms" / "json" / "Phrase.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
            hebrew = root / "wlc.tsv"
            rows = ["xml:id\\tref\\tlemma\\ttext"]
            for index, token in enumerate(ids, start=1):
                lemma = "דָּבָר" if index <= 7 else "דֶּלֶת"
                rows.append(f"{token}\\tGEN 15:1!{index}\\t{lemma}\\tword{index}")
            hebrew.write_text("\\n".join(rows) + "\\n", encoding="utf-8")
            greek = root / "greek.tsv"
            greek.write_text("xml:id\\tref\\tlemma\\n", encoding="utf-8")
            result = module.audit(root, hebrew, greek)
            self.assertEqual(result["summary"]["zero_exact_lemma_overlap"], 1)
            item = result["findings"][0]
            self.assertEqual(len(item["source_examples"]), 6)
            self.assertEqual(len(item["source_lemma_examples"]), 2)
            rare = next(x for x in item["source_lemma_examples"]
                        if x["lemma"] == "דֶּלֶת")
            self.assertEqual(rare["word_id"], "o8")
            self.assertEqual(rare["ref"], "GEN 15:1!8")
            self.assertEqual(rare["text"], "word8")

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
