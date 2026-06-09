"""Resume OpenAlex candidate search for scholars not yet queried.

Reads the existing analytics_output/openalex_author_candidates.csv,
identifies which scholars have already been tried, and only queries
the remaining ones. Appends results to the existing CSV.

Usage:
  python scratch/openalex_author_candidates.py --resume
"""

import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
SITE_DATA = ROOT / "site_data.json"
AUTHORITY_IDS = ROOT / "authority_ids.json"
OUTPUT_CSV = ROOT / "analytics_output" / "openalex_author_candidates.csv"

OPENALEX_BASE = "https://api.openalex.org"
USER_AGENT = "IndologyScholars-research/0.4 (mailto:gasyoun@gmail.com)"
RATE_LIMIT_S = 0.3
MAX_CANDIDATES = 5
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
TIMEOUT = 90


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def openalex_search(query):
    if not query or not query.strip():
        return []
    url = f"{OPENALEX_BASE}/authors?search={quote(query)}&per-page={MAX_CANDIDATES}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as exc:
        print(f"  [WARN] {exc}", file=sys.stderr)
        return []
    finally:
        time.sleep(RATE_LIMIT_S)


def score_candidate(candidate, latin_name):
    score = 0.0
    inst = candidate.get("last_known_institution") or {}
    if inst.get("country_code") == "RU":
        score += 0.4
    disp = (candidate.get("display_name") or "").lower()
    if latin_name:
        latin_parts = latin_name.lower().split()
        if latin_parts and latin_parts[0] in disp:
            score += 0.2
    if (candidate.get("works_count") or 0) >= 3:
        score += 0.2
    if candidate.get("affiliations"):
        score += 0.1
    return round(min(score, 1.0), 2)


def main():
    data = load_site_data()
    authority = json.loads(AUTHORITY_IDS.read_text(encoding="utf-8"))
    persons_auth = authority.get("persons", {})

    # Load already-queried person IDs from existing CSV
    already = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                already.add(row["person_id"])

    new_rows = []
    queried = 0
    skipped_auth = 0
    skipped_done = 0

    scholars = data.get("scholars", [])
    remaining = [s for s in scholars if s["id"] not in already and not persons_auth.get(s["id"], {}).get("openalex")]
    print(f"Total: {len(scholars)} | Already done: {len(already)} | Skipped (has openalex): {len(scholars) - len(remaining) - len(already)} | Remaining: {len(remaining)}")

    for scholar in remaining:
        pid = scholar["id"]
        full_name_ru = scholar.get("full_name_ru") or scholar.get("name") or ""
        latin_name = persons_auth.get(pid, {}).get("preferred_latin_name", "") or ""
        total_talks = scholar.get("total_talks", 0)

        queries = []
        if full_name_ru and not re.match(r"^[А-ЯЁA-Z]\.", full_name_ru.split()[0] if full_name_ru.split() else [""]):
            queries.append(("cyrillic_fullname", full_name_ru))
        if latin_name:
            queries.append(("latin_name", latin_name))
        if not queries:
            queries.append(("display_name", full_name_ru))

        queried += 1
        print(f"[{queried:3d}/{len(remaining)}] {pid}: {full_name_ru[:50]} ({total_talks} talks)")

        for q_type, q_str in queries:
            candidates = openalex_search(q_str)
            if not candidates:
                print(f"       [{q_type}] No results")
                continue

            print(f"       [{q_type}] {len(candidates)} result(s)")
            for cand in candidates:
                cand_id = cand.get("id", "")
                cand_name = cand.get("display_name", "")
                works_count = cand.get("works_count", 0)
                inst = cand.get("last_known_institution") or {}
                inst_name = inst.get("display_name", "")
                inst_country = inst.get("country_code", "")
                is_ru = (inst_country == "RU")
                rel_score = score_candidate(cand, latin_name)

                new_rows.append({
                    "person_id": pid,
                    "local_display_name": full_name_ru,
                    "local_latin_name": latin_name,
                    "total_talks": total_talks,
                    "query_type": q_type,
                    "query_string": q_str,
                    "openalex_id": cand_id,
                    "openalex_name": cand_name,
                    "works_count": works_count,
                    "top_affiliation_name": inst_name,
                    "top_affiliation_country": inst_country,
                    "is_ru_affiliated": "yes" if is_ru else "no",
                    "relevance_score": rel_score,
                    "manual_status": "todo",
                    "notes": "",
                })

    # Append to existing CSV
    fieldnames = [
        "person_id", "local_display_name", "local_latin_name", "total_talks",
        "query_type", "query_string",
        "openalex_id", "openalex_name", "works_count",
        "top_affiliation_name", "top_affiliation_country", "is_ru_affiliated",
        "relevance_score", "manual_status", "notes",
    ]
    write_header = not OUTPUT_CSV.exists()
    with open(OUTPUT_CSV, "a" if not write_header else "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerows(new_rows)

    print(f"\nDone. Newly queried: {len(remaining)} scholars.")
    print(f"New rows: {len(new_rows)}  ->  {OUTPUT_CSV}")
    print(f"Next: python tools/inject_openalex_matches.py")


if __name__ == "__main__":
    main()
