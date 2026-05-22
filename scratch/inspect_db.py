import sqlite3

def main():
    con = sqlite3.connect("conferences.db")
    cursor = con.cursor()
    cursor.execute("""
        select affiliation_text_raw, count(*) as c
        from presentation_person
        group by affiliation_text_raw
        order by c desc
    """)
    out = []
    for row in cursor.fetchall():
        aff = row[0] or "NULL"
        out.append(f"{aff}: {row[1]}")
        
    with open("scratch/top_affiliations.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out))

if __name__ == '__main__':
    main()
