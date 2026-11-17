"""Audit repeated exact word groups without changing lexical annotation data.

Repeated target groups may represent multiple incoming source edges or parallel
Macula annotation channels, not redundant Scripture words. Source-aligned
findings remain review candidates, never automatically approved deletions.
"""
from __future__ import annotations
import argparse
import collections
import csv
import json
import re
from pathlib import Path

CATEGORIES=("people","places","groups","deities","fauna","flora","realia","keyterms")
OCCURRENCE_FIELDS=("explicit_instances","pronominal_referents","subject_referents")


def _source_ids(value, corpus):
    """Read exact numeric Macula word targets, with or without corpus prefix.

    This recognizes word IDs inside subjref lists and semantic-frame role
    strings without inventing replacement IDs or comparing partial prefixes.
    """
    if not isinstance(value, str):
        return set()
    prefix = "o" if corpus.lower() == "wlc" else "n"
    digits = 12 if corpus.lower() == "wlc" else 11
    pattern = rf"(?<![A-Za-z0-9])(?:[on])?([0-9]{{{digits},}})(?![0-9])"
    return {prefix + word for word in re.findall(pattern, value)}


def _source_annotations(path, wanted):
    """Load just the source rows relevant to repeated ACAI subject groups."""
    if path is None or not wanted:
        return {}
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"xml:id", "subjref", "frame"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"Missing {sorted(required)} columns in Macula source: {path}")
        for row in reader:
            token = row.get("xml:id")
            if token in wanted:
                rows[token] = {"subjref": row.get("subjref", ""),
                               "frame": row.get("frame", "")}
    return rows


def _trace_parallel_subject_annotations(results, pending, hebrew, greek, summary):
    """Recognize only concrete parallel Macula subjref/frame evidence.

    A matching annotation pair does NOT prove that an ACAI repeat is bad:
    this diagnostic cannot reconstruct the original import edge provenance.
    """
    wanted = {"wlc": set(), "sblgnt": set()}
    for finding, corpus, repeats, _ in pending:
        wanted[corpus.lower()].update(token for group in repeats for token in group)
    sources = {"wlc": _source_annotations(hebrew, wanted["wlc"]),
               "sblgnt": _source_annotations(greek, wanted["sblgnt"])}
    for finding, corpus, repeats, explicit_ids in pending:
        source = sources[corpus.lower()]
        parallel = []
        unresolved = []
        for group in repeats:
            matched = []
            for token in group:
                row = source.get(token)
                if row is None:
                    continue
                subjects = _source_ids(row["subjref"], corpus)
                frames = _source_ids(row["frame"], corpus)
                if subjects & frames & explicit_ids:
                    matched.append(token)
            if matched:
                parallel.append({"group": list(group), "source_tokens": matched})
            else:
                unresolved.append(list(group))
        finding["source_provenance"] = {
            "repeated_groups_examined": len(repeats),
            "parallel_subjref_frame_candidates": len(parallel),
            "unresolved_or_other_source_patterns": len(unresolved),
            "examples": parallel[:5],
        }
        summary["subject_repeated_groups_examined"] += len(repeats)
        summary["parallel_source_annotation_candidates"] += len(parallel)
        summary["subject_groups_not_explained_by_parallel_fields"] += len(unresolved)

def inspect(root, hebrew=None, greek=None):
    summary=collections.Counter()
    results=[]
    flagged_records=set()
    pending=[]
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
                    result={"id":data["id"],"occurrence_field":field,
                        "corpus":corpus,"duplicate_groups":repeats,
                        "cross_group_word_ids":overlap_words,
                        "repeat_examples":examples}
                    results.append(result)
                    if (field == "subject_referents" and repeats
                            and corpus.lower() in ("wlc", "sblgnt")):
                        repeated=[group for group, n in
                                  collections.Counter(group_tuples).items() if n > 1]
                        explicit=set(token for groups in
                                     data.get("explicit_instances", {}).values()
                                     for group in groups for token in group)
                        pending.append((result, corpus, repeated, explicit))
    summary["records_with_any_repeat"]=len(flagged_records)
    if hebrew is not None and greek is not None:
        _trace_parallel_subject_annotations(results, pending, hebrew, greek, summary)
    results.sort(key=lambda x:(-x["duplicate_groups"],-x["cross_group_word_ids"],
                               x["id"],x["occurrence_field"],x["corpus"]))
    return {"summary":dict(summary),"findings":results}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--output",type=Path,default=Path("duplicate-word-groups.json"))
    p.add_argument("--top",type=int,default=30)
    p.add_argument("--hebrew",type=Path,help="Pinned Macula WLC word TSV for source-backed triage")
    p.add_argument("--greek",type=Path,help="Pinned Macula SBLGNT word TSV")
    a=p.parse_args()
    if (a.hebrew is None) != (a.greek is None):
        p.error("Supply both --hebrew and --greek, or neither")
    result=inspect(a.root, hebrew=a.hebrew, greek=a.greek)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DUPLICATE_WORD_GROUP_SUMMARY "+json.dumps(result["summary"],sort_keys=True))
    for item in result["findings"][:a.top]:
        print("DUPLICATE_WORD_GROUP_CANDIDATE "+json.dumps(item,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":
    main()
