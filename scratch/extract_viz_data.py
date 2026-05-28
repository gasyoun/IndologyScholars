import sqlite3
import csv
import json
from collections import defaultdict

DB_PATH = "conferences.db"
CSV_PATH = "analytics_output/expanded_classification_deepseek.csv"

# 1. Heatmap Data
# Group by year, series, and count videos
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
    SELECT e.year, es.series_name_en, COUNT(m.media_id)
    FROM presentation p
    JOIN session s ON p.session_id = s.session_id
    JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
    JOIN event_day ed ON edv.event_day_id = ed.event_day_id
    JOIN event e ON ed.event_id = e.event_id
    JOIN event_series es ON e.event_series_id = es.event_series_id
    JOIN media m ON m.attached_to_id = p.presentation_id AND m.attached_to_type = 'presentation'
    WHERE m.media_type = 'video' OR m.media_type = 'youtube'
    GROUP BY e.year, es.series_name_en
""")
video_counts = cursor.fetchall()

heatmap_data = []
for year, series, count in video_counts:
    group = "zograf" if "zograf" in series.lower() else "roerich"
    heatmap_data.append({"y": year, "g": group, "c": count})

# Include all years where events happened
cursor.execute("SELECT DISTINCT year FROM event ORDER BY year")
all_years = [r[0] for r in cursor.fetchall()]

# Print heatmap
print("HEATMAP_DATA:")
print(json.dumps({"years": all_years, "data": heatmap_data}, indent=2, ensure_ascii=False))

# 2. Alluvial Data
# period_l2 -> theme_l1 -> meso_codes
period_theme_links = defaultdict(int)
theme_meso_links = defaultdict(int)

try:
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            period = row.get("period_l2")
            theme = row.get("theme_l1")
            meso = row.get("meso_codes") or row.get("proposed_meso")
            
            if not period or period == "unspecified": period = "Unknown"
            if not theme or theme == "unspecified": theme = "Unknown"
            if not meso or meso == "unspecified": meso = "Other"
            
            # Simple clean up
            meso = meso.split(',')[0].strip() # Take first meso code
            
            period_theme_links[(period, theme)] += 1
            theme_meso_links[(theme, meso)] += 1
except Exception as e:
    print("Error reading CSV:", e)

# Filter out low frequency links to keep the diagram clean
alluvial_data = {
    "nodes": [],
    "links": []
}

node_indices = {}
def get_node(name, group):
    key = (name, group)
    if key not in node_indices:
        node_indices[key] = len(alluvial_data["nodes"])
        alluvial_data["nodes"].append({"name": name, "group": group})
    return node_indices[key]

# We need a robust threshold, e.g. >= 5 connections
for (p, t), v in period_theme_links.items():
    if v >= 2:
        source = get_node(p, "period")
        target = get_node(t, "theme")
        alluvial_data["links"].append({"source": source, "target": target, "value": v})

for (t, m), v in theme_meso_links.items():
    if v >= 5: # higher threshold for meso to prevent clutter
        source = get_node(t, "theme")
        target = get_node(m, "meso")
        alluvial_data["links"].append({"source": source, "target": target, "value": v})

print("\nALLUVIAL_DATA:")
print(json.dumps(alluvial_data, indent=2, ensure_ascii=False))
