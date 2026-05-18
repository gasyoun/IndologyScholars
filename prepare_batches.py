import sqlite3
import os

def prepare_batches(batch_size=20):
    conn = sqlite3.connect('indology_scholars.db')
    cursor = conn.cursor()
    
    # Берем только те записи, которые еще не были структурированы
    cursor.execute('''
        SELECT id, extracted_name, raw_biography 
        FROM scholars 
        WHERE id NOT IN (SELECT raw_text_id FROM structured_scholars)
    ''')
    raw_entries = cursor.fetchall()
    
    output_dir = 'chatgpt_prompts'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Инструкция (Schema) для ChatGPT
    system_prompt = """
Ты — эксперт-архивариус. Я дам тебе массив биографий. Твоя задача — вернуть МАССИВ строго валидных JSON-объектов.
Ничего не удаляй! Все труды и книги помести в массив "bibliography", а все остальные факты (награды, семья) в строку "additional_notes".

Структура каждого JSON-объекта ДОЛЖНА быть такой:
{
  "raw_text_id": (ОБЯЗАТЕЛЬНО: возьми из моего запроса),
  "last_name": "Фамилия",
  "first_names": "Имя и отчество (если есть)",
  "birth_date": "YYYY-MM-DD или год",
  "birth_place": "Город, Страна",
  "death_date": "YYYY-MM-DD или год",
  "death_place": "Город, Страна",
  "specializations": ["область1", "язык2"],
  "institutions": ["Университет1"],
  "bibliography": ["Труд 1", "Книга 2"],
  "additional_notes": "Любые другие биографические детали."
}

Ответь ТОЛЬКО валидным JSON-массивом (начинается с [ и заканчивается ]). Без приветствий и пояснений.

Вот данные:
"""

    total_batches = (len(raw_entries) + batch_size - 1) // batch_size

    for i in range(total_batches):
        batch = raw_entries[i * batch_size:(i + 1) * batch_size]
        
        prompt_content = system_prompt + "\n"
        
        for row_id, name, raw_bio in batch:
            prompt_content += f"\n--- НАЧАЛО ЗАПИСИ (raw_text_id: {row_id}) ---\n"
            prompt_content += f"Имя в базе: {name}\n"
            prompt_content += f"Текст биографии: {raw_bio}\n"
            prompt_content += f"--- КОНЕЦ ЗАПИСИ ---\n"

        file_path = os.path.join(output_dir, f'batch_{i+1:03d}.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt_content)
            
    conn.close()
    print(f"Готово! Создано {total_batches} файлов с промптами в папке '{output_dir}'.")

if __name__ == "__main__":
    prepare_batches()
