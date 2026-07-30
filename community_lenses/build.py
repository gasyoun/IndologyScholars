"""Deterministic fixture loader / builder / validator for the five-lens schema.

Wave 1A (H1893) scope only: loads the representative JSON fixtures under
``community_lenses/fixtures/`` into the sqlite schema from ``schema.py``,
runs every cross-cutting guardrail (ID/reference integrity, controlled-value
membership, source/derived separation, rights defaults, native/derived
mixing), and provides a canonical, deterministic serialize/reload round trip.
No adapters, no live acquisition, no substantive crosswalk adjudication:
those are H1894/H1895/H1896.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import ids as ids_mod
from . import taxonomy
from .manifests import SourceManifest, validate_manifest, validate_no_mixed_snapshot
from .schema import CORPUS_IDS, build_schema, create_connection, validate_schema

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Tables dumped/inserted in dependency order; must stay in sync with the
# fixture JSON keys and schema.TABLE_ORDER's parent-before-child ordering.
_FIXTURE_TABLES = (
    ("containers", "container"),
    ("records", "record"),
    ("record_names", "record_name"),
    ("record_relations", "record_relation"),
    ("classification_assignments", "classification_assignment"),
    ("annotations", "annotation"),
    ("quotes", "quote"),
)


class FixtureError(ValueError):
    pass


def list_fixture_corpora() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in FIXTURES_DIR.glob("*.json")))


def load_fixture(corpus_id: str) -> dict:
    path = FIXTURES_DIR / f"{corpus_id}.json"
    if not path.exists():
        raise FixtureError(f"no fixture for corpus_id={corpus_id!r} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_fixtures() -> dict[str, dict]:
    return {corpus_id: load_fixture(corpus_id) for corpus_id in CORPUS_IDS}


def fixture_manifest(fixture: dict) -> SourceManifest:
    return SourceManifest(**fixture["manifest"])


def _insert_corpus(conn: sqlite3.Connection, corpus: dict) -> None:
    conn.execute(
        """INSERT INTO corpus
           (corpus_id, title, medium, forum_orientation, native_unit,
            canonical_url, rights_status)
           VALUES (:corpus_id, :title, :medium, :forum_orientation,
                   :native_unit, :canonical_url, :rights_status)""",
        corpus,
    )


def _insert_snapshot(conn: sqlite3.Connection, manifest: SourceManifest) -> None:
    data = manifest.to_dict()
    conn.execute(
        """INSERT INTO source_snapshot
           (snapshot_id, corpus_id, coverage_start, coverage_end, cutoff_date,
            coverage_status, source_version, acquired_at, source_sha256,
            pipeline_commit, schema_version, codebook_version, rights_basis)
           VALUES (:snapshot_id, :corpus_id, :coverage_start, :coverage_end,
                   :cutoff_date, :coverage_status, :source_version,
                   :acquired_at, :source_sha256, :pipeline_commit,
                   :schema_version, :codebook_version, :rights_basis)""",
        data,
    )


_TABLE_COLUMNS = {
    "container": (
        "container_id", "corpus_id", "source_snapshot_id",
        "parent_container_id", "container_type", "source_native_id",
        "title", "date_from", "date_to", "source_url",
    ),
    "record": (
        "record_id", "corpus_id", "source_record_id",
        "source_record_id_method", "container_id", "record_type",
        "title_or_subject", "body_locator", "created_at", "language",
        "canonical_url", "content_sha256", "status", "is_partial_2026",
        "access_class", "source_snapshot_id",
    ),
    "record_name": (
        "record_id", "ordinal", "role", "name_as_source",
        "affiliation_as_source", "source_account_id", "person_id",
    ),
    "record_relation": (
        "subject_record_id", "predicate", "object_record_id", "evidence_locator",
    ),
    "classification_assignment": (
        "record_id", "scheme_id", "label_id", "value", "evidence_span",
        "method", "method_version", "confidence", "review_status",
        "reviewer", "assigned_at",
    ),
    "annotation": (
        "annotation_id", "record_id", "annotation_type", "body", "author",
        "created_at", "access_class",
    ),
    "quote": (
        "quote_id", "record_id", "person_id", "author_display",
        "quote_verbatim", "omissions_marked", "source_url", "source_date",
        "retrieved_at", "thread_subject", "context_note",
        "context_before_sha256", "context_after_sha256",
        "public_access_checked_at", "contact_data_removed",
        "rights_review_status", "article_claim_id",
    ),
}


def _insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    columns = _TABLE_COLUMNS[table]
    for row in rows:
        # Only name columns the row actually supplies, so a genuinely absent
        # key (e.g. an omitted quote.rights_review_status) falls through to
        # the table's own DEFAULT/CHECK instead of an explicit NULL.
        present = [c for c in columns if c in row]
        placeholders = ", ".join(f":{c}" for c in present)
        conn.execute(
            f"INSERT INTO {table} ({', '.join(present)}) VALUES ({placeholders})",
            {c: row[c] for c in present},
        )


def validate_record_ids(fixture: dict) -> list[str]:
    """Every record_id must equal ids.make_record_id(corpus_id, source_record_id)."""
    errors = []
    corpus_id = fixture["corpus"]["corpus_id"]
    for record in fixture["records"]:
        expected = ids_mod.make_record_id(corpus_id, record["source_record_id"])
        if record["record_id"] != expected:
            errors.append(
                f"{corpus_id}: record_id {record['record_id']!r} != expected "
                f"{expected!r} from make_record_id"
            )
    return errors


def populate_corpus(conn: sqlite3.Connection, fixture: dict) -> None:
    _insert_corpus(conn, fixture["corpus"])
    manifest = fixture_manifest(fixture)
    manifest_errors = validate_manifest(manifest)
    if manifest_errors:
        raise FixtureError(
            f"{fixture['corpus']['corpus_id']}: invalid manifest: {manifest_errors}"
        )
    _insert_snapshot(conn, manifest)
    for fixture_key, table in _FIXTURE_TABLES:
        _insert_rows(conn, table, fixture.get(fixture_key, []))


# Schemes that are shared across lenses (vs. native_topic, which is one
# per-source namespace living inside a single shared table; see
# codebooks/native_topic.csv).
_SHARED_SCHEME_NAMES = (
    "shared_topic",
    "community_function",
    "renou_state",
    "renou_register",
    "argument_level",
)


def seed_taxonomy_schemes(conn: sqlite3.Connection) -> None:
    """Register every H1893 codebook as a taxonomy_scheme row.

    classification_assignment.scheme_id is a foreign key into this table, so
    every codebook a fixture assigns labels from must be registered here
    before fixture rows are inserted.
    """
    for name in taxonomy.CODEBOOK_NAMES:
        conn.execute(
            """INSERT INTO taxonomy_scheme
               (scheme_id, name, owner_corpus_id, is_shared_axis, version, description)
               VALUES (:scheme_id, :name, :owner_corpus_id, :is_shared_axis, :version, :description)""",
            {
                "scheme_id": name,
                "name": name,
                "owner_corpus_id": None,
                "is_shared_axis": 1 if name in _SHARED_SCHEME_NAMES else 0,
                "version": taxonomy.codebook_version(name),
                "description": f"H1893 codebook contract: community_lenses/codebooks/{name}.csv",
            },
        )


def build_database(fixtures: dict[str, dict] | None = None) -> sqlite3.Connection:
    """Build an in-memory database from every fixture, deterministically."""
    if fixtures is None:
        fixtures = load_all_fixtures()
    conn = create_connection(":memory:")
    build_schema(conn)
    seed_taxonomy_schemes(conn)
    # Deterministic order regardless of dict insertion order.
    for corpus_id in sorted(fixtures):
        populate_corpus(conn, fixtures[corpus_id])
    conn.commit()
    return conn


def dump_database(conn: sqlite3.Connection) -> dict:
    """Canonical, order-independent snapshot of every table's contents."""
    from .schema import TABLE_ORDER

    dump: dict[str, list[dict]] = {}
    for table in TABLE_ORDER:
        cursor = conn.execute(f"SELECT * FROM {table}")
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        rows.sort(key=lambda r: json.dumps(r, sort_keys=True, default=str))
        dump[table] = rows
    return dump


def canonical_json(conn: sqlite3.Connection) -> str:
    return json.dumps(dump_database(conn), indent=2, sort_keys=True, default=str) + "\n"


def validate_build(conn: sqlite3.Connection, fixtures: dict[str, dict]) -> list[str]:
    """Run every H1893 guardrail; empty return means the build is clean."""
    errors: list[str] = []

    errors.extend(f"schema: {e}" for e in validate_schema(conn))

    manifests = [fixture_manifest(f) for f in fixtures.values()]
    errors.extend(f"manifest: {e}" for e in validate_no_mixed_snapshot(manifests))
    for corpus_id, fixture in fixtures.items():
        for e in validate_manifest(fixture_manifest(fixture)):
            errors.append(f"manifest[{corpus_id}]: {e}")

    for corpus_id, fixture in fixtures.items():
        errors.extend(f"ids[{corpus_id}]: {e}" for e in validate_record_ids(fixture))

    for name, codebook_errors in taxonomy.validate_all_codebooks().items():
        errors.extend(f"codebook[{name}]: {e}" for e in codebook_errors)

    # Controlled-value membership: any classification_assignment whose
    # scheme_id names a codebook must use a label_id that exists in it.
    codebook_names = set(taxonomy.CODEBOOK_NAMES)
    label_sets: dict[str, set[str]] = {}
    for row in conn.execute(
        "SELECT record_id, scheme_id, label_id FROM classification_assignment"
    ):
        scheme_id = row["scheme_id"]
        if scheme_id not in codebook_names:
            continue
        if scheme_id not in label_sets:
            label_sets[scheme_id] = {
                r["label_id"] for r in taxonomy.load_codebook(scheme_id)
            }
        if row["label_id"] not in label_sets[scheme_id]:
            errors.append(
                f"classification_assignment: record {row['record_id']!r} uses "
                f"label_id {row['label_id']!r} not present in codebook "
                f"{scheme_id!r}"
            )

    # Native/derived separation: a record's native title_or_subject text must
    # never be reused verbatim as a *shared_topic* classification value (that
    # would silently flatten native vocabulary into the shared axis without a
    # crosswalk decision — the exact thing H1893 must not do).
    for row in conn.execute(
        """SELECT r.record_id, r.title_or_subject, ca.value
           FROM record r JOIN classification_assignment ca
             ON ca.record_id = r.record_id AND ca.scheme_id = 'shared_topic'"""
    ):
        if row["title_or_subject"] and row["value"] == row["title_or_subject"]:
            errors.append(
                f"native/derived mixing: record {row['record_id']!r} copies "
                "title_or_subject verbatim into a shared_topic assignment"
            )

    return errors
