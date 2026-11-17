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

MD_INSTANCE_TAIL = re.compile(r"\(([^()\n]+)\)\s*$")


def _markdown_display_counts(content: str):
    """Count rendered BSB verse occurrences per section, not Hebrew/Greek word parts.

    Reports are review candidates: BSB-aligned display grouping and source
    original-language segmentation can differ legitimately.
    """
    counts = Counter()
    present = set()
    unparseable = 0
    section = None
    for line in content.splitlines():
        if line.startswith("#"):
            if line == "### OT Instances (BSB)":
                section = "OT"
            elif line == "### NT Instances (BSB)":
                section = "NT"
            elif line == "### References (Whole Bible)":
                section = "REF"
            else:
                section = None
            if section is not None:
                present.add(section)
            continue
        if section is None or not line.startswith("* "):
            continue
        if section == "REF":
            counts[section] += len([v for v in line[2:].split("; ") if v])
        else:
            match = MD_INSTANCE_TAIL.search(line)
            if match:
                counts[section] += len([v for v in match.group(1).split("; ") if v])
            else:
                unparseable += 1
    return counts, present, unparseable



# Canonical 66-book order for ACAI's existing BSB Markdown abbreviations.
# This is a standard reference parser, not an entity-specific exception.
MD_BOOKS = (
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH "
    "EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL "
    "AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT "
    "ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS "
    "1PE 2PE 1JN 2JN 3JN JUD REV"
).split()
MD_BOOK_INDEX = {book: pos for pos, book in enumerate(MD_BOOKS, 1)}
MD_VERSE_REF = re.compile(r"^([1-3]?[A-Z]{3}) ([0-9]+):([0-9]+)$")


def _markdown_verse_counts(content: str):
    """Parse the *existing* displayed verse lists, preserving multiplicity.

    Malformed labels are reported for review rather than guessed or coerced.
    This detects wrong verses even when the total number of entries matches.
    """
    verses = {period: Counter() for period in ("OT", "NT", "REF")}
    invalid = Counter()
    section = None
    for line in content.splitlines():
        if line.startswith("#"):
            section = {
                "### OT Instances (BSB)": "OT",
                "### NT Instances (BSB)": "NT",
                "### References (Whole Bible)": "REF",
            }.get(line)
            continue
        if not line.startswith("* ") or section is None:
            continue
        if section == "REF":
            entries = line[2:].split("; ")
        else:
            match = MD_INSTANCE_TAIL.search(line)
            if not match:
                continue  # The existing malformed-bullet rule reports this.
            entries = match.group(1).split("; ")
        for label in entries:
            parsed = MD_VERSE_REF.fullmatch(label.strip())
            if not parsed or parsed.group(1) not in MD_BOOK_INDEX:
                invalid[section] += 1
                continue
            book = MD_BOOK_INDEX[parsed.group(1)]
            chapter, verse = int(parsed.group(2)), int(parsed.group(3))
            if not (1 <= chapter <= 999 and 1 <= verse <= 999):
                invalid[section] += 1
                continue
            verses[section][f"{book:02d}{chapter:03d}{verse:03d}"] += 1
    return verses, invalid


def _verse_delta(rendered: Counter, source: Counter) -> str:
    """Compact, repeatable examples of wrong/missing displayed verse IDs."""
    extra = sorted((rendered - source).elements())
    missing = sorted((source - rendered).elements())
    return f"extra={extra[:5]!r} ({len(extra)}), missing={missing[:5]!r} ({len(missing)})"


FAMILY_MD_FIELDS = {
    "Father": "father", "Mother": "mother", "Partner(s)": "partners",
    "Offspring": "offspring", "Sibling(s)": "siblings",
}
MD_FAMILY_LINK = re.compile(r"\]\(([^)]+)\)")


def _markdown_family_metadata(content: str):
    """Extract existing structured family infobox links, not biography prose."""
    found = False
    rendered = {}
    for line in content.splitlines():
        if line.startswith("**Familial Relationships of ") and line.endswith("**"):
            found = True
            continue
        if not found:
            continue
        if line.startswith(("**", "##")):
            break
        if not line.startswith("* ") or ": " not in line:
            continue
        label, value = line[2:].split(": ", 1)
        if label == "Gender":
            rendered["gender"] = value.strip()
        elif label in FAMILY_MD_FIELDS:
            rendered[FAMILY_MD_FIELDS[label]] = [
                "person:" + Path(target).stem
                for target in MD_FAMILY_LINK.findall(value)
            ]
    return found, rendered


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
                report("duplicate_reference", rid, f"{rel}#/references/{i}", ref, "error")
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

        # Compare the derivative Markdown against the recorded word *groups*.
        # This deliberately does not invent names, source tokens or new refs.
        md_rel = f"{Path(rel).parts[0]}/md/{Path(rel).stem}.md"
        md_file = root / md_rel
        if md_file.is_file():
            try:
                md = md_file.read_text(encoding="utf-8")
            except UnicodeError as exc:
                report("invalid_markdown_encoding", rid, md_rel, str(exc))
            else:
                displayed, sections, malformed = _markdown_display_counts(md)
                if malformed:
                    report("malformed_markdown_instance", rid, md_rel,
                           f"{malformed} instance bullets lack a terminal reference list")
                sources = Counter()
                explicit_map = record.get("explicit_instances", {})
                if not isinstance(explicit_map, dict):
                    explicit_map = {}
                for corpus, groups in explicit_map.items():
                    if not isinstance(groups, list):
                        continue
                    if corpus.lower() == "wlc":
                        sources["OT"] += len(groups)
                    elif corpus.upper() == "SBLGNT":
                        sources["NT"] += len(groups)
                for period in ("OT", "NT"):
                    if period in sections or sources[period]:
                        if displayed[period] != sources[period]:
                            report("markdown_instance_group_count_mismatch", rid, md_rel,
                                   f"{period}: {displayed[period]} rendered BSB instances "
                                   f"vs {sources[period]} original-language groups")
                if "REF" in sections and displayed["REF"] != len(references):
                    report("markdown_reference_count_mismatch", rid, md_rel,
                           f"{displayed['REF']} rendered references vs "
                           f"{len(references)} JSON references")

                # Count-only comparisons cannot catch a wrong-versus-right
                # verse swap when both lists have the same length. Verify the
                # full verse multisets without changing any source data.
                displayed_verses, invalid_labels = _markdown_verse_counts(md)
                source_verses = {"OT": Counter(), "NT": Counter()}
                invalid_groups = Counter()
                for corpus, groups in explicit_map.items():
                    period = ("OT" if corpus.lower() == "wlc" else
                              "NT" if corpus.upper() == "SBLGNT" else None)
                    if period is None or not isinstance(groups, list):
                        continue
                    for group in groups:
                        if (not isinstance(group, list) or not group or
                                any(not isinstance(token, str) or not TOKEN.fullmatch(token)
                                    for token in group)):
                            invalid_groups[period] += 1
                            continue
                        # Several word parts can describe one occurrence,
                        # but a multi-verse group cannot safely be assigned
                        # to one verse by taking its first word.
                        verse_ids = {token[1:9] for token in group}
                        if len(verse_ids) != 1:
                            invalid_groups[period] += 1
                            continue
                        source_verses[period][next(iter(verse_ids))] += 1
                for period in ("OT", "NT"):
                    if invalid_labels[period]:
                        report("markdown_unparseable_verse", rid, md_rel,
                               f"{period}: {invalid_labels[period]} unparseable displayed IDs")
                    if invalid_groups[period]:
                        report("source_uncomparable_word_group", rid, rel,
                               f"{period}: {invalid_groups[period]} ambiguous source groups")
                    if (period in sections and displayed[period] == sources[period]
                            and not invalid_labels[period] and not invalid_groups[period]
                            and displayed_verses[period] != source_verses[period]):
                        report("markdown_instance_verse_mismatch", rid, md_rel,
                               f"{period}: " + _verse_delta(
                                   displayed_verses[period], source_verses[period]))
                if "REF" in sections:
                    if invalid_labels["REF"]:
                        report("markdown_unparseable_verse", rid, md_rel,
                               f"REF: {invalid_labels['REF']} unparseable displayed IDs")
                    elif (displayed["REF"] == len(references)
                          and all(isinstance(ref, str) and BCV8.fullmatch(ref)
                                  for ref in references)):
                        expected_refs = Counter(references)
                        if displayed_verses["REF"] != expected_refs:
                            report("markdown_reference_verse_mismatch", rid, md_rel,
                                   _verse_delta(displayed_verses["REF"], expected_refs))

                # An old generated family infobox must not reverse a vetted
                # JSON kinship correction (e.g. Ahlai or Judas).
                if rid.startswith("person:"):
                    has_family, family = _markdown_family_metadata(md)
                    if has_family:
                        expected_gender = record.get("gender")
                        if expected_gender != family.get("gender"):
                            report("markdown_family_metadata_mismatch", rid,
                                   f"{md_rel}#/gender",
                                   f"gender: JSON={expected_gender!r}, "
                                   f"Markdown={family.get('gender')!r}")
                        for key in FAMILY_MD_FIELDS.values():
                            value = record.get(key, [])
                            if isinstance(value, str):
                                expected = [value]
                            elif isinstance(value, list):
                                expected = value
                            else:
                                expected = []
                            rendered = family.get(key, [])
                            if sorted(expected) != sorted(rendered):
                                report("markdown_family_metadata_mismatch", rid,
                                       f"{md_rel}#/{key}",
                                       f"{key}: JSON={expected!r}, "
                                       f"Markdown={rendered!r}")

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
