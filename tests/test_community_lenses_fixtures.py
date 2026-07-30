"""H1893: representative fixtures for all five lenses.

Definition-of-done checks: all five fixtures validate; invalid IDs/
references, missing provenance/rights, and native/derived mixing fail
closed; round trip and deterministic rebuild pass; rights defaults for
closed-list quote/person fields default non-public/non-exportable.
"""
from __future__ import annotations

import copy
import sqlite3

import pytest

from community_lenses import build
from community_lenses.schema import CORPUS_IDS


def test_all_five_lenses_have_a_fixture():
    assert build.list_fixture_corpora() == tuple(sorted(CORPUS_IDS))


def test_clean_build_from_all_fixtures_validates_with_no_errors():
    fixtures = build.load_all_fixtures()
    conn = build.build_database(fixtures)
    errors = build.validate_build(conn, fixtures)
    assert errors == [], errors


def test_deterministic_rebuild_produces_byte_identical_dump():
    fixtures = build.load_all_fixtures()
    conn1 = build.build_database(fixtures)
    conn2 = build.build_database(fixtures)
    assert build.canonical_json(conn1) == build.canonical_json(conn2)


def test_canonical_json_is_stable_regardless_of_fixture_dict_order():
    fixtures = build.load_all_fixtures()
    reordered = dict(reversed(list(fixtures.items())))
    conn1 = build.build_database(fixtures)
    conn2 = build.build_database(reordered)
    assert build.canonical_json(conn1) == build.canonical_json(conn2)


def test_serialize_reload_round_trip_preserves_every_record():
    fixtures = build.load_all_fixtures()
    conn = build.build_database(fixtures)
    before = build.dump_database(conn)

    # "Reload" = re-run the same deterministic build from the same fixture
    # source (there is no adapter/live acquisition in H1893 scope, so the
    # only round trip available is fixture -> db -> canonical dump -> same
    # fixture -> db -> canonical dump).
    conn2 = build.build_database(build.load_all_fixtures())
    after = build.dump_database(conn2)
    assert before == after
    for corpus_id in CORPUS_IDS:
        assert any(
            row["corpus_id"] == corpus_id for row in before["record"]
        ), f"no record row survived the round trip for {corpus_id!r}"


@pytest.mark.parametrize("corpus_id", sorted(CORPUS_IDS))
def test_each_lens_fixture_manifest_is_individually_valid(corpus_id):
    fixture = build.load_fixture(corpus_id)
    manifest = build.fixture_manifest(fixture)
    from community_lenses.manifests import validate_manifest

    assert validate_manifest(manifest) == []


def test_bvp_fixture_is_explicitly_unavailable_not_silently_empty():
    fixture = build.load_fixture("bvp")
    assert fixture["manifest"]["coverage_status"] == "unavailable"
    assert fixture["records"][0]["status"] == "unavailable"


# --- fail-closed: invalid IDs/references ------------------------------------

def test_record_id_not_matching_make_record_id_fails_closed():
    fixture = copy.deepcopy(build.load_fixture("conferences"))
    fixture["records"][0]["record_id"] = "conferences:a-different-id"
    errors = build.validate_record_ids(fixture)
    assert errors and "!=" in errors[0]


def test_dangling_container_reference_fails_closed():
    fixtures = {cid: copy.deepcopy(build.load_fixture(cid)) for cid in CORPUS_IDS}
    fixtures["conferences"]["records"][0]["container_id"] = "conferences:container:does-not-exist"
    with pytest.raises(sqlite3.IntegrityError):
        build.build_database(fixtures)


def test_dangling_snapshot_reference_fails_closed():
    fixtures = {cid: copy.deepcopy(build.load_fixture(cid)) for cid in CORPUS_IDS}
    fixtures["conferences"]["records"][0]["source_snapshot_id"] = "does-not-exist"
    with pytest.raises(sqlite3.IntegrityError):
        build.build_database(fixtures)


# --- fail-closed: missing provenance/rights ----------------------------------

def test_missing_manifest_field_fails_closed():
    fixtures = {cid: copy.deepcopy(build.load_fixture(cid)) for cid in CORPUS_IDS}
    fixtures["vk_ors"]["manifest"]["rights_basis"] = ""
    with pytest.raises(build.FixtureError):
        build.build_database(fixtures)


def test_missing_access_class_fails_closed():
    fixtures = {cid: copy.deepcopy(build.load_fixture(cid)) for cid in CORPUS_IDS}
    del fixtures["conferences"]["records"][0]["access_class"]
    with pytest.raises(sqlite3.IntegrityError):
        build.build_database(fixtures)


# --- fail-closed: native/derived mixing --------------------------------------

def test_copying_native_title_into_shared_topic_value_fails_closed():
    fixtures = {cid: copy.deepcopy(build.load_fixture(cid)) for cid in CORPUS_IDS}
    record = fixtures["conferences"]["records"][0]
    fixtures["conferences"]["classification_assignments"].append(
        {
            "record_id": record["record_id"],
            "scheme_id": "shared_topic",
            "label_id": "grammar_linguistics",
            "value": record["title_or_subject"],
            "evidence_span": "title",
            "method": "test_bad_shortcut",
            "method_version": "1.0.0",
            "confidence": 1.0,
            "review_status": "pending",
            "reviewer": None,
            "assigned_at": "2026-07-30T00:00:00Z",
        }
    )
    conn = build.build_database(fixtures)
    errors = build.validate_build(conn, fixtures)
    assert any("native/derived mixing" in e for e in errors)


def test_unknown_codebook_label_fails_closed():
    fixtures = {cid: copy.deepcopy(build.load_fixture(cid)) for cid in CORPUS_IDS}
    record = fixtures["conferences"]["records"][0]
    fixtures["conferences"]["classification_assignments"].append(
        {
            "record_id": record["record_id"],
            "scheme_id": "shared_topic",
            "label_id": "not_a_real_label",
            "value": "x",
            "evidence_span": "title",
            "method": "test",
            "method_version": "1.0.0",
            "confidence": 1.0,
            "review_status": "pending",
            "reviewer": None,
            "assigned_at": "2026-07-30T00:00:00Z",
        }
    )
    conn = build.build_database(fixtures)
    errors = build.validate_build(conn, fixtures)
    assert any("not present in codebook" in e for e in errors)


# --- rights defaults must fail closed (hard guardrail) -----------------------

def test_quote_omitting_rights_review_status_defaults_non_exportable():
    conn = build.build_database()
    conn.execute(
        """INSERT INTO record
           (record_id, corpus_id, source_record_id, container_id, record_type,
            status, access_class, source_snapshot_id)
           VALUES ('conferences:rights-test','conferences','rights-test',NULL,
                   't','active','public','conferences:2026-07-17')"""
    )
    conn.execute(
        """INSERT INTO quote (quote_id, record_id, quote_verbatim)
           VALUES ('q1','conferences:rights-test','a verbatim quote')"""
    )
    row = conn.execute(
        "SELECT rights_review_status FROM quote WHERE quote_id='q1'"
    ).fetchone()
    assert row["rights_review_status"] == "non_exportable"


def test_quote_cannot_be_inserted_as_bare_public_status():
    conn = build.build_database()
    conn.execute(
        """INSERT INTO record
           (record_id, corpus_id, source_record_id, container_id, record_type,
            status, access_class, source_snapshot_id)
           VALUES ('conferences:rights-test2','conferences','rights-test2',NULL,
                   't','active','public','conferences:2026-07-17')"""
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO quote (quote_id, record_id, quote_verbatim, rights_review_status)
               VALUES ('q2','conferences:rights-test2','a verbatim quote','public')"""
        )


def test_person_defaults_to_pending_review_never_auto_accepted():
    conn = build.build_database()
    conn.execute(
        "INSERT INTO person (person_id, display_name) VALUES ('p1','Test Person')"
    )
    row = conn.execute(
        "SELECT review_status FROM person WHERE person_id='p1'"
    ).fetchone()
    assert row["review_status"] == "pending"


def test_person_match_assertion_cannot_be_silently_accepted():
    conn = build.build_database()
    conn.execute(
        "INSERT INTO person (person_id, display_name) VALUES ('p1','Test Person')"
    )
    conn.execute(
        """INSERT INTO record
           (record_id, corpus_id, source_record_id, container_id, record_type,
            status, access_class, source_snapshot_id)
           VALUES ('conferences:match-test','conferences','match-test',NULL,
                   't','active','public','conferences:2026-07-17')"""
    )
    conn.execute(
        """INSERT INTO person_match_assertion
           (assertion_id, source_record_id, candidate_person_id, method)
           VALUES ('a1','conferences:match-test','p1','name_similarity')"""
    )
    row = conn.execute(
        "SELECT status FROM person_match_assertion WHERE assertion_id='a1'"
    ).fetchone()
    assert row["status"] == "pending", (
        "a person_match_assertion must require an explicit human-reviewed "
        "flag to become 'accepted' — it must never default to accepted"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO person_match_assertion
               (assertion_id, source_record_id, candidate_person_id, method, status)
               VALUES ('a2','conferences:match-test','p1','name_similarity','auto_merged')"""
        )
