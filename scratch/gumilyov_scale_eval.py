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

SYSTEM_PROMPT = """Вы - эксперт по истории науки и индологии, применяющий методологию Льва Гумилева (три уровня научного поиска).
Определите уровень доклада (1, 2 или 3) на основе предоставленного текста.
Верните ТОЛЬКО одну цифру: 1, 2 или 3.

Определения:
1 (Микроистория): Исследование деталей, частностей, биографий, отдельных документов, дат, фактов, узких лингвистических особенностей.
2 (Региональный): События, причинно-следственные связи в рамках одной эпохи или одной страны (региона), общая история учения.
3 (Глобальный): Широкие обобщения, глобальные закономерности, взаимодействие огромных человеческих массивов (этносов, суперэтносов, цивилизаций), длительные сдвиги тысячелетий.
"""

def call_llm(text):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Текст для классификации:\n{text}"}
        ],
        "temperature": 0.1,
        "max_tokens": 10
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        digits = [c for c in content if c.isdigit()]
        if digits:
            return int(digits[0])
        return -1
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return -1

def main():
    conn = sqlite3.connect('conferences.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.presentation_id, p.title, m.media_title
        FROM presentation p
        JOIN media m ON p.presentation_id = m.attached_to_id
        WHERE m.attached_to_type = 'presentation' AND m.media_type = 'video'
    ''')
    records = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(records)} videos. Starting LLM comparison...")
    results = []
    
    for pid, title, media_title in records:
        print(f"Processing {pid}: {title}")
        
        # 1. Title Only
        t_only = call_llm(f"Название доклада: {title}")
        time.sleep(0.5)
        
        # 2. Title + Video Title Context
        v_ctx = call_llm(f"Название доклада: {title}\nРасширенный контекст (название видеозаписи): {media_title}")
        time.sleep(0.5)
        
        results.append({
            "presentation_id": pid,
            "title": title,
            "video_title": media_title,
            "level_title_only": t_only,
            "level_video_context": v_ctx,
            "match": t_only == v_ctx
        })
    
    df = pd.DataFrame(results)
    out_path = "analytics_output/gumilyov_video_comparison.csv"
    os.makedirs("analytics_output", exist_ok=True)
    df.to_csv(out_path, index=False, encoding='utf-8')
    
    matches = df['match'].sum()
    print(f"\n--- RESULTS ---")
    print(f"Saved to {out_path}")
    print(f"Total Matches: {matches} / {len(df)} ({matches/len(df)*100:.1f}%)")
    
    discrepancies = df[~df['match']]
    print(f"\nDiscrepancies ({len(discrepancies)}):")
    for _, row in discrepancies.iterrows():
        print(f"[{row['presentation_id']}] Title: {row['title']} | Video: {row['video_title']}")
        print(f"  Title-Only: {row['level_title_only']} | Video-Context: {row['level_video_context']}")

if __name__ == "__main__":
    main()
