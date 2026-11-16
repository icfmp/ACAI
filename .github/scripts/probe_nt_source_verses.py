"""Read-only probe of selected cross-version NT place names and verse endings.

Evidence only. Displaying a source verse is not a decision to change an ACAI
entity or to prefer one textual tradition over another.
"""
import argparse
import csv
import json
from pathlib import Path

VERSES = {"43001028", "44020015", "54006021", "45016027", "45016023", "45016024", "45016025", "45014024", "47013013", "47013014", "44008036", "44008037", "44015033", "44015034", "40023013", "40023014"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--greek",type=Path,required=True)
    a=p.parse_args()
    found={v:[] for v in VERSES}
    final={}
    with a.greek.open(encoding="utf-8-sig",newline="") as file:
        for row in csv.DictReader(file,delimiter="\t"):
            token=row.get("xml:id","")
            if not token.startswith("n") or len(token)<10 or not token[1:9].isdigit():
                continue
            verse=token[1:9]
            book=int(verse[:2])
            if 45<=book<=65:
                final[book]=max(final.get(book,verse),verse)
            if verse in found:
                found[verse].append({
                    "id":token,
                    "ref":row.get("ref",""),
                    "text":row.get("text",""),
                    "english":row.get("english","")
                })
    print("NT_EPISTLE_LAST_VERSES "+json.dumps(dict(sorted(final.items()))))
    for verse in sorted(found):
        print("NT_SOURCE_VERSE "+json.dumps({"verse":verse,"tokens":found[verse]},ensure_ascii=False))
if __name__=="__main__":
    main()
