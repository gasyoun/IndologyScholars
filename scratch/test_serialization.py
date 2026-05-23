import sqlite3

def main():
    con = sqlite3.connect("conferences.db")
    cursor = con.cursor()
    cursor.execute("SELECT title FROM presentation WHERE title LIKE 'К %'")
    rows = [r[0] for r in cursor.fetchall() if r[0]]
    with open("scratch/k_titles.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(rows)))

if __name__ == '__main__':
    main()
