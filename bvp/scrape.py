#!/usr/bin/env python3
"""Bounded, resumable acquisition of public Bharatiya Vidvat Parishat pages.

This first acquisition unit enumerates the server-rendered first listing page
and fetches a caller-bounded number of conversation pages. It deliberately
does not claim complete archive pagination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from fetch_hardening import Backoff, FailLedger

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://groups.google.com"
GROUP_PATH = "/g/bvparishat"
GROUP_URL = BASE + GROUP_PATH
UA = (
    "IndologyScholars-BVP-research/0.1 "
    "(bounded public archive acquisition; contact via repository)"
)
PARSER_VERSION = 3
RANGE_RE = re.compile(
    r"(?P<first>\d[\d,]*)\s*[–-]\s*(?P<last>\d[\d,]*)"
    r"\s+of\s+(?P<total>\d[\d,]*)"
)
MESSAGE_COUNT_RE = re.compile(r"(\d[\d,]*)\s+messages?", re.IGNORECASE)


class StopCrawl(RuntimeError):
    """Raised when the origin explicitly asks the crawler to stop."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def extract_ds7_payloads(html: str) -> list[Any]:
    """Decode server-rendered Google callback payloads without executing JS."""
    soup = BeautifulSoup(html, "html.parser")
    payloads: list[Any] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if "AF_initDataCallback" not in text or "key: 'ds:7'" not in text:
            continue
        try:
            start = text.index("data:") + len("data:")
            end = text.rindex(", sideChannel:")
            payloads.append(json.loads(text[start:end].strip()))
        except (ValueError, json.JSONDecodeError):
            continue
    return payloads


def parse_listing(html: str) -> dict[str, Any]:
    """Parse the server-rendered first listing page using semantic attributes."""
    soup = BeautifulSoup(html, "html.parser")
    conversations: dict[str, dict[str, Any]] = {}
    for row in soup.select('[role="row"][data-rowid]'):
        conversation_id = (row.get("data-rowid") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", conversation_id):
            continue
        if conversation_id in conversations:
            continue
        subject_node = row.select_one(".o1DPKc")
        snippet_node = row.select_one(".WzoK")
        date_node = row.select_one(".tRlaM")
        count_node = row.select_one(".F5JnCe")
        count_label = (
            (count_node.get("aria-label") or count_node.get_text(" ", strip=True))
            if count_node
            else ""
        )
        count_match = MESSAGE_COUNT_RE.search(count_label)
        conversations[conversation_id] = {
            "conversation_id": conversation_id,
            "url": f"{GROUP_URL}/c/{conversation_id}",
            "subject": subject_node.get_text(" ", strip=True)
            if subject_node
            else "",
            "snippet": snippet_node.get_text(" ", strip=True)
            if snippet_node
            else "",
            "display_date": date_node.get_text(" ", strip=True)
            if date_node
            else "",
            "message_count": int(count_match.group(1).replace(",", ""))
            if count_match
            else None,
        }

    range_node = soup.select_one(".aEb7Ed")
    range_text = range_node.get_text(" ", strip=True) if range_node else ""
    range_match = RANGE_RE.search(range_text)
    listing = {
        "page_first": None,
        "page_last": None,
        "displayed_total": None,
        "range_text": range_text,
    }
    if range_match:
        listing.update(
            {
                "page_first": int(range_match.group("first").replace(",", "")),
                "page_last": int(range_match.group("last").replace(",", "")),
                "displayed_total": int(
                    range_match.group("total").replace(",", "")
                ),
            }
        )
    for payload in extract_ds7_payloads(html):
        if (
            isinstance(payload, list)
            and len(payload) >= 4
            and isinstance(payload[1], int)
            and isinstance(payload[2], list)
            and isinstance(payload[3], str)
        ):
            listing["embedded_total"] = payload[1]
            listing["continuation_token"] = payload[3]
            break
    return {
        "listing": listing,
        "conversations": list(conversations.values()),
    }


def _largest_message_node(
    soup: BeautifulSoup, conversation_id: str, message_id: str
) -> Any:
    candidates = soup.select(
        f'[data-conv-id="{conversation_id}"]'
        f'[data-message-id="{message_id}"]'
    )
    if not candidates:
        candidates = soup.select(f'[data-message-id="{message_id}"]')
    return max(
        candidates,
        key=lambda node: len(node.get_text(" ", strip=True)),
        default=None,
    )


def _find_nested(
    value: Any,
    predicate: Any,
) -> Any:
    if predicate(value):
        return value
    if isinstance(value, list):
        for item in value:
            found = _find_nested(item, predicate)
            if found is not None:
                return found
    return None


def _html_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str) and "<" in value:
        values.append(value)
    elif isinstance(value, list):
        for item in value:
            values.extend(_html_strings(item))
    return values


def _parse_embedded_messages(
    html: str,
    expected_id: str | None,
) -> tuple[str, str, list[dict[str, Any]]] | None:
    for data in extract_ds7_payloads(html):
        if not (
            isinstance(data, list)
            and len(data) >= 3
            and isinstance(data[0], list)
            and data[0]
            and isinstance(data[2], list)
        ):
            continue
        group_id = data[0][0]
        summary = data[1] if isinstance(data[1], list) else []
        conversation_id = (
            summary[1]
            if len(summary) > 1 and isinstance(summary[1], str)
            else expected_id or ""
        )
        subject = (
            summary[2]
            if len(summary) > 2 and isinstance(summary[2], str)
            else ""
        )
        messages: list[dict[str, Any]] = []
        for record in data[2]:
            header = _find_nested(
                record,
                lambda value: (
                    isinstance(value, list)
                    and len(value) > 7
                    and value[0] == group_id
                    and isinstance(value[1], str)
                    and isinstance(value[2], list)
                ),
            )
            payload = _find_nested(
                record,
                lambda value: (
                    isinstance(value, list)
                    and len(value) >= 2
                    and value[0] == 2
                    and isinstance(value[1], list)
                    and bool(_html_strings(value[1]))
                ),
            )
            if header is None or payload is None:
                continue
            author = (
                header[2][0]
                if header[2]
                and isinstance(header[2][0], list)
                else []
            )
            timestamp = header[7] if isinstance(header[7], list) else []
            body_parts = _html_strings(payload[1])
            body_html = "\n".join(body_parts)
            body_text = BeautifulSoup(body_html, "html.parser").get_text(
                "\n", strip=True
            )
            messages.append(
                {
                    "message_id": header[1],
                    "author_display": author[0]
                    if len(author) > 0 and isinstance(author[0], str)
                    else "",
                    "author_native_id": author[3]
                    if len(author) > 3 and isinstance(author[3], str)
                    else None,
                    "subject": header[5]
                    if len(header) > 5 and isinstance(header[5], str)
                    else "",
                    "timestamp_epoch": timestamp[0]
                    if timestamp and isinstance(timestamp[0], int)
                    else None,
                    "timestamp_nanos": timestamp[1]
                    if len(timestamp) > 1 and isinstance(timestamp[1], int)
                    else None,
                    "body_html": body_html,
                    "body_html_sha256": sha256_text(body_html),
                    "body_text": body_text,
                    "body_text_sha256": sha256_text(body_text),
                }
            )
        if messages:
            return conversation_id, subject, messages
    return None


def parse_thread(html: str, expected_id: str | None = None) -> dict[str, Any]:
    """Extract stable thread/message identifiers and rendered source text.

    Rendered text is a local evidence field, not a publication-ready quote.
    """
    embedded = _parse_embedded_messages(html, expected_id)
    if embedded:
        conversation_id, subject, messages = embedded
        return {
            "conversation_id": conversation_id,
            "subject": subject,
            "message_count": len(messages),
            "messages": messages,
            "parse_source": "AF_initDataCallback ds:7",
        }

    soup = BeautifulSoup(html, "html.parser")
    subject_node = soup.select_one('h1[jsname="GNEpNe"]')
    subject = subject_node.get_text(" ", strip=True) if subject_node else ""

    ids_by_conversation: dict[str, list[str]] = {}
    for node in soup.select("[data-conv-id][data-message-id]"):
        conversation_id = (node.get("data-conv-id") or "").strip()
        message_id = (node.get("data-message-id") or "").strip()
        if not conversation_id or not message_id:
            continue
        ids_by_conversation.setdefault(conversation_id, [])
        if message_id not in ids_by_conversation[conversation_id]:
            ids_by_conversation[conversation_id].append(message_id)

    if expected_id and expected_id in ids_by_conversation:
        conversation_id = expected_id
    elif ids_by_conversation:
        conversation_id = max(ids_by_conversation, key=lambda key: len(ids_by_conversation[key]))
    else:
        conversation_id = expected_id or ""

    messages: list[dict[str, Any]] = []
    for message_id in ids_by_conversation.get(conversation_id, []):
        node = _largest_message_node(soup, conversation_id, message_id)
        author_node = node.select_one("h3.s1f8Zd") if node else None
        rendered_text = node.get_text("\n", strip=True) if node else ""
        messages.append(
            {
                "message_id": message_id,
                "author_display": author_node.get_text(" ", strip=True)
                if author_node
                else "",
                "rendered_text": rendered_text,
                "rendered_text_sha256": sha256_text(rendered_text),
            }
        )
    return {
        "conversation_id": conversation_id,
        "subject": subject,
        "message_count": len(messages),
        "messages": messages,
        "parse_source": "semantic DOM fallback",
    }


class Scraper:
    def __init__(
        self,
        out: Path,
        delay: float = 2.0,
        retries: int = 1,
    ) -> None:
        self.out = out
        self.raw_dir = out / "raw"
        self.thread_dir = self.raw_dir / "threads"
        self.meta_dir = out / "meta"
        self.parsed_dir = out / "parsed"
        for directory in (
            self.thread_dir,
            self.meta_dir,
            self.parsed_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.8",
            }
        )
        self.state_path = self.meta_dir / "state.json"
        self.state = self._load_state()
        self.failed = FailLedger(self.meta_dir / "urls_failed.txt")
        self.failed.load()
        self.backoff = Backoff()

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "schema_version": 1,
            "created_at": utc_now(),
            "discovered": {},
            "fetched": {},
            "parsed": {},
            "retries": 0,
            "errors": {},
            "listing": {},
            "coverage_status": "pilot",
        }

    def save_state(self) -> None:
        self.state["updated_at"] = utc_now()
        self.state["counts"] = {
            "discovered": len(self.state["discovered"]),
            "fetched": len(self.state["fetched"]),
            "parsed": len(self.state["parsed"]),
            "incomplete_messages": sum(
                row.get("incomplete_messages", 0)
                for row in self.state["parsed"].values()
            ),
            "failed": len(self.failed.known),
            "retries": self.state["retries"],
        }
        atomic_json(self.state_path, self.state)

    def _pause(self) -> None:
        time.sleep(self.delay + random.uniform(0.2, 0.8))

    def fetch(self, url: str) -> str:
        if url in self.failed:
            raise RuntimeError(f"known failed URL: {url}")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                self.state["retries"] += 1
                self.save_state()
                time.sleep(random.uniform(2.0, 5.0))
            try:
                response = self.session.get(url, timeout=(10, 40))
                if response.status_code in {403, 429}:
                    retry_after = response.headers.get("Retry-After", "")
                    raise StopCrawl(
                        f"origin returned {response.status_code}; "
                        f"Retry-After={retry_after!r}"
                    )
                if response.status_code == 404:
                    self.failed.add(url)
                    raise RuntimeError(f"permanent HTTP 404: {url}")
                response.raise_for_status()
                self.backoff.record_success()
                return response.text
            except StopCrawl:
                raise
            except requests.RequestException as error:
                last_error = error
                pause = self.backoff.record_error()
                if pause:
                    time.sleep(pause)
                if attempt >= self.retries:
                    self.failed.add(url)
        raise RuntimeError(f"fetch failed: {url}: {last_error}")

    def acquire_listing(self) -> list[dict[str, Any]]:
        html = self.fetch(GROUP_URL)
        listing_path = self.raw_dir / "listing-page-1.html"
        atomic_text(listing_path, html)
        parsed = parse_listing(html)
        self.state["listing"] = {
            **parsed["listing"],
            "url": GROUP_URL,
            "retrieved_at": utc_now(),
            "raw_sha256": sha256_text(html),
            "enumeration_scope": "server-rendered first page only",
        }
        for row in parsed["conversations"]:
            self.state["discovered"][row["conversation_id"]] = row
        self.save_state()
        return parsed["conversations"]

    def acquire_thread(self, row: dict[str, Any]) -> None:
        conversation_id = row["conversation_id"]
        raw_path = self.thread_dir / f"{conversation_id}.html"
        prior = self.state["parsed"].get(conversation_id, {})
        if raw_path.exists() and prior.get("parser_version") == PARSER_VERSION:
            return
        if raw_path.exists():
            html = raw_path.read_text(encoding="utf-8")
        else:
            self._pause()
            html = self.fetch(row["url"])
            atomic_text(raw_path, html)
            self.state["fetched"][conversation_id] = {
                "url": row["url"],
                "retrieved_at": utc_now(),
                "raw_sha256": sha256_text(html),
            }
        parsed = parse_thread(html, expected_id=conversation_id)
        parsed["url"] = row["url"]
        parsed["retrieved_at"] = utc_now()
        parsed["raw_sha256"] = sha256_text(html)
        atomic_json(self.parsed_dir / f"{conversation_id}.json", parsed)
        self.state["parsed"][conversation_id] = {
            "message_count": parsed["message_count"],
            "subject": parsed["subject"],
            "parser_version": PARSER_VERSION,
            "incomplete_messages": sum(
                1
                for message in parsed["messages"]
                if not (
                    message.get("author_display")
                    and (
                        message.get("body_text")
                        or message.get("rendered_text")
                    )
                )
            ),
        }
        self.save_state()

    def run(self, max_threads: int) -> dict[str, Any]:
        rows = self.acquire_listing()
        processed_now = 0
        for row in rows:
            if processed_now >= max_threads:
                break
            conversation_id = row["conversation_id"]
            raw_path = self.thread_dir / f"{conversation_id}.html"
            prior = self.state["parsed"].get(conversation_id, {})
            if raw_path.exists() and prior.get("parser_version") == PARSER_VERSION:
                continue
            try:
                self.acquire_thread(row)
            except StopCrawl:
                raise
            except RuntimeError as error:
                self.state.setdefault("errors", {})[conversation_id] = {
                    "url": row["url"],
                    "error": str(error),
                    "at": utc_now(),
                }
                self.save_state()
                print(f"WARN: {error}", file=sys.stderr)
            processed_now += 1
        self.state["coverage_status"] = "partial"
        self.state["coverage_note"] = (
            "Only the server-rendered first listing page is enumerated; "
            "continuation-token pagination is not yet implemented."
        )
        self.save_state()
        return self.state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        default=3,
        help="maximum newly parsed conversation pages this run",
    )
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_threads < 0:
        raise SystemExit("--max-threads must be non-negative")
    scraper = Scraper(args.out, delay=args.delay, retries=args.retries)
    try:
        state = scraper.run(args.max_threads)
    except StopCrawl as error:
        scraper.save_state()
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    print(json.dumps(state["counts"], ensure_ascii=False))
    print(f"coverage_status={state['coverage_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
