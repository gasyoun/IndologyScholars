"""Re-key the vestigial `presentation_id` column in the theme-code CSVs.

Background
----------
`presentation_id` is regenerated deterministically every build by
`build_and_populate_db.stable_presentation_id()` (hash of series+year+title+
speaker+session_order). The LLM theme-code CSVs were frozen under an *older*
id scheme, so their `presentation_id` column no longer matches the live DB.

The live pipeline already sidesteps this: `generate_site_data.py` and
`generate_publication_pages.py` join theme codes by the NATURAL key
`(year, series, title)`, not by `presentation_id`. This utility refreshes the
now-vestigial `presentation_id` column so the supplementary files handed to the
journal are internally consistent with `conferences.db`.

Canonical join key for any future external CSV is `(year, series, title)`.

Usage:  python scratch/rekey_theme_codes.py
"""
import csv
import os
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "conferences.db")
TARGETS = [
    "analytics_output/theme_codes_final.csv",
    "analytics_output/theme_codes_final_v2.csv",
    "article/supplementary_theme_codes.csv",
]
SERIES_BY_ID = {1: "Zograf Readings", 2: "Roerich Readings"}


def norm(t):
    return re.sub(r"\s+", " ", (t or "").strip()).lower()


def build_live_map():
    con = sqlite3.connect(DB)
    q = """
        SELECT pr.presentation_id, pr.title, e.year, e.event_series_id
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
    """
    live = {}
    for pid, title, year, sid in con.execute(q):
        live[(str(year), SERIES_BY_ID.get(sid, ""), norm(title))] = pid
    con.close()
    return live


def rekey_file(path, live):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"  SKIP (missing): {path}")
        return
    with open(full, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    if "presentation_id" not in fields:
        print(f"  SKIP (no presentation_id column): {path}")
        return
    matched = changed = 0
    for r in rows:
        key = (str(r["year"]).strip(), str(r["series"]).strip(), norm(r["title"]))
        new_id = live.get(key)
        if new_id:
            matched += 1
            if r["presentation_id"] != new_id:
                r["presentation_id"] = new_id
                changed += 1
    with open(full, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {path}: {len(rows)} rows, matched {matched}, re-keyed {changed}, "
          f"unmatched {len(rows) - matched}")


def main():
    live = build_live_map()
    print(f"Live presentations (natural keys): {len(live)}")
    for path in TARGETS:
        rekey_file(path, live)


if __name__ == "__main__":
    main()
