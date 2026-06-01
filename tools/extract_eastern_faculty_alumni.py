"""Build a reproducible review queue for SPbU Oriental/Eastern Faculty alumni.

The script is intentionally conservative. A programme affiliation such as
"SPbU, Oriental Faculty" is evidence of institutional context, not proof that a
person graduated from the faculty. Without Gemini it emits source-backed
candidates for manual review. With --use-gemini it asks Gemini to classify the
provided local snippets, but it still writes only curator-facing statuses.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_SITE_DATA = Path("site_data_scholars.json")
DEFAULT_OUTPUT = Path("curation/eastern_faculty_alumni.csv")
FIELDNAMES = [
    "person_id",
    "display_name",
    "status",
    "source_url",
    "source_note",
    "checked_at",
    "curator_note",
]

EASTERN_FACULTY_PATTERNS = [
    re.compile(r"восточн\w*\s+факульт", re.I),
    re.compile(r"востфак", re.I),
    re.compile(r"спбгу[^.;,\n]{0,80}восточн", re.I),
    re.compile(r"ленинградск\w*\s+университет[^.;,\n]{0,100}восточн", re.I),
    re.compile(r"faculty\s+of\s+asian\s+and\s+african\s+studies", re.I),
    re.compile(r"oriental\s+faculty", re.I),
]


def load_json(path: Path):
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("const "):
        text = text.split("=", 1)[1].strip().rstrip(";")
    return json.loads(text)


def compact(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "; ".join(compact(item) for item in value if compact(item))
    if isinstance(value, dict):
        return "; ".join(f"{key}: {compact(val)}" for key, val in value.items() if compact(val))
    return re.sub(r"\s+", " ", str(value)).strip()


def scholar_context(scholar: dict) -> str:
    chunks = [
        scholar.get("full_name_ru"),
        scholar.get("full_name_en"),
        scholar.get("name"),
        scholar.get("all_affiliations"),
        scholar.get("affiliation_notes"),
        scholar.get("degree"),
        scholar.get("degree_source_url"),
    ]
    talk_bits = []
    for talk in scholar.get("talks") or []:
        talk_bits.append(
            {
                "year": talk.get("year"),
                "title": talk.get("title"),
                "affiliation": talk.get("affiliation"),
                "affiliation_reported": talk.get("affiliation_reported"),
                "source_url": talk.get("source_url"),
            }
        )
    chunks.append(talk_bits[:20])
    return compact(chunks)


def matches_eastern_faculty(text: str) -> bool:
    return any(pattern.search(text) for pattern in EASTERN_FACULTY_PATTERNS)


def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["person_id"]: row for row in csv.DictReader(f) if row.get("person_id")}


def gemini_prompt(name: str, context: str) -> str:
    return f"""
You are helping curate a prosopographic dataset for Russian Indology.
Classify whether the local evidence below proves that the person is a graduate
or alumnus/alumna of the Oriental Faculty / Faculty of Asian and African Studies
at St Petersburg University.

Important rule: affiliation or employment at the faculty is only a candidate
signal, not proof of graduation.

Return only JSON:
{{
  "status": "confirmed" | "candidate" | "rejected",
  "evidence": "short evidence phrase",
  "confidence": 0.0
}}

Person: {name}
Local snippets: {context[:6000]}
""".strip()


def call_gemini(prompt: str, model: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", "replace")) from exc
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.I | re.M).strip()
    return json.loads(text)


def build_rows(site_data: Path, use_gemini: bool, model: str, limit: int | None) -> list[dict]:
    scholars = load_json(site_data)
    rows = []
    for scholar in scholars:
        context = scholar_context(scholar)
        if not matches_eastern_faculty(context):
            continue
        name = scholar.get("full_name_ru") or scholar.get("name") or scholar.get("id")
        status = "needs_source"
        note = "Heuristic candidate: local corpus mentions SPbU Oriental/Eastern Faculty; alumni status still requires source-backed verification."
        if use_gemini:
            verdict = call_gemini(gemini_prompt(name, context), model)
            status = verdict.get("status") or "candidate"
            note = f"Gemini {model}: {verdict.get('evidence', '').strip()} confidence={verdict.get('confidence')}"
        rows.append(
            {
                "person_id": scholar.get("id") or "",
                "display_name": name,
                "status": status,
                "source_url": compact(scholar.get("degree_source_url")),
                "source_note": note,
                "checked_at": "",
                "curator_note": "",
            }
        )
        if limit and len(rows) >= limit:
            break
    return rows


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-data", type=Path, default=DEFAULT_SITE_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="Merge candidates into the curated CSV.")
    parser.add_argument("--use-gemini", action="store_true", help="Ask Gemini to classify local snippets.")
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows_by_id = load_existing(args.output)
    for row in build_rows(args.site_data, args.use_gemini, args.model, args.limit):
        rows_by_id.setdefault(row["person_id"], row)

    rows = sorted(rows_by_id.values(), key=lambda row: (row.get("display_name") or "", row.get("person_id") or ""))
    if args.write:
        write_rows(args.output, rows)
        print(f"Wrote {len(rows)} rows to {args.output}")
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
