"""Regression tests for exact-group duplicate triage."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

p=Path(__file__).with_name("audit_duplicate_word_groups.py")
spec=importlib.util.spec_from_file_location("duplicate_group_audit",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class GroupTests(unittest.TestCase):
    def test_identical_and_distinct_groups_are_not_conflated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"fauna"/"json"
            folder.mkdir(parents=True)
            data={"id":"fauna:X","primary_id":"fauna:X",
                  "explicit_instances":{"wlc":[["o01001001001"],["o01001001001"],
                                                 ["o01001001001","o01001001002"]]}}
            (folder/"X.json").write_text(json.dumps(data))
            result=m.inspect(root)
            self.assertEqual(result["summary"]["exact_duplicate_groups"],1)
            self.assertEqual(result["summary"]["word_ids_in_different_groups"],1)
            self.assertEqual(result["findings"][0]["id"],"fauna:X")
    def test_indirect_referent_groups_are_reported_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"people"/"json"
            folder.mkdir(parents=True)
            data={"id":"person:X","primary_id":"person:X",
                  "explicit_instances":{"wlc":[["o010010010011"]]},
                  "pronominal_referents":{"wlc":[["o010010010021"],
                                                  ["o010010010021"]]},
                  "subject_referents":{"wlc":[["o010010010031"],
                                               ["o010010010031"],
                                               ["o010010010031","o010010010041"]]}}
            (folder/"X.json").write_text(json.dumps(data))
            result=m.inspect(root)
            self.assertEqual(result["summary"]["records_with_any_repeat"],1)
            self.assertEqual(result["summary"]["occurrence_fields_with_any_repeat"],2)
            self.assertEqual(result["summary"]["exact_duplicate_groups"],2)
            self.assertEqual(result["summary"]["word_ids_in_different_groups"],1)
            self.assertEqual({x["occurrence_field"] for x in result["findings"]},
                             {"pronominal_referents","subject_referents"})
            self.assertTrue(all(x["corpus"]=="wlc" for x in result["findings"]))

    def test_parallel_source_subject_and_frame_links_are_candidates_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "people" / "json"
            p.mkdir(parents=True)
            for name, token in (("A", "o160090040062"), ("B", "o160090040111")):
                (p / (name + ".json")).write_text(json.dumps({
                    "id": "person:" + name, "primary_id": "person:" + name,
                    "explicit_instances": {"wlc": [[token]]},
                    "subject_referents": {"wlc": [
                        ["o160090040132"], ["o160090040132"]]},
                }), encoding="utf-8")
            (p / "C.json").write_text(json.dumps({
                "id": "person:C", "primary_id": "person:C",
                "explicit_instances": {"wlc": [["o160090040072"]]},
                "subject_referents": {"wlc": [
                    ["o160090040133"], ["o160090040133"]]},
            }), encoding="utf-8")
            hebrew = root / "wlc.tsv"
            hebrew.write_text(
                "xml:id\tref\tsubjref\tframe\n"
                "o160090040132\tNEH 9:4!13\t"
                "160090040062 160090040111\t"
                "A0:160090040062;160090040111;\n",
                encoding="utf-8",
            )
            greek = root / "sblgnt.tsv"
            greek.write_text("xml:id\tref\tsubjref\tframe\n", encoding="utf-8")
            results = m.inspect(root, hebrew=hebrew, greek=greek)
            self.assertEqual(results["summary"]["exact_duplicate_groups"], 3)
            self.assertEqual(results["summary"]["subject_repeated_groups_examined"], 3)
            self.assertEqual(results["summary"]["parallel_source_annotation_candidates"], 2)
            self.assertEqual(results["summary"]["subject_groups_not_explained_by_parallel_fields"], 1)
            self.assertEqual(
                {r["id"]: r["source_provenance"]["parallel_subjref_frame_candidates"]
                 for r in results["findings"]},
                {"person:A": 1, "person:B": 1, "person:C": 0},
            )
            # No source evidence authorizes changing any original record.
            self.assertEqual(json.loads((p / "A.json").read_text())
                             ["subject_referents"]["wlc"],
                             [["o160090040132"], ["o160090040132"]])

    def test_pronominal_referent_links_are_not_mistaken_for_dedup_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "people" / "json"
            folder.mkdir(parents=True)
            records = (
                ("HebrewMatched", "wlc", "o010010010011", "o010010010021"),
                ("HebrewUnmatched", "wlc", "o010010010031", "o010010010021"),
                ("GreekMatched", "SBLGNT", "n40001001001", "n40001001002"),
            )
            for name, corpus, explicit, pronoun in records:
                (folder / (name + ".json")).write_text(json.dumps({
                    "id": "person:" + name,
                    "primary_id": "person:" + name,
                    "explicit_instances": {corpus: [[explicit]]},
                    "pronominal_referents": {corpus: [[pronoun], [pronoun]]},
                }), encoding="utf-8")
            hebrew = root / "wlc.tsv"
            hebrew.write_text(
                "xml:id\tref\tsubjref\tframe\tparticipantref\n"
                "o010010010021\tGEN 1:1!2\t\t\t010010010011\n",
                encoding="utf-8",
            )
            greek = root / "sblgnt.tsv"
            greek.write_text(
                "xml:id\tref\tsubjref\tframe\treferent\n"
                "n40001001002\tMAT 1:1!2\t\t\tn40001001001\n",
                encoding="utf-8",
            )
            result = m.inspect(root, hebrew=hebrew, greek=greek)
            self.assertEqual(result["summary"]["pronominal_repeated_groups_examined"], 3)
            self.assertEqual(result["summary"]["pronominal_source_referent_linked"], 2)
            self.assertEqual(result["summary"]["pronominal_source_referent_unconfirmed"], 1)
            match = {finding["id"]: finding["source_provenance"]
                     for finding in result["findings"]}
            self.assertEqual(match["person:HebrewMatched"]["source_referent_linked_groups"], 1)
            self.assertEqual(match["person:HebrewUnmatched"]["source_referent_linked_groups"], 0)
            self.assertEqual(match["person:GreekMatched"]["source_referent_linked_groups"], 1)
            for name, corpus, _, pronoun in records:
                # Read-only: repeated groups still exist in the same order.
                record = json.loads((folder / (name + ".json")).read_text())
                self.assertEqual(record["pronominal_referents"][corpus],
                                 [[pronoun], [pronoun]])

    def test_primary_only_pronoun_matches_are_not_treated_as_own_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "keyterms" / "json"
            folder.mkdir(parents=True)
            entries = (
                ("Parent", "keyterm:Parent", "n40001001001", []),
                ("Secondary", "keyterm:Parent", "n40001001003",
                 [["n40001001002"], ["n40001001002"]]),
            )
            for name, primary, explicit, pronouns in entries:
                (folder / (name + ".json")).write_text(json.dumps({
                    "id": "keyterm:" + name,
                    "primary_id": primary,
                    "explicit_instances": {"SBLGNT": [[explicit]]},
                    "pronominal_referents": {"SBLGNT": pronouns},
                }), encoding="utf-8")
            hebrew = root / "wlc.tsv"
            hebrew.write_text("xml:id\tref\tsubjref\tframe\n", encoding="utf-8")
            greek = root / "sblgnt.tsv"
            greek.write_text(
                "xml:id\tref\tsubjref\tframe\treferent\n"
                "n40001001002\tMAT 1:1!2\t\t\tn40001001001\n",
                encoding="utf-8",
            )
            result = m.inspect(root, hebrew=hebrew, greek=greek)
            finding = result["findings"][0]
            self.assertEqual(finding["id"], "keyterm:Secondary")
            provenance = finding["source_provenance"]
            self.assertEqual(provenance["source_referent_linked_groups"], 0)
            self.assertEqual(provenance["source_referent_primary_only_groups"], 1)
            self.assertEqual(provenance["source_referent_unconfirmed_groups"], 0)
            self.assertEqual(provenance["primary_only_examples"][0]["primary_id"],
                             "keyterm:Parent")
            self.assertEqual(result["summary"]["pronominal_primary_only_source_linked"], 1)
            # Parent-only source support is not a declaration of synonymy
            # and cannot authorize changing either record's associations.
            record = json.loads((folder / "Secondary.json").read_text())
            self.assertEqual(record["pronominal_referents"]["SBLGNT"],
                             [["n40001001002"], ["n40001001002"]])

    def test_subject_source_evidence_classes_are_exclusive(self):
        """Read-only triage of own, parent and source-missing pointer shapes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "keyterms" / "json"
            folder.mkdir(parents=True)
            own_a, own_b, parent = ("o010010010011", "o010010010021",
                                    "o010010010031")
            rows = [
                ("o010010010041", own_a, own_a, "own_parallel"),
                ("o010010010051", own_a, own_b, "own_split_fields"),
                ("o010010010061", own_a, "", "own_subjref_only"),
                ("o010010010071", "", own_a, "own_frame_only"),
                ("o010010010081", parent, parent, "primary_parallel"),
                ("o010010010091", parent, own_a if False else own_b, "own_frame_only"),
                ("o010010010101", parent, "", "primary_subjref_only"),
                ("o010010010111", "", parent, "primary_frame_only"),
                ("o010010010121", "010010010131", "", "source_without_entity_link"),
            ]
            # The split-field priority is deliberate: matching the
            # secondary's explicit token outranks parent-only evidence.
            rows[5] = ("o010010010091", parent, "o010010010141",
                       "primary_subjref_only")
            (folder / "Parent.json").write_text(json.dumps({
                "id": "keyterm:Parent", "primary_id": "keyterm:Parent",
                "explicit_instances": {"wlc": [[parent]]},
            }))
            groups = [[token] for token, *_ in rows] + [["o010010010151"]]
            (folder / "Secondary.json").write_text(json.dumps({
                "id": "keyterm:Secondary", "primary_id": "keyterm:Parent",
                "explicit_instances": {"wlc": [[own_a], [own_b]]},
                "subject_referents": {"wlc": [
                    entry for group in groups for entry in (group, group)]},
            }))
            hebrew = root / "wlc.tsv"
            hebrew.write_text(
                "xml:id\tref\tsubjref\tframe\n" +
                "".join(f"{tok}\tGEN 1:1!4\t{sub.replace('o', '')}\t"
                        f"{('A0:' + frame.replace('o', '') + ';') if frame else ''}\n"
                        for tok, sub, frame, _ in rows),
                encoding="utf-8",
            )
            greek = root / "sblgnt.tsv"
            greek.write_text("xml:id\tref\tsubjref\tframe\n")
            result = m.inspect(root, hebrew=hebrew, greek=greek)
            finding = next(x for x in result["findings"]
                           if x["id"] == "keyterm:Secondary")
            classes = finding["source_provenance"]["subject_evidence_classes"]
            self.assertEqual(sum(classes.values()), 10)
            self.assertEqual(classes["own_parallel"], 1)
            self.assertEqual(classes["own_split_fields"], 1)
            self.assertEqual(classes["own_subjref_only"], 1)
            self.assertEqual(classes["own_frame_only"], 1)
            self.assertEqual(classes["primary_parallel"], 1)
            self.assertEqual(classes["primary_subjref_only"], 2)
            self.assertEqual(classes["primary_frame_only"], 1)
            self.assertEqual(classes["source_without_entity_link"], 1)
            self.assertEqual(classes["source_word_missing"], 1)
            self.assertEqual(result["summary"]["subject_repeated_groups_examined"], 10)
            self.assertEqual(result["summary"]["parallel_source_annotation_candidates"], 1)
            record = json.loads((folder / "Secondary.json").read_text())
            self.assertEqual(record["subject_referents"]["wlc"],
                             [entry for group in groups
                              for entry in (group, group)])

    def test_macula_referent_parser_never_matches_partial_ids(self):
        self.assertEqual(
            m._source_ids("A0:160090040062; A1:160090040111;", "wlc"),
            {"o160090040062", "o160090040111"},
        )
        self.assertEqual(
            m._source_ids("16009004006", "wlc"), set(),
        )
        self.assertEqual(
            m._source_ids("n44010032007", "SBLGNT"),
            {"n44010032007"},
        )

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"people"/"json"
            folder.mkdir(parents=True)
            data={"id":"person:X","primary_id":"person:X",
                  "explicit_instances":{"wlc":[["o01001001001"],["o01001001002"]]}}
            (folder/"X.json").write_text(json.dumps(data))
            self.assertEqual(m.inspect(root)["findings"],[])
if __name__=="__main__":
    unittest.main()
