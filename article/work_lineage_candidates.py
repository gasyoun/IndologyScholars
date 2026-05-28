"""Heuristic generator of advisor / student candidate pairs.

Issue #9 ("Genealogy and networks"). This script does **not** produce verified
relationships. It scans the corpus for plausible advisor / student pairs using
two signals — co-authorship across multiple years and age gap — and writes
``analytics_output/lineage_candidates.csv`` for a maintainer to review and copy
verified rows into ``curation/teacher_student.csv``.

Heuristic
---------
A pair (A, B) is emitted as a candidate when:
- A and B co-authored at least **2** presentations (multi-author rows of the same
  ``presentation_id``), AND
- if both birth years are known: |Δage| ≥ **15** years (older = candidate advisor);
- if either birth year is missing: co-authorship count must be ≥ **3** and the
  pair is emitted without an age-based advisor inference (maintainer decides).

This is intentionally conservative: many true advisor / student ties are
invisible to co-authorship (the advisor never co-presents with the student),
and many co-authorship pairs are peers, not lineage. Output is a starting
point for verification, not a list of facts.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "conferences.db"
OUT_CSV = ROOT / "analytics_output" / "lineage_candidates.csv"

MIN_CO_AUTHORED = 2          # at least this many co-authored presentations
MIN_AGE_GAP_YEARS = 15       # advisor is older than student by at least this many years
STRONG_CO_AUTHORED = 3       # if birth years are missing, require this many


def _to_int(value) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def collect_co_authorships(con: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    rows = con.execute(
        """
        SELECT pp.presentation_id, pp.person_id, e.year
        FROM presentation_person pp
        JOIN presentation pr USING(presentation_id)
        JOIN session s USING(session_id)
        JOIN event_day_venue edv USING(event_day_venue_id)
        JOIN event_day ed USING(event_day_id)
        JOIN event e USING(event_id)
        """
    ).fetchall()
    by_presentation: dict[str, list[tuple[str, int | None]]] = defaultdict(list)
    for pres_id, person_id, year in rows:
        by_presentation[pres_id].append((person_id, _to_int(year)))

    pair_stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "years": []}
    )
    for pres_id, members in by_presentation.items():
        if len(members) < 2:
            continue
        ids_sorted = sorted({m[0] for m in members})
        year = next((y for _, y in members if y is not None), None)
        for a, b in combinations(ids_sorted, 2):
            pair_stats[(a, b)]["count"] += 1
            if year is not None:
                pair_stats[(a, b)]["years"].append(year)
    return pair_stats


def person_lookup(con: sqlite3.Connection) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in con.execute(
        "SELECT person_id, normalized_key, display_name, full_name_ru, birth_year FROM person"
    ).fetchall():
        person_id, normalized_key, display_name, full_name_ru, birth_year = row
        out[person_id] = {
            "person_id": person_id,
            "normalized_key": normalized_key or "",
            "display_name": display_name or "",
            "full_name_ru": full_name_ru or "",
            "birth_year": _to_int(birth_year),
        }
    return out


def build_candidates(
    pair_stats: dict[tuple[str, str], dict],
    people: dict[str, dict],
) -> list[dict]:
    candidates: list[dict] = []
    for (a_id, b_id), stats in pair_stats.items():
        if stats["count"] < MIN_CO_AUTHORED:
            continue
        a, b = people.get(a_id), people.get(b_id)
        if not a or not b:
            continue

        by_a, by_b = a["birth_year"], b["birth_year"]
        years = sorted(stats["years"]) if stats["years"] else []
        first_year = years[0] if years else ""
        last_year = years[-1] if years else ""

        if by_a is not None and by_b is not None:
            if by_a == by_b:
                continue
            if by_a < by_b:
                advisor, student, delta = a, b, by_b - by_a
            else:
                advisor, student, delta = b, a, by_a - by_b
            if delta < MIN_AGE_GAP_YEARS:
                continue
            delta_str = str(delta)
            evidence = (
                f"Co-authored {stats['count']} presentations"
                f" ({first_year}-{last_year}), ΔAge = {delta} years"
            )
        else:
            if stats["count"] < STRONG_CO_AUTHORED:
                continue
            advisor, student = a, b
            delta = None
            delta_str = ""
            evidence = (
                f"Co-authored {stats['count']} presentations"
                f" ({first_year}-{last_year}); birth years missing on at least one side"
            )

        candidates.append(
            {
                "candidate_advisor_normalized_key": advisor["normalized_key"],
                "candidate_advisor_display_name": advisor["full_name_ru"] or advisor["display_name"],
                "candidate_advisor_birth_year": advisor["birth_year"] or "",
                "candidate_student_normalized_key": student["normalized_key"],
                "candidate_student_display_name": student["full_name_ru"] or student["display_name"],
                "candidate_student_birth_year": student["birth_year"] or "",
                "birth_year_delta": delta_str,
                "co_authored_count": stats["count"],
                "first_co_authored_year": first_year,
                "last_co_authored_year": last_year,
                "evidence_summary": evidence,
                "status": "candidate",
            }
        )

    # Strongest first: most co-authorships, then biggest age gap.
    candidates.sort(
        key=lambda c: (-(c["co_authored_count"]), -(int(c["birth_year_delta"]) if c["birth_year_delta"] else 0))
    )
    return candidates


def write_candidates(candidates: list[dict], path: Path = OUT_CSV) -> None:
    fieldnames = [
        "candidate_advisor_normalized_key",
        "candidate_advisor_display_name",
        "candidate_advisor_birth_year",
        "candidate_student_normalized_key",
        "candidate_student_display_name",
        "candidate_student_birth_year",
        "birth_year_delta",
        "co_authored_count",
        "first_co_authored_year",
        "last_co_authored_year",
        "evidence_summary",
        "status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)


def main() -> int:
    con = sqlite3.connect(str(DB))
    people = person_lookup(con)
    pair_stats = collect_co_authorships(con)
    candidates = build_candidates(pair_stats, people)
    write_candidates(candidates)

    multi_pres = sum(1 for stats in pair_stats.values())
    print(f"Pairs co-authored at least once: {multi_pres}")
    print(f"Pairs at {MIN_CO_AUTHORED}+ co-authorships: {sum(1 for s in pair_stats.values() if s['count'] >= MIN_CO_AUTHORED)}")
    print(f"Lineage candidates emitted: {len(candidates)}")
    print(f"Wrote {OUT_CSV}")
    if candidates:
        print()
        print("Top 5 candidates (strongest first):")
        for c in candidates[:5]:
            print(
                f"  {c['candidate_advisor_display_name']} ({c['candidate_advisor_birth_year']})"
                f"  ->  {c['candidate_student_display_name']} ({c['candidate_student_birth_year']})"
                f"  | {c['evidence_summary']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
