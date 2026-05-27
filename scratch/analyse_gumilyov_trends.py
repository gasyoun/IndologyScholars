import pandas as pd
import numpy as np
import scipy.stats as stats
import os
import sys

# Reconfigure stdout to force UTF-8 printing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=== GUMILYOV PASSIONARITY LIFECYCLE TREND ANALYSIS ===")
    
    csv_path = "analytics_output/gumilyov_scale.csv"
    if not os.path.exists(csv_path):
        print(f"Data file {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} classified presentations from {csv_path}.")

    # Group by year and gumilyov_level to aggregate counts
    pivot_df = df.groupby(['year', 'gumilyov_level']).size().unstack(fill_value=0)
    
    # Rename columns to match levels
    pivot_df.columns = ['Level_1_Microhistory', 'Level_2_Regional', 'Level_3_Global']
    pivot_df['Total'] = pivot_df.sum(axis=1)
    
    # Calculate percentages
    pivot_df['Pct_Level_1'] = (pivot_df['Level_1_Microhistory'] / pivot_df['Total']) * 100
    pivot_df['Pct_Level_2'] = (pivot_df['Level_2_Regional'] / pivot_df['Total']) * 100
    pivot_df['Pct_Level_3'] = (pivot_df['Level_3_Global'] / pivot_df['Total']) * 100
    
    # Save the aggregated trends
    trend_csv_path = "analytics_output/gumilyov_scale_trends.csv"
    pivot_df.to_csv(trend_csv_path)
    print(f"Saved aggregated yearly trends to {trend_csv_path}.")

    print("\n=== YEARLY DISTRIBUTION TRENDS (%) ===")
    print(pivot_df[['Total', 'Pct_Level_1', 'Pct_Level_2', 'Pct_Level_3']].round(1).to_string())

    # --- STATISTICAL ANALYSIS OF THE SPECIALIZATION HYPOTHESIS ---
    print("\n=== TESTING THE SPECIALIZATION HYPOTHESIS ===")
    # Run a Spearman rank correlation between the Year and the percentage of Level 1 (Microhistory) papers
    years = pivot_df.index.values
    pct_l1 = pivot_df['Pct_Level_1'].values
    pct_l3 = pivot_df['Pct_Level_3'].values
    
    rho_l1, p_val_l1 = stats.spearmanr(years, pct_l1)
    rho_l3, p_val_l3 = stats.spearmanr(years, pct_l3)
    
    print(f"Correlation between Year and Level 1 (Microhistory) %:")
    print(f"  Spearman's rho = {rho_l1:.4f} | p-value = {p_val_l1:.6f}")
    if p_val_l1 < 0.05:
        if rho_l1 > 0:
            print("  ★ SIGNIFICANT POSITIVE SHIFT: The field is statistically shifting towards hyperspecialized Microhistory over time.")
        else:
            print("  ★ SIGNIFICANT NEGATIVE SHIFT: The field is statistically moving away from Microhistory over time.")
    else:
        print("  ★ NO STATISTICALLY SIGNIFICANT DRIFT: The balance of Microhistory vs. general synthesis remains stable.")

    print(f"\nCorrelation between Year and Level 3 (Global Synthesis) %:")
    print(f"  Spearman's rho = {rho_l3:.4f} | p-value = {p_val_l3:.6f}")
    if p_val_l3 < 0.05:
        if rho_l3 > 0:
            print("  ★ SIGNIFICANT POSITIVE SHIFT: The field is statistically shifting towards global, civilizational theories over time.")
        else:
            print("  ★ SIGNIFICANT NEGATIVE SHIFT: The field is statistically moving away from grand synthesis over time.")
    else:
        print("  ★ NO STATISTICALLY SIGNIFICANT DRIFT: The level of global synthesis remains stable.")

    # 4. Generate beautiful HTML stacked area chart visualization
    years_list = list(years)
    l1_list = list(pivot_df['Pct_Level_1'].round(1))
    l2_list = list(pivot_df['Pct_Level_2'].round(1))
    l3_list = list(pivot_df['Pct_Level_3'].round(1))
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Visualizing the Passionarity Lifecycle of Indological Ideas</title>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #0f1412;
            --panel: #161f1c;
            --border: #283731;
            --text: #e2e9e5;
            --accent: #5db093;
        }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 2rem;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .container {{
            max-width: 960px;
            width: 100%;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 12px 36px rgba(0,0,0,0.3);
        }}
        h1 {{
            font-size: 1.5rem;
            color: #fff;
            margin-top: 0;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.5rem;
        }}
        p {{
            color: #8fa098;
            font-size: 0.92rem;
            line-height: 1.6;
        }}
        .stats-summary {{
            margin-top: 1.5rem;
            border-top: 1px solid var(--border);
            padding-top: 1rem;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.8rem;
            text-align: center;
        }}
        .stat-val {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--accent);
        }}
        .stat-label {{
            font-size: 0.78rem;
            color: #8fa098;
            margin-top: 0.2rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Academic Lifecycle & Gumilyov Scale Trend (2004–2026)</h1>
        <p>This interactive stacked area chart tracks the temporal distribution of research scopes across 22 years of Indological conferences. It visualizes how academic topics shift between <strong>Level 1: Microhistory/Philology</strong> (micro-level facts/single text analysis), <strong>Level 2: Regional/Tradition</strong> (meso-level doctrinal studies), and <strong>Level 3: Global/Civilizational</strong> (macro-level synthesis).</p>
        
        <div style="position: relative; height:400px; width:100%;">
            <canvas id="lifecycle-chart"></canvas>
        </div>
        
        <div class="stats-summary">
            <div class="stat-card">
                <div class="stat-val">{rho_l1:.4f}</div>
                <div class="stat-label">Spearman ρ (Microhistory Shift)</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{rho_l3:.4f}</div>
                <div class="stat-label">Spearman ρ (Global Shift)</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{"Significant Shift" if p_val_l1 < 0.05 or p_val_l3 < 0.05 else "Stable Balance"}</div>
                <div class="stat-label">Statistical Conclusion</div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('lifecycle-chart').getContext('2d');
        const chart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {years_list},
                datasets: [
                    {{
                        label: 'Level 1: Microhistory / Philology (%)',
                        data: {l1_list},
                        backgroundColor: 'rgba(93, 176, 147, 0.45)',
                        borderColor: '#5db093',
                        fill: true,
                        tension: 0.25
                    }},
                    {{
                        label: 'Level 2: Regional Studies / Traditions (%)',
                        data: {l2_list},
                        backgroundColor: 'rgba(197, 154, 86, 0.45)',
                        borderColor: '#c59a56',
                        fill: true,
                        tension: 0.25
                    }},
                    {{
                        label: 'Level 3: Global Synthesis (%)',
                        data: {l3_list},
                        backgroundColor: 'rgba(239, 68, 68, 0.35)',
                        borderColor: '#f87171',
                        fill: true,
                        tension: 0.25
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'top',
                        labels: {{
                            color: '#e2e9e5'
                        }}
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false
                    }}
                }},
                scales: {{
                    x: {{
                        stacked: true,
                        grid: {{ color: 'rgba(40, 55, 49, 0.3)' }},
                        ticks: {{ color: '#8fa098' }}
                    }},
                    y: {{
                        stacked: true,
                        max: 100,
                        grid: {{ color: 'rgba(40, 55, 49, 0.3)' }},
                        ticks: {{
                            color: '#8fa098',
                            callback: function(value) {{ return value + '%'; }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    html_path = "scratch/gumilyov_scale_trends.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\nSuccessfully generated interactive stacked trend visualization at: {html_path}")

if __name__ == '__main__':
    main()
