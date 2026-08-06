#!/usr/bin/env python3
"""Deterministic reconciliation logic for sequential BVP listing pages.

This module is fetch-agnostic: it takes already-retrieved listing HTML (from
a real browser driving the public Next control, or from a fixture in tests)
and turns it into an atomic per-page checkpoint plus fault detection. Keeping
this separate from the Playwright driver in ``paginate_live.py`` lets the
fault-detection contract be unit-tested without a browser.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scrape import parse_listing  # noqa: E402  (sys.path set up by callers)

SCHEMA_VERSION = 1


class PaginationFault(RuntimeError):
    """Raised when a page reconciliation trips a named stop condition."""

    def __init__(self, fault_type: str, detail: str) -> None:
        super().__init__(f"{fault_type}: {detail}")
        self.fault_type = fault_type
        self.detail = detail


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def page_signature(row_ids: list[str]) -> str:
    """A deterministic signature identifying a page's row set, order-sensitive."""
    return sha256_text("\n".join(row_ids))


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class Paginator:
    """Reconciles sequential listing pages against the stop-condition contract.

    ``requested_pages`` bounds how many pages the caller intends to enumerate
    this run; it is only used to judge "premature cursor loss" (a missing
    continuation control before the bound is reached).
    """

    def __init__(self, state_path: Path, requested_pages: int) -> None:
        self.state_path = state_path
        self.requested_pages = requested_pages
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "schema_version": SCHEMA_VERSION,
            "created_at": utc_now(),
            "requested_pages": self.requested_pages,
            "pages": {},
            "signatures_seen": {},
            "all_row_ids": [],
            "faults": [],
            "coverage_status": "pilot",
        }

    def save(self) -> None:
        self.state["updated_at"] = utc_now()
        atomic_json(self.state_path, self.state)

    def completed_ordinals(self) -> set[int]:
        return {int(key) for key in self.state["pages"]}

    def has_page(self, ordinal: int) -> bool:
        return str(ordinal) in self.state["pages"]

    def _record_fault(self, ordinal: int, fault_type: str, detail: str) -> None:
        self.state["faults"].append(
            {
                "ordinal": ordinal,
                "type": fault_type,
                "at": utc_now(),
                "detail": detail,
            }
        )
        self.state["coverage_status"] = "stopped"
        self.save()

    def reconcile_page(
        self,
        ordinal: int,
        html: str,
        cursor_evidence: str | None,
    ) -> dict[str, Any]:
        """Parse, checkpoint, and fault-check one sequential listing page.

        Raises ``PaginationFault`` (state already persisted) on any of the
        named stop conditions. Returns the page record on success.
        """
        parsed = parse_listing(html)
        row_ids = [row["conversation_id"] for row in parsed["conversations"]]
        listing = parsed["listing"]
        displayed_total = listing.get("displayed_total")
        page_first = listing.get("page_first")
        page_last = listing.get("page_last")

        if not row_ids or displayed_total is None:
            self._record_fault(
                ordinal,
                "schema_drift",
                f"page {ordinal} produced no rows or no displayed range "
                f"(row_count={len(row_ids)}, displayed_total={displayed_total})",
            )
            raise PaginationFault(
                "schema_drift", f"page {ordinal} failed to parse expected structure"
            )

        first_page = self.state["pages"].get("1")
        if first_page is not None:
            baseline_total = first_page["displayed_total"]
            if baseline_total is not None and displayed_total != baseline_total:
                self._record_fault(
                    ordinal,
                    "denominator_change",
                    f"displayed_total changed from {baseline_total} to {displayed_total}",
                )
                raise PaginationFault(
                    "denominator_change",
                    f"page {ordinal}: {baseline_total} -> {displayed_total}",
                )

        signature = page_signature(row_ids)
        if signature in self.state["signatures_seen"]:
            prior_ordinal = self.state["signatures_seen"][signature]
            self._record_fault(
                ordinal,
                "repeated_signature",
                f"page {ordinal} row-set signature matches page {prior_ordinal}",
            )
            raise PaginationFault(
                "repeated_signature", f"page {ordinal} duplicates page {prior_ordinal}"
            )

        previously_seen_ids = set(self.state["all_row_ids"])
        new_ids = [row_id for row_id in row_ids if row_id not in previously_seen_ids]
        if previously_seen_ids and not new_ids:
            self._record_fault(
                ordinal,
                "no_new_ids",
                f"page {ordinal} contributed zero unseen conversation ids",
            )
            raise PaginationFault("no_new_ids", f"page {ordinal} had no new ids")

        previous_ordinal = ordinal - 1
        previous_page = self.state["pages"].get(str(previous_ordinal))
        if previous_page is not None and page_first is not None:
            previous_last = previous_page.get("page_last")
            if previous_last is not None and page_first <= previous_last:
                self._record_fault(
                    ordinal,
                    "overlap_or_backward_range",
                    f"page {ordinal} range starts at {page_first}, "
                    f"not after previous page_last={previous_last}",
                )
                raise PaginationFault(
                    "overlap_or_backward_range",
                    f"page {ordinal}: first={page_first} <= previous_last={previous_last}",
                )

        if (
            cursor_evidence is None
            and ordinal < self.requested_pages
            and previous_page is not None
            and previous_page.get("cursor_evidence_sha256") is not None
        ):
            self._record_fault(
                ordinal,
                "premature_cursor_loss",
                f"page {ordinal} lost continuation evidence before "
                f"reaching the requested {self.requested_pages} pages",
            )
            raise PaginationFault(
                "premature_cursor_loss", f"page {ordinal} has no cursor evidence"
            )

        record = {
            "ordinal": ordinal,
            "retrieved_at": utc_now(),
            "row_ids": row_ids,
            "row_set_sha256": signature,
            "page_first": page_first,
            "page_last": page_last,
            "displayed_total": displayed_total,
            "cursor_evidence_sha256": sha256_text(cursor_evidence)
            if cursor_evidence
            else None,
            "parse_status": "ok",
        }
        self.state["pages"][str(ordinal)] = record
        self.state["signatures_seen"][signature] = ordinal
        self.state["all_row_ids"].extend(new_ids)
        if len(self.completed_ordinals()) >= self.requested_pages:
            self.state["coverage_status"] = "partial"
        self.save()
        return record

    def reconcile_report(self) -> dict[str, Any]:
        pages = self.state["pages"]
        first_page = pages.get("1")
        unique_ids = self.state["all_row_ids"]
        listed_rows = sum(len(page["row_ids"]) for page in pages.values())
        duplicate_ids = listed_rows - len(set(unique_ids))
        gap = None
        if pages:
            last_ordinal = max(int(key) for key in pages)
            last_page = pages[str(last_ordinal)]
            if (
                first_page is not None
                and last_page.get("displayed_total") is not None
                and last_page.get("page_last") is not None
            ):
                gap = last_page["displayed_total"] - last_page["page_last"]
        return {
            "displayed_total": first_page["displayed_total"] if first_page else None,
            "pages_requested": self.requested_pages,
            "pages_completed": len(pages),
            "listed_rows": listed_rows,
            "unique_conversation_ids": len(set(unique_ids)),
            "duplicate_ids": duplicate_ids,
            "unexplained_gap": gap,
            "faults": self.state["faults"],
            "coverage_status": self.state["coverage_status"],
        }
