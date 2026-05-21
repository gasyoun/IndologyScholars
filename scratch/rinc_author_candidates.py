"""
scratch/rinc_author_candidates.py

Phase 4 — РИНЦ/eLIBRARY Lookup Workflow
========================================
Generates a review queue for scholars missing a `rinc_author_id` or `spin` in `authority_ids.json`.
Extracts the likely surname and formats an eLIBRARY search URL.

Output: analytics_output/rinc_lookup_queue.csv
"""

import sys
import csv
import json
import sqlite3
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).parent.parent
DB = ROOT / "conferences.db"
AUTHORITY_IDS = ROOT / "authority_ids.json"
OUT_CSV = ROOT / "analytics_output" / "rinc_lookup_queue.csv"

def extract_cyrillic_surname(full_name_ru: str) -> str:
    """Return likely surname from a 'Фамилия Имя Отчество' or 'И.И. Фамилия' string."""
    name = (full_name_ru or "").strip()
    if not name:
        return ""
    parts = name.split()
    if not parts:
        return ""
    if re.match(r"^[А-ЯЁA-Z]\.([А-ЯЁA-Z]\.)?$", parts[0]):
        return parts[-1] if len(parts) >= 2 else ""
    return parts[0]

def main():
    with open(AUTHORITY_IDS, encoding="utf-8") as f:
        authority = json.load(f)
    persons_auth = authority.get("persons", {})

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT pers.person_id, pers.display_name, pers.full_name_ru,
               COUNT(DISTINCT pres.presentation_id) AS n_talks
          FROM person pers
          LEFT JOIN presentation_person pp ON pp.person_id = pers.person_id
          LEFT JOIN presentation pres ON pres.presentation_id = pp.presentation_id
         GROUP BY pers.person_id
         ORDER BY n_talks DESC
    """)
    rows = cur.fetchall()
    
    out = []
    for pid, disp, full, n in rows:
        auth_data = persons_auth.get(pid, {})
        if auth_data.get("rinc_author_id") or auth_data.get("spin"):
            continue  # Already has RINC data
            
        full_name = full or disp or ""
        surname = extract_cyrillic_surname(full_name)
        
        out.append({
            "person_id": pid,
            "display_name": disp,
            "full_name_ru": full_name,
            "n_talks": n,
            "rinc_search_url": f"https://elibrary.ru/author_items.asp?authorid=&fams={surname}" if surname else "",
            "review_status": "todo",
            "rinc_author_id": "",
            "spin": "",
            "profile_url": "",
            "reviewer": "",
            "checked_at": ""
        })

    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        if out:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
            
    print(f"Wrote {OUT_CSV} ({len(out)} rows pending review)")
    conn.close()

if __name__ == "__main__":
    main()
