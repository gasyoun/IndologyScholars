import sqlite3
import json
from collections import defaultdict

DB_PATH = "conferences.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all presentations and people
cursor.execute("""
    SELECT p.presentation_id, p.session_id, pp.person_id, per.display_name
    FROM presentation p
    JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
    JOIN person per ON pp.person_id = per.person_id
""")
rows = cursor.fetchall()

# Count presentations per person to filter top scholars
person_counts = defaultdict(int)
for r in rows:
    person_counts[r[3]] += 1

# Filter: must have >= 3 presentations
top_people = {name for name, count in person_counts.items() if count >= 3}

# Build edges based on shared sessions (which implies shared thematic group)
session_people = defaultdict(set)
for pres_id, sess_id, pers_id, name in rows:
    if name in top_people:
        session_people[sess_id].add(name)

edges = defaultdict(int)
for sess_id, people in session_people.items():
    people = list(people)
    for i in range(len(people)):
        for j in range(i+1, len(people)):
            p1, p2 = sorted([people[i], people[j]])
            edges[(p1, p2)] += 1

print(f"Top people (>=3 presentations): {len(top_people)}")
print(f"Edges (shared sessions): {len(edges)}")
conn.close()
