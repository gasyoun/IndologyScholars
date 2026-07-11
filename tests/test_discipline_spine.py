"""Regression tests for the prosopographical spine (H473, Phase 1).

These pin the invariants that keep the "Indology in Russia" / "Sanskritology in
Russia" sections honest:

* every person carries at least one discipline, so the facet pages are total;
* the ``unattested`` sentinel is never mixed with a real discipline, and never
  silently stands in for one;
* an empty ``death_year`` produces a registry card, never a memorial essay
  (roadmap risk P3: empty means UNKNOWN, not "alive");
* the curated CSVs only reference discipline codes that actually exist;
* re-running the build does not duplicate the H473 ``data_assertion`` rows nor
  disturb the 803 curated ones.
"""
import csv
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "conferences.db"
CURATOR_ID = "h473_discipline_tagger"

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="conferences.db not built")


@pytest.fixture(scope="module")
def conn():
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


def _rows(name):
    with (ROOT / "curation" / name).open(encoding="utf-8-sig", newline="") as handle:
        return [r for r in csv.DictReader(handle) if any((v or "").strip() for v in r.values())]


def test_every_person_has_at_least_one_discipline(conn):
    persons = conn.execute("SELECT count(*) FROM person").fetchone()[0]
    tagged = conn.execute("SELECT count(DISTINCT person_id) FROM person_discipline").fetchone()[0]
    assert persons == tagged, f"{persons - tagged} person(s) carry no discipline"


def test_unattested_never_co_occurs_with_a_real_discipline(conn):
    offenders = conn.execute(
        """
        SELECT person_id FROM person_discipline WHERE discipline_id = 'unattested'
          AND person_id IN (
            SELECT person_id FROM person_discipline WHERE discipline_id != 'unattested'
          )
        """
    ).fetchall()
    assert offenders == [], f"unattested mixed with real disciplines: {offenders}"


def test_unattested_confidence_is_zero(conn):
    confidences = [
        row[0]
        for row in conn.execute(
            "SELECT confidence FROM person_discipline WHERE discipline_id = 'unattested'"
        )
    ]
    assert all(c == 0.0 for c in confidences), confidences


def test_decision_d1_ratified_all_four_proposed_codes(conn):
    """D1 (10-07-2026) ratified literature/linguistics/ethnography/history_of_indology.

    Every subject discipline is now `core` and hangs under the indology umbrella;
    only the `unattested` sentinel sits outside. No `proposed` code may survive
    without a fresh ruling.
    """
    rows = dict(conn.execute("SELECT discipline_id, status FROM discipline"))
    for code in ("literature", "linguistics", "ethnography", "history_of_indology"):
        assert rows[code] == "core", f"{code} should be ratified by D1, got {rows[code]!r}"
    assert "proposed" not in rows.values(), (
        f"unratified codes present: {[c for c, s in rows.items() if s == 'proposed']}"
    )
    assert rows["unattested"] == "sentinel"


def test_unattested_is_not_a_child_of_indology(conn):
    parent = conn.execute(
        "SELECT parent_discipline_id FROM discipline WHERE discipline_id = 'unattested'"
    ).fetchone()[0]
    assert parent is None, "the sentinel must not hang under the indology umbrella"


def test_taxonomy_is_rooted_and_acyclic(conn):
    rows = dict(conn.execute("SELECT discipline_id, parent_discipline_id FROM discipline"))
    assert rows["indology"] is None
    for code, parent in rows.items():
        assert parent is None or parent in rows, f"{code} points at unknown parent {parent}"
        seen, cursor = set(), code
        while rows.get(cursor):
            cursor = rows[cursor]
            assert cursor not in seen, f"cycle through {code}"
            seen.add(cursor)


def test_crosswalk_only_uses_known_discipline_codes(conn):
    known = {r[0] for r in conn.execute("SELECT discipline_id FROM discipline")}
    for row in _rows("meso_discipline_crosswalk.csv"):
        code = (row["discipline_code"] or "").strip()
        if code:  # blank = deliberate no-map
            assert code in known, f"crosswalk references unknown discipline {code!r}"


def test_manual_assignments_only_use_known_codes_and_keys(conn):
    known = {r[0] for r in conn.execute("SELECT discipline_id FROM discipline")}
    keys = {r[0] for r in conn.execute("SELECT normalized_key FROM person")}
    for row in _rows("person_disciplines.csv"):
        assert row["discipline_code"].strip() in known, row["discipline_code"]
        assert row["normalized_key"].strip() in keys, row["normalized_key"]
        assert 0.0 <= float(row["confidence"]) <= 1.0


def test_confidence_within_bounds(conn):
    bad = conn.execute(
        "SELECT count(*) FROM person_discipline WHERE confidence < 0.0 OR confidence > 1.0"
    ).fetchone()[0]
    assert bad == 0


def test_h473_assertions_match_person_discipline_rows_exactly(conn):
    """Idempotency: a rebuild replaces, never appends."""
    pd_rows = conn.execute("SELECT count(*) FROM person_discipline").fetchone()[0]
    assertions = conn.execute(
        "SELECT count(*) FROM data_assertion WHERE curator_id = ?", (CURATOR_ID,)
    ).fetchone()[0]
    assert pd_rows == assertions


def test_curated_assertions_survive_the_rebuild(conn):
    """The 803 irreproducible provenance rows must never be dropped.

    These live ONLY in the committed conferences.db (ORCID / Wikidata / birth years) and
    are owned by three curators. The invariant is pinned to those specific curators, not to
    ``!= h473_discipline_tagger``: later derived layers add their own curated rows (e.g. the
    H484 historical seeder), which must not mask a regression in the original 803.
    """
    original = conn.execute(
        "SELECT count(*) FROM data_assertion WHERE curator_id IN "
        "('system_normalizer', 'scraper', 'MG')"
    ).fetchone()[0]
    assert original == 803


def test_relation_types_are_constrained(conn):
    types = {r[0] for r in conn.execute("SELECT DISTINCT relation_type FROM relation")}
    assert types <= {"teacher", "student", "successor"}


def test_memorial_split_follows_death_year():
    """Registry pages must never print a birth-death span; memorials must."""
    import generate_scholars_pages as gsp

    assert gsp.is_memorial({"death_year": 2020}) is True
    assert gsp.is_memorial({"death_year": None}) is False
    assert gsp.is_memorial({}) is False
    # An unknown death year yields a registry card and no memorial block.
    assert gsp.build_memorial_html({"death_year": None, "name": "X"}) == ""
    assert "Место в традиции" in gsp.build_memorial_html({"death_year": 1999, "name": "X"})
    assert gsp.build_registry_note_html({"death_year": 1999}) == ""
    assert "Карточка-реестр" in gsp.build_registry_note_html({"death_year": None})


def test_lifespan_never_invents_dates():
    import generate_scholars_pages as gsp

    assert gsp.format_lifespan({"birth_year": 1941, "death_year": 2020}) == " (1941–2020)"
    assert gsp.format_lifespan({"birth_year": 1941, "death_year": None}) == " (род. 1941)"
    assert gsp.format_lifespan({"birth_year": None, "death_year": None}) == ""
    # A death year with no birth year must not print a bare dangling span.
    assert gsp.format_lifespan({"birth_year": None, "death_year": 2020}) == ""


def test_tentative_disciplines_are_marked_in_chips():
    import generate_scholars_pages as gsp

    confident = gsp.discipline_chips(
        {"disciplines": [{"code": "sanskritology", "label_ru": "Санскритология", "confidence": 0.95}]}
    )
    assert "(?)" not in confident

    tentative = gsp.discipline_chips(
        {"disciplines": [{"code": "sanskritology", "label_ru": "Санскритология", "confidence": 0.5}]}
    )
    assert "(?)" in tentative and "chip-tentative" in tentative

    sentinel = gsp.discipline_chips(
        {"disciplines": [{"code": "unattested", "label_ru": "Дисциплина не установлена", "confidence": 0.0}]}
    )
    assert "chip-unattested" in sentinel and "(?)" not in sentinel
