"""Audit: trace city labels in conference programs to known institutional affiliations.

Matches city-only labels to the nearest institution label within the same scholar's
presentation history (within a ±3 year window).

Outputs:
  analytics_output/city_trajectory_audit.csv   — per-label matching
  analytics_output/city_trajectory_summary.csv  — per-scholar summary
"""

import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = "conferences.db"
OUT_AUDIT = Path("analytics_output/city_trajectory_audit.csv")
OUT_SUMMARY = Path("analytics_output/city_trajectory_summary.csv")

INST_PATTERNS = [
    "университет", "институт", "РАН", "музей", "центр",
    "школа", "академия", "библиотека", "РГГУ", "МГУ",
    "СПбГУ", "ВШЭ", "РУДН", "Государственный",
    "College", "University", "семинар", "факультет",
    "кафедра", "колледж", "лаборатория", "отдел",
    "Академия", "НИИ", "ПСТГУ", "РАНХ", "МГИМО",
    "фонд", "общество", "издательство",
]


def is_institution(raw: str) -> bool:
    for pat in INST_PATTERNS:
        if pat in raw:
            return True
    return False


def normalize_city(raw: str) -> str:
    """Strip common suffixes from city labels."""
    raw = raw.strip().rstrip(".")
    for suffix in [" г.", " г", " город", " р-н", " обл.", " обл"]:
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
    return raw


def build_trajectories():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Series name lookup
    series_names = {1: "Zograf", 2: "Roerich"}

    q = """SELECT p.person_id, p.display_name, p.full_name_ru, ev.year,
           ev.event_series_id, pp.affiliation_text_raw
    FROM presentation_person pp
    JOIN person p ON pp.person_id = p.person_id
    JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    JOIN session s ON pr.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event ev ON ed.event_id = ev.event_id
    WHERE pp.role = 'speaker'
      AND pp.affiliation_text_raw IS NOT NULL
      AND pp.affiliation_text_raw NOT IN ('', 'Не указана')
    ORDER BY p.person_id, ev.year"""

    rows = c.execute(q).fetchall()

    person_timeline = defaultdict(list)
    person_names = {}
    for pid, dname, fname, year, series_id, aff in rows:
        name = (fname or dname or pid)
        person_names[pid] = name
        person_timeline[pid].append((year, series_id, aff, is_institution(aff)))

    # Per-label matching
    audit_rows = []
    summary_rows = []

    for pid in sorted(person_timeline.keys()):
        entries = person_timeline[pid]
        name = person_names[pid]
        inst_entries = [(y, a) for y, s, a, is_i in entries if is_i]
        city_entries = [(y, a) for y, s, a, is_i in entries if not is_i]

        total_talks = len(entries)
        city_talk_count = len(city_entries)
        inst_talk_count = len(inst_entries)
        has_any_inst = inst_talk_count > 0

        # Aggregate unique city labels
        unique_cities = sorted(set(normalize_city(a) for y, a in city_entries))
        unique_insts = sorted(set(a for y, a in inst_entries))

        matched_cities = 0
        for cy, ca in city_entries:
            best_dist = 999
            best_inst = ""
            for iy, ia in inst_entries:
                dist = abs(cy - iy)
                if dist < best_dist:
                    best_dist = dist
                    best_inst = ia
            matched = best_inst if best_dist <= 3 else ""
            confidence = "near" if best_dist <= 1 else ("far" if best_dist <= 3 else "none")

            if confidence != "none":
                matched_cities += 1

            audit_rows.append({
                "person_id": pid,
                "display_name": name,
                "city_year": cy,
                "city_label": ca,
                "matched_institution": matched,
                "year_distance": best_dist if best_dist < 999 else "",
                "confidence": confidence,
            })

        # Per-scholar summary
        city_list = "; ".join(f"{normalize_city(a)} ({y})" for y, a in city_entries)
        inst_list = "; ".join(f"{a} ({y})" for y, a in inst_entries)
        coverage_pct = (matched_cities / city_talk_count * 100) if city_talk_count else 0

        summary_rows.append({
            "person_id": pid,
            "display_name": name,
            "total_talks": total_talks,
            "city_only_talks": city_talk_count,
            "institution_talks": inst_talk_count,
            "matched_city_labels": matched_cities,
            "coverage_pct": round(coverage_pct, 1),
            "unique_cities": "; ".join(unique_cities),
            "unique_institutions": "; ".join(unique_insts),
        })

    # Write audit CSV
    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    fields_a = ["person_id", "display_name", "city_year", "city_label",
                "matched_institution", "year_distance", "confidence"]
    with open(OUT_AUDIT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_a)
        w.writeheader()
        w.writerows(audit_rows)

    # Write summary CSV
    fields_s = ["person_id", "display_name", "total_talks", "city_only_talks",
                "institution_talks", "matched_city_labels", "coverage_pct",
                "unique_cities", "unique_institutions"]
    with open(OUT_SUMMARY, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_s)
        w.writeheader()
        w.writerows(summary_rows)

    # Stats
    total_city = sum(1 for r in audit_rows)
    matched = sum(1 for r in audit_rows if r["confidence"] != "none")
    near = sum(1 for r in audit_rows if r["confidence"] == "near")
    far = sum(1 for r in audit_rows if r["confidence"] == "far")
    unmatched = total_city - matched

    scholars_with_city = sum(1 for s in summary_rows if s["city_only_talks"] > 0)
    scholars_full_match = sum(1 for s in summary_rows if s["coverage_pct"] == 100 and s["city_only_talks"] > 0)
    scholars_partial = sum(1 for s in summary_rows if 0 < s["coverage_pct"] < 100)
    scholars_no_match = sum(1 for s in summary_rows if s["coverage_pct"] == 0 and s["city_only_talks"] > 0)

    print(f"City-only labels:              {total_city}")
    print(f"Matched to institution:        {matched}  ({matched/total_city*100:.1f}%)")
    print(f"  Near match (<=1 year gap):   {near}")
    print(f"  Far match (<=3 year gap):    {far}")
    print(f"Unmatched:                     {unmatched}  ({unmatched/total_city*100:.1f}%)")
    print()
    print(f"Scholars with city labels:     {scholars_with_city}")
    print(f"  Fully matched:               {scholars_full_match}")
    print(f"  Partially matched:           {scholars_partial}")
    print(f"  Not matched at all:          {scholars_no_match}  ({scholars_no_match/scholars_with_city*100:.1f}%)")
    print()
    print(f"Outputs: {OUT_AUDIT}, {OUT_SUMMARY}")

    conn.close()


if __name__ == "__main__":
    build_trajectories()
