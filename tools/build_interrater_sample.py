"""Inter-rater reliability sampling for L1 theme and argument-level coding.

Design requirements implemented here:

1. **True blinding.** The coding sheet given to the second coder
   (`interrater_sample_blind.csv`) contains no trace of the existing
   classifications. The originals are written to a separate key file
   (`interrater_sample_key.csv`) that is joined only at scoring time by
   `tools/compute_interrater_agreement.py`. Do not give the key file to
   the second coder.

2. **Stratified sampling.** A simple random sample from a corpus that is
   ~86% L1 / <1% L3 contains almost no elevated-level items, making the
   reliability of exactly the most contested codes unmeasurable. The sample
   therefore includes ALL argument-level-3 items, an oversample of level-2
   items, and a random fill of level-1 items, with the stratum recorded in
   the key file so agreement can be reported per stratum.

Usage:
  python tools/build_interrater_sample.py
Outputs:
  analytics_output/interrater_sample_blind.csv  (give to second coder)
  analytics_output/interrater_sample_key.csv    (keep; used for scoring)
"""

import csv
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site_data.json"
BLIND_PATH = ROOT / "analytics_output" / "interrater_sample_blind.csv"
KEY_PATH = ROOT / "analytics_output" / "interrater_sample_key.csv"

SEED = 20260612
SAMPLE_SIZE = 100
L2_TARGET = 30  # oversampled relative to corpus share

THEME_CODES = [
    "history_and_culture",
    "religion_and_philosophy",
    "literature_and_poetry",
    "linguistics_and_philology",
    "art_and_material_culture",
    "unspecified",
]


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def collect_talks():
    """Unique presentations with their published L1 theme and argument level."""
    data = load_site_data()
    talks = {}
    for scholar in data.get("scholars", []):
        for talk in scholar.get("talks", []):
            pid = talk.get("presentation_id")
            title = (talk.get("title") or "").strip()
            if not pid or not title or pid in talks:
                continue
            level = talk.get("argument_level") or talk.get("gumilyov_scale")
            talks[pid] = {
                "presentation_id": pid,
                "title": title,
                "year": talk.get("year"),
                "series": talk.get("series") or "",
                "existing_l1": (talk.get("theme") or {}).get("code") or "unspecified",
                "existing_g": str(level) if level else "",
            }
    return sorted(talks.values(), key=lambda t: str(t["presentation_id"]))


def main():
    rng = random.Random(SEED)
    talks = [t for t in collect_talks() if t["existing_g"] in ("1", "2", "3")]
    print(f"Unique classified presentations: {len(talks)}")

    by_level = {"1": [], "2": [], "3": []}
    for t in talks:
        by_level[t["existing_g"]].append(t)

    sample = list(by_level["3"])  # census of the rare stratum
    sample += rng.sample(by_level["2"], min(L2_TARGET, len(by_level["2"])))
    l1_fill = max(0, SAMPLE_SIZE - len(sample))
    sample += rng.sample(by_level["1"], min(l1_fill, len(by_level["1"])))

    # Shuffle so stratum membership is not inferable from row order.
    rng.shuffle(sample)

    print(f"Sample: {len(sample)} items "
          f"(G3 census: {len(by_level['3'])}, G2 oversample: {min(L2_TARGET, len(by_level['2']))}, "
          f"G1 fill: {l1_fill}) | seed {SEED}")

    BLIND_PATH.parent.mkdir(parents=True, exist_ok=True)
    blind_fields = ["presentation_id", "title", "year", "series", "coder_2_l1", "coder_2_g"]
    with BLIND_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=blind_fields, extrasaction="ignore")
        w.writeheader()
        for t in sample:
            w.writerow({**t, "coder_2_l1": "", "coder_2_g": ""})

    key_fields = ["presentation_id", "existing_l1", "existing_g"]
    with KEY_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=key_fields, extrasaction="ignore")
        w.writeheader()
        for t in sorted(sample, key=lambda t: str(t["presentation_id"])):
            w.writerow(t)

    print(f"Blind coding sheet: {BLIND_PATH}")
    print(f"Answer key (do NOT share with the coder): {KEY_PATH}")
    print()
    print("Instructions for the second coder (send together with the blind sheet):")
    print("  1. Read only the title, year, and series.")
    print("  2. coder_2_l1: ONE theme code from:")
    for c in THEME_CODES:
        print(f"       {c}")
    print("  3. coder_2_g: ONE argument level:")
    print("       1 = micro-case (single text/author/term/source)")
    print("       2 = tradition, school, or broad class of phenomena")
    print("       3 = inter-regional, civilizational, or methodological frame")
    print("  4. Do not look up the original classification, the author, or the abstract.")
    print("  5. When in doubt, prefer the most conservative code (unspecified / 1).")
    print()
    print("Scoring: python tools/compute_interrater_agreement.py")


if __name__ == "__main__":
    main()
