"""Reference-to-original-word alignment triage for the entire ACAI snapshot.

Read-only, zero external sources. This establishes internal consistency only:
it cannot establish that a word actually names the intended entity.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

CATEGORIES = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")


def inspect(root: Path) -> dict:
    stats = collections.Counter()
    findings = []
    category_counts = collections.defaultdict(collections.Counter)
    canonical = {}
    secondary = []
    for category in CATEGORIES:
        for path in sorted((root / category / "json").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            entity = data["id"]
            primary = data.get("primary_id")
            refs = data.get("references", [])
            if not isinstance(refs, list):
                continue
            declared = set(refs)
            explicit = set()
            token_rows = []
            indirect = set()
            for field in ("pronominal_referents", "subject_referents"):
                for groups in data.get(field, {}).values():
                    for group in groups:
                        for token in group:
                            if isinstance(token, str) and len(token) >= 9:
                                indirect.add(token[1:9])
            for corpus, groups in data.get("explicit_instances", {}).items():
                for group in groups:
                    for token in group:
                        if isinstance(token, str) and len(token) >= 9:
                            explicit.add(token[1:9])
                            token_rows.append((corpus, token))
            stats["records"] += 1
            stats["reference_entries"] += len(refs)
            stats["explicit_token_entries"] += len(token_rows)
            stats["distinct_explicit_verses"] += len(explicit)
            stats["distinct_declared_verses"] += len(declared)
            category_counts[category]["records"] += 1
            category_counts[category]["declared_verses"] += len(declared)
            category_counts[category]["explicit_verses"] += len(explicit)
            if entity == primary:
                canonical[entity] = (declared, set(token_rows))
                stats["primary_records"] += 1
            else:
                secondary.append((entity, primary, declared, set(token_rows)))
                stats["secondary_records"] += 1
            missing = sorted(declared - explicit)
            completely_unanchored = sorted(declared - explicit - indirect)
            extra = sorted(explicit - declared)
            if not token_rows and refs:
                stats["records_without_explicit_tokens"] += 1
            if missing:
                stats["records_with_unanchored_refs"] += 1
                stats["unanchored_ref_entries"] += len(missing)
                findings.append({
                    "rule": "reference_without_explicit_word",
                    "id": entity, "count": len(missing),
                    "examples": missing[:12],
                    "category": category,
                })
            if completely_unanchored:
                stats["records_with_no_token_at_verse"] += 1
                stats["references_without_any_token"] += len(completely_unanchored)
                findings.append({
                    "rule": "reference_without_any_word_or_referent",
                    "id": entity, "count": len(completely_unanchored),
                    "examples": completely_unanchored[:12], "category": category,
                })
            if missing:
                stats["refs_covered_by_only_indirect_tokens"] += len(missing)-len(completely_unanchored)
            if extra:
                stats["records_with_unlisted_explicit_verses"] += 1
                stats["unlisted_explicit_verses"] += len(extra)
                findings.append({
                    "rule": "explicit_word_verse_not_referenced",
                    "id": entity, "count": len(extra),
                    "examples": extra[:12],
                    "category": category,
                })
            exact_tokens = collections.Counter(token_rows)
            repeated = sorted((key for key, count in exact_tokens.items() if count > 1))
            if repeated:
                stats["records_with_repeated_explicit_tokens"] += 1
                stats["repeated_explicit_token_entries"] += sum(exact_tokens[k]-1 for k in repeated)
                findings.append({
                    "rule": "same_exact_explicit_token_repeated_within_record",
                    "id": entity, "count": len(repeated),
                    "examples": [f"{c}:{t}" for c, t in repeated[:10]],
                    "category": category,
                })
    # Alias occurrences should already appear in the canonical record by documented
    # ACAI design, though keyterm granularity can differ; deviations are candidates.
    for entity, primary, refs, tokens in secondary:
        if primary not in canonical:
            continue
        cref, ctok = canonical[primary]
        missing_refs = sorted(refs - cref)
        missing_tokens = sorted(tokens - ctok)
        if missing_refs or missing_tokens:
            stats["secondary_with_primary_alignment_gaps"] += 1
            stats["secondary_gap_records_" + entity.split(":", 1)[0]] += 1
            stats["secondary_refs_absent_from_primary"] += len(missing_refs)
            stats["secondary_tokens_absent_from_primary"] += len(missing_tokens)
            findings.append({
                "rule": "secondary_name_not_in_primary",
                "id": entity, "primary": primary,
                "count": len(missing_refs)+len(missing_tokens),
                "reference_examples": missing_refs[:10],
                "token_examples": [f"{c}:{t}" for c, t in missing_tokens[:10]],
                "category": entity.split(":", 1)[0],
            })
    findings.sort(key=lambda x: (x["rule"], -x["count"], x["id"]))
    return {"summary": dict(sorted(stats.items())),
            "by_category": {k: dict(v) for k, v in sorted(category_counts.items())},
            "findings": findings}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--output", type=Path, default=Path("reference-alignment-results.json"))
    p.add_argument("--top", type=int, default=20)
    args = p.parse_args()
    result = inspect(args.root)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("REFERENCE_AUDIT_SUMMARY " + json.dumps(result["summary"], sort_keys=True))
    print("REFERENCE_AUDIT_BY_CATEGORY " + json.dumps(result["by_category"], sort_keys=True))
    rules = collections.Counter(x["rule"] for x in result["findings"])
    print("REFERENCE_AUDIT_FINDING_TYPES " + json.dumps(rules, sort_keys=True))
    for rule in sorted(rules):
        items = [x for x in result["findings"] if x["rule"] == rule]
        for finding in items[:args.top]:
            print("REFERENCE_AUDIT_CANDIDATE " + json.dumps(finding, sort_keys=True))
    print("This is not a source-language semantic verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
