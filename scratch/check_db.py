import sqlite3
import sys

def main():
    conn = sqlite3.connect('conferences.db')
    cur = conn.cursor()
    cur.execute("SELECT person_id, display_name, normalized_key, birth_year, death_year FROM person")
    rows = cur.fetchall()
    
    missing = [row for row in rows if row[3] is None]
    
    with open('scratch/missing_birth_years_list.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total scholars: {len(rows)}\n")
        f.write(f"Scholars missing birth year: {len(missing)}\n\n")
        for i, row in enumerate(missing, 1):
            f.write(f"{i:3d}. ID: {row[0]} | Display Name: {row[1]} | Key: {row[2]} | Years: {row[3]}-{row[4]}\n")
            
    print("Done. Wrote list to scratch/missing_birth_years_list.txt")
    conn.close()

if __name__ == '__main__':
    main()
