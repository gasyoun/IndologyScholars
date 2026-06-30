"""Import human case-study review notes into curated case metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ALLOWED_STATUSES = {"candidate", "selected", "rejected", "needs_more_review"}
ALLOWED_TRACKS = {"", "philological_substance", "infrastructure_history"}
INTAKE_COLUMNS = [
    "thread_root_id",
    "curation_status",
    "review_track",
    "short_title",
    "public_note",
    "why_it_matters",
    "curator_comments",
    "manual_reviewer",
    "manual_review_date",
]
UPDATE_COLUMNS = [col for col in INTAKE_COLUMNS if col != "thread_root_id"]


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()


def ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame


def seed_first_review_notes(output_dir: Path, overwrite: bool = False) -> Path:
    processed_dir = output_dir / "data" / "processed"
    curation_dir = output_dir / "data" / "curation"
    curation_dir.mkdir(parents=True, exist_ok=True)
    path = curation_dir / "first_review_notes.csv"
    if path.exists() and not overwrite:
        return path
    shortlist = read_csv(processed_dir / "first_review_shortlist.csv")
    if shortlist.empty:
        raise FileNotFoundError("first_review_shortlist.csv is required before seeding review notes")
    notes = pd.DataFrame(
        {
            "thread_root_id": shortlist["thread_root_id"],
            "curation_status": "",
            "review_track": "",
            "short_title": shortlist["short_title"],
            "public_note": "",
            "why_it_matters": "",
            "curator_comments": "",
            "manual_reviewer": "",
            "manual_review_date": "",
        }
    )
    notes.to_csv(path, index=False, encoding="utf-8")
    return path


def validate_value(column: str, value: str) -> tuple[bool, str]:
    if column == "curation_status" and value not in ALLOWED_STATUSES:
        return False, f"invalid status: {value}"
    if column == "review_track" and value not in ALLOWED_TRACKS:
        return False, f"invalid track: {value}"
    return True, ""


def import_review_notes(
    output_dir: Path,
    notes_path: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, object]:
    processed_dir = output_dir / "data" / "processed"
    curated_path = processed_dir / "curated_case_studies.csv"
    audit_path = processed_dir / "review_import_audit.csv"
    notes_path = notes_path or output_dir / "data" / "curation" / "first_review_notes.csv"
    curated = ensure_columns(read_csv(curated_path), INTAKE_COLUMNS)
    notes = ensure_columns(read_csv(notes_path), INTAKE_COLUMNS)
    if curated.empty:
        raise FileNotFoundError("curated_case_studies.csv is required before importing review notes")
    if notes.empty:
        raise FileNotFoundError(f"{notes_path} is empty or missing")

    curated_index = {str(row["thread_root_id"]): idx for idx, row in curated.iterrows()}
    audit_rows = []
    updates = 0
    for note_row_number, note in notes.iterrows():
        thread_id = str(note["thread_root_id"]).strip()
        if not thread_id:
            audit_rows.append(
                {
                    "thread_root_id": "",
                    "column": "",
                    "action": "error",
                    "old_value": "",
                    "new_value": "",
                    "reason": "missing thread_root_id",
                    "note_row": note_row_number + 2,
                }
            )
            continue
        if thread_id not in curated_index:
            audit_rows.append(
                {
                    "thread_root_id": thread_id,
                    "column": "",
                    "action": "error",
                    "old_value": "",
                    "new_value": "",
                    "reason": "thread_root_id not found in curated_case_studies.csv",
                    "note_row": note_row_number + 2,
                }
            )
            continue
        target_idx = curated_index[thread_id]
        for column in UPDATE_COLUMNS:
            new_value = str(note[column]).strip()
            if new_value == "":
                continue
            ok, reason = validate_value(column, new_value)
            old_value = str(curated.at[target_idx, column]).strip()
            if not ok:
                action = "error"
            elif column == "curation_status" and old_value == "candidate" and new_value != "candidate":
                action = "would_update" if dry_run else "updated"
                reason = "dry run" if dry_run else ""
                if not dry_run:
                    curated.at[target_idx, column] = new_value
                updates += 1
            elif old_value and old_value != new_value and not force:
                action = "skipped"
                reason = "target field is non-empty; use --force to overwrite"
            elif old_value == new_value:
                action = "unchanged"
                reason = "same value"
            else:
                action = "would_update" if dry_run else "updated"
                reason = "dry run" if dry_run else ""
                if not dry_run:
                    curated.at[target_idx, column] = new_value
                updates += 1
            audit_rows.append(
                {
                    "thread_root_id": thread_id,
                    "column": column,
                    "action": action,
                    "old_value": old_value,
                    "new_value": new_value,
                    "reason": reason,
                    "note_row": note_row_number + 2,
                }
            )

    audit = pd.DataFrame(
        audit_rows,
        columns=["thread_root_id", "column", "action", "old_value", "new_value", "reason", "note_row"],
    )
    audit.to_csv(audit_path, index=False, encoding="utf-8")
    if not dry_run:
        curated.to_csv(curated_path, index=False, encoding="utf-8")
    return {
        "notes_path": notes_path,
        "curated_path": curated_path,
        "audit_path": audit_path,
        "audit_rows": len(audit),
        "updates": updates,
        "dry_run": dry_run,
        "force": force,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--notes-path", type=Path)
    parser.add_argument("--seed", action="store_true", help="Create data/curation/first_review_notes.csv from the shortlist.")
    parser.add_argument("--overwrite-seed", action="store_true", help="Overwrite existing seeded notes when used with --seed.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    if args.seed:
        path = seed_first_review_notes(args.output_dir, overwrite=args.overwrite_seed)
        print({"seeded": path})
        return
    print(import_review_notes(args.output_dir, args.notes_path, args.dry_run, args.force))


if __name__ == "__main__":
    main()
