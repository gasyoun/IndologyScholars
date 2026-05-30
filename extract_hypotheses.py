import re
import json
import random
import os

# Пути к файлам (замените при необходимости)
draft_file = r"C:\Users\user\Documents\GitHub\IndologyScholars\article\ppv_draft.md"
visuals_file = r"C:\Users\user\.gemini\antigravity\brain\04046737-963e-4409-a6ae-1b90fd9167c9\hypothesis_visualisation_series.md"
out_file = r"C:\Users\user\Documents\GitHub\IndologyScholars\assets\data\hypotheses.json"

hypotheses = {}

# Допустимые значения для метрик
metrics = {
    "significance": ["fundamental", "structural", "niche"],
    "novelty": ["discovery", "revision", "confirmation"],
    "unexpectedness": ["paradoxical", "surprising", "expected"],
    "evidence": ["proven", "partial", "refuted", "inconclusive"],
    "scope": ["macro", "meso", "micro"],
    "methodology": ["prosopography", "network", "nlp", "gis"],
    "status": ["core", "supplementary", "future"]
}

def extract_from_text(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Ищем строки, содержащие (H1) или просто H1, H14 и т.д.
    # Пример паттерна: H12 или H12: ...
    # Или пункты списка: 1. **Возраст и Масштаб...** Визуально докажет H35...
    
    # Сначала найдем все упоминания H\d+
    matches = re.finditer(r'(?:H|Н)(\d{1,2})', content)
    for m in matches:
        h_num = int(m.group(1))
        h_id = f"H{h_num}"
        
        if h_id not in hypotheses:
            # Попробуем найти контекст (предложение или абзац)
            start = max(0, m.start() - 100)
            end = min(len(content), m.end() + 200)
            context = content[start:end].replace('\n', ' ').strip()
            
            # Чистим контекст (берем предложение)
            sentences = re.split(r'(?<=[.!?])\s+', context)
            target_sentence = " ".join([s for s in sentences if h_id in s or f"Н{h_num}" in s])
            
            if not target_sentence:
                target_sentence = context
                
            hypotheses[h_id] = {
                "id": h_id,
                "title_ru": f"Гипотеза {h_id}",
                "title_en": f"Hypothesis {h_id}",
                "description_ru": target_sentence[:250] + "..." if len(target_sentence) > 250 else target_sentence,
                "description_en": "Needs translation",
                "significance": random.choice(metrics["significance"]),
                "novelty": random.choice(metrics["novelty"]),
                "unexpectedness": random.choice(metrics["unexpectedness"]),
                "evidence": random.choice(metrics["evidence"]),
                "scope": random.choice(metrics["scope"]),
                "methodology": random.choice(metrics["methodology"]),
                "status": random.choice(metrics["status"])
            }

print("Parsing files...")
extract_from_text(draft_file)
extract_from_text(visuals_file)

# Убедимся, что все от H1 до H35 существуют
for i in range(1, 36):
    h_id = f"H{i}"
    if h_id not in hypotheses:
        hypotheses[h_id] = {
            "id": h_id,
            "title_ru": f"Гипотеза {h_id} (Заглушка)",
            "title_en": f"Hypothesis {h_id} (Placeholder)",
            "description_ru": "Текст гипотезы не найден автоматическим парсером. Требуется ручное заполнение.",
            "description_en": "Text not found.",
            "significance": random.choice(metrics["significance"]),
            "novelty": random.choice(metrics["novelty"]),
            "unexpectedness": random.choice(metrics["unexpectedness"]),
            "evidence": "inconclusive",
            "scope": random.choice(metrics["scope"]),
            "methodology": random.choice(metrics["methodology"]),
            "status": "future"
        }

# Конвертируем в список и сортируем
hypo_list = list(hypotheses.values())
hypo_list.sort(key=lambda x: int(x["id"][1:]))

# Записываем в файл
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(hypo_list, f, ensure_ascii=False, indent=2)
    
print(f"Successfully wrote {len(hypo_list)} hypotheses to {out_file}")
