"""Compute inter-rater agreement for L1 theme classification and G-level.

Reads the filled-in interrater_sample.csv (with coder_2_l1 and coder_2_g columns
filled by the second-blind coder), computes Cohen's κ against the existing
classifications, and reports agreement statistics.

Usage:
  python tools/compute_interrater_agreement.py [--csv analytics_output/interrater_sample.csv]
"""

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "analytics_output" / "interrater_sample.csv"


def cohen_kappa(a, b):
    """Compute Cohen's κ from two parallel lists of categorical labels."""
    n = len(a)
    if n == 0:
        return 0.0, 0.0, 0

    cats = sorted(set(a) | set(b))
    cat_idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)

    # Observed agreement matrix
    obs = [[0] * k for _ in range(k)]
    for ai, bi in zip(a, b):
        obs[cat_idx[ai]][cat_idx[bi]] += 1

    p_o = sum(obs[i][i] for i in range(k)) / n

    row_sums = [sum(obs[i][j] for j in range(k)) for i in range(k)]
    col_sums = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    p_e = sum(row_sums[i] * col_sums[i] for i in range(k)) / (n * n)

    if p_e == 1.0:
        return 1.0, 1.0, n

    kappa = (p_o - p_e) / (1 - p_e)
    return round(kappa, 4), round(p_o, 4), n


def pairwise_agreement(a, b):
    """Simple percentage agreement."""
    n = len(a)
    if n == 0:
        return 0.0
    return round(sum(1 for x, y in zip(a, b) if x == y) / n, 4)


def main():
    csv_path = DEFAULT_CSV
    if len(sys.argv) > 1 and sys.argv[1] != "--csv":
        csv_path = Path(sys.argv[1])
    elif "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        csv_path = Path(sys.argv[idx + 1])

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    print(f"Loaded {len(rows)} rows from {csv_path}")

    l1_existing = []
    l1_coder2 = []
    g_existing = []
    g_coder2 = []
    uncoded_1 = 0
    uncoded_g = 0

    for r in rows:
        e_l1 = r.get("existing_l1", "").strip()
        c_l1 = r.get("coder_2_l1", "").strip()
        e_g = r.get("existing_g", "").strip()
        c_g = r.get("coder_2_g", "").strip()

        if c_l1:
            l1_existing.append(e_l1)
            l1_coder2.append(c_l1)
        else:
            uncoded_1 += 1

        if c_g:
            g_existing.append(e_g)
            g_coder2.append(c_g)
        else:
            uncoded_g += 1

    print(f"\n{'='*60}")
    print("INTER-RATER AGREEMENT REPORT")
    print(f"{'='*60}")

    if uncoded_1 == len(rows):
        print("\n  L1: No second-coder data yet. Fill 'coder_2_l1' column and re-run.")
    else:
        kappa, po, n = cohen_kappa(l1_existing, l1_coder2)
        agree = pairwise_agreement(l1_existing, l1_coder2)
        print(f"\n  L1 Theme Classification (n={n} coded, {uncoded_1} uncoded):")
        print(f"    Percentage agreement: {agree:.1%}")
        print(f"    Cohen's κ:           {kappa:.3f}")
        if kappa < 0:
            print(f"    Interpretation:       Less than chance")
        elif kappa < 0.2:
            print(f"    Interpretation:       Slight agreement")
        elif kappa < 0.4:
            print(f"    Interpretation:       Fair agreement")
        elif kappa < 0.6:
            print(f"    Interpretation:       Moderate agreement")
        elif kappa < 0.8:
            print(f"    Interpretation:       Substantial agreement")
        else:
            print(f"    Interpretation:       Almost perfect agreement")

        # Confusion pairs
        disagreements = [(l1_existing[i], l1_coder2[i]) for i in range(n) if l1_existing[i] != l1_coder2[i]]
        if disagreements:
            print(f"\n  Disagreements (n={len(disagreements)}):")
            from collections import Counter
            for (e, c), count in Counter(disagreements).most_common(10):
                print(f"    {c:35s} ← existing: {e}  (×{count})")

    if uncoded_g == len(rows):
        print("\n  G-level: No second-coder data yet. Fill 'coder_2_g' column and re-run.")
    else:
        kappa, po, n = cohen_kappa(g_existing, g_coder2)
        agree = pairwise_agreement(g_existing, g_coder2)
        print(f"\n  G-level Classification (n={n} coded, {uncoded_g} uncoded):")
        print(f"    Percentage agreement: {agree:.1%}")
        print(f"    Cohen's κ:           {kappa:.3f}")
        if kappa < 0.6:
            print(f"    Interpretation:       Below substantial — classifications not fully reproducible")
        elif kappa < 0.8:
            print(f"    Interpretation:       Substantial agreement")
        else:
            print(f"    Interpretation:       Almost perfect agreement")

        disagreements = [(g_existing[i], g_coder2[i]) for i in range(n) if g_existing[i] != g_coder2[i]]
        if disagreements:
            print(f"\n  Disagreements (n={len(disagreements)}):")
            from collections import Counter
            for (e, c), count in Counter(disagreements).most_common(10):
                print(f"    G{c} ← existing: G{e}  (×{count})")

    print(f"\n{'='*60}")
    print(f"To improve L1 agreement: review disagreements above for ambiguous titles.")
    print(f"For G-level: borderline G1/G2 cases often involve 'tradition' keywords in titles.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
