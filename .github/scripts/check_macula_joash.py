"""Read-only source-word verification for ACAI's homonymous kings.

Inputs: full ACAI checkout and pinned Macula Hebrew TSV. No source data is edited.
Only extracts narrow evidence for explicitly listed token IDs; never publishes source corpus.
"""
import argparse
import csv
import json
from pathlib import Path

TOKENS = [
    "o120140010032", "o120140010111",
    "o120140130061", "o120140130101",
    "o120140230071", "o120140230131",
    "o140250230061", "o140250230101",
    "o140250250041", "o140250250091",
]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tsv", type=Path, required=True)
    args = p.parse_args()
    found = {}
    with args.tsv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = reader.fieldnames or []
        print("MACULA_SOURCE_COLUMNS " + json.dumps(columns))
        for row in reader:
            values = set(row.values())
            matching = values.intersection(TOKENS)
            for token in matching:
                found[token] = {
                    k: v for k,v in row.items()
                    if k and (k.lower() in ("id", "ref", "reference", "text", "word", "gloss", "lemma", "english", "english_gloss", "mandarin", "transliteration")
                              or "gloss" in k.lower())
                }
    print("MACULA_SOURCE_SUMMARY " + json.dumps({
        "requested":len(TOKENS),"matched":len(found),"unmatched":sorted(set(TOKENS)-set(found))
    }))
    for token in TOKENS:
        if token in found:
            print("MACULA_SOURCE_TOKEN " + json.dumps({"id":token,"source":found[token]},ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
