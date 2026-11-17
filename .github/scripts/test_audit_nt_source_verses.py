"""Tests for the NT verse-source compatibility scan."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

src=Path(__file__).with_name("audit_nt_source_verses.py")
spec=importlib.util.spec_from_file_location("nt_verse_audit",src)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

epistle_path=Path(__file__).with_name("audit_epistle_endings.py")
epistle_spec=importlib.util.spec_from_file_location("epistle_endings", epistle_path)
epistle_module=importlib.util.module_from_spec(epistle_spec)
epistle_spec.loader.exec_module(epistle_module)


class VerseCompatibilityTests(unittest.TestCase):
    def test_epistle_endings_distinguish_present_last_verse_from_source_absence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "people" / "json"
            folder.mkdir(parents=True)
            (folder / "Person.json").write_text(json.dumps({
                "id": "person:Person", "primary_id": "person:Person",
                "references": [
                    "45016023", "45016025", "45016027",
                    "47013014", "45015020", "45016027", "bad",
                ],
                "explicit_instances": {
                    "SBLGNT": [["n45016023001"], ["n47013014001"]]
                },
            }), encoding="utf-8")
            (folder / "Second.json").write_text(json.dumps({
                "id": "person:Second", "primary_id": "person:Second",
                "references": ["46016024"],
            }), encoding="utf-8")
            source = root / "source.tsv"
            source.write_text(
                "xml:id\\tref\\n"
                "n45016023001\\tROM 16:23!1\\n"
                "n47013013001\\t2CO 13:13!1\\n"
                "n46016024001\\t1CO 16:24!1\\n",
                encoding="utf-8")
            report = epistle_module.audit(root, source)
            self.assertEqual(report["records_referencing_any_final_verse"], 2)
            self.assertEqual(report["unanchored_record_count"], 1)
            self.assertEqual(report["findings"][0]["id"], "person:Second")
            cases = report["absent_source_final_chapter_references"]
            self.assertEqual({x["verse_id"] for x in cases},
                             {"45016025", "45016027", "47013014"})
            self.assertEqual(len(cases), 3)  # repeated ACAI ref counts once
            self.assertEqual(report["absent_source_final_chapter_record_count"], 1)
            self.assertTrue(next(
                x for x in cases if x["verse_id"] == "47013014"
            )["acai_record_has_word_or_referent_anchor"])
            self.assertFalse(next(
                x for x in cases if x["verse_id"] == "45016027"
            )["acai_record_has_word_or_referent_anchor"])
            self.assertEqual({
                x["pinned_last_verse"] for x in cases
            }, {"45016023", "47013013"})

    def test_source_absence_is_counted_not_corrected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/"people"/"json"
            folder.mkdir(parents=True)
            content={"id":"person:Test","primary_id":"person:Test",
                     "references":["45016024","45016027","01001001","bad"]}
            (folder/"Test.json").write_text(json.dumps(content),encoding="utf-8")
            tsv=root/"source.tsv"
            tsv.write_text("xml:id\tref\n"+"n45016024001\tROM 16:24!1\n")
            result=module.inspect(root,tsv)
            self.assertEqual(result["summary"]["record_reference_entries"],2)
            self.assertEqual(result["summary"]["record_reference_entries_absent_from_source"],1)
            self.assertEqual(result["summary"]["invalid_reference_format"],1)
            self.assertEqual(result["verses_absent_from_pinned_source"][0]["verse_id"],"45016027")
    def test_old_testament_verses_source_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/"people"/"json"
            folder.mkdir(parents=True)
            (folder/"Test.json").write_text(json.dumps({
                "id":"person:Test","primary_id":"person:Test",
                "references":["01001001","01001002","44001001"]}))
            tsv=root/"source.tsv"
            tsv.write_text("xml:id\tref\n"+"o01001001001\tGEN 1:1!1\n")
            result=module.inspect(root,tsv,corpus="ot")
            self.assertEqual(result["summary"]["record_reference_entries"],2)
            self.assertEqual(result["summary"]["record_reference_entries_absent_from_source"],1)
            self.assertEqual(result["verses_absent_from_pinned_source"][0]["verse_id"],"01001002")

    def test_names_and_missing_canonical_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/"places"/"json"
            folder.mkdir(parents=True)
            for name,primary in (("A","A"),("B","A")):
                (folder/(name+".json")).write_text(json.dumps({
                    "id":"place:"+name,"primary_id":"place:"+primary,
                    "references":["43001028"]}))
            source=root/"source.tsv"
            source.write_text("xml:id\tref\nn44001001001\tACT 1:1!1\n")
            result=module.inspect(root,source)
            case=result["verses_absent_from_pinned_source"][0]
            self.assertEqual(case["number_of_entity_references"],2)
            self.assertEqual(case["canonical_references"],1)
            self.assertEqual(case["categories"]["places"],2)

if __name__=="__main__":
    unittest.main()
