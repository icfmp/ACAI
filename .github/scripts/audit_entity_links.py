"""Inspect exact entity-ID references throughout ACAI JSON, without editing data.

This is deliberately independent of resource type and can be reused for
proposed identity migrations. Textual descriptions and source attributions
are reported separately from structured links.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TYPE_DIRS = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")


def walk_strings(value, location=""):
    """Yield (JSON pointer, value) for every string, escaping pointer keys."""
    if isinstance(value, str):
        yield location or "/", value
    elif isinstance(value, dict):
        for key, child in value.items():
            part = str(key).replace("~", "~0").replace("/", "~1")
            yield from walk_strings(child, location + "/" + part)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_strings(child, location + "/" + str(index))


def scan(root: Path, target_ids: set[str]) -> list[dict[str, str]]:
    found = []
    for category in TYPE_DIRS:
        for path in sorted((root / category / "json").glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            for pointer, value in walk_strings(record):
                if value in target_ids:
                    kind = ("localization" if pointer.startswith("/localizations/")
                            else "provenance" if pointer.startswith("/alternate_sources/")
                            else "structured")
                    found.append({
                        "file": path.relative_to(root).as_posix(),
                        "record": record.get("id", ""),
                        "pointer": pointer,
                        "value": value,
                        "kind": kind,
                    })
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--target", action="append",
                    help="Exact entity ID to find; repeat for multiple entities.")
    ap.add_argument("--targets-file", type=Path,
                    help="UTF-8 file of retired IDs, one per line; blank lines and # comments ignored.")
    ap.add_argument("--fail-structured", action="store_true",
                    help="Exit nonzero when structural references to any target remain.")
    ap.add_argument("--fail-any", action="store_true",
                    help="Exit nonzero when any exact ID matches, including localized metadata.")
    args = ap.parse_args()
    targets = set(args.target or [])
    if args.targets_file:
        targets.update(
            line.strip() for line in args.targets_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not targets:
        ap.error("Supply at least one --target or --targets-file containing an ID")
    result = scan(args.root, targets)
    for match in result:
        print("ENTITY_ID_REFERENCE " + json.dumps(match, sort_keys=True, ensure_ascii=False))
    structured = sum(1 for x in result if x["kind"] == "structured")
    localizations = sum(1 for x in result if x["kind"] == "localization")
    provenance = sum(1 for x in result if x["kind"] == "provenance")
    print("ENTITY_ID_AUDIT " + json.dumps({
        "targets": sorted(targets),
        "structured": structured,
        "localization": localizations,
        "provenance": provenance,
        "matches": len(result),
    }, sort_keys=True))
    return int((args.fail_structured and structured > 0) or (args.fail_any and bool(result)))


if __name__ == "__main__":
    raise SystemExit(main())
