"""Prosopographical spine loader: disciplines, roles, relations (H473, Phase 1).

Populates the tables added to ``pipeline.schema.init_db``:

* ``discipline``        -- from ``curation/disciplines.csv`` (flat + parent pointer)
* ``person_discipline`` -- derived, see below
* ``person_role``       -- from ``curation/verified_affiliation_spans.csv``
* ``relation``          -- from ``curation/teacher_student.csv`` (verified rows only)
* ``work`` / ``work_discipline`` -- created empty; filled in Phase 4

How ``person_discipline`` is derived
------------------------------------
Two sources, manual wins on conflict:

1. **Crosswalk.** ``curation/meso_discipline_crosswalk.csv`` maps each meso code
   to zero or more disciplines. Meso codes come from
   ``analytics_output/meso_codes_deepseek.csv`` (an LLM classification of all
   1362 presentation titles, 100% coverage, cross-model agreement reported in
   ``docs/classification-reliability-packet.md``).

2. **Manual.** ``curation/person_disciplines.csv`` -- hand assignment from the
   talk titles, for persons the crosswalk cannot reach.

``keyword_filtering.py`` is **deliberately not used**. Its Cyrillic stems are
unanchored ("тика" fires inside "Эротика"/"практика"), giving a >=7.1% error
floor -- see ``docs/renou-precision-audit.md`` and risk P1 of the roadmap.

Confidence is the **maximum** of the contributing mappings, never their
accumulation: several weak signals must not manufacture certainty.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

from pipeline.genealogy import load_relationships
from pipeline.parser import stable_hash

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DISCIPLINES_CSV = ROOT / "curation" / "disciplines.csv"
CROSSWALK_CSV = ROOT / "curation" / "meso_discipline_crosswalk.csv"
PERSON_DISCIPLINES_CSV = ROOT / "curation" / "person_disciplines.csv"
AFFILIATION_SPANS_CSV = ROOT / "curation" / "verified_affiliation_spans.csv"
MESO_CODES_CSV = ROOT / "analytics_output" / "meso_codes_deepseek.csv"

CURATOR_ID = "h473_discipline_tagger"
UNATTESTED = "unattested"

# curation/teacher_student.csv vocabulary -> relation.relation_type CHECK vocabulary.
# Every row is stored subject=advisor, object=student.
RELATION_TYPE_MAP = {
    "advisor": "teacher",
    "supervisor": "teacher",
    "mentor": "teacher",
    "lectured": "teacher",
    "academic_lineage": "successor",
}


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [r for r in csv.DictReader(handle) if any((v or "").strip() for v in r.values())]


def load_taxonomy(conn):
    rows = _rows(DISCIPLINES_CSV)
    codes = {r["discipline_code"].strip() for r in rows}
    for r in rows:
        parent = (r.get("parent_code") or "").strip() or None
        if parent and parent not in codes:
            raise ValueError(f"disciplines.csv: unknown parent_code {parent!r}")
        conn.execute(
            "INSERT OR REPLACE INTO discipline VALUES (?,?,?,?,?,?)",
            (
                r["discipline_code"].strip(),
                r["label_ru"].strip(),
                (r.get("label_en") or "").strip() or None,
                parent,
                (r.get("status") or "core").strip(),
                (r.get("note") or "").strip() or None,
            ),
        )
    conn.commit()
    return codes


def load_crosswalk(known_codes):
    """meso_code -> list of (discipline_code, confidence). Blank target = deliberate no-map."""
    xwalk = defaultdict(list)
    for r in _rows(CROSSWALK_CSV):
        disc = (r.get("discipline_code") or "").strip()
        if not disc:
            continue
        if disc not in known_codes:
            raise ValueError(f"meso_discipline_crosswalk.csv: unknown discipline_code {disc!r}")
        xwalk[r["meso_code"].strip()].append((disc, float(r["confidence"])))
    return xwalk


def load_meso_by_presentation():
    out = {}
    for r in _rows(MESO_CODES_CSV):
        pid = (r.get("presentation_id") or "").strip()
        if pid:
            out[pid] = [c for c in (r.get("meso_codes") or "").split("|") if c]
    return out


def derive_person_disciplines(conn, xwalk, known_codes):
    """Returns {person_id: {discipline_id: (confidence, method, evidence)}}."""
    meso = load_meso_by_presentation()

    talks = defaultdict(list)
    for person_id, presentation_id in conn.execute(
        "SELECT person_id, presentation_id FROM presentation_person"
    ):
        talks[person_id].append(presentation_id)

    assigned: dict[str, dict[str, tuple]] = defaultdict(dict)
    for person_id, presentations in talks.items():
        support = defaultdict(int)
        best = {}
        for pid in presentations:
            hit = set()
            for code in meso.get(pid, []):
                for disc, conf in xwalk.get(code, []):
                    hit.add(disc)
                    if conf > best.get(disc, 0.0):
                        best[disc] = conf
            for disc in hit:
                support[disc] += 1
        for disc, conf in best.items():
            n = support[disc]
            assigned[person_id][disc] = (
                round(conf, 2),
                "meso_crosswalk",
                f"{n} доклад(ов) с meso-кодами, отображёнными на «{disc}»",
            )

    # Manual assignments override the crosswalk.
    key_to_person = {}
    for person_id, normalized_key in conn.execute(
        "SELECT person_id, normalized_key FROM person"
    ):
        key_to_person[normalized_key] = person_id

    manual_unattested = set()
    for r in _rows(PERSON_DISCIPLINES_CSV):
        key = r["normalized_key"].strip()
        person_id = key_to_person.get(key)
        if person_id is None:
            raise ValueError(f"person_disciplines.csv: normalized_key {key!r} not in person table")
        disc = r["discipline_code"].strip()
        if disc not in known_codes:
            raise ValueError(f"person_disciplines.csv: unknown discipline_code {disc!r}")
        if disc == UNATTESTED:
            manual_unattested.add(person_id)
            continue
        assigned[person_id][disc] = (
            round(float(r["confidence"]), 2),
            (r.get("method") or "manual").strip(),
            (r.get("evidence") or "").strip(),
        )

    # `unattested` is a sentinel, not a discipline: it may only stand alone.
    for person_id in manual_unattested:
        if not assigned.get(person_id):
            assigned[person_id][UNATTESTED] = (
                0.0,
                "manual_title_review",
                "В архиве нет ни одного научного доклада (только институциональные приветствия).",
            )

    # Nobody may silently fall through: an unclassified person gets the sentinel
    # and is reported, never a guessed discipline.
    all_persons = [r[0] for r in conn.execute("SELECT person_id FROM person")]
    orphans = [p for p in all_persons if not assigned.get(p)]
    for person_id in orphans:
        assigned[person_id][UNATTESTED] = (
            0.0,
            "fallback",
            "Ни один meso-код и ни одна ручная строка не дали дисциплину.",
        )
    return assigned, orphans


def write_person_disciplines(conn, assigned):
    conn.execute("DELETE FROM person_discipline")
    # Idempotent: drop only the rows this module owns, never the 803 curated ones.
    conn.execute("DELETE FROM data_assertion WHERE curator_id = ?", (CURATOR_ID,))

    verified_at = _build_date()
    rows = 0
    for person_id, discs in assigned.items():
        for disc, (conf, method, evidence) in sorted(discs.items()):
            conn.execute(
                "INSERT OR REPLACE INTO person_discipline VALUES (?,?,?,?,?,?,?)",
                (person_id, disc, conf, method, evidence, None, None),
            )
            conn.execute(
                "INSERT INTO data_assertion "
                "(entity_type, entity_id, attribute, value, source_url, citation, confidence, curator_id, verified_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "person",
                    person_id,
                    "discipline",
                    disc,
                    None,
                    evidence or None,
                    f"{conf:.2f}",
                    CURATOR_ID,
                    verified_at,
                ),
            )
            rows += 1
    conn.commit()
    return rows


def _build_date():
    import datetime as dt

    return dt.date.today().isoformat()


def load_relations(conn):
    key_to_person = dict(
        (nk, pid) for pid, nk in conn.execute("SELECT person_id, normalized_key FROM person")
    )
    conn.execute("DELETE FROM relation")
    inserted, skipped = 0, 0
    for rel in load_relationships(include_candidates=False):
        subject = key_to_person.get(rel.advisor_key)
        obj = key_to_person.get(rel.student_key)
        if not subject or not obj:
            skipped += 1
            continue
        relation_type = RELATION_TYPE_MAP.get(rel.relationship_type)
        if not relation_type:
            skipped += 1
            continue
        relation_id = "REL_" + stable_hash(subject, obj, relation_type)
        conn.execute(
            "INSERT OR REPLACE INTO relation VALUES (?,?,?,?,?,?,?)",
            (
                relation_id,
                subject,
                obj,
                relation_type,
                rel.evidence_url or None,
                1.0 if rel.status == "verified" else 0.5,
                f"{rel.relationship_type}: {rel.evidence_note}".strip(": "),
            ),
        )
        inserted += 1
    conn.commit()
    return inserted, skipped


def load_person_roles(conn):
    conn.execute("DELETE FROM person_role")
    known_persons = {r[0] for r in conn.execute("SELECT person_id FROM person")}
    inserted, skipped = 0, 0
    for r in _rows(AFFILIATION_SPANS_CSV):
        person_id = (r.get("person_id") or "").strip()
        if person_id not in known_persons:
            skipped += 1
            continue

        def year(field):
            raw = (r.get(field) or "").strip()
            return int(raw) if raw else None

        affiliation = (r.get("affiliation_ru") or "").strip()
        role_id = "ROLE_" + stable_hash(person_id, affiliation, r.get("start_year") or "")
        conn.execute(
            "INSERT OR REPLACE INTO person_role VALUES (?,?,?,?,?,?,?,?)",
            (
                role_id,
                person_id,
                None,  # organization_id: affiliation strings are not yet reconciled to organization
                "affiliation",
                year("start_year"),
                year("end_year"),
                (r.get("source_url") or "").strip() or None,
                affiliation + (f" — {r.get('note')}" if r.get("note") else ""),
            ),
        )
        inserted += 1
    conn.commit()
    return inserted, skipped


def warn_if_curated_assertions_missing(conn):
    """`data_assertion` is irreproducible: only the committed .db carries its 803 rows.

    ``init_db`` now creates the table when absent, so a build after
    ``rm conferences.db`` no longer crashes in ``generate_site_data.py``. That
    turned a loud failure into a quiet one -- every ORCID and Wikidata link would
    vanish from the site without a word. Say so, loudly.
    """
    curated = conn.execute(
        "SELECT count(*) FROM data_assertion WHERE curator_id != ?", (CURATOR_ID,)
    ).fetchone()[0]
    if curated == 0:
        print(
            "  WARNING: data_assertion holds no curated rows. The 803 provenance rows "
            "(ORCID / Wikidata / birth years) live ONLY in the committed conferences.db "
            "and are not reproducible from source. If you deleted the .db, restore it "
            "from git (`git checkout -- conferences.db`) before publishing."
        )
    return curated


def populate_prosopography(conn):
    known_codes = load_taxonomy(conn)
    xwalk = load_crosswalk(known_codes)
    assigned, orphans = derive_person_disciplines(conn, xwalk, known_codes)
    rows = write_person_disciplines(conn, assigned)

    curated = warn_if_curated_assertions_missing(conn)
    relations, rel_skipped = load_relations(conn)
    roles, role_skipped = load_person_roles(conn)

    persons = len(assigned)
    unattested = sum(1 for d in assigned.values() if UNATTESTED in d)
    print(f"Disciplines: {len(known_codes)} codes; {rows} person-discipline rows over {persons} persons.")
    print(f"  attested: {persons - unattested}; unattested sentinel: {unattested}")
    if orphans:
        print(f"  WARNING: {len(orphans)} person(s) fell through to the fallback sentinel: {orphans}")
    print(f"  curated data_assertion rows preserved: {curated}")
    print(f"Relations: {relations} inserted, {rel_skipped} skipped (person not in corpus).")
    print(f"Person roles: {roles} inserted, {role_skipped} skipped.")
    return rows
