import sqlite3
import os
import re

def extract_year(date_str):
    if not date_str:
        return None
    match = re.search(r'\b(1[4-9]\d{2}|20\d{2})\b', date_str)
    return int(match.group(1)) if match else None

def generate_jubilee_markdowns(start_year=2026, span=20, db_path='indology_scholars.db', output_dir='jubilees'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    intervals = {50, 75, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 500}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT last_name, first_names, birth_date, death_date 
            FROM structured_scholars 
            ORDER BY last_name ASC
        ''')
        scholars = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Ошибка: Таблица 'structured_scholars' не найдена.")
        return
    finally:
        conn.close()

    files_created = 0

    for current_year in range(start_year, start_year + span):
        birth_jubilees = []
        death_jubilees = []

        for row in scholars:
            last_name, first_names = row[0] or "Unknown", row[1] or ""
            b_date, d_date = row[2] or "Unknown", row[3] or "Unknown"
            
            b_year, d_year = extract_year(b_date), extract_year(d_date)
            full_name = f"{first_names} {last_name}".strip()

            if b_year and (current_year - b_year) in intervals:
                birth_jubilees.append((current_year - b_year, full_name, b_date, d_date))

            if d_year and (current_year - d_year) in intervals:
                death_jubilees.append((current_year - d_year, full_name, b_date, d_date))

        if not birth_jubilees and not death_jubilees:
            continue

        birth_jubilees.sort(key=lambda x: x[0], reverse=True)
        death_jubilees.sort(key=lambda x: x[0], reverse=True)

        md_content = f"---\ntitle: Памятные даты индологии {current_year}\nyear: {current_year}\ntype: commemorative-index\n---\n\n"
        md_content += f"# Памятные даты: {current_year}\n\n"

        if birth_jubilees:
            md_content += "## Годовщины со дня рождения\n\n"
            for ann, name, b, d in birth_jubilees:
                md_content += f"- **{name}**: {ann}-летие со дня рождения (b. {b} — d. {d})\n"
            md_content += "\n"

        if death_jubilees:
            md_content += "## Годовщины со дня смерти\n\n"
            for ann, name, b, d in death_jubilees:
                md_content += f"- **{name}**: {ann}-летие со дня смерти (b. {b} — d. {d})\n"

        file_path = os.path.join(output_dir, f"anniversaries_{current_year}.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        files_created += 1

    print(f"Готово. Создано {files_created} файлов в папке '{output_dir}/'.")

if __name__ == "__main__":
    generate_jubilee_markdowns()
