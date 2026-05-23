import sqlite3

def run():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.person_id, p.display_name, pr.title, e.year, pp.affiliation_text_raw
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE p.person_id = 'PERS_6b867946'
    """)
    rows = cursor.fetchall()
    with open("scratch/check_db_sharygin_out.txt", "w", encoding="utf-8") as f:
        f.write("Presentations:\n")
        for row in rows:
            f.write(str(row) + "\n")
    conn.close()

if __name__ == '__main__':
    run()
