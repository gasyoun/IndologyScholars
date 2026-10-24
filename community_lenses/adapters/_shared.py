"""Shared helpers for the four Wave 1B adapters.

Deliberately independent of any live network access: every helper here
operates on files already present on disk (a sqlite db, a csv, an mbox).
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..manifests import SourceManifest
from ..schema import SCHEMA_VERSION
from ..taxonomy import codebook_version

REPO_ROOT = Path(__file__).resolve().parents[2]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_acquired_at(path: Path) -> str:
    """ISO-8601 UTC timestamp of a source file's last modification.

    Pinning acquired_at to the source file's own mtime (rather than
    "now") is what makes an adapter idempotent across repeated runs: two
    runs against the same unchanged file produce the same manifest.
    """
    dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def pipeline_commit() -> str:
    """Current git HEAD short sha, or a documented placeholder if unavailable."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown-not-a-git-checkout"


def codebook_version_or_default(name: str) -> str:
    try:
        return codebook_version(name)
    except Exception:
        return "1.0.0"


def build_manifest(
    *,
    corpus_id: str,
    snapshot_id: str,
    coverage_status: str,
    source_version: str,
    acquired_at: str,
    source_sha256: str,
    rights_basis: str,
    coverage_start: str | None = None,
    coverage_end: str | None = None,
    cutoff_date: str | None = None,
) -> SourceManifest:
    return SourceManifest(
        snapshot_id=snapshot_id,
        corpus_id=corpus_id,
        coverage_status=coverage_status,
        source_version=source_version,
        acquired_at=acquired_at,
        source_sha256=source_sha256,
        pipeline_commit=pipeline_commit(),
        schema_version=SCHEMA_VERSION,
        codebook_version=codebook_version_or_default("native_topic"),
        rights_basis=rights_basis,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        cutoff_date=cutoff_date,
    )


def unavailable_fixture(
    *,
    corpus_id: str,
    title: str,
    native_unit: str,
    rights_basis: str,
    gap_note: str,
) -> dict:
    """A graceful placeholder fixture for a corpus whose source is absent.

    Mirrors the shape of community_lenses/fixtures/bvp.json's own
    coverage_status="unavailable" pattern -- a schema-valid, fail-open stub
    that a downstream build can still load without crashing, and that shows
    up as a NAMED gap in the coverage report rather than a silent success.
    """
    snapshot_id = f"{corpus_id}:none"
    return {
        "corpus": {
            "corpus_id": corpus_id,
            "title": title,
            "medium": "unknown",
            "forum_orientation": "unknown",
            "native_unit": native_unit,
            "canonical_url": None,
            "rights_status": "unknown_source_not_available_on_this_machine",
        },
        "manifest": build_manifest(
            corpus_id=corpus_id,
            snapshot_id=snapshot_id,
            coverage_status="unavailable",
            source_version="not_acquired",
            # Deterministic placeholder, not wall-clock "now" -- source_version
            # is already "not_acquired", and a real timestamp here would break
            # idempotence across repeated builds of the same unavailable source.
            acquired_at="1970-01-01T00:00:00Z",
            source_sha256="0" * 64,
            rights_basis=rights_basis,
        ).to_dict(),
        "containers": [],
        "records": [
            {
                "record_id": f"{corpus_id}:placeholder",
                "corpus_id": corpus_id,
                "source_record_id": "placeholder",
                "source_record_id_method": "native",
                "container_id": None,
                "record_type": "unavailable_placeholder",
                "title_or_subject": None,
                "body_locator": gap_note,
                "created_at": None,
                "language": None,
                "canonical_url": None,
                "content_sha256": None,
                "status": "unavailable",
                "is_partial_2026": 0,
                "access_class": "unknown",
                "source_snapshot_id": snapshot_id,
            }
        ],
        "record_names": [],
        "record_relations": [],
        "classification_assignments": [],
        "annotations": [],
        "quotes": [],
    }


def render_coverage_report(
    *,
    corpus_id: str,
    title: str,
    native_unit: str,
    coverage_status: str,
    manifest_snapshot_id: str,
    date_range: str,
    denominator_definition: str,
    included: int,
    excluded: int,
    failures: int,
    completeness_status: str,
    notes: list[str],
) -> str:
    lines = [
        f"# {title} — H1895 coverage report",
        "",
        f"_Generated by community_lenses/adapters (corpus_id={corpus_id})._",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Native unit type | {native_unit} |",
        f"| Manifest / snapshot ID | `{manifest_snapshot_id}` |",
        f"| Coverage status | `{coverage_status}` |",
        f"| Date range | {date_range} |",
        f"| Denominator definition | {denominator_definition} |",
        f"| Included | {included} |",
        f"| Excluded | {excluded} |",
        f"| Failures | {failures} |",
        f"| Completeness | {completeness_status} |",
        "",
    ]
    if notes:
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)
