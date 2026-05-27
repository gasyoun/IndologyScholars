import re
import csv
import difflib

def verify_db(conn):
    cursor = conn.cursor()
    print("\n--- DATABASE SUMMARY VERIFICATION ---")
    
    # Event Series
    cursor.execute("SELECT * FROM event_series")
    print(f"Event Series count: {len(cursor.fetchall())}")
    
    # Events
    cursor.execute("SELECT event_series_id, COUNT(*) FROM event GROUP BY event_series_id")
    print(f"Events per Series: {cursor.fetchall()}")
    
    # EventDays
    cursor.execute("SELECT COUNT(*) FROM event_day")
    print(f"Total Event Days: {cursor.fetchone()[0]}")
    
    # Persons
    cursor.execute("SELECT COUNT(*) FROM person")
    print(f"Total Unique Scholars/Persons: {cursor.fetchone()[0]}")
    
    # Presentations
    cursor.execute("SELECT COUNT(*) FROM presentation")
    print(f"Total Presentations parsed: {cursor.fetchone()[0]}")
    
    # Show top 10 speakers across both series
    cursor.execute("""
        SELECT p.display_name, COUNT(*) as cnt 
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        GROUP BY pp.person_id 
        ORDER BY cnt DESC LIMIT 10
    """)
    print("\nTop 10 Speakers (Combined Zograf and Roerich):")
    for row in cursor.fetchall():
        print(f" - {row[0]}: {row[1]} talks")
        
    # Check overlap of participants between Zograf (1) and Roerich (2)
    cursor.execute("""
        SELECT DISTINCT p.display_name 
        FROM presentation_person pp1
        JOIN presentation pr1 ON pr1.presentation_id = pp1.presentation_id
        JOIN session s1 ON s1.session_id = pr1.session_id
        JOIN event_day_venue edv1 ON edv1.event_day_venue_id = s1.event_day_venue_id
        JOIN event_day ed1 ON ed1.event_day_id = edv1.event_day_id
        JOIN event e1 ON e1.event_id = ed1.event_id
        JOIN person p ON p.person_id = pp1.person_id
        WHERE e1.event_series_id = 1
        INTERSECT
        SELECT DISTINCT p.display_name 
        FROM presentation_person pp2
        JOIN presentation pr2 ON pr2.presentation_id = pp2.presentation_id
        JOIN session s2 ON s2.session_id = pr2.session_id
        JOIN event_day_venue edv2 ON edv2.event_day_venue_id = s2.event_day_venue_id
        JOIN event_day ed2 ON ed2.event_day_id = edv2.event_day_id
        JOIN event e2 ON e2.event_id = ed2.event_id
        JOIN person p ON p.person_id = pp2.person_id
        WHERE e2.event_series_id = 2
    """)
    overlap = cursor.fetchall()
    print(f"\nTotal Overlapping Participants (attended BOTH Zograf and Roerich): {len(overlap)}")
    print("Sample overlap speakers:")
    for row in overlap[:10]:
        print(f" - {row[0]}")


def ingest_video_media(conn):
    """Read analytics_output/video_presentation_mapping.csv and insert
    YouTube videos as media rows attached to their matched presentations.
    """
    mapping_path = "analytics_output/video_presentation_mapping.csv"
    try:
        f = open(mapping_path, "r", encoding="utf-8")
    except FileNotFoundError:
        print(f"  (no {mapping_path} — skipping video ingestion)")
        return

    cursor = conn.cursor()

    def _norm(text):
        if not text:
            return ""
        t = text.lower().replace("ё", "е")
        t = re.sub(r"[^\w\s\-]", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    # Cache presentations per year
    by_year_cache = {}

    def _get_candidates(year):
        if year not in by_year_cache:
            rows = cursor.execute("""
                SELECT pr.presentation_id, pr.title,
                       GROUP_CONCAT(pers.display_name, ' / ')
                FROM presentation pr
                JOIN session s ON s.session_id = pr.session_id
                JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
                JOIN event_day ed ON ed.event_day_id = edv.event_day_id
                JOIN event e ON e.event_id = ed.event_id
                JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
                JOIN person pers ON pers.person_id = pp.person_id
                WHERE e.event_series_id = 1 AND e.year = ?
                GROUP BY pr.presentation_id
            """, (year,)).fetchall()
            by_year_cache[year] = [(pid, t, sp) for pid, t, sp in rows]
        return by_year_cache[year]

    inserted = 0
    no_match = 0
    skipped = 0
    REINGEST_THRESHOLD = 0.55

    with f:
        for row in csv.DictReader(f):
            status = (row.get("status") or "").strip()
            if status not in ("auto", "manual_confirmed"):
                skipped += 1
                continue
            year_str = (row.get("year") or "").strip()
            if not year_str.isdigit():
                skipped += 1
                continue
            year = int(year_str)
            video_url = (row.get("video_url") or "").strip()
            video_id = (row.get("video_id") or "").strip()
            video_title = (row.get("video_title") or "").strip()
            title_hint = (row.get("title_hint") or "").strip()
            speaker_hint = (row.get("speaker_hint") or "").strip()
            if not video_url or not title_hint:
                skipped += 1
                continue

            target = _norm(title_hint + " " + speaker_hint)
            best_pid = None
            best_ratio = 0.0
            for pid, title, speakers in _get_candidates(year):
                candidate_norm = _norm(title + " " + (speakers or ""))
                r = difflib.SequenceMatcher(None, target, candidate_norm).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best_pid = pid
            if not best_pid or best_ratio < REINGEST_THRESHOLD:
                no_match += 1
                continue

            media_id = f"YT_{video_id}"
            cursor.execute("DELETE FROM media WHERE media_id = ?", (media_id,))
            cursor.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?)",
                (media_id, "presentation", best_pid, "video", video_url, video_title,
                 "video/youtube", video_url, f"hint-matched at build time (ratio={best_ratio:.2f}, status={status})")
            )
            inserted += 1
    conn.commit()
    print(f"  Video media: {inserted} inserted, {no_match} could not be matched against current DB, {skipped} skipped (status != auto/manual_confirmed)")
