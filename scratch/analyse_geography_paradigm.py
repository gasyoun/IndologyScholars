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
import csv
from collections import defaultdict

def main():
    print("=== GEOGRAPHY VS. RESEARCH PARADIGM ANALYSIS ===")
    
    # Connect to database
    conn = sqlite3.connect('conferences.db')
    cursor = conn.cursor()
    
    # Load themes from theme_codes_final_v2.csv
    theme_mapping = {}
    try:
        with open("analytics_output/theme_codes_final_v2.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                theme_mapping[row["presentation_id"]] = row["l1"]
    except FileNotFoundError:
        print("ERROR: theme_codes_final_v2.csv not found")
        return

    # Fetch presentations with speaker affiliation and event series
    cursor.execute("""
        SELECT 
            pr.presentation_id,
            e.year,
            es.series_name_ru,
            pp.affiliation_text_raw
        FROM presentation pr
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
    """)
    records = cursor.fetchall()
    conn.close()
    
    print(f"Loaded {len(records)} presentation participations.")

    # Helper to extract city from raw affiliation
    def extract_city(text):
        if not text:
            return None
        text_low = text.lower()
        if "санкт-петербург" in text_low or "спб" in text_low or "ленинград" in text_low:
            return "Санкт-Петербург"
        if "москва" in text_low or "мгу" in text_low or "ив ран" in text_low or "вшэ" in text_low:
            return "Москва"
        return None

    # Aggregate datasets
    data = []
    for pres_id, year, series, affiliation in records:
        city = extract_city(affiliation)
        theme = theme_mapping.get(pres_id)
        if city and theme and theme != "unspecified":
            data.append({
                "presentation_id": pres_id,
                "city": city,
                "theme": theme,
                "series": "Zograf" if "Зограф" in series else "Roerich"
            })
            
    df = pd.DataFrame(data)
    print(f"Classified {len(df)} participations with verified city (SPb/Moscow) and theme classification.")
    
    # 1. Contingency Table for City vs. Theme
    print("\n=== Contingency Table: Speaker City vs. Theme ===")
    contingency_city = pd.crosstab(df['city'], df['theme'])
    print(contingency_city)
    
    # Run Chi-Square test for Speaker City vs. Theme
    chi2_city, p_city, dof_city, expected_city = stats.chi2_contingency(contingency_city)
    print(f"\nChi-Square Test (City vs. Theme):")
    print(f"  Chi2 statistic = {chi2_city:.4f}")
    print(f"  p-value = {p_city:.8f}")
    print(f"  Degrees of freedom = {dof_city}")
    if p_city < 0.05:
        print("  ★ STATISTICALLY SIGNIFICANT SEGREGREGATION: St. Petersburg and Moscow represent distinct intellectual paradigms!")
    else:
        print("  ★ NO SIGNIFICANT SEGREGATION: Speakers from both cities share the same thematic distribution.")

    # 2. Contingency Table for Event Series vs. Theme
    print("\n=== Contingency Table: Event Series vs. Theme ===")
    contingency_series = pd.crosstab(df['series'], df['theme'])
    print(contingency_series)
    
    # Run Chi-Square test for Event Series vs. Theme
    chi2_series, p_series, dof_series, expected_series = stats.chi2_contingency(contingency_series)
    print(f"\nChi-Square Test (Event Series vs. Theme):")
    print(f"  Chi2 statistic = {chi2_series:.4f}")
    print(f"  p-value = {p_series:.8f}")
    print(f"  Degrees of freedom = {dof_series}")
    if p_series < 0.05:
        print("  ★ STATISTICALLY SIGNIFICANT SEGREGREGATION: Zograf and Roerich readings represent distinct intellectual paradigms!")
    else:
        print("  ★ NO SIGNIFICANT SEGREGATION: Both series share the same thematic distribution.")

    # 3. Specific Monopolies / Strengths
    print("\n=== Detailed Proportions (%) ===")
    proportions = contingency_city.div(contingency_city.sum(axis=1), axis=0) * 100
    print(proportions.round(1))
    
    # 4. Generate data matrix for the Chord diagram
    cities_list = ["Санкт-Петербург", "Москва"]
    themes_list = sorted(df['theme'].unique().tolist())
    all_labels = cities_list + themes_list
    
    # Create an empty square matrix for Chord diagram
    size = len(all_labels)
    matrix = np.zeros((size, size), dtype=int)
    
    # Fill flows: from City to Theme
    for i, city in enumerate(cities_list):
        for j, theme in enumerate(themes_list):
            count = contingency_city.loc[city, theme]
            matrix[i, len(cities_list) + j] = int(count)
            matrix[len(cities_list) + j, i] = int(count) # undirected for D3
            
    print("\nChord Matrix:")
    print(matrix)
    print("Labels:", all_labels)

if __name__ == '__main__':
    main()
