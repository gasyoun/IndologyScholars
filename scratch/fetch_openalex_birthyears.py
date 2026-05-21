#!/usr/bin/env python3
"""
Fetch birth-year estimates for Russian Indology scholars via OpenAlex API.

Input: analytics_output/rinc_lookup_queue.csv (top 60 rows)
Output:
  - Modified rinc_lookup_queue.csv with filled birth_year_estimate column
  - analytics_output/birth_year_proxy_estimates.csv (successful estimates only)

Procedure:
  1. Query OpenAlex authors API with scholar name
  2. Disambiguate: pick RU-affiliated author with highest works_count
  3. Fetch earliest work publication year
  4. Estimate: birth_year = first_pub_year - 25
  5. Sanity check: clamp to [1900, 2005]
"""

import sys
import csv
import time
import re
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

OPENALEX_API = "https://api.openalex.org"
USER_AGENT = "IndologyScholars-research/0.3 (mailto:gasyoun@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT}
RATE_LIMIT_DELAY = 0.15  # seconds between requests
MAX_ROWS = 60

def extract_surname_cyrillic(full_name):
    """Extract the main surname (first word) in Cyrillic for matching."""
    words = full_name.split()
    if words:
        return words[0].lower()
    return ""

def is_russian_author(author):
    """Check if author has Russian affiliation."""
    # Check last_known_institutions
    if author.get("last_known_institutions"):
        for inst in author["last_known_institutions"]:
            if inst.get("country_code") == "RU":
                return True
    # Check affiliations
    if author.get("affiliations"):
        for aff in author["affiliations"]:
            if aff.get("institution", {}).get("country_code") == "RU":
                return True
    return False

def contains_cyrillic_surname(author, surname_cyrillic):
    """Check if author name contains the Cyrillic surname."""
    display = author.get("display_name", "").lower()
    alt_names = [n.lower() for n in author.get("alternative_names", [])]
    all_names = [display] + alt_names
    return any(surname_cyrillic in name for name in all_names)

def pick_author(results, query_name):
    """Pick best author candidate from OpenAlex results."""
    if not results:
        return None

    surname_cyrillic = extract_surname_cyrillic(query_name)

    # Priority 1: RU-affiliated authors, sort by works_count descending
    ru_authors = [a for a in results if is_russian_author(a)]
    if ru_authors:
        ru_authors.sort(key=lambda a: a.get("works_count", 0), reverse=True)
        return ru_authors[0]

    # Priority 2: Any result containing the Cyrillic surname
    surname_matches = [a for a in results if contains_cyrillic_surname(a, surname_cyrillic)]
    if surname_matches:
        surname_matches.sort(key=lambda a: a.get("works_count", 0), reverse=True)
        return surname_matches[0]

    return None

def fetch_earliest_work_year(works_api_url):
    """Fetch earliest publication year from author's works."""
    time.sleep(RATE_LIMIT_DELAY)
    try:
        url = f"{works_api_url}&sort=publication_year:asc&per_page=1"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("results") and data["results"][0].get("publication_year"):
            return data["results"][0]["publication_year"]

        # Fallback: try per_page=5
        url = f"{works_api_url}&sort=publication_year:asc&per_page=5"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for work in data.get("results", []):
            if work.get("publication_year"):
                return work["publication_year"]

        return None
    except Exception as e:
        print(f"  Error fetching works: {e}", file=sys.stderr)
        return None

def query_openalex_author(openalex_url):
    """Query OpenAlex authors API. Return (author_dict, author_id) or (None, None)."""
    time.sleep(RATE_LIMIT_DELAY)
    try:
        resp = requests.get(openalex_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        return results
    except Exception as e:
        print(f"  Error querying OpenAlex: {e}", file=sys.stderr)
        return []

def estimate_birth_year(first_pub_year):
    """Estimate birth year from first publication year."""
    if not first_pub_year or first_pub_year < 1900 or first_pub_year > 2025:
        return None, f"implausible_pub_year={first_pub_year}"

    estimate = first_pub_year - 25
    if estimate < 1900 or estimate > 2005:
        return None, f"implausible_estimate={estimate}"

    return estimate, None

def main():
    queue_path = Path("C:/Users/user/Documents/GitHub/IndologyScholars/analytics_output/rinc_lookup_queue.csv")
    output_path = Path("C:/Users/user/Documents/GitHub/IndologyScholars/analytics_output/birth_year_proxy_estimates.csv")

    # Read CSV
    rows = []
    fieldnames = []
    with open(queue_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Add birth_year_estimate column if missing
    if "birth_year_estimate" not in fieldnames:
        fieldnames.append("birth_year_estimate")

    # Process top 60 rows
    estimates = []
    stats = {"success": 0, "no_match": 0, "ambiguous_no_ru": 0, "implausible": 0}

    for i, row in enumerate(rows[:MAX_ROWS]):
        person_id = row["person_id"]
        display_name = row["display_name"]
        openalex_url = row["openalex_url"]
        n_talks = row["n_talks"]

        # Skip if already processed
        if row.get("first_publication_source") == "openalex":
            continue

        if (i + 1) % 10 == 0:
            print(f"Progress: {i+1}/{MAX_ROWS}")

        # Query OpenAlex
        results = query_openalex_author(openalex_url)

        if not results:
            row["notes"] = "no_match"
            continue

        # Pick best author
        author = pick_author(results, display_name)
        if not author:
            row["notes"] = "ambiguous_no_RU"
            continue

        # Fetch earliest work
        works_api_url = author.get("works_api_url")
        if not works_api_url:
            row["notes"] = "no_works_api"
            continue

        first_pub_year = fetch_earliest_work_year(works_api_url)

        if not first_pub_year:
            row["notes"] = "no_publication_year"
            continue

        # Estimate birth year
        estimate, implausible_note = estimate_birth_year(first_pub_year)

        row["first_publication_year"] = str(first_pub_year)
        row["first_publication_source"] = "openalex"

        if implausible_note:
            row["notes"] = implausible_note
            stats["implausible"] += 1
        else:
            row["birth_year_estimate"] = str(estimate)
            row["notes"] = ""
            stats["success"] += 1

            # Record successful estimate
            estimates.append({
                "person_id": person_id,
                "display_name": display_name,
                "n_talks": n_talks,
                "first_publication_year": str(first_pub_year),
                "birth_year_estimate": str(estimate),
                "openalex_author_id": author.get("id", ""),
            })

    # Count no_match, ambiguous_no_ru
    for row in rows[:MAX_ROWS]:
        if row.get("notes") == "no_match":
            stats["no_match"] += 1
        elif row.get("notes") == "ambiguous_no_RU":
            stats["ambiguous_no_ru"] += 1

    # Write updated CSV back
    with open(queue_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Write estimates CSV
    if estimates:
        estimate_fieldnames = ["person_id", "display_name", "n_talks", "first_publication_year", "birth_year_estimate", "openalex_author_id"]
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=estimate_fieldnames)
            writer.writeheader()
            writer.writerows(estimates)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Processed: {MAX_ROWS} rows")
    print(f"Success (estimated): {stats['success']}")
    print(f"No match: {stats['no_match']}")
    print(f"Ambiguous (no RU affiliation): {stats['ambiguous_no_ru']}")
    print(f"Implausible pub year: {stats['implausible']}")
    print(f"Other failures: {MAX_ROWS - stats['success'] - stats['no_match'] - stats['ambiguous_no_ru'] - stats['implausible']}")

    # Top 5 by n_talks
    if estimates:
        estimates.sort(key=lambda x: int(x["n_talks"]), reverse=True)
        print("\nTop 5 successful estimates by n_talks:")
        for j, est in enumerate(estimates[:5], 1):
            print(f"  {j}. {est['display_name']} ({est['n_talks']} talks) → birth_year_estimate: {est['birth_year_estimate']}")

    print(f"\nEstimates CSV: {output_path}")
    print(f"Updated queue CSV: {queue_path}")

if __name__ == "__main__":
    main()
