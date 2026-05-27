import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import sqlite3
import pandas as pd
import numpy as np
import scipy.stats as stats
import json
import os

def main():
    print("=== COLLABORATIVE CAPITAL & SCHOLAR RETENTION ANALYSIS ===")
    
    conn = sqlite3.connect('conferences.db')
    cursor = conn.cursor()
    
    # 1. Map each presentation to number of authors
    cursor.execute("""
        SELECT presentation_id, COUNT(person_id) as author_count
        FROM presentation_person
        GROUP BY presentation_id
    """)
    pres_author_counts = {r[0]: r[1] for r in cursor.fetchall()}
    
    # 2. Fetch all presentation participations with speaker, year, series, and raw affiliation
    cursor.execute("""
        SELECT 
            pp.person_id,
            p.display_name,
            pp.presentation_id,
            e.year,
            pp.affiliation_text_raw
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
    """)
    records = cursor.fetchall()
    conn.close()

    # Helper to extract city from raw affiliation
    def extract_city(text):
        if not text:
            return "Регионы / Ино"
        text_low = text.lower()
        if "санкт-петербург" in text_low or "спб" in text_low or "ленинград" in text_low:
            return "Санкт-Петербург"
        if "москва" in text_low or "мгу" in text_low or "ив ран" in text_low or "вшэ" in text_low:
            return "Москва"
        return "Регионы / Ино"

    # Analyze at scholar level
    scholar_talks = {}
    for pid, name, pres_id, year, affiliation in records:
        city = extract_city(affiliation)
        if pid not in scholar_talks:
            scholar_talks[pid] = {
                "name": name,
                "city": city, # primary city
                "years": set(),
                "talks": []
            }
        scholar_talks[pid]["years"].add(int(year))
        scholar_talks[pid]["talks"].append(pres_id)
        # Keep metropolitan city if seen
        if city in ("Москва", "Санкт-Петербург"):
            scholar_talks[pid]["city"] = city

    scholars_data = []
    for pid, s in scholar_talks.items():
        years = sorted(list(s["years"]))
        total_years = len(years)
        returned = total_years >= 2
        
        # Check if they have at least one co-authored paper
        has_collaboration = any(pres_author_counts.get(tid, 1) > 1 for tid in s["talks"])
        
        scholars_data.append({
            "person_id": pid,
            "name": s["name"],
            "city": s["city"],
            "total_talks": len(s["talks"]),
            "total_years": total_years,
            "returned": returned,
            "has_collaboration": has_collaboration
        })
        
    df = pd.DataFrame(scholars_data)
    print(f"Loaded {len(df)} scholars.")
    
    # 1. Co-authorship Advantage: Test if scholars who collaborate have a higher retention/return rate
    print("\n=== Co-authorship Advantage: Retention Rates ===")
    ct_collab = pd.crosstab(df['has_collaboration'], df['returned'])
    print(ct_collab)
    
    odds_ratio, p_collab = stats.fisher_exact(ct_collab)
    print(f"\nFisher's Exact Test (Collaboration vs. Return):")
    print(f"  Odds ratio = {odds_ratio:.4f}")
    print(f"  p-value = {p_collab:.6f}")
    
    retention_collab = df.groupby('has_collaboration')['returned'].mean() * 100
    print("\nRetention Rates by Collaboration Profile (%):")
    print(retention_collab.round(1))
    
    # 2. Metropolitan Concentration: Do metropolitan centers act as collaboration hubs?
    print("\n=== Metropolitan Concentration of Collaboration ===")
    ct_geo_collab = pd.crosstab(df['city'], df['has_collaboration'])
    print(ct_geo_collab)
    
    chi2_geo, p_geo, dof_geo, expected_geo = stats.chi2_contingency(ct_geo_collab)
    print(f"\nChi-Square Test (Geography vs. Collaboration Profile):")
    print(f"  Chi2 statistic = {chi2_geo:.4f}")
    print(f"  p-value = {p_geo:.6f}")
    
    collab_rate_geo = df.groupby('city')['has_collaboration'].mean() * 100
    print("\nCollaboration Rate by City Profile (%):")
    print(collab_rate_geo.round(1))

    # 3. Grouped analysis for visualizer
    print("\n=== Grouped Analysis for Bar Chart (Retention Rates segmented by Geography) ===")
    grouped = df.groupby(['city', 'has_collaboration'])['returned'].agg(['count', 'mean']).reset_index()
    grouped['mean'] = (grouped['mean'] * 100).round(1)
    print(grouped)

if __name__ == '__main__':
    main()
