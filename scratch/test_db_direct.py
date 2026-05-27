import sqlite3

def test_db():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    cursor.execute("SELECT person_id, display_name, normalized_key, birth_year FROM person WHERE birth_year IS NULL")
    rows = cursor.fetchall()
    
    with open("scratch/db_raw_out.txt", 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(f"ID: {row[0]} | Display Name: {row[1]} | Key: {row[2]} | Birth: {row[3]}\n")
            
    print(f"Wrote {len(rows)} rows to scratch/db_raw_out.txt")
    conn.close()

if __name__ == "__main__":
    test_db()
