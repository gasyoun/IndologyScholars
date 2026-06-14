"""Tests for the non-participant indologist registry (docs/roster-merge-design.md).

Guards the curated registry CSV and the roster->corpus merge invariants:
  - registry schema (status vocabulary; verified rows must cite a source),
  - registry_id is unique, RIND_-prefixed, deterministic, and never collides
    with the conference person_id (PERS_*) namespace,
  - stat isolation: registry people are genuinely non-participants and the
    conference scholar count is unaffected by the registry.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scratch"))
sys.path.insert(0, str(ROOT / "tools"))

import crossref_nonparticipants as cx          # noqa: E402
import build_non_participant_registry as reg    # noqa: E402

REGISTRY_CSV = ROOT / "curation" / "non_participant_indologists.csv"
LINKS_CSV = ROOT / "analytics_output" / "roster_participant_links.csv"
SUMMARY = ROOT / "site_data_summary.json"

EXPECTED_COLUMNS = [
    "registry_id", "full_name_ru", "full_name_en", "birth_year", "death_year",
    "field", "role", "affiliation", "alma_mater", "degree",
    "wikidata_qid", "orcid", "source_url", "status", "note",
]


def _rows():
    with REGISTRY_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ── schema ───────────────────────────────────────────────────────────

def test_registry_exists_and_columns():
    assert REGISTRY_CSV.exists()
    with REGISTRY_CSV.open(encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    assert header == EXPECTED_COLUMNS


def test_status_vocabulary():
    for r in _rows():
        assert r["status"] in {"verified", "candidate"}, r["status"]


def test_verified_requires_source():
    # the anti-fabrication rule: a published 'verified' row must cite a source
    offenders = [r["registry_id"] for r in _rows()
                 if r["status"] == "verified" and not r["source_url"].strip()]
    assert offenders == [], offenders


def test_every_row_has_a_name():
    for r in _rows():
        assert r["full_name_ru"].strip()


# ── registry_id ──────────────────────────────────────────────────────

def test_registry_id_unique_and_prefixed():
    ids = [r["registry_id"] for r in _rows()]
    assert len(ids) == len(set(ids)), "duplicate registry_id"
    assert all(i.startswith("RIND_") for i in ids)


def test_registry_id_disjoint_from_person_ids():
    # registry people must never borrow the conference PERS_* namespace
    ids = [r["registry_id"] for r in _rows()]
    assert not any(i.startswith("PERS_") for i in ids)


def test_registry_id_is_deterministic():
    p = {"surname": "Алаев", "given_name": "Леонид Борисович", "birth_year": 1932}
    assert reg.registry_id_for(p) == reg.registry_id_for(dict(p))
    # stable hash, independent of unrelated fields
    p2 = dict(p, role="историк", workplace="ИВ РАН")
    assert reg.registry_id_for(p) == reg.registry_id_for(p2)


def test_no_duplicate_names_in_registry():
    """Phase-5 idempotency guard: filling a birth year changes registry_id
    (birth_year is in the hash), so the merge must also dedupe by name. A
    duplicate normalized name means an enrichment re-run would re-append people."""
    names = [cx.normalize(r["full_name_ru"]) for r in _rows()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate names in registry: {dupes}"


# ── stat isolation ───────────────────────────────────────────────────

def test_registry_people_are_non_participants():
    """Every registry person must fail the participation matcher — otherwise a
    speaker leaked into the non-participant list."""
    conf = cx.load_conf_data()
    leaked = []
    for r in _rows():
        parts = r["full_name_ru"].split()
        if len(parts) < 2:
            continue
        person = {"surname": parts[0], "given_name": " ".join(parts[1:]),
                  "full_name": r["full_name_ru"]}
        is_participant, _ = cx.classify_participation(person, conf)
        if is_participant:
            leaked.append(r["full_name_ru"])
    assert leaked == [], f"participants leaked into registry: {leaked}"


def test_conference_scholar_count_unchanged():
    """The registry is parallel data; it must not change conference headline
    numbers."""
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))["summary"]
    # 268 after the 2026-06-14 Phase-1 dedup merged three duplicate person
    # records (typo'd initials) into their canonical persons via person_aliases.csv.
    assert summary["total_scholars"] == 268


# ── participant links ────────────────────────────────────────────────

def test_participant_links_reference_real_scholars():
    if not LINKS_CSV.exists():
        return
    conf_ids = {c.get("id") for c in cx.load_conf_data()}
    with LINKS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pid = row["matched_person_id"]
            assert pid in conf_ids, f"link points to unknown person_id {pid}"
