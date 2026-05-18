import sqlite3

def inspect():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    
    # 1. Check tables and counts
    print("--- TABLES ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        print(f"Table {t}: {cnt} rows")
        
    # 2. Check event_day columns
    print("\n--- event_day COLUMNS ---")
    cursor.execute("PRAGMA table_info(event_day)")
    for col in cursor.fetchall():
        print(col)
        
    # 3. Check presentation columns
    print("\n--- presentation COLUMNS ---")
    cursor.execute("PRAGMA table_info(presentation)")
    for col in cursor.fetchall():
        print(col)
        
    # 4. Check presentation_person columns
    print("\n--- presentation_person COLUMNS ---")
    cursor.execute("PRAGMA table_info(presentation_person)")
    for col in cursor.fetchall():
        print(col)
        
    # 5. Check a few sample days
    print("\n--- SAMPLE DAYS ---")
    cursor.execute("SELECT * FROM event_day LIMIT 5")
    for r in cursor.fetchall():
        print(r)
        
    # 6. Check a few sample sessions
    print("\n--- SAMPLE SESSIONS ---")
    cursor.execute("SELECT * FROM session LIMIT 5")
    for r in cursor.fetchall():
        print(r)

    # 7. Check a few sample presentation_persons
    print("\n--- SAMPLE PRESENTATION_PERSONS ---")
    cursor.execute("SELECT * FROM presentation_person LIMIT 5")
    for r in cursor.fetchall():
        print(r)
        
    conn.close()

if __name__ == "__main__":
    inspect()
