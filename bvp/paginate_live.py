#!/usr/bin/env python3
"""Sequential public BVP listing pagination, driven by a real browser.

Drives the public "Next page" control in a headless Chromium tab rather than
guessing or replaying Google Groups' private batchexecute RPC contract. One
tab, concurrency one, polite delay/jitter between pages, bounded retry on
transient errors, and an immediate stop on HTTP 403/429 or any named fault
from ``pagination.Paginator``.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pagination import Paginator, PaginationFault  # noqa: E402
from scrape import GROUP_URL, UA, StopCrawl, atomic_text, sha256_text  # noqa: E402

NEXT_PAGE_ARIA_LABEL = "Next page"
ROW_SELECTOR = '[role="row"][data-rowid]'


def run_pages(
    paginator: Paginator,
    fetch_next: Callable[[int], tuple[str, str | None]],
    max_pages: int,
    delay: float = 2.0,
    retries: int = 1,
) -> None:
    """Drive ``fetch_next`` for each unfetched ordinal up to ``max_pages``.

    ``fetch_next(ordinal)`` must return ``(html, cursor_evidence)`` for that
    page, or raise ``StopCrawl`` on an HTTP 403/429 origin response. Already
    checkpointed ordinals are skipped (resume). Any ``PaginationFault`` or
    ``StopCrawl`` propagates immediately — no retry on either.
    """
    for ordinal in range(1, max_pages + 1):
        if paginator.has_page(ordinal):
            continue
        if ordinal > 1:
            time.sleep(delay + random.uniform(0.2, 0.8))
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            if attempt:
                time.sleep(random.uniform(2.0, 5.0))
            try:
                html, cursor_evidence = fetch_next(ordinal)
            except StopCrawl:
                raise
            except PaginationFault:
                raise
            except Exception as error:  # noqa: BLE001 - bounded retry, then re-raise
                last_error = error
                continue
            paginator.reconcile_page(ordinal, html, cursor_evidence)
            last_error = None
            break
        if last_error is not None:
            raise RuntimeError(f"page {ordinal} fetch failed: {last_error}")


def _browser_fetch_next(out_dir: Path):
    """Build a ``fetch_next`` closure backed by one headless Chromium tab.

    Imported lazily so ``run_pages`` and the fault-detection tests never need
    Playwright installed.
    """
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA)
    page = context.new_page()
    state = {"navigated": False}

    def fetch_next(ordinal: int) -> tuple[str, str | None]:
        if not state["navigated"]:
            response = page.goto(
                GROUP_URL, wait_until="domcontentloaded", timeout=30000
            )
            if response is not None and response.status in (403, 429):
                raise StopCrawl(f"origin returned {response.status} on navigate")
            page.wait_for_selector(ROW_SELECTOR, timeout=20000)
            state["navigated"] = True
        else:
            next_button = page.get_by_label(NEXT_PAGE_ARIA_LABEL, exact=True)
            if next_button.count() == 0 or not next_button.first.is_enabled():
                raise PaginationFault(
                    "premature_cursor_loss",
                    f"page {ordinal}: Next page control missing or disabled",
                )
            first_row = page.locator(ROW_SELECTOR).first
            first_id_before = first_row.get_attribute("data-rowid")
            next_button.first.click()
            page.wait_for_function(
                """(prevFirstId) => {
                    const row = document.querySelector('[role="row"][data-rowid]');
                    return row && row.getAttribute('data-rowid') !== prevFirstId;
                }""",
                arg=first_id_before,
                timeout=20000,
            )
        html = page.content()
        raw_path = out_dir / "raw" / f"listing-page-{ordinal}.html"
        atomic_text(raw_path, html)
        cursor_evidence = sha256_text(f"page-{ordinal}:{page.url}")
        return html, cursor_evidence

    fetch_next.close = lambda: (context.close(), browser.close(), playwright.stop())  # type: ignore[attr-defined]
    return fetch_next


def run_live_pilot(
    out_dir: Path, max_pages: int = 3, delay: float = 2.0
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "meta" / "pagination.json"
    paginator = Paginator(state_path, requested_pages=max_pages)
    fetch_next = _browser_fetch_next(out_dir)
    try:
        run_pages(paginator, fetch_next, max_pages=max_pages, delay=delay)
    finally:
        fetch_next.close()
    return paginator.reconcile_report()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--delay", type=float, default=2.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_pages != 3:
        print(
            "WARN: the H1892 pilot bound is exactly three pages; "
            f"refusing --max-pages={args.max_pages}",
            file=sys.stderr,
        )
        return 2
    try:
        report = run_live_pilot(args.out, max_pages=args.max_pages, delay=args.delay)
    except (StopCrawl, PaginationFault) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    import json

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
