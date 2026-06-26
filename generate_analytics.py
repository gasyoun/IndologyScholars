import sqlite3
import csv
import os
import statistics
import datetime
from collections import defaultdict
from dataclasses import dataclass

from generate_site_data import classify_theme, clean_title
from publication_helpers import normalize_affiliation

DB_PATH = "conferences.db"
OUTPUT_DIR = "analytics_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def gini(values):
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0
    weighted = sum(i * value for i, value in enumerate(sorted_values, start=1))
    return (2 * weighted) / (n * total) - (n + 1) / n


def fetch_participation(cursor, series_id):
    cursor.execute("""
        SELECT pp.person_id, e.year
          FROM presentation_person pp
          JOIN presentation pres ON pres.presentation_id = pp.presentation_id
          JOIN session s ON s.session_id = pres.session_id
          JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
          JOIN event_day ed ON ed.event_day_id = edv.event_day_id
          JOIN event e ON e.event_id = ed.event_id
         WHERE e.event_series_id = ?
    """, (series_id,))
    person_years = defaultdict(set)
    for person_id, year in cursor.fetchall():
        person_years[person_id].add(year)
    return {person_id: sorted(years) for person_id, years in person_years.items()}


def compute_closedness(label, person_years):
    talks_per_person = [len(years) for years in person_years.values()]
    n_scholars = len(talks_per_person)
    n_total_participations = sum(talks_per_person)

    one_talk = sum(1 for talks in talks_per_person if talks == 1)
    core = sum(1 for talks in talks_per_person if talks >= 5)

    years_sorted = sorted({year for years in person_years.values() for year in years})
    debuts_by_year = defaultdict(int)
    counts_by_year = defaultdict(int)
    for years in person_years.values():
        debut = min(years)
        debuts_by_year[debut] += 1
        for year in years:
            counts_by_year[year] += 1

    newcomer_rows = []
    for year in years_sorted:
        newcomers = debuts_by_year[year]
        total = counts_by_year[year]
        newcomer_rows.append({
            "series": label,
            "year": year,
            "newcomers": newcomers,
            "total": total,
            "newcomer_pct": round(newcomers / total * 100, 1) if total else 0,
        })

    one_appearance = sum(1 for years in person_years.values() if len(years) == 1)
    retention = (n_scholars - one_appearance) / n_scholars * 100 if n_scholars else 0

    # Product-limit / Kaplan-Meier table for VIS_009. The rendered page uses
    # the same semantics: final-window observations and single appearances are
    # right-censored rather than counted as departures at t=0.
    last_obs_year = max((max(years) for years in person_years.values()), default=0)
    censor_from = last_obs_year - 1
    cohort_spans = defaultdict(list)
    for years in person_years.values():
        debut, last = min(years), max(years)
        span = last - debut
        event = 0 if last >= censor_from or last == debut else 1
        cohort_spans[debut].append((span, event))

    cohort_rows = []
    for debut_year in sorted(cohort_spans):
        observations = cohort_spans[debut_year]
        cohort_size = len(observations)
        survival = 1.0
        for delta in range(0, max(span for span, _ in observations) + 1):
            at_risk = sum(1 for span, _ in observations if span >= delta)
            events = sum(1 for span, event in observations if span == delta and event == 1)
            if at_risk and events:
                survival *= 1 - events / at_risk
            cohort_rows.append({
                "series": label,
                "debut_year": debut_year,
                "years_since_debut": delta,
                "at_risk": at_risk,
                "cohort_size": cohort_size,
                "survival_pct": round(survival * 100, 1),
            })

    median_talks = sorted(talks_per_person)[len(talks_per_person) // 2] if talks_per_person else 0
    summary = {
        "series": label,
        "n_scholars": n_scholars,
        "n_total_participations": n_total_participations,
        "one_talk_wonder_pct": round(100 * one_talk / n_scholars, 1) if n_scholars else 0,
        "core_5plus_pct": round(100 * core / n_scholars, 1) if n_scholars else 0,
        "gini_concentration": round(gini(talks_per_person), 3),
        "retention_pct": round(retention, 1),
        "median_talks_per_scholar": median_talks,
        "max_talks_per_scholar": max(talks_per_person) if talks_per_person else 0,
    }
    return summary, newcomer_rows, cohort_rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_closedness_metrics(cursor):
    summary_rows = []
    newcomer_rows = []
    cohort_rows = []

    for series_id, label in [(1, "Zograf"), (2, "Roerich")]:
        summary, newcomers, cohorts = compute_closedness(label, fetch_participation(cursor, series_id))
        summary_rows.append(summary)
        newcomer_rows.extend(newcomers)
        cohort_rows.extend(cohorts)

    combined_years = defaultdict(set)
    for series_id in [1, 2]:
        for person_id, years in fetch_participation(cursor, series_id).items():
            combined_years[person_id].update(years)
    combined_years = {person_id: sorted(years) for person_id, years in combined_years.items()}
    combined_summary, _, _ = compute_closedness("Combined", combined_years)
    summary_rows.append(combined_summary)

    write_csv(
        os.path.join(OUTPUT_DIR, "closedness_metrics.csv"),
        summary_rows,
        list(summary_rows[0].keys()),
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "newcomer_rate_by_year.csv"),
        newcomer_rows,
        ["series", "year", "newcomers", "total", "newcomer_pct"],
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "cohort_survival.csv"),
        cohort_rows,
        ["series", "debut_year", "years_since_debut", "at_risk", "cohort_size", "survival_pct"],
    )
    return len(cohort_rows)


def node_id(node_type, local_id):
    return f"{node_type}:{local_id}"


@dataclass
class EdgeAttributes:
    edge_type: str
    year: str = None
    series: str = None
    weight: int = 1


def add_edge(edges, source, target, attrs: EdgeAttributes):
    if not source or not target or source == target:
        return
    # Person-person edges are undirected in this export; keep a stable order.
    if attrs.edge_type.startswith("person_person") and source > target:
        source, target = target, source
    key = (source, target, attrs.edge_type, attrs.year or "", attrs.series or "")
    current = edges.get(key)
    if current:
        current["weight"] += attrs.weight
    else:
        edges[key] = {
            "source": source,
            "target": target,
            "edge_type": attrs.edge_type,
            "year": attrs.year or "",
            "series": attrs.series or "",
            "weight": attrs.weight,
        }


def generate_network_exports(cursor):
    cursor.execute("""
        SELECT
            pr.presentation_id,
            pr.title,
            e.event_id,
            e.year,
            es.series_name_en,
            s.session_id,
            pp.person_id,
            p.display_name,
            p.full_name_ru,
            pp.role,
            pp.author_order,
            pp.affiliation_text_raw
        FROM presentation pr
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        ORDER BY e.year, es.event_series_id, s.session_id, pr.presentation_id, pp.author_order
    """)
    rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    nodes = {}
    edges = {}
    presentations = defaultdict(list)
    sessions = defaultdict(list)

    for row in rows:
        person_local_id = row["person_id"]
        person_node = node_id("person", person_local_id)
        if person_node not in nodes:
            nodes[person_node] = {
                "node_id": person_node,
                "node_type": "person",
                "label": row["full_name_ru"] or row["display_name"],
                "local_id": person_local_id,
                "weight": 0,
            }
        nodes[person_node]["weight"] += 1

        event_node = node_id("event", row["event_id"])
        if event_node not in nodes:
            nodes[event_node] = {
                "node_id": event_node,
                "node_type": "event",
                "label": f"{row['series_name_en']} {row['year']}",
                "local_id": row["event_id"],
                "weight": 0,
            }
        nodes[event_node]["weight"] += 1
        add_edge(edges, person_node, event_node, EdgeAttributes("person_event", row["year"], row["series_name_en"]))

        org = normalize_affiliation(row["affiliation_text_raw"])
        org_node = None
        if org:
            org_node = node_id("organization", org)
            if org_node not in nodes:
                nodes[org_node] = {
                    "node_id": org_node,
                    "node_type": "organization",
                    "label": org,
                    "local_id": org,
                    "weight": 0,
                }
            nodes[org_node]["weight"] += 1
            add_edge(edges, person_node, org_node, EdgeAttributes("person_organization", row["year"], row["series_name_en"]))

        theme = classify_theme(row["year"], row["series_name_en"], clean_title(row["title"] or "")).get("code") or "History"
        theme_node = node_id("theme", theme)
        if theme_node not in nodes:
            nodes[theme_node] = {
                "node_id": theme_node,
                "node_type": "theme",
                "label": theme,
                "local_id": theme,
                "weight": 0,
            }
        nodes[theme_node]["weight"] += 1
        add_edge(edges, person_node, theme_node, EdgeAttributes("person_theme", row["year"], row["series_name_en"]))
        if org_node:
            add_edge(edges, org_node, theme_node, EdgeAttributes("organization_theme", row["year"], row["series_name_en"]))

        presentations[row["presentation_id"]].append((person_node, row))
        sessions[row["session_id"]].append((person_node, row))

    for members in presentations.values():
        people = sorted({person for person, _ in members})
        if len(people) < 2:
            continue
        sample = members[0][1]
        for i, source in enumerate(people):
            for target in people[i + 1:]:
                add_edge(edges, source, target, EdgeAttributes("person_person_copresentation", sample["year"], sample["series_name_en"]))

    for members in sessions.values():
        people = sorted({person for person, _ in members})
        if len(people) < 2:
            continue
        sample = members[0][1]
        for i, source in enumerate(people):
            for target in people[i + 1:]:
                add_edge(edges, source, target, EdgeAttributes("person_person_same_session", sample["year"], sample["series_name_en"]))

    with open(os.path.join(OUTPUT_DIR, "network_nodes.csv"), "w", encoding="utf-8", newline="") as f:
        fieldnames = ["node_id", "node_type", "label", "local_id", "weight"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(nodes.values(), key=lambda row: (row["node_type"], row["label"])))

    with open(os.path.join(OUTPUT_DIR, "network_edges.csv"), "w", encoding="utf-8", newline="") as f:
        fieldnames = ["source", "target", "edge_type", "year", "series", "weight"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(edges.values(), key=lambda row: (row["edge_type"], row["source"], row["target"], str(row["year"]))))

    return len(nodes), len(edges)


def generate_coauthorship_review(cursor):
    cursor.execute("""
        WITH multi AS (
            SELECT presentation_id
            FROM presentation_person
            GROUP BY presentation_id
            HAVING COUNT(*) > 1
        )
        SELECT
            pr.presentation_id,
            pr.title,
            e.year,
            es.series_name_en,
            GROUP_CONCAT(
                COALESCE(p.full_name_ru, p.display_name) || ' [' || pp.role || ']',
                ' | '
            ) AS people,
            pr.source_snippet,
            pr.source_url
        FROM presentation pr
        JOIN multi m ON m.presentation_id = pr.presentation_id
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        GROUP BY pr.presentation_id
        ORDER BY e.year, es.event_series_id, pr.presentation_id
    """)
    rows = []
    for row in cursor.fetchall():
        presentation_id, title, year, series, people, source_snippet, source_url = row
        rows.append({
            "presentation_id": presentation_id,
            "year": year,
            "series": series,
            "title": title,
            "people": people,
            "source_snippet": source_snippet,
            "source_url": source_url,
            "review_status": "source_backed_review",
            "human_action": "Confirm that the programme line denotes a true joint presentation before citing as coauthorship.",
        })

    with open(os.path.join(OUTPUT_DIR, "coauthorship_review.csv"), "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "presentation_id", "year", "series", "title", "people",
            "source_snippet", "source_url", "review_status", "human_action",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def generate_senior_absence_audit(cursor):
    cursor.execute("""
        WITH person_years AS (
            SELECT
                p.person_id,
                COALESCE(p.full_name_ru, p.display_name) AS display_name,
                p.birth_year,
                p.death_year,
                e.year,
                COUNT(DISTINCT pr.presentation_id) AS talks
            FROM person p
            JOIN presentation_person pp ON pp.person_id = p.person_id
            JOIN presentation pr ON pr.presentation_id = pp.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            GROUP BY p.person_id, e.year
        ),
        agg AS (
            SELECT
                person_id,
                display_name,
                birth_year,
                death_year,
                SUM(CASE WHEN year <= 2022 THEN talks ELSE 0 END) AS talks_to_2022,
                SUM(CASE WHEN year >= 2023 THEN talks ELSE 0 END) AS talks_after_2022,
                SUM(CASE WHEN year <= 2025 THEN talks ELSE 0 END) AS talks_to_2025,
                SUM(CASE WHEN year = 2026 THEN talks ELSE 0 END) AS talks_2026,
                MIN(year) AS first_year,
                MAX(year) AS last_year
            FROM person_years
            GROUP BY person_id
        )
        SELECT * FROM agg
        WHERE birth_year IS NOT NULL
          AND birth_year <= 1960
          AND death_year IS NULL
          AND (
            (talks_to_2022 >= 5 AND COALESCE(talks_after_2022, 0) = 0)
            OR (talks_to_2025 >= 5 AND COALESCE(talks_2026, 0) = 0)
          )
        ORDER BY display_name
    """)
    source_rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    rows = []
    for row in source_rows:
        if row["talks_to_2022"] >= 5 and (row["talks_after_2022"] or 0) == 0:
            rows.append({
                "cohort": "absent_after_2022",
                "person_id": row["person_id"],
                "display_name": row["display_name"],
                "birth_year": row["birth_year"],
                "first_year": row["first_year"],
                "last_year": row["last_year"],
                "talks_before_threshold": row["talks_to_2022"],
                "talks_after_threshold": row["talks_after_2022"] or 0,
                "living_status_basis": "death_year blank in local database; externally verify before biographical claims",
                "review_status": "review",
                "interpretation_note": "Frequent senior-generation participant through 2022, absent in 2023-2026 archive data.",
            })
        if row["talks_to_2025"] >= 5 and (row["talks_2026"] or 0) == 0:
            rows.append({
                "cohort": "absent_in_2026",
                "person_id": row["person_id"],
                "display_name": row["display_name"],
                "birth_year": row["birth_year"],
                "first_year": row["first_year"],
                "last_year": row["last_year"],
                "talks_before_threshold": row["talks_to_2025"],
                "talks_after_threshold": row["talks_2026"] or 0,
                "living_status_basis": "death_year blank in local database; externally verify before biographical claims",
                "review_status": "review",
                "interpretation_note": "Frequent senior-generation participant before 2026, absent from the 2026 Zograf programme in current data.",
            })

    with open(os.path.join(OUTPUT_DIR, "senior_absence_audit.csv"), "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "cohort", "person_id", "display_name", "birth_year", "first_year",
            "last_year", "talks_before_threshold", "talks_after_threshold",
            "living_status_basis", "review_status", "interpretation_note",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Total scholars with talk counts per series
    cursor.execute("""
        SELECT
            p.person_id,
            p.display_name,
            COUNT(DISTINCT pr.presentation_id) as total_talks,
            SUM(CASE WHEN e.event_series_id = 1 THEN 1 ELSE 0 END) as zograf_talks,
            SUM(CASE WHEN e.event_series_id = 2 THEN 1 ELSE 0 END) as roerich_talks,
            MIN(e.year) as first_year_seen,
            MAX(e.year) as last_year_seen
        FROM person p
        JOIN presentation_person pp ON pp.person_id = p.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        GROUP BY p.person_id
        ORDER BY total_talks DESC, p.display_name ASC
    """)
    total_scholars = cursor.fetchall()

    roerich_only = [r for r in total_scholars if r[3] == 0 and r[4] > 0]
    zograf_only  = [r for r in total_scholars if r[3] > 0 and r[4] == 0]
    overlap      = [r for r in total_scholars if r[3] > 0 and r[4] > 0]

    # 2. Age cohort trend: age of each speaker on conference start date
    cursor.execute("""
        SELECT
            e.event_id,
            e.year,
            e.start_date,
            e.event_series_id,
            GROUP_CONCAT(CAST(SUBSTR(e.start_date,1,4) AS INTEGER) - p.birth_year) AS ages_csv
        FROM event e
        JOIN event_day ed ON ed.event_id = e.event_id
        JOIN event_day_venue edv ON edv.event_day_id = ed.event_day_id
        JOIN session s ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN presentation pr ON pr.session_id = s.session_id
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        WHERE p.birth_year IS NOT NULL
          AND e.start_date IS NOT NULL
        GROUP BY e.event_id
        ORDER BY e.start_date
    """)
    age_trend_rows = []
    for event_id, year, start_date, series_id, ages_csv in cursor.fetchall():
        ages = sorted([int(x) for x in ages_csv.split(",") if x])
        if not ages:
            continue
        n = len(ages)
        series_name = "Zograf" if series_id == 1 else "Roerich"
        p25 = statistics.quantiles(ages, n=4)[0] if n >= 4 else ages[0]
        p75 = statistics.quantiles(ages, n=4)[2] if n >= 4 else ages[-1]
        age_trend_rows.append({
            "event_id": event_id,
            "year": year,
            "conf_date": start_date,
            "series": series_name,
            "n_speakers_with_age": n,
            "avg_age": round(sum(ages) / n, 1),
            "median_age": round(statistics.median(ages), 1),
            "min_age": ages[0],
            "max_age": ages[-1],
            "p25_age": round(p25, 1),
            "p75_age": round(p75, 1),
        })

    n_with_age = sum(1 for r in total_scholars
                     if any(True for _ in [r]))  # placeholder; use direct query
    cursor.execute("SELECT COUNT(*) FROM person WHERE birth_year IS NOT NULL")
    n_with_age = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM person")
    n_total_persons = cursor.fetchone()[0]

    # 3. Scholars missing birth_year
    cursor.execute("""
        SELECT
            p.person_id,
            p.display_name,
            p.full_name_ru,
            p.full_name_en,
            COUNT(DISTINCT pr.presentation_id) AS total_talks,
            SUM(CASE WHEN e.event_series_id = 1 THEN 1 ELSE 0 END) AS zograf_talks,
            SUM(CASE WHEN e.event_series_id = 2 THEN 1 ELSE 0 END) AS roerich_talks,
            MIN(e.year) AS first_year,
            MAX(e.year) AS last_year
        FROM person p
        JOIN presentation_person pp ON pp.person_id = p.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        WHERE p.birth_year IS NULL
        GROUP BY p.person_id
        ORDER BY total_talks DESC, p.display_name ASC
    """)
    missing_rows = cursor.fetchall()

    # ── CSV exports ───────────────────────────────────────────────────────────

    with open(os.path.join(OUTPUT_DIR, "total_indologists.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PersonID", "DisplayName", "TotalTalks", "ZografTalks", "RoerichTalks",
                         "FirstYearSeen", "LastYearSeen", "SeriesAttended"])
        for row in total_scholars:
            series = []
            if row[3] > 0: series.append("Zograf")
            if row[4] > 0: series.append("Roerich")
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5], row[6], "+".join(series)])

    with open(os.path.join(OUTPUT_DIR, "roerich_only_indologists.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PersonID", "DisplayName", "RoerichTalks", "FirstYearSeen", "LastYearSeen"])
        for row in roerich_only:
            writer.writerow([row[0], row[1], row[4], row[5], row[6]])

    with open(os.path.join(OUTPUT_DIR, "zograf_only_indologists.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PersonID", "DisplayName", "ZografTalks", "FirstYearSeen", "LastYearSeen"])
        for row in zograf_only:
            writer.writerow([row[0], row[1], row[3], row[5], row[6]])

    with open(os.path.join(OUTPUT_DIR, "age_cohort_trend.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "event_id", "year", "conf_date", "series",
            "n_speakers_with_age", "avg_age", "median_age",
            "min_age", "max_age", "p25_age", "p75_age",
        ])
        writer.writeheader()
        writer.writerows(age_trend_rows)

    network_node_count, network_edge_count = generate_network_exports(cursor)
    coauthorship_review_count = generate_coauthorship_review(cursor)
    senior_absence_count = generate_senior_absence_audit(cursor)
    cohort_survival_count = generate_closedness_metrics(cursor)

    # ── missing_birth_years.md ────────────────────────────────────────────────

    with open("missing_birth_years.md", "w", encoding="utf-8") as f:
        f.write("# Учёные без даты рождения / Scholars Missing Birth Year\n\n")
        f.write(f"Дата генерации: {datetime.date.today()}\n\n")
        f.write(f"Без года рождения: **{len(missing_rows)}** из {n_total_persons} участников "
                f"({n_with_age} уже заполнены).\n\n")
        f.write("Для заполнения выполните SQL-запрос:\n\n")
        f.write("```sql\n")
        f.write("UPDATE person SET birth_year = <YYYY> WHERE person_id = '<id>';\n")
        f.write("```\n\n")
        f.write("После заполнения запустите `python generate_analytics.py && python generate_scholars_pages.py`.\n\n")
        f.write("---\n\n")
        f.write("| # | Имя (display_name) | ФИО рус. | ФИО англ. | Докл. | Зограф | Рерих | Годы |\n")
        f.write("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :--- |\n")
        for i, row in enumerate(missing_rows, 1):
            pid, dname, ru, en, total, zog, roe, first, last = row
            period = f"{first}–{last}" if first != last else str(first)
            f.write(f"| {i} | {dname or ''} | {ru or ''} | {en or ''} "
                    f"| {total} | {zog} | {roe} | {period} |\n")

    # ── indology_scholars_analytics.md (single "w" block) ────────────────────

    zograf_range = cursor.execute("SELECT MIN(year), MAX(year) FROM event WHERE event_series_id = 1").fetchone()
    roerich_range = cursor.execute("SELECT MIN(year), MAX(year) FROM event WHERE event_series_id = 2").fetchone()
    zograf_label = f"{zograf_range[0]}–{zograf_range[1]}"
    roerich_label = f"{roerich_range[0]}–{roerich_range[1]}"

    with open("indology_scholars_analytics.md", "w", encoding="utf-8") as f:
        f.write("# Russian Indological Scholarship: Comparative Statistical Analytics\n\n")
        f.write("> [!NOTE]\n")
        f.write("> This analytical report is generated dynamically based on the relational SQL database "
                f"compiled from Zograf Readings ({zograf_label}) and Roerich Readings ({roerich_label}) conference programs.\n\n")

        f.write("## 1. High-Level Executive Summary\n\n")
        f.write(f"- **Total Unique Scholars Identified**: {len(total_scholars)}\n")
        f.write(f"- **Total Historical Presentations/Talks**: {sum(r[2] for r in total_scholars)}\n")
        f.write(f"- **Scholars in Zograf Readings only**: {len(zograf_only)}\n")
        f.write(f"- **Scholars in Roerich Readings only**: {len(roerich_only)}\n")
        f.write(f"- **Scholars Active in BOTH Conferences (Overlapping Cohort)**: {len(overlap)}\n\n")

        f.write("## 2. Overlapping Cohort (The Core of Russian Indology)\n")
        f.write("These scholars are active in both major Petersburg (Zograf) and Moscow (Roerich) forums, "
                "representing the intellectual bridge of the community:\n\n")
        f.write("| Scholar Name | Total Talks | Zograf Talks | Roerich Talks | Active Period |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: |\n")
        for row in overlap[:30]:
            f.write(f"| {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}–{row[6]} |\n")

        f.write("\n## 3. Top 15 Most Active Zograf Readings Participants\n\n")
        f.write("| Scholar Name | Zograf Talks | Active Period |\n")
        f.write("| :--- | :---: | :---: |\n")
        for row in sorted(total_scholars, key=lambda r: r[3], reverse=True)[:15]:
            f.write(f"| {row[1]} | {row[3]} | {row[5]}–{row[6]} |\n")

        f.write("\n## 4. Top 15 Most Active Roerich Readings Participants\n\n")
        f.write("| Scholar Name | Roerich Talks | Active Period |\n")
        f.write("| :--- | :---: | :---: |\n")
        for row in sorted(total_scholars, key=lambda r: r[4], reverse=True)[:15]:
            f.write(f"| {row[1]} | {row[4]} | {row[5]}–{row[6]} |\n")

        f.write("\n## 5. CSV Export Deliverables\n")
        f.write("The complete structured lists have been generated and exported to the `analytics_output` folder:\n")
        f.write("1. **total_indologists.csv** — complete master list.\n")
        f.write("2. **zograf_only_indologists.csv** — Petersburg-centric scholars.\n")
        f.write("3. **roerich_only_indologists.csv** — Moscow-centric scholars.\n")
        f.write("4. **age_cohort_trend.csv** — median age per conference event (speakers with known birth year).\n")
        f.write("5. **network_nodes.csv / network_edges.csv** — participation network exports with explicit edge types.\n\n")

        f.write("## 6. Демографический тренд: возраст участников на день конференции\n\n")
        f.write("> Возраст = год начала конференции − год рождения участника (погрешность ≤1 год).\n")
        f.write(f"> Год рождения известен для **{n_with_age}** из {n_total_persons} учёных "
                f"({len(missing_rows)} отсутствуют, см. `missing_birth_years.md`).\n\n")

        f.write("### Зографские чтения (май, Санкт-Петербург)\n\n")
        f.write("| Год | Дата | N | Ср. возраст | Медиана | P25–P75 | Мин–Макс |\n")
        f.write("| :---: | :--- | :---: | :---: | :---: | :--- | :--- |\n")
        for r in age_trend_rows:
            if r["series"] == "Zograf":
                f.write(f"| {r['year']} | {r['conf_date']} | {r['n_speakers_with_age']} "
                        f"| {r['avg_age']} | {r['median_age']} "
                        f"| {r['p25_age']}–{r['p75_age']} | {r['min_age']}–{r['max_age']} |\n")

        f.write("\n### Рериховские чтения (декабрь, Москва)\n\n")
        f.write("| Год | Дата | N | Ср. возраст | Медиана | P25–P75 | Мин–Макс |\n")
        f.write("| :---: | :--- | :---: | :---: | :---: | :--- | :--- |\n")
        for r in age_trend_rows:
            if r["series"] == "Roerich":
                f.write(f"| {r['year']} | {r['conf_date']} | {r['n_speakers_with_age']} "
                        f"| {r['avg_age']} | {r['median_age']} "
                        f"| {r['p25_age']}–{r['p75_age']} | {r['min_age']}–{r['max_age']} |\n")

        f.write("\n## 7. Network Analysis\n\n")
        f.write("We analyze the structure of Russian Indological conferences through the lens of participation networks. ")
        f.write("Unlike traditional bibliometric networks (which map who cites whom), our networks map **co-presence and shared scholarly context**. ")
        f.write("They help identify institutional centers of gravity, disciplinary clustering, and bridge scholars between the Zograf and Roerich readings.\n\n")
        f.write(f"**Nodes Generated:** {network_node_count}\n\n")
        f.write(f"**Edges Generated:** {network_edge_count}\n\n")
        f.write("The network is exported into standard edge list and node list CSV formats (`network_nodes.csv` and `network_edges.csv`) for use in external graphing tools like Gephi or Cytoscape.\n")

    print(f"analytics_output/: total_indologists.csv, zograf_only_indologists.csv, "
          f"roerich_only_indologists.csv, age_cohort_trend.csv")
    print(f"network exports: {network_node_count} nodes, {network_edge_count} edges")
    print(f"coauthorship_review.csv: {coauthorship_review_count} rows.")
    print(f"senior_absence_audit.csv: {senior_absence_count} rows.")
    print(f"closedness metrics: cohort_survival.csv {cohort_survival_count} rows.")
    print(f"indology_scholars_analytics.md: sections 1–6 written.")
    print(f"missing_birth_years.md: {len(missing_rows)} scholars listed.")
    conn.close()

if __name__ == "__main__":
    main()
