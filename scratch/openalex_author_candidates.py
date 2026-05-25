#!/usr/bin/env python3
"""
scratch/openalex_author_candidates.py

Phase 3 — OpenAlex Candidate Identification
============================================
Iterates through all scholars in site_data.json who currently lack an `openalex`
ID in authority_ids.json.  For each scholar we issue two OpenAlex /authors search
queries (Cyrillic full name, then preferred Latin name) and score the returned
candidates.  Results are written to:

    analytics_output/openalex_author_candidates.csv

IMPORTANT CONSTRAINTS (per archive/plans/sciguide.md):
- No automatic merge of IDs into authority_ids.json.
- No birth-year estimation from first publication year.
- Each candidate must be manually validated before being added.
- Polite rate-limit: 0.2 s delay per HTTP request.
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

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
SITE_DATA = ROOT / "site_data.json"
AUTHORITY_IDS = ROOT / "authority_ids.json"
OUTPUT_CSV = ROOT / "analytics_output" / "openalex_author_candidates.csv"

# ---------------------------------------------------------------------------
# OpenAlex configuration
# ---------------------------------------------------------------------------
OPENALEX_BASE = "https://api.openalex.org"
USER_AGENT = "IndologyScholars-research/0.4 (mailto:gasyoun@gmail.com)"
RATE_LIMIT_S = 0.2   # polite delay between requests
MAX_CANDIDATES = 5   # candidates to inspect per scholar
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Helper: extract Cyrillic surname from full_name_ru
# ---------------------------------------------------------------------------
CYRILLIC_UPPER = re.compile(r"[А-ЯЁ]")

def extract_cyrillic_surname(full_name_ru: str) -> str:
    """Return likely surname from a 'Фамилия Имя Отчество' or 'И.И. Фамилия' string."""
    name = (full_name_ru or "").strip()
    if not name:
        return ""
    parts = name.split()
    if not parts:
        return ""
    # If first part is all-initials style (e.g. "А.В."), surname is last
    if re.match(r"^[А-ЯЁA-Z]\.([А-ЯЁA-Z]\.)?$", parts[0]):
        return parts[-1] if len(parts) >= 2 else ""
    # Standard: first part is surname
    return parts[0]


# ---------------------------------------------------------------------------
# OpenAlex API: search authors
# ---------------------------------------------------------------------------
def openalex_search(query: str) -> list:
    """Return up to MAX_CANDIDATES raw author objects from OpenAlex."""
    if not query or not query.strip():
        return []
    url = f"{OPENALEX_BASE}/authors?search={quote(query)}&per-page={MAX_CANDIDATES}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.RequestException as exc:
        print(f"  [WARN] OpenAlex request failed for '{query}': {exc}", file=sys.stderr)
        return []
    finally:
        time.sleep(RATE_LIMIT_S)


# ---------------------------------------------------------------------------
# Score a single OpenAlex author result
# ---------------------------------------------------------------------------
def score_candidate(candidate: dict, cyrillic_surname: str, latin_name: str) -> float:
    """
    Heuristic scoring (0.0 – 1.0) for match relevance.

    Signals:
      +0.4  last_known_institution.country_code == "RU"
      +0.2  display_name contains the Cyrillic surname (transliterated check skipped —
             reviewer does that manually)
      +0.2  works_count >= 3
      +0.1  affiliations list non-empty
      +0.1  display_name_alternatives contains a name fragment matching the query
    """
    score = 0.0
    inst = candidate.get("last_known_institution") or {}
    if inst.get("country_code") == "RU":
        score += 0.4
    disp = (candidate.get("display_name") or "").lower()
    if latin_name:
        # Check if Latin surname appears in display name
        latin_parts = latin_name.lower().split()
        if latin_parts and latin_parts[0] in disp:
            score += 0.2
    if (candidate.get("works_count") or 0) >= 3:
        score += 0.2
    if candidate.get("affiliations"):
        score += 0.1
    alternatives = candidate.get("display_name_alternatives") or []
    if latin_name and latin_name.strip():
        latin_first = latin_name.lower().split()[0]
        if any(latin_first in a.lower() for a in alternatives if a):
            score += 0.1
    return round(min(score, 1.0), 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Load site_data and authority_ids
    with open(SITE_DATA, encoding="utf-8") as f:
        data = json.load(f)
    with open(AUTHORITY_IDS, encoding="utf-8") as f:
        authority = json.load(f)

    persons_auth = authority.get("persons", {})
    scholars = data.get("scholars", [])

    rows = []
    skipped = 0
    queried = 0

    for scholar in scholars:
        pid = scholar["id"]
        person_auth = persons_auth.get(pid, {})

        # Skip if already has openalex
        if person_auth.get("openalex"):
            skipped += 1
            continue

        full_name_ru = scholar.get("full_name_ru") or scholar.get("name") or ""
        display_name  = scholar.get("display_name") or scholar.get("name") or ""
        latin_name    = person_auth.get("preferred_latin_name", "") or ""
        total_talks   = scholar.get("total_talks", 0)

        # Build search queries: prefer full Cyrillic name, fallback to Latin
        queries = []
        if full_name_ru and not re.match(r"^[А-ЯЁA-Z]\.", full_name_ru.split()[0]):
            # Has a real full Cyrillic name (not initials-only)
            queries.append(("cyrillic_fullname", full_name_ru))
        if latin_name:
            queries.append(("latin_name", latin_name))
        if not queries:
            # Initials-only — use display name as last resort
            queries.append(("display_name", display_name))

        surname_ru = extract_cyrillic_surname(full_name_ru or display_name)
        queried += 1

        print(f"[{queried:3d}] {pid}: {full_name_ru or display_name!r} ({total_talks} talks)")

        for q_type, q_str in queries:
            candidates = openalex_search(q_str)
            if not candidates:
                print(f"       [{q_type}] No results for '{q_str}'")
                continue

            print(f"       [{q_type}] {len(candidates)} result(s) for '{q_str}'")

            for cand in candidates:
                cand_id      = cand.get("id", "")
                cand_name    = cand.get("display_name", "")
                works_count  = cand.get("works_count", 0)
                inst         = cand.get("last_known_institution") or {}
                inst_name    = inst.get("display_name", "")
                inst_country = inst.get("country_code", "")
                is_ru        = (inst_country == "RU")
                rel_score    = score_candidate(cand, surname_ru, latin_name)

                rows.append({
                    "person_id":            pid,
                    "local_display_name":   full_name_ru or display_name,
                    "local_latin_name":     latin_name,
                    "total_talks":          total_talks,
                    "query_type":           q_type,
                    "query_string":         q_str,
                    "openalex_id":          cand_id,
                    "openalex_name":        cand_name,
                    "works_count":          works_count,
                    "top_affiliation_name": inst_name,
                    "top_affiliation_country": inst_country,
                    "is_ru_affiliated":     "yes" if is_ru else "no",
                    "relevance_score":      rel_score,
                    "manual_status":        "todo",  # reviewers fill: confirmed / rejected / ambiguous
                    "notes":                "",
                })

    # Write CSV
    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    fieldnames = [
        "person_id", "local_display_name", "local_latin_name", "total_talks",
        "query_type", "query_string",
        "openalex_id", "openalex_name", "works_count",
        "top_affiliation_name", "top_affiliation_country", "is_ru_affiliated",
        "relevance_score", "manual_status", "notes",
    ]
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Queried {queried} scholars, skipped {skipped} (already have openalex).")
    print(f"Candidate rows written: {len(rows)}")
    print(f"Output: {OUTPUT_CSV}")
    print()
    print("NEXT STEP: Open analytics_output/openalex_author_candidates.csv,")
    print("review each row, and for confirmed matches add 'openalex' to authority_ids.json")
    print("with confidence='confirmed', checked_at='YYYY-MM-DD'.")


if __name__ == "__main__":
    main()
