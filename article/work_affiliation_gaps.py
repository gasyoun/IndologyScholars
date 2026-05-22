"""Affiliation-gap diagnostics for the PPV article (corr.md #14, #23).

Produces two lists requested by the editor:
  A) scholars with no institutional affiliation in ANY year;
  B) participants of the 2026 Zograf (XLVII) program whose affiliation is
     city-only (a place name, not an institution).

Also dumps the raw 2026 Zograf affiliation strings so the city-only
heuristic can be eyeballed and corrected by hand.

Read-only against conferences.db. Outputs to article/hypothesis_output/.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "conferences.db"
OUT = ROOT / "article" / "hypothesis_output"
OUT.mkdir(parents=True, exist_ok=True)

# Place names that are NOT institutions (corr.md #14: Kaliningrad etc.).
CITY_TOKENS = {
    "москва", "санкт-петербург", "санкт петербург", "спб", "с.-петербург",
    "петербург", "калининград", "новосибирск", "казань", "екатеринбург",
    "владивосток", "уфа", "томск", "элиста", "улан-удэ", "ялта", "нижний новгород",
    "пермь", "воронеж", "ростов-на-дону", "красноярск", "иркутск",
}
# Tokens that mark a real institution.
INST_TOKENS = [
    "ран", "университет", "институт", "ивр", "ив ", "маэ", "музей", "рггу",
    "вшэ", "спбгу", "мгу", "рудн", "кафедр", "академи", "центр", "library",
    "university", "institute", "museum", "лаборатор", "школа", "семинар",
    "фонд", "общество", "ноц", "игитуп", "игиту",
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def classify(aff: str) -> str:
    """Return 'empty', 'city-only', or 'institution'."""
    n = norm(aff)
    if not n:
        return "empty"
    # strip trailing city qualifiers like ", спб" / ", москва"
    core = n
    for c in CITY_TOKENS:
        core = re.sub(rf"[ ,(]+{re.escape(c)}[ ,)]*$", "", core).strip(" ,()")
    if not core or core in CITY_TOKENS:
        return "city-only"
    if any(tok in n for tok in INST_TOKENS):
        return "institution"
    # short, single-word, no institution marker -> treat as place/unknown
    if len(n) <= 18 and "," not in n and " " not in n:
        return "city-only"
    return "institution"


def main() -> None:
    c = sqlite3.connect(str(DB))
    cur = c.cursor()

    series = {r[0]: f"{r[1]} / {r[2]}" for r in cur.execute("SELECT event_series_id, series_name_en, series_name_ru FROM event_series")}

    rows = cur.execute(
        """
        SELECT p.person_id, p.display_name, p.source_url,
               e.year, e.event_series_id, e.ordinal_roman,
               pp.affiliation_text_raw
        FROM presentation_person pp
        JOIN person p              ON p.person_id = pp.person_id
        JOIN presentation pr       ON pr.presentation_id = pp.presentation_id
        JOIN session s             ON s.session_id = pr.session_id
        JOIN event_day_venue edv   ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed          ON ed.event_day_id = edv.event_day_id
        JOIN event e               ON e.event_id = ed.event_id
        """
    ).fetchall()

    by_person: dict[str, dict] = defaultdict(
        lambda: {"name": "", "url": "", "affils": [], "years": set(), "series": set()}
    )
    zograf_2026: list[dict] = []

    for pid, name, url, year, sid, roman, aff in rows:
        rec = by_person[pid]
        rec["name"] = name
        rec["url"] = url or ""
        rec["affils"].append(aff or "")
        rec["years"].add(year)
        rec["series"].add(series.get(sid, str(sid)))
        sname = norm(series.get(sid, ""))
        if year == 2026 and ("зограф" in sname or "zograf" in sname):
            zograf_2026.append({
                "person_id": pid, "display_name": name,
                "affiliation_text_raw": aff or "", "klass": classify(aff or ""),
                "source_url": url or "",
            })

    # List A: no institutional affiliation in ANY year.
    list_a = []
    for pid, rec in by_person.items():
        klasses = {classify(a) for a in rec["affils"]}
        if "institution" not in klasses:
            list_a.append({
                "person_id": pid, "display_name": rec["name"],
                "n_talks": len(rec["affils"]),
                "years": ",".join(str(y) for y in sorted(rec["years"])),
                "series": "|".join(sorted(rec["series"])),
                "raw_affils": " || ".join(sorted({a for a in rec["affils"] if a.strip()})),
                "source_url": rec["url"],
            })
    list_a.sort(key=lambda r: (-r["n_talks"], r["display_name"]))

    with (OUT / "missing_affiliation_ever.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["person_id", "display_name", "n_talks", "years", "series", "raw_affils", "source_url"])
        w.writeheader(); w.writerows(list_a)

    # dedupe 2026 list by person
    seen = {}
    for r in zograf_2026:
        seen.setdefault(r["person_id"], r)
    z26 = sorted(seen.values(), key=lambda r: (r["klass"], r["display_name"]))
    with (OUT / "zograf_2026_affiliations.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["person_id", "display_name", "klass", "affiliation_text_raw", "source_url"])
        w.writeheader(); w.writerows(z26)

    z26_cityonly = [r for r in z26 if r["klass"] in ("city-only", "empty")]

    # Backfill: last-known institutional affiliation from PRIOR years (corr.md #23).
    # Recompute per-person (year -> affiliation) so we can pick the most recent institution.
    per_person_year_aff: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for pid, name, url, year, sid, roman, aff in rows:
        if classify(aff or "") == "institution":
            per_person_year_aff[pid].append((year, aff))

    backfill = []
    for r in z26_cityonly:
        pid = r["person_id"]
        prior = sorted([ya for ya in per_person_year_aff.get(pid, []) if ya[0] < 2026], reverse=True)
        last_inst = prior[0] if prior else None
        backfill.append({
            "person_id": pid,
            "display_name": r["display_name"],
            "city_2026": r["affiliation_text_raw"],
            "last_known_institution": last_inst[1] if last_inst else "",
            "last_known_year": last_inst[0] if last_inst else "",
            "status": "recoverable" if last_inst else "WEB-LOOKUP-NEEDED",
            "source_url": r["source_url"],
        })
    backfill.sort(key=lambda r: (r["status"], r["display_name"]))
    with (OUT / "zograf_2026_historical_affiliation.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["person_id", "display_name", "city_2026", "last_known_institution", "last_known_year", "status", "source_url"])
        w.writeheader(); w.writerows(backfill)

    n_recoverable = sum(1 for b in backfill if b["status"] == "recoverable")
    n_lookup = sum(1 for b in backfill if b["status"] == "WEB-LOOKUP-NEEDED")

    print(f"Total persons: {len(by_person)}")
    print(f"List A (no institutional affiliation EVER): {len(list_a)}")
    print(f"Zograf-2026 participants in DB: {len(z26)}")
    print(f"  of which city-only or empty: {len(z26_cityonly)}")
    print("\n2026 city-only / empty sample:")
    for r in z26_cityonly[:25]:
        print(f"  [{r['klass']:11}] {r['display_name']:30} | {r['affiliation_text_raw']}")
    print(f"\n2026 city-only backfill: {n_recoverable} recoverable from prior years, "
          f"{n_lookup} need web-lookup")
    print("Web-lookup priority (no institution in any prior year):")
    for b in backfill:
        if b["status"] == "WEB-LOOKUP-NEEDED":
            print(f"  {b['display_name']:32} | 2026 city: {b['city_2026']}")
    print("\nWrote: missing_affiliation_ever.csv, zograf_2026_affiliations.csv, "
          "zograf_2026_historical_affiliation.csv")


if __name__ == "__main__":
    main()
