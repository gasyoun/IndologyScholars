import sqlite3
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    conn = sqlite3.connect('conferences.db')
    cur = conn.cursor()
    
    if len(sys.argv) < 2:
        print("Usage: python check_scholar_presentations.py <person_id_or_name_key>")
        conn.close()
        return
        
    search_term = sys.argv[1]
    
    # Search by ID or key
    cur.execute("""
        SELECT person_id, display_name, normalized_key, birth_year, death_year
        FROM person
        WHERE person_id = ? OR normalized_key LIKE ? OR display_name LIKE ?
    """, (search_term, f"%{search_term}%", f"%{search_term}%"))
    
    persons = cur.fetchall()
    if not persons:
        print("No person found.")
        conn.close()
        return
        
    for p in persons:
        pid, name, key, byear, dyear = p
        print(f"\n==================================================")
        print(f"ID: {pid} | Name: {name} | Key: {key} | Years: {byear}-{dyear}")
        print(f"==================================================")
        
        cur.execute("""
            SELECT p.title, e.year, e.event_id, pp.affiliation_text_raw
            FROM presentation p
            JOIN presentation_person pp ON pp.presentation_id = p.presentation_id
            JOIN session s ON s.session_id = p.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            WHERE pp.person_id = ?
        """, (pid,))
        
        for r in cur.fetchall():
            print(f"Year: {r[1]} | Conf: {r[2]} | Aff: {r[3]}\nTitle: {r[0]}")
            print("-" * 50)
            
    conn.close()

if __name__ == '__main__':
    main()
