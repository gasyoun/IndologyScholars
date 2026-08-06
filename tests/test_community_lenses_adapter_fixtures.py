"""H1895: the four Wave 1B adapters (conferences, nagari, vk_ors, indology_l).

Definition-of-done checks: every adapter's fixture loads and validates twice
without duplicate/churn (idempotence); record_ids are stable and match
``ids.make_record_id``; parent/reference integrity and rights defaults hold
under the full H1893 build guardrails; native and derived labels stay
distinguishable; per-source denominators are reported; a mixed/partial
snapshot is rejected fail-closed; and the graceful "source unavailable"
degrade path never crashes and never fabricates data. BVP is out of scope
(H1896 owns it).
"""

from __future__ import annotations

import copy
import sqlite3

import pytest

from community_lenses import build
from community_lenses.adapters import conferences, indology_l, nagari, vk_ors
from community_lenses.ids import make_record_id
from community_lenses.manifests import SourceManifest, validate_manifest, validate_no_mixed_snapshot
from community_lenses.schema import build_schema, create_connection

ADAPTERS = {
    "conferences": conferences,
    "nagari": nagari,
    "vk_ors": vk_ors,
    "indology_l": indology_l,
}


def _fresh_connection() -> sqlite3.Connection:
    conn = create_connection(":memory:")
    build_schema(conn)
    build.seed_taxonomy_schemes(conn)
    return conn


def _populate(conn: sqlite3.Connection, corpus_id: str, fixture: dict) -> None:
    if corpus_id == "conferences":
        conferences.insert_persons(conn, fixture)
    if corpus_id == "nagari":
        nagari.insert_extra_schemes(conn, fixture)
    build.populate_corpus(conn, fixture)


@pytest.mark.parametrize("corpus_id", sorted(ADAPTERS))
def test_adapter_fixture_matches_its_own_corpus_id(corpus_id):
    fixture = ADAPTERS[corpus_id].build_fixture()
    assert fixture["corpus"]["corpus_id"] == corpus_id
    assert fixture["manifest"]["corpus_id"] == corpus_id


@pytest.mark.parametrize("corpus_id", sorted(ADAPTERS))
def test_adapter_manifest_is_individually_valid(corpus_id):
    fixture = ADAPTERS[corpus_id].build_fixture()
    manifest = SourceManifest(**fixture["manifest"])
    assert validate_manifest(manifest) == []


@pytest.mark.parametrize("corpus_id", sorted(ADAPTERS))
def test_adapter_record_ids_are_stable_and_match_make_record_id(corpus_id):
    fixture = ADAPTERS[corpus_id].build_fixture()
    for record in fixture["records"]:
        expected = make_record_id(corpus_id, record["source_record_id"])
        assert record["record_id"] == expected


@pytest.mark.parametrize("corpus_id", sorted(ADAPTERS))
def test_adapter_fixture_loads_and_validates_with_no_errors(corpus_id):
    fixture = ADAPTERS[corpus_id].build_fixture()
    conn = _fresh_connection()
    _populate(conn, corpus_id, fixture)
    conn.commit()
    errors = build.validate_build(conn, {corpus_id: fixture})
    assert errors == [], errors


@pytest.mark.parametrize("corpus_id", sorted(ADAPTERS))
def test_adapter_build_is_idempotent_across_two_runs(corpus_id):
    """Running the adapter twice against the same unchanged source must not churn."""
    fixture_a = ADAPTERS[corpus_id].build_fixture()
    fixture_b = ADAPTERS[corpus_id].build_fixture()

    conn_a = _fresh_connection()
    _populate(conn_a, corpus_id, fixture_a)
    conn_a.commit()

    conn_b = _fresh_connection()
    _populate(conn_b, corpus_id, fixture_b)
    conn_b.commit()

    assert build.canonical_json(conn_a) == build.canonical_json(conn_b)


@pytest.mark.parametrize("corpus_id", ("conferences", "vk_ors"))
def test_adapter_produces_at_least_one_real_record(corpus_id):
    """conferences and vk_ors have real local source data on this machine."""
    fixture = ADAPTERS[corpus_id].build_fixture()
    assert fixture["manifest"]["coverage_status"] != "unavailable"
    assert len(fixture["records"]) > 0


def test_nagari_produces_a_pilot_slice_when_a_pilot_db_exists():
    fixture = nagari.build_fixture()
    # This machine has either a pilot nagari.db (coverage_status="pilot") or
    # none at all ("unavailable") -- both are legitimate, honest outcomes;
    # what must never happen is a silent "complete" claim with zero evidence.
    assert fixture["manifest"]["coverage_status"] in ("pilot", "complete", "unavailable")
    if fixture["manifest"]["coverage_status"] == "unavailable":
        assert fixture["records"][0]["status"] == "unavailable"
    else:
        assert len(fixture["records"]) > 0


def test_indology_l_is_a_named_blocked_gap_not_a_silent_success():
    """Requirement 5: reject mixed/partial input -- H1894 was never built, so refuse."""
    fixture = indology_l.build_fixture()
    assert fixture["manifest"]["coverage_status"] == "unavailable"
    assert fixture["records"][0]["status"] == "unavailable"
    report = indology_l.coverage_report(fixture)
    assert "H1894" in report


# --- graceful degrade: source absent -----------------------------------------

def test_nagari_degrades_gracefully_when_no_db_is_found(monkeypatch):
    monkeypatch.setattr(nagari, "_find_db", lambda: None)
    fixture = nagari.build_fixture()
    assert fixture["manifest"]["coverage_status"] == "unavailable"
    assert fixture["records"][0]["status"] == "unavailable"
    conn = _fresh_connection()
    _populate(conn, "nagari", fixture)
    conn.commit()
    assert build.validate_build(conn, {"nagari": fixture}) == []


def test_vk_ors_degrades_gracefully_when_no_db_is_found(monkeypatch):
    monkeypatch.setattr(vk_ors, "_find_db", lambda: None)
    fixture = vk_ors.build_fixture()
    assert fixture["manifest"]["coverage_status"] == "unavailable"
    assert fixture["records"][0]["status"] == "unavailable"
    conn = _fresh_connection()
    build.populate_corpus(conn, fixture)
    conn.commit()
    assert build.validate_build(conn, {"vk_ors": fixture}) == []


def test_conferences_degrades_gracefully_when_no_db_is_found(monkeypatch, tmp_path):
    monkeypatch.setattr(conferences, "DB_PATH", tmp_path / "does-not-exist.db")
    fixture = conferences.build_fixture()
    assert fixture["manifest"]["coverage_status"] == "unavailable"
    assert fixture["records"][0]["status"] == "unavailable"


# --- fail-closed: a mixed/partial snapshot must never build ------------------

def test_mixed_snapshot_coverage_status_is_rejected_fail_closed():
    fixture = copy.deepcopy(conferences.build_fixture())
    fixture["manifest"]["coverage_status"] = "mixed_snapshot"
    manifest = SourceManifest(**fixture["manifest"])
    errors = validate_no_mixed_snapshot([manifest])
    assert errors and "mixed_snapshot" in errors[0]


# --- rights defaults and native/derived separation ---------------------------

def test_nagari_never_auto_links_a_person():
    fixture = nagari.build_fixture()
    assert all(rn["person_id"] is None for rn in fixture["record_names"])


def test_vk_ors_never_invents_a_participant_identity():
    fixture = vk_ors.build_fixture()
    assert all(rn["person_id"] is None for rn in fixture["record_names"])


def test_conferences_persons_default_to_pending_unless_authority_confirms():
    fixture = conferences.build_fixture()
    for person in fixture.get("_persons", []):
        assert person["review_status"] in ("pending", "accepted")
        if person["review_status"] == "accepted":
            assert person["reviewer"] == "authority_ids.json"


def test_conferences_and_vk_ors_never_copy_native_title_into_a_shared_topic_value():
    for corpus_id in ("conferences", "vk_ors"):
        fixture = ADAPTERS[corpus_id].build_fixture()
        titles_by_record = {r["record_id"]: r.get("title_or_subject") for r in fixture["records"]}
        for assignment in fixture["classification_assignments"]:
            if assignment["scheme_id"] != "shared_topic":
                continue
            native_title = titles_by_record.get(assignment["record_id"])
            assert native_title is None or assignment["value"] != native_title


def test_no_adapter_writes_a_shared_topic_crosswalk_assignment():
    """H1897 owns the crosswalk; H1895 must not pre-empt it."""
    for corpus_id, module in ADAPTERS.items():
        fixture = module.build_fixture()
        scheme_ids = {a["scheme_id"] for a in fixture["classification_assignments"]}
        assert "shared_topic" not in scheme_ids, (
            f"{corpus_id} adapter must not assign shared_topic labels -- that "
            "crosswalk adjudication is H1897's scope"
        )


# --- coverage report: denominators and completeness -------------------------

@pytest.mark.parametrize("corpus_id", sorted(ADAPTERS))
def test_coverage_report_names_native_unit_and_denominator(corpus_id):
    fixture = ADAPTERS[corpus_id].build_fixture()
    report = ADAPTERS[corpus_id].coverage_report(fixture)
    assert "Native unit type" in report
    assert "Denominator definition" in report
    assert "Manifest / snapshot ID" in report
    assert fixture["manifest"]["snapshot_id"] in report
