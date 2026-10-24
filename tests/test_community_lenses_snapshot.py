"""H1899: frozen comparison packages — temporal separation, manifests, reproducibility.

Built on the FIXTURE database (`build.build_database()`), so the whole file runs
in under a second and never depends on which local sources happen to be present
on the machine. Three synthetic records are injected to exercise the temporal
gate in all three directions: pre-cutoff, post-cutoff, and undated.

Gates covered: V4 (zero 2026 leakage, undated in neither package), V11 (complete
SHA-256 manifest, unlisted-file detection, content-identical rebuild) and R13
(an existing destination is never overwritten).
"""
from __future__ import annotations

import json

import pytest

from community_lenses import build, snapshot


CUTOFF = "2025-12-31"


@pytest.fixture()
def conn():
    connection = build.build_database()
    template = connection.execute(
        "SELECT * FROM record WHERE created_at IS NOT NULL ORDER BY record_id LIMIT 1"
    ).fetchone()
    if template is None:  # pragma: no cover - fixtures always carry dated records
        pytest.skip("no dated fixture record to clone")
    columns = template.keys()

    def _clone(suffix: str, created_at: str | None, is_partial: int) -> None:
        values = dict(zip(columns, template))
        values["record_id"] = f"{values['corpus_id']}:h1899-{suffix}"
        values["source_record_id"] = f"h1899-{suffix}"
        values["created_at"] = created_at
        values["is_partial_2026"] = is_partial
        placeholders = ", ".join(f":{column}" for column in columns)
        connection.execute(
            f"INSERT INTO record ({', '.join(columns)}) VALUES ({placeholders})", values
        )

    _clone("pre", "2024-05-05T10:00:00", 0)
    _clone("post", "2026-03-03T10:00:00", 1)
    _clone("undated", None, 0)
    connection.commit()
    return connection


# ---------------------------------------------------------------------------
# V4 — temporal separation
# ---------------------------------------------------------------------------

def test_through_2025_holds_no_2026_record(conn):
    rows, accounting = snapshot.select_records(conn, snapshot.THROUGH_2025, CUTOFF)
    assert rows
    assert all(str(row["created_at"])[:10] <= CUTOFF for row in rows)
    assert snapshot.validate_cutoff(rows, snapshot.THROUGH_2025, CUTOFF) == []
    assert accounting["excluded_undated"] >= 1


def test_partial_2026_holds_only_2026_records(conn):
    rows, _accounting = snapshot.select_records(conn, snapshot.PARTIAL_2026, CUTOFF)
    assert rows
    assert all(str(row["created_at"])[:10] > CUTOFF for row in rows)
    assert snapshot.validate_cutoff(rows, snapshot.PARTIAL_2026, CUTOFF) == []


def test_undated_records_belong_to_neither_package(conn):
    through, through_acc = snapshot.select_records(conn, snapshot.THROUGH_2025, CUTOFF)
    partial, partial_acc = snapshot.select_records(conn, snapshot.PARTIAL_2026, CUTOFF)
    ids = {row["record_id"] for row in through} | {row["record_id"] for row in partial}
    undated = [
        row["record_id"]
        for row in conn.execute("SELECT record_id FROM record WHERE created_at IS NULL")
    ]
    assert undated, "the fixture must contain at least one undated record"
    for record_id in undated:
        assert record_id not in ids
    assert through_acc["excluded_undated"] == partial_acc["excluded_undated"] == len(undated)


def test_a_leaked_record_is_detected():
    leaked = [{"record_id": "x:1", "created_at": "2026-02-02T00:00:00"}]
    assert snapshot.validate_cutoff(leaked, snapshot.THROUGH_2025, CUTOFF)
    assert snapshot.validate_cutoff(
        [{"record_id": "x:2", "created_at": "2019-02-02T00:00:00"}],
        snapshot.PARTIAL_2026,
        CUTOFF,
    )


# ---------------------------------------------------------------------------
# Rights: only approved-exportable quotes travel
# ---------------------------------------------------------------------------

def test_snapshot_quote_file_carries_only_approved_exports(conn, tmp_path):
    destination = snapshot.freeze(
        snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF, root=tmp_path,
        created_at="1970-01-01T00:00:00Z",
    )
    text = (destination / "quotes_exportable.csv").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines[0].startswith("quote_id"), "header must always be present"
    # The register's mechanical gate currently approves nothing; a package may
    # therefore be header-only, but it may never contain a non-approved row.
    assert len(lines) - 1 == len(snapshot.exportable_quote_rows())


# ---------------------------------------------------------------------------
# R13 — never overwrite an existing package
# ---------------------------------------------------------------------------

def test_existing_destination_is_refused(conn, tmp_path):
    snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF, root=tmp_path,
                    created_at="1970-01-01T00:00:00Z")
    with pytest.raises(snapshot.SnapshotError) as excinfo:
        snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF, root=tmp_path)
    assert "already exists" in str(excinfo.value)


def test_unknown_snapshot_name_is_refused(conn, tmp_path):
    with pytest.raises(snapshot.SnapshotError):
        snapshot.freeze("whatever-2027", conn, {}, cutoff=CUTOFF, root=tmp_path)


# ---------------------------------------------------------------------------
# V11 — manifest completeness and verification
# ---------------------------------------------------------------------------

def test_manifest_lists_every_file_and_verifies(conn, tmp_path):
    destination = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                                  root=tmp_path, created_at="1970-01-01T00:00:00Z")
    assert snapshot.verify_snapshot(destination) == []

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    listed = {entry["path"] for entry in manifest["files"]}
    on_disk = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path.name not in ("manifest.json", "manifest.txt")
    }
    assert listed == on_disk
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
    assert manifest["created_at"] == "1970-01-01T00:00:00Z"
    assert "created_at" in manifest["creation_metadata_fields"]
    assert (destination / "manifest.txt").exists()
    assert (destination / "DATA_DICTIONARY.md").exists()
    assert (destination / "schema.sql").read_text(encoding="utf-8").startswith("-- corpus")


def test_tampered_file_fails_verification(conn, tmp_path):
    destination = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                                  root=tmp_path, created_at="1970-01-01T00:00:00Z")
    records = destination / "records.csv"
    records.write_text(records.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    errors = snapshot.verify_snapshot(destination)
    assert any("hash mismatch" in error for error in errors)


def test_unlisted_file_fails_verification(conn, tmp_path):
    destination = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                                  root=tmp_path, created_at="1970-01-01T00:00:00Z")
    (destination / "smuggled.csv").write_text("x\n", encoding="utf-8")
    errors = snapshot.verify_snapshot(destination)
    assert any("unlisted file present" in error for error in errors)


def test_missing_file_fails_verification(conn, tmp_path):
    destination = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                                  root=tmp_path, created_at="1970-01-01T00:00:00Z")
    (destination / "records.csv").unlink()
    errors = snapshot.verify_snapshot(destination)
    assert any("listed file missing" in error for error in errors)


# ---------------------------------------------------------------------------
# V11 — unchanged rebuild is content-identical except creation metadata
# ---------------------------------------------------------------------------

def test_unchanged_rebuild_is_content_identical(conn, tmp_path):
    first = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                            root=tmp_path / "a", created_at="1970-01-01T00:00:00Z")
    second = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                             root=tmp_path / "b", created_at="2026-08-06T12:00:00Z")
    assert snapshot.compare_snapshots(first, second) == [], (
        "an unchanged rebuild must differ only in the documented creation metadata"
    )
    left = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    right = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    assert left["created_at"] != right["created_at"]


def test_compare_detects_a_real_content_difference(conn, tmp_path):
    first = snapshot.freeze(snapshot.THROUGH_2025, conn, {}, cutoff=CUTOFF,
                            root=tmp_path / "a", created_at="1970-01-01T00:00:00Z")
    second = snapshot.freeze(snapshot.PARTIAL_2026, conn, {}, cutoff=CUTOFF,
                             root=tmp_path / "b", created_at="1970-01-01T00:00:00Z")
    differences = snapshot.compare_snapshots(first, second)
    assert any("content differs" in difference for difference in differences)


# ---------------------------------------------------------------------------
# Rights: closed-corpus subject lines never travel inside a package
# ---------------------------------------------------------------------------

def test_non_public_titles_are_not_copied_into_a_package(conn):
    rows, _ = snapshot.select_records(conn, snapshot.THROUGH_2025, CUTOFF)
    for row in rows:
        if row["access_class"] != "public":
            assert row["public_title"] == "", row["record_id"]


def test_the_live_packages_verify_if_they_exist():
    for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
        destination = snapshot.SNAPSHOT_ROOT / name
        if not destination.exists():
            pytest.skip(f"{name} not frozen in this checkout")
        assert snapshot.verify_snapshot(destination) == []
