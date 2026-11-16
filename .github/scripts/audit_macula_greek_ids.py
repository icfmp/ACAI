"""Cross-check ACAI NT word and referent IDs against pinned Macula Greek SBLGNT.

Read-only. Reports missing exact tokens; a missing ID can also be caused by
version/segmentation mismatch and must be reviewed before editing source data.
"""
import argparse
import collections
import csv
import json
from pathlib import Path

CATEGORIES=("people","places","groups","deities","fauna","flora","realia","keyterms")
FIELDS=("explicit_instances","pronominal_referents","subject_referents")

def scan(root,source):
    assignments=collections.defaultdict(list)
    for category in CATEGORIES:
        for path in (root/category/"json").glob("*.json"):
            d=json.loads(path.read_text(encoding="utf8"))
            for field in FIELDS:
                for corpus,groups in d.get(field,{}).items():
                    if corpus.lower()!="sblgnt":
                        continue
                    for group in groups:
                        for token in group:
                            if isinstance(token,str):
                                assignments[token].append((d["id"],field))
    present=set()
    with source.open(encoding="utf-8-sig",newline="") as f:
        t=csv.DictReader(f,delimiter="\t")
        print("MACULA_GREEK_COLUMNS "+json.dumps(t.fieldnames))
        key=next((k for k in ("xml:id","id","nodeId") if k in (t.fieldnames or [])),None)
        if key is None:
            raise ValueError("Unexpected Macula Greek TSV format; no word ID column")
        for row in t:
            tok=row.get(key)
            if tok in assignments:
                present.add(tok)
    missing=sorted(set(assignments)-present)
    fields=collections.Counter()
    entities=collections.Counter()
    for token in missing:
        for entity,field in assignments[token]:
            fields[field]+=1
            entities[entity]+=1
    return {
        "summary":{
            "unique_mentioned_source_ids":len(assignments),
            "matched_in_pinned_macula":len(present),
            "missing_from_pinned_macula":len(missing),
            "acai_assignments":sum(map(len,assignments.values())),
            "missing_by_field":dict(fields),
            "top_affected_entities":entities.most_common(30)
        },
        "missing": [{"id":token,"entities":sorted(set(e for e,f in assignments[token]))[:8]} for token in missing]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--tsv",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("macula-greek-existence.json"))
    a=p.parse_args()
    result=scan(a.root,a.tsv)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("MACULA_FULL_GREEK_AUDIT "+json.dumps(result["summary"],sort_keys=True))
    for x in result["missing"][:60]:
        print("MACULA_GREEK_MISSING_SOURCE_WORD "+json.dumps(x))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
