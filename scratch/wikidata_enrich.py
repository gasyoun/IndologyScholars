"""Enrich master records from Wikidata, keyed by Q-ID.

``enwiki_bridge.py`` back-fills Q-IDs but not lifespans, so many people carry a
Q-ID with ``birth_year=null`` — which makes ``crossref_nonparticipants.py``
mis-file them as living "significant absences" (e.g. Бётлингк, d. 1904). This
pass turns each Q-ID into a birth/death year using the Wikidata REST endpoint
``Special:EntityData/Qxxx.json`` (the docs' "stable" path — query.wikidata.org
SPARQL and the action API are unreliable; the REST file is not).

It only FILLS EMPTY fields — curated values are never overwritten — and writes
atomically, so a partial/blocked run cannot corrupt the master. Wikidata is
unreachable from the CI host, so run this where it resolves (inside .ru it
usually does); unreachable Q-IDs are simply skipped and reported.

Usage:
  python scratch/wikidata_enrich.py            # enrich missing dates
  python scratch/wikidata_enrich.py --dry-run  # report only
  python scratch/wikidata_enrich.py --limit 20 # cap the number of lookups
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import scrape_common as sc

SCRATCH = Path(__file__).resolve().parent
MASTER = SCRATCH / "wikipedia_indologists_expanded.json"
ENTITYDATA = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"


def _year(time_str: str) -> int | None:
    """Wikidata time literal '+1840-01-01T00:00:00Z' → 1840 (BCE → negative)."""
    m = re.match(r"([+-])(\d{4})", time_str or "")
    if not m:
        return None
    year = int(m.group(2))
    return -year if m.group(1) == "-" else year


def parse_entity_dates(doc: dict, qid: str) -> tuple[int | None, int | None]:
    """(birth_year, death_year) from a Special:EntityData JSON document."""
    entity = doc.get("entities", {}).get(qid, {})
    claims = entity.get("claims", {})

    def first_time(pid: str) -> int | None:
        for claim in claims.get(pid, []):
            val = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            y = _year(val.get("time", "")) if isinstance(val, dict) else None
            if y is not None:
                return y
        return None

    return first_time("P569"), first_time("P570")


def fetch_entity(qid: str, *, use_cache: bool) -> dict | None:
    return sc.get_json(ENTITYDATA.format(qid=qid), cache=use_cache, verbose=True)


def main() -> None:
    sc.setup_utf8()
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    use_cache = "--no-cache" not in args
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    if not MASTER.exists():
        print(f"[!] {MASTER} not found.")
        return
    with open(MASTER, "r", encoding="utf-8") as f:
        master = json.load(f)
    people = master.get("people", [])

    todo = [p for p in people
            if p.get("wikidata_qid")
            and (p.get("birth_year") is None or p.get("death_year") is None)]
    if limit:
        todo = todo[:limit]
    print(f"=== Wikidata enrichment ===")
    print(f"  people with a Q-ID and a missing date: {len(todo)}")
    if dry_run:
        print("  (dry run: no fetching, no writing)")
        for p in todo:
            print(f"      {p['wikidata_qid']:<11} {p.get('full_name','')}")
        return

    filled = unreachable = 0
    for p in todo:
        doc = fetch_entity(p["wikidata_qid"], use_cache=use_cache)
        if not doc:
            unreachable += 1
            continue
        b, d = parse_entity_dates(doc, p["wikidata_qid"])
        touched = False
        if p.get("birth_year") is None and b is not None:
            p["birth_year"] = b
            touched = True
        if p.get("death_year") is None and d is not None:
            p["death_year"] = d
            touched = True
        if touched:
            filled += 1
            print(f"      + {p['wikidata_qid']:<11} {p.get('full_name','')}: "
                  f"{p.get('birth_year','?')}–{p.get('death_year') or ''}")

    print(f"\n  enriched: {filled}   unreachable Q-IDs: {unreachable}")
    if filled:
        master["people"] = people
        sc.atomic_write_json(MASTER, master)
        print(f"  wrote {MASTER.name}. Re-run crossref_nonparticipants.py to "
              f"refresh the report (dates now classify correctly).")
    else:
        print("  nothing filled — master unchanged"
              + (" (Wikidata unreachable from here)." if unreachable else "."))


if __name__ == "__main__":
    main()
