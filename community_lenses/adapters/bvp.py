"""Bharatiya Vidvat Parishat (BVP) Google Group adapter — H1896 Wave 1C.

Reads the frozen, local, gitignored acquisition products of ``bvp/scrape.py``
(``bvp/data/meta/state.json`` + ``bvp/data/parsed/*.json``) and loads them into
the H1893 shared contract. This adapter is a pure reader: it never issues a
network request, never repairs a source gap, and never upgrades the pinned
``bvp/data/meta/state.json`` coverage status.

BVP is treated as the study's principal India-centred Sanskrit forum because
that is Gasūns' expert corpus-selection intuition (documented in H1896) --
**not** evidence that BVP statistically represents all Indian Sanskrit
scholarship. The public listing denominator is 23,467 conversations; only the
30 conversations on the server-rendered first listing page have been
enumerated (``bvp/README.md``). ``coverage_status`` therefore stays
``"partial"`` until a separate bounded pagination unit reconciles the full
listing, and every population-level claim (annual trend, person-share,
topic-share, whole-population) is mechanically disabled via
``population_metrics_allowed`` / ``require_population_metrics`` until the
manifest itself satisfies H1893's complete-coverage predicate
(``coverage_status == "complete"``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import _shared
from ..ids import make_record_id

REPO_ROOT = _shared.REPO_ROOT
CORPUS_ID = "bvp"

BVP_DIR = REPO_ROOT / "bvp" / "data"
STATE_PATH = BVP_DIR / "meta" / "state.json"
PARSED_DIR = BVP_DIR / "parsed"

GROUP_URL = "https://groups.google.com/g/bvparishat"
GROUP_TITLE = "Bharatiya Vidvat Parishat (BVP) Google Group"
RIGHTS_BASIS = (
    "public Google Group (groups.google.com/g/bvparishat), server-rendered and "
    "publicly viewable without login or membership; individual posters retain "
    "authorship of their own messages"
)

# codebooks/native_topic.csv reserves 'bvp:native_category' as a placeholder
# for "whatever native category scheme the BVP source turns out to expose
# once acquired" -- but the acquired evidence is a free-text conversation/
# message subject line, not a category scheme, and codebooks/*.csv is out of
# H1896's owned-file scope (see the handoff's Scope section). The generic
# 'other' row ("a recognizable native topic that does not fit an existing
# per-source row above") is the codebook's own designed fallback for exactly
# this case, so it is used verbatim here instead.
_NATIVE_TOPIC_LABEL_ID = "other"


class DuplicateNativeId(ValueError):
    pass


class PopulationMetricsDisabled(RuntimeError):
    pass


def _epoch_to_iso(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _load_parsed_conversations(conversation_ids: list[str]) -> dict[str, dict]:
    """Load parsed/<id>.json for each id that actually has a parsed file.

    An id in ``state["discovered"]`` with no matching parsed file is a real,
    honest gap (an interrupted run) -- the caller sees it as missing from the
    returned dict, never as a fabricated empty conversation.
    """
    conversations: dict[str, dict] = {}
    for conversation_id in conversation_ids:
        path = PARSED_DIR / f"{conversation_id}.json"
        if path.exists():
            conversations[conversation_id] = json.loads(path.read_text(encoding="utf-8"))
    return conversations


def _build_from_state(
    state: dict,
    conversations: dict[str, dict],
    *,
    state_sha256: str,
) -> dict:
    """Pure transform: state.json + parsed conversation dicts -> H1893 fixture.

    No disk I/O -- independently testable with synthetic ``state``/
    ``conversations`` for partial/incomplete/exclusion/parse-failure/
    duplicate-ID/ordering/interrupted-manifest/denominator-mismatch cases.
    """
    coverage_status = state["coverage_status"]
    listing = state.get("listing", {})
    counts = state.get("counts", {})
    displayed_total = listing.get("displayed_total")
    discovered_ids = sorted(state.get("discovered", {}).keys())
    conversations_parse_failed = sorted(set(discovered_ids) - set(conversations.keys()))

    snapshot_id = f"{CORPUS_ID}:{coverage_status}:{state['updated_at'][:10]}:{state_sha256[:12]}"

    containers: dict[str, dict] = {}
    records: list[dict] = []
    record_names: list[dict] = []
    classification_assignments: list[dict] = []
    annotations: list[dict] = []

    seen_message_ids: dict[str, str] = {}  # native message_id -> record_id that claimed it
    messages_total = 0
    messages_incomplete = 0
    created_dates: list[str] = []

    for conversation_id in sorted(conversations.keys()):
        conv = conversations[conversation_id]
        conv_subject = conv.get("subject") or None
        conv_url = conv.get("url") or GROUP_URL
        container_id = f"{CORPUS_ID}:container:{conversation_id}"

        messages = conv.get("messages", [])
        for msg in messages:
            messages_total += 1
            native_message_id = msg["message_id"]

            if native_message_id in seen_message_ids:
                raise DuplicateNativeId(
                    f"duplicate native message_id {native_message_id!r} in conversation "
                    f"{conversation_id!r}; already claimed by record "
                    f"{seen_message_ids[native_message_id]!r}"
                )

            record_id = make_record_id(CORPUS_ID, native_message_id)
            seen_message_ids[native_message_id] = record_id

            created_at = _epoch_to_iso(msg.get("timestamp_epoch"))
            if created_at:
                created_dates.append(created_at[:10])

            author_display = msg.get("author_display") or ""
            body_text_sha = msg.get("body_text_sha256")
            rendered_sha = msg.get("rendered_text_sha256")
            is_incomplete = not (author_display and body_text_sha)
            if is_incomplete:
                messages_incomplete += 1

            if container_id not in containers:
                containers[container_id] = {
                    "container_id": container_id,
                    "corpus_id": CORPUS_ID,
                    "source_snapshot_id": snapshot_id,
                    "parent_container_id": None,
                    "container_type": "conversation",
                    "source_native_id": conversation_id,
                    "title": conv_subject,
                    "date_from": None,
                    "date_to": None,
                    "source_url": conv_url,
                }

            records.append(
                {
                    "record_id": record_id,
                    "corpus_id": CORPUS_ID,
                    "source_record_id": native_message_id,
                    "source_record_id_method": "native",
                    "container_id": container_id,
                    "record_type": "message",
                    "title_or_subject": msg.get("subject") or None,
                    "body_locator": (
                        f"bvp/data/parsed/{conversation_id}.json#message_id={native_message_id} "
                        f"(parse_source={conv.get('parse_source', 'unknown')})"
                    ),
                    "created_at": created_at,
                    "language": None,
                    "canonical_url": conv_url,
                    "content_sha256": body_text_sha or rendered_sha,
                    "status": "active",
                    "is_partial_2026": 1 if (created_at and created_at.startswith("2026")) else 0,
                    "access_class": "public",
                    "source_snapshot_id": snapshot_id,
                }
            )

            if author_display:
                record_names.append(
                    {
                        "record_id": record_id,
                        "ordinal": 1,
                        "role": "author",
                        "name_as_source": author_display,
                        "affiliation_as_source": None,
                        "source_account_id": msg.get("author_native_id") or None,
                        "person_id": None,  # identity linkage is H1898's scope
                    }
                )

            subject_value = msg.get("subject") or conv_subject
            if subject_value:
                classification_assignments.append(
                    {
                        "record_id": record_id,
                        "scheme_id": "native_topic",
                        "label_id": _NATIVE_TOPIC_LABEL_ID,
                        "value": subject_value,
                        "evidence_span": "subject",
                        "method": "conversation_or_message_subject_line",
                        "method_version": "1.0.0",
                        "confidence": 1.0,
                        "review_status": "not_applicable",
                        "reviewer": None,
                        "assigned_at": state["updated_at"],
                    }
                )

            if is_incomplete:
                annotations.append(
                    {
                        "annotation_id": f"{CORPUS_ID}:incomplete:{native_message_id}",
                        "record_id": record_id,
                        "annotation_type": "incomplete_record",
                        "body": (
                            "native message missing a public author display and/or body text "
                            f"(parse_source={conv.get('parse_source', 'unknown')}); kept as an "
                            "explicit record, excluded from content/person-denominator percentages "
                            "per bvp_source_assessment.md, never silently dropped or fabricated"
                        ),
                        "author": "community_lenses.adapters.bvp",
                        "created_at": state["updated_at"],
                        "access_class": "public",
                    }
                )

        if messages and containers[container_id]["date_from"] is None:
            dates = [m for m in (_epoch_to_iso(mm.get("timestamp_epoch")) for mm in messages) if m]
            if dates:
                containers[container_id]["date_from"] = min(dates)
                containers[container_id]["date_to"] = max(dates)

    for conversation_id in conversations_parse_failed:
        annotations.append(
            {
                "annotation_id": f"{CORPUS_ID}:parse_failed:{conversation_id}",
                "record_id": None,
                "annotation_type": "conversation_parse_failed",
                "body": (
                    f"conversation {conversation_id!r} is listed in state.json 'discovered' "
                    "but has no parsed/<id>.json on disk -- an interrupted acquisition run, "
                    "not a genuine zero-message conversation"
                ),
                "author": "community_lenses.adapters.bvp",
                "created_at": state["updated_at"],
                "access_class": "public",
            }
        )

    coverage_complete_predicate = (
        displayed_total is not None
        and len(discovered_ids) == displayed_total
        and not conversations_parse_failed
        and coverage_status == "complete"
    )

    reconciliation = {
        "displayed_total": displayed_total,
        "conversations_discovered": len(discovered_ids),
        "conversations_fetched": counts.get("fetched"),
        "conversations_parsed": len(conversations),
        "conversations_parse_failed": len(conversations_parse_failed),
        "conversations_not_yet_enumerated": (
            None if displayed_total is None else displayed_total - len(discovered_ids)
        ),
        "messages_total": messages_total,
        "messages_incomplete": messages_incomplete,
        "messages_excluded_from_person_denominator": messages_incomplete,
        "listing_failures": counts.get("failed", 0),
        "retries": counts.get("retries", 0),
    }

    manifest = _shared.build_manifest(
        corpus_id=CORPUS_ID,
        snapshot_id=snapshot_id,
        coverage_status=coverage_status,
        source_version=(
            f"bvp/data/meta/state.json@{state_sha256[:12]} "
            f"(schema_version={state.get('schema_version')}; "
            f"discovered={len(discovered_ids)}/{displayed_total} conversations; "
            f"messages={messages_total} incl. {messages_incomplete} incomplete)"
        ),
        acquired_at=state["updated_at"],
        source_sha256=state_sha256,
        rights_basis=RIGHTS_BASIS,
        coverage_start=(min(created_dates) if created_dates else None),
        coverage_end=(max(created_dates) if created_dates else None),
        cutoff_date=state["updated_at"][:10],
    )

    fixture = {
        "corpus": {
            "corpus_id": CORPUS_ID,
            "title": GROUP_TITLE,
            "medium": "mailing_list",
            "forum_orientation": "many_to_many_threaded",
            "native_unit": "message",
            "canonical_url": GROUP_URL,
            "rights_status": "public_google_group_first_page_partial",
        },
        "manifest": manifest.to_dict(),
        "containers": list(containers.values()),
        "records": records,
        "record_names": record_names,
        "record_relations": [],  # native reply-parent not exposed by this source
        "classification_assignments": classification_assignments,
        "annotations": annotations,
        "quotes": [],
        "_reconciliation": reconciliation,
        "_capabilities": {"supports_population_metrics": coverage_complete_predicate},
    }
    return fixture


def population_metrics_allowed(fixture: dict) -> bool:
    return bool(fixture.get("_capabilities", {}).get("supports_population_metrics", False))


def require_population_metrics(fixture: dict) -> None:
    """Raise unless the pinned manifest satisfies H1893's complete-coverage predicate.

    No caller may obtain an annual trend, person-share, topic-share, or
    whole-population claim from a partial/pilot BVP snapshot by omission of
    this check.
    """
    if not population_metrics_allowed(fixture):
        raise PopulationMetricsDisabled(
            f"bvp coverage_status={fixture['manifest']['coverage_status']!r} "
            "(supports_population_metrics=False): population-level claims are "
            "disabled until the manifest reconciles the full listing denominator"
        )


def build_fixture() -> dict:
    state = _load_state()
    if state is None:
        return _shared.unavailable_fixture(
            corpus_id=CORPUS_ID,
            title=GROUP_TITLE,
            native_unit="message",
            rights_basis=RIGHTS_BASIS,
            gap_note=(
                f"no bvp/data/meta/state.json found at {STATE_PATH}; run "
                "bvp/scrape.py to produce the frozen local acquisition manifest"
            ),
        )

    discovered_ids = sorted(state.get("discovered", {}).keys())
    conversations = _load_parsed_conversations(discovered_ids)
    state_sha256 = _shared.file_sha256(STATE_PATH)
    return _build_from_state(state, conversations, state_sha256=state_sha256)


def coverage_report(fixture: dict) -> str:
    manifest = fixture["manifest"]
    is_available = manifest["coverage_status"] != "unavailable"
    recon = fixture.get("_reconciliation", {})
    displayed_total = recon.get("displayed_total")
    discovered = recon.get("conversations_discovered")
    messages_total = recon.get("messages_total", 0)
    messages_incomplete = recon.get("messages_incomplete", 0)
    included = max(messages_total - messages_incomplete, 0)

    if is_available and displayed_total:
        completeness_status = (
            f"partial: {discovered}/{displayed_total} conversations enumerated "
            f"({discovered / displayed_total:.4%}); continuation-token pagination "
            "is a separate, not-yet-built bounded unit (see bvp/README.md)"
        )
    elif is_available:
        completeness_status = "partial: denominator not yet reconciled"
    else:
        completeness_status = "unavailable on this machine"

    return _shared.render_coverage_report(
        corpus_id=CORPUS_ID,
        title="Bharatiya Vidvat Parishat (BVP) Google Group",
        native_unit="message",
        coverage_status=manifest["coverage_status"],
        manifest_snapshot_id=manifest["snapshot_id"],
        date_range=f"{manifest.get('coverage_start') or '?'} .. {manifest.get('coverage_end') or '?'}",
        denominator_definition=(
            "one row per native Google Groups message_id across every conversation "
            "discovered on the server-rendered first BVP listing page (30 of a "
            f"displayed {displayed_total or '?'} total conversations)"
        ),
        included=included if is_available else 0,
        excluded=messages_incomplete if is_available else 0,
        failures=recon.get("conversations_parse_failed", 0) + recon.get("listing_failures", 0),
        completeness_status=completeness_status,
        notes=[
            "BVP is treated as this study's principal India-centred Sanskrit forum because that "
            "is Gasūns' expert corpus-selection intuition (documented in H1896) -- not evidence "
            "that BVP statistically represents all Indian Sanskrit scholarship.",
            "coverage_status stays 'partial' until a separate bounded pagination unit reconciles "
            f"the full {displayed_total or '?'}-conversation listing denominator; this adapter "
            "never upgrades that status itself.",
            (
                f"{messages_incomplete} of {messages_total} native messages parsed via a "
                "semantic-DOM fallback with no public author/body -- kept as explicit records "
                "(status=active) and excluded from content/person-denominator percentages, never "
                "silently dropped."
                if messages_incomplete
                else "No incomplete message records in this snapshot."
            ),
            f"supports_population_metrics={fixture.get('_capabilities', {}).get('supports_population_metrics', False)}: "
            "no annual trend, person-share, topic-share, or whole-population claim may be derived "
            "from this partial snapshot (community_lenses.adapters.bvp.require_population_metrics).",
            "Native topic evidence is the verbatim message/conversation subject line, registered "
            "under the codebook's generic 'other' row -- 'bvp:native_category' remains a proposed "
            "placeholder in codebooks/native_topic.csv, out of H1896's owned-file scope, since the "
            "acquired evidence is a free-text subject, not a category scheme.",
            "Never resolves a message author to a `person` row (identity linkage is H1898's scope) "
            "and never emits a `quote` (selection/rights review is H1898's scope too).",
        ],
    )
