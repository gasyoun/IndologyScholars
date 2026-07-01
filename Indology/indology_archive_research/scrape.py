"""Harvest and parse INDOLOGY Mailman/Pipermail archive metadata."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import re
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.header import decode_header, make_header
from email.parser import Parser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .topics import clean_subject

BASE_URL = "https://list.indology.info/pipermail/indology/"
USER_AGENT = "indology-archive-research-map/1.0"
MONTH_LINK_RE = re.compile(
    r"(?P<month>[A-Za-z]+)\s+(?P<year>\d{4}).*?(?P<size>\d+)\s+KB",
    re.I | re.S,
)
FROM_LINE_RE = re.compile(r"(?m)^From [^\n]*\n")


@dataclass(frozen=True)
class ArchiveMonth:
    year: int
    month_name: str
    month_num: int
    slug: str
    thread_url: str
    subject_url: str
    author_url: str
    date_url: str
    gzip_url: str
    gzip_kb: int | None


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def fetch_url(
    url: str,
    cache_path: Path,
    insecure: bool,
    delay: float,
    retries: int,
    refresh: bool = False,
) -> bytes:
    """Fetch a URL with a filesystem cache."""

    if not refresh and cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path.read_bytes()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    context = ssl._create_unverified_context() if insecure else None
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=90, context=context) as response:
                data = response.read()
            cache_path.write_bytes(data)
            if delay:
                time.sleep(delay)
            return data
        except Exception as exc:  # pragma: no cover - network-path dependent
            last_error = exc
            wait = min(30, attempt * 5)
            print(f"fetch failed ({attempt}/{retries}) {url}: {exc}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"could not fetch {url}: {last_error}")


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._href = attrs_dict.get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append((self._href, text))
            self._href = None
            self._text = []


def parse_archive_index(index_html: str) -> list[ArchiveMonth]:
    collector = LinkCollector()
    collector.feed(index_html)
    by_slug: dict[str, dict[str, str]] = {}
    for href, text in collector.links:
        match = re.match(r"(?P<slug>\d{4}-[A-Za-z]+)/(?P<view>thread|subject|author|date)\.html", href)
        if match:
            by_slug.setdefault(match.group("slug"), {})[match.group("view")] = urljoin(BASE_URL, href)
        match = re.match(r"(?P<slug>\d{4}-[A-Za-z]+)\.txt\.gz", href)
        if match:
            by_slug.setdefault(match.group("slug"), {})["gzip"] = urljoin(BASE_URL, href)

    months: list[ArchiveMonth] = []
    for slug, urls in by_slug.items():
        year_text, month_name = slug.split("-", 1)
        month_num = MONTHS[month_name.lower()]
        gzip_url = urls.get("gzip", urljoin(BASE_URL, f"{slug}.txt.gz"))
        size_match = re.search(rf"{re.escape(month_name)}\s+{year_text}:.*?Gzip'd Text\s+(\d+)\s+KB", index_html, re.I | re.S)
        months.append(
            ArchiveMonth(
                year=int(year_text),
                month_name=month_name,
                month_num=month_num,
                slug=slug,
                thread_url=urls.get("thread", urljoin(BASE_URL, f"{slug}/thread.html")),
                subject_url=urls.get("subject", urljoin(BASE_URL, f"{slug}/subject.html")),
                author_url=urls.get("author", urljoin(BASE_URL, f"{slug}/author.html")),
                date_url=urls.get("date", urljoin(BASE_URL, f"{slug}/date.html")),
                gzip_url=gzip_url,
                gzip_kb=int(size_match.group(1)) if size_match else None,
            )
        )
    months.sort(key=lambda m: (m.year, m.month_num))
    return months


class MessageListParser(HTMLParser):
    """Parse date/subject/author pages containing LI/A/I message rows."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._href: str | None = None
        self._subject: list[str] = []
        self._author: list[str] = []
        self._in_a = False
        self._in_i = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "a":
            href = dict(attrs).get("href")
            if href and href.endswith(".html"):
                self._href = href.split("#", 1)[0]
                self._subject = []
                self._in_a = True
        elif tag == "i" and self._href:
            self._author = []
            self._in_i = True

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._subject.append(data)
        elif self._in_i:
            self._author.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a":
            self._in_a = False
        elif tag == "i" and self._href:
            subject = " ".join("".join(self._subject).split())
            author = " ".join("".join(self._author).split())
            self.rows.append({"archive_id": Path(self._href).stem, "href": self._href, "subject_html": subject, "author_html": author})
            self._href = None
            self._in_i = False


class ThreadParser(MessageListParser):
    """Parse thread pages and record root thread ids from nesting comments."""

    def __init__(self) -> None:
        super().__init__()
        self._pending_depth = 0
        self._stack: dict[int, str] = {}

    def handle_comment(self, data: str) -> None:
        match = re.match(r"\s*(\d+)\s", data)
        if match:
            self._pending_depth = int(match.group(1))

    def handle_endtag(self, tag: str) -> None:
        before = len(self.rows)
        super().handle_endtag(tag)
        if len(self.rows) > before:
            row = self.rows[-1]
            depth = self._pending_depth
            archive_id = row["archive_id"]
            if depth == 0:
                root = archive_id
            else:
                root = self._stack.get(0, archive_id)
            self._stack[depth] = archive_id
            row["thread_depth"] = str(depth)
            row["thread_root_id"] = root
            self._pending_depth = 0


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return html.unescape(value)


def parse_mbox_messages(gzip_bytes: bytes) -> list[dict[str, str]]:
    text = gzip.decompress(gzip_bytes).decode("utf-8", "replace")
    starts = []
    for match in FROM_LINE_RE.finditer(text):
        probe = text[match.end() : match.end() + 1200]
        header_probe = probe.split("\n\n", 1)[0]
        if re.search(r"(?mi)^From:\s+", header_probe) and re.search(r"(?mi)^Date:\s+", header_probe) and re.search(r"(?mi)^Subject:\s+", header_probe):
            starts.append(match.start())
    if not starts:
        return []
    starts.append(len(text))
    # Historical Pipermail mboxes contain a few malformed Message-ID headers.
    # compat32 preserves raw header text instead of validating structured values.
    parser = Parser(policy=policy.compat32)
    rows: list[dict[str, str]] = []
    for i in range(len(starts) - 1):
        chunk = text[starts[i] : starts[i + 1]]
        header_body = chunk.split("\n", 1)[1] if "\n" in chunk else chunk
        header_text = header_body.split("\n\n", 1)[0]
        message = parser.parsestr(header_text + "\n\n")
        date_raw = decode_header_value(message.get("Date"))
        parsed_date = ""
        year = ""
        month = ""
        try:
            dt = parsedate_to_datetime(date_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_date = dt.isoformat()
            year = str(dt.year)
            month = f"{dt.month:02d}"
        except Exception:
            pass
        message_id = decode_header_value(message.get("Message-ID"))
        rows.append(
            {
                "mbox_index": str(i),
                "from_header": decode_header_value(message.get("From")),
                "author": decode_header_value(message.get("From")),
                "date_raw": date_raw,
                "date": parsed_date,
                "year": year,
                "month": month,
                "subject": decode_header_value(message.get("Subject")),
                "message_id": message_id,
                "in_reply_to": decode_header_value(message.get("In-Reply-To")),
                "references": decode_header_value(message.get("References")),
                "message_hash": hashlib.sha1((message_id or header_text[:200]).encode("utf-8", "replace")).hexdigest()[:16],
            }
        )
    return rows


def _norm_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", clean_subject(value or "").casefold()).strip()


def align_archive_and_mbox(
    archive_rows: list[dict[str, str]],
    mbox_rows: list[dict[str, str]],
    slug: str,
    lookahead: int = 12,
) -> tuple[list[tuple[dict[str, str], dict[str, str]]], list[dict[str, object]]]:
    """Align HTML archive rows to mbox headers, skipping extra mbox rows.

    Pipermail occasionally exposes more parseable mbox messages than date-index
    rows. A pure positional merge then shifts every later header in that month.
    This conservative matcher uses subject equality/containment within a short
    lookahead window and records any skipped rows for audit.
    """

    aligned: list[tuple[dict[str, str], dict[str, str]]] = []
    skipped: list[dict[str, object]] = []
    if len(archive_rows) == len(mbox_rows):
        return [
            (
                archive_row,
                {**mbox_row, "mbox_alignment_score": "positional", "mbox_alignment_index": str(index)},
            )
            for index, (archive_row, mbox_row) in enumerate(zip(archive_rows, mbox_rows))
        ], skipped

    cursor = 0
    remaining_skips = max(0, len(mbox_rows) - len(archive_rows))
    for archive_index, archive_row in enumerate(archive_rows):
        archive_subject = _norm_match_text(archive_row.get("subject_html", ""))
        best_index = cursor
        best_score = -1
        upper = min(len(mbox_rows), cursor + min(lookahead, remaining_skips + 1))
        for candidate_index in range(cursor, upper):
            candidate = mbox_rows[candidate_index]
            candidate_subject = _norm_match_text(candidate.get("subject", ""))
            score = 0
            if archive_subject and candidate_subject:
                if archive_subject == candidate_subject:
                    score += 100
                elif archive_subject in candidate_subject or candidate_subject in archive_subject:
                    score += 60
            if archive_row.get("author_html", "").casefold() == candidate.get("author", "").casefold():
                score += 5
            if score > best_score:
                best_score = score
                best_index = candidate_index
        if best_score < 100 or best_index - cursor > remaining_skips:
            best_index = cursor
            best_score = 0
        if best_index > cursor:
            for skipped_index in range(cursor, best_index):
                skipped_row = mbox_rows[skipped_index]
                skipped.append(
                    {
                        "slug": slug,
                        "mbox_index": skipped_row.get("mbox_index", skipped_index),
                        "date": skipped_row.get("date", ""),
                        "author": skipped_row.get("author", ""),
                        "subject": skipped_row.get("subject", ""),
                        "reason": "extra_mbox_row_skipped_during_subject_alignment",
                    }
                )
            remaining_skips -= best_index - cursor
        selected = mbox_rows[best_index] if best_index < len(mbox_rows) else {}
        selected = {**selected, "mbox_alignment_score": str(best_score), "mbox_alignment_index": str(best_index)}
        aligned.append((archive_row, selected))
        cursor = best_index + 1

    for skipped_index in range(cursor, len(mbox_rows)):
        skipped_row = mbox_rows[skipped_index]
        skipped.append(
            {
                "slug": slug,
                "mbox_index": skipped_row.get("mbox_index", skipped_index),
                "date": skipped_row.get("date", ""),
                "author": skipped_row.get("author", ""),
                "subject": skipped_row.get("subject", ""),
                "reason": "trailing_extra_mbox_row",
            }
        )
    return aligned, skipped


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def harvest_archive(
    output_dir: Path,
    start_year: int,
    end_year: int,
    insecure: bool,
    delay: float,
    retries: int,
) -> None:
    raw_dir = output_dir / "data" / "raw"
    processed_dir = output_dir / "data" / "processed"
    index_bytes = fetch_url(BASE_URL, raw_dir / "index.html", insecure, delay, retries, refresh=True)
    index_html = index_bytes.decode("utf-8", "replace")
    months = [m for m in parse_archive_index(index_html) if start_year <= m.year <= end_year]

    month_rows: list[dict[str, object]] = []
    message_rows: list[dict[str, object]] = []
    parse_issues: list[dict[str, object]] = []
    skipped_mbox_rows: list[dict[str, object]] = []

    for month in months:
        print(f"harvesting {month.slug}", flush=True)
        month_raw = raw_dir / month.slug
        date_html = fetch_url(month.date_url, month_raw / "date.html", insecure, delay, retries).decode("utf-8", "replace")
        thread_html = fetch_url(month.thread_url, month_raw / "thread.html", insecure, delay, retries).decode("utf-8", "replace")
        gzip_bytes = fetch_url(month.gzip_url, raw_dir / f"{month.slug}.txt.gz", insecure, delay, retries)

        date_parser = MessageListParser()
        date_parser.feed(date_html)
        thread_parser = ThreadParser()
        thread_parser.feed(thread_html)
        thread_by_id = {row["archive_id"]: row for row in thread_parser.rows}
        mbox_rows = parse_mbox_messages(gzip_bytes)

        archive_count = len(date_parser.rows)
        mbox_count = len(mbox_rows)
        if archive_count != mbox_count:
            parse_issues.append(
                {
                    "slug": month.slug,
                    "issue": "count_mismatch",
                    "archive_count": archive_count,
                    "mbox_count": mbox_count,
                }
            )

        aligned_rows, skipped_rows = align_archive_and_mbox(date_parser.rows, mbox_rows, month.slug)
        skipped_mbox_rows.extend(skipped_rows)

        for idx, (archive_row, mbox_row) in enumerate(aligned_rows):
            thread_row = thread_by_id.get(archive_row["archive_id"], {})
            merged = {
                **mbox_row,
                "archive_id": archive_row["archive_id"],
                "archive_href": archive_row["href"],
                "archive_url": urljoin(month.date_url, archive_row["href"]),
                "slug": month.slug,
                "archive_year": month.year,
                "archive_month": month.month_num,
                "subject_html": archive_row["subject_html"],
                "author_html": archive_row["author_html"],
                "thread_root_id": thread_row.get("thread_root_id", archive_row["archive_id"]),
                "thread_depth": thread_row.get("thread_depth", "0"),
            }
            message_rows.append(merged)

        month_rows.append(
            {
                "slug": month.slug,
                "year": month.year,
                "month": month.month_num,
                "month_name": month.month_name,
                "message_count_index": archive_count,
                "message_count_mbox": mbox_count,
                "gzip_kb_index": month.gzip_kb,
                "thread_url": month.thread_url,
                "date_url": month.date_url,
                "gzip_url": month.gzip_url,
            }
        )

    message_fields = [
        "archive_id",
        "archive_href",
        "archive_url",
        "slug",
        "archive_year",
        "archive_month",
        "mbox_index",
        "from_header",
        "author",
        "author_html",
        "date_raw",
        "date",
        "year",
        "month",
        "subject",
        "subject_html",
        "message_id",
        "in_reply_to",
        "references",
        "message_hash",
        "mbox_alignment_score",
        "mbox_alignment_index",
        "thread_root_id",
        "thread_depth",
    ]
    write_csv(processed_dir / "months.csv", month_rows, list(month_rows[0].keys()) if month_rows else [])
    write_csv(processed_dir / "messages_raw.csv", message_rows, message_fields)
    write_csv(processed_dir / "parse_issues.csv", parse_issues, ["slug", "issue", "archive_count", "mbox_count"])
    write_csv(processed_dir / "skipped_mbox_rows.csv", skipped_mbox_rows, ["slug", "mbox_index", "date", "author", "subject", "reason"])


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--start-year", type=int, default=1990)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between uncached HTTP requests.")
    parser.add_argument("--retries", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    harvest_archive(args.output_dir, args.start_year, args.end_year, args.insecure, args.delay, args.retries)


if __name__ == "__main__":
    main()
