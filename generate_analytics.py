import sqlite3
import csv
import os
import statistics
import datetime

DB_PATH = "conferences.db"
OUTPUT_DIR = "analytics_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    with open("indology_scholars_analytics.md", "w", encoding="utf-8") as f:
        f.write("# Russian Indological Scholarship: Comparative Statistical Analytics\n\n")
        f.write("> [!NOTE]\n")
        f.write("> This analytical report is generated dynamically based on the relational SQL database "
                "compiled from Zograf Readings (2004–2025) and Roerich Readings (2007–2025) conference programs.\n\n")

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
        f.write("4. **age_cohort_trend.csv** — median age per conference event (speakers with known birth year).\n\n")

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

    print(f"analytics_output/: total_indologists.csv, zograf_only_indologists.csv, "
          f"roerich_only_indologists.csv, age_cohort_trend.csv")
    print(f"indology_scholars_analytics.md: sections 1–6 written.")
    print(f"missing_birth_years.md: {len(missing_rows)} scholars listed.")
    conn.close()

if __name__ == "__main__":
    main()
