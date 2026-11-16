"""Triage exact-word collisions by canonical category and repeated entity pairs.

Input comes from read-only audit_consistency.py; this script never changes records.
Unambiguous proper-name identities still require original-language editorial review.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=Path("audit-results.json"))
    p.add_argument("--top", type=int, default=40)
    args = p.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    rows = [x for x in data["findings"] if x["rule"] == "cross_entity_explicit_token"]
    categories = collections.Counter()
    pair_counts = collections.Counter()
    same_type = []
    for x in rows:
        entities = x["entity"].split("|")
        kinds = tuple(sorted({s.split(":", 1)[0] for s in entities}))
        categories["+".join(kinds)] += 1
        if len(kinds) == 1 and kinds[0] in {"person", "place", "deity"}:
            same_type.append(x)
            for i, a in enumerate(entities):
                for b in entities[i+1:]:
                    pair_counts[(a, b)] += 1
    print("TRIAGE_COLLISION_TOTALS " + json.dumps(dict(categories.most_common()), sort_keys=True))
    print("TRIAGE_SAME_IDENTITY_TYPE_COUNT " + str(len(same_type)))
    for (a, b), n in pair_counts.most_common(args.top):
        print("TRIAGE_IDENTITY_PAIR " + json.dumps({"a": a, "b": b, "shared_exact_token_ids": n}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
