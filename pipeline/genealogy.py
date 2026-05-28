"""Genealogy / advisor-student loader for the IndologyScholars corpus.

Reads ``curation/teacher_student.csv`` (schema: ``curation/teacher_student_schema.md``),
validates each row against the schema, and exposes the verified set as a list of
``Relationship`` records. Heuristic candidate suggestions live separately in
``analytics_output/lineage_candidates.csv`` (produced by
``article/work_lineage_candidates.py``) and are **never** read by this module —
only manually verified rows are loaded.

Issue #9 ("Genealogy and networks"): this module is the read side of the
genealogy track. The build pipeline does not (yet) wire its output into
``site_data.json`` or profile pages — that wiring is the next step, kept
separate to avoid colliding with active visualisation work.
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
CURATION_CSV = ROOT / "curation" / "teacher_student.csv"

REQUIRED_FIELDS = (
    "student_normalized_key",
    "student_display_name",
    "advisor_normalized_key",
    "advisor_display_name",
    "relationship_type",
    "status",
    "added_date",
)

RELATIONSHIP_TYPES = {
    "advisor",
    "supervisor",
    "mentor",
    "academic_lineage",
    "lectured",
}

STATUSES = {"verified", "candidate", "disputed"}


@dataclass(frozen=True)
class Relationship:
    student_key: str
    student_name: str
    advisor_key: str
    advisor_name: str
    relationship_type: str
    period_start: int | None
    period_end: int | None
    evidence_url: str
    evidence_note: str
    status: str
    added_date: str
    notes: str
    row_number: int  # 1-based in the source CSV, for diagnostics


def _coerce_year(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        year = int(raw)
    except ValueError as exc:
        raise ValueError(f"period field must be an integer year or empty, got {raw!r}") from exc
    if not (1700 <= year <= 2100):
        raise ValueError(f"period year out of range: {year}")
    return year


def _validate(row: dict, row_number: int) -> None:
    for field in REQUIRED_FIELDS:
        if not (row.get(field) or "").strip():
            raise ValueError(f"row {row_number}: required field {field!r} is empty")
    if row["relationship_type"].strip() not in RELATIONSHIP_TYPES:
        raise ValueError(
            f"row {row_number}: relationship_type must be one of "
            f"{sorted(RELATIONSHIP_TYPES)}, got {row['relationship_type']!r}"
        )
    if row["status"].strip() not in STATUSES:
        raise ValueError(
            f"row {row_number}: status must be one of {sorted(STATUSES)}, "
            f"got {row['status']!r}"
        )
    if row["status"].strip() == "verified" and not (row.get("evidence_url") or "").strip():
        raise ValueError(
            f"row {row_number}: status=verified requires a non-empty evidence_url "
            "(see curation/teacher_student_schema.md anti-fabrication rule)"
        )
    if row["student_normalized_key"].strip() == row["advisor_normalized_key"].strip():
        raise ValueError(
            f"row {row_number}: student and advisor keys are identical "
            f"({row['student_normalized_key']!r})"
        )


def _iter_rows(path: Path) -> Iterator[tuple[int, dict]]:
    """Yield (csv_row_number, row_dict). Skips blank and `#`-comment lines."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        # Read header from the first non-comment, non-blank line.
        header: list[str] | None = None
        raw_rows: list[tuple[int, list[str]]] = []
        for csv_lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            cells = next(csv.reader([line]))
            if header is None:
                header = cells
            else:
                raw_rows.append((csv_lineno, cells))
        if header is None:
            return
        for csv_lineno, cells in raw_rows:
            if len(cells) < len(header):
                cells = cells + [""] * (len(header) - len(cells))
            yield csv_lineno, dict(zip(header, cells))


def load_relationships(
    path: Path = CURATION_CSV,
    *,
    include_candidates: bool = False,
) -> list[Relationship]:
    """Load and validate relationships. Returns only ``verified`` by default."""
    if not path.exists():
        return []
    out: list[Relationship] = []
    for row_number, row in _iter_rows(path):
        _validate(row, row_number)
        if not include_candidates and row["status"].strip() != "verified":
            continue
        out.append(
            Relationship(
                student_key=row["student_normalized_key"].strip(),
                student_name=row["student_display_name"].strip(),
                advisor_key=row["advisor_normalized_key"].strip(),
                advisor_name=row["advisor_display_name"].strip(),
                relationship_type=row["relationship_type"].strip(),
                period_start=_coerce_year(row.get("period_start", "")),
                period_end=_coerce_year(row.get("period_end", "")),
                evidence_url=(row.get("evidence_url") or "").strip(),
                evidence_note=(row.get("evidence_note") or "").strip(),
                status=row["status"].strip(),
                added_date=row["added_date"].strip(),
                notes=(row.get("notes") or "").strip(),
                row_number=row_number,
            )
        )
    return out


def by_advisor(relationships: Iterable[Relationship]) -> dict[str, list[Relationship]]:
    out: dict[str, list[Relationship]] = {}
    for r in relationships:
        out.setdefault(r.advisor_key, []).append(r)
    return out


def by_student(relationships: Iterable[Relationship]) -> dict[str, list[Relationship]]:
    out: dict[str, list[Relationship]] = {}
    for r in relationships:
        out.setdefault(r.student_key, []).append(r)
    return out


if __name__ == "__main__":
    rels = load_relationships(include_candidates=False)
    candidates = load_relationships(include_candidates=True)
    print(f"verified: {len(rels)}  total (verified+candidate+disputed): {len(candidates)}")
    if rels:
        for r in rels:
            print(f"  {r.advisor_name}  ->  {r.student_name}  [{r.relationship_type}]")
