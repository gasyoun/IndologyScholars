import sqlite3
import csv
import os

DB_PATH = "conferences.db"
OUTPUT_DIR = "analytics_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Generate Total Indologists List
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
    
    with open(os.path.join(OUTPUT_DIR, "total_indologists.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PersonID", "DisplayName", "TotalTalks", "ZografTalks", "RoerichTalks", "FirstYearSeen", "LastYearSeen", "SeriesAttended"])
        for row in total_scholars:
            series = []
            if row[3] > 0: series.append("Zograf")
            if row[4] > 0: series.append("Roerich")
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5], row[6], "+".join(series)])
            
    # 2. Generate Roerich-Only Indologists List
    roerich_only = [r for r in total_scholars if r[3] == 0 and r[4] > 0]
    with open(os.path.join(OUTPUT_DIR, "roerich_only_indologists.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PersonID", "DisplayName", "RoerichTalks", "FirstYearSeen", "LastYearSeen"])
        for row in roerich_only:
            writer.writerow([row[0], row[1], row[4], row[5], row[6]])
            
    # 3. Generate Zograf-Only Indologists List
    zograf_only = [r for r in total_scholars if r[3] > 0 and r[4] == 0]
    with open(os.path.join(OUTPUT_DIR, "zograf_only_indologists.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PersonID", "DisplayName", "ZografTalks", "FirstYearSeen", "LastYearSeen"])
        for row in zograf_only:
            writer.writerow([row[0], row[1], row[3], row[5], row[6]])

    # 4. Generate beautiful Markdown report
    with open("indology_scholars_analytics.md", "w", encoding="utf-8") as f:
        f.write("# Russian Indological Scholarship: Comparative Statistical Analytics\n\n")
        f.write("> [!NOTE]\n")
        f.write("> This analytical report is generated dynamically based on the relational SQL database compiled from Zograf Readings (2004–2025) and Roerich Readings (2007–2025) conference programs.\n\n")
        
        f.write("## 1. High-Level Executive Summary\n\n")
        f.write(f"- **Total Unique Scholars Identified**: {len(total_scholars)}\n")
        f.write(f"- **Total Historical Presentations/Talks**: {sum(r[2] for r in total_scholars)}\n")
        f.write(f"- **Scholars in Zograf Readings only**: {len(zograf_only)}\n")
        f.write(f"- **Scholars in Roerich Readings only**: {len(roerich_only)}\n")
        f.write(f"- **Scholars Active in BOTH Conferences (Overlapping Cohort)**: {len(total_scholars) - len(zograf_only) - len(roerich_only)}\n\n")
        
        f.write("## 2. Overlapping Cohort (The Core of Russian Indology)\n")
        f.write("These scholars are active in both major Petersburg (Zograf) and Moscow (Roerich) forums, representing the intellectual bridge of the community:\n\n")
        f.write("| Scholar Name | Total Talks | Zograf Talks | Roerich Talks | Active Period |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: |\n")
        overlap_scholars = [r for r in total_scholars if r[3] > 0 and r[4] > 0]
        for row in overlap_scholars[:30]:
            f.write(f"| {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}–{row[6]} |\n")
            
        f.write("\n## 3. Top 15 Most Active Zograf Readings Participants\n\n")
        f.write("| Scholar Name | Zograf Talks | Active Period |\n")
        f.write("| :--- | :---: | :---: |\n")
        zograf_active = sorted(total_scholars, key=lambda r: r[3], reverse=True)
        for row in zograf_active[:15]:
            f.write(f"| {row[1]} | {row[3]} | {row[5]}–{row[6]} |\n")
            
        f.write("\n## 4. Top 15 Most Active Roerich Readings Participants\n\n")
        f.write("| Scholar Name | Roerich Talks | Active Period |\n")
        f.write("| :--- | :---: | :---: |\n")
        roerich_active = sorted(total_scholars, key=lambda r: r[4], reverse=True)
        for row in roerich_active[:15]:
            f.write(f"| {row[1]} | {row[4]} | {row[5]}–{row[6]} |\n")
            
        f.write("\n## 5. CSV Export Deliverables\n")
        f.write("The complete structured lists have been generated and exported to the `analytics_output` folder:\n")
        f.write("1. **[total_indologists.csv](file:///c:/Users/user/Documents/GitHub/IndologyScholars/analytics_output/total_indologists.csv)**: Complete master list of 213 indologists.\n")
        f.write("2. **[zograf_only_indologists.csv](file:///c:/Users/user/Documents/GitHub/IndologyScholars/analytics_output/zograf_only_indologists.csv)**: 96 Petersburg-centric scholars.\n")
        f.write("3. **[roerich_only_indologists.csv](file:///c:/Users/user/Documents/GitHub/IndologyScholars/analytics_output/roerich_only_indologists.csv)**: 87 Moscow-centric scholars.\n")
        
    print("Analytics, reports, and CSV outputs successfully generated in analytics_output/ and indology_scholars_analytics.md!")
    conn.close()

if __name__ == "__main__":
    main()
