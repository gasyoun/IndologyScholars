import sqlite3
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    conn = sqlite3.connect('conferences.db')
    cur = conn.cursor()
    cur.execute("SELECT person_id, display_name, full_name_ru, full_name_en, birth_year, death_year FROM person WHERE person_id = 'PERS_8e117242'")
    row = cur.fetchone()
    print("Row:", row)
    conn.close()

if __name__ == '__main__':
    main()
