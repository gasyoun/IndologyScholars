import sqlite3

def test():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    cursor.execute("SELECT person_id, display_name, normalized_key, birth_year FROM person WHERE person_id = 'PERS_9f159bcf'")
    row = cursor.fetchone()
    print("Found PERS_9f159bcf:")
    print(row)
    conn.close()

if __name__ == "__main__":
    test()
