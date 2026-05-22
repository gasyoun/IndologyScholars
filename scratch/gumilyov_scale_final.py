import os
import sys
import json
import sqlite3
import pandas as pd
import requests
import time
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

load_dotenv()
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not found in .env")
    sys.exit(1)

SYSTEM_PROMPT = """Вы - строгий эксперт по истории науки и индологии, применяющий методологию Льва Гумилева (три уровня научного поиска).
Определите уровень доклада (1, 2 или 3) на основе ТОЛЬКО его названия.
Верните ТОЛЬКО одну цифру: 1, 2 или 3. (И ничего больше, никаких точек или текста).

Определения:
1 (Микроистория): Исследование деталей, частностей, биографий, отдельных документов, дат, фактов, узких лингвистических особенностей. 
КРИТИЧЕСКОЕ ПРАВИЛО: Если доклад анализирует ОДИН конкретный текст (например, роман, сутру, главу Махабхараты), концепцию ОДНОГО автора (писателя, мыслителя, например, Г. Оберхаммера) или ОДИН конкретный лингвистический термин, это СТРОГО Уровень 1. Даже если в названии звучат громкие слова вроде "трансцендентальный", "религия" или "история".
2 (Региональный): События, причинно-следственные связи в рамках одной эпохи или одной страны (региона), история целого учения или традиции (например, "история буддизма в Тибете", "современные баулы").
3 (Глобальный): Широкие обобщения, глобальные закономерности, взаимодействие огромных человеческих массивов (суперэтносов, цивилизаций), длительные сдвиги тысячелетий.
"""

def call_llm(text):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Название доклада: {text}"}
        ],
        "temperature": 0.0,
        "max_tokens": 5
    }
    
    for attempt in range(3):
        try:
            resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            digits = [c for c in content if c.isdigit()]
            if digits:
                return int(digits[0])
            return 2 # default fallback
        except Exception as e:
            time.sleep(2)
    return 2 # fallback if all attempts fail

def main():
    conn = sqlite3.connect('conferences.db')
    cursor = conn.cursor()
    # Fetch unique (year, series_id, title) since we now use this natural key
    cursor.execute('''
        SELECT DISTINCT e.year, e.event_series_id, p.title
        FROM presentation p
        JOIN session s ON p.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE p.title IS NOT NULL AND p.title != ''
    ''')
    records = cursor.fetchall()
    conn.close()
    
    print(f"Loaded {len(records)} unique presentations. Processing...")
    
    # Allow resuming
    out_path = "analytics_output/gumilyov_scale.csv"
    existing_keys = set()
    if os.path.exists(out_path):
        df_ex = pd.read_csv(out_path)
        for _, row in df_ex.iterrows():
            existing_keys.add(f"{row['year']}-{row['series_id']}-{row['title']}")
        results = df_ex.to_dict('records')
    else:
        results = []
    
    new_count = 0
    for idx, (year, series_id, title) in enumerate(records):
        key = f"{year}-{series_id}-{title}"
        if key in existing_keys:
            continue
            
        print(f"[{idx}/{len(records)}] Classifying: {title}")
        level = call_llm(title)
        
        results.append({
            "year": year,
            "series_id": series_id,
            "title": title,
            "gumilyov_level": level
        })
        new_count += 1
        
        # Save checkpoints
        if new_count % 50 == 0:
            pd.DataFrame(results).to_csv(out_path, index=False)
            print(f"Checkpoint saved ({len(results)} items)")
            
    # Final save
    if new_count > 0:
        pd.DataFrame(results).to_csv(out_path, index=False)
    
    print(f"Done. Processed {new_count} new records. Saved {len(results)} total to {out_path}.")

if __name__ == "__main__":
    main()
