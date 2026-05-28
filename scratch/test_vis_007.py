import sqlite3
import json
from collections import defaultdict

DB_PATH = "conferences.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get top 50 scholars
cursor.execute("""
    SELECT per.display_name, COUNT(p.presentation_id) as total
    FROM presentation p
    JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
    JOIN person per ON pp.person_id = per.person_id
    GROUP BY per.person_id
    ORDER BY total DESC
    LIMIT 50
""")
top_scholars_list = [row[0] for row in cursor.fetchall()]
top_scholars_set = set(top_scholars_list)

# Find shared sessions
cursor.execute("""
    SELECT p.session_id, per.display_name
    FROM presentation p
    JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
    JOIN person per ON pp.person_id = per.person_id
""")
session_people = defaultdict(set)
for sess_id, name in cursor.fetchall():
    if name in top_scholars_set:
        session_people[sess_id].add(name)

edges = defaultdict(int)
for sess_id, people in session_people.items():
    people_list = list(people)
    for i in range(len(people_list)):
        for j in range(i+1, len(people_list)):
            p1, p2 = sorted([people_list[i], people_list[j]])
            edges[(p1, p2)] += 1

# Format data
nodes = [{"id": name, "group": 1} for name in top_scholars_list]
links = [{"source": p1, "target": p2, "value": count} for (p1, p2), count in edges.items()]

print(f"Nodes: {len(nodes)}")
print(f"Links: {len(links)}")
conn.close()
