"""Historical prosopography seeder (H484, Phase 2, decision A1 variant A).

Loads indologists who never presented at the Zograf/Roerich readings into the single
``person`` spine, tagged ``person_kind = 'historical'``. They carry no
``presentation_person`` rows, so every published "speaker" count -- all of which join
through ``presentation_person`` -- is unaffected: the cited figure of 268 stays 268.

Source of truth is ``curation/historical_persons.csv`` (+ ``historical_person_roles.csv``),
regenerated from Wikidata by ``tools/resolve_historical_wikidata.py``. It must live in
``curation/``, never only in the ``.db``: ``pipeline.schema.init_db`` drops and re-seeds
``person`` on every build, so a figure whose only home was the database would vanish on
the next rebuild -- the exact trap the ``apply_birth_years`` chain fell into.

Ordering (see build_and_populate_db.py):

1. ``seed_historical_persons`` runs BEFORE ``populate_prosopography`` so the manual
   discipline path in ``pipeline.disciplines`` can resolve these people by normalized_key.
2. ``seed_historical_roles`` runs AFTER it, because ``load_person_roles`` opens with an
   unconditional ``DELETE FROM person_role`` that would otherwise wipe these rows.

Provenance: every biographical fact (birth_year, death_year, wikidata_qid) is written to
``data_assertion`` under this module's own ``curator_id`` with the figure's Wikidata URL as
``source_url``. It NEVER touches the 803 curated rows owned by other curators -- it deletes
only its own before re-inserting, so the seeder is idempotent.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from pipeline.biography import canonical_person_key, person_id_for_key

ROOT = Path(__file__).resolve().parents[1]
PERSONS_CSV = ROOT / "curation" / "historical_persons.csv"
ROLES_CSV = ROOT / "curation" / "historical_person_roles.csv"

CURATOR_ID = "h484_historical_seeder"


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [r for r in csv.DictReader(handle) if any((v or "").strip() for v in r.values())]


def _int_or_none(value: str):
    value = (value or "").strip()
    return int(value) if value else None


def seed_historical_persons(conn):
    """Insert historical figures into `person` (kind='historical') + their data_assertions.

    Returns (persons_inserted, assertions_written). Idempotent: only this module's own
    person rows and data_assertion rows are cleared first.
    """
    rows = _rows(PERSONS_CSV)

    # A historical figure with no death_year is a data defect for this period (roadmap
    # risk P3), not an unknown -- and the memorial template keys off death_year. Refuse it
    # loudly rather than seed a half-record that renders as a living scholar.
    missing = [r["display_name"] for r in rows if not _int_or_none(r.get("death_year"))]
    if missing:
        raise ValueError(
            "historical_persons.csv: death_year is mandatory for a historical figure "
            f"(roadmap P3). Missing for: {', '.join(missing)}. "
            "Re-run tools/resolve_historical_wikidata.py or supply a printed source."
        )

    cursor = conn.cursor()
    existing_kind = {c[1] for c in cursor.execute("PRAGMA table_info(person)")}
    if "person_kind" not in existing_kind:
        raise RuntimeError(
            "person.person_kind is absent -- rebuild with the H484 schema before seeding."
        )

    # Idempotent reset of only what this module owns.
    cursor.execute("DELETE FROM person WHERE person_kind = 'historical'")
    cursor.execute("DELETE FROM data_assertion WHERE curator_id = ?", (CURATOR_ID,))

    # data_assertion.verified_at is NOT NULL; Phase 1 fills it with the build date.
    verified_at = dt.date.today().isoformat()
    persons = 0
    assertions = 0
    seen_ids: dict[str, str] = {}
    for r in rows:
        display_name = r["display_name"].strip()
        norm_key = canonical_person_key(display_name)
        pid = person_id_for_key(norm_key)

        if pid in seen_ids:
            raise ValueError(
                f"historical_persons.csv: {display_name!r} collides with "
                f"{seen_ids[pid]!r} on person_id {pid}."
            )
        collision = cursor.execute(
            "SELECT display_name FROM person WHERE person_id = ?", (pid,)
        ).fetchone()
        if collision:
            # A historical figure sharing an id with a conference participant means the
            # same human presented -- that is a MERGE decision for a curator, not a silent
            # overwrite. Stop rather than clobber a participant row.
            raise ValueError(
                f"historical_persons.csv: {display_name!r} (id {pid}) already exists as a "
                f"participant {collision[0]!r}. Resolve by hand -- do not seed over it."
            )
        seen_ids[pid] = display_name

        birth_year = _int_or_none(r.get("birth_year"))
        death_year = _int_or_none(r.get("death_year"))
        source_url = (r.get("source_url") or "").strip() or None
        notes = (r.get("note") or "").strip() or None

        cursor.execute(
            "INSERT INTO person (person_id, display_name, full_name_ru, full_name_en, "
            "birth_year, death_year, normalized_key, source_url, notes, person_kind) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                pid,
                display_name,
                (r.get("full_name_ru") or display_name).strip(),
                (r.get("full_name_en") or "").strip() or None,
                birth_year,
                death_year,
                norm_key,
                source_url,
                notes,
                "historical",
            ),
        )
        persons += 1

        # One data_assertion per sourced fact. status='disputed' rows still get the chosen
        # year, with the disagreement carried in `notes` -> the assertion citation.
        for attribute, value in (
            ("birth_year", birth_year),
            ("death_year", death_year),
            ("wikidata_qid", (r.get("wikidata_qid") or "").strip() or None),
        ):
            if value is None:
                continue
            confidence = 0.7 if (r.get("status") == "disputed" and attribute == "birth_year") else 1.0
            cursor.execute(
                "INSERT INTO data_assertion "
                "(entity_type, entity_id, attribute, value, source_url, citation, confidence, curator_id, verified_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "person",
                    pid,
                    attribute,
                    str(value),
                    source_url,
                    notes,
                    confidence,
                    CURATOR_ID,
                    verified_at,
                ),
            )
            assertions += 1

    conn.commit()
    return persons, assertions


def seed_historical_roles(conn):
    """Add institutional trajectories for historical figures to `person_role`.

    Must run AFTER populate_prosopography, whose load_person_roles wipes person_role.
    organization_id stays NULL (Wikidata org QIDs are not reconciled to our `organization`
    table); the org label + QID live in notes, matching the Phase 1 convention.
    """
    cursor = conn.cursor()
    hist_ids = {
        r[0] for r in cursor.execute("SELECT person_id FROM person WHERE person_kind = 'historical'")
    }
    key_to_id = {
        canonical_person_key(r["display_name"]): r for r in _rows(PERSONS_CSV)
    }
    # Map each role row (keyed by qid) to a person_id via the persons CSV.
    qid_to_pid = {}
    for r in _rows(PERSONS_CSV):
        pid = person_id_for_key(canonical_person_key(r["display_name"]))
        if pid in hist_ids:
            qid_to_pid[(r.get("wikidata_qid") or "").strip()] = pid

    inserted = 0
    skipped = 0
    for r in _rows(ROLES_CSV):
        pid = qid_to_pid.get((r.get("wikidata_qid") or "").strip())
        if not pid:
            skipped += 1
            continue
        org_label = (r.get("organization_ru") or "").strip()
        org_qid = (r.get("organization_qid") or "").strip()
        role_id = f"ROLE_H_{pid[5:]}_{org_qid}_{r.get('role', '')}"
        note = org_label + (f" [{org_qid}]" if org_qid else "")
        cursor.execute(
            "INSERT OR REPLACE INTO person_role VALUES (?,?,?,?,?,?,?,?)",
            (
                role_id,
                pid,
                None,  # organization_id: Wikidata org QID not reconciled to `organization`
                (r.get("role") or "affiliation").strip(),
                _int_or_none(r.get("from_year")),
                _int_or_none(r.get("to_year")),
                (r.get("source_url") or "").strip() or None,
                note,
            ),
        )
        inserted += 1

    conn.commit()
    return inserted, skipped
