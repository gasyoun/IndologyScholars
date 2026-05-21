"""
Метрики «закрытости клуба» для Зографа и Рерих по отдельности.

Шесть метрик:
  1) one-talk-wonder share — доля учёных с ровно 1 докладом за 20 лет
  2) core share (≥5 talks) — доля «ядра»
  3) Gini concentration — коэффициент Джини по числу докладов на человека
  4) newcomer rate по годам — доля новичков в каждой конференции
  5) retention probability — P(возврат после дебюта)
  6) cohort half-life — через сколько лет 50% дебютантов перестают появляться

Вывод: analytics_output/closedness_metrics.csv (сводка)
        analytics_output/newcomer_rate_by_year.csv (детально по годам)
        analytics_output/cohort_survival.csv (cohort × years_since_debut)
"""

import sys
import csv
import sqlite3
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

DB = "conferences.db"
OUT_DIR = "analytics_output"


def gini(values):
    if not values:
        return 0.0
    vs = sorted(values)
    n = len(vs)
    cum = 0
    for i, v in enumerate(vs, start=1):
        cum += i * v
    s = sum(vs)
    if s == 0:
        return 0.0
    return (2 * cum) / (n * s) - (n + 1) / n


def fetch_participation(cur, series_id):
    """Return dict: person_id -> sorted list of years they appeared."""
    cur.execute("""
        SELECT pp.person_id, e.year
          FROM presentation_person pp
          JOIN presentation pres ON pres.presentation_id = pp.presentation_id
          JOIN session s ON s.session_id = pres.session_id
          JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
          JOIN event_day ed ON ed.event_day_id = edv.event_day_id
          JOIN event e ON e.event_id = ed.event_id
         WHERE e.event_series_id = ?
    """, (series_id,))
    pp = defaultdict(set)
    for pid, year in cur.fetchall():
        pp[pid].add(year)
    return {pid: sorted(ys) for pid, ys in pp.items()}


def compute_closedness(label, person_years):
    """Compute metrics 1-6 for a single conference series."""
    talks_per_person = [len(ys) for ys in person_years.values()]
    n_scholars = len(talks_per_person)
    n_total_talks = sum(talks_per_person)

    one_talk = sum(1 for t in talks_per_person if t == 1)
    core = sum(1 for t in talks_per_person if t >= 5)

    # Newcomer rate per year
    years_sorted = sorted({y for ys in person_years.values() for y in ys})
    debuts_by_year = defaultdict(int)
    counts_by_year = defaultdict(int)
    for pid, ys in person_years.items():
        debut = min(ys)
        debuts_by_year[debut] += 1
        for y in ys:
            counts_by_year[y] += 1
    newcomer_table = []
    for y in years_sorted:
        nc = debuts_by_year[y]
        tot = counts_by_year[y]
        rate = (nc / tot * 100) if tot else 0
        newcomer_table.append({"series": label, "year": y, "newcomers": nc, "total": tot, "newcomer_pct": round(rate, 1)})

    # Retention: among people who debuted, P(at least one more appearance)
    debut_only = sum(1 for ys in person_years.values() if len(ys) == 1)
    debut_returned = n_scholars - debut_only
    retention = (debut_returned / n_scholars * 100) if n_scholars else 0

    # Cohort half-life: for each debut year, fraction still appearing N years later
    cohort_data = defaultdict(lambda: defaultdict(int))  # debut_year -> years_since -> n_active
    cohort_size = defaultdict(int)
    for pid, ys in person_years.items():
        debut = min(ys)
        cohort_size[debut] += 1
        ys_set = set(ys)
        for y in ys:
            cohort_data[debut][y - debut] += 1
    cohort_rows = []
    for debut_year in sorted(cohort_data.keys()):
        for delta in sorted(cohort_data[debut_year].keys()):
            cohort_rows.append({
                "series": label,
                "debut_year": debut_year,
                "years_since_debut": delta,
                "active_n": cohort_data[debut_year][delta],
                "cohort_size": cohort_size[debut_year],
                "survival_pct": round(100 * cohort_data[debut_year][delta] / cohort_size[debut_year], 1),
            })

    summary = {
        "series": label,
        "n_scholars": n_scholars,
        "n_total_participations": n_total_talks,
        "one_talk_wonder_pct": round(100 * one_talk / n_scholars, 1) if n_scholars else 0,
        "core_5plus_pct": round(100 * core / n_scholars, 1) if n_scholars else 0,
        "gini_concentration": round(gini(talks_per_person), 3),
        "retention_pct": round(retention, 1),
        "median_talks_per_scholar": sorted(talks_per_person)[len(talks_per_person) // 2] if talks_per_person else 0,
        "max_talks_per_scholar": max(talks_per_person) if talks_per_person else 0,
    }
    return summary, newcomer_table, cohort_rows


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Series 1 = Zograf, 2 = Roerich
    out_summary = []
    out_newcomer = []
    out_cohort = []

    for series_id, label in [(1, "Zograf"), (2, "Roerich")]:
        person_years = fetch_participation(cur, series_id)
        summary, newcomer_rows, cohort_rows = compute_closedness(label, person_years)
        out_summary.append(summary)
        out_newcomer.extend(newcomer_rows)
        out_cohort.extend(cohort_rows)
        print(f"\n=== {label} ===")
        for k, v in summary.items():
            print(f"  {k}: {v}")

    # Combined (both series together) — for overall picture
    person_years_all = defaultdict(set)
    for series_id in [1, 2]:
        for pid, ys in fetch_participation(cur, series_id).items():
            person_years_all[pid].update(ys)
    person_years_all = {pid: sorted(ys) for pid, ys in person_years_all.items()}
    sum_all, _, _ = compute_closedness("Combined", person_years_all)
    out_summary.append(sum_all)
    print(f"\n=== Combined ===")
    for k, v in sum_all.items():
        print(f"  {k}: {v}")

    # Write CSVs
    with open(f"{OUT_DIR}/closedness_metrics.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_summary[0].keys()))
        w.writeheader()
        w.writerows(out_summary)
    with open(f"{OUT_DIR}/newcomer_rate_by_year.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_newcomer[0].keys()))
        w.writeheader()
        w.writerows(out_newcomer)
    with open(f"{OUT_DIR}/cohort_survival.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_cohort[0].keys()))
        w.writeheader()
        w.writerows(out_cohort)

    print(f"\nWrote 3 CSVs to {OUT_DIR}/")
    conn.close()


if __name__ == "__main__":
    main()
