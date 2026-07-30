"""Common relational schema for the five-lens community comparison.

Implements the tables specified in
docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md, scoped to
Wave 1A (H1893): schema + stable IDs only, no adapters, no populated
crosswalks, no identity merges, no selected quotes. Every table enforces
foreign keys and controlled enumerations so that invalid IDs/references,
missing provenance/rights, and native/derived mixing fail closed rather than
silently passing.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = "1.0.0"

CORPUS_IDS = ("conferences", "nagari", "vk_ors", "indology_l", "bvp")
COVERAGE_STATUSES = ("complete", "partial", "pilot", "unavailable", "mixed_snapshot")
RECORD_STATUSES = (
    "active",
    "corrected",
    "withdrawn",
    "deleted",
    "redacted",
    "unavailable",
)
RELATION_PREDICATES = (
    "reply_to",
    "thread_member",
    "comment_on",
    "attachment_of",
    "revision_of",
    "duplicate_of",
    "cross_post_of",
    "derived_from",
    "presented_at",
    "participated_in",
)
MAPPING_RELATIONS = ("exact", "broad", "narrow", "related", "unmapped")
REVIEW_STATUSES = ("pending", "accepted", "rejected", "not_applicable")
ACCESS_CLASSES = ("public", "restricted", "private", "unknown")
QUOTE_POLICIES = ("non_exportable", "exportable_approved", "pending_review")

_CORPUS_LIST = ", ".join(f"'{c}'" for c in CORPUS_IDS)
_COVERAGE_LIST = ", ".join(f"'{c}'" for c in COVERAGE_STATUSES)
_RECORD_STATUS_LIST = ", ".join(f"'{c}'" for c in RECORD_STATUSES)
_PREDICATE_LIST = ", ".join(f"'{c}'" for c in RELATION_PREDICATES)
_MAPPING_LIST = ", ".join(f"'{c}'" for c in MAPPING_RELATIONS)
_REVIEW_LIST = ", ".join(f"'{c}'" for c in REVIEW_STATUSES)
_ACCESS_LIST = ", ".join(f"'{c}'" for c in ACCESS_CLASSES)
_QUOTE_POLICY_LIST = ", ".join(f"'{c}'" for c in QUOTE_POLICIES)

# Table order matters: children are dropped/created after the parents they
# reference so that `PRAGMA foreign_keys=ON` never rejects a CREATE TABLE.
TABLE_ORDER = (
    "corpus",
    "source_snapshot",
    "container",
    "record",
    "record_name",
    "record_relation",
    "person",
    "person_name",
    "person_match_assertion",
    "taxonomy_scheme",
    "classification_assignment",
    "taxonomy_crosswalk",
    "provenance_assertion",
    "correction",
    "annotation",
    "quote",
)

DDL: dict[str, str] = {
    "corpus": f"""
        CREATE TABLE corpus (
            corpus_id TEXT PRIMARY KEY CHECK (corpus_id IN ({_CORPUS_LIST})),
            title TEXT NOT NULL,
            medium TEXT NOT NULL,
            forum_orientation TEXT NOT NULL,
            native_unit TEXT NOT NULL,
            canonical_url TEXT,
            rights_status TEXT NOT NULL
        )
    """,
    "source_snapshot": f"""
        CREATE TABLE source_snapshot (
            snapshot_id TEXT PRIMARY KEY,
            corpus_id TEXT NOT NULL REFERENCES corpus(corpus_id),
            coverage_start TEXT,
            coverage_end TEXT,
            cutoff_date TEXT,
            coverage_status TEXT NOT NULL CHECK (coverage_status IN ({_COVERAGE_LIST})),
            source_version TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            pipeline_commit TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            codebook_version TEXT NOT NULL,
            rights_basis TEXT NOT NULL
        )
    """,
    "container": """
        CREATE TABLE container (
            container_id TEXT PRIMARY KEY,
            corpus_id TEXT NOT NULL REFERENCES corpus(corpus_id),
            source_snapshot_id TEXT NOT NULL REFERENCES source_snapshot(snapshot_id),
            parent_container_id TEXT REFERENCES container(container_id),
            container_type TEXT NOT NULL,
            source_native_id TEXT NOT NULL,
            title TEXT,
            date_from TEXT,
            date_to TEXT,
            source_url TEXT
        )
    """,
    "record": f"""
        CREATE TABLE record (
            record_id TEXT PRIMARY KEY,
            corpus_id TEXT NOT NULL REFERENCES corpus(corpus_id),
            source_record_id TEXT NOT NULL,
            source_record_id_method TEXT NOT NULL DEFAULT 'native'
                CHECK (source_record_id_method IN ('native', 'fallback_hash')),
            container_id TEXT REFERENCES container(container_id),
            record_type TEXT NOT NULL,
            title_or_subject TEXT,
            body_locator TEXT,
            created_at TEXT,
            language TEXT,
            canonical_url TEXT,
            content_sha256 TEXT,
            status TEXT NOT NULL CHECK (status IN ({_RECORD_STATUS_LIST})),
            is_partial_2026 INTEGER NOT NULL DEFAULT 0 CHECK (is_partial_2026 IN (0, 1)),
            access_class TEXT NOT NULL CHECK (access_class IN ({_ACCESS_LIST})),
            source_snapshot_id TEXT NOT NULL REFERENCES source_snapshot(snapshot_id),
            UNIQUE (corpus_id, source_record_id)
        )
    """,
    "record_name": """
        CREATE TABLE record_name (
            record_id TEXT NOT NULL REFERENCES record(record_id),
            ordinal INTEGER NOT NULL,
            role TEXT NOT NULL,
            name_as_source TEXT NOT NULL,
            affiliation_as_source TEXT,
            source_account_id TEXT,
            person_id TEXT REFERENCES person(person_id),
            PRIMARY KEY (record_id, ordinal)
        )
    """,
    "record_relation": f"""
        CREATE TABLE record_relation (
            subject_record_id TEXT NOT NULL REFERENCES record(record_id),
            predicate TEXT NOT NULL CHECK (predicate IN ({_PREDICATE_LIST})),
            object_record_id TEXT NOT NULL REFERENCES record(record_id),
            evidence_locator TEXT,
            PRIMARY KEY (subject_record_id, predicate, object_record_id)
        )
    """,
    "person": f"""
        CREATE TABLE person (
            person_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            orcid TEXT,
            wikidata TEXT,
            review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ({_REVIEW_LIST})),
            reviewer TEXT,
            review_date TEXT
        )
    """,
    "person_name": """
        CREATE TABLE person_name (
            person_id TEXT NOT NULL REFERENCES person(person_id),
            ordinal INTEGER NOT NULL,
            script TEXT NOT NULL,
            transliteration_scheme TEXT,
            name_text TEXT NOT NULL,
            is_preferred INTEGER NOT NULL DEFAULT 0 CHECK (is_preferred IN (0, 1)),
            evidence_record_id TEXT REFERENCES record(record_id),
            PRIMARY KEY (person_id, ordinal)
        )
    """,
    "person_match_assertion": f"""
        CREATE TABLE person_match_assertion (
            assertion_id TEXT PRIMARY KEY,
            source_record_id TEXT NOT NULL REFERENCES record(record_id),
            candidate_person_id TEXT NOT NULL REFERENCES person(person_id),
            method TEXT NOT NULL,
            score REAL,
            evidence TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ({_REVIEW_LIST}))
        )
    """,
    "taxonomy_scheme": """
        CREATE TABLE taxonomy_scheme (
            scheme_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_corpus_id TEXT REFERENCES corpus(corpus_id),
            is_shared_axis INTEGER NOT NULL DEFAULT 0 CHECK (is_shared_axis IN (0, 1)),
            version TEXT NOT NULL,
            description TEXT
        )
    """,
    "classification_assignment": f"""
        CREATE TABLE classification_assignment (
            record_id TEXT NOT NULL REFERENCES record(record_id),
            scheme_id TEXT NOT NULL REFERENCES taxonomy_scheme(scheme_id),
            label_id TEXT NOT NULL,
            value TEXT,
            evidence_span TEXT,
            method TEXT NOT NULL,
            method_version TEXT NOT NULL,
            confidence REAL,
            review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ({_REVIEW_LIST})),
            reviewer TEXT,
            assigned_at TEXT NOT NULL,
            PRIMARY KEY (record_id, scheme_id, label_id)
        )
    """,
    "taxonomy_crosswalk": f"""
        CREATE TABLE taxonomy_crosswalk (
            source_scheme TEXT NOT NULL REFERENCES taxonomy_scheme(scheme_id),
            source_label TEXT NOT NULL,
            target_scheme TEXT NOT NULL REFERENCES taxonomy_scheme(scheme_id),
            target_label TEXT NOT NULL,
            mapping_relation TEXT NOT NULL CHECK (mapping_relation IN ({_MAPPING_LIST})),
            rationale TEXT,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ({_REVIEW_LIST})),
            version TEXT NOT NULL,
            PRIMARY KEY (source_scheme, source_label, target_scheme, target_label)
        )
    """,
    "provenance_assertion": """
        CREATE TABLE provenance_assertion (
            assertion_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            asserted_value TEXT,
            source_record_id TEXT REFERENCES record(record_id),
            source_locator TEXT,
            acquired_at TEXT NOT NULL,
            method TEXT NOT NULL,
            tool_or_model_version TEXT,
            confidence REAL,
            review_status TEXT NOT NULL DEFAULT 'pending'
        )
    """,
    "correction": """
        CREATE TABLE correction (
            correction_id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            proposed_value TEXT,
            evidence_locator TEXT,
            decision TEXT NOT NULL DEFAULT 'pending',
            reviewer TEXT,
            decided_at TEXT,
            applied_version TEXT
        )
    """,
    "annotation": f"""
        CREATE TABLE annotation (
            annotation_id TEXT PRIMARY KEY,
            record_id TEXT NOT NULL REFERENCES record(record_id),
            annotation_type TEXT NOT NULL,
            body TEXT,
            author TEXT,
            created_at TEXT,
            access_class TEXT NOT NULL DEFAULT 'restricted' CHECK (access_class IN ({_ACCESS_LIST}))
        )
    """,
    "quote": f"""
        CREATE TABLE quote (
            quote_id TEXT PRIMARY KEY,
            record_id TEXT NOT NULL REFERENCES record(record_id),
            person_id TEXT REFERENCES person(person_id),
            author_display TEXT,
            quote_verbatim TEXT NOT NULL,
            omissions_marked INTEGER NOT NULL DEFAULT 0 CHECK (omissions_marked IN (0, 1)),
            source_url TEXT,
            source_date TEXT,
            retrieved_at TEXT,
            thread_subject TEXT,
            context_note TEXT,
            context_before_sha256 TEXT,
            context_after_sha256 TEXT,
            public_access_checked_at TEXT,
            contact_data_removed INTEGER NOT NULL DEFAULT 0 CHECK (contact_data_removed IN (0, 1)),
            rights_review_status TEXT NOT NULL DEFAULT 'non_exportable' CHECK (rights_review_status IN ({_QUOTE_POLICY_LIST})),
            article_claim_id TEXT
        )
    """,
}


def create_connection(db_path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def build_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, dropping any pre-existing ones first (idempotent)."""
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in reversed(TABLE_ORDER):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    for table in TABLE_ORDER:
        conn.execute(DDL[table])
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def validate_schema(conn: sqlite3.Connection) -> list[str]:
    """Return a list of foreign-key/integrity violations (empty means valid)."""
    conn.execute("PRAGMA foreign_keys = ON")
    violations = [
        f"foreign key violation: table={row[0]} rowid={row[1]} refers to table={row[2]}"
        for row in conn.execute("PRAGMA foreign_key_check")
    ]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        violations.append(f"integrity_check failed: {integrity}")
    return violations
