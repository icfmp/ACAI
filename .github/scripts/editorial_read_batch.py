"""Print a deterministic batch of ACAI canonical entity descriptions for human/LLM triage.

Read-only. JSON lines are output for editorial review; no automatic pass verdict.
Use --start / --limit to divide the full snapshot without skipping entries.
"""
import argparse
import json
from pathlib import Path

CATEGORIES = ("people", "places", "groups", "deities", "fauna", "flora", "realia", "keyterms")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--limit", type=int, default=250)
    p.add_argument("--all-records", action="store_true")
    p.add_argument("--secondary-only", action="store_true")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    records = []
    for category in CATEGORIES:
        for path in sorted((root / category / "json").glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            is_primary = record.get("id") == record.get("primary_id")
            if args.secondary_only and is_primary:
                continue
            if not args.secondary_only and not args.all_records and not is_primary:
                continue
            eng = record.get("localizations", {}).get("eng", {})
            descriptions = [x.get("description", "") for x in eng.get("descriptions", []) if isinstance(x, dict)]
            records.append({
                "id": record.get("id"),
                "label": eng.get("preferred_label"),
                "description": " | ".join(filter(None, descriptions)),
                "primary_id": record.get("primary_id"),
                "references": len(record.get("references") or []),
                "flags": {k: record[k] for k in ("non_biblical", "mentioned_in_bible")
                          if k in record},
            })
    selected = records[args.start:args.start + args.limit]
    print("EDITORIAL_BATCH " + json.dumps({
        "total": len(records), "start": args.start,
        "end_exclusive": args.start + len(selected), "count": len(selected)
    }))
    for record in selected:
        print("EDITORIAL_RECORD " + json.dumps(record, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
