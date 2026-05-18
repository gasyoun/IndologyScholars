import sqlite3

def test_db():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    cursor.execute("SELECT day_label_raw FROM event_day WHERE event_day_id = 'D2004_1'")
    row = cursor.fetchone()
    if row:
        print(f"Direct raw value: {repr(row[0])}")
        with open("scratch/db_raw_out.txt", 'w', encoding='utf-8') as f:
            f.write(row[0])
    conn.close()

if __name__ == "__main__":
    test_db()
