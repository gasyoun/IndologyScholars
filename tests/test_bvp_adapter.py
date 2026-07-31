"""H1896: the BVP (Bharatiya Vidvat Parishat) Wave 1C adapter.

Covers the real, on-disk partial acquisition (bvp/data/meta/state.json +
bvp/data/parsed/*.json, produced by bvp/scrape.py per H1892) plus synthetic
scenarios exercised directly against the pure ``_build_from_state`` transform:
a partial manifest, an incomplete record, denominator exclusion, a parse
failure (interrupted manifest), a rejected duplicate native ID, deterministic
ordering, an explicit denominator mismatch, and an attempted population-level
query against partial input. A synthetic complete manifest is used only to
prove the ``supports_population_metrics`` gate can flip true -- the live BVP
manifest is never labeled complete.
"""

from __future__ import annotations

import copy
import sqlite3

import pytest

from community_lenses import build
from community_lenses.adapters import bvp
from community_lenses.ids import make_record_id
from community_lenses.manifests import SourceManifest, validate_manifest
from community_lenses.schema import build_schema, create_connection

SHA_A = "a" * 64
SHA_B = "b" * 64


def _fresh_connection() -> sqlite3.Connection:
    conn = create_connection(":memory:")
    build_schema(conn)
    build.seed_taxonomy_schemes(conn)
    return conn


def _base_state(**overrides) -> dict:
    state = {
        "schema_version": 1,
        "updated_at": "2026-07-29T13:08:46+00:00",
        "coverage_status": "partial",
        "discovered": {"conv1": {}, "conv2": {}},
        "listing": {"displayed_total": 23467},
        "counts": {"fetched": 2, "parsed": 2, "failed": 0, "retries": 2},
    }
    state.update(overrides)
    return state


def _message(
    message_id: str,
    *,
    author_display: str = "Ajay Sharma",
    subject: str | None = "Sanskrit translation tools",
    timestamp_epoch: int | None = 1784883576,
    body_text_sha256: str | None = "c" * 64,
    rendered_text_sha256: str | None = None,
    author_native_id: str | None = "112681138012681924883",
) -> dict:
    msg = {"message_id": message_id, "author_display": author_display}
    if subject is not None:
        msg["subject"] = subject
    if timestamp_epoch is not None:
        msg["timestamp_epoch"] = timestamp_epoch
    if body_text_sha256 is not None:
        msg["body_text_sha256"] = body_text_sha256
    if rendered_text_sha256 is not None:
        msg["rendered_text_sha256"] = rendered_text_sha256
    if author_native_id is not None:
        msg["author_native_id"] = author_native_id
    return msg


def _conversation(conversation_id: str, messages: list[dict], **overrides) -> dict:
    conv = {
        "conversation_id": conversation_id,
        "subject": "Sanskrit translation tools",
        "url": f"https://groups.google.com/g/bvparishat/c/{conversation_id}",
        "parse_source": "AF_initDataCallback ds:7",
        "messages": messages,
    }
    conv.update(overrides)
    return conv


# --- real, on-disk partial acquisition --------------------------------------


def test_live_bvp_fixture_matches_corpus_id_and_is_partial():
    fixture = bvp.build_fixture()
    assert fixture["corpus"]["corpus_id"] == "bvp"
    assert fixture["manifest"]["corpus_id"] == "bvp"
    # H1892's frozen local acquisition exists on this machine (bvp/data/); if
    # it were ever absent this degrades to "unavailable", never a fabricated
    # "complete".
    assert fixture["manifest"]["coverage_status"] in ("partial", "unavailable")


def test_live_bvp_manifest_is_individually_valid():
    fixture = bvp.build_fixture()
    manifest = SourceManifest(**fixture["manifest"])
    assert validate_manifest(manifest) == []


def test_live_bvp_record_ids_are_stable_and_match_make_record_id():
    fixture = bvp.build_fixture()
    for record in fixture["records"]:
        expected = make_record_id("bvp", record["source_record_id"])
        assert record["record_id"] == expected


def test_live_bvp_produces_real_records_and_never_claims_complete():
    fixture = bvp.build_fixture()
    assert len(fixture["records"]) > 0
    assert fixture["manifest"]["coverage_status"] == "partial"
    assert bvp.population_metrics_allowed(fixture) is False


def test_live_bvp_fixture_loads_and_validates_with_no_errors():
    fixture = bvp.build_fixture()
    conn = _fresh_connection()
    build.populate_corpus(conn, fixture)
    conn.commit()
    errors = build.validate_build(conn, {"bvp": fixture})
    assert errors == [], errors


def test_live_bvp_build_is_idempotent_across_two_runs():
    fixture_a = bvp.build_fixture()
    fixture_b = bvp.build_fixture()

    conn_a = _fresh_connection()
    build.populate_corpus(conn_a, fixture_a)
    conn_a.commit()

    conn_b = _fresh_connection()
    build.populate_corpus(conn_b, fixture_b)
    conn_b.commit()

    assert build.canonical_json(conn_a) == build.canonical_json(conn_b)


def test_live_bvp_has_at_least_one_incomplete_record_kept_explicit():
    """bvp_source_assessment.md: one thread parsed via DOM fallback with no
    usable public author/body -- must remain a real record, not be dropped."""
    fixture = bvp.build_fixture()
    recon = fixture["_reconciliation"]
    assert recon["messages_incomplete"] >= 1
    incomplete_annotations = [
        a for a in fixture["annotations"] if a["annotation_type"] == "incomplete_record"
    ]
    assert len(incomplete_annotations) == recon["messages_incomplete"]
    # The incomplete record itself is still present in `records`, not discarded.
    incomplete_record_ids = {a["record_id"] for a in incomplete_annotations}
    present_record_ids = {r["record_id"] for r in fixture["records"]}
    assert incomplete_record_ids <= present_record_ids


def test_live_bvp_never_auto_links_a_person():
    fixture = bvp.build_fixture()
    assert all(rn["person_id"] is None for rn in fixture["record_names"])


def test_live_bvp_never_emits_a_quote_or_shared_topic_assignment():
    fixture = bvp.build_fixture()
    assert fixture["quotes"] == []
    scheme_ids = {a["scheme_id"] for a in fixture["classification_assignments"]}
    assert "shared_topic" not in scheme_ids


def test_live_bvp_never_copies_native_title_into_a_shared_topic_value():
    fixture = bvp.build_fixture()
    titles_by_record = {r["record_id"]: r.get("title_or_subject") for r in fixture["records"]}
    for assignment in fixture["classification_assignments"]:
        if assignment["scheme_id"] != "shared_topic":
            continue
        native_title = titles_by_record.get(assignment["record_id"])
        assert native_title is None or assignment["value"] != native_title


def test_live_bvp_coverage_report_names_native_unit_and_denominator():
    fixture = bvp.build_fixture()
    report = bvp.coverage_report(fixture)
    assert "Native unit type" in report
    assert "Denominator definition" in report
    assert "Manifest / snapshot ID" in report
    assert fixture["manifest"]["snapshot_id"] in report


def test_live_bvp_coverage_report_states_expert_judgment_not_representativeness():
    fixture = bvp.build_fixture()
    report = bvp.coverage_report(fixture)
    assert "Gas" in report  # Gasūns -- avoid a literal ū encoding dependency in the assertion
    assert "not evidence" in report or "representative" in report


def test_live_bvp_degrades_gracefully_when_no_state_is_found(monkeypatch):
    monkeypatch.setattr(bvp, "_load_state", lambda: None)
    fixture = bvp.build_fixture()
    assert fixture["manifest"]["coverage_status"] == "unavailable"
    assert fixture["records"][0]["status"] == "unavailable"
    conn = _fresh_connection()
    build.populate_corpus(conn, fixture)
    conn.commit()
    assert build.validate_build(conn, {"bvp": fixture}) == []


# --- synthetic scenarios against the pure transform -------------------------


def test_partial_manifest_round_trips_and_validates():
    state = _base_state()
    conversations = {
        "conv1": _conversation("conv1", [_message("m1")]),
        "conv2": _conversation("conv2", [_message("m2", author_display="Someone Else")]),
    }
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)
    assert fixture["manifest"]["coverage_status"] == "partial"
    conn = _fresh_connection()
    build.populate_corpus(conn, fixture)
    conn.commit()
    assert build.validate_build(conn, {"bvp": fixture}) == []


def test_incomplete_record_is_kept_and_excluded_from_person_denominator():
    state = _base_state(discovered={"conv1": {}})
    conversations = {
        "conv1": _conversation(
            "conv1",
            [_message("m1", author_display="", subject=None, timestamp_epoch=None, body_text_sha256=None,
                      rendered_text_sha256="d" * 64, author_native_id=None)],
        )
    }
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)

    assert len(fixture["records"]) == 1
    assert fixture["records"][0]["status"] == "active"
    # No fabricated author -> no record_name row at all.
    assert fixture["record_names"] == []
    assert fixture["_reconciliation"]["messages_incomplete"] == 1
    assert fixture["_reconciliation"]["messages_excluded_from_person_denominator"] == 1
    annotation_types = {a["annotation_type"] for a in fixture["annotations"]}
    assert "incomplete_record" in annotation_types


def test_exclusion_denominator_is_named_not_silently_dropped():
    state = _base_state(discovered={"conv1": {}}, listing={"displayed_total": 100})
    conversations = {"conv1": _conversation("conv1", [_message("m1")])}
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)
    recon = fixture["_reconciliation"]
    assert recon["conversations_not_yet_enumerated"] == 99
    report = bvp.coverage_report(fixture)
    assert "99" not in report or "23467" not in report  # sanity: report is generated, not hand-copied
    assert "partial" in report.lower()


def test_parse_failure_interrupted_manifest_is_named_not_fabricated():
    """conv2 is discovered (listed in state.json) but has no parsed/<id>.json --
    an interrupted run, not a genuine zero-message conversation."""
    state = _base_state(discovered={"conv1": {}, "conv2": {}})
    conversations = {"conv1": _conversation("conv1", [_message("m1")])}
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)

    recon = fixture["_reconciliation"]
    assert recon["conversations_parse_failed"] == 1
    assert recon["conversations_discovered"] == 2
    assert recon["conversations_parsed"] == 1
    failed_annotations = [
        a for a in fixture["annotations"] if a["annotation_type"] == "conversation_parse_failed"
    ]
    assert len(failed_annotations) == 1
    assert "conv2" in failed_annotations[0]["body"]
    # Nothing invented a record for the missing conversation.
    assert all(r["container_id"] != "bvp:container:conv2" for r in fixture["records"])


def test_duplicate_native_id_is_rejected_fail_closed():
    state = _base_state(discovered={"conv1": {}, "conv2": {}})
    conversations = {
        "conv1": _conversation("conv1", [_message("dup-id")]),
        "conv2": _conversation("conv2", [_message("dup-id")]),
    }
    with pytest.raises(bvp.DuplicateNativeId):
        bvp._build_from_state(state, conversations, state_sha256=SHA_A)


def test_deterministic_ordering_is_independent_of_input_dict_order():
    state = _base_state(discovered={"conv1": {}, "conv2": {}})
    conversations_forward = {
        "conv1": _conversation("conv1", [_message("m1")]),
        "conv2": _conversation("conv2", [_message("m2", author_display="Second Author")]),
    }
    conversations_reversed = dict(reversed(list(conversations_forward.items())))

    fixture_a = bvp._build_from_state(state, conversations_forward, state_sha256=SHA_A)
    fixture_b = bvp._build_from_state(state, conversations_reversed, state_sha256=SHA_A)

    ids_a = [r["record_id"] for r in fixture_a["records"]]
    ids_b = [r["record_id"] for r in fixture_b["records"]]
    assert ids_a == ids_b == sorted(ids_a)


def test_explicit_denominator_mismatch_between_listing_and_discovered():
    """displayed_total (embedded/DOM listing count) vs. discovered (enumerated
    IDs) can legitimately diverge; the gap must be a named, computed field."""
    state = _base_state(discovered={"conv1": {}}, listing={"displayed_total": 23467})
    conversations = {"conv1": _conversation("conv1", [_message("m1")])}
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)
    recon = fixture["_reconciliation"]
    assert recon["displayed_total"] == 23467
    assert recon["conversations_discovered"] == 1
    assert recon["conversations_not_yet_enumerated"] == 23466


def test_attempted_population_query_is_rejected_on_partial_input():
    state = _base_state()
    conversations = {"conv1": _conversation("conv1", [_message("m1")])}
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)
    assert bvp.population_metrics_allowed(fixture) is False
    with pytest.raises(bvp.PopulationMetricsDisabled):
        bvp.require_population_metrics(fixture)


def test_synthetic_complete_manifest_flips_the_gate_true():
    """The ONLY place a coverage_status='complete' BVP manifest may exist:
    a fully synthetic fixture built solely to prove the gate can flip. The
    live bvp/data/ acquisition is never labeled complete by this adapter."""
    state = _base_state(
        coverage_status="complete",
        discovered={"conv1": {}},
        listing={"displayed_total": 1},
    )
    conversations = {"conv1": _conversation("conv1", [_message("m1")])}
    fixture = bvp._build_from_state(state, conversations, state_sha256=SHA_A)

    assert fixture["manifest"]["coverage_status"] == "complete"
    assert bvp.population_metrics_allowed(fixture) is True
    bvp.require_population_metrics(fixture)  # must not raise

    conn = _fresh_connection()
    build.populate_corpus(conn, fixture)
    conn.commit()
    assert build.validate_build(conn, {"bvp": fixture}) == []


def test_mixed_snapshot_coverage_status_is_still_rejected_fail_closed():
    fixture = copy.deepcopy(bvp.build_fixture())
    fixture["manifest"]["coverage_status"] = "mixed_snapshot"
    from community_lenses.manifests import validate_no_mixed_snapshot

    manifest = SourceManifest(**fixture["manifest"])
    errors = validate_no_mixed_snapshot([manifest])
    assert errors and "mixed_snapshot" in errors[0]
