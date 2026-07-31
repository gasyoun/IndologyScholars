"""VK "Общество ревнителей санскрита" wall adapter — H1895 Wave 1B.

Reads the existing ``vk_ors_archive``-built ``vk_ors.db`` (posts + per-post
``hashtags`` extracted by that package's own ``RE_HASHTAG`` regex — reused
verbatim here, never reimplemented) and loads it into the H1893 contract.
Real, self-applied hashtags are the only native_topic signal used; no
keyword-derived topic is fabricated in their place (this repo has no
per-post keyword classifier for VK, only aggregate term counts in
``vk-ors/data/processed/post_terms.csv``, which cannot be attributed to a
single post and is deliberately not used here). Never invents a distinct
participant/thread identity: this is one broadcast account's public wall,
not a many-to-many forum, so every post's sole ``record_name`` is the page
account itself.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from . import _shared
from ..ids import make_record_id

REPO_ROOT = _shared.REPO_ROOT
CORPUS_ID = "vk_ors"

_CANDIDATE_DB_PATHS = (
    REPO_ROOT / "vk-ors" / "data" / "vk_ors.db",
    Path(r"C:\Users\user\Documents\GitHub\IndologyScholars\vk-ors\data\vk_ors.db"),
)

_URL_RE = re.compile(r"wall(-?\d+)_(\d+)")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")

_PAGE_TITLE = "Общество ревнителей санскрита"
_PAGE_URL = "https://vk.com/sanskrit_ors"


def _find_db() -> Path | None:
    for path in _CANDIDATE_DB_PATHS:
        if path.exists():
            return path
    return None


def build_fixture() -> dict:
    db_path = _find_db()
    if db_path is None:
        return _shared.unavailable_fixture(
            corpus_id=CORPUS_ID,
            title='VK "Общество ревнителей санскрита" wall archive',
            native_unit="post",
            rights_basis="public VK wall, fetched via wall.get with no auth beyond a public token",
            gap_note=f"no vk_ors.db found under {', '.join(str(p) for p in _CANDIDATE_DB_PATHS)}",
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        posts = [dict(row) for row in conn.execute("SELECT * FROM posts ORDER BY id")]
        hashtags_by_post: dict[int, list[str]] = {}
        for row in conn.execute("SELECT post_id, tag FROM hashtags ORDER BY post_id, tag"):
            hashtags_by_post.setdefault(row["post_id"], []).append(row["tag"])
    finally:
        conn.close()

    snapshot_id = f"{CORPUS_ID}:{_shared.file_acquired_at(db_path)[:10]}"
    manifest = _shared.build_manifest(
        corpus_id=CORPUS_ID,
        snapshot_id=snapshot_id,
        coverage_status="complete",
        source_version=f"vk_ors.db@{_shared.file_sha256(db_path)[:12]}",
        acquired_at=_shared.file_acquired_at(db_path),
        source_sha256=_shared.file_sha256(db_path),
        rights_basis="public VK wall, fetched via wall.get with no auth beyond a public token",
        coverage_start=min((p["date_utc"][:10] for p in posts if p["date_utc"]), default=None),
        coverage_end=max((p["date_utc"][:10] for p in posts if p["date_utc"]), default=None),
        cutoff_date=_shared.file_acquired_at(db_path)[:10],
    )

    owner_id = "unknown_owner"
    match_first = next((m for p in posts if (m := _URL_RE.search(p["url"] or ""))), None)
    if match_first:
        owner_id = match_first.group(1)
    container_id = f"{CORPUS_ID}:container:wall"

    records = []
    record_names = []
    classification_assignments = []
    failures = 0

    for post in posts:
        url = post.get("url") or ""
        match = _URL_RE.search(url)
        if match is None:
            # Native VK addressing (owner_id_post_id) cannot be recovered from
            # this row's url; skip rather than invent a comparable identity.
            failures += 1
            continue
        source_record_id = f"{match.group(1)}_{match.group(2)}"
        record_id = make_record_id(CORPUS_ID, source_record_id)
        text = post.get("text") or ""

        records.append(
            {
                "record_id": record_id,
                "corpus_id": CORPUS_ID,
                "source_record_id": source_record_id,
                "source_record_id_method": "native",
                "container_id": container_id,
                "record_type": "post",
                "title_or_subject": None,
                "body_locator": f"vk-ors/data/vk_ors.db#posts.id={post['id']}",
                "created_at": post.get("date_utc") or None,
                "language": "ru" if _CYRILLIC_RE.search(text) else None,
                "canonical_url": url or None,
                "content_sha256": _shared.text_sha256(text) if text else None,
                "status": "active",
                "is_partial_2026": 1 if (post.get("year") == 2026) else 0,
                "access_class": "public",
                "source_snapshot_id": snapshot_id,
            }
        )

        record_names.append(
            {
                "record_id": record_id,
                "ordinal": 1,
                "role": "author",
                "name_as_source": _PAGE_TITLE,
                "affiliation_as_source": None,
                "source_account_id": owner_id,
                "person_id": None,  # one broadcast account; never a fabricated participant identity
            }
        )

        tags = hashtags_by_post.get(post["id"])
        if tags:
            # A post's native_topic row is fixed to label_id='vk_ors:hashtag'
            # per the H1893 codebook contract, so every distinct real hashtag
            # on one post is folded into a single comma-joined value (the
            # native_topic.csv row's own worked example uses exactly this
            # "#tag1, #tag2" format) -- never a keyword-derived guess.
            classification_assignments.append(
                {
                    "record_id": record_id,
                    "scheme_id": "native_topic",
                    "label_id": "vk_ors:hashtag",
                    "value": ", ".join(f"#{tag}" for tag in sorted(set(tags))),
                    "evidence_span": "hashtag",
                    "method": "insights_hashtag_extraction",
                    "method_version": "1.0.0",
                    "confidence": 1.0,
                    "review_status": "not_applicable",
                    "reviewer": None,
                    "assigned_at": manifest.acquired_at,
                }
            )

    return {
        "corpus": {
            "corpus_id": CORPUS_ID,
            "title": _PAGE_TITLE,
            "medium": "social_media_wall",
            "forum_orientation": "one_to_many_broadcast_with_comments",
            "native_unit": "post",
            "canonical_url": _PAGE_URL,
            "rights_status": "public_vk_wall",
        },
        "manifest": manifest.to_dict(),
        "containers": [
            {
                "container_id": container_id,
                "corpus_id": CORPUS_ID,
                "source_snapshot_id": snapshot_id,
                "parent_container_id": None,
                "container_type": "wall",
                "source_native_id": owner_id,
                "title": _PAGE_TITLE,
                "date_from": manifest.coverage_start,
                "date_to": manifest.coverage_end,
                "source_url": _PAGE_URL,
            }
        ],
        "records": records,
        "record_names": record_names,
        "record_relations": [],
        "classification_assignments": classification_assignments,
        "annotations": [],
        "quotes": [],
        "_failures": failures,
    }


def coverage_report(fixture: dict) -> str:
    manifest = fixture["manifest"]
    records = fixture["records"]
    is_available = manifest["coverage_status"] != "unavailable"
    return _shared.render_coverage_report(
        corpus_id=CORPUS_ID,
        title="VK Общество ревнителей санскрита",
        native_unit="post",
        coverage_status=manifest["coverage_status"],
        manifest_snapshot_id=manifest["snapshot_id"],
        date_range=f"{manifest.get('coverage_start') or '?'} .. {manifest.get('coverage_end') or '?'}",
        denominator_definition="one row per post id in vk_ors.db's `posts` table",
        included=len(records),
        excluded=fixture.get("_failures", 0),
        failures=fixture.get("_failures", 0),
        completeness_status="complete for the exported wall" if is_available else "unavailable",
        notes=[
            "Only real, self-applied hashtags (vk_ors.db `hashtags`, itself extracted from post "
            "text by vk_ors_archive.ingest's own RE_HASHTAG) are used as native_topic evidence.",
            "No keyword-derived topic is substituted: this repo has only aggregate per-corpus "
            "term counts (vk-ors/data/processed/post_terms.csv), not a per-post keyword classifier, "
            "so it cannot be attributed to an individual post without fabrication.",
            "One broadcast account, no reply graph: every record_name is the page account itself; "
            "no comparable participant/thread identity is invented for what is a single-page wall.",
        ],
    )
