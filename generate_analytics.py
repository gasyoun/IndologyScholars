import sqlite3
import csv
import os
import statistics
import datetime
from collections import defaultdict
from dataclasses import dataclass

from generate_site_data import classify_theme, clean_title

DB_PATH = "conferences.db"
OUTPUT_DIR = "analytics_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def normalize_affiliation(aff):
    if not aff:
        return None
    value = aff.lower()
    if "ивр " in value or "восточных рукописей" in value:
        return "ИВР РАН"
    if "ив ран" in value or "востоковедения ран" in value or "ивран" in value:
        return "ИВ РАН"
    if "спбгу" in value or "петербургский" in value:
        return "СПбГУ"
    if "мгу" in value or "ломоносова" in value:
        return "МГУ"
    if "вшэ" in value or "высшая школа" in value:
        return "НИУ ВШЭ"
    if "рггу" in value or "гуманитарный" in value:
        return "РГГУ"
    if "маэ" in value or "кунсткамера" in value:
        return "МАЭ РАН"
    if "эрмитаж" in value:
        return "Государственный Эрмитаж"
    if "институт философии" in value or "иф ран" in value:
        return "ИФ РАН"
    if "независим" in value or "independent" in value:
        return "Независимые исследователи"
    return None


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
    print(f"indology_scholars_analytics.md: sections 1–6 written.")
    print(f"missing_birth_years.md: {len(missing_rows)} scholars listed.")
    conn.close()

if __name__ == "__main__":
    main()
