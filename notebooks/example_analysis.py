"""Example analysis — loading IndologyScholars data from the published dataset.

Prerequisites:
    pip install pandas matplotlib numpy scipy

This notebook demonstrates:
    1. Loading site_data from the JavaScript payload
    2. Basic descriptive statistics
    3. Gender distribution over time
    4. Top scholars by participation
    5. Theme distribution across venues
    6. Reproducing the overlap null model (41 vs 128.4)

To cite this dataset:
    Gasūns, M. (2026). IndologyScholars: Archive of Talks in Russian Indology
    [Data set]. Zenodo. https://doi.org/10.5281/zenodo.21360652
"""

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent if "__file__" in dir() else Path(".")
SITE_DATA = ROOT / "site_data.json"

print("Loading site_data.json...")
text = SITE_DATA.read_text(encoding="utf-8")
prefix = "const CONFERENCE_DATA = "
if text.startswith(prefix):
    text = text[len(prefix):]
if text.endswith(";"):
    text = text[:-1]
data = json.loads(text)

scholars = data["scholars"]
timeline = data["timeline"]
summary = data["summary"]

print(f"  Scholars: {len(scholars)}")
print(f"  Events: {summary.get('total_events', '?')}")
print(f"  Unique talks: {summary.get('unique_talks', len(set(t['presentation_id'] for s in scholars for t in s.get('talks',[]))))}")
print(f"  Author participations: {summary.get('author_participations', '?')}")

# ---------------------------------------------------------------------------
# 2. Basic descriptive statistics
# ---------------------------------------------------------------------------

def describe():
    talks_per_scholar = sorted([s["total_talks"] for s in scholars], reverse=True)

    women = [s for s in scholars if s.get("gender") == "F"]
    men = [s for s in scholars if s.get("gender") == "M"]
    unknown = [s for s in scholars if s.get("gender") not in ("F", "M")]

    zograf = [s for s in scholars if s.get("zograf_talks", 0) > 0]
    roerich = [s for s in scholars if s.get("roerich_talks", 0) > 0]
    both = [s for s in scholars if s["zograf_talks"] > 0 and s["roerich_talks"] > 0]

    print("\n--- Descriptive Statistics ---")
    print(f"  Scholars: {len(scholars)}")
    print(f"    Women: {len(women)} ({100*len(women)/len(scholars):.1f}%)")
    print(f"    Men:   {len(men)} ({100*len(men)/len(scholars):.1f}%)")
    print(f"    Unknown: {len(unknown)}")
    print(f"  Zograf-only:   {len(zograf) - len(both)}")
    print(f"  Roerich-only:  {len(roerich) - len(both)}")
    print(f"  Both venues:   {len(both)} ({100*len(both)/len(scholars):.1f}%)")
    print(f"  Median talks:  {talks_per_scholar[len(talks_per_scholar)//2]}")
    print(f"  Top 5:")

    for s in sorted(scholars, key=lambda x: -x["total_talks"])[:5]:
        print(f"    {s['full_name_ru'] or s['name']}: {s['total_talks']} talks")

describe()

# ---------------------------------------------------------------------------
# 3. Gender distribution over time
# ---------------------------------------------------------------------------

def gender_timeline():
    print("\n--- Gender Distribution by Year ---")
    year_counts = {}
    for s in scholars:
        g = s.get("gender")
        for t in s.get("talks", []):
            y = t.get("year")
            if y and g in ("F", "M"):
                year_counts.setdefault(y, {"F": 0, "M": 0})
                year_counts[y][g] += 1

    print(f"  {'Year':<6} {'Total':<7} {'Women':<7} {'Men':<7} {'% Women':<8}")
    for y in sorted(year_counts):
        w, m = year_counts[y]["F"], year_counts[y]["M"]
        t = w + m
        print(f"  {y:<6} {t:<7} {w:<7} {m:<7} {100*w/t:.1f}%")

gender_timeline()

# ---------------------------------------------------------------------------
# 4. Theme distribution
# ---------------------------------------------------------------------------

def theme_stats():
    print("\n--- Theme Distribution by Venue ---")
    themes = {"Zograf": {}, "Roerich": {}}
    for s in scholars:
        for t in s.get("talks", []):
            series = "Zograf" if "Zograf" in t.get("series", "") else "Roerich"
            code = t.get("theme", {}).get("code", "unspecified")
            themes[series][code] = themes[series].get(code, 0) + 1

    all_codes = sorted(set(list(themes["Zograf"]) + list(themes["Roerich"])))
    print(f"  {'Code':<35} {'Zograf':<8} {'Roerich':<8}")
    for code in all_codes:
        z = themes["Zograf"].get(code, 0)
        r = themes["Roerich"].get(code, 0)
        print(f"  {code:<35} {z:<8} {r:<8}")

theme_stats()

# ---------------------------------------------------------------------------
# 5. Null model: overlap expected vs observed
# ---------------------------------------------------------------------------

def null_model_overlap(n_permutations=10000, seed=20260603):
    """Permutation test: how many scholars overlap between venues by chance?"""
    import numpy as np

    rng = np.random.default_rng(seed)

    zograf_count = sum(s["zograf_talks"] for s in scholars)
    roerich_count = sum(s["roerich_talks"] for s in scholars)
    n = len(scholars)

    observed = sum(1 for s in scholars if s["zograf_talks"] > 0 and s["roerich_talks"] > 0)

    # Build slot-per-participation array
    slots = []
    for i, s in enumerate(scholars):
        slots.extend([i] * (s["zograf_talks"] + s["roerich_talks"]))
    slots = np.array(slots)
    base_labels = np.array([0] * zograf_count + [1] * roerich_count)

    null_overlap = np.empty(n_permutations)
    for b in range(n_permutations):
        lab = rng.permutation(base_labels)
        z = np.bincount(slots, weights=(lab == 0), minlength=n)
        r = np.bincount(slots, weights=(lab == 1), minlength=n)
        null_overlap[b] = np.sum((z > 0) & (r > 0))

    mu, sd = null_overlap.mean(), null_overlap.std(ddof=1)
    z_score = (observed - mu) / sd if sd else 0.0
    p_val = (np.sum(null_overlap <= observed) + 1) / (n_permutations + 1)

    print(f"\n--- Null Model: Venue Overlap ---")
    print(f"  Observed overlap:  {observed}")
    print(f"  Expected (null):   {mu:.1f} ± {sd:.1f}")
    print(f"  Z-score:           {z_score:.2f}")
    print(f"  One-sided p:       {p_val:.4g}")
    print(f"  Interpretation:    Overlap is {abs(z_score):.0f} sigma below expectation")

null_model_overlap(10000)

# ---------------------------------------------------------------------------
# 6. Save summary
# ---------------------------------------------------------------------------
print("\n--- Analysis complete ---")
print("To publish findings, cite:")
print("  Gasūns, M. (2026). IndologyScholars: Archive of Talks in Russian Indology.")
print("  Zenodo. https://doi.org/10.5281/zenodo.21360652")
print("  Data dictionary: https://gasyoun.github.io/IndologyScholars/data_dictionary_en.html")
