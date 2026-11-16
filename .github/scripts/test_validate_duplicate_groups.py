"""Regression coverage for the generic repeated-source-word-group invariant."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("validate.py")
SPEC = importlib.util.spec_from_file_location("acai_validation", SOURCE)
assert SPEC is not None and SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


class ExactWordGroupsTests(unittest.TestCase):
    def test_repeated_exact_group_fails(self):
        record = {"_path": "people/json/Test.json",
                  "explicit_instances": {"wlc": [["o01001001001", "o01001001002"],
                                                  ["o01001001001", "o01001001002"]]}}
        errors = []
        VALIDATE.lint_repeated_explicit_groups({"person:Test": record}, errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("repeats group 1", errors[0])

    def test_same_word_in_distinct_multiword_group_is_not_a_duplicate(self):
        record = {"_path": "people/json/Test.json",
                  "explicit_instances": {"wlc": [["o01001001001"],
                                                  ["o01001001001", "o01001001002"]]}}
        errors = []
        VALIDATE.lint_repeated_explicit_groups({"person:Test": record}, errors)
        self.assertEqual(errors, [])

    def test_different_corpora_and_entities_are_independent(self):
        one = {"_path": "people/json/A.json",
               "explicit_instances": {"wlc": [["o01001001001"]],
                                      "SBLGNT": [["o01001001001"]]}}
        two = {"_path": "people/json/B.json",
               "explicit_instances": {"wlc": [["o01001001001"]]}}
        errors = []
        VALIDATE.lint_repeated_explicit_groups({"person:A": one, "person:B": two}, errors)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
