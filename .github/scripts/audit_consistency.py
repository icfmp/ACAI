"""Read-only, deterministic consistency scan of the entire ACAI JSON snapshot.

This complements (never replaces) validate.py. Findings are candidates for editorial
review, not automatically approved corrections. Python standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TYPE_DIRS = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")
RELATION_FIELDS = ("father", "mother", "partners", "offspring", "siblings", "referred_to_as")
OCCURRENCE_FIELDS = ("explicit_instances", "pronominal_referents", "subject_referents")
BCV8 = re.compile(r"^[0-9]{8}$")
TOKEN = re.compile(r"^[on][0-9]{11,}$")


def scan(root: Path) -> dict:
    records = {}
    findings = []
    counts = Counter()

    def report(rule, record, location, detail, severity="review"):
        findings.append(dict(rule=rule, severity=severity, entity=record,
                             location=location, detail=detail))

    for directory in TYPE_DIRS:
        for path in sorted((root / directory / "json").glob("*.json")):
            rel = path.relative_to(root).as_posix()
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError) as exc:
                report("invalid_json", "", rel, str(exc), "error")
                continue
            if not isinstance(record, dict):
                report("invalid_record", "", rel, "Expected JSON object", "error")
                continue
            rid = record.get("id")
            if not isinstance(rid, str):
                report("missing_id", "", rel, "Missing/string id", "error")
                continue
            records[rid] = (record, rel)
            counts["records"] += 1
            if rid == record.get("primary_id"):
                counts["canonical_entities"] += 1

    # A source token can be attributed to multiple names of the SAME entity,
    # but attribution to DIFFERENT canonical identities deserves inspection.
    assignments = defaultdict(set)
    for rid, (record, rel) in sorted(records.items()):
        primary = record.get("primary_id")
        if primary not in records:
            report("missing_primary", rid, rel, str(primary), "error")
        references = record.get("references", [])
        if not isinstance(references, list):
            report("malformed_references", rid, rel, "Expected list", "error")
            references = []
        seen = set()
        for i, ref in enumerate(references):
            counts["reference_assignments"] += 1
            if not isinstance(ref, str) or not BCV8.fullmatch(ref):
                report("invalid_reference_format", rid, f"{rel}#/references/{i}", str(ref), "error")
            if isinstance(ref, str) and ref in seen:
                report("duplicate_reference", rid, f"{rel}#/references/{i}", ref)
            seen.add(ref)

        for field in RELATION_FIELDS:
            values = record.get(field, [])
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list):
                report("malformed_relationship", rid, f"{rel}#/{field}", "Expected string or list")
                continue
            for index, value in enumerate(values):
                if isinstance(value, str) and re.match(r"^[a-z]+:", value) and value not in records:
                    report("dangling_relationship", rid, f"{rel}#/{field}/{index}", value)

        # A relationship must not identify one canonical person simultaneously
        # as this person's parent and sibling. Keep this as a review finding:
        # investigate historical/figurative kinship before altering source data.
        if rid.startswith("person:"):
            siblings = record.get("siblings", [])
            if isinstance(siblings, list):
                for parent_field in ("father", "mother"):
                    parent_id = record.get(parent_field)
                    if isinstance(parent_id, str) and parent_id in siblings:
                        report(
                            "parent_sibling_identity_conflict", rid,
                            f"{rel}#/{parent_field}",
                            f"{parent_id} is also present in siblings",
                        )

        for field in OCCURRENCE_FIELDS:
            corpus_map = record.get(field, {})
            if not isinstance(corpus_map, dict):
                report("malformed_occurrences", rid, f"{rel}#/{field}", "Expected object", "error")
                continue
            for corpus, groups in corpus_map.items():
                if not isinstance(groups, list):
                    report("malformed_groups", rid, f"{rel}#/{field}/{corpus}", "Expected list", "error")
                    continue
                for gi, group in enumerate(groups):
                    if not isinstance(group, list):
                        report("malformed_group", rid, f"{rel}#/{field}/{corpus}/{gi}", "Expected list", "error")
                        continue
                    for ti, token in enumerate(group):
                        loc = f"{rel}#/{field}/{corpus}/{gi}/{ti}"
                        counts[field + "_tokens"] += 1
                        if not isinstance(token, str) or not TOKEN.fullmatch(token):
                            report("invalid_token_format", rid, loc, str(token), "error")
                            continue
                        # ORG BCV8 in token IDs: n/o + 8-digit verse + word suffix.
                        verse = token[1:9]
                        if field == "explicit_instances":
                            assignments[(corpus, token)].add(primary)
                            if verse not in seen:
                                report("explicit_verse_not_listed", rid, loc, verse)

        for corpus, speeches in record.get("speeches", {}).items():
            if not isinstance(speeches, list):
                continue
            for speech in speeches:
                if isinstance(speech, dict) and isinstance(speech.get("words"), list):
                    counts["speech_tokens"] += len(speech["words"])

        if record.get("mentioned_in_bible") is True and record.get("non_biblical") is True:
            report("contradictory_biblical_flags", rid, rel,
                   "mentioned_in_bible=true and non_biblical=true", "error")

    for (corpus, token), primaries in sorted(assignments.items()):
        if len(primaries) > 1:
            report("cross_entity_explicit_token", "|".join(sorted(str(p) for p in primaries)),
                   f"{corpus}:{token}", "One exact word ID assigned to distinct canonical entities")

    counts["cross_entity_token_collisions"] = sum(
        len(v) > 1 for v in assignments.values()
    )
    counts["findings"] = len(findings)
    return {"schema_version": 1, "summary": dict(sorted(counts.items())),
            "findings": sorted(findings, key=lambda x: (x["rule"], x["entity"], x["location"]))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = scan(args.root)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    print("Full findings are unverified candidates, not editorial corrections.")
    return 0 if not any(x["severity"] == "error" for x in result["findings"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
