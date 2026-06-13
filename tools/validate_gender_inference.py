"""Manual validation protocol for name-based gender inference.

Stage 1 (no verified data yet): draws a deterministic random sample of
scholars, writes analytics_output/gender_validation_sample.csv with the
inferred gender and a blank `verified_gender` column. A human fills in
`verified_gender` (F / M / X) from independent evidence (patronymic in the
source programme, institutional bio, photograph caption, self-description);
`X` marks cases where no reliable determination is possible.

Stage 2 (verified column filled): reports accuracy of the inference against
the verified labels with a Wilson 95% confidence interval, plus the error
table. The resulting error rate is the figure cited on findings/gender.html
and in the data paper.

Usage:
  python tools/validate_gender_inference.py            # build or score sample
  python tools/validate_gender_inference.py --rebuild  # force a fresh sample
"""

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from publication_helpers import classify_gender, wilson_interval  # noqa: E402

SITE_DATA = ROOT / "site_data.json"
OUT_CSV = ROOT / "analytics_output" / "gender_validation_sample.csv"
SEED = 20260612
SAMPLE_SIZE = 60

FIELDS = [
    "person_id",
    "full_name_ru",
    "inferred_gender",
    "verified_gender",
    "evidence_url",
    "note",
]


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def build_sample():
    scholars = load_site_data().get("scholars", [])
    random.seed(SEED)
    sample = random.sample(scholars, min(SAMPLE_SIZE, len(scholars)))
    rows = []
    for s in sorted(sample, key=lambda x: str(x.get("id"))):
        name = s.get("full_name_ru") or s.get("name") or ""
        rows.append({
            "person_id": s.get("id"),
            "full_name_ru": name,
            "inferred_gender": classify_gender(name) or "U",
            "verified_gender": "",
            "evidence_url": "",
            "note": "",
        })
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote blank validation sample ({len(rows)} scholars, seed {SEED}) to {OUT_CSV}")
    print("Fill `verified_gender` (F/M/X) with an evidence_url per row, then re-run.")


def score_sample(rows):
    verified = [r for r in rows if r.get("verified_gender", "").strip()]
    if not verified:
        return False
    decidable = [r for r in verified if r["verified_gender"].strip().upper() in ("F", "M")]
    inferred_known = [r for r in decidable if r["inferred_gender"] in ("F", "M")]
    correct = sum(
        1 for r in inferred_known
        if r["inferred_gender"] == r["verified_gender"].strip().upper()
    )
    n = len(inferred_known)
    coverage = len(inferred_known) / len(decidable) if decidable else 0.0

    print("GENDER INFERENCE VALIDATION REPORT")
    print(f"  Sample rows verified: {len(verified)} / {len(rows)}")
    print(f"  Human-undecidable (X): {len(verified) - len(decidable)}")
    print(f"  Inference coverage among decidable: {coverage:.1%}")
    if n:
        acc = correct / n
        lo, hi = wilson_interval(correct, n)
        print(f"  Accuracy where both decided: {correct}/{n} = {acc:.1%}")
        print(f"  Wilson 95% CI: [{lo:.1%}, {hi:.1%}]")
        errors = [r for r in inferred_known if r["inferred_gender"] != r["verified_gender"].strip().upper()]
        if errors:
            print("  Errors:")
            for r in errors:
                print(f"    {r['person_id']} {r['full_name_ru']}: inferred {r['inferred_gender']}, verified {r['verified_gender']}")
        else:
            print("  No errors in the verified sample.")
    return True


def main():
    rebuild = "--rebuild" in sys.argv
    if OUT_CSV.exists() and not rebuild:
        with OUT_CSV.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if score_sample(rows):
            return
        print(f"{OUT_CSV} exists but has no verified rows yet; fill `verified_gender` and re-run.")
        return
    build_sample()


if __name__ == "__main__":
    main()
