"""k-fold self-consistency re-classification of all 1362 talks.

Unlimited DeepSeek budget buys repetition: classify every talk k times at a
non-zero temperature, majority-vote each field, and surface calibrated
agreement so only genuinely ambiguous talks reach a human. The taxonomy,
prompt, and validation are REUSED from the existing publication classifier
(article/work_expanded_classification_deepseek.py) — this script only adds the
repeat-and-vote layer; it does not redefine the coding scheme.

Run on a clean-egress host (smoke test first):
    python tools/openmodel_client.py --selftest
    python tools/run_kfold_classification.py --k 5 --temp 0.5
    python tools/run_kfold_classification.py --limit 40        # cheap trial

Outputs (analytics_output/):
    classification_kfold.csv               consensus + per-field agreement
    classification_kfold_disagreements.csv human-review queue (splits only)
    classification_kfold_runs.json         resumable raw-run checkpoint
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "article"))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import work_expanded_classification_deepseek as wc  # noqa: E402  (prompts + normalizer)
from openmodel_client import chat_json, GatewayError  # noqa: E402

INPUT = ROOT / "scratch" / "classification_input.csv"
ANALYTICS = ROOT / "analytics_output"
RUNS_CACHE = ANALYTICS / "classification_kfold_runs.json"
OUT = ANALYTICS / "classification_kfold.csv"
QUEUE = ANALYTICS / "classification_kfold_disagreements.csv"

VOTE_FIELDS = ["theme_l1", "period_l2", "material_l3", "character_l4", "gumilyov_level"]


def load_input(limit: int) -> list[dict]:
    rows = []
    with open(INPUT, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"presentation_id": r["presentation_id"], "year": r["year"],
                         "series": r["series"], "raw_title": r["raw_title"],
                         "title": r["title"], "prior_gumilyov_level": r["prior_gumilyov_level"],
                         "prior_theme_l1": r["prior_theme_l1"]})
    return rows[:limit] if limit else rows


def load_cache() -> dict:
    if RUNS_CACHE.exists():
        return json.loads(RUNS_CACHE.read_text(encoding="utf-8"))
    return {"runs": {}, "done": []}


def save_cache(cache: dict) -> None:
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    RUNS_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def collect_runs(rows: list[dict], k: int, temp: int, restart: bool) -> dict:
    cache = {"runs": {}, "done": []} if restart else load_cache()
    runs: dict = cache["runs"]
    done = set(cache["done"])
    by_id = {r["presentation_id"]: r for r in rows}
    bs = wc.BATCH_SIZE
    total = len(rows)
    for run in range(k):
        for start in range(0, total, bs):
            key = f"r{run}_b{start}"
            if key in done:
                continue
            batch = rows[start:start + bs]
            messages = [{"role": "system", "content": wc.SYSTEM_PROMPT},
                        {"role": "user", "content": wc.user_prompt(batch)}]
            try:
                parsed = chat_json(messages, temperature=temp, max_tokens=6000)
            except GatewayError as exc:
                raise SystemExit(f"Gateway rejected request ({exc}). Check endpoint/model "
                                 "on this host with: python tools/openmodel_client.py --selftest")
            results = parsed.get("results", []) if isinstance(parsed, dict) else []
            answer = {str(x.get("id")): x for x in results if isinstance(x, dict)}
            for pres in batch:
                pid = pres["presentation_id"]
                raw = answer.get(str(pid))
                if not raw:
                    continue
                norm = wc.normalize_result(raw, by_id[pid])
                if norm["valid"] != "yes":
                    continue
                rec = {fld: norm[fld] for fld in VOTE_FIELDS}
                rec["meso_codes"] = norm["meso_codes"]
                rec["confidence"] = norm["confidence"]
                runs.setdefault(pid, []).append(rec)
            done.add(key)
            cache["done"] = sorted(done)
            save_cache(cache)
            print(f"run {run+1}/{k} batch @{start}: cached {len(runs)} talks", flush=True)
    return runs


def vote(values: list) -> tuple[str, float]:
    """Modal value and its agreement share."""
    c = Counter(str(v) for v in values)
    val, n = c.most_common(1)[0]
    return val, round(n / len(values), 3)


def aggregate(rows: list[dict], runs: dict) -> tuple[list[dict], list[dict]]:
    consensus, queue = [], []
    overrides = wc.CLASSIFICATION_OVERRIDES
    for r in rows:
        pid = r["presentation_id"]
        rr = runs.get(pid, [])
        if not rr:
            continue
        row = {"presentation_id": pid, "year": r["year"], "series": r["series"],
               "title": r["title"], "n_runs": len(rr),
               "is_override": "yes" if pid in overrides else "no"}
        agreements = []
        for fld in VOTE_FIELDS:
            val, agr = vote([x[fld] for x in rr])
            row[fld] = val
            row[f"{fld}_agreement"] = agr
            agreements.append(agr)
            # aggressive publish, flag uncertainty inline
            row[f"{fld}_marked"] = val if agr == 1.0 else f"{val}(?)"
        # meso codes appearing in a majority of runs
        meso_counter: Counter = Counter()
        for x in rr:
            for code in str(x["meso_codes"]).split("|"):
                if code:
                    meso_counter[code] += 1
        thresh = len(rr) / 2
        row["meso_codes"] = "|".join(c for c, n in meso_counter.most_common(3) if n >= thresh)
        row["mean_confidence"] = round(sum(x["confidence"] for x in rr) / len(rr), 3)
        row["overall_agreement"] = round(sum(agreements) / len(agreements), 3)
        row["changed_vs_prior"] = ("yes" if str(row["gumilyov_level"]) !=
                                    str(r["prior_gumilyov_level"]) else "no")
        gl_agr = row["gumilyov_level_agreement"]
        th_agr = row["theme_l1_agreement"]
        row["flagged_for_review"] = ("yes" if (gl_agr < 1.0 or th_agr < 0.6
                                               or row["overall_agreement"] < 0.7) else "no")
        consensus.append(row)
        if row["flagged_for_review"] == "yes" and row["is_override"] == "no":
            queue.append(row)
    return consensus, queue


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5, help="runs per talk (self-consistency)")
    ap.add_argument("--temp", type=float, default=0.5, help="sampling temperature for diversity")
    ap.add_argument("--limit", type=int, default=0, help="first N talks only (trial)")
    ap.add_argument("--restart", action="store_true", help="ignore the run checkpoint")
    args = ap.parse_args()

    rows = load_input(args.limit)
    print(f"talks: {len(rows)} | k={args.k} | temp={args.temp}")
    runs = collect_runs(rows, args.k, args.temp, args.restart)
    consensus, queue = aggregate(rows, runs)

    base_fields = ["presentation_id", "year", "series", "title", "n_runs"]
    field_cols = []
    for fld in VOTE_FIELDS:
        field_cols += [fld, f"{fld}_marked", f"{fld}_agreement"]
    tail = ["meso_codes", "mean_confidence", "overall_agreement", "changed_vs_prior",
            "is_override", "flagged_for_review"]
    write_csv(OUT, consensus, base_fields + field_cols + tail)
    write_csv(QUEUE, queue, base_fields + field_cols + tail)

    flagged = sum(1 for r in consensus if r["flagged_for_review"] == "yes")
    changed = sum(1 for r in consensus if r["changed_vs_prior"] == "yes")
    print(f"\n=== K-FOLD SUMMARY ===")
    print(f"talks aggregated   : {len(consensus)}")
    print(f"flagged for review : {flagged}  -> {QUEUE.name}")
    print(f"level changed vs prior: {changed}")
    if consensus:
        unan = sum(1 for r in consensus if r["gumilyov_level_agreement"] == 1.0)
        print(f"unanimous on L-scale: {unan}/{len(consensus)} "
              f"({unan/len(consensus)*100:.0f}%)")
    print(f"consensus -> {OUT}")


if __name__ == "__main__":
    main()
