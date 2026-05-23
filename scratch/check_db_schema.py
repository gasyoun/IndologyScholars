import sqlite3

def run():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        print(table, [col[1] for col in cursor.fetchall()])
    conn.close()

if __name__ == '__main__':
    run()
