import sqlite3
import pandas as pd
import json
from collections import defaultdict

conn = sqlite3.connect('conferences.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- Testing Phase 1 Data Extraction ---")

# VIS_016: Generational Eras (Смена поколений)
cursor.execute('''
    SELECT p.birth_year, e.year, es.series_name_en 
    FROM person p
    JOIN presentation_person pp ON p.person_id = pp.person_id
    JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    JOIN session s ON pr.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event e ON ed.event_id = e.event_id
    JOIN event_series es ON e.event_series_id = es.event_series_id
    WHERE p.birth_year IS NOT NULL
''')
eras = defaultdict(lambda: defaultdict(int))
for row in cursor.fetchall():
    decade = (row['birth_year'] // 10) * 10
    year = row['year']
    eras[year][decade] += 1
print(f"VIS_016: Found {len(eras)} years of generational data. Decades: {set([k for sub in eras.values() for k in sub.keys()])}")

# VIS_018: Title Length Dynamics (Длина названий)
cursor.execute('''
    SELECT pr.title, e.year 
    FROM presentation pr
    JOIN session s ON pr.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event e ON ed.event_id = e.event_id
''')
lengths = defaultdict(list)
for row in cursor.fetchall():
    if row['title']:
        words = len(row['title'].split())
        lengths[row['year']].append(words)
print(f"VIS_018: Found {len(lengths)} years of title length data.")

# VIS_020: Top Presenters Velocity (Скорость публикации топ-авторов)
cursor.execute('''
    SELECT pp.person_id, p.display_name, e.year
    FROM person p
    JOIN presentation_person pp ON p.person_id = pp.person_id
    JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    JOIN session s ON pr.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event e ON ed.event_id = e.event_id
''')
velocity = defaultdict(list)
for row in cursor.fetchall():
    velocity[row['display_name']].append(row['year'])
    
top_scholars = sorted(velocity.items(), key=lambda x: len(x[1]), reverse=True)[:10]
print(f"VIS_020: Top 10 scholars: {[s[0] for s in top_scholars]}")

conn.close()

# VIS_017: Theme by Age
try:
    df = pd.read_csv('analytics_output/expanded_classification_deepseek.csv')
    print(f"VIS_017: Loaded DeepSeek themes, cols: {df.columns.tolist()[:5]}")
except Exception as e:
    print(f"VIS_017 Error: {e}")

