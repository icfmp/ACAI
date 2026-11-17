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
    """Load pinned Macula source rows for repeated indirect ACAI groups."""
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
                rows[token] = {
                    "subjref": row.get("subjref", ""),
                    "frame": row.get("frame", ""),
                    "participantref": row.get("participantref", ""),
                    "referent": row.get("referent", ""),
                }
    return rows


def _trace_indirect_source_annotations(results, pending, hebrew, greek, summary,
                                       explicit_by_id, primary_by_id):
    """Trace repeated indirect groups to recorded source attributes, read-only.

    Parallel subjref/frame mentions suggest why subject links can repeat.
    Matching pronoun referents confirm an anchored link, NOT why it repeats.
    Neither observation authorizes deduplication of an ACAI record.
    """
    wanted = {"wlc": set(), "sblgnt": set()}
    for finding, corpus, repeats, _ in pending:
        wanted[corpus.lower()].update(token for group in repeats for token in group)
    sources = {"wlc": _source_annotations(hebrew, wanted["wlc"]),
               "sblgnt": _source_annotations(greek, wanted["sblgnt"])}
    for finding, corpus, repeats, explicit_ids in pending:
        source = sources[corpus.lower()]
        matched_groups = []
        primary_only_groups = []
        unmatched_groups = []
        subject = finding["occurrence_field"] == "subject_referents"
        primary = primary_by_id.get(finding["id"])
        # An aggregate's exact tokens are evidence of indexing inheritance,
        # not proof that a secondary keyterm has the same lexical meaning.
        primary_ids = (explicit_by_id.get(primary, set()) - explicit_ids
                       if primary != finding["id"] else set())
        for group in repeats:
            linked = []
            parent_linked = []
            for token in group:
                row = source.get(token)
                if row is None:
                    continue
                if subject:
                    subjects = _source_ids(row["subjref"], corpus)
                    frames = _source_ids(row["frame"], corpus)
                    supported = bool(subjects & frames & explicit_ids)
                else:
                    # Macula Greek uses "referent"; Hebrew Lowfat/TSV may
                    # use "participantref". Read both without guessing aliases.
                    referenced = (_source_ids(row["referent"], corpus)
                                  | _source_ids(row["participantref"], corpus))
                    supported = bool(referenced & explicit_ids)
                    if not supported and referenced & primary_ids:
                        parent_linked.append(token)
                if supported:
                    linked.append(token)
            if linked:
                matched_groups.append({"group": list(group), "source_tokens": linked})
            elif parent_linked and not subject:
                primary_only_groups.append(
                    {"group": list(group), "source_tokens": parent_linked,
                     "primary_id": primary})
            else:
                unmatched_groups.append(list(group))
        if subject:
            finding["source_provenance"] = {
                "repeated_groups_examined": len(repeats),
                "parallel_subjref_frame_candidates": len(matched_groups),
                "unresolved_or_other_source_patterns": len(unmatched_groups),
                "examples": matched_groups[:5],
            }
            summary["subject_repeated_groups_examined"] += len(repeats)
            summary["parallel_source_annotation_candidates"] += len(matched_groups)
            summary["subject_groups_not_explained_by_parallel_fields"] += len(unmatched_groups)
        else:
            finding["source_provenance"] = {
                "repeated_groups_examined": len(repeats),
                "source_referent_linked_groups": len(matched_groups),
                "source_referent_primary_only_groups": len(primary_only_groups),
                "source_referent_unconfirmed_groups": len(unmatched_groups),
                "note": ("A parent-only match indicates indexing inheritance, "
                         "not semantic identity or proof of necessary multiplicity."),
                "examples": matched_groups[:5],
                "primary_only_examples": primary_only_groups[:5],
            }
            summary["pronominal_repeated_groups_examined"] += len(repeats)
            summary["pronominal_source_referent_linked"] += len(matched_groups)
            summary["pronominal_primary_only_source_linked"] += len(primary_only_groups)
            summary["pronominal_source_referent_unconfirmed"] += len(unmatched_groups)

def inspect(root, hebrew=None, greek=None):
    summary=collections.Counter()
    results=[]
    flagged_records=set()
    pending=[]
    explicit_by_id={}
    primary_by_id={}
    for category in CATEGORIES:
        for path in sorted((root/category/"json").glob("*.json")):
            data=json.loads(path.read_text(encoding="utf-8"))
            explicit_by_id[data["id"]]=set(
                token for groups in data.get("explicit_instances", {}).values()
                for group in groups for token in group
            )
            primary_by_id[data["id"]]=data.get("primary_id")
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
                    if (field in ("subject_referents", "pronominal_referents") and repeats
                            and corpus.lower() in ("wlc", "sblgnt")):
                        repeated=[group for group, n in
                                  collections.Counter(group_tuples).items() if n > 1]
                        pending.append(
                            (result, corpus, repeated, explicit_by_id[data["id"]]))
    summary["records_with_any_repeat"]=len(flagged_records)
    if hebrew is not None and greek is not None:
        _trace_indirect_source_annotations(
            results, pending, hebrew, greek, summary, explicit_by_id, primary_by_id)
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
