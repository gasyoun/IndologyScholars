import sqlite3
import re
from collections import Counter

DB_PATH = "conferences.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Geo Map (Cities)
cursor.execute("SELECT affiliation_text_raw FROM presentation_person WHERE affiliation_text_raw IS NOT NULL AND affiliation_text_raw != ''")
affiliations = [row[0] for row in cursor.fetchall()]

# Extremely simple city extraction heuristic for top Russian/Indology centers
cities = {
    "Санкт-Петербург": ["спб", "санкт-петербург", "st. petersburg", "st petersburg", "leningrad"],
    "Москва": ["москва", "moscow"],
    "Улан-Удэ": ["улан-удэ", "ulan-ude"],
    "Новосибирск": ["новосибирск", "novosibirsk"],
    "Кызыл": ["кызыл", "kyzyl"],
    "Элиста": ["элиста", "elista"],
    "Казань": ["казань", "kazan"],
    "Пенза": ["пенза", "penza"],
    "Лондон": ["лондон", "london"],
    "Париж": ["париж", "paris"],
    "Дели": ["дели", "delhi", "new delhi"]
}

city_counts = Counter()
for aff in affiliations:
    aff_lower = aff.lower()
    for city_name, synonyms in cities.items():
        if any(syn in aff_lower for syn in synonyms):
            city_counts[city_name] += 1
            break # only count one city per affiliation

print("Top Cities:", city_counts.most_common(10))

# 2. Keyword Bubble Cloud
cursor.execute("SELECT keywords FROM presentation WHERE keywords IS NOT NULL AND keywords != ''")
keywords_raw = [row[0] for row in cursor.fetchall()]

all_keywords = []
for k_str in keywords_raw:
    # keywords might be comma separated or semicolon separated
    kwds = re.split(r'[,;]', k_str)
    for k in kwds:
        clean_k = k.strip().lower()
        if len(clean_k) > 2:
            all_keywords.append(clean_k)

kw_counts = Counter(all_keywords)
print("Top Keywords:", kw_counts.most_common(15))

conn.close()
