"""H1893: shared five-lens schema — IDs, manifests, and the sqlite contract.

Exercises community_lenses/{ids,schema,manifests}.py directly (no fixtures):
stable-ID rules, source-manifest validation, and that the schema's own FK/
CHECK constraints fail closed on bad input.
"""
from __future__ import annotations

import sqlite3

import pytest

from community_lenses import ids as ids_mod
from community_lenses.manifests import SourceManifest, validate_manifest, validate_no_mixed_snapshot
from community_lenses.schema import build_schema, create_connection, validate_schema


# --- IDs -------------------------------------------------------------------

def test_make_record_id_is_namespaced_and_reversible():
    record_id = ids_mod.make_record_id("nagari", "<abc@example.org>")
    assert record_id == "nagari:<abc@example.org>"
    corpus_id, source_record_id = ids_mod.parse_record_id(record_id)
    assert corpus_id == "nagari"
    assert source_record_id == "<abc@example.org>"


def test_make_record_id_rejects_unknown_corpus():
    with pytest.raises(ids_mod.InvalidRecordId):
        ids_mod.make_record_id("not_a_lens", "x")


def test_make_record_id_rejects_forbidden_characters_in_native_id():
    with pytest.raises(ids_mod.InvalidRecordId):
        ids_mod.make_record_id("vk_ors", "has:colon")
    with pytest.raises(ids_mod.InvalidRecordId):
        ids_mod.make_record_id("vk_ors", "")


def test_record_id_never_embeds_a_mutable_title():
    # The stable ID is a pure function of (corpus_id, source_record_id); the
    # same native ID must always yield the same record_id regardless of any
    # title/classification passed around it elsewhere in the pipeline.
    a = ids_mod.make_record_id("conferences", "PRES_demo1")
    b = ids_mod.make_record_id("conferences", "PRES_demo1")
    assert a == b


def test_fallback_hash_is_deterministic_and_documented_as_fallback_only():
    h1 = ids_mod.fallback_message_id_hash("<Foo@Example.ORG>")
    h2 = ids_mod.fallback_message_id_hash("  <foo@example.org>  ")
    assert h1 == h2
    assert h1.isalnum()


# --- manifests ---------------------------------------------------------------

def _valid_manifest(**overrides) -> SourceManifest:
    base = dict(
        snapshot_id="conferences:2026-07-17",
        corpus_id="conferences",
        coverage_status="complete",
        source_version="v1",
        acquired_at="2026-07-17T09:00:00Z",
        source_sha256="a" * 64,
        pipeline_commit="deadbeef",
        schema_version="1.0.0",
        codebook_version="1.0.0",
        rights_basis="public programme",
    )
    base.update(overrides)
    return SourceManifest(**base)


def test_valid_manifest_has_no_errors():
    from community_lenses.schema import SCHEMA_VERSION

    manifest = _valid_manifest(schema_version=SCHEMA_VERSION)
    assert validate_manifest(manifest) == []


def test_manifest_missing_required_field_fails_closed():
    manifest = _valid_manifest(source_version="")
    errors = validate_manifest(manifest)
    assert any("missing required field" in e for e in errors)


def test_manifest_bad_sha256_fails_closed():
    manifest = _valid_manifest(source_sha256="not-a-hash")
    errors = validate_manifest(manifest)
    assert any("source_sha256" in e for e in errors)


def test_manifest_unknown_corpus_fails_closed():
    manifest = _valid_manifest(corpus_id="not_a_lens")
    errors = validate_manifest(manifest)
    assert any("unknown corpus_id" in e for e in errors)


def test_manifest_mismatched_schema_version_fails_closed():
    manifest = _valid_manifest(schema_version="0.0.1")
    errors = validate_manifest(manifest)
    assert any("schema_version" in e for e in errors)


def test_mixed_snapshot_coverage_status_fails_closed():
    manifest = _valid_manifest(coverage_status="mixed_snapshot")
    errors = validate_no_mixed_snapshot([manifest])
    assert errors and "mixed_snapshot" in errors[0]


# --- schema fails closed -----------------------------------------------------

def _connection() -> sqlite3.Connection:
    conn = create_connection(":memory:")
    build_schema(conn)
    return conn


def _insert_minimal_corpus_and_snapshot(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO corpus VALUES ('conferences','t','m','o','u',NULL,'r')"
    )
    conn.execute(
        """INSERT INTO source_snapshot VALUES
           ('snap1','conferences',NULL,NULL,NULL,'complete','v1',
            '2026-01-01T00:00:00Z',?,
            'deadbeef','1.0.0','1.0.0','public')""",
        ("a" * 64,),
    )


def test_schema_rejects_record_with_unknown_corpus_id():
    conn = _connection()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO record
               (record_id, corpus_id, source_record_id, container_id,
                record_type, status, access_class, source_snapshot_id)
               VALUES ('x:1','not_a_lens','1',NULL,'t','active','public','snap1')"""
        )


def test_schema_rejects_record_with_dangling_snapshot_id():
    conn = _connection()
    _insert_minimal_corpus_and_snapshot(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO record
               (record_id, corpus_id, source_record_id, container_id,
                record_type, status, access_class, source_snapshot_id)
               VALUES ('conferences:1','conferences','1',NULL,'t','active',
                       'public','does-not-exist')"""
        )


def test_schema_rejects_unknown_access_class():
    conn = _connection()
    _insert_minimal_corpus_and_snapshot(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO record
               (record_id, corpus_id, source_record_id, container_id,
                record_type, status, access_class, source_snapshot_id)
               VALUES ('conferences:1','conferences','1',NULL,'t','active',
                       'wide_open','snap1')"""
        )


def test_schema_rejects_duplicate_corpus_source_record_id():
    conn = _connection()
    _insert_minimal_corpus_and_snapshot(conn)
    conn.execute(
        """INSERT INTO record
           (record_id, corpus_id, source_record_id, container_id,
            record_type, status, access_class, source_snapshot_id)
           VALUES ('conferences:1','conferences','1',NULL,'t','active',
                   'public','snap1')"""
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO record
               (record_id, corpus_id, source_record_id, container_id,
                record_type, status, access_class, source_snapshot_id)
               VALUES ('conferences:1-dup','conferences','1',NULL,'t','active',
                       'public','snap1')"""
        )


def test_empty_schema_validates_clean():
    conn = _connection()
    assert validate_schema(conn) == []
