"""Read-only original-word evidence for same-category ACAI identity collisions.

Uses global audit findings, pinned Macula TSVs and ACAI's actual IDs. It is an
editorial review aid, NOT an automatic identity reassignment or correctness score.
"""
import argparse
import collections
import csv
import json
from pathlib import Path

KINDS = {"person", "place", "deity"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--findings", type=Path, default=Path("audit-results.json"))
    p.add_argument("--hebrew",type=Path,required=True)
    p.add_argument("--greek",type=Path,required=True)
    p.add_argument("--top",type=int,default=18)
    args=p.parse_args()
    findings=json.loads(args.findings.read_text(encoding="utf-8"))["findings"]
    items={}
    pairs=collections.defaultdict(list)
    for item in findings:
        if item["rule"]!="cross_entity_explicit_token":
            continue
        entities=item["entity"].split("|")
        types={e.split(":",1)[0] for e in entities}
        if len(types)!=1 or not types.issubset(KINDS):
            continue
        corpus,token=item["location"].split(":",1)
        items[(corpus,token)]=entities
        for i,a in enumerate(entities):
            for b in entities[i+1:]:
                pairs[(a,b)].append((corpus,token))
    selected=sorted(pairs.items(),key=lambda x:(-len(x[1]),x[0]))[:args.top]
    target={key for _,lst in selected for key in lst}
    wordrows={}
    for corpus,path in (("wlc",args.hebrew),("SBLGNT",args.greek)):
        with path.open(encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f,delimiter="\t"):
                tok=row.get("xml:id")
                if (corpus,tok) in target:
                    wordrows[(corpus,tok)]={
                        "ref":row.get("ref",""),
                        "word":row.get("text",""),
                        "gloss":row.get("english","") or row.get("gloss",""),
                        "lemma":row.get("lemma",""),
                    }
    print("HOMONYM_CONTEXT_COUNTS "+json.dumps({
        "collisions_within_people_places_deities":len(items),
        "distinct_entity_pairs":len(pairs),
        "selected_pairs":len(selected),
        "source_rows_matched":len(wordrows),
        "source_rows_requested":len(target),
    }))
    for (a,b),lst in selected:
        rows=[]
        for k in sorted(lst):
            d=wordrows.get(k)
            rows.append({"token":k[1],"corpus":k[0],**(d or {})})
        print("HOMONYM_CONTEXT_PAIR "+json.dumps({
            "a":a,"b":b,"shared_exact_ids":len(lst),"tokens":rows
        },ensure_ascii=False,sort_keys=True))
if __name__=="__main__":
    main()
