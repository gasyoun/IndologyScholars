"""Merge a Gemini Flash response JSONL into authority_ids.json.

Usage:
  python import_seo_handoff.py <reply_file>

The reply file may be either a bare .jsonl (one JSON object per line) OR a
markdown / text file that contains a single ```jsonl fenced block — the
importer extracts the fenced block automatically.

Behavior:
  - Non-destructive: existing values are NOT overwritten unless the new
    value is non-empty and the field is missing or empty in the file.
  - Null / empty / blank-string values from the reply are dropped.
  - Items with unknown `key` are still merged (you may be enriching items
    not currently in use). To restrict merging, use --strict.
  - Unknown `item_type` rows are skipped with a warning.
"""

import argparse
import json
import re
import sys
from pathlib import Path

AUTHORITY_PATH = Path("authority_ids.json")
FENCED_JSONL_RE = re.compile(r"```jsonl\s*\n(.*?)\n```", re.DOTALL)

PLACE_FIELDS = {"name_en", "alternateName", "wikidata", "country", "country_ru"}
ORG_FIELDS = {"full_name_ru", "name_en", "alternateName", "url", "wikidata", "ror"}


def extract_jsonl_payload(text):
    match = FENCED_JSONL_RE.search(text)
    if match:
        return match.group(1)
    return text


def load_items(path):
    raw = Path(path).read_text(encoding="utf-8")
    payload = extract_jsonl_payload(raw)
    items = []
    for line_no, line in enumerate(payload.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"WARN line {line_no}: not valid JSON, skipped — {exc}", file=sys.stderr)
    return items


def clean_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, list):
        cleaned = [v.strip() if isinstance(v, str) else v for v in value]
        cleaned = [v for v in cleaned if v]
        return cleaned or None
    return value


def merge_authority(items, strict, allowed_keys):
    if not AUTHORITY_PATH.exists():
        sys.exit(
            f"ERROR: {AUTHORITY_PATH} not found. Run generate_publication_pages.py once to create it."
        )
    payload = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    payload.setdefault("places", {})
    payload.setdefault("organizations", {})

    added = {"place": 0, "organization": 0}
    updated = {"place": 0, "organization": 0}
    skipped_unknown = 0
    skipped_filtered = 0
    skipped_empty = 0
    skipped_bad = 0

    for item in items:
        item_type = item.get("item_type")
        key = item.get("key")
        if not key:
            skipped_bad += 1
            continue
        if item_type == "place":
            allowed = PLACE_FIELDS
            section = payload["places"]
            valid_keys = allowed_keys.get("place")
        elif item_type == "organization":
            allowed = ORG_FIELDS
            section = payload["organizations"]
            valid_keys = allowed_keys.get("organization")
        else:
            print(f"WARN unknown item_type {item_type!r} for key {key!r}, skipped", file=sys.stderr)
            skipped_unknown += 1
            continue

        if strict and valid_keys is not None and key not in valid_keys:
            print(f"WARN strict mode: key {key!r} not currently in use, skipped", file=sys.stderr)
            skipped_filtered += 1
            continue

        cleaned = {}
        for field, value in item.items():
            if field not in allowed:
                continue
            cv = clean_value(value)
            if cv is not None:
                cleaned[field] = cv

        if not cleaned:
            skipped_empty += 1
            continue

        if key in section:
            section[key].update(cleaned)
            updated[item_type] += 1
        else:
            section[key] = cleaned
            added[item_type] += 1

    AUTHORITY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Merged into {AUTHORITY_PATH}:")
    print(f"  places:        {added['place']} added, {updated['place']} updated")
    print(f"  organizations: {added['organization']} added, {updated['organization']} updated")
    if any([skipped_unknown, skipped_filtered, skipped_empty, skipped_bad]):
        print("  skipped:")
        if skipped_bad:
            print(f"    {skipped_bad} missing/empty key")
        if skipped_unknown:
            print(f"    {skipped_unknown} unknown item_type")
        if skipped_filtered:
            print(f"    {skipped_filtered} filtered by --strict")
        if skipped_empty:
            print(f"    {skipped_empty} had no usable fields after cleaning")


def discover_in_use_keys():
    """Return {place, organization} -> set of keys actually used in the current data.

    Best-effort only; used solely for --strict mode reporting.
    """
    try:
        from publication_helpers import load_site_data
        from generate_publication_pages import normalize_affiliation, timeline_records

        data = load_site_data("site_data.json")
        records = timeline_records(data)
        places = {
            item["ru"]
            for item in (data.get("geography_stats") or [])
            if item.get("ru") and item["ru"] not in {"Не указана", "Not specified"}
        }
        orgs = set()
        for record in records:
            name = normalize_affiliation(record.get("affiliation"))
            if name and name != "Независимые исследователи":
                orgs.add(name)
        return {"place": places, "organization": orgs}
    except Exception as exc:
        print(f"WARN could not discover in-use keys ({exc}); --strict will be a no-op", file=sys.stderr)
        return {"place": None, "organization": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reply_file", help="Path to Gemini Flash reply (jsonl or markdown with fenced jsonl).")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Skip items whose key isn't currently in use in site_data.json.",
    )
    args = parser.parse_args()

    items = load_items(args.reply_file)
    if not items:
        sys.exit("No valid items found in reply file.")
    print(f"Loaded {len(items)} items from {args.reply_file}")

    allowed_keys = discover_in_use_keys() if args.strict else {"place": None, "organization": None}
    merge_authority(items, strict=args.strict, allowed_keys=allowed_keys)


if __name__ == "__main__":
    main()
