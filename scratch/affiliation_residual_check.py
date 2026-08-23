"""One-off check: current affiliation-mention resolution stats vs. the
docs/ROADMAP_2026.md A12 residual-tail claim (~14 institutions / ~60 mentions
with no Q-ID). Reads conferences.db + authority_ids.json + geography.json.
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publication_helpers import normalize_affiliation, load_authority_overrides

conn = sqlite3.connect("conferences.db")
cur = conn.cursor()
cur.execute(
    "SELECT affiliation_text_raw, organization_id FROM presentation_person "
    "WHERE affiliation_text_raw IS NOT NULL AND TRIM(affiliation_text_raw) != ''"
)
rows = cur.fetchall()

overrides = load_authority_overrides()
orgs = overrides["organizations"]
geo = json.load(open("assets/data/geography.json", encoding="utf-8"))
city_names = set()
if isinstance(geo, dict):
    for key in ("cities", "aliases"):
        block = geo.get(key)
        if isinstance(block, dict):
            city_names.update(k.lower() for k in block.keys())
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and item.get("name"):
                    city_names.add(str(item["name"]).lower())

total = len(rows)
not_stated = 0
org_resolved_with_qid = 0
org_resolved_no_qid = 0
city_like = 0
unresolved = Counter()

for raw, org_id in rows:
    text = (raw or "").strip()
    low = text.lower()
    if not text or "не указана" in low or low in ("n/a", "-", "unspecified", "independent", "независим"):
        not_stated += 1
        continue
    canon = normalize_affiliation(text)
    if canon:
        auth = orgs.get(canon, {})
        if auth.get("wikidata") or auth.get("ror"):
            org_resolved_with_qid += 1
        else:
            org_resolved_no_qid += 1
        continue
    # crude city check: any known city token appears in the raw text
    if any(c in low for c in city_names):
        city_like += 1
        continue
    unresolved[text] += 1

print(f"total mentions: {total}")
print(f"not stated (Не указана / blank): {not_stated}")
print(f"org resolved WITH Q-ID/ROR: {org_resolved_with_qid}")
print(f"org resolved WITHOUT Q-ID/ROR: {org_resolved_no_qid}")
print(f"city-name matched (not org-resolved): {city_like}")
print(f"truly unresolved distinct strings: {len(unresolved)}, mentions: {sum(unresolved.values())}")
print()
print("All unresolved affiliation strings:")
for text, n in unresolved.most_common(len(unresolved)):
    print(f"  {n:4d}  {text}")

print()
print(f"authority_ids.json organizations total: {len(orgs)}")
missing_qid = [k for k, v in orgs.items() if not (v.get("wikidata") or v.get("ror"))]
print(f"organizations WITHOUT wikidata/ror: {missing_qid}")
