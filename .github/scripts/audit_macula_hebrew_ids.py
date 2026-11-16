"""Cross-check every ACAI Hebrew occurrence token against pinned Macula WLC.

No source transformation. The emitted JSON lists missing source IDs by entity,
type and referent field, for investigation before any editorial correction.
"""
from __future__ import annotations
import argparse
import collections
import csv
import json
from pathlib import Path

DIRS=("people","places","groups","deities","fauna","flora","realia","keyterms")
FIELDS=("explicit_instances","pronominal_referents","subject_referents")

def audit(root:Path, tsv:Path):
    ids={}
    for folder in DIRS:
        for path in (root/folder/"json").glob("*.json"):
            d=json.loads(path.read_text(encoding="utf-8"))
            for field in FIELDS:
                for corpus,groups in d.get(field,{}).items():
                    if corpus.lower() != "wlc":
                        continue
                    for group in groups:
                        for token in group:
                            if isinstance(token,str):
                                ids.setdefault(token,[]).append((d["id"],field))
    found={}
    with tsv.open(encoding="utf-8-sig",newline="") as handle:
        rows=csv.DictReader(handle,delimiter="\t")
        if "xml:id" not in (rows.fieldnames or []):
            raise ValueError("Unexpected Macula TSV schema: xml:id missing")
        for row in rows:
            token=row.get("xml:id")
            if token in ids:
                found[token]=(row.get("ref",""),row.get("text",""),row.get("lemma",""))
    missing=sorted(set(ids)-set(found))
    cases=[]
    byfield=collections.Counter()
    byentity=collections.Counter()
    for token in missing:
        for entity,field in ids[token]:
            byfield[field]+=1
            byentity[entity]+=1
        cases.append({"id":token,"entities":sorted(set(e for e,f in ids[token]))[:8]})
    return {"summary":{
        "unique_mentioned_source_ids":len(ids),
        "found_in_pinned_macula":len(found),
        "missing_from_pinned_macula":len(missing),
        "acai_assignments":sum(len(v) for v in ids.values()),
        "missing_by_field":dict(byfield),
        "top_affected_entities":byentity.most_common(30)
    },"missing_id_details":cases}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--tsv",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("macula-hebrew-existence.json"))
    a=p.parse_args()
    result=audit(a.root,a.tsv)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MACULA_FULL_HEBREW_AUDIT "+json.dumps(result["summary"],sort_keys=True))
    for x in result["missing_id_details"][:50]:
        print("MACULA_MISSING_SOURCE_WORD "+json.dumps(x))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
