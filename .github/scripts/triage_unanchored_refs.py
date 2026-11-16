"""Classify ACAI unanchored verse links for editorial triage, without mutating data.

Separate genuinely unnamed participants, alternative-text/epistle links,
cross-record aliases and references in source text but without a word-level
anchor. The classifications are review buckets, not error verdicts.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path

CATEGORIES=("people","places","groups","deities","fauna","flora","realia","keyterms")
INDIRECT=("pronominal_referents","subject_referents")
def inspect(root:Path)->dict:
    counters=collections.Counter()
    buckets=collections.defaultdict(list)
    for category in CATEGORIES:
        for path in sorted((root/category/"json").glob("*.json")):
            d=json.loads(path.read_text(encoding="utf-8"))
            refs=set(d.get("references",[]))
            if not refs:continue
            anchored=set()
            explicit=set()
            for field in ("explicit_instances",)+INDIRECT:
                for groups in d.get(field,{}).values():
                    for group in groups:
                        for token in group:
                            if isinstance(token,str) and len(token)>=9:
                                anchored.add(token[1:9])
                                if field=="explicit_instances":explicit.add(token[1:9])
            missing=sorted(refs-anchored)
            if not missing:continue
            own=d["id"] == d.get("primary_id")
            has_explicit=bool(explicit)
            for verse in missing:
                book=int(verse[:2]) if verse[:2].isdigit() else -1
                if not has_explicit:
                    key="zero_explicit_tokens"
                elif not own:
                    key="secondary_form_missing_anchor"
                elif category=="people":
                    key="named_or_unnamed_person_missing_anchor"
                elif category=="places":
                    key="canonical_place_missing_anchor"
                else:
                    key="other_category_missing_anchor"
                counters[key]+=1
                counters["category_"+category]+=1
                if 40<=book<=66:counters["nt_unanchored"]+=1
                elif 1<=book<=39:counters["ot_unanchored"]+=1
                entry={"id":d["id"],"verse":verse,"references":len(refs),
                       "description":d.get("localizations",{}).get("eng",{}).get("descriptions",[{}])[0].get("description","")[:130]}
                buckets[key].append(entry)
    result={"summary":dict(sorted(counters.items())),
            "buckets":{k:v for k,v in sorted(buckets.items())}}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--output",type=Path,default=Path("unanchored-triage.json"))
    p.add_argument("--top",type=int,default=35)
    a=p.parse_args()
    result=inspect(a.root)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("UNANCHORED_TRIAGE_SUMMARY "+json.dumps(result["summary"],sort_keys=True))
    for key,rows in result["buckets"].items():
        print("UNANCHORED_TRIAGE_BUCKET "+json.dumps({"kind":key,"count":len(rows),"examples":rows[:a.top]},ensure_ascii=False))
if __name__=="__main__":main()
