"""Ingest the Google Takeout ``topics.mbox`` into a searchable SQLite database.

The Takeout export of a Google Group ships one big RFC-4155 mbox (all messages,
newest-first) plus ``members.csv``. This module parses every message with the
modern :mod:`email` API (``policy=default`` so MIME parts, base64/quoted-printable
transfer encodings and RFC-2047 headers are decoded for us), reconstructs threads
from the Gmail thread id (``X-GM-THRID``), records attachment *metadata* (never the
blobs), and writes:

* ``messages``      — one row per message, with decoded plain-text body.
* ``attachments``   — one row per attachment (filename, type, size).
* ``members``       — the roster from ``members.csv``.
* ``messages_fts``  — an FTS5 index over subject + body + sender for ranked
  full-text search across Russian, IAST and Devanagari (unicode61, diacritics
  folded so ``atman`` matches ``ātman``).

Usage::

    python -m nagari_group_archive.ingest --limit 300     # quick validation slice
    python -m nagari_group_archive.ingest                 # full run

Nothing here is destructive to the source: the mbox is opened read-only.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import time
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths: the raw dump lives in the *main* checkout (git-ignored, 1.88 GB); this
# package is built in an isolated worktree, so default to an absolute location
# and let the CLI override it.
# ---------------------------------------------------------------------------
DEFAULT_DUMP = Path(
    r"C:/Users/user/Documents/GitHub/IndologyScholars/nagari-2005-2026/nagari@googlegroups.com"
)
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "nagari.db"

RE_PREFIX = re.compile(
    r"^\s*(re|re\[\d+\]|aw|sv|fwd|fw|отв|пересылаемое сообщение)\s*[:\]]?\s*",
    re.IGNORECASE,
)
RE_LISTTAG = re.compile(r"^\s*\[[^\]]{1,40}\]\s*")
RE_WS = re.compile(r"\s+")
RE_TAG = re.compile(r"<[^>]+>")
RE_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def decode_hdr(value: str | None) -> str:
    """Decode an RFC-2047 header to a clean unicode string."""
    if not value:
        return ""
    try:
        text = str(make_header(decode_header(value)))
    except Exception:
        text = str(value)
    return RE_WS.sub(" ", text.replace(" ", " ")).strip()


def clean_subject(subject: str) -> str:
    """Strip Re:/Fwd:/list-tag noise to a thread-stable subject."""
    text = subject or ""
    prev = None
    while prev != text:
        prev = text
        text = RE_PREFIX.sub("", text)
        text = RE_LISTTAG.sub("", text)
    return RE_WS.sub(" ", text).strip()


def html_to_text(html: str) -> str:
    text = RE_STYLE.sub(" ", html or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = RE_TAG.sub("", text)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(a, b)
    return re.sub(r"[ \t]*\n[ \t]*", "\n", text).strip()


def part_text(part: EmailMessage) -> str:
    """Best-effort decode of a single text/* part to unicode."""
    try:
        content = part.get_content()
        return content if isinstance(content, str) else content.decode("utf-8", "replace")
    except Exception:
        raw = part.get_payload(decode=True)
        if not raw:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, "replace")
        except (LookupError, TypeError):
            return raw.decode("utf-8", "replace")


def extract(msg: EmailMessage) -> tuple[str, list[dict]]:
    """Return (plain-text body, attachment metadata list)."""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict] = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get_content_disposition() or "").lower()
        filename = decode_hdr(part.get_filename())

        if disp == "attachment" or filename:
            raw = part.get_payload(decode=False)
            cte = (part.get("Content-Transfer-Encoding") or "").lower()
            if isinstance(raw, str) and cte == "base64":
                size = int(len(re.sub(r"\s", "", raw)) * 3 / 4)  # estimate, no blob decode
            else:
                try:
                    size = len(part.get_payload(decode=True) or b"")
                except Exception:
                    size = 0
            ext = Path(filename).suffix.lower().lstrip(".") if filename else ""
            attachments.append(
                {"filename": filename, "content_type": ctype, "size_bytes": size, "ext": ext}
            )
            continue

        if ctype == "text/plain":
            plain_parts.append(part_text(part))
        elif ctype == "text/html":
            html_parts.append(part_text(part))

    if plain_parts:
        body = "\n".join(p for p in plain_parts if p).strip()
    else:
        body = "\n".join(html_to_text(h) for h in html_parts if h).strip()
    return body, attachments


def iter_messages(mbox_path: Path, limit: int | None = None):
    """Yield parsed message dicts from the mbox, streaming (low memory).

    We parse the mbox boundaries ourselves rather than via :class:`mailbox.mbox`
    so the 1.88 GB file streams without building a full in-memory table of
    contents, and so a single malformed message never aborts the run.
    """
    parser = BytesParser(policy=policy.default)
    from_re = re.compile(rb"^From ", re.MULTILINE)
    with mbox_path.open("rb") as fh:
        buf: list[bytes] = []
        idx = 0

        def flush(block: bytes):
            nonlocal idx
            block = block.strip(b"\n")
            if not block:
                return None
            idx += 1
            try:
                msg = parser.parsebytes(block)
            except Exception as exc:  # pragma: no cover - defensive
                return {"_index": idx, "_error": f"parse:{exc}"}
            return parse_message(msg, idx)

        for line in fh:
            if line.startswith(b"From ") and buf:
                out = flush(b"".join(buf))
                buf = [line]
                if out is not None:
                    yield out
                    if limit and idx >= limit:
                        return
            else:
                buf.append(line)
        if buf:
            out = flush(b"".join(buf))
            if out is not None:
                yield out


def parse_message(msg: EmailMessage, idx: int) -> dict:
    subject = decode_hdr(msg.get("Subject"))
    from_name, from_email = parseaddr(decode_hdr(msg.get("From")))
    date_raw = msg.get("Date")
    dt = None
    if date_raw:
        try:
            dt = parsedate_to_datetime(date_raw)
        except (TypeError, ValueError, IndexError):
            dt = None
    iso = dt.astimezone().isoformat() if dt and dt.tzinfo else (dt.isoformat() if dt else "")
    year = dt.year if dt else None
    month = dt.month if dt else None
    ym = f"{dt.year:04d}-{dt.month:02d}" if dt else ""

    body, attachments = extract(msg)
    body = body[:400_000]  # guard against pathological quoted mega-threads
    return {
        "_index": idx,
        "gm_thrid": (msg.get("X-GM-THRID") or "").strip(),
        "gmail_labels": (msg.get("X-Gmail-Labels") or "").strip(),
        "message_id": (msg.get("Message-Id") or msg.get("Message-ID") or "").strip(),
        "in_reply_to": (msg.get("In-Reply-To") or "").strip(),
        "references": (msg.get("References") or "").strip(),
        "date_utc": iso,
        "year": year,
        "month": month,
        "ym": ym,
        "from_name": from_name.strip(),
        "from_email": from_email.strip().lower(),
        "to_raw": decode_hdr(msg.get("To"))[:1000],
        "subject": subject,
        "subject_clean": clean_subject(subject),
        "body_text": body,
        "body_chars": len(body),
        "attachments": attachments,
    }


SCHEMA = """
CREATE TABLE messages (
    id            INTEGER PRIMARY KEY,
    gm_thrid      TEXT,
    gmail_labels  TEXT,
    message_id    TEXT,
    in_reply_to   TEXT,
    references_raw TEXT,
    date_utc      TEXT,
    year          INTEGER,
    month         INTEGER,
    ym            TEXT,
    from_name     TEXT,
    from_email    TEXT,
    to_raw        TEXT,
    subject       TEXT,
    subject_clean TEXT,
    body_text     TEXT,
    body_chars    INTEGER,
    n_attachments INTEGER,
    has_pdf       INTEGER
);
CREATE TABLE attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   INTEGER REFERENCES messages(id),
    filename     TEXT,
    content_type TEXT,
    size_bytes   INTEGER,
    ext          TEXT
);
CREATE TABLE members (
    display_name TEXT,
    email        TEXT,
    delivery     TEXT,
    role         TEXT,
    joined_utc   TEXT,
    joined_year  INTEGER
);
CREATE TABLE parse_issues (
    mbox_index INTEGER,
    error      TEXT
);
CREATE INDEX idx_msg_thrid ON messages(gm_thrid);
CREATE INDEX idx_msg_ym    ON messages(ym);
CREATE INDEX idx_msg_email ON messages(from_email);
CREATE INDEX idx_att_msg   ON attachments(message_id);
CREATE INDEX idx_att_ext   ON attachments(ext);
CREATE VIRTUAL TABLE messages_fts USING fts5(
    subject_clean, body_text, from_name,
    from_email UNINDEXED, ym UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def load_members(db: sqlite3.Connection, members_csv: Path) -> int:
    if not members_csv.exists():
        return 0
    rows = []
    with members_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            ts = (r.get("updatedTimestamp") or "").strip()
            jy = int(ts[:4]) if ts[:4].isdigit() else None
            rows.append(
                (
                    (r.get("displayName") or "").strip(),
                    (r.get("email") or "").strip().lower(),
                    (r.get("emailDeliverySetting") or "").strip(),
                    (r.get("role") or "").strip(),
                    ts,
                    jy,
                )
            )
    db.executemany(
        "INSERT INTO members(display_name,email,delivery,role,joined_utc,joined_year) VALUES (?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def build(dump: Path, db_path: Path, limit: int | None) -> dict:
    mbox_path = dump / "topics.mbox"
    members_csv = dump / "members.csv"
    if not mbox_path.exists():
        raise FileNotFoundError(f"missing {mbox_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)

    n_msg = n_att = n_err = 0
    start = time.time()
    for rec in iter_messages(mbox_path, limit=limit):
        if rec.get("_error"):
            db.execute("INSERT INTO parse_issues(mbox_index,error) VALUES (?,?)", (rec["_index"], rec["_error"]))
            n_err += 1
            continue
        atts = rec["attachments"]
        has_pdf = 1 if any(a["ext"] == "pdf" or "pdf" in a["content_type"] for a in atts) else 0
        db.execute(
            """INSERT INTO messages(id,gm_thrid,gmail_labels,message_id,in_reply_to,references_raw,
               date_utc,year,month,ym,from_name,from_email,to_raw,subject,subject_clean,
               body_text,body_chars,n_attachments,has_pdf)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rec["_index"], rec["gm_thrid"], rec["gmail_labels"], rec["message_id"],
                rec["in_reply_to"], rec["references"], rec["date_utc"], rec["year"], rec["month"],
                rec["ym"], rec["from_name"], rec["from_email"], rec["to_raw"], rec["subject"],
                rec["subject_clean"], rec["body_text"], rec["body_chars"], len(atts), has_pdf,
            ),
        )
        for a in atts:
            db.execute(
                "INSERT INTO attachments(message_id,filename,content_type,size_bytes,ext) VALUES (?,?,?,?,?)",
                (rec["_index"], a["filename"], a["content_type"], a["size_bytes"], a["ext"]),
            )
            n_att += 1
        n_msg += 1
        if n_msg % 1000 == 0:
            db.commit()
            print(f"  ... {n_msg} messages, {n_att} attachments, {time.time()-start:.0f}s", flush=True)

    print("  populating FTS index ...", flush=True)
    db.execute(
        "INSERT INTO messages_fts(rowid,subject_clean,body_text,from_name,from_email,ym) "
        "SELECT id,subject_clean,body_text,from_name,from_email,ym FROM messages"
    )
    n_mem = load_members(db, members_csv)
    db.commit()
    db.execute("PRAGMA optimize")
    db.close()
    return {"messages": n_msg, "attachments": n_att, "members": n_mem, "errors": n_err, "seconds": round(time.time() - start, 1)}


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", type=Path, default=DEFAULT_DUMP, help="Takeout folder with topics.mbox + members.csv")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="output SQLite path")
    ap.add_argument("--limit", type=int, default=None, help="parse only the first N messages (validation)")
    args = ap.parse_args(argv)
    print(f"Ingesting {args.dump / 'topics.mbox'}", flush=True)
    stats = build(args.dump, args.db, args.limit)
    print(f"Done: {stats}", flush=True)
    print(f"DB: {args.db}", flush=True)


if __name__ == "__main__":
    main()
