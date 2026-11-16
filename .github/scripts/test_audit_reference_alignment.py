"""Regression tests for read-only reference-alignment audit."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

p = Path(__file__).with_name("audit_reference_alignment.py")
spec = importlib.util.spec_from_file_location("reference_audit", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AlignmentAuditTests(unittest.TestCase):
    def test_unanchored_duplicate_and_alias_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "people" / "json"
            folder.mkdir(parents=True)
            a = {"id":"person:Original","primary_id":"person:Original",
                 "references":["01001001","01001002"],
                 "explicit_instances":{"wlc":[["o010010010011","o010010010011"]]}}
            b = {"id":"person:Variant","primary_id":"person:Original",
                 "references":["01001003"],
                 "explicit_instances":{"wlc":[["o010010030011"]]}}
            (folder/"Original.json").write_text(json.dumps(a))
            (folder/"Variant.json").write_text(json.dumps(b))
            result=m.inspect(root)
            summary=result["summary"]
            self.assertEqual(summary["records"],2)
            self.assertEqual(summary["records_with_unanchored_refs"],1)
            self.assertEqual(summary["secondary_with_primary_alignment_gaps"],1)
            self.assertEqual(summary["records_with_repeated_explicit_tokens"],1)
            self.assertEqual(summary["secondary_refs_absent_from_primary"],1)
            self.assertEqual(summary["secondary_tokens_absent_from_primary"],1)

    def test_consistent_canonical_and_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"places"/"json"
            folder.mkdir(parents=True)
            for name in ("Main","Alt"):
                data={"id":"place:"+name,"primary_id":"place:Main",
                      "references":["01001001"],
                      "explicit_instances":{"wlc":[["o010010010011"]]}}
                (folder/(name+".json")).write_text(json.dumps(data))
            result=m.inspect(root)
            self.assertEqual(result["findings"],[])


if __name__=="__main__":
    unittest.main()
