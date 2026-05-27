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
import csv
from collections import defaultdict

def main():
    print("=== GENERATIONAL COHORT SUCCESSION & THEME EVOLUTION ===")
    
    conn = sqlite3.connect('conferences.db')
    cursor = conn.cursor()
    
    # 1. Fetch scholar birth years
    cursor.execute("SELECT person_id, display_name, birth_year FROM person WHERE birth_year IS NOT NULL")
    scholar_births = {r[0]: (r[1], int(r[2])) for r in cursor.fetchall()}
    
    # 2. Load period classifications from expanded_classification_deepseek.csv
    period_mapping = {}
    try:
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                period_mapping[row["presentation_id"]] = row["period_l2"]
    except FileNotFoundError:
        print("ERROR: expanded_classification_deepseek.csv not found")
        return

    # 3. Load scale levels from gumilyov_scale.csv
    scale_mapping = {}
    try:
        with open("analytics_output/gumilyov_scale.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                scale_mapping[row["presentation_id"]] = int(row["gumilyov_level"])
    except FileNotFoundError:
        pass

    # 4. Fetch presentation-person connections
    cursor.execute("SELECT person_id, presentation_id FROM presentation_person")
    participations = cursor.fetchall()
    conn.close()

    # Define cohorts canonical boundaries
    def get_cohort(year):
        if year < 1940:
            return "Предшественники (до 1940)"
        elif year < 1950:
            return "Когорта Василькова (1940-е)"
        elif year < 1960:
            return "Поколение 1950-х"
        elif year < 1970:
            return "Поколение 1960-х"
        elif year < 1980:
            return "Поколение 1970-х"
        elif year < 1990:
            return "Поколение 1980-х"
        elif year < 2000:
            return "Поколение 1990-х"
        else:
            return "Когорта Толчельникова (2000-е)"

    data = []
    for pid, pres_id in participations:
        if pid in scholar_births:
            name, birth = scholar_births[pid]
            period = period_mapping.get(pres_id, "unspecified")
            level = scale_mapping.get(pres_id)
            cohort = get_cohort(birth)
            
            data.append({
                "person_id": pid,
                "name": name,
                "birth_year": birth,
                "cohort": cohort,
                "presentation_id": pres_id,
                "period": period,
                "gumilyov_level": level
            })

    df = pd.DataFrame(data)
    print(f"Loaded {len(df)} presentation participations with birth years.")

    # 1. The Modernity Shift: Do younger cohorts systematically favor Colonial/Contemporary/Modern over Classical/Vedic?
    print("\n=== 1. The Modernity Shift ===")
    df_valid_periods = df[df['period'].isin(['vedic', 'classical', 'medieval', 'colonial', 'modern', 'contemporary'])]
    
    # Classify periods into Classical/Vedic vs. Modern/Colonial/Contemp
    def classify_period_group(p):
        if p in ('vedic', 'classical', 'medieval'):
            return "Classical & Vedic"
        else:
            return "Modern & Contemporary"

    df_valid_periods['period_group'] = df_valid_periods['period'].apply(classify_period_group)
    
    # Group by cohort and period group
    ct_modernity = pd.crosstab(df_valid_periods['cohort'], df_valid_periods['period_group'])
    print(ct_modernity)
    
    chi2_mod, p_mod, dof_mod, expected_mod = stats.chi2_contingency(ct_modernity)
    print(f"\nChi-Square Test (Cohort vs. Period Group):")
    print(f"  Chi2 statistic = {chi2_mod:.4f}")
    print(f"  p-value = {p_mod:.8f}")
    
    proportions_mod = ct_modernity.div(ct_modernity.sum(axis=1), axis=0) * 100
    print("\nClassical/Vedic vs Modern/Contemporary Proportions by Cohort (%):")
    print(proportions_mod.round(1))

    # 2. The Synthesis Shift: Are younger scholars more inclined to write Level 1 (microhistory), whereas senior scholars dominate Level 3?
    print("\n=== 2. The Synthesis Shift ===")
    df_valid_levels = df[df['gumilyov_level'].isin([1, 2, 3])]
    
    ct_levels = pd.crosstab(df_valid_levels['cohort'], df_valid_levels['gumilyov_level'])
    print(ct_levels)
    
    chi2_level, p_level, dof_level, expected_level = stats.chi2_contingency(ct_levels)
    print(f"\nChi-Square Test (Cohort vs. Gumilyov Level):")
    print(f"  Chi2 statistic = {chi2_level:.4f}")
    print(f"  p-value = {p_level:.8f}")
    
    proportions_level = ct_levels.div(ct_levels.sum(axis=1), axis=0) * 100
    print("\nGumilyov Level Proportions by Cohort (%):")
    print(proportions_level.round(1))

if __name__ == '__main__':
    main()
