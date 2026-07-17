"""H1142 — extract nagari attachments locally for rights-triage inspection.

Writes blobs to nagari/data/attachments/ (inside the blanket-ignored nagari/data/ —
verified with `git check-ignore -v` before first write). Extraction is for INSPECTION
by the rights census only; nothing here is a publication step.

Also emits nagari/data/attachment_evidence.jsonl: one row per BOOK-LIKE attachment
(ext in pdf/djvu/doc/docx/epub) with the identification evidence the census judges
from — filename, poster, date, thread subject, message-body head, and (for PDFs)
embedded metadata + first-page text via pypdf when available.

Deterministic; UTF-8. Fable 5 (claude-fable-5), 17-07-2026.
"""

import json
import mailbox
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
MAIN = Path(r"C:\Users\user\Documents\GitHub\IndologyScholars")
DB = MAIN / "nagari" / "data" / "nagari.db"
MBOX = MAIN / "nagari-2005-2026" / "nagari@googlegroups.com" / "topics.mbox"
OUT_DIR = MAIN / "nagari" / "data" / "attachments"
EVIDENCE = MAIN / "nagari" / "data" / "attachment_evidence.jsonl"

BOOK_EXT = ("pdf", "djvu", "doc", "docx", "epub")


def norm_mid(s):
    return (s or "").strip().strip("<>").strip()


def safe_name(att_id, filename):
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename or "unnamed")[:120]
    return f"{att_id}__{base}"


def main():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    atts = db.execute(
        "SELECT a.id, a.message_id AS mrow, a.filename, a.content_type, a.size_bytes, a.ext, "
        "m.message_id AS mid, m.from_name, m.from_email, m.date_utc, m.year, "
        "COALESCE(m.subject_clean, m.subject) AS subject, m.body_text "
        "FROM attachments a JOIN messages m ON a.message_id = m.id"
    ).fetchall()
    by_mid = {}
    for r in atts:
        by_mid.setdefault(norm_mid(r["mid"]), []).append(r)
    print(f"attachments in DB: {len(atts)} across {len(by_mid)} messages")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written, missing = 0, 0
    mbox = mailbox.mbox(str(MBOX))
    for msg in mbox:
        mid = norm_mid(msg.get("Message-Id") or msg.get("Message-ID"))
        rows = by_mid.get(mid)
        if not rows:
            continue
        parts = {}
        for part in msg.walk():
            fn = part.get_filename()
            if not fn:
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                payload = None
            if payload:
                parts.setdefault(fn, payload)
        used = set()
        for r in rows:
            payload = parts.get(r["filename"])
            key = r["filename"]
            if payload is None:
                cands = [(f, p) for f, p in parts.items()
                         if f.lower() == (r["filename"] or "").lower() and f not in used]
                if cands:
                    key, payload = cands[0]
            if payload is None and r["size_bytes"]:
                # RFC2231/encoded-name drift: pair by closest payload size (±2% or ±2KB)
                tol = max(2048, int(r["size_bytes"]) * 0.02)
                cands = sorted(
                    ((abs(len(p) - int(r["size_bytes"])), f, p) for f, p in parts.items() if f not in used),
                    key=lambda x: x[0])
                if cands and cands[0][0] <= tol:
                    _, key, payload = cands[0]
            if payload is None:
                missing += 1
                continue
            used.add(key)
            (OUT_DIR / safe_name(r["id"], r["filename"])).write_bytes(payload)
            written += 1
    print(f"extracted: {written} · unmatched-in-mbox: {missing}")

    # evidence for book-like rows
    try:
        from pypdf import PdfReader
        have_pypdf = True
    except ImportError:
        have_pypdf = False
        print("WARN: pypdf unavailable — PDF metadata/first-page evidence skipped")

    n = 0
    with EVIDENCE.open("w", encoding="utf-8") as out:
        for r in atts:
            if (r["ext"] or "").lower() not in BOOK_EXT:
                continue
            body = (r["body_text"] or "").strip().replace("\r", "")
            ev = {
                "att_id": r["id"], "filename": r["filename"], "ext": r["ext"],
                "size_bytes": r["size_bytes"], "content_type": r["content_type"],
                "poster_name": r["from_name"], "poster_email": r["from_email"],
                "date": r["date_utc"], "year": r["year"], "subject": r["subject"],
                "body_head": body[:600],
                "pdf_meta": None, "page1_text": None, "extract_ok": False,
            }
            f = OUT_DIR / safe_name(r["id"], r["filename"])
            if f.exists():
                ev["extract_ok"] = True
                if have_pypdf and (r["ext"] or "").lower() == "pdf":
                    try:
                        reader = PdfReader(str(f))
                        meta = reader.metadata or {}
                        ev["pdf_meta"] = {k: str(v)[:200] for k, v in dict(meta).items()}
                        pages_text = []
                        for p in reader.pages[:3]:
                            try:
                                pages_text.append(p.extract_text() or "")
                            except Exception:
                                pages_text.append("")
                        ev["page1_text"] = re.sub(r"\s+", " ", " ".join(pages_text))[:900] or None
                    except Exception as e:
                        ev["pdf_meta"] = {"_error": str(e)[:150]}
            out.write(json.dumps(ev, ensure_ascii=False) + "\n")
            n += 1
    print(f"evidence rows (book-like): {n} -> {EVIDENCE}")


if __name__ == "__main__":
    main()
