"""Score the Renou-classifier precision gold sample from a filled decisions JSON.

Consumes the export produced by the voting sheet built by
`build_renou_precision_sheet.py` (schema: {sheet_id, generated, decided,
items:[{id, layer, stratum, risk, decision, note}]}) and reports precision per
stratum, per layer, and per risk tier, with Wilson 95% confidence intervals.

`unsure` votes are excluded from the denominator and reported separately; an
unfinished pass (any `decision: null`) is reported as coverage, never silently
treated as a rejection.

Because the sample is deliberately risk-stratified rather than uniform, the pooled
number is NOT an estimate of corpus precision. The corpus-level estimate is the
stratum-weighted figure, which reweights each stratum's observed precision by its
true share of the 1,706 conference / 9,110 archive matches. Both are printed; cite
the weighted one.

Usage:
    python tools/score_renou_precision.py review/indologyscholars-renou-precision_gold150_decisions.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFERENCE_MATCHES = REPO_ROOT / "analytics_output" / "renou_presentation_matches.csv"
ARCHIVE_MATCHES = REPO_ROOT / "Indology" / "data" / "processed" / "renou_message_matches.csv"


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def wilson(correct: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — correct at the small n this sample yields per stratum."""
    if total == 0:
        return (0.0, 0.0)
    phat = correct / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def population_counts() -> dict[str, dict[str, int]]:
    """True match count per stratum, per layer — the reweighting denominator."""
    counts: dict[str, dict[str, int]] = {"conference": defaultdict(int), "archive": defaultdict(int)}
    for layer, path in (("conference", CONFERENCE_MATCHES), ("archive", ARCHIVE_MATCHES)):
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                counts[layer][f"{row['renou_axis']}:{row['renou_code']}"] += 1
    return counts


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("decisions", type=Path, help="filled *_decisions.json from the voting sheet")
    args = parser.parse_args()

    payload = json.loads(args.decisions.read_text(encoding="utf-8"))
    items = payload["items"]

    voted = [i for i in items if i.get("decision")]
    unvoted = len(items) - len(voted)
    print(f"sheet    : {payload.get('sheet_id')}")
    print(f"generated: {payload.get('generated')}   decided: {payload.get('decided')}")
    print(f"coverage : {len(voted)}/{len(items)} voted" + (f"  ({unvoted} UNVOTED — partial pass)" if unvoted else ""))
    print()

    # (layer, stratum) -> [correct, incorrect, unsure]
    cell: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for item in voted:
        key = (item["layer"], item["stratum"])
        idx = {"correct": 0, "incorrect": 1, "unsure": 2}[item["decision"]]
        cell[key][idx] += 1

    pop = population_counts()

    for layer in ("conference", "archive"):
        keys = sorted(k for k in cell if k[0] == layer)
        if not keys:
            continue
        print(f"=== {layer} ===")
        print(f"{'stratum':<22}{'n':>4}{'ok':>4}{'bad':>5}{'?':>4}{'precision':>12}{'95% CI':>16}{'matches':>9}")
        num = den = 0.0
        for key in keys:
            ok, bad, unsure = cell[key]
            judged = ok + bad
            prec = ok / judged if judged else float("nan")
            lo, hi = wilson(ok, judged)
            n_pop = pop[layer].get(key[1], 0)
            if judged:
                num += prec * n_pop
                den += n_pop
            shown = f"{prec:.0%}" if judged else "—"
            ci = f"[{lo:.0%}, {hi:.0%}]" if judged else "—"
            print(f"{key[1]:<22}{ok+bad+unsure:>4}{ok:>4}{bad:>5}{unsure:>4}{shown:>12}{ci:>16}{n_pop:>9}")

        tot_ok = sum(cell[k][0] for k in keys)
        tot_bad = sum(cell[k][1] for k in keys)
        pooled = tot_ok / (tot_ok + tot_bad) if (tot_ok + tot_bad) else float("nan")
        weighted = num / den if den else float("nan")
        print(f"{'-'*72}")
        print(f"  pooled (sample, NOT corpus): {pooled:.1%}")
        print(f"  stratum-weighted (corpus estimate): {weighted:.1%}   <- cite this")
        print()

    print("=== by risk tier (both layers pooled) ===")
    by_risk: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for item in voted:
        if item["decision"] == "correct":
            by_risk[item["risk"]][0] += 1
        elif item["decision"] == "incorrect":
            by_risk[item["risk"]][1] += 1
    for tier in ("high", "med", "low"):
        ok, bad = by_risk[tier]
        if ok + bad:
            lo, hi = wilson(ok, ok + bad)
            print(f"  {tier:<5} n={ok+bad:<4} precision {ok/(ok+bad):.0%}  [{lo:.0%}, {hi:.0%}]")

    notes = [i for i in voted if i.get("note")]
    if notes:
        print(f"\n=== {len(notes)} annotated items ===")
        for item in notes:
            print(f"  [{item['decision']:<9}] {item['stratum']:<20} {item['note']}")

    return 0 if unvoted == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
