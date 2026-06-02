"""Apply found birth years from curation/birth_year_findings.csv to the database.

Usage:
  python tools/apply_birth_years.py           # apply all findings
  python tools/apply_birth_years.py --dry-run  # show what would be applied
"""

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
FINDINGS_PATH = ROOT / "curation" / "birth_year_findings.csv"


def apply(dry_run: bool = False):
    if not FINDINGS_PATH.exists():
        print(f"No findings file at {FINDINGS_PATH}")
        print("Run 'python tools/scrape_birth_years.py' first to find birth years.")
        sys.exit(1)

    with open(FINDINGS_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        findings = list(reader)

    print(f"Loading {len(findings)} findings...")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    applied = 0
    for finding in findings:
        pid = finding["person_id"]
        year = int(finding["birth_year"])
        source = finding.get("source_url", "")

        # Check current state
        c.execute("SELECT birth_year, full_name_ru, display_name FROM person WHERE person_id=?", (pid,))
        row = c.fetchone()
        if not row:
            print(f"  SKIP {pid}: not found in DB")
            continue

        current_year, fname, dname = row
        name = fname or dname or pid

        if current_year and current_year > 0:
            print(f"  SKIP {name}: already has birth_year={current_year}")
            continue

        if dry_run:
            print(f"  WOULD SET {name}: birth_year={year} (from {source[:50]})")
        else:
            c.execute("UPDATE person SET birth_year=?, source_url=? WHERE person_id=?",
                      (year, source, pid))
            # Also insert data_assertion
            c.execute("""INSERT OR REPLACE INTO data_assertion (entity_type, entity_id, attribute, value, source_url, confidence, curator_id, verified_at)
                         VALUES ('person', ?, 'birth_year', ?, ?, 'confirmed', 'scraper', datetime('now'))""",
                      (pid, str(year), source))
            print(f"  SET {name}: birth_year={year} (from {source[:50]})")
            applied += 1

    if not dry_run and applied > 0:
        conn.commit()
        print(f"\nApplied {applied} birth years. Run 'python build_and_populate_db.py' to rebuild.")

    conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    apply(dry_run=dry_run)
