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
