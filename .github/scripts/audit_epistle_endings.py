"""Triage references to the last canonical verse of NT letters.

Derives each last verse directly from pinned Macula SBLGNT word IDs
(book IDs 45-65), not from a hardcoded English Bible verse table. A reference
with no source-word or referent anchor is a review candidate, not proof of a
later epistle subscription. All operations are read-only.
"""
from __future__ import annotations
import argparse
import collections
import csv
import json
from pathlib import Path

CATEGORIES = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")
BOOK_MIN, BOOK_MAX = 45, 65

def audit(root: Path, source: Path) -> dict:
    final = {}
    with source.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter="\t"):
            tok = row.get("xml:id", "")
            if len(tok) < 10 or not tok.startswith("n") or not tok[1:9].isdigit():
                continue
            book = int(tok[1:3])
            if BOOK_MIN <= book <= BOOK_MAX:
                verse = tok[1:9]
                final[book] = max(final.get(book, verse), verse)
    finals = set(final.values())
    findings = []
    all_records_at_end = 0
    for cat in CATEGORIES:
        for file in sorted((root/cat/"json").glob("*.json")):
            item = json.loads(file.read_text(encoding="utf-8"))
            end_refs = sorted(set(item.get("references", [])).intersection(finals))
            if not end_refs:
                continue
            all_records_at_end += 1
            linked = set()
            for field in ("explicit_instances","pronominal_referents","subject_referents"):
                for groups in item.get(field, {}).values():
                    for group in groups:
                        for token in group:
                            if isinstance(token, str) and len(token) >= 9:
                                linked.add(token[1:9])
            missing = [ref for ref in end_refs if ref not in linked]
            if missing:
                desc = item.get("localizations", {}).get("eng", {}).get("descriptions", [])
                findings.append({
                    "id": item["id"], "primary_id": item.get("primary_id"),
                    "unanchored_end_verses": missing,
                    "description": " | ".join(x.get("description","") for x in desc if isinstance(x,dict))[:240],
                    "category":cat,
                })
    return {
        "source_defined_final_verses": dict(sorted(final.items())),
        "records_referencing_any_final_verse": all_records_at_end,
        "unanchored_record_count": len(findings),
        "unanchored_reference_count": sum(len(x["unanchored_end_verses"]) for x in findings),
        "findings": findings,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root", type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--greek",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("epistle-ending-review.json"))
    a=p.parse_args()
    r=audit(a.root,a.greek)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EPISTLE_ENDINGS_AUDIT_SUMMARY "+json.dumps({
        "epistle_book_count":len(r["source_defined_final_verses"]),
        "records_at_end":r["records_referencing_any_final_verse"],
        "unanchored_records":r["unanchored_record_count"],
        "unanchored_verses":r["unanchored_reference_count"],
    },sort_keys=True))
    for x in r["findings"]:
        print("EPISTLE_ENDINGS_CANDIDATE "+json.dumps(x,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
