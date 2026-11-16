"""Show nearby pinned Macula Hebrew rows for 18 unresolved subject IDs.

Investigation only; never guesses replacements or edits source data.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tsv",type=Path,required=True)
    p.add_argument("--missing",type=Path,default=Path("macula-hebrew-existence.json"))
    a=p.parse_args()
    report=json.loads(a.missing.read_text(encoding="utf-8"))
    missing=[x["id"] for x in report["missing_id_details"]]
    verses={tok[1:9] for tok in missing}
    rows=defaultdict(list)
    with a.tsv.open(encoding="utf-8-sig",newline="") as file:
        for row in csv.DictReader(file,delimiter="\t"):
            tok=row.get("xml:id","")
            if tok[1:9] in verses:
                rows[tok[1:9]].append({
                    "id":tok,"ref":row.get("ref",""),"text":row.get("text",""),
                    "english":row.get("english",""),
                    "subjref":row.get("subjref",""),
                })
    for token in missing:
        candidates=sorted(
            rows.get(token[1:9],[]),
            key=lambda row:(abs(int(row["id"][9:])-int(token[9:])),row["id"])
            if row["id"][9:].isdigit() and token[9:].isdigit()
            else (999999,row["id"])
        )[:4]
        print("MACULA_NEAREST_MISSING_SUBJECT "+json.dumps({
            "missing":token,"candidates":candidates
        },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
