"""Fetch the small Renou/Atlas feed published by gasyoun/IndologyArchiveAtlas.

`Indology/` split out into its own repo (H460) so this site no longer reads
that tree directly. `generate_renou_layer.py`'s cross-site comparison instead
consumes this one-way feed, cached locally under
`analytics_output/indology_feed/`. Safe to skip: a missing feed just means
the archive-side columns in the Renou comparison come back empty (`read_csv`
already tolerates a missing file).

Atomic promotion contract (H1894): every fetch is all-or-nothing.

1. Try to fetch a versioned `feed/manifest.json` from upstream first. If it
   declares a file set, download every declared file into a staging
   directory and validate schema version, checksums, and (for CSVs) row
   counts against what the manifest promised.
2. If upstream has not yet published `feed/manifest.json` (H1894 Step 2
   action 6), fall back to the legacy fixed five-file Renou export and
   validate only that every expected file downloaded and parses as CSV.
3. Only after every declared/expected file validates does the staging
   directory get swapped in for the live one -- two local, near-instant
   directory renames, so nothing partial is ever visible under
   `LOCAL_FEED_DIR`. Any failure (missing file, checksum mismatch, schema
   mismatch, row-count drift, or an interrupted download) aborts before
   either rename runs, leaving the previously promoted snapshot
   byte-identical.
4. A local pinning manifest (`LOCAL_MANIFEST_PATH`) records the coverage
   status, source version, acquisition time, pipeline commit, and a
   sha256/size/row-count entry for every promoted file -- one manifest
   pinning every file this pipeline actually promoted, independent of
   whether upstream ships its own.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
import urllib.request

FEED_BASE_URL = "https://raw.githubusercontent.com/gasyoun/IndologyArchiveAtlas/main/feed"
MANIFEST_NAME = "manifest.json"

# Legacy fallback file set: used only while upstream has not yet published a
# versioned feed/manifest.json. Never invent atlas-only records in this mode.
LEGACY_FEED_FILES = [
    "renou_coverage.csv",
    "renou_export_index.csv",
    "renou_state_summary.csv",
    "renou_register_summary.csv",
    "renou_message_matches.csv",
]

# Feed schema versions this fetcher knows how to validate/promote. Bump only
# alongside a matching update to validate_against_manifest below.
SUPPORTED_FEED_SCHEMA_VERSIONS = ("1.0",)

ROOT = Path(__file__).resolve().parents[1]
LOCAL_FEED_DIR = ROOT / "analytics_output" / "indology_feed"
LOCAL_MANIFEST_PATH = ROOT / "analytics_output" / "indology_feed_manifest.json"

Fetcher = Callable[[str], bytes]


class FeedFetchError(RuntimeError):
    """Raised for genuinely unexpected failures (not the expected abort paths)."""


@dataclass(frozen=True)
class StagedFile:
    name: str
    sha256: str
    size: int
    row_count: int | None


def default_fetcher(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _csv_row_count(data: bytes) -> int | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    rows = list(csv.reader(io.StringIO(text)))
    return max(len(rows) - 1, 0) if rows else 0


def fetch_upstream_manifest(fetcher: Fetcher = default_fetcher) -> dict | None:
    """Return the parsed feed/manifest.json, or None if unavailable/unreachable."""
    try:
        data = fetcher(f"{FEED_BASE_URL}/{MANIFEST_NAME}")
    except (URLError, HTTPError, TimeoutError, OSError):
        return None
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _download_files(file_names: list[str], staging_dir: Path, fetcher: Fetcher) -> dict[str, StagedFile]:
    """Download every named file into staging_dir.

    A file the server genuinely does not have (HTTPError/URLError) is
    skipped rather than aborting the whole fetch -- it surfaces as a
    "missing declared file" validation error instead, distinct from a
    connection dropping mid-transfer (any other exception), which aborts
    immediately as an interrupted fetch.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged: dict[str, StagedFile] = {}
    for name in file_names:
        try:
            data = fetcher(f"{FEED_BASE_URL}/{name}")
        except (HTTPError, URLError):
            continue
        (staging_dir / name).write_bytes(data)
        staged[name] = StagedFile(
            name=name,
            sha256=_sha256_bytes(data),
            size=len(data),
            row_count=_csv_row_count(data) if name.endswith(".csv") else None,
        )
    return staged


def validate_against_manifest(upstream_manifest: dict, staged: dict[str, StagedFile]) -> list[str]:
    """Validate downloaded files against a versioned upstream manifest."""
    errors: list[str] = []

    schema_version = upstream_manifest.get("schema_version")
    if schema_version not in SUPPORTED_FEED_SCHEMA_VERSIONS:
        errors.append(f"unsupported feed schema_version: {schema_version!r}")

    declared_files = upstream_manifest.get("files") or []
    declared_names = {entry["name"] for entry in declared_files}
    staged_names = set(staged)

    missing = declared_names - staged_names
    if missing:
        errors.append(f"missing declared file(s): {sorted(missing)}")

    for entry in declared_files:
        name = entry.get("name")
        if name not in staged:
            continue
        s = staged[name]
        expected_sha = entry.get("sha256")
        if expected_sha and expected_sha != s.sha256:
            errors.append(
                f"checksum mismatch for {name}: manifest declares {expected_sha}, downloaded has {s.sha256}"
            )
        expected_rows = entry.get("row_count")
        if expected_rows is not None and s.row_count is not None and expected_rows != s.row_count:
            errors.append(
                f"row-count drift for {name}: manifest declares {expected_rows}, downloaded has {s.row_count}"
            )

    return errors


def validate_legacy_staging(staged: dict[str, StagedFile], expected_names: list[str]) -> list[str]:
    """Validate the legacy (pre-manifest) fallback fetch."""
    errors: list[str] = []
    missing = set(expected_names) - set(staged)
    if missing:
        errors.append(f"missing legacy feed file(s): {sorted(missing)}")
    for name, s in staged.items():
        if name.endswith(".csv") and s.row_count is None:
            errors.append(f"{name}: could not be parsed as CSV")
    return errors


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _promote(staging_dir: Path, live_dir: Path) -> None:
    """Swap staging_dir in for live_dir via two local, near-instant renames.

    Nothing touches live_dir before this is called (all validation runs
    against staging_dir only), and any failure here rolls back to the prior
    live_dir contents rather than leaving a half-swapped state.
    """
    backup_dir = live_dir.with_name(live_dir.name + ".prev")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    if live_dir.exists():
        live_dir.rename(backup_dir)
    try:
        staging_dir.rename(live_dir)
    except Exception:
        if backup_dir.exists() and not live_dir.exists():
            backup_dir.rename(live_dir)
        raise
    if backup_dir.exists():
        shutil.rmtree(backup_dir)


def _write_local_manifest(
    staged: dict[str, StagedFile],
    *,
    manifest_path: Path,
    coverage_status: str,
    source_version: str,
    rights_basis: str,
    gaps: list[str],
) -> None:
    combined = _sha256_bytes(
        "".join(staged[name].sha256 for name in sorted(staged)).encode("utf-8")
    )
    payload = {
        "snapshot_id": f"indology_l:{source_version}",
        "corpus_id": "indology_l",
        "coverage_status": coverage_status,
        "source_version": source_version,
        "acquired_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_sha256": combined,
        "pipeline_commit": _git_commit(),
        "schema_version": SUPPORTED_FEED_SCHEMA_VERSIONS[0],
        "codebook_version": "1.0.0",
        "rights_basis": rights_basis,
        "gaps": gaps,
        "files": [
            {
                "name": staged[name].name,
                "sha256": staged[name].sha256,
                "size": staged[name].size,
                "row_count": staged[name].row_count,
            }
            for name in sorted(staged)
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch_feed(
    *,
    dest_dir: Path = LOCAL_FEED_DIR,
    manifest_path: Path = LOCAL_MANIFEST_PATH,
    fetcher: Fetcher = default_fetcher,
    staging_parent: Path | None = None,
) -> dict:
    """Fetch, validate, and atomically promote the INDOLOGY-L feed.

    Returns a report dict with at least a "status" key ("ok" or "error").
    Expected failure modes (unreachable manifest, checksum mismatch, missing
    file, schema mismatch, row-count drift, interrupted download) are
    reported rather than raised, and leave dest_dir/manifest_path untouched.
    """
    staging_parent = staging_parent or dest_dir.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=".indology_feed_staging_", dir=staging_parent))

    try:
        upstream_manifest = fetch_upstream_manifest(fetcher)

        if upstream_manifest is not None:
            declared_names = [entry["name"] for entry in upstream_manifest.get("files", [])]
            try:
                staged = _download_files(declared_names, staging_dir, fetcher)
            except Exception as exc:
                return {"status": "error", "mode": "versioned", "reason": f"interrupted fetch: {exc}"}

            errors = validate_against_manifest(upstream_manifest, staged)
            if errors:
                return {"status": "error", "mode": "versioned", "reason": "; ".join(errors)}

            _promote(staging_dir, dest_dir)
            _write_local_manifest(
                staged,
                manifest_path=manifest_path,
                coverage_status=upstream_manifest.get("coverage_status", "complete"),
                source_version=upstream_manifest.get(
                    "upstream_commit", upstream_manifest.get("generated_at", "unknown")
                ),
                rights_basis=upstream_manifest.get(
                    "rights_basis",
                    "public Pipermail archive via gasyoun/IndologyArchiveAtlas feed",
                ),
                gaps=upstream_manifest.get("gaps", []),
            )
            return {"status": "ok", "mode": "versioned", "files": sorted(staged)}

        # Legacy fallback: upstream has not yet published feed/manifest.json.
        try:
            staged = _download_files(LEGACY_FEED_FILES, staging_dir, fetcher)
        except Exception as exc:
            return {"status": "error", "mode": "legacy", "reason": f"interrupted fetch: {exc}"}

        errors = validate_legacy_staging(staged, LEGACY_FEED_FILES)
        if errors:
            return {"status": "error", "mode": "legacy", "reason": "; ".join(errors)}

        _promote(staging_dir, dest_dir)
        _write_local_manifest(
            staged,
            manifest_path=manifest_path,
            coverage_status="partial",
            source_version="legacy-unversioned",
            rights_basis=(
                "public Pipermail archive via gasyoun/IndologyArchiveAtlas feed "
                "(pre-manifest legacy export)"
            ),
            gaps=["upstream feed/manifest.json not yet published; broader atlas exports unavailable"],
        )
        return {"status": "ok", "mode": "legacy", "files": sorted(staged)}
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = fetch_feed()
    if report["status"] == "ok":
        print(
            f"fetched+promoted {len(report['files'])} feed file(s) "
            f"({report['mode']} mode) into {LOCAL_FEED_DIR}"
        )
    else:
        print(f"feed fetch aborted ({report['mode']} mode): {report['reason']}", file=sys.stderr)
        print(f"previous snapshot preserved at {LOCAL_FEED_DIR}", file=sys.stderr)
