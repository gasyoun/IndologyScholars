"""Build a deterministic review sample for the classification reliability packet."""
from __future__ import annotations

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from classification_overrides import CLASSIFICATION_OVERRIDES  # noqa: E402

CLASSIFICATION_CSV = ROOT / "analytics_output" / "expanded_classification_deepseek.csv"
OUT_CSV = ROOT / "analytics_output" / "classification_reliability_sample.csv"
SEED = "classification-reliability-v1-2026-05-31"


def rank(row: dict[str, str], bucket: str) -> str:
    basis = "|".join([SEED, bucket, row.get("presentation_id", ""), row.get("title", "")])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def read_rows() -> list[dict[str, str]]:
    with CLASSIFICATION_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def add_selected(
    selected: dict[str, dict[str, str]],
    row: dict[str, str],
    bucket: str,
    reason: str,
) -> None:
    presentation_id = row.get("presentation_id", "")
    if not presentation_id:
        return
    existing = selected.get(presentation_id)
    if existing:
        existing["selection_reason"] = existing["selection_reason"] + "; " + reason
        return
    selected[presentation_id] = {
        "presentation_id": presentation_id,
        "year": row.get("year", ""),
        "series": row.get("series", ""),
        "title": row.get("title", ""),
        "theme_l1": row.get("theme_l1", ""),
        "period_l2": row.get("period_l2", ""),
        "gumilyov_level": row.get("gumilyov_level", ""),
        "meso_codes": row.get("meso_codes", ""),
        "confidence": row.get("confidence", ""),
        "review_bucket": bucket,
        "review_status": "manual_override"
        if presentation_id in CLASSIFICATION_OVERRIDES
        else "queued_for_manual_review",
        "selection_reason": reason,
        "model_rationale": row.get("rationale", ""),
        "override_reason": CLASSIFICATION_OVERRIDES.get(presentation_id, {}).get("reason", ""),
    }


def take_ranked(rows: list[dict[str, str]], bucket: str, count: int) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: rank(row, bucket))[:count]


def build_sample(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}

    by_level: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_series_level: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        level = row.get("gumilyov_level", "")
        by_level[level].append(row)
        by_series_level[(row.get("series", ""), level)].append(row)

    for row in by_level.get("3", []):
        add_selected(selected, row, "all_g3", "all rare G3 records are included")

    for row in rows:
        if row.get("presentation_id") in CLASSIFICATION_OVERRIDES:
            add_selected(selected, row, "manual_override", "expert-reviewed override record")

    for (series, level), bucket_rows in sorted(by_series_level.items()):
        if level not in {"1", "2"}:
            continue
        bucket = f"{series}|G{level}"
        for row in take_ranked(bucket_rows, bucket, 6):
            add_selected(
                selected,
                row,
                "stratified_series_level",
                f"deterministic sample from {series} G{level}",
            )

    return sorted(
        selected.values(),
        key=lambda row: (
            int(row.get("gumilyov_level") or 0),
            row.get("series", ""),
            row.get("year", ""),
            row.get("presentation_id", ""),
        ),
    )


def write_sample(rows: list[dict[str, str]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "presentation_id",
        "year",
        "series",
        "title",
        "theme_l1",
        "period_l2",
        "gumilyov_level",
        "meso_codes",
        "confidence",
        "review_bucket",
        "review_status",
        "selection_reason",
        "model_rationale",
        "override_reason",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = read_rows()
    sample = build_sample(rows)
    write_sample(sample)
    print(f"Wrote {len(sample)} classification reliability rows to {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
