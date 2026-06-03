"""Inter-rater reliability sampling for L1 and G1 classification.

Uses a fixed random seed to sample 100 unique presentation titles from the DB.
Outputs a blank coding CSV for a second-blind coder, with columns for:
  - L1 theme code + G1/G2/G3 level
The second coder fills these independently; Cohen's κ / Krippendorff's α
is then computed against the original classifications in site_data.json.

Usage:
  python tools/build_interrater_sample.py
Output:
  analytics_output/interrater_sample.csv
"""

import csv
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
SITE_DATA = ROOT / "site_data.json"
OUT_PATH = ROOT / "analytics_output" / "interrater_sample.csv"

SEED = 20260603
SAMPLE_SIZE = 100

THEME_CODES = [
    "history_and_culture",
    "religion_and_philosophy",
    "literature_and_poetry",
    "linguistics_and_philology",
    "art_and_material_culture",
    "unspecified",
]

GUMILYOV_LEVELS = ["1", "2", "3"]


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def main():
    random.seed(SEED)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT DISTINCT pr.presentation_id, pr.title, e.year, es.series_name_en
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        WHERE pr.title IS NOT NULL AND TRIM(pr.title) != ''
        ORDER BY e.year, es.event_series_id, pr.presentation_id
    """).fetchall()
    conn.close()

    print(f"Total unique presentation titles in DB: {len(rows)}")

    sample = random.sample(rows, min(SAMPLE_SIZE, len(rows)))

    # Load existing classifications for comparison (not shown to second coder)
    data = load_site_data()
    talk_map = {}
    for scholar in data.get("scholars", []):
        for talk in scholar.get("talks", []):
            pid = talk.get("presentation_id")
            if pid:
                talk_map[pid] = talk

    print(f"\n{'='*50}")
    print(f"INTER-RATER RELIABILITY CODING SHEET")
    print(f"Seed: {SEED} | Sample size: {len(sample)}")
    print(f"{'='*50}")
    print()
    print("Instructions for the second-blind coder:")
    print("  1. Read the presentation title below.")
    print("  2. Assign ONE L1 theme code from the list.")
    print("  3. Assign ONE G-level (1=micro-case, 2=tradition/school, 3=global synthesis).")
    print("  4. Do NOT look up the original classification or the author.")
    print("  5. When in doubt, prefer the most conservative code (unspecified / G1).")
    print()
    print("L1 theme codes:")
    for c in THEME_CODES:
        print(f"  {c}")
    print()
    print("G levels: 1 = micro-case (single text/author/term/source)")
    print("           2 = tradition, school, broad class of phenomena")
    print("           3 = inter-regional, civilizational, or methodological frame")
    print()

    out_rows = []
    for row in sample:
        pid = row["presentation_id"]
        title = row["title"]
        year = row["year"]
        series = row["series_name_en"]

        existing = talk_map.get(pid, {})
        orig_l1 = existing.get("theme", {}).get("code", "?")
        orig_g = existing.get("gumilyov_scale", "?")

        print(f"ID: {pid}")
        print(f"Title: {title}")
        print(f"Year: {year} | Series: {series}")
        print(f"  CODER_2_L1: [    ]    (orig: {orig_l1})")
        print(f"  CODER_2_G:  [    ]    (orig: {orig_g})")
        print()

        out_rows.append({
            "presentation_id": pid,
            "title": title,
            "year": year,
            "series": series,
            "coder_2_l1": "",
            "coder_2_g": "",
            "existing_l1": orig_l1,
            "existing_g": orig_g,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["presentation_id", "title", "year", "series", "coder_2_l1", "coder_2_g", "existing_l1", "existing_g"]
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"\n{'='*50}")
    print(f"Wrote {len(out_rows)} rows to {OUT_PATH}")
    print(f"To compute agreement: python tools/compute_interrater_agreement.py")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
