import sqlite3
import json
import os
import glob

def setup_structured_tables(conn):
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS structured_scholars (id INTEGER PRIMARY KEY, last_name TEXT, first_names TEXT, birth_date TEXT, birth_place TEXT, death_date TEXT, death_place TEXT, additional_notes TEXT, raw_text_id INTEGER UNIQUE, FOREIGN KEY(raw_text_id) REFERENCES scholars(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS scholar_tags (scholar_id INTEGER, tag TEXT, FOREIGN KEY(scholar_id) REFERENCES structured_scholars(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS scholar_bibliography (scholar_id INTEGER, work_title TEXT, FOREIGN KEY(scholar_id) REFERENCES structured_scholars(id))''')
    conn.commit()

def import_json_results(results_dir='chatgpt_results'):
    if not os.path.exists(results_dir):
        print(f"Папка {results_dir} не найдена. Создайте ее и положите туда JSON-ответы от ChatGPT.")
        return

    conn = sqlite3.connect('indology_scholars.db')
    setup_structured_tables(conn)
    cursor = conn.cursor()
    
    json_files = glob.glob(os.path.join(results_dir, '*.json'))
    total_imported = 0

    for file_path in json_files:
        print(f"Обработка файла: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_array = json.load(f)
                
            for data in data_array:
                raw_text_id = data.get('raw_text_id')
                if not raw_text_id:
                    print("Ошибка: В JSON нет raw_text_id, пропускаем.")
                    continue
                    
                cursor.execute('SELECT id FROM structured_scholars WHERE raw_text_id = ?', (raw_text_id,))
                if cursor.fetchone():
                    print(f"Запись raw_text_id {raw_text_id} уже импортирована. Пропуск.")
                    continue

                cursor.execute('''
                    INSERT INTO structured_scholars (last_name, first_names, birth_date, birth_place, death_date, death_place, additional_notes, raw_text_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data.get('last_name'), data.get('first_names'), 
                    data.get('birth_date'), data.get('birth_place'), 
                    data.get('death_date'), data.get('death_place'), 
                    data.get('additional_notes'), raw_text_id
                ))
                
                new_scholar_id = cursor.lastrowid
                
                for tag in data.get('specializations', []):
                    if tag:
                        cursor.execute('INSERT INTO scholar_tags (scholar_id, tag) VALUES (?, ?)', (new_scholar_id, tag.strip().lower()))
                
                for work in data.get('bibliography', []):
                    if work:
                        cursor.execute('INSERT INTO scholar_bibliography (scholar_id, work_title) VALUES (?, ?)', (new_scholar_id, work.strip()))
                
                total_imported += 1
                
            conn.commit()
            print(f"Файл {os.path.basename(file_path)} успешно импортирован.")
            
        except json.JSONDecodeError as e:
            print(f"Ошибка в формате JSON в файле {file_path}: {e}")
            conn.rollback()
        except Exception as e:
            print(f"Непредвиденная ошибка при обработке {file_path}: {e}")
            conn.rollback()

    conn.close()
    print(f"Готово. Всего импортировано {total_imported} записей.")

if __name__ == "__main__":
    import_json_results()
