"""Nāgarī closed Google Group archive adapter — H1895 Wave 1B.

Reads ``nagari/data/nagari.db`` (built by the existing
``nagari_group_archive.ingest`` module from the group's own Takeout mbox
export — never reimplemented here) and loads it into the H1893 contract.
Reuses the group's own native two-level topic taxonomy
(``nagari_group_archive.taxonomy``) and redaction defaults
(``nagari_group_archive.redact``) verbatim; never resolves a message author
to a ``person`` row (identity linkage is H1898's scope), and never emits a
``quote`` (selection/rights review is H1898's scope too).

If no ``nagari.db`` exists yet (the raw mbox has not been ingested on this
machine), this degrades gracefully to an explicit ``coverage_status =
"unavailable"`` placeholder rather than crashing or fabricating data.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from . import _shared
from ..ids import fallback_message_id_hash, make_record_id, normalize_message_id

REPO_ROOT = _shared.REPO_ROOT
CORPUS_ID = "nagari"

# Candidate locations for a built nagari.db: this worktree's own package data
# dir first, then the sibling main-tree checkout (worktrees never carry the
# gitignored mbox/db themselves; nagari_group_archive.ingest's own DEFAULT_DUMP
# already anticipates this split by pointing at the main tree).
_CANDIDATE_DB_PATHS = (
    REPO_ROOT / "nagari" / "data" / "nagari.db",
    # The canonical built db on this machine (H1898 §Inputs pins it here); the
    # nagari_group_archive path below was the pre-H1898 guess and no longer
    # exists. Keeping both means neither layout silently degrades the lens to
    # "unavailable" while a real db sits on disk — the H1899 compatibility fix
    # recorded in analytics_output/community_lenses/reports/comparison_validity.md.
    Path(r"C:\Users\user\Documents\GitHub\IndologyScholars\nagari\data\nagari.db"),
    Path(r"C:\Users\user\Documents\GitHub\IndologyScholars\nagari\nagari_group_archive\data\nagari.db"),
)

_NATIVE_SCHEME_ID = "nagari_native_taxonomy"


def _find_db() -> Path | None:
    for path in _CANDIDATE_DB_PATHS:
        if path.exists():
            return path
    return None


def _import_taxonomy_and_redact():
    """Import the nagari package's own taxonomy/redact modules (reuse, not reimplement)."""
    nagari_pkg_dir = REPO_ROOT / "nagari"
    if str(nagari_pkg_dir) not in sys.path:
        sys.path.insert(0, str(nagari_pkg_dir))
    from nagari_group_archive import redact, taxonomy  # noqa: PLC0415

    return taxonomy, redact


def build_fixture() -> dict:
    db_path = _find_db()
    if db_path is None:
        return _shared.unavailable_fixture(
            corpus_id=CORPUS_ID,
            title="Nāgarī closed Google Group archive",
            native_unit="message",
            rights_basis="closed Google Group; group-owner permission on file, not republished in full",
            gap_note=(
                "no built nagari.db found; the raw Takeout mbox exists at "
                r"C:\Users\user\Documents\GitHub\IndologyScholars\nagari-2005-2026 "
                "but has not been ingested via nagari_group_archive.ingest.build() "
                "on this machine"
            ),
        )

    taxonomy, redact = _import_taxonomy_and_redact()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        messages = [dict(row) for row in conn.execute("SELECT * FROM messages ORDER BY id")]
    finally:
        conn.close()

    snapshot_id = f"{CORPUS_ID}:pilot:{_shared.file_acquired_at(db_path)[:10]}"
    manifest = _shared.build_manifest(
        corpus_id=CORPUS_ID,
        snapshot_id=snapshot_id,
        coverage_status="pilot",
        source_version=f"nagari.db@{_shared.file_sha256(db_path)[:12]} (first {len(messages)} mbox messages)",
        acquired_at=_shared.file_acquired_at(db_path),
        source_sha256=_shared.file_sha256(db_path),
        rights_basis="closed Google Group; group-owner permission on file, not republished in full",
        coverage_start=min((m["date_utc"][:10] for m in messages if m["date_utc"]), default=None),
        coverage_end=max((m["date_utc"][:10] for m in messages if m["date_utc"]), default=None),
        cutoff_date=_shared.file_acquired_at(db_path)[:10],
    )

    containers: dict[str, dict] = {}
    records = []
    record_names = []
    record_relations = []
    classification_assignments = []

    known_message_ids: dict[str, str] = {}  # normalized native message-id -> record_id
    pending_replies: list[tuple[str, str]] = []  # (subject_record_id, normalized in_reply_to)

    for msg in messages:
        gm_thrid = (msg.get("gm_thrid") or "").strip()
        raw_message_id = (msg.get("message_id") or "").strip()

        if raw_message_id:
            source_record_id = raw_message_id
            source_record_id_method = "native"
        else:
            # No stable native archive ID for this message: fall back to a
            # documented content hash, never silently (ids.fallback_message_id_hash).
            composite = f"{msg['id']}:{msg.get('subject_clean', '')}:{msg.get('date_utc', '')}"
            source_record_id = fallback_message_id_hash(composite)
            source_record_id_method = "fallback_hash"

        record_id = make_record_id(CORPUS_ID, source_record_id)
        if raw_message_id:
            known_message_ids[normalize_message_id(raw_message_id)] = record_id

        container_id = None
        if gm_thrid:
            container_id = f"{CORPUS_ID}:container:{gm_thrid}"
            if container_id not in containers:
                containers[container_id] = {
                    "container_id": container_id,
                    "corpus_id": CORPUS_ID,
                    "source_snapshot_id": snapshot_id,
                    "parent_container_id": None,
                    "container_type": "thread",
                    "source_native_id": gm_thrid,
                    "title": msg.get("subject_clean") or msg.get("subject"),
                    "date_from": msg.get("date_utc"),
                    "date_to": msg.get("date_utc"),
                    "source_url": None,
                }
            else:
                thread = containers[container_id]
                if msg.get("date_utc"):
                    thread["date_to"] = max(thread["date_to"] or "", msg["date_utc"])
                    thread["date_from"] = min(thread["date_from"] or msg["date_utc"], msg["date_utc"])

        records.append(
            {
                "record_id": record_id,
                "corpus_id": CORPUS_ID,
                "source_record_id": source_record_id,
                "source_record_id_method": source_record_id_method,
                "container_id": container_id,
                "record_type": "message",
                "title_or_subject": msg.get("subject_clean") or msg.get("subject") or None,
                "body_locator": (
                    "nagari/nagari_group_archive (gitignored raw mbox; not redistributed) "
                    f"mbox_index={msg['id']}"
                ),
                "created_at": msg.get("date_utc") or None,
                "language": None,
                "canonical_url": None,
                "content_sha256": None,
                "status": "active",
                "is_partial_2026": 1 if (msg.get("year") == 2026) else 0,
                "access_class": "restricted",
                "source_snapshot_id": snapshot_id,
            }
        )

        # Redaction default: names are public, addresses are not (redact.mask_name).
        from_email = msg.get("from_email") or ""
        record_names.append(
            {
                "record_id": record_id,
                "ordinal": 1,
                "role": "author",
                "name_as_source": msg.get("from_name") or "",
                "affiliation_as_source": None,
                "source_account_id": redact.mask_name(from_email) if from_email else None,
                "person_id": None,  # never auto-link people (H1898's scope)
            }
        )

        in_reply_to = (msg.get("in_reply_to") or "").strip()
        if in_reply_to:
            pending_replies.append((record_id, normalize_message_id(in_reply_to)))

        # Native topic: verbatim subject line (matches H1893's contract for this scheme).
        subject_value = msg.get("subject_clean") or msg.get("subject")
        if subject_value:
            classification_assignments.append(
                {
                    "record_id": record_id,
                    "scheme_id": "native_topic",
                    "label_id": "nagari:group_thread_topic",
                    "value": subject_value,
                    "evidence_span": "subject",
                    "method": "thread_subject",
                    "method_version": "1.0.0",
                    "confidence": 1.0,
                    "review_status": "not_applicable",
                    "reviewer": None,
                    "assigned_at": manifest.acquired_at,
                }
            )

        # Reuse the group's own native two-level curated taxonomy, verbatim
        # (never a crosswalk onto shared_topic -- that is H1897's scope).
        text_for_classify = " ".join(filter(None, [msg.get("subject"), msg.get("subject_clean")]))
        classification = taxonomy.classify(text_for_classify)
        if classification.primary != "разное":
            classification_assignments.append(
                {
                    "record_id": record_id,
                    "scheme_id": _NATIVE_SCHEME_ID,
                    "label_id": f"{classification.parent}/{classification.primary}",
                    "value": classification.primary,
                    "evidence_span": "subject",
                    "method": "nagari_group_archive.taxonomy.classify (reused verbatim)",
                    "method_version": "1.0.0",
                    "confidence": None,
                    "review_status": "not_applicable",
                    "reviewer": None,
                    "assigned_at": manifest.acquired_at,
                }
            )

    for subject_record_id, normalized_target in pending_replies:
        object_record_id = known_message_ids.get(normalized_target)
        if object_record_id and object_record_id != subject_record_id:
            record_relations.append(
                {
                    "subject_record_id": subject_record_id,
                    "predicate": "reply_to",
                    "object_record_id": object_record_id,
                    "evidence_locator": "In-Reply-To header",
                }
            )

    return {
        "corpus": {
            "corpus_id": CORPUS_ID,
            "title": "Nāgarī closed Google Group archive",
            "medium": "mailing_list",
            "forum_orientation": "many_to_many_threaded",
            "native_unit": "message",
            "canonical_url": None,
            "rights_status": "closed_group_archive_republished_with_permission",
        },
        "manifest": manifest.to_dict(),
        "containers": list(containers.values()),
        "records": records,
        "record_names": record_names,
        "record_relations": record_relations,
        "classification_assignments": classification_assignments,
        "annotations": [],
        "quotes": [],
        "_extra_schemes": [
            {
                "scheme_id": _NATIVE_SCHEME_ID,
                "name": "Nāgarī native two-level taxonomy",
                # owner_corpus_id is left NULL (not "nagari") purely so this
                # scheme can be registered before populate_corpus() inserts the
                # `corpus` row it would otherwise FK against; is_shared_axis=0
                # and the description already record that it is nagari-owned.
                "owner_corpus_id": None,
                "is_shared_axis": 0,
                "version": "1.0.0",
                "description": (
                    "Nagari-owned (not a shared axis); reused verbatim from "
                    "nagari_group_archive.taxonomy.PARENTS (parent/child regex "
                    "classifier); not crosswalked onto shared_topic (H1897's scope)."
                ),
            }
        ],
    }


def insert_extra_schemes(conn: sqlite3.Connection, fixture: dict) -> None:
    """Register this adapter's own native taxonomy_scheme row(s); call before populate_corpus."""
    for scheme in fixture.get("_extra_schemes", []):
        conn.execute(
            """INSERT OR IGNORE INTO taxonomy_scheme
               (scheme_id, name, owner_corpus_id, is_shared_axis, version, description)
               VALUES (:scheme_id, :name, :owner_corpus_id, :is_shared_axis, :version, :description)""",
            scheme,
        )


def coverage_report(fixture: dict) -> str:
    manifest = fixture["manifest"]
    records = fixture["records"]
    is_available = manifest["coverage_status"] != "unavailable"
    return _shared.render_coverage_report(
        corpus_id=CORPUS_ID,
        title="Nāgarī closed Google Group",
        native_unit="message",
        coverage_status=manifest["coverage_status"],
        manifest_snapshot_id=manifest["snapshot_id"],
        date_range=f"{manifest.get('coverage_start') or '?'} .. {manifest.get('coverage_end') or '?'}",
        denominator_definition="one row per parsed mbox message (nagari.db `messages` table)",
        included=len(records) if is_available else 0,
        excluded=0,
        failures=0,
        completeness_status=(
            f"pilot slice only ({len(records)} of the full 2005-2026 archive) -- "
            "run nagari_group_archive.ingest.build() without --limit for the full ingest"
            if is_available
            else "unavailable on this machine"
        ),
        notes=[
            "Never auto-links a message author to a `person` row -- identity linkage is H1898's scope.",
            "record_name.source_account_id is redacted via nagari_group_archive.redact.mask_name "
            "(names are public per group convention, addresses are not).",
            "Native topic (`native_topic` scheme) is the verbatim subject line; the native two-level "
            "parent/child taxonomy is reused verbatim under its own `nagari_native_taxonomy` scheme, "
            "not crosswalked onto shared_topic.",
            "quote_policy defaults to non_exportable at the schema level; this adapter emits zero quotes.",
        ],
    )
