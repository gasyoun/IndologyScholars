"""Compute inter-rater agreement for L1 theme and argument-level coding.

Joins the second coder's filled blind sheet (interrater_sample_blind.csv)
with the answer key (interrater_sample_key.csv) and reports, per coding axis:

  - percentage agreement
  - Cohen's kappa with a bootstrap 95% CI
  - Krippendorff's alpha (nominal, two raters)
  - Gwet's AC1 with a bootstrap 95% CI (reported because the corpus level
    distribution is heavily skewed, which makes raw kappa
    prevalence-sensitive; Gwet 2008)
  - per-category and per-stratum agreement and a disagreement table

Interpretation bands for kappa follow Landis & Koch (1977). Note that the
sample is deliberately stratified (census of level-3 items, oversampled
level-2), so pooled statistics describe the stratified sample, not the
corpus; per-stratum agreement is the corpus-relevant reading.

Usage:
  python tools/compute_interrater_agreement.py
  python tools/compute_interrater_agreement.py --blind path.csv --key path.csv
"""

import argparse
import csv
import random
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLIND = ROOT / "analytics_output" / "interrater_sample_blind.csv"
DEFAULT_KEY = ROOT / "analytics_output" / "interrater_sample_key.csv"

BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 20260612


def percentage_agreement(a, b):
    n = len(a)
    if n == 0:
        return 0.0
    return sum(1 for x, y in zip(a, b) if x == y) / n


def cohen_kappa(a, b):
    """Cohen's kappa for two parallel lists of nominal labels."""
    n = len(a)
    if n == 0:
        return 0.0
    cats = sorted(set(a) | set(b))
    p_o = percentage_agreement(a, b)
    ca, cb = Counter(a), Counter(b)
    p_e = sum(ca[c] * cb[c] for c in cats) / (n * n)
    if p_e == 1.0:
        # Degenerate resample (every item in one category): kappa is 0/0, i.e.
        # undefined. Returning 1.0 here would bias the bootstrap CI upward on a
        # skewed corpus; return NaN so bootstrap_ci drops the replicate instead.
        return float("nan")
    return (p_o - p_e) / (1 - p_e)


def gwet_ac1(a, b):
    """Gwet's first-order agreement coefficient (AC1) for two raters,
    nominal categories (Gwet 2008)."""
    n = len(a)
    if n == 0:
        return 0.0
    cats = sorted(set(a) | set(b))
    k = len(cats)
    if k == 1:
        return 1.0
    p_o = percentage_agreement(a, b)
    ca, cb = Counter(a), Counter(b)
    pi = {c: (ca[c] + cb[c]) / (2 * n) for c in cats}
    p_e = sum(p * (1 - p) for p in pi.values()) / (k - 1)
    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def krippendorff_alpha_nominal(a, b):
    """Krippendorff's alpha, nominal metric, two raters, no missing data."""
    n = len(a)
    if n == 0:
        return 0.0
    values = list(a) + list(b)
    counts = Counter(values)
    total = len(values)
    if len(counts) == 1:
        return 1.0
    d_o = sum(1 for x, y in zip(a, b) if x != y) * 2 / (n * 2)
    # expected disagreement from the pooled value distribution
    d_e = 1 - sum(c * (c - 1) for c in counts.values()) / (total * (total - 1))
    if d_e == 0:
        return 1.0
    return 1 - d_o / d_e


def bootstrap_ci(stat_fn, a, b, reps=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED):
    """Percentile bootstrap 95% CI resampling items."""
    n = len(a)
    if n == 0:
        return 0.0, 0.0
    rng = random.Random(seed)
    stats = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        val = stat_fn([a[i] for i in idx], [b[i] for i in idx])
        if val == val:  # drop undefined (NaN) replicates — NaN != NaN
            stats.append(val)
    if not stats:
        return float("nan"), float("nan")
    stats.sort()
    m = len(stats)
    return stats[int(0.025 * m)], stats[min(int(0.975 * m), m - 1)]


def landis_koch(kappa):
    if kappa < 0:
        return "less than chance"
    if kappa < 0.2:
        return "slight"
    if kappa < 0.4:
        return "fair"
    if kappa < 0.6:
        return "moderate"
    if kappa < 0.8:
        return "substantial"
    return "almost perfect"


def report_axis(name, existing, coder2, strata):
    n = len(existing)
    if n == 0:
        print(f"\n  {name}: no coded rows yet.")
        return
    p_a = percentage_agreement(existing, coder2)
    kappa = cohen_kappa(existing, coder2)
    k_lo, k_hi = bootstrap_ci(cohen_kappa, existing, coder2)
    alpha = krippendorff_alpha_nominal(existing, coder2)
    ac1 = gwet_ac1(existing, coder2)
    a_lo, a_hi = bootstrap_ci(gwet_ac1, existing, coder2)

    print(f"\n  {name} (n={n}):")
    print(f"    Percentage agreement:  {p_a:.1%}")
    print(f"    Cohen's kappa:         {kappa:.3f}  [95% CI {k_lo:.3f}, {k_hi:.3f}]  ({landis_koch(kappa)}, Landis & Koch 1977)")
    print(f"    Krippendorff's alpha:  {alpha:.3f}")
    print(f"    Gwet's AC1:            {ac1:.3f}  [95% CI {a_lo:.3f}, {a_hi:.3f}]")

    by_stratum = {}
    for e, c, s in zip(existing, coder2, strata):
        by_stratum.setdefault(s, ([], []))
        by_stratum[s][0].append(e)
        by_stratum[s][1].append(c)
    if len(by_stratum) > 1:
        print("    Per-stratum agreement (stratum = original argument level):")
        for s in sorted(by_stratum):
            ea, cb = by_stratum[s]
            print(f"      G{s}: {percentage_agreement(ea, cb):.1%}  (n={len(ea)})")

    disagreements = Counter(
        (e, c) for e, c in zip(existing, coder2) if e != c
    )
    if disagreements:
        print(f"    Disagreements ({sum(disagreements.values())}):")
        for (e, c), count in disagreements.most_common(12):
            print(f"      coder2={c}  vs  existing={e}  (x{count})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind", type=Path, default=DEFAULT_BLIND)
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    args = parser.parse_args()

    for path in (args.blind, args.key):
        if not path.exists():
            print(f"File not found: {path}")
            print("Run tools/build_interrater_sample.py first.")
            sys.exit(1)

    with args.blind.open(encoding="utf-8-sig", newline="") as f:
        blind = {r["presentation_id"]: r for r in csv.DictReader(f)}
    with args.key.open(encoding="utf-8-sig", newline="") as f:
        key = {r["presentation_id"]: r for r in csv.DictReader(f)}

    missing_key = sorted(set(blind) - set(key))
    if missing_key:
        print(f"WARNING: {len(missing_key)} blind rows have no key entry; they are skipped.")

    l1_e, l1_c, l1_s = [], [], []
    g_e, g_c, g_s = [], [], []
    uncoded = 0
    for pid, row in blind.items():
        k = key.get(pid)
        if not k:
            continue
        stratum = k.get("existing_g", "")
        c_l1 = (row.get("coder_2_l1") or "").strip()
        c_g = (row.get("coder_2_g") or "").strip().lstrip("GgLl")
        if not c_l1 and not c_g:
            uncoded += 1
            continue
        if c_l1:
            l1_e.append(k.get("existing_l1", ""))
            l1_c.append(c_l1)
            l1_s.append(stratum)
        if c_g:
            g_e.append(k.get("existing_g", ""))
            g_c.append(c_g)
            g_s.append(stratum)

    print("=" * 64)
    print("INTER-RATER AGREEMENT REPORT")
    print(f"Rows in blind sheet: {len(blind)}; fully uncoded: {uncoded}")
    print("Note: the sample is stratified (G3 census, G2 oversample); pooled")
    print("statistics describe the sample, per-stratum values the corpus.")
    print("=" * 64)

    report_axis("L1 theme classification", l1_e, l1_c, l1_s)
    report_axis("Argument level (G)", g_e, g_c, g_s)

    print()
    print("References: Landis & Koch (1977) Biometrics 33:159-174;")
    print("Krippendorff (2004) Content Analysis; Gwet (2008) Br J Math Stat Psychol 61:29-48.")


if __name__ == "__main__":
    main()
