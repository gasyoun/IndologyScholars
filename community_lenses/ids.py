"""Stable-ID rules for the shared community-lenses record space.

Per ARCHITECTURE §"record": ``record_id`` is a source-namespaced key that must
never embed a mutable title, name, topic, or classification. Native stable IDs
(``PRES_*``, RFC ``Message-ID``, VK owner/post IDs, Atlas message IDs) are
preserved untouched as ``source_record_id``; a content hash is a documented
fallback only, never the default.
"""

from __future__ import annotations

import base64
import hashlib
import unicodedata

CORPUS_IDS = ("conferences", "nagari", "vk_ors", "indology_l", "bvp")

# A source_record_id must not contain the record-id separator or whitespace
# that would make the namespaced key ambiguous to split back apart. A
# fallback-hash identity (see fallback_message_id_hash) is tracked via
# record.source_record_id_method='fallback_hash', not via a ':'-prefixed
# source_record_id, so ':' stays reserved purely for the corpus_id separator.
_FORBIDDEN_ID_CHARS = (":", "\n", "\r", "\t")


class InvalidRecordId(ValueError):
    pass


def validate_corpus_id(corpus_id: str) -> None:
    if corpus_id not in CORPUS_IDS:
        raise InvalidRecordId(
            f"unknown corpus_id {corpus_id!r}; expected one of {CORPUS_IDS}"
        )


def validate_source_record_id(source_record_id: str) -> None:
    if not source_record_id:
        raise InvalidRecordId("source_record_id must be non-empty")
    for ch in _FORBIDDEN_ID_CHARS:
        if ch in source_record_id:
            raise InvalidRecordId(
                f"source_record_id {source_record_id!r} contains forbidden "
                f"character {ch!r}"
            )


def make_record_id(corpus_id: str, source_record_id: str) -> str:
    """Build the namespaced shared key ``<corpus_id>:<source_record_id>``.

    The native ``source_record_id`` is preserved byte-for-byte; only the
    corpus prefix is added.
    """
    validate_corpus_id(corpus_id)
    validate_source_record_id(source_record_id)
    return f"{corpus_id}:{source_record_id}"


def parse_record_id(record_id: str) -> tuple[str, str]:
    """Split a namespaced record_id back into (corpus_id, source_record_id)."""
    if ":" not in record_id:
        raise InvalidRecordId(f"record_id {record_id!r} is missing the corpus prefix")
    corpus_id, _, source_record_id = record_id.partition(":")
    validate_corpus_id(corpus_id)
    validate_source_record_id(source_record_id)
    return corpus_id, source_record_id


def normalize_message_id(raw_message_id: str) -> str:
    """Normalize an RFC Message-ID for deterministic fallback hashing.

    Strips surrounding angle brackets/whitespace and applies NFC + casefold so
    that trivially different renderings of the same header hash identically.
    """
    text = raw_message_id.strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1]
    text = unicodedata.normalize("NFC", text).strip().casefold()
    return text


def fallback_message_id_hash(raw_message_id: str) -> str:
    """Base32 SHA-256 fallback identity for mail with no stable archive ID.

    Used only when a source has no immutable native record identifier; the
    fact that a fallback method was used must be recorded separately (e.g. in
    ``record.status`` / adapter reconciliation notes), never silently.
    """
    normalized = normalize_message_id(raw_message_id)
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii").rstrip("=").lower()


def content_sha256(text: str) -> str:
    """Integrity hash for record content; never a primary ID when a native ID exists."""
    normalized = unicodedata.normalize("NFC", text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
