"""Audit repeated exact word groups without changing lexical annotation data.

Identical token groups are strong import duplication candidates; overlapping
but nonidentical groups can encode distinct phrase/sense mappings and require
separate editorial review.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path

CATEGORIES=("people","places","groups","deities","fauna","flora","realia","keyterms")
OCCURRENCE_FIELDS=("explicit_instances","pronominal_referents","subject_referents")

def inspect(root):
    summary=collections.Counter()
    results=[]
    flagged_records=set()
    for category in CATEGORIES:
        for path in sorted((root/category/"json").glob("*.json")):
            data=json.loads(path.read_text(encoding="utf-8"))
            for field in OCCURRENCE_FIELDS:
                corpus_map=data.get(field,{})
                if not isinstance(corpus_map,dict):
                    continue  # validate.py handles malformed fields
                for corpus,groups in corpus_map.items():
                    if not isinstance(groups,list):
                        continue
                    group_tuples=[tuple(g) for g in groups if isinstance(g,list)]
                    repeats=sum(v-1 for v in collections.Counter(group_tuples).values())
                    word_to_groups=collections.defaultdict(set)
                    word_counts=collections.Counter()
                    for group in group_tuples:
                        for word in group:
                            word_counts[word]+=1
                            word_to_groups[word].add(group)
                    overlap_words=sum(1 for word,v in word_counts.items()
                                      if v>1 and len(word_to_groups[word])>1)
                    if not repeats and not overlap_words:
                        continue
                    flagged_records.add(data["id"])
                    summary["occurrence_fields_with_any_repeat"]+=1
                    summary["exact_duplicate_groups"]+=repeats
                    summary["word_ids_in_different_groups"]+=overlap_words
                    examples=[{"group":list(group),"times":n} for group,n in
                              collections.Counter(group_tuples).most_common()
                              if n>1][:5]
                    results.append({"id":data["id"],"occurrence_field":field,
                        "corpus":corpus,"duplicate_groups":repeats,
                        "cross_group_word_ids":overlap_words,
                        "repeat_examples":examples})
    summary["records_with_any_repeat"]=len(flagged_records)
    results.sort(key=lambda x:(-x["duplicate_groups"],-x["cross_group_word_ids"],
                               x["id"],x["occurrence_field"],x["corpus"]))
    return {"summary":dict(summary),"findings":results}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--output",type=Path,default=Path("duplicate-word-groups.json"))
    p.add_argument("--top",type=int,default=30)
    a=p.parse_args()
    result=inspect(a.root)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DUPLICATE_WORD_GROUP_SUMMARY "+json.dumps(result["summary"],sort_keys=True))
    for item in result["findings"][:a.top]:
        print("DUPLICATE_WORD_GROUP_CANDIDATE "+json.dumps(item,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":
    main()
