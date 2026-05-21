"""Export a presentation ID stability manifest from conferences.db.

This is an audit tool: it does not modify the database. Run it before and
after a rebuild, then compare the two manifests with compare_id_manifests.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import unicodedata
from pathlib import Path


DEFAULT_DB = Path("conferences.db")
DEFAULT_OUT = Path("analytics_output/presentation_id_manifest.csv")


def canonical_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text


def stable_key_hash(*parts: object) -> str:
    basis = "|".join(canonical_text(part) for part in parts)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def source_snippet_hash(value: object) -> str:
    text = canonical_text(value)
    if not text:
        return ""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def fetch_rows(db_path: Path) -> list[dict[str, object]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            pr.presentation_id,
            es.series_name_en AS series,
            e.year,
            e.event_id,
            pr.session_id,
            pr.title,
            pr.source_url,
            pr.source_snippet,
            GROUP_CONCAT(
                CASE
                    WHEN pp.author_order IS NOT NULL THEN printf('%04d:', pp.author_order)
                    ELSE '9999:'
                END || COALESCE(p.full_name_ru, p.display_name),
                ' || '
            ) AS ordered_speakers
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        LEFT JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        LEFT JOIN person p ON p.person_id = pp.person_id
        GROUP BY pr.presentation_id
        ORDER BY e.year, es.series_name_en, pr.title, pr.presentation_id
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clean_speakers(value: object) -> tuple[str, str]:
    raw = "" if value is None else str(value)
    speakers = []
    for item in raw.split(" || "):
        if ":" in item:
            item = item.split(":", 1)[1]
        item = item.strip()
        if item:
            speakers.append(item)
    return (speakers[0] if speakers else "", " | ".join(speakers))


def build_manifest_rows(db_path: Path) -> list[dict[str, object]]:
    manifest_rows = []
    for row in fetch_rows(db_path):
        first_speaker, all_speakers = clean_speakers(row.get("ordered_speakers"))
        stable_key_candidate = stable_key_hash(
            row.get("series"),
            row.get("year"),
            row.get("title"),
            first_speaker,
            row.get("source_url"),
        )
        manifest_rows.append(
            {
                "presentation_id": row.get("presentation_id") or "",
                "series": row.get("series") or "",
                "year": row.get("year") or "",
                "event_id": row.get("event_id") or "",
                "session_id": row.get("session_id") or "",
                "title": row.get("title") or "",
                "first_speaker": first_speaker,
                "all_speakers": all_speakers,
                "source_url": row.get("source_url") or "",
                "source_snippet_hash": source_snippet_hash(row.get("source_snippet")),
                "stable_key_candidate": stable_key_candidate,
            }
        )
    return manifest_rows


def write_manifest(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "presentation_id",
        "series",
        "year",
        "event_id",
        "session_id",
        "title",
        "first_speaker",
        "all_speakers",
        "source_url",
        "source_snippet_hash",
        "stable_key_candidate",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="CSV manifest output path")
    args = parser.parse_args()

    db_path = Path(args.db)
    out_path = Path(args.out)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    rows = build_manifest_rows(db_path)
    write_manifest(rows, out_path)

    stable_keys = [row["stable_key_candidate"] for row in rows]
    duplicate_stable_keys = len(stable_keys) - len(set(stable_keys))
    print(f"Wrote {len(rows)} presentation manifest rows to {out_path}")
    print(f"Duplicate stable_key_candidate rows: {duplicate_stable_keys}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
