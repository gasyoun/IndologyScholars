"""H1894 regression tests: atomic INDOLOGY-L feed fetch/promotion.

Locks in the all-or-nothing contract for tools/fetch_indology_feed.py: a
clean fetch promotes every declared file behind one local manifest, and
every fault mode (missing file, checksum mismatch, schema mismatch,
row-count drift, interrupted download) aborts before the live snapshot
directory is touched, so the prior good snapshot survives byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fetch_indology_feed as feed  # noqa: E402


COVERAGE_CSV = "state,message_count\nI,3\nII,5\n"
EXPORT_CSV = "export_id,title\nE1,foo\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_versioned_manifest(*, coverage_row_count: int | None = 2, schema_version: str = "1.0") -> dict:
    return {
        "schema_version": schema_version,
        "upstream_commit": "abc123",
        "coverage_status": "complete",
        "rights_basis": "public Pipermail archive",
        "gaps": [],
        "files": [
            {"name": "renou_coverage.csv", "sha256": _sha(COVERAGE_CSV), "row_count": coverage_row_count},
            {"name": "renou_export_index.csv", "sha256": _sha(EXPORT_CSV), "row_count": 1},
        ],
    }


def make_fetcher(manifest: dict | None, files: dict[str, str], *, fail_on: str | None = None):
    def fetcher(url: str) -> bytes:
        name = url.rsplit("/", 1)[-1]
        if name == feed.MANIFEST_NAME:
            if manifest is None:
                raise feed.URLError("no manifest published")
            return json.dumps(manifest).encode("utf-8")
        if name == fail_on:
            # A dropped connection mid-transfer, distinct from a clean 404:
            # not a URLError/HTTPError, so it must abort rather than skip.
            raise ConnectionResetError(f"simulated interruption fetching {name}")
        if name not in files:
            raise feed.URLError(f"404 {name}")
        return files[name].encode("utf-8")

    return fetcher


@pytest.fixture
def paths(tmp_path):
    return {
        "dest_dir": tmp_path / "indology_feed",
        "manifest_path": tmp_path / "indology_feed_manifest.json",
        "staging_parent": tmp_path,
    }


def test_clean_promotion_versioned_manifest(paths):
    manifest = make_versioned_manifest()
    fetcher = make_fetcher(manifest, {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV})

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "ok"
    assert report["mode"] == "versioned"
    assert (paths["dest_dir"] / "renou_coverage.csv").read_text(encoding="utf-8") == COVERAGE_CSV
    assert (paths["dest_dir"] / "renou_export_index.csv").read_text(encoding="utf-8") == EXPORT_CSV

    local_manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    pinned_names = {f["name"] for f in local_manifest["files"]}
    assert pinned_names == {"renou_coverage.csv", "renou_export_index.csv"}
    for entry in local_manifest["files"]:
        assert entry["sha256"]
    assert local_manifest["coverage_status"] == "complete"


def test_clean_promotion_legacy_fallback(paths):
    files = {name: f"h,v\n1,2\n" for name in feed.LEGACY_FEED_FILES}
    fetcher = make_fetcher(None, files)

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "ok"
    assert report["mode"] == "legacy"
    for name in feed.LEGACY_FEED_FILES:
        assert (paths["dest_dir"] / name).exists()
    local_manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    assert local_manifest["coverage_status"] == "partial"
    assert local_manifest["gaps"]


def _seed_baseline(paths):
    manifest = make_versioned_manifest()
    fetcher = make_fetcher(manifest, {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV})
    baseline = feed.fetch_feed(fetcher=fetcher, **paths)
    assert baseline["status"] == "ok"
    return {
        "coverage_bytes": (paths["dest_dir"] / "renou_coverage.csv").read_bytes(),
        "export_bytes": (paths["dest_dir"] / "renou_export_index.csv").read_bytes(),
        "manifest_bytes": paths["manifest_path"].read_bytes(),
    }


def _assert_snapshot_preserved(paths, baseline):
    assert (paths["dest_dir"] / "renou_coverage.csv").read_bytes() == baseline["coverage_bytes"]
    assert (paths["dest_dir"] / "renou_export_index.csv").read_bytes() == baseline["export_bytes"]
    assert paths["manifest_path"].read_bytes() == baseline["manifest_bytes"]


def test_missing_declared_file_aborts_and_preserves_snapshot(paths):
    baseline = _seed_baseline(paths)

    manifest = make_versioned_manifest()
    # Declare a third file the fetcher will never be able to serve.
    manifest["files"].append({"name": "renou_state_summary.csv", "sha256": _sha("x"), "row_count": 0})
    fetcher = make_fetcher(manifest, {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV})

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "error"
    assert "missing declared file" in report["reason"]
    _assert_snapshot_preserved(paths, baseline)


def test_checksum_mismatch_aborts_and_preserves_snapshot(paths):
    baseline = _seed_baseline(paths)

    manifest = make_versioned_manifest()
    manifest["files"][0]["sha256"] = "0" * 64
    fetcher = make_fetcher(manifest, {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV})

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "error"
    assert "checksum mismatch" in report["reason"]
    _assert_snapshot_preserved(paths, baseline)


def test_schema_mismatch_aborts_and_preserves_snapshot(paths):
    baseline = _seed_baseline(paths)

    manifest = make_versioned_manifest(schema_version="99.0")
    fetcher = make_fetcher(manifest, {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV})

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "error"
    assert "schema_version" in report["reason"]
    _assert_snapshot_preserved(paths, baseline)


def test_row_count_drift_aborts_and_preserves_snapshot(paths):
    baseline = _seed_baseline(paths)

    manifest = make_versioned_manifest(coverage_row_count=999)
    fetcher = make_fetcher(manifest, {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV})

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "error"
    assert "row-count drift" in report["reason"]
    _assert_snapshot_preserved(paths, baseline)


def test_interrupted_fetch_aborts_and_preserves_snapshot(paths):
    baseline = _seed_baseline(paths)

    manifest = make_versioned_manifest()
    fetcher = make_fetcher(
        manifest,
        {"renou_coverage.csv": COVERAGE_CSV, "renou_export_index.csv": EXPORT_CSV},
        fail_on="renou_export_index.csv",
    )

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "error"
    assert "interrupted fetch" in report["reason"]
    _assert_snapshot_preserved(paths, baseline)
    # No leftover staging directories under the parent.
    leftovers = [p for p in paths["staging_parent"].iterdir() if p.name.startswith(".indology_feed_staging_")]
    assert leftovers == []


def test_legacy_missing_file_aborts_and_preserves_snapshot(paths):
    baseline = _seed_baseline(paths)

    files = {name: "h,v\n1,2\n" for name in feed.LEGACY_FEED_FILES[:-1]}
    fetcher = make_fetcher(None, files)

    report = feed.fetch_feed(fetcher=fetcher, **paths)

    assert report["status"] == "error"
    assert report["mode"] == "legacy"
    _assert_snapshot_preserved(paths, baseline)


def test_validate_against_manifest_reports_multiple_errors():
    manifest = make_versioned_manifest(schema_version="0.1")
    manifest["files"][0]["sha256"] = "0" * 64
    staged = {
        "renou_coverage.csv": feed.StagedFile("renou_coverage.csv", _sha(COVERAGE_CSV), len(COVERAGE_CSV), 2),
        "renou_export_index.csv": feed.StagedFile("renou_export_index.csv", _sha(EXPORT_CSV), len(EXPORT_CSV), 1),
    }
    errors = feed.validate_against_manifest(manifest, staged)
    assert any("schema_version" in e for e in errors)
    assert any("checksum mismatch" in e for e in errors)
