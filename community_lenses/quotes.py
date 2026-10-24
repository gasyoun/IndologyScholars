"""Exact quotation register — H1898 Step 9.

Machinery for building the exact-quote evidence layer over the H1893 shared
contract:

- every quotation is verbatim: registration verifies the quote
  character-for-character against the pinned source text, with ellipses and
  bracketed omissions marked explicitly (``[...]`` / ``[…]``); if the exact
  wording or its context cannot be retained the quote is OMITTED — a
  paraphrase can never enter the register;
- every row carries author, record, thread/context, source URL/date,
  retrieval date, before/after context hashes, a public-access check, a
  contact-data-removal flag, a rights-review state and an
  ``article_claim_id``;
- closed/restricted corpora (nagari) are mechanically ``non_exportable``
  until an explicit approval record names approver, scope, date and
  permitted use — author preference for real quotes does not override it;
- every row pairs with aggregate evidence (numerator, denominator, unit,
  coverage status, snapshot id, method version) or an explicit
  ``aggregate_evidence_unavailable`` reason: a quotation may ILLUSTRATE an
  aggregate result, never establish its prevalence.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

QUOTES_PATH = REPO_ROOT / "curation" / "community_quotes.csv"
QUOTE_REVIEW_PATH = (
    REPO_ROOT
    / "analytics_output"
    / "community_lenses"
    / "review"
    / "quote_context_review.csv"
)

REGISTER_VERSION = "h1898-quotes-1.0.0"

# Corpora whose source community is closed/restricted: rows are forced
# non_exportable unless a complete explicit approval record is present.
CLOSED_CORPORA = ("nagari",)

RIGHTS_STATES = ("non_exportable", "exportable_approved", "pending_review")

OMISSION_MARKERS = ("[...]", "[…]")

# Observable, source-visible actions — the only vocabulary allowed for
# attributable behaviour. No intention/nationality/reputation inference.
OBSERVABLE_ACTIONS = (
    "asked",
    "answered",
    "supplied_reference",
    "announced",
    "disputed",
    "translated",
    "corrected",
    "requested",
    "reported",
    "shared_resource",
    "presented",
)

QUOTE_COLUMNS = [
    "quote_id",
    "corpus_id",
    "record_id",
    "person_id",
    "author_display",
    "behaviour",
    "quote_verbatim",
    "omissions_marked",
    "source_url",
    "source_date",
    "retrieved_at",
    "thread_subject",
    "context_note",
    "context_before_sha256",
    "context_after_sha256",
    "public_access_checked_at",
    "contact_data_removed",
    "rights_review_status",
    "rights_approver",
    "rights_approval_scope",
    "rights_approval_date",
    "rights_permitted_use",
    "article_claim_id",
    "agg_status",
    "agg_numerator",
    "agg_denominator",
    "agg_denominator_unit",
    "agg_coverage_status",
    "agg_snapshot_id",
    "agg_method_version",
    "agg_note",
    "register_version",
]

REVIEW_COLUMNS = [
    "quote_id",
    "corpus_id",
    "record_id",
    "author_display",
    "verification",
    "context_ruled_out",
    "rights_gate",
    "reviewer",
    "reviewed_date",
    "outcome",
    "note",
]

_CONTACT_RES = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                      # email
    re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)"),          # phone-ish
)


class QuoteError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Verbatim verification
# ---------------------------------------------------------------------------

def split_on_omissions(quote: str) -> list[str]:
    pattern = "|".join(re.escape(m) for m in OMISSION_MARKERS)
    return [seg for seg in re.split(pattern, quote) if seg != ""]


def has_omission_markers(quote: str) -> bool:
    return any(marker in quote for marker in OMISSION_MARKERS)


def verify_verbatim(quote: str, source_text: str) -> tuple[int, int]:
    """Verify ``quote`` appears character-for-character in ``source_text``.

    Without omission markers the quote must be one exact contiguous span.
    With markers, every segment must appear in order without overlap.
    Returns (start, end) of the full matched span in the source.
    Raises QuoteError when the source does not contain the exact wording —
    the caller must then OMIT the quote, never paraphrase it.
    """
    if not quote.strip():
        raise QuoteError("empty quote")
    segments = split_on_omissions(quote) if has_omission_markers(quote) else [quote]
    pos = 0
    start = None
    end = None
    for segment in segments:
        found = source_text.find(segment, pos)
        if found < 0:
            raise QuoteError(
                f"quote segment not found verbatim in pinned source: {segment[:60]!r}"
            )
        if start is None:
            start = found
        end = found + len(segment)
        pos = end
    assert start is not None and end is not None
    return start, end


def context_hashes(source_text: str, start: int, end: int) -> tuple[str, str]:
    """sha256 of the text before and after the matched span.

    Hashing (not storing) the surrounding messages keeps closed-list context
    reviewable locally without ever publishing raw neighbouring text.
    """
    before = hashlib.sha256(source_text[:start].encode("utf-8")).hexdigest()
    after = hashlib.sha256(source_text[end:].encode("utf-8")).hexdigest()
    return before, after


def contact_data_present(text: str) -> bool:
    return any(rx.search(text) for rx in _CONTACT_RES)


# ---------------------------------------------------------------------------
# Rights gate
# ---------------------------------------------------------------------------

def approval_complete(row: dict) -> bool:
    return all(
        (row.get(field) or "").strip()
        for field in (
            "rights_approver",
            "rights_approval_scope",
            "rights_approval_date",
            "rights_permitted_use",
        )
    )


def effective_rights_status(row: dict) -> str:
    """Mechanical rights gate.

    - closed-corpus rows without a COMPLETE approval record are
      ``non_exportable`` no matter what the row claims;
    - no row anywhere may be ``exportable_approved`` without a complete
      approval record;
    - otherwise the recorded state stands (default ``pending_review``).
    """
    recorded = row.get("rights_review_status") or "pending_review"
    if recorded not in RIGHTS_STATES:
        raise QuoteError(f"unknown rights_review_status {recorded!r}")
    if row["corpus_id"] in CLOSED_CORPORA and not approval_complete(row):
        return "non_exportable"
    if recorded == "exportable_approved" and not approval_complete(row):
        return "non_exportable"
    return recorded


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_quote(row: dict, source_text: str) -> dict:
    """Validate one candidate quote against its pinned source text and
    return the completed register row. Fail-closed on every gate."""
    required = (
        "quote_id",
        "corpus_id",
        "record_id",
        "author_display",
        "behaviour",
        "quote_verbatim",
        "article_claim_id",
        "retrieved_at",
    )
    missing = [f for f in required if not (row.get(f) or "").strip()]
    if missing:
        raise QuoteError(f"quote {row.get('quote_id')!r}: missing required fields {missing}")

    if row["behaviour"] not in OBSERVABLE_ACTIONS:
        raise QuoteError(
            f"quote {row['quote_id']}: behaviour {row['behaviour']!r} is not an "
            f"observable source action (allowed: {OBSERVABLE_ACTIONS})"
        )

    start, end = verify_verbatim(row["quote_verbatim"], source_text)
    before_sha, after_sha = context_hashes(source_text, start, end)

    completed = dict(row)
    completed["omissions_marked"] = "1" if has_omission_markers(row["quote_verbatim"]) else "0"
    completed["context_before_sha256"] = before_sha
    completed["context_after_sha256"] = after_sha
    completed["rights_review_status"] = effective_rights_status(row)
    completed["contact_data_removed"] = (
        "0" if contact_data_present(row["quote_verbatim"]) else "1"
    )
    completed["register_version"] = REGISTER_VERSION

    validate_aggregate_pointer(completed)

    if completed["rights_review_status"] == "exportable_approved":
        if completed["contact_data_removed"] != "1":
            raise QuoteError(
                f"quote {row['quote_id']}: contact data present in an exportable row"
            )
    return completed


def validate_aggregate_pointer(row: dict) -> None:
    """Every quote pairs with aggregate evidence or an explicit gap."""
    status = (row.get("agg_status") or "").strip()
    if status == "aggregate_evidence_unavailable":
        if not (row.get("agg_note") or "").strip():
            raise QuoteError(
                f"quote {row['quote_id']}: aggregate_evidence_unavailable requires agg_note reason"
            )
        return
    if status != "available":
        raise QuoteError(
            f"quote {row['quote_id']}: agg_status must be 'available' or "
            f"'aggregate_evidence_unavailable', got {status!r}"
        )
    required = (
        "agg_numerator",
        "agg_denominator",
        "agg_denominator_unit",
        "agg_coverage_status",
        "agg_snapshot_id",
        "agg_method_version",
    )
    missing = [f for f in required if not (row.get(f) or "").strip()]
    if missing:
        raise QuoteError(f"quote {row['quote_id']}: aggregate pointer missing {missing}")
    int(row["agg_numerator"])
    int(row["agg_denominator"])


# ---------------------------------------------------------------------------
# Export gate + persistence
# ---------------------------------------------------------------------------

def exportable_rows(rows: list[dict]) -> list[dict]:
    """The ONLY sanctioned way to select rows for any public artifact."""
    out = []
    for row in rows:
        if effective_rights_status(row) != "exportable_approved":
            continue
        if contact_data_present(row["quote_verbatim"]):
            continue
        out.append(row)
    return out


def insert_quote(conn: sqlite3.Connection, row: dict) -> None:
    """Mirror a completed register row into the shared-contract quote table."""
    conn.execute(
        """INSERT OR REPLACE INTO quote
           (quote_id, record_id, person_id, author_display, quote_verbatim,
            omissions_marked, source_url, source_date, retrieved_at,
            thread_subject, context_note, context_before_sha256,
            context_after_sha256, public_access_checked_at,
            contact_data_removed, rights_review_status, article_claim_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["quote_id"],
            row["record_id"],
            row.get("person_id") or None,
            row["author_display"],
            row["quote_verbatim"],
            int(row["omissions_marked"]),
            row.get("source_url"),
            row.get("source_date"),
            row["retrieved_at"],
            row.get("thread_subject"),
            row.get("context_note"),
            row["context_before_sha256"],
            row["context_after_sha256"],
            row.get("public_access_checked_at"),
            int(row["contact_data_removed"]),
            row["rights_review_status"],
            row["article_claim_id"],
        ),
    )
    conn.commit()


def write_quotes(rows: list[dict], path: Path = QUOTES_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUOTE_COLUMNS)
        writer.writeheader()
        writer.writerows({c: row.get(c, "") for c in QUOTE_COLUMNS} for row in rows)
    return path


def write_review_queue(rows: list[dict], path: Path = QUOTE_REVIEW_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows({c: row.get(c, "") for c in REVIEW_COLUMNS} for row in rows)
    return path
