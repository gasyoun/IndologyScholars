"""Regression tests for the historical prosopography layer (H484, Phase 2).

Decision A1, variant A: historical indologists who never presented live in the single
``person`` spine, discriminated by ``person_kind='historical'``. These tests pin the
invariants that keep that layer from corrupting the cited conference statistics:

* the count of "speakers" is a count of people with >=1 talk -- adding historical
  figures must not move it off 268 (task 1: the retarget is zero-delta by construction);
* every historical figure has a non-empty ``death_year`` (roadmap risk P3) and a source;
* historical figures never leak into ``presentation_person`` or the ``scholars`` payload;
* their profile pages render in the memorial format without a talk to their name.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "conferences.db"
SITE_DATA = ROOT / "site_data.json"

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="conferences.db not built")


@pytest.fixture(scope="module")
def conn():
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def site_data():
    if not SITE_DATA.exists():
        pytest.skip("site_data.json not generated")
    return json.loads(SITE_DATA.read_text(encoding="utf-8"))


def test_person_kind_column_exists(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(person)")}
    assert "person_kind" in cols


def test_kinds_partition_the_spine(conn):
    kinds = dict(conn.execute("SELECT person_kind, COUNT(*) FROM person GROUP BY person_kind"))
    assert set(kinds) == {"conference_participant", "historical"}
    assert kinds["historical"] >= 26


def test_speaker_count_is_talk_derived_not_person_count(conn):
    """Task 1's invariant: the cited number counts people with a talk, not rows in person.

    Historical figures inflate COUNT(*) FROM person but never presented, so the two must
    now differ by exactly the historical headcount -- proving the count is talk-derived.
    """
    total_person = conn.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    with_talk = conn.execute(
        "SELECT COUNT(DISTINCT person_id) FROM presentation_person"
    ).fetchone()[0]
    historical = conn.execute(
        "SELECT COUNT(*) FROM person WHERE person_kind = 'historical'"
    ).fetchone()[0]
    assert with_talk == total_person - historical
    assert with_talk == 268


def test_historical_figures_never_presented(conn):
    leaked = conn.execute(
        "SELECT COUNT(*) FROM presentation_person pp "
        "JOIN person p ON p.person_id = pp.person_id "
        "WHERE p.person_kind = 'historical'"
    ).fetchone()[0]
    assert leaked == 0


def test_every_historical_figure_has_a_death_year(conn):
    missing = conn.execute(
        "SELECT display_name FROM person WHERE person_kind = 'historical' AND death_year IS NULL"
    ).fetchall()
    assert missing == [], f"historical figures without a death_year (roadmap P3): {missing}"


def test_every_historical_figure_has_a_sourced_assertion(conn):
    """Each historical figure needs >=1 data_assertion carrying a source_url."""
    orphans = conn.execute(
        "SELECT p.display_name FROM person p "
        "WHERE p.person_kind = 'historical' AND NOT EXISTS ("
        "  SELECT 1 FROM data_assertion a "
        "  WHERE a.entity_id = p.person_id AND a.source_url IS NOT NULL)"
    ).fetchall()
    assert orphans == [], f"historical figures with no sourced assertion: {orphans}"


def test_historical_figures_carry_a_discipline(conn):
    """No memorial page may fall through to the `unattested` sentinel."""
    unclassified = conn.execute(
        "SELECT p.display_name FROM person p WHERE p.person_kind = 'historical' AND NOT EXISTS ("
        "  SELECT 1 FROM person_discipline d "
        "  WHERE d.person_id = p.person_id AND d.discipline_id != 'unattested')"
    ).fetchall()
    assert unclassified == []


def test_site_data_keeps_268_and_lists_historical_apart(site_data):
    assert site_data["summary"]["total_scholars"] == 268
    assert len(site_data["scholars"]) == 268
    historical = site_data.get("historical_scholars", [])
    assert len(historical) >= 26
    participant_ids = {s["id"] for s in site_data["scholars"]}
    assert participant_ids.isdisjoint({s["id"] for s in historical})
    for s in historical:
        assert s["death_year"], f"{s['full_name_ru']} has no death_year in site_data"
        assert s["total_talks"] == 0


def test_zero_talk_historical_profile_renders_as_memorial(site_data):
    import generate_scholars_pages as gsp

    historical = site_data.get("historical_scholars", [])
    if not historical:
        pytest.skip("no historical scholars in site_data")
    gsp.initialize_presentation_slugs(historical)
    meso_items, meso_by = gsp.load_meso_context()
    authority = gsp.load_authority_ids()
    for s in historical:
        related = gsp.related_scholars(s, historical, meso_by, meso_items)
        html = gsp.render_profile(s, related, authority, meso_by, meso_items)
        assert gsp.is_memorial(s)
        assert "memorial-block" in html
