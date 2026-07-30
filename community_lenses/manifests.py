"""Source-manifest contract: pinned, hashed, coverage-labeled inputs.

Per ARCHITECTURE §"source_snapshot" and VERIFICATION V1: every lens's snapshot
must declare coverage dates, cutoff, coverage status, source version/hash,
acquisition time, pipeline commit, schema/codebook versions, and rights
basis before any record from it enters the shared build. No source may
silently refresh mid-build.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .ids import CORPUS_IDS
from .schema import COVERAGE_STATUSES, SCHEMA_VERSION

REQUIRED_FIELDS = (
    "snapshot_id",
    "corpus_id",
    "coverage_status",
    "source_version",
    "acquired_at",
    "source_sha256",
    "pipeline_commit",
    "schema_version",
    "codebook_version",
    "rights_basis",
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SourceManifest:
    snapshot_id: str
    corpus_id: str
    coverage_status: str
    source_version: str
    acquired_at: str
    source_sha256: str
    pipeline_commit: str
    schema_version: str
    codebook_version: str
    rights_basis: str
    coverage_start: str | None = None
    coverage_end: str | None = None
    cutoff_date: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def validate_manifest(manifest: SourceManifest) -> list[str]:
    """Return a list of contract violations; empty means the manifest is valid."""
    errors: list[str] = []
    data = manifest.to_dict()

    for field_name in REQUIRED_FIELDS:
        if not data.get(field_name):
            errors.append(f"missing required field: {field_name}")

    if manifest.corpus_id not in CORPUS_IDS:
        errors.append(f"unknown corpus_id: {manifest.corpus_id!r}")

    if manifest.coverage_status not in COVERAGE_STATUSES:
        errors.append(f"unknown coverage_status: {manifest.coverage_status!r}")

    for date_field in ("coverage_start", "coverage_end", "cutoff_date"):
        value = data.get(date_field)
        if value is not None and not _ISO_DATE.match(value):
            errors.append(f"{date_field} must be ISO YYYY-MM-DD, got {value!r}")

    if manifest.acquired_at and not _ISO_DATETIME.match(manifest.acquired_at):
        errors.append(
            f"acquired_at must be ISO 8601 datetime, got {manifest.acquired_at!r}"
        )

    if not re.match(r"^[0-9a-f]{64}$", manifest.source_sha256 or ""):
        errors.append(
            f"source_sha256 must be a 64-char lowercase hex digest, got "
            f"{manifest.source_sha256!r}"
        )

    if manifest.schema_version != SCHEMA_VERSION:
        errors.append(
            f"schema_version {manifest.schema_version!r} does not match "
            f"package SCHEMA_VERSION {SCHEMA_VERSION!r}"
        )

    return errors


def dump_manifests(manifests: list[SourceManifest]) -> str:
    """Deterministically serialize manifests: sorted by corpus_id, sorted keys."""
    ordered = sorted(manifests, key=lambda m: m.corpus_id)
    return json.dumps([m.to_dict() for m in ordered], indent=2, sort_keys=True) + "\n"


def load_manifests(path: str | Path) -> list[SourceManifest]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [SourceManifest(**row) for row in raw]


def validate_no_mixed_snapshot(manifests: list[SourceManifest]) -> list[str]:
    """Fail closed on any lens whose manifest is a mixed/blended snapshot."""
    return [
        f"corpus {m.corpus_id!r} has coverage_status=mixed_snapshot (snapshot {m.snapshot_id!r})"
        for m in manifests
        if m.coverage_status == "mixed_snapshot"
    ]
