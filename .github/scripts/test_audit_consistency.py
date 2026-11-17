"""Focused regression tests for the global read-only scanner."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).with_name("audit_consistency.py")
spec = importlib.util.spec_from_file_location("audit_consistency", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GlobalAuditTests(unittest.TestCase):
    def test_exact_lemma_duplicates_are_reviewed_without_conflating_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "flora" / "json"
            folder.mkdir(parents=True)
            entry = {
                "id": "flora:Agarwood", "primary_id": "flora:Agarwood",
                "lemmas": {
                    "he": ["אָהָל", "אֲהָלֹות", "אֲהָלֹות"],
                    "el": ["ἀγάπη", "ἀγάπη", "αγάπη"],
                },
            }
            filename = folder / "Agarwood.json"
            filename.write_text(json.dumps(entry, ensure_ascii=False),
                                encoding="utf-8")
            scanned = module.scan(root)
            findings = [item for item in scanned["findings"]
                        if item["rule"] == "duplicate_exact_lemma"]
            self.assertEqual(len(findings), 2)
            self.assertTrue(all(item["severity"] == "review" for item in findings))
            self.assertEqual({item["location"].split("#/")[1] for item in findings},
                             {"lemmas/he/2", "lemmas/el/1"})
            self.assertEqual(scanned["summary"]["duplicate_exact_lemma_entries"], 2)
            self.assertEqual(scanned["summary"]["records_with_duplicate_exact_lemmas"], 1)

            # Original and alternate source spellings remain distinct; an
            # exact comparison must not silently normalize/merge them.
            entry["lemmas"]["he"] = ["אָהָל", "אֲהָלֹות"]
            entry["lemmas"]["el"] = ["ἀγάπη", "αγάπη"]
            filename.write_text(json.dumps(entry, ensure_ascii=False),
                                encoding="utf-8")
            scanned = module.scan(root)
            self.assertFalse(any(item["rule"] == "duplicate_exact_lemma"
                                 for item in scanned["findings"]))
            self.assertEqual(json.loads(filename.read_text(encoding="utf-8")),
                             entry)

    def test_cross_person_duplicate_and_missing_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            p.mkdir(parents=True)
            a = {"id": "person:A", "primary_id": "person:A",
                 "references": ["42024010"],
                 "explicit_instances": {"SBLGNT": [["n42024010005"]]}}
            b = {"id": "person:B", "primary_id": "person:B",
                 "references": ["42024011"],
                 "explicit_instances": {"SBLGNT": [["n42024010005"]]}}
            (p / "A.json").write_text(json.dumps(a))
            (p / "B.json").write_text(json.dumps(b))
            result = module.scan(root)
            rules = {f["rule"] for f in result["findings"]}
            self.assertIn("cross_entity_explicit_token", rules)
            self.assertIn("explicit_verse_not_listed", rules)
            self.assertEqual(result["summary"]["canonical_entities"], 2)

    def test_duplicate_verse_is_invalid_even_with_multiple_word_occurrences(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            p.mkdir(parents=True)
            record = {
                "id": "person:A", "primary_id": "person:A",
                "references": ["01001001", "01001001"],
                "explicit_instances": {
                    "wlc": [["o010010010011"], ["o010010010021"]]
                },
            }
            path = p / "A.json"
            path.write_text(json.dumps(record))
            findings = [f for f in module.scan(root)["findings"]
                        if f["rule"] == "duplicate_reference"]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["severity"], "error")
            self.assertTrue(findings[0]["location"].endswith("#/references/1"))

            # Two legitimate source-word occurrences can share one verse ID.
            record["references"] = ["01001001"]
            path.write_text(json.dumps(record))
            findings = module.scan(root)["findings"]
            self.assertFalse(any(f["rule"] == "duplicate_reference"
                                 for f in findings))

    def test_secondary_name_does_not_create_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            p.mkdir(parents=True)
            for name in ("A", "Alias"):
                (p / (name + ".json")).write_text(json.dumps(
                    {"id": "person:" + name, "primary_id": "person:A",
                     "references": ["01001001"],
                     "explicit_instances": {"WLC": [["o010010010011"]]}}))
            result = module.scan(root)
            self.assertEqual(result["summary"]["cross_entity_token_collisions"], 0)

    def test_parent_sibling_conflict_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            p.mkdir(parents=True)
            for name, fields in (
                ("Parent", {}),
                ("Sibling", {}),
                ("Conflicted", {"father": "person:Parent",
                                "siblings": ["person:Parent"]}),
                ("Consistent", {"father": "person:Parent",
                                "siblings": ["person:Sibling"]}),
            ):
                (p / (name + ".json")).write_text(json.dumps(
                    {"id": "person:" + name,
                     "primary_id": "person:" + name, **fields}))
            issues = [x for x in module.scan(root)["findings"]
                      if x["rule"] == "parent_sibling_identity_conflict"]
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["entity"], "person:Conflicted")
            self.assertEqual(issues[0]["severity"], "review")

    def test_markdown_and_source_counts_are_reviewed_without_overcounting_word_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            md = root / "people" / "md"
            p.mkdir(parents=True)
            md.mkdir(parents=True)
            (p / "A.json").write_text(json.dumps({
                "id": "person:A", "primary_id": "person:A",
                "references": ["42001001"],
                "explicit_instances": {
                    "SBLGNT": [["n42001001001", "n42001001002"]]
                },
            }))
            display = md / "A.md"
            display.write_text(
                "### NT Instances (BSB)\n\n"
                "* a person (LUK 1:1; LUK 1:1)\n\n"
                "### References (Whole Bible)\n\n"
                "* LUK 1:1; LUK 1:1\n"
            )
            findings = module.scan(root)["findings"]
            kinds = {v["rule"] for v in findings}
            self.assertIn("markdown_instance_group_count_mismatch", kinds)
            self.assertIn("markdown_reference_count_mismatch", kinds)
            self.assertTrue(all(v["severity"] == "review" for v in findings))

            # Two original word parts in *one* group mean one occurrence.
            display.write_text(
                "### NT Instances (BSB)\n\n"
                "* a person (LUK 1:1)\n\n"
                "### References (Whole Bible)\n\n"
                "* LUK 1:1\n"
            )
            findings = module.scan(root)["findings"]
            self.assertNotIn("markdown_instance_group_count_mismatch",
                             {v["rule"] for v in findings})
            self.assertNotIn("markdown_reference_count_mismatch",
                             {v["rule"] for v in findings})

    def test_same_counts_do_not_hide_wrong_displayed_verses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            md = root / "people" / "md"
            p.mkdir(parents=True)
            md.mkdir(parents=True)
            record = {
                "id": "person:A", "primary_id": "person:A",
                "references": ["42001001", "42001002"],
                "explicit_instances": {"SBLGNT": [
                    ["n42001001005"], ["n42001002005"]
                ]},
            }
            (p / "A.json").write_text(json.dumps(record))
            page = md / "A.md"
            page.write_text(
                "### NT Instances (BSB)\n\n"
                "* named person (LUK 1:1; LUK 1:3)\n\n"
                "### References (Whole Bible)\n\n"
                "* LUK 1:1; LUK 1:3\n"
            )
            findings = module.scan(root)["findings"]
            rules = {f["rule"] for f in findings}
            self.assertIn("markdown_instance_verse_mismatch", rules)
            self.assertIn("markdown_reference_verse_mismatch", rules)
            self.assertNotIn("markdown_instance_group_count_mismatch", rules)
            self.assertNotIn("markdown_reference_count_mismatch", rules)
            self.assertTrue(all(f["severity"] == "review" for f in findings))

            page.write_text(
                "### NT Instances (BSB)\n\n"
                "* named person (LUK 1:1; LUK 1:2)\n\n"
                "### References (Whole Bible)\n\n"
                "* LUK 1:1; LUK 1:2\n"
            )
            rules = {f["rule"] for f in module.scan(root)["findings"]}
            self.assertNotIn("markdown_instance_verse_mismatch", rules)
            self.assertNotIn("markdown_reference_verse_mismatch", rules)

    def test_numbered_bible_books_are_parsed_without_guessing(self):
        counts, invalid = module._markdown_verse_counts(
            "### OT Instances (BSB)\n\n"
            "* place (1KI 4:13; 2CH 23:1)\n\n"
            "### NT Instances (BSB)\n\n"
            "* person (1CO 12:3)\n"
        )
        self.assertEqual(counts["OT"]["11004013"], 1)
        self.assertEqual(counts["OT"]["14023001"], 1)
        self.assertEqual(counts["NT"]["46012003"], 1)
        self.assertFalse(invalid)

    def test_family_infobox_keeps_person_and_group_ids_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "people" / "json"
            pages = root / "people" / "md"
            directory.mkdir(parents=True)
            pages.mkdir(parents=True)
            (directory / "Parent.json").write_text(json.dumps({
                "id": "person:Parent", "primary_id": "person:Parent",
                "offspring": ["person:Child", "group:Kittim",
                              "Ludim@Gen.10.13-1Ch"]
            }))
            (directory / "Child.json").write_text(json.dumps({
                "id": "person:Child", "primary_id": "person:Child"
            }))
            page = pages / "Parent.md"
            page.write_text(
                "**Familial Relationships of Parent**\n\n"
                "* Offspring: [Child](Child.md), group:Kittim (Group), "
                "Ludim@Gen.10.13-1Ch (Group)\n\n"
                "**OT Distribution of References**\n"
            )
            def mismatch():
                return [x for x in module.scan(root)["findings"]
                        if x["rule"] == "markdown_family_metadata_mismatch"
                        and x["entity"] == "person:Parent"]
            self.assertFalse(mismatch())
            page.write_text(page.read_text().replace(
                "group:Kittim (Group)", "group:Dodanim (Group)"
            ))
            findings = mismatch()
            self.assertEqual(len(findings), 1)
            self.assertTrue(findings[0]["location"].endswith("#/offspring"))

    def test_stale_family_infobox_is_reviewed_without_rewriting_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            md = root / "people" / "md"
            p.mkdir(parents=True)
            md.mkdir(parents=True)
            for name in ("Parent", "Child"):
                record = {"id": "person:" + name, "primary_id": "person:" + name}
                if name == "Child":
                    record.update(gender="female", father="person:Parent")
                (p / (name + ".json")).write_text(json.dumps(record))
            page = md / "Child.md"
            page.write_text(
                "# Child\nA biographical paragraph that must not be rewritten.\n\n"
                "**Familial Relationships of Child**\n\n"
                "* Gender: male\n* Father: [Wrong](Wrong.md)\n\n"
                "**Key References for Child**:\n"
            )
            issues = [x for x in module.scan(root)["findings"]
                      if x["rule"] == "markdown_family_metadata_mismatch"]
            self.assertEqual({x["location"].split("#/")[1] for x in issues},
                             {"gender", "father"})
            self.assertTrue(all(x["severity"] == "review" for x in issues))
            page.write_text(
                "# Child\nA biographical paragraph that must not be rewritten.\n\n"
                "**Familial Relationships of Child**\n\n"
                "* Gender: female\n* Father: [Parent](Parent.md)\n\n"
                "**Key References for Child**:\n"
            )
            self.assertNotIn(
                "markdown_family_metadata_mismatch",
                {x["rule"] for x in module.scan(root)["findings"]},
            )

    def test_conflicting_flags_and_missing_relation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "places" / "json"
            p.mkdir(parents=True)
            (p / "A.json").write_text(json.dumps(
                {"id": "place:A", "primary_id": "place:A",
                 "mentioned_in_bible": True, "non_biblical": True,
                 "referred_to_as": ["place:Missing"]}))
            findings = module.scan(root)["findings"]
            rules = {x["rule"] for x in findings}
            self.assertIn("contradictory_biblical_flags", rules)
            self.assertIn("dangling_relationship", rules)
            self.assertEqual(
                next(x["severity"] for x in findings
                     if x["rule"] == "contradictory_biblical_flags"),
                "error",
            )
            self.assertEqual(
                next(x["severity"] for x in findings
                     if x["rule"] == "dangling_relationship"),
                "review",
            )


if __name__ == "__main__":
    unittest.main()
