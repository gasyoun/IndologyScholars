#!/usr/bin/env python3
"""
fetch_openalex_birthyears_v2.py

Revised OpenAlex birth-year proxy lookup with stricter filtering.
Process top 60 rows of rinc_lookup_queue.csv.

Filter accepts ONLY if ALL conditions hold:
1. works_count >= 5
2. earliest publication_year >= 2015
3. birth_year_estimate = first_pub_year - 25, within [1960, 2005]

Overwrites:
- analytics_output/rinc_lookup_queue.csv (top 60 rows only)
- analytics_output/birth_year_proxy_estimates.csv (full replacement)
"""

import csv
import sys
import json
import time
import requests
from urllib.parse import quote
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# User-Agent
USER_AGENT = "IndologyScholars-research/0.3 (mailto:gasyoun@gmail.com)"
OPENALEX_API = "https://api.openalex.org"

# Target directory
ANALYTICS_DIR = Path(__file__).parent.parent / "analytics_output"
INPUT_CSV = ANALYTICS_DIR / "rinc_lookup_queue.csv"
OUTPUT_CSV = ANALYTICS_DIR / "rinc_lookup_queue.csv"
ESTIMATES_CSV = ANALYTICS_DIR / "birth_year_proxy_estimates.csv"

def get_author_by_name(name):
    """Search OpenAlex for author by name, return best RU-affiliated match or None."""
    if not name or name.strip() == "":
        return None

    try:
        url = f"{OPENALEX_API}/authors?search={quote(name)}"
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "results" not in data or len(data["results"]) == 0:
            return None

        # Find best RU-affiliated author
        for author in data["results"]:
            if author.get("last_known_institution"):
                inst = author["last_known_institution"]
                if inst.get("country_code") == "RU":
                    return author

        # No RU affiliation found, return first (but mark as ambiguous)
        return data["results"][0] if data["results"] else None

    except requests.RequestException as e:
        print(f"Error fetching author {name}: {e}", file=sys.stderr)
        return None

def get_earliest_publication_year(author_id):
    """
    Fetch earliest publication_year from OpenAlex works_api_url.
    Returns (year, works_count) or (None, 0) on error.
    """
    if not author_id:
        return None, 0

    try:
        # The author object should have works_api_url
        url = f"{OPENALEX_API}/works?filter=author.id:{author_id}&sort=publication_year:asc&per-page=1"
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        works_count = data.get("meta", {}).get("count", 0)

        if "results" in data and len(data["results"]) > 0:
            first_work = data["results"][0]
            year = first_work.get("publication_year")
            return year, works_count

        return None, works_count

    except requests.RequestException as e:
        print(f"Error fetching works for {author_id}: {e}", file=sys.stderr)
        return None, 0

def process_row(row_dict):
    """
    Process a single row. Return updated row_dict with new estimates or rejection notes.

    Returns tuple: (updated_row, should_include_in_estimates)
    """
    display_name = row_dict.get("display_name", "").strip()
    openalex_query = row_dict.get("openalex_query", "").strip()

    # Skip if already has ambiguous_no_RU or similar hard rejects
    notes = row_dict.get("notes", "").strip()
    if notes in ["no_match", "ambiguous_no_RU", "no_publication_year"]:
        # Don't re-process these
        return row_dict, False

    # Skip if already marked as a v1 estimate (only re-process if first_publication_source == "openalex")
    # Actually, per instructions: "if a row already shows first_publication_source = "openalex" from v1, still re-process"
    # So we'll only skip if it's explicitly marked as rejected_filter
    if notes and notes.startswith("rejected_filter"):
        # This was already rejected in v2, keep it
        return row_dict, False

    # Query OpenAlex
    search_name = openalex_query if openalex_query else display_name
    author = get_author_by_name(search_name)

    if not author:
        row_dict["notes"] = "no_match"
        row_dict["birth_year_estimate"] = ""
        row_dict["first_publication_year"] = ""
        row_dict["first_publication_source"] = ""
        return row_dict, False

    author_id = author.get("id")
    works_count = author.get("works_count", 0)

    # Check 1: works_count >= 5
    if works_count < 5:
        row_dict["notes"] = f"rejected_filter:low_works_count={works_count}"
        row_dict["birth_year_estimate"] = ""
        row_dict["first_publication_year"] = ""
        row_dict["first_publication_source"] = ""
        return row_dict, False

    # Get earliest publication year
    first_pub_year, _ = get_earliest_publication_year(author_id)

    if not first_pub_year:
        row_dict["notes"] = "rejected_filter:no_pub_year"
        row_dict["birth_year_estimate"] = ""
        row_dict["first_publication_year"] = ""
        row_dict["first_publication_source"] = ""
        return row_dict, False

    # Check 2: earliest publication_year >= 2015
    if first_pub_year < 2015:
        row_dict["notes"] = f"rejected_filter:pub_year_pre_2015={first_pub_year}"
        row_dict["birth_year_estimate"] = ""
        row_dict["first_publication_year"] = ""
        row_dict["first_publication_source"] = ""
        return row_dict, False

    # Calculate birth estimate
    birth_estimate = first_pub_year - 25

    # Check 3: birth_estimate within [1960, 2005]
    if not (1960 <= birth_estimate <= 2005):
        row_dict["notes"] = f"rejected_filter:birth_estimate_out_of_range={birth_estimate}"
        row_dict["birth_year_estimate"] = ""
        row_dict["first_publication_year"] = ""
        row_dict["first_publication_source"] = ""
        return row_dict, False

    # All checks passed!
    row_dict["birth_year_estimate"] = str(birth_estimate)
    row_dict["first_publication_year"] = str(first_pub_year)
    row_dict["first_publication_source"] = "openalex"
    row_dict["notes"] = ""

    # Return as estimate row (include in estimates CSV)
    # Add works_count to estimate row
    estimate_row = {
        "person_id": row_dict["person_id"],
        "display_name": display_name,
        "n_talks": row_dict.get("n_talks", ""),
        "first_publication_year": str(first_pub_year),
        "birth_year_estimate": str(birth_estimate),
        "openalex_author_id": author_id,
        "works_count": str(works_count)
    }

    return row_dict, estimate_row

def main():
    # Load queue CSV
    rows = []
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows from {INPUT_CSV}", file=sys.stderr)

    # Process only top 60 rows
    top_60_rows = rows[:60]
    rest_rows = rows[60:]

    accepted_count = 0
    rejected_reasons = {}
    estimate_rows = []

    for i, row in enumerate(top_60_rows):
        print(f"Processing {i+1}/60: {row.get('display_name', '')}", file=sys.stderr)
        updated_row, estimate = process_row(row)
        rows[i] = updated_row

        if estimate:
            accepted_count += 1
            estimate_rows.append(estimate)
        else:
            notes = updated_row.get("notes", "")
            if notes.startswith("rejected_filter:"):
                reason = notes.replace("rejected_filter:", "")
                reason_key = reason.split("=")[0]  # Extract base reason
                rejected_reasons[reason_key] = rejected_reasons.get(reason_key, 0) + 1

        # Rate limiting
        time.sleep(0.2)

    # Write updated queue CSV
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        if rows:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}", file=sys.stderr)

    # Write estimates CSV
    with open(ESTIMATES_CSV, "w", encoding="utf-8", newline="") as f:
        if estimate_rows:
            fieldnames = ["person_id", "display_name", "n_talks", "first_publication_year", "birth_year_estimate", "openalex_author_id", "works_count"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(estimate_rows)

    print(f"Wrote {len(estimate_rows)} estimates to {ESTIMATES_CSV}", file=sys.stderr)

    # Summary
    print("\n=== SUMMARY ===", file=sys.stderr)
    print(f"Accepted: {accepted_count}/60", file=sys.stderr)
    print(f"Rejected: {60 - accepted_count}/60", file=sys.stderr)
    print(f"Rejection reasons: {rejected_reasons}", file=sys.stderr)

    # Show top 5 by n_talks
    if estimate_rows:
        print("\n=== TOP 5 BY N_TALKS ===", file=sys.stderr)
        sorted_estimates = sorted(estimate_rows, key=lambda x: int(x.get("n_talks", 0)), reverse=True)
        for i, est in enumerate(sorted_estimates[:5]):
            print(f"{i+1}. {est['display_name']} (n_talks={est['n_talks']}, first_pub={est['first_publication_year']}, birth_est={est['birth_year_estimate']}, works={est['works_count']})", file=sys.stderr)

if __name__ == "__main__":
    main()
