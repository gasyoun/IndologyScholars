import sqlite3
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    conn = sqlite3.connect('conferences.db')
    cur = conn.cursor()
    
    # Let's check event table columns first
    cur.execute("PRAGMA table_info(event)")
    cols = [r[1] for r in cur.fetchall()]
    print("Event table columns:", cols)
    
    # We will construct a safe select query based on common columns
    for pid in ['PERS_8e117242', 'PERS_04c4d444']:
        print(f"\n--- ID: {pid} ---")
        cur.execute("""
            SELECT p.title, e.year, e.event_id
            FROM presentation p
            JOIN presentation_person pp ON pp.presentation_id = p.presentation_id
            JOIN session s ON s.session_id = p.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            WHERE pp.person_id = ?
        """, (pid,))
        for row in cur.fetchall():
            print(f"Year: {row[1]} | EventID: {row[2]} | Title: {row[0]}")
            
    conn.close()

if __name__ == '__main__':
    main()
