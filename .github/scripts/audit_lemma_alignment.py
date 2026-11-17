"""Read-only lexical-lemma consistency candidates against pinned Macula TSVs.

A missing exact lexical overlap is a *triage candidate*, not an editorial error:
compound names, spelling variants, morphology and aliases need human review.
This script never edits ACAI records or original-language source data.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import unicodedata
from pathlib import Path

CATEGORIES = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")
LANGUAGES = {"he": "wlc", "el": "sblgnt", "gr": "sblgnt"}


def normalize(value: str) -> str:
    """Normalize only for comparison, never for writing back to ACAI."""
    decomposed = unicodedata.normalize("NFD", value).lower().replace("ς", "σ")
    base = "".join(c for c in decomposed if not unicodedata.category(c).startswith("M"))
    return " ".join("".join(c if c.isalpha() or c.isspace() else " " for c in base).split())


def source_index(path: Path, wanted: set[str]) -> dict[str, dict[str, str]]:
    matched = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not {"xml:id", "lemma"}.issubset(reader.fieldnames or ()):
            raise ValueError(f"Unexpected Macula TSV schema in {path}: xml:id/lemma required")
        for row in reader:
            token = row.get("xml:id", "")
            if token in wanted:
                matched[token] = {"ref": row.get("ref", ""),
                                  "lemma": row.get("lemma", ""),
                                  "text": row.get("text", "")}
    return matched


def audit(root: Path, hebrew: Path, greek: Path) -> dict:
    records = []
    wanted = {"wlc": set(), "sblgnt": set()}
    for category in CATEGORIES:
        for path in sorted((root / category / "json").glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            lemmas = record.get("lemmas") or {}
            explicit = record.get("explicit_instances") or {}
            if not isinstance(lemmas, dict) or not isinstance(explicit, dict):
                continue
            by_corpus = collections.defaultdict(list)
            for corpus, groups in explicit.items():
                if not isinstance(groups, list):
                    continue
                for group in groups:
                    if isinstance(group, list):
                        by_corpus[corpus.lower()].append(tuple(t for t in group if isinstance(t, str)))
            for language, values in lemmas.items():
                corpus = LANGUAGES.get(language.lower())
                if corpus is None or not isinstance(values, list):
                    continue
                declared = sorted(set(x for x in values if isinstance(x, str) and normalize(x)))
                if not declared:
                    continue
                groups = by_corpus[corpus]
                ids = set(t for group in groups for t in group)
                records.append((category, record["id"], language, corpus, declared, ids, groups))
                wanted[corpus].update(ids)
    indexes = {"wlc": source_index(hebrew, wanted["wlc"]),
               "sblgnt": source_index(greek, wanted["sblgnt"])}
    summary = collections.Counter(records_scanned=len(records))
    findings = []
    for category, entity, language, corpus, declared, ids, groups in records:
        summary["language_" + language] += 1
        if not ids:
            summary["without_explicit_source_ids"] += 1
            continue
        source = [indexes[corpus][i] for i in sorted(ids) if i in indexes[corpus]]
        if not source:
            summary["without_matching_source_ids"] += 1
            continue
        summary["with_source_words"] += 1
        known = {normalize(s["lemma"]) for s in source if normalize(s["lemma"])}
        # A compound proper name is often represented by a group of adjacent
        # original-language words; compare its ordered lemma phrase as well.
        for group in groups:
            if group and all(t in indexes[corpus] for t in group):
                phrase = normalize(" ".join(indexes[corpus][t]["lemma"] for t in group))
                if phrase:
                    known.add(phrase)
        normalized_declared = {d: normalize(d) for d in declared}
        matched = [d for d, norm in normalized_declared.items() if norm in known]
        if len(matched) == len(declared):
            summary["all_declared_lemmas_found"] += 1
            continue
        rule = "zero_exact_lemma_overlap" if not matched else "partial_exact_lemma_overlap"
        summary[rule] += 1
        # Preserve one exact source-word ID for each distinct lemma. The first six
        # word examples below may hide a rare anomalous lemma in large records.
        # Populate this only for candidates to keep the audit lightweight.
        lemma_examples = {}
        for token in sorted(ids):
            entry = indexes[corpus].get(token)
            if entry is None or not entry["lemma"]:
                continue
            lemma_examples.setdefault(entry["lemma"], {
                "word_id": token, "ref": entry["ref"],
                "lemma": entry["lemma"], "text": entry["text"],
            })
        findings.append({
            "rule": rule, "category": category, "id": entity, "language": language,
            "declared_lemmas": declared, "matched_declared_lemmas": matched,
            "unmatched_declared_lemmas": [d for d in declared if d not in matched],
            "source_lemmas": sorted({s["lemma"] for s in source if s["lemma"]})[:30],
            "source_word_ids": len(source), "missing_source_ids": len(ids) - len(source),
            "source_lemma_examples": [lemma_examples[k] for k in sorted(lemma_examples)[:30]],
            "source_examples": [{"ref": x["ref"], "lemma": x["lemma"], "text": x["text"]}
                                for x in source[:6]],
        })
    findings.sort(key=lambda x: (x["rule"], x["category"], x["id"], x["language"]))
    return {"summary": dict(sorted(summary.items())), "findings": findings,
            "caveat": "Exact lexical match triage only: multiword names, inflections, variants and aliases may be valid."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--hebrew", type=Path, required=True)
    parser.add_argument("--greek", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("lemma-alignment-candidates.json"))
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    result = audit(args.root, args.hebrew, args.greek)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("LEMMA_ALIGNMENT_SUMMARY " + json.dumps(result["summary"], sort_keys=True))
    for rule in ("zero_exact_lemma_overlap", "partial_exact_lemma_overlap"):
        selected = [x for x in result["findings"] if x["rule"] == rule][:args.top]
        for item in selected:
            print("LEMMA_ALIGNMENT_CANDIDATE " + json.dumps(item, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
