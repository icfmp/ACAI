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
