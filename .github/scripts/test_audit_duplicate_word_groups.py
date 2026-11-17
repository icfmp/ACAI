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
