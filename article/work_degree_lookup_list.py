"""Build the priority list for the degree web-lookup (corr.md #9).

Outputs article/hypothesis_output/degree_lookup_queue.csv with, for each
cross-cohort scholar (appeared on BOTH series), the disambiguation hints a
web search needs: full Russian name, birth year, last-known institution.
Read-only on conferences.db.
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
ZOGRAF, ROERICH = 1, 2

INST_TOKENS = ["ран", "университет", "институт", "ивр", "маэ", "музей", "рггу",
               "вшэ", "спбгу", "мгу", "рудн", "кафедр", "академи", "центр",
               "university", "institute", "museum"]


def has_inst(a: str) -> bool:
    return bool(a) and any(t in a.lower() for t in INST_TOKENS)


def main():
    c = sqlite3.connect(str(DB))
    rows = c.execute(
        """
        SELECT pp.person_id, p.display_name, p.full_name_ru, p.birth_year,
               p.death_year, e.event_series_id, e.year, pp.affiliation_text_raw
        FROM presentation_person pp
        JOIN person p            ON p.person_id = pp.person_id
        JOIN presentation pr     ON pr.presentation_id = pp.presentation_id
        JOIN session s           ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed        ON ed.event_day_id = edv.event_day_id
        JOIN event e             ON e.event_id = ed.event_id
        """
    ).fetchall()
    c.close()

    info = defaultdict(lambda: {"name": "", "ru": "", "by": "", "dy": "",
                                "series": set(), "n": 0, "inst": []})
    for pid, name, ru, by, dy, sid, year, aff in rows:
        r = info[pid]
        r["name"] = name; r["ru"] = ru or name; r["by"] = by or ""; r["dy"] = dy or ""
        r["series"].add(sid); r["n"] += 1
        if has_inst(aff):
            r["inst"].append((year, aff.strip()))

    cross = [(pid, r) for pid, r in info.items() if {ZOGRAF, ROERICH} <= r["series"]]
    cross.sort(key=lambda x: -x[1]["n"])

    out = []
    for pid, r in cross:
        last_inst = sorted(r["inst"], reverse=True)[0][1] if r["inst"] else ""
        out.append({
            "person_id": pid,
            "display_name": r["name"],
            "full_name_ru": r["ru"],
            "birth_year": r["by"],
            "death_year": r["dy"],
            "n_talks": r["n"],
            "last_known_institution": last_inst,
            "degree": "", "degree_year": "", "degree_source_url": "",
            "confidence": "", "verified": "",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    fields = ["person_id", "display_name", "full_name_ru", "birth_year", "death_year",
              "n_talks", "last_known_institution", "degree", "degree_year",
              "degree_source_url", "confidence", "verified"]
    with (OUT / "degree_lookup_queue.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)

    print(f"Cross-cohort scholars (both series): {len(out)}")
    for r in out:
        print(f"  {r['display_name'][:32]:32} by={str(r['birth_year']):6} "
              f"n={r['n_talks']:2}  inst={r['last_known_institution'][:40]}")
    print("\nWrote degree_lookup_queue.csv")


if __name__ == "__main__":
    main()
