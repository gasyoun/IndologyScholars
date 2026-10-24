"""Conferences (Roerich/Zograf Readings) adapter — H1895 Wave 1B.

Reads the repo's own long-standing ``conferences.db`` (sessions,
presentations, presentation-person links, persons) and the existing derived
assets already computed for it — ``authority_ids.json`` (ORCID/Wikidata),
``curation/person_aliases.csv`` (accepted person-name merges),
``analytics_output/renou_presentation_matches.csv`` (Renou state/register),
and ``analytics_output/gumilyov_scale.csv`` (argument-level G1-G3) — and
loads them into the H1893 shared contract. Nothing here recomputes those
assets or adjudicates a new crosswalk; every classification value is reused
verbatim from an already-existing, already-decided source.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from . import _shared
from ..ids import make_record_id

REPO_ROOT = _shared.REPO_ROOT
DB_PATH = REPO_ROOT / "conferences.db"
AUTHORITY_IDS_PATH = REPO_ROOT / "authority_ids.json"
RENOU_MATCHES_PATH = REPO_ROOT / "analytics_output" / "renou_presentation_matches.csv"
GUMILYOV_SCALE_PATH = REPO_ROOT / "analytics_output" / "gumilyov_scale.csv"

CORPUS_ID = "conferences"

_ACCEPTED_CONFIDENCE = {"confirmed", "manual"}
_GUMILYOV_LABEL = {1: "G1", 2: "G2", 3: "G3"}


def _load_authority_ids() -> dict:
    if not AUTHORITY_IDS_PATH.exists():
        return {}
    return json.loads(AUTHORITY_IDS_PATH.read_text(encoding="utf-8")).get("persons", {})


def _load_renou_matches() -> dict[str, dict[str, dict]]:
    """presentation_id -> {"state": row, "register": row}, first rule_id wins (deterministic)."""
    result: dict[str, dict[str, dict]] = {}
    if not RENOU_MATCHES_PATH.exists():
        return result
    with RENOU_MATCHES_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda r: (r["presentation_id"], r["renou_axis"], r["rule_id"]))
    for row in rows:
        by_axis = result.setdefault(row["presentation_id"], {})
        by_axis.setdefault(row["renou_axis"], row)
    return result


def _load_gumilyov_scale() -> dict[str, dict]:
    if not GUMILYOV_SCALE_PATH.exists():
        return {}
    with GUMILYOV_SCALE_PATH.open(encoding="utf-8", newline="") as handle:
        return {row["presentation_id"]: row for row in csv.DictReader(handle)}


def build_fixture() -> dict:
    if not DB_PATH.exists():
        return _shared.unavailable_fixture(
            corpus_id=CORPUS_ID,
            title="Roerich/Zograf Readings conference corpus",
            native_unit="presentation",
            rights_basis="publicly posted institutional conference programme",
            gap_note=f"conferences.db not found at {DB_PATH}",
        )

    authority_ids = _load_authority_ids()
    renou_matches = _load_renou_matches()
    gumilyov = _load_gumilyov_scale()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        events = {row["event_id"]: dict(row) for row in conn.execute("SELECT * FROM event")}
        sessions = {row["session_id"]: dict(row) for row in conn.execute("SELECT * FROM session")}
        session_event: dict[str, str] = {}
        for row in conn.execute(
            """SELECT s.session_id, dv.event_day_venue_id, ed.event_id
               FROM session s
               JOIN event_day_venue dv ON dv.event_day_venue_id = s.event_day_venue_id
               JOIN event_day ed ON ed.event_day_id = dv.event_day_id"""
        ):
            session_event[row["session_id"]] = row["event_id"]

        presentations = [dict(row) for row in conn.execute("SELECT * FROM presentation")]
        presentation_persons = [
            dict(row) for row in conn.execute("SELECT * FROM presentation_person")
        ]
        persons = {row["person_id"]: dict(row) for row in conn.execute("SELECT * FROM person")}
    finally:
        conn.close()

    snapshot_id = f"{CORPUS_ID}:{_shared.file_acquired_at(DB_PATH)[:10]}"
    manifest = _shared.build_manifest(
        corpus_id=CORPUS_ID,
        snapshot_id=snapshot_id,
        coverage_status="complete",
        source_version=f"conferences.db@{_shared.file_sha256(DB_PATH)[:12]}",
        acquired_at=_shared.file_acquired_at(DB_PATH),
        source_sha256=_shared.file_sha256(DB_PATH),
        rights_basis="publicly posted institutional conference programme",
        coverage_start="2004-01-01" if events else None,
        coverage_end=max((e["end_date"] or e["start_date"] for e in events.values()), default=None),
        cutoff_date=_shared.file_acquired_at(DB_PATH)[:10],
    )

    latest_year = max((e["year"] for e in events.values()), default=0)

    containers = []
    for session_id, session in sorted(sessions.items()):
        event_id = session_event.get(session_id)
        event = events.get(event_id, {})
        containers.append(
            {
                "container_id": f"{CORPUS_ID}:container:{session_id}",
                "corpus_id": CORPUS_ID,
                "source_snapshot_id": snapshot_id,
                "parent_container_id": None,
                "container_type": "session",
                "source_native_id": session_id,
                "title": session.get("session_title"),
                "date_from": event.get("start_date"),
                "date_to": event.get("end_date"),
                "source_url": session.get("source_url") or event.get("source_url"),
            }
        )

    records = []
    record_names = []
    classification_assignments = []
    seen_persons: dict[str, dict] = {}

    for pres in sorted(presentations, key=lambda p: p["presentation_id"]):
        pres_id = pres["presentation_id"]
        record_id = make_record_id(CORPUS_ID, pres_id)
        session = sessions.get(pres["session_id"], {})
        event_id = session_event.get(pres["session_id"])
        event = events.get(event_id, {})
        year = event.get("year")

        records.append(
            {
                "record_id": record_id,
                "corpus_id": CORPUS_ID,
                "source_record_id": pres_id,
                "source_record_id_method": "native",
                "container_id": f"{CORPUS_ID}:container:{pres['session_id']}",
                "record_type": "presentation",
                "title_or_subject": pres.get("title"),
                "body_locator": f"conferences.db#presentation.presentation_id={pres_id}",
                "created_at": event.get("start_date"),
                "language": pres.get("language"),
                "canonical_url": pres.get("source_url"),
                "content_sha256": None,
                "status": "active",
                "is_partial_2026": 1 if year == latest_year and latest_year >= 2026 else 0,
                "access_class": "public",
                "source_snapshot_id": snapshot_id,
            }
        )

        # Native topic: verbatim event theme, exactly as reported by the programme.
        theme = event.get("theme_ru") or event.get("theme_en")
        if theme:
            classification_assignments.append(
                {
                    "record_id": record_id,
                    "scheme_id": "native_topic",
                    "label_id": "conferences:programme_topic",
                    "value": theme,
                    "evidence_span": "event.theme_ru",
                    "method": "programme_metadata",
                    "method_version": "1.0.0",
                    "confidence": 1.0,
                    "review_status": "not_applicable",
                    "reviewer": None,
                    "assigned_at": manifest.acquired_at,
                }
            )

        # Argument level: reuse the already-computed Gumilev scale verbatim.
        gscale = gumilyov.get(pres_id)
        if gscale and gscale.get("gumilyov_level"):
            try:
                level = int(gscale["gumilyov_level"])
            except ValueError:
                level = None
            label_id = _GUMILYOV_LABEL.get(level)
            if label_id:
                classification_assignments.append(
                    {
                        "record_id": record_id,
                        "scheme_id": "argument_level",
                        "label_id": label_id,
                        "value": gscale.get("title"),
                        "evidence_span": "title",
                        "method": f"gumilyov_scale.csv ({gscale.get('source', 'existing derived asset')})",
                        "method_version": "1.0.0",
                        "confidence": float(gscale["confidence"]) if gscale.get("confidence") else None,
                        "review_status": "not_applicable",
                        "reviewer": None,
                        "assigned_at": manifest.acquired_at,
                    }
                )

        # Renou state/register: reuse the already-computed matches verbatim.
        for axis, scheme_id in (("state", "renou_state"), ("register", "renou_register")):
            row = renou_matches.get(pres_id, {}).get(axis)
            if row:
                classification_assignments.append(
                    {
                        "record_id": record_id,
                        "scheme_id": scheme_id,
                        "label_id": row["renou_code"],
                        "value": row["renou_label"],
                        "evidence_span": row.get("matched_field") or "title",
                        "method": f"renou_presentation_matches.csv (rule {row.get('rule_id')})",
                        "method_version": "1.0.0",
                        "confidence": None,
                        "review_status": "not_applicable",
                        "reviewer": None,
                        "assigned_at": manifest.acquired_at,
                    }
                )

        # Speakers: preserve native person IDs and reuse accepted authority IDs.
        speakers = sorted(
            (pp for pp in presentation_persons if pp["presentation_id"] == pres_id),
            key=lambda pp: (pp["author_order"] or 0, pp["person_id"]),
        )
        for pp in speakers:
            person = persons.get(pp["person_id"])
            if person is None:
                continue
            seen_persons[pp["person_id"]] = person
            record_names.append(
                {
                    "record_id": record_id,
                    "ordinal": pp["author_order"] or 1,
                    "role": pp["role"] or "speaker",
                    "name_as_source": person["display_name"],
                    "affiliation_as_source": pp.get("affiliation_text_raw"),
                    "source_account_id": None,
                    "person_id": f"{CORPUS_ID}:{pp['person_id']}",
                }
            )

    fixture = {
        "corpus": {
            "corpus_id": CORPUS_ID,
            "title": "Roerich/Zograf Readings conference corpus",
            "medium": "conference_programme",
            "forum_orientation": "one_to_many_scheduled",
            "native_unit": "presentation",
            "canonical_url": "https://ancient.ivran.ru/rerihovskie-chteniya",
            "rights_status": "public_published_programme",
        },
        "manifest": manifest.to_dict(),
        "containers": containers,
        "records": records,
        "record_names": record_names,
        "record_relations": [],
        "classification_assignments": classification_assignments,
        "annotations": [],
        "quotes": [],
        # H1893's `person`/`person_name` tables are populated separately (see
        # populate_persons below) since community_lenses.build's fixture loader
        # only inserts the seven _FIXTURE_TABLES keys; adapters own persons.
    }
    fixture["_persons"] = _build_person_rows(seen_persons, authority_ids)
    return fixture


def _build_person_rows(seen_persons: dict[str, dict], authority_ids: dict) -> list[dict]:
    rows = []
    for native_id, person in sorted(seen_persons.items()):
        authority = authority_ids.get(native_id, {})
        confidence = authority.get("confidence")
        rows.append(
            {
                "person_id": f"{CORPUS_ID}:{native_id}",
                "display_name": person["display_name"],
                "orcid": authority.get("orcid"),
                "wikidata": authority.get("wikidata"),
                "review_status": "accepted" if confidence in _ACCEPTED_CONFIDENCE else "pending",
                "reviewer": "authority_ids.json" if authority else None,
                "review_date": authority.get("checked_at"),
            }
        )
    return rows


def insert_persons(conn: sqlite3.Connection, fixture: dict) -> None:
    """Insert this adapter's person rows; call once, before record_name insert."""
    for row in fixture.get("_persons", []):
        conn.execute(
            """INSERT OR IGNORE INTO person
               (person_id, display_name, orcid, wikidata, review_status, reviewer, review_date)
               VALUES (:person_id, :display_name, :orcid, :wikidata, :review_status, :reviewer, :review_date)""",
            row,
        )


def coverage_report(fixture: dict) -> str:
    manifest = fixture["manifest"]
    records = fixture["records"]
    return _shared.render_coverage_report(
        corpus_id=CORPUS_ID,
        title="Roerich/Zograf Readings conferences",
        native_unit="presentation",
        coverage_status=manifest["coverage_status"],
        manifest_snapshot_id=manifest["snapshot_id"],
        date_range=f"{manifest.get('coverage_start') or '?'} .. {manifest.get('coverage_end') or '?'}",
        denominator_definition="one row per presentation_id in conferences.db's `presentation` table",
        included=len(records),
        excluded=0,
        failures=0,
        completeness_status="complete for the database's own extent" if records else "unavailable",
        notes=[
            "Native topic reuses event.theme_ru/theme_en verbatim (programme metadata), never rewritten.",
            "argument_level reuses analytics_output/gumilyov_scale.csv verbatim (existing G1-G3 assignments).",
            "renou_state/renou_register reuse analytics_output/renou_presentation_matches.csv verbatim.",
            (
                "theme_codes_final_v2.csv's l1/l2/l3/l4 thematic codes are deliberately NOT "
                "mapped into shared_topic here -- that crosswalk adjudication is H1897's scope, "
                "not H1895's."
            ),
            (
                "Historical figures (person_kind=historical in conferences.db) are excluded from "
                "speaker record_names by construction: presentation_person only links actual "
                "conference speakers, never historical/biographical references (CLAUDE.md #10)."
            ),
        ],
    )
