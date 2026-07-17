"""Export the archive as per-thread Markdown chunks for grep / Obsidian / git.

The SQLite DB is the source of truth; this renders a readable, greppable mirror:
one ``.md`` per Gmail thread, grouped into ``md/<year>/`` folders, each with YAML
front-matter (subject, participants, span) followed by the messages in
chronological order. A ``md/INDEX.md`` links every year.

Third-party email addresses are redacted (see :mod:`nagari_group_archive.redact`,
shared with :mod:`page`), but bodies still carry real sender names and quoted
private correspondence, so ``md/`` stays git-ignored pending a human publication
decision — same rule as the DB.

Usage::

    python -m nagari_group_archive.export_md            # all threads
    python -m nagari_group_archive.export_md --min-messages 2
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from nagari_group_archive.redact import mask_name, redact_emails

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "nagari.db"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "md"

ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WS = re.compile(r"\s+")


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def slug(subject: str, limit: int = 48) -> str:
    text = ILLEGAL.sub(" ", subject or "").strip()
    text = WS.sub(" ", text)
    text = text.replace(" ", "_")
    return (text[:limit].rstrip("_") or "no-subject")


def yaml_escape(v: str) -> str:
    return '"' + (v or "").replace('"', "'") + '"'


def export(db_path: Path, out: Path, min_messages: int) -> dict:
    db = sqlite3.connect(db_path)
    rows = db.execute(
        "SELECT gm_thrid, id, date_utc, from_name, from_email, subject, subject_clean, "
        "body_text, year, n_attachments FROM messages ORDER BY gm_thrid, date_utc"
    ).fetchall()
    threads = defaultdict(list)
    for r in rows:
        threads[r[0]].append(r)

    if out.exists():
        for p in sorted(out.rglob("*.md"), reverse=True):
            p.unlink()
    out.mkdir(parents=True, exist_ok=True)

    years_index = defaultdict(list)
    written = 0
    for thr, items in threads.items():
        if not thr or len(items) < min_messages:
            continue
        items.sort(key=lambda x: x[2] or "")
        first = items[0]
        year = first[8] or "undated"
        subject = redact_emails(first[6] or first[5] or "(без темы)")
        participants = []
        for it in items:
            nm = it[3] or it[4]
            if nm:
                nm = mask_name(nm)
                if nm not in participants:
                    participants.append(nm)
        span_first = next((it[2] for it in items if it[2]), "")
        span_last = next((it[2] for it in reversed(items) if it[2]), "")

        lines = [
            "---",
            f"thread_id: {thr}",
            f"subject: {yaml_escape(subject)}",
            f"year: {year}",
            f"messages: {len(items)}",
            f"participants: {yaml_escape(', '.join(participants[:25]))}",
            f"first: {span_first}",
            f"last: {span_last}",
            "---",
            "",
            f"# {subject}",
            "",
            f"> {len(items)} сообщений · {len(participants)} участников · {span_first[:10]} — {span_last[:10]}",
            "",
        ]
        for n, it in enumerate(items, 1):
            who_raw = it[3] or it[4]
            who = mask_name(who_raw) if who_raw else "(аноним)"
            when = (it[2] or "")[:19].replace("T", " ")
            att = f" · 📎 {it[9]}" if it[9] else ""
            body = redact_emails((it[7] or "").strip())
            lines.append(f"## {n}. {who} — {when}{att}")
            lines.append("")
            lines.append(body if body else "_(пустое тело / только вложение)_")
            lines.append("")

        folder = out / str(year)
        folder.mkdir(parents=True, exist_ok=True)
        fname = f"{slug(subject)}__{thr[-8:]}.md"
        (folder / fname).write_text("\n".join(lines), encoding="utf-8")
        years_index[str(year)].append((subject, f"{year}/{fname}", len(items)))
        written += 1

    # per-year + master index
    idx = ["# Архив «Общество ревнителей санскрита» — Markdown-зеркало", "",
           f"Всего тредов: {written}", ""]
    for year in sorted(years_index, reverse=True):
        entries = sorted(years_index[year], key=lambda e: e[2], reverse=True)
        idx.append(f"## {year} ({len(entries)} тредов)")
        for subject, rel, n in entries[:400]:
            idx.append(f"- [{subject}]({rel}) — {n} сообщ.")
        idx.append("")
    (out / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")
    db.close()
    return {"threads_written": written, "years": len(years_index)}


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--min-messages", type=int, default=1)
    args = ap.parse_args(argv)
    stats = export(args.db, args.out, args.min_messages)
    print(f"md export done: {stats} -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
