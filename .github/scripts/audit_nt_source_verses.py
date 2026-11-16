"""Find ACAI verse references absent from the selected pinned source edition.

This is a source-compatibility audit, not a biblical-versification validator:
absent source verses may reflect another edition, a longer textual reading,
or a reference to a traditional subscription. No input files are modified.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

CATEGORIES = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")


def inspect(root: Path, source_tsv: Path, *, corpus: str = "nt") -> dict:
    if corpus not in ("nt", "ot"):
        raise ValueError("corpus must be nt or ot")
    prefix = "n" if corpus == "nt" else "o"
    first_book, last_book = (40, 66) if corpus == "nt" else (1, 39)
    source_verses = set()
    with source_tsv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            word = row.get("xml:id", "")
            if len(word) >= 9 and word.startswith(prefix) and word[1:9].isdigit():
                source_verses.add(word[1:9])

    occurrences = collections.defaultdict(list)
    stats = collections.Counter()
    for category in CATEGORIES:
        for path in sorted((root/category/"json").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for verse in data.get("references", []):
                if not isinstance(verse, str) or len(verse) != 8 or not verse.isdigit():
                    stats["invalid_reference_format"] += 1
                    continue
                book = int(verse[:2])
                if not first_book <= book <= last_book:
                    continue
                stats["record_reference_entries"] += 1
                if verse not in source_verses:
                    stats["record_reference_entries_absent_from_source"] += 1
                    occurrences[verse].append({"entity": data["id"], "category": category,
                        "canonical":data.get("primary_id") == data.get("id")})
    report = []
    for verse, items in sorted(occurrences.items(), key=lambda v:(-len(v[1]),v[0])):
        categories = collections.Counter(x["category"] for x in items)
        report.append({
            "verse_id": verse,
            "number_of_entity_references": len(items),
            "canonical_references":sum(x["canonical"] for x in items),
            "categories": dict(categories),
            "entities":[x["entity"] for x in items],
        })
    return {"summary": {
        "source_verses":len(source_verses),
        "record_reference_entries":stats["record_reference_entries"],
        "record_reference_entries_absent_from_source":stats["record_reference_entries_absent_from_source"],
        "distinct_referenced_verses_absent_from_source":len(report),
        "invalid_reference_format":stats["invalid_reference_format"],
    }, "verses_absent_from_pinned_source":report}


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--corpus",choices=("nt","ot"),default="nt")
    parser.add_argument("--output",type=Path,default=Path("nt-source-verse-compatibility.json"))
    parser.add_argument("--top",type=int,default=80)
    args=parser.parse_args()
    result=inspect(args.root,args.source,corpus=args.corpus)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(args.corpus.upper()+"_SOURCE_VERSE_COMPATIBILITY_SUMMARY "+json.dumps(result["summary"],sort_keys=True))
    for item in result["verses_absent_from_pinned_source"][:args.top]:
        print(args.corpus.upper()+"_SOURCE_VERSE_ABSENCE "+json.dumps(item,sort_keys=True))
    print("Missing source verse is NOT evidence that the verse should be added to or removed from any edition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
