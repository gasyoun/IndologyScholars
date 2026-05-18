import sqlite3
import json

DB_PATH = "conferences.db"
OUTPUT_FILE = "site_data.js"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch all scholars
    cursor.execute("""
        SELECT 
            p.person_id,
            p.display_name,
            p.normalized_key,
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
    scholars_raw = cursor.fetchall()
    
    scholars = []
    for r in scholars_raw:
        # Get all talks for this scholar
        cursor.execute("""
            SELECT 
                pr.title, 
                e.year, 
                es.series_name_en, 
                pp.affiliation_text_raw,
                pr.is_online
            FROM presentation pr
            JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            JOIN event_series es ON es.event_series_id = e.event_series_id
            WHERE pp.person_id = ?
            ORDER BY e.year DESC
        """, (r[0],))
        talks_raw = cursor.fetchall()
        talks = []
        for t in talks_raw:
            talks.append({
                "title": t[0],
                "year": t[1],
                "series": t[2],
                "affiliation": t[3],
                "is_online": bool(t[4])
            })
            
        scholars.append({
            "id": r[0],
            "name": r[1],
            "total_talks": r[3],
            "zograf_talks": r[4],
            "roerich_talks": r[5],
            "first_year": r[6],
            "last_year": r[7],
            "talks": talks
        })
        
    # 2. Fetch all timeline talks grouped by Year and Series
    cursor.execute("""
        SELECT 
            e.year,
            es.series_name_en,
            p.display_name,
            pp.affiliation_text_raw,
            pr.title,
            pr.is_online,
            v.display_name,
            ed.day_label_raw,
            s.session_title
        FROM presentation pr
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN venue v ON v.venue_id = edv.venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        ORDER BY e.year DESC, es.event_series_id ASC, ed.day_number ASC, pr.presentation_id ASC
    """)
    timeline_raw = cursor.fetchall()
    
    timeline = {}
    for r in timeline_raw:
        year = str(r[0])
        series = r[1]
        if year not in timeline:
            timeline[year] = {"Zograf": [], "Roerich": []}
        
        series_key = "Zograf" if "Zograf" in series else "Roerich"
        timeline[year][series_key].append({
            "speaker": r[2],
            "affiliation": r[3],
            "title": r[4],
            "is_online": bool(r[5]),
            "venue": r[6],
            "day": r[7],
            "session": r[8]
        })

    # 3. Calculate year-by-year statistics for charts
    cursor.execute("""
        SELECT e.year, 
               SUM(CASE WHEN e.event_series_id = 1 THEN 1 ELSE 0 END) as zograf_talks,
               SUM(CASE WHEN e.event_series_id = 2 THEN 1 ELSE 0 END) as roerich_talks
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        GROUP BY e.year
        ORDER BY e.year ASC
    """)
    stats_raw = cursor.fetchall()
    stats = []
    for r in stats_raw:
        stats.append({
            "year": r[0],
            "zograf": r[1],
            "roerich": r[2],
            "total": r[1] + r[2]
        })

    # Write as a javascript module file
    site_data = {
        "scholars": scholars,
        "timeline": timeline,
        "stats": stats
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("const CONFERENCE_DATA = ")
        json.dump(site_data, f, ensure_ascii=False, indent=2)
        f.write(";\n")
        
    print(f"Successfully generated JS data structure in {OUTPUT_FILE}!")
    conn.close()

if __name__ == "__main__":
    main()
