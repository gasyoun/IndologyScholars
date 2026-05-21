"""Compare two presentation ID manifests and write an ID stability audit.

The comparison treats stable_key_candidate as the natural-key proxy and
presentation_id as the volatile ID under test.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


DEFAULT_JSON_OUT = Path("analytics_output/id_stability_audit.json")


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def index_unique(rows: list[dict[str, str]], key: str) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(key, "")].append(row)
    unique = {value: items[0] for value, items in grouped.items() if value and len(items) == 1}
    duplicates = {value: items for value, items in grouped.items() if value and len(items) > 1}
    return unique, duplicates


def display_record(row: dict[str, str]) -> dict[str, str]:
    return {
        "presentation_id": row.get("presentation_id", ""),
        "stable_key_candidate": row.get("stable_key_candidate", ""),
        "year": row.get("year", ""),
        "series": row.get("series", ""),
        "title": row.get("title", ""),
        "first_speaker": row.get("first_speaker", ""),
        "source_url": row.get("source_url", ""),
    }


def compare(before: list[dict[str, str]], after: list[dict[str, str]]) -> dict[str, object]:
    before_by_id, before_duplicate_ids = index_unique(before, "presentation_id")
    after_by_id, after_duplicate_ids = index_unique(after, "presentation_id")
    before_by_key, before_duplicate_keys = index_unique(before, "stable_key_candidate")
    after_by_key, after_duplicate_keys = index_unique(after, "stable_key_candidate")

    before_ids = set(before_by_id)
    after_ids = set(after_by_id)
    before_keys = set(before_by_key)
    after_keys = set(after_by_key)
    common_keys = before_keys & after_keys

    changed_for_same_key = []
    unchanged_for_same_key = 0
    for key in sorted(common_keys):
        before_row = before_by_key[key]
        after_row = after_by_key[key]
        if before_row.get("presentation_id") == after_row.get("presentation_id"):
            unchanged_for_same_key += 1
        else:
            changed_for_same_key.append(
                {
                    "stable_key_candidate": key,
                    "before_presentation_id": before_row.get("presentation_id", ""),
                    "after_presentation_id": after_row.get("presentation_id", ""),
                    "year": after_row.get("year", before_row.get("year", "")),
                    "series": after_row.get("series", before_row.get("series", "")),
                    "title": after_row.get("title", before_row.get("title", "")),
                    "first_speaker": after_row.get("first_speaker", before_row.get("first_speaker", "")),
                }
            )

    before_key_counts = Counter(row.get("stable_key_candidate", "") for row in before if row.get("stable_key_candidate"))
    after_key_counts = Counter(row.get("stable_key_candidate", "") for row in after if row.get("stable_key_candidate"))

    duplicate_key_samples = []
    for label, duplicate_map in (("before", before_duplicate_keys), ("after", after_duplicate_keys)):
        for key, rows in sorted(duplicate_map.items()):
            duplicate_key_samples.append(
                {
                    "manifest": label,
                    "stable_key_candidate": key,
                    "count": len(rows),
                    "records": [display_record(row) for row in rows[:10]],
                }
            )

    return {
        "generated": date.today().isoformat(),
        "summary": {
            "before_rows": len(before),
            "after_rows": len(after),
            "before_unique_presentation_ids": len(before_ids),
            "after_unique_presentation_ids": len(after_ids),
            "common_presentation_ids": len(before_ids & after_ids),
            "removed_presentation_ids": len(before_ids - after_ids),
            "added_presentation_ids": len(after_ids - before_ids),
            "before_unique_stable_keys": len(before_keys),
            "after_unique_stable_keys": len(after_keys),
            "common_stable_keys": len(common_keys),
            "missing_stable_keys_after": len(before_keys - after_keys),
            "new_stable_keys_after": len(after_keys - before_keys),
            "unchanged_ids_for_same_stable_key": unchanged_for_same_key,
            "changed_ids_for_same_stable_key": len(changed_for_same_key),
            "before_duplicate_presentation_ids": sum(len(rows) for rows in before_duplicate_ids.values()),
            "after_duplicate_presentation_ids": sum(len(rows) for rows in after_duplicate_ids.values()),
            "before_duplicate_stable_key_rows": sum(count for key, count in before_key_counts.items() if count > 1),
            "after_duplicate_stable_key_rows": sum(count for key, count in after_key_counts.items() if count > 1),
        },
        "changed_ids_for_same_stable_key_records": changed_for_same_key,
        "changed_ids_for_same_stable_key_sample": changed_for_same_key[:100],
        "missing_stable_keys_after_sample": [
            display_record(before_by_key[key]) for key in sorted(before_keys - after_keys)[:100]
        ],
        "new_stable_keys_after_sample": [
            display_record(after_by_key[key]) for key in sorted(after_keys - before_keys)[:100]
        ],
        "duplicate_stable_key_samples": duplicate_key_samples[:100],
    }


def write_optional_csv(audit: dict[str, object], csv_path: Path | None) -> None:
    if not csv_path:
        return
    rows = audit.get("changed_ids_for_same_stable_key_records", [])
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "stable_key_candidate",
        "before_presentation_id",
        "after_presentation_id",
        "year",
        "series",
        "title",
        "first_speaker",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", help="Manifest CSV from before rebuild")
    parser.add_argument("after", help="Manifest CSV from after rebuild")
    parser.add_argument("--out", default=str(DEFAULT_JSON_OUT), help="JSON audit output")
    parser.add_argument("--csv-out", default="", help="Optional CSV of changed IDs for same stable key")
    args = parser.parse_args()

    before_path = Path(args.before)
    after_path = Path(args.after)
    out_path = Path(args.out)
    csv_path = Path(args.csv_out) if args.csv_out else None

    before = read_manifest(before_path)
    after = read_manifest(after_path)
    audit = compare(before, after)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    write_optional_csv(audit, csv_path)

    summary = audit["summary"]
    print(f"Wrote ID stability audit to {out_path}")
    print(f"Before rows: {summary['before_rows']}; after rows: {summary['after_rows']}")
    print(f"Changed IDs for same stable key: {summary['changed_ids_for_same_stable_key']}")
    print(f"Missing stable keys after rebuild: {summary['missing_stable_keys_after']}")
    print(f"New stable keys after rebuild: {summary['new_stable_keys_after']}")
    print(f"Duplicate stable-key rows after rebuild: {summary['after_duplicate_stable_key_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
