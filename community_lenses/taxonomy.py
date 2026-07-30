"""Versioned codebook contracts (H1893 shells; substantive mappings are later waves).

Each codebook in ``community_lenses/codebooks/`` is a CSV with a fixed column
contract (label_id, label, definition, inclusion, exclusion, examples,
parent_label_id, status, version). H1893 populates only the six axes named in
the handoff, and only where the labels are already decision-locked in
ARCHITECTURE (the shared intellectual-content axis, the shared community
function axis, the Gumilev argument-level scale, and the existing Renou
state/register vocabulary reused from generate_renou_layer.py). It does not
perform the substantive per-source crosswalk adjudication (mapping every
native label to a shared one): that is Step 6 of the full Wave-1
implementation and out of scope here.
"""

from __future__ import annotations

import csv
from pathlib import Path

CODEBOOK_NAMES = (
    "native_topic",
    "shared_topic",
    "community_function",
    "renou_state",
    "renou_register",
    "argument_level",
)

REQUIRED_COLUMNS = (
    "label_id",
    "label",
    "definition",
    "inclusion",
    "exclusion",
    "examples",
    "parent_label_id",
    "status",
    "version",
)

STATUS_VALUES = ("active", "deprecated", "proposed")

CODEBOOKS_DIR = Path(__file__).resolve().parent / "codebooks"


class CodebookError(ValueError):
    pass


def codebook_path(name: str) -> Path:
    if name not in CODEBOOK_NAMES:
        raise CodebookError(f"unknown codebook {name!r}; expected one of {CODEBOOK_NAMES}")
    return CODEBOOKS_DIR / f"{name}.csv"


def load_codebook(name: str) -> list[dict]:
    path = codebook_path(name)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            raise CodebookError(
                f"{path.name} columns {reader.fieldnames} do not match the "
                f"required contract {list(REQUIRED_COLUMNS)}"
            )
        return list(reader)


def _all_label_ids() -> set[str]:
    """Union of label_ids across every codebook.

    ``parent_label_id`` may point either within the same codebook (a
    sub-label of a broader one) or into a coarser sibling codebook (e.g. a
    ``renou_register`` row's parent is a ``renou_state`` label) — both are
    legitimate, so parent existence is checked against this combined set.
    """
    ids: set[str] = set()
    for codebook_name in CODEBOOK_NAMES:
        try:
            rows = load_codebook(codebook_name)
        except (CodebookError, FileNotFoundError):
            # A sibling codebook file may legitimately be absent (e.g. a test
            # exercising a single codebook in isolation); a missing sibling
            # just means its labels are not available as parent targets.
            continue
        for row in rows:
            ids.add(row["label_id"])
    return ids


def validate_codebook(name: str) -> list[str]:
    """Return contract violations for one codebook; empty means it is valid."""
    errors: list[str] = []
    try:
        rows = load_codebook(name)
    except CodebookError as exc:
        return [str(exc)]

    all_ids = _all_label_ids()
    seen_ids: set[str] = set()
    seen_versions: set[str] = set()
    for row in rows:
        label_id = row["label_id"]
        if not label_id:
            errors.append(f"{name}: row with empty label_id")
            continue
        if label_id in seen_ids:
            errors.append(f"{name}: duplicate label_id {label_id!r}")
        seen_ids.add(label_id)

        if not row["label"]:
            errors.append(f"{name}: label_id {label_id!r} has empty label")
        if not row["version"]:
            errors.append(f"{name}: label_id {label_id!r} has empty version")
        else:
            seen_versions.add(row["version"])
        if row["status"] not in STATUS_VALUES:
            errors.append(
                f"{name}: label_id {label_id!r} has unknown status {row['status']!r}"
            )
        parent = row.get("parent_label_id")
        if parent and parent not in all_ids:
            errors.append(
                f"{name}: label_id {label_id!r} has dangling parent_label_id {parent!r}"
            )

    return errors


def validate_all_codebooks() -> dict[str, list[str]]:
    return {name: validate_codebook(name) for name in CODEBOOK_NAMES}


def codebook_version(name: str) -> str:
    """A codebook's declared version is the single version shared by all its rows."""
    rows = load_codebook(name)
    versions = {row["version"] for row in rows if row["version"]}
    if len(versions) > 1:
        raise CodebookError(
            f"{name} mixes versions within one file: {sorted(versions)}; "
            "bump via a new version for all rows or split the codebook"
        )
    return next(iter(versions), "0.0.0")
