"""H1897: classification logic tests — lossless round-trip, review-gated
proposals, deterministic Gumilev pilot, deterministic stratified sample.

Runs on the synthetic fixture under
``tests/fixtures/community_lenses/taxonomy/`` (never on live sources), so the
invariants are pinned fast and hermetically:

- native assignments survive crosswalk application and the pilot byte-for-byte;
- every derived assignment is a pending proposal (nothing silently accepted);
- ``not_applicable`` beats every G rule (announcements can never become G1)
  and no record carries both ``not_applicable`` and a G level;
- conference ``argument_level`` is canonical and never re-proposed;
- the ruleset and the review sample are deterministic.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from community_lenses import build, classify, taxonomy

FIXTURE_PATH = (
    taxonomy.REPO_ROOT / "tests" / "fixtures" / "community_lenses" / "taxonomy"
    / "nagari_pilot.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fresh_conn() -> sqlite3.Connection:
    conn = build.create_connection(":memory:")
    build.build_schema(conn)
    build.seed_taxonomy_schemes(conn)
    fixture = _load_fixture()
    for scheme in fixture.get("_extra_schemes", []):
        conn.execute(
            """INSERT OR IGNORE INTO taxonomy_scheme
               (scheme_id, name, owner_corpus_id, is_shared_axis, version, description)
               VALUES (:scheme_id, :name, :owner_corpus_id, :is_shared_axis, :version,
                       :description)""",
            scheme,
        )
    build.populate_corpus(conn, fixture)
    return conn


def _pipeline(conn: sqlite3.Connection):
    before = classify.native_assignment_snapshot(conn)
    inserted_crosswalk = classify.apply_crosswalk_assignments(conn)
    inserted_pilot = classify.run_argument_level_pilot(conn)
    return before, inserted_crosswalk, inserted_pilot


# ---------------------------------------------------------------------------
# Round-trip: native classification is immutable evidence
# ---------------------------------------------------------------------------

def test_native_assignments_survive_pipeline_byte_for_byte():
    conn = _fresh_conn()
    before, inserted_crosswalk, inserted_pilot = _pipeline(conn)
    assert inserted_crosswalk > 0, "the fixture's native labels have crosswalk mappings"
    assert inserted_pilot > 0
    assert classify.verify_native_roundtrip(conn, before) == []
    # Count AND exact set equality (the DoD's own wording).
    after = classify.native_assignment_snapshot(conn)
    assert len(after) == len(before)
    assert set(after) == set(before)


def test_roundtrip_detects_tampering():
    conn = _fresh_conn()
    before, _, _ = _pipeline(conn)
    conn.execute(
        "UPDATE classification_assignment SET value = 'REWRITTEN' "
        "WHERE scheme_id = 'nagari_native_taxonomy' AND label_id = 'тексты/текст'"
    )
    errors = classify.verify_native_roundtrip(conn, before)
    assert errors, "a rewritten native value must fail the round-trip"


# ---------------------------------------------------------------------------
# Derived assignments are pending proposals, layered not replacing
# ---------------------------------------------------------------------------

def test_crosswalk_assignments_are_pending_additional_assertions():
    conn = _fresh_conn()
    _pipeline(conn)
    rows = conn.execute(
        "SELECT record_id, scheme_id, label_id, review_status, method_version, evidence_span "
        "FROM classification_assignment WHERE method = ?",
        (classify.CROSSWALK_METHOD,),
    ).fetchall()
    assert rows
    for record_id, scheme_id, label_id, review_status, version, evidence_span in rows:
        assert review_status == "pending", "no crosswalk-derived label may be auto-accepted"
        assert scheme_id in taxonomy.CROSSWALK_TARGET_SCHEMES
        assert version == taxonomy.CROSSWALK_VERSION
        assert evidence_span.startswith("crosswalk:"), "provenance must name the native source label"


def test_crosswalk_application_is_idempotent():
    conn = _fresh_conn()
    _pipeline(conn)
    assert classify.apply_crosswalk_assignments(conn) == 0
    assert classify.run_argument_level_pilot(conn) == 0


def test_fixture_nagari_native_label_layers_intellectual_content():
    conn = _fresh_conn()
    _pipeline(conn)
    derived = [tuple(row) for row in conn.execute(
        "SELECT label_id FROM classification_assignment "
        "WHERE record_id = 'nagari:h1897-quoted' AND scheme_id = 'intellectual_content'"
    )]
    assert ("texts_philology",) in derived
    native = [tuple(row) for row in conn.execute(
        "SELECT label_id, value FROM classification_assignment "
        "WHERE record_id = 'nagari:h1897-quoted' AND scheme_id = 'nagari_native_taxonomy'"
    )]
    assert native == [("тексты/текст", "текст")], "native label must stay untouched next to the shared one"


# ---------------------------------------------------------------------------
# Deterministic Gumilev pilot rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected_label",
    [
        ("Анонс конференции по сравнительному языкознанию", "not_applicable"),
        ("Поздравляю всех с Новым годом!", "not_applicable"),
        ("Ищу PDF грамматики Уитни, поделитесь пожалуйста", "not_applicable"),
        ("https://example.org/scan.pdf", "not_applicable"),
        ("Сравнительный синтаксис ведийского и авестийского", "G3"),
        ("История изучения санскрита в России", "G2"),
        ("Разбор шлоки из «Бхагавадгиты», глава вторая", "G1"),
        ("Вопрос по произношению", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_propose_argument_level_rules(text, expected_label):
    label, rule_id = classify.propose_argument_level(text)
    assert label == expected_label
    assert rule_id


def test_not_applicable_beats_every_g_rule():
    # An announcement that ALSO contains a G3 trigger stays not_applicable:
    # announcements must never be forced into a G level.
    label, rule_id = classify.propose_argument_level(
        "Анонс: сравнительная типология в цивилизационной перспективе"
    )
    assert label == "not_applicable"
    assert rule_id.startswith("na_")


def test_ruleset_is_deterministic():
    for text in ("Анонс доклада", "«Мегхадута» и её переводы", "просто тема"):
        assert classify.propose_argument_level(text) == classify.propose_argument_level(text)


def test_pilot_assigns_exactly_one_level_per_record_and_skips_conferences():
    conn = _fresh_conn()
    _pipeline(conn)
    rows = conn.execute(
        """SELECT r.record_id, c.corpus_id, COUNT(*) AS n
           FROM classification_assignment ca
           JOIN record r ON r.record_id = ca.record_id
           JOIN container c ON c.container_id = r.container_id
           WHERE ca.scheme_id = 'argument_level' AND ca.method = ?
           GROUP BY r.record_id""",
        (classify.PILOT_METHOD,),
    ).fetchall()
    assert rows
    for record_id, corpus_id, n in rows:
        assert n == 1, f"{record_id} carries {n} pilot levels"
        assert corpus_id in classify.PILOT_CORPORA, (
            "conference argument_level is canonical and must never be re-proposed"
        )


def test_no_not_applicable_record_has_a_g_level():
    conn = _fresh_conn()
    _pipeline(conn)
    offenders = conn.execute(
        """SELECT a.record_id FROM classification_assignment a
           JOIN classification_assignment b
             ON b.record_id = a.record_id AND b.scheme_id = 'argument_level'
           WHERE a.scheme_id = 'argument_level' AND a.label_id = 'not_applicable'
             AND b.label_id IN ('G1', 'G2', 'G3')"""
    ).fetchall()
    assert offenders == []


def test_pilot_proposals_are_pending_with_ruleset_provenance():
    conn = _fresh_conn()
    _pipeline(conn)
    rows = conn.execute(
        "SELECT review_status, method_version, value FROM classification_assignment "
        "WHERE method = ?",
        (classify.PILOT_METHOD,),
    ).fetchall()
    assert rows
    for review_status, method_version, rule_id in rows:
        assert review_status == "pending", "no pilot proposal may be silently accepted"
        assert method_version == classify.PILOT_RULESET_VERSION
        assert rule_id, "every proposal must carry the matched rule id"


# ---------------------------------------------------------------------------
# Deterministic stratified review sample
# ---------------------------------------------------------------------------

def test_review_sample_is_deterministic_and_complete():
    conn = _fresh_conn()
    _pipeline(conn)
    sample_a = classify.build_review_sample(conn)
    sample_b = classify.build_review_sample(_pipeline_conn())
    assert sample_a == sample_b

    proposed_g3 = {
        row[0] for row in conn.execute(
            "SELECT record_id FROM classification_assignment "
            "WHERE scheme_id = 'argument_level' AND label_id = 'G3' AND method = ?",
            (classify.PILOT_METHOD,),
        )
    }
    sampled = {row["record_id"] for row in sample_a}
    assert proposed_g3 <= sampled, "every proposed G3 must be in the review sample"

    for row in sample_a:
        for col in ("review_intellectual_content", "review_community_function",
                    "review_argument_applicability", "review_argument_level",
                    "reviewer", "review_decision"):
            assert row[col] == "", "review columns must be empty for the human reviewer"
        assert row["stratum"]


def _pipeline_conn() -> sqlite3.Connection:
    conn = _fresh_conn()
    _pipeline(conn)
    return conn


def test_period_bins_follow_architecture_contract():
    assert classify.period_bin("1985-05-01") == "pre-1990"
    assert classify.period_bin("1990-01-01") == "1990-2004"
    assert classify.period_bin("2010-12-31") == "2005-2010"
    assert classify.period_bin("2017-06-15") == "2011-2017"
    assert classify.period_bin("2025-01-01") == "2018-2025"
    assert classify.period_bin("2026-01-01") == "2026-partial"
    assert classify.period_bin(None) == "undated"
