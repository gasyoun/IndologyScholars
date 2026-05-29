import sqlite3
import pandas as pd

conn = sqlite3.connect('conferences.db')
cursor = conn.cursor()

print("--- Checking DB capability for 15 ideas ---")

# 1. Newcomer Influx
cursor.execute("SELECT MIN(e.year) FROM presentation p JOIN presentation_person pp ON p.presentation_id = pp.presentation_id JOIN session s ON p.session_id = s.session_id JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id JOIN event_day ed ON edv.event_day_id = ed.event_day_id JOIN event e ON ed.event_id = e.event_id GROUP BY pp.person_id")
first_years = [r[0] for r in cursor.fetchall()]
print(f"1. Total newcomers tracked: {len(first_years)}")

# 2. Generational Eras
cursor.execute("SELECT birth_year FROM person WHERE birth_year IS NOT NULL")
births = [r[0] for r in cursor.fetchall()]
print(f"2. People with birth years: {len(births)}")

# 12. Language Mix
cursor.execute("SELECT language, COUNT(*) FROM presentation GROUP BY language")
langs = cursor.fetchall()
print(f"12. Languages: {langs}")

# 15. Online Shift
cursor.execute("SELECT is_online, COUNT(*) FROM presentation GROUP BY is_online")
online = cursor.fetchall()
print(f"15. Online formats: {online}")

# 10. Chairpersons
cursor.execute("SELECT role, COUNT(*) FROM presentation_person GROUP BY role")
roles = cursor.fetchall()
print(f"10. Roles: {roles}")

conn.close()

try:
    df = pd.read_csv('analytics_output/expanded_classification_deepseek.csv')
    print(f"6. Period L2 columns exist? {'period_l2' in df.columns}")
    print(f"7. Gumilyov columns exist? {'gumilyov_level' in df.columns}")
    
    # 8. Title Length
    print(f"8. Titles present: {len(df['raw_title'].dropna())}")
except Exception as e:
    print("CSV read error:", e)
