import sqlite3
import pandas as pd
import json
from collections import defaultdict

conn = sqlite3.connect('conferences.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- Testing Phase 2 Data Extraction ---")

# VIS_020: Velocity of Top Scholars (Рейтинг активности)
cursor.execute('''
    SELECT p.display_name, e.year
    FROM person p
    JOIN presentation_person pp ON p.person_id = pp.person_id
    JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    JOIN session s ON pr.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event e ON ed.event_id = e.event_id
    ORDER BY e.year ASC
''')
yearly_counts = defaultdict(lambda: defaultdict(int))
for row in cursor.fetchall():
    yearly_counts[row['year']][row['display_name']] += 1

# Identify top 5 all-time
all_time = defaultdict(int)
for y, counts in yearly_counts.items():
    for name, c in counts.items():
        all_time[name] += c
top5 = sorted(all_time.items(), key=lambda x: x[1], reverse=True)[:5]
top5_names = [x[0] for x in top5]
print(f"VIS_020: Top 5 scholars ready.")

# VIS_021: Institutional Gravity
cursor.execute('''
    SELECT affiliation_text_raw, COUNT(*) as c
    FROM presentation_person
    WHERE affiliation_text_raw IS NOT NULL AND affiliation_text_raw != ''
    GROUP BY affiliation_text_raw
    ORDER BY c DESC
    LIMIT 10
''')
insts = cursor.fetchall()
print(f"VIS_021: Top institutions: {len(insts)}")

# VIS_022: Geographic Diversity Index
cursor.execute('''
    SELECT e.year, o.city_ru
    FROM presentation_person pp
    JOIN organization o ON pp.organization_id = o.organization_id
    JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    JOIN session s ON pr.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event e ON ed.event_id = e.event_id
    WHERE o.city_ru IS NOT NULL
''')
cities_by_year = defaultdict(set)
for row in cursor.fetchall():
    cities_by_year[row['year']].add(row['city_ru'])
print(f"VIS_022: Diversity tracked for {len(cities_by_year)} years.")

# VIS_023: Thematic Bipartite Graph
try:
    df = pd.read_csv('analytics_output/expanded_classification_deepseek.csv')
    print("VIS_023: Loaded themes CSV.")
except:
    pass

conn.close()
