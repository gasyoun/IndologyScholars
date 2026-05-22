"""Verify the degree display wiring WITHOUT rebuilding conferences.db.

1. unit-test generate_scholars_pages.format_degree + JSON-LD credential;
2. on a TEMP COPY of conferences.db, add+populate the degree columns and run
   the exact PRAGMA-detection + SELECT used by generate_site_data, confirming
   the degree flows through.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# --- Test 1: render helpers ---
import generate_scholars_pages as gsp  # noqa: E402

sample = {
    "id": "PERS_test", "url_slug": "test", "name": "Лысенко В. Г.",
    "full_name_ru": "Лысенко Виктория Георгиевна", "full_name_en": "Lysenko Victoria Georgievna",
    "degree": "доктор философских наук", "degree_year": "",
    "degree_source_url": "https://ru.wikipedia.org/wiki/Лысенко,_Виктория_Георгиевна",
    "dominant_theme": "Philosophy", "total_talks": 16, "first_year": 2007, "last_year": 2025,
}
print("format_degree (with degree):")
print("  ", gsp.format_degree(sample))
print("format_degree (no degree):", repr(gsp.format_degree({"degree": None})))

jsonld = gsp.profile_structured_data(sample, {"persons": {}})
cred = jsonld[0]["mainEntity"].get("hasCredential")
print("JSON-LD hasCredential:", cred)

# --- Test 2: data path on a temp DB copy ---
src = ROOT / "conferences.db"
tmp = Path(tempfile.gettempdir()) / "conferences_degree_test.db"
shutil.copy(src, tmp)
con = sqlite3.connect(str(tmp))
cur = con.cursor()
for col in ("degree", "degree_year", "degree_source_url"):
    cur.execute(f"ALTER TABLE person ADD COLUMN {col} TEXT")
cur.execute("UPDATE person SET degree='доктор философских наук', degree_source_url='https://example/x' "
            "WHERE display_name LIKE '%Лысенко%'")
con.commit()

# replicate generate_site_data detection + select
person_cols = {r[1] for r in cur.execute("PRAGMA table_info(person)").fetchall()}
has_degree = {"degree", "degree_year", "degree_source_url"} <= person_cols
degree_select = ", degree, degree_year, degree_source_url" if has_degree else ""
print("\nhas_degree detected:", has_degree)
rows = cur.execute(
    f"SELECT person_id, display_name, birth_year, death_year, full_name_ru, full_name_en{degree_select} "
    "FROM person WHERE degree IS NOT NULL"
).fetchall()
print(f"persons with degree in temp DB: {len(rows)}")
for r in rows[:3]:
    print("  ", r[1], "->", r[6])
con.close()
tmp.unlink()
print("\nOK: real conferences.db untouched (temp copy used and deleted).")
