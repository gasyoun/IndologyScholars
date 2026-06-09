"""Inject high-confidence OpenAlex matches into authority_ids.json.

Reads analytics_output/openalex_author_candidates.csv,
for rows with relevance_score >= 0.8 (or custom threshold),
extracts the openalex_id and optional orcid/wikidata from the
OpenAlex API, and adds them to authority_ids.json with
confidence='candidate' (never 'confirmed' — human review still needed).

Usage:
  python tools/inject_openalex_matches.py [--threshold 0.8] [--dry-run]
"""

import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8")

TODAY = date.today().isoformat()

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_CSV = ROOT / "analytics_output" / "openalex_author_candidates.csv"
AUTHORITY_IDS = ROOT / "authority_ids.json"

OPENALEX_BASE = "https://api.openalex.org"
USER_AGENT = "IndologyScholars-research/0.4 (mailto:gasyoun@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
RATE_LIMIT_S = 0.3
API_TIMEOUT = 30


def fetch_author(openalex_id):
    url = f"{OPENALEX_BASE}/authors/{openalex_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=API_TIMEOUT)
        time.sleep(RATE_LIMIT_S)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"    [WARN] API lookup failed for {openalex_id}: {exc}", file=sys.stderr)
        return {}


def main():
    threshold = 0.8
    dry_run = False
    if "--threshold" in sys.argv:
        idx = sys.argv.index("--threshold")
        threshold = float(sys.argv[idx + 1])
    if "--dry-run" in sys.argv:
        dry_run = True

    if not CANDIDATES_CSV.exists():
        print(f"Not found: {CANDIDATES_CSV}")
        sys.exit(1)

    rows = list(csv.DictReader(open(CANDIDATES_CSV, encoding="utf-8")))
    high = [r for r in rows if float(r.get("relevance_score", 0)) >= threshold]
    print(f"Total candidates: {len(rows)}")
    print(f"High-confidence (>= {threshold}): {len(high)}")

    if not high:
        print("No high-confidence matches found.")
        return

    authority = json.loads(AUTHORITY_IDS.read_text(encoding="utf-8"))
    persons = authority.setdefault("persons", {})

    added = 0
    changed = 0
    for r in high:
        pid = r["person_id"]
        oa_id = r["openalex_id"].split("/")[-1] if "/" in r["openalex_id"] else r["openalex_id"]

        if pid not in persons:
            persons[pid] = {}

        existing = persons[pid]
        if existing.get("openalex"):
            oa_existing = existing["openalex"]
            if not existing.get("orcid") or not existing.get("wikidata"):
                author_data = fetch_author(oa_existing)
                ids_block = author_data.get("ids", {}) if author_data else {}
                if ids_block.get("orcid") and not existing.get("orcid"):
                    existing["orcid"] = ids_block["orcid"].split("/")[-1]
                    print(f"  [+] {pid}: backfilled orcid:{existing['orcid']}")
                    changed += 1
                if ids_block.get("wikidata") and not existing.get("wikidata"):
                    existing["wikidata"] = ids_block["wikidata"].split("/")[-1]
                    print(f"  [+] {pid}: backfilled wikidata:{existing['wikidata']}")
                    changed += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] {pid}: {r['local_display_name'][:40]} -> openalex:{oa_id} (score={r['relevance_score']})")
            continue

        author_data = fetch_author(oa_id)
        ids_block = author_data.get("ids", {}) if author_data else {}

        existing["openalex"] = oa_id
        if ids_block.get("orcid"):
            existing["orcid"] = ids_block["orcid"].split("/")[-1]
        if ids_block.get("wikidata"):
            existing["wikidata"] = ids_block["wikidata"].split("/")[-1]
        existing.setdefault("confidence", "candidate")
        existing.setdefault("checked_at", TODAY)
        added += 1

        extras = []
        if existing.get("orcid"):
            extras.append(f"orcid:{existing['orcid']}")
        if existing.get("wikidata"):
            extras.append(f"wikidata:{existing['wikidata']}")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        print(f"  [+] {pid}: {r['local_display_name'][:40]} -> openalex:{oa_id}{extra_str}")

    if not dry_run and (added > 0 or changed > 0):
        with open(AUTHORITY_IDS, "w", encoding="utf-8") as f:
            json.dump(authority, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\nInjected {added} matches, {changed} enrichments into {AUTHORITY_IDS}")
        print("Review each with confidence='candidate' before changing to 'confirmed'.")
    elif added == 0 and changed == 0:
        print("No new matches or enrichments to apply.")


if __name__ == "__main__":
    main()
