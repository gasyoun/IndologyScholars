"""Build a review queue for Wikipedia pages or mentions of archive scholars.

This script does not mutate authority_ids.json. It writes candidates so the
authority layer can be expanded deliberately:
- analytics_output/wikipedia_authority_candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site_data.json"
AUTHORITY = ROOT / "authority_ids.json"
ANALYTICS = ROOT / "analytics_output"
API = "https://ru.wikipedia.org/w/api.php"
USER_AGENT = "IndologyScholarsAuthorityAudit/1.0 (https://gasyoun.github.io/IndologyScholars/)"


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_tags(value: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", html.unescape(value or "")))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def name_query(scholar: dict) -> str:
    return clean_text(scholar.get("full_name_ru") or scholar.get("original_fullname") or scholar.get("name"))


def surname_and_given(name: str) -> tuple[str, str]:
    parts = [part for part in re.findall(r"[А-ЯЁа-яёA-Za-z-]+", name) if part]
    if not parts:
        return "", ""
    if len(parts) >= 2 and not re.match(r"^[А-ЯЁA-Z]$", parts[0]):
        return parts[0].lower(), parts[1].lower()
    return parts[-1].lower(), ""


def page_url(title: str) -> str:
    return "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def wiki_search(query: str, limit: int = 3, timeout: int = 20) -> list[dict]:
    params = {
        "action": "query",
        "list": "search",
        "format": "json",
        "utf8": "1",
        "srlimit": str(limit),
        "srsearch": query,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("query", {}).get("search", [])


def score_candidate(query: str, candidate: dict) -> tuple[str, int]:
    surname, given = surname_and_given(query)
    title = clean_text(candidate.get("title")).lower()
    snippet = strip_tags(candidate.get("snippet")).lower()
    haystack = f"{title} {snippet}"
    if surname and surname in title and given and given in title:
        return "page_title_full_name", 95
    if surname and surname in title:
        return "page_title_surname", 80
    if surname and surname in haystack:
        return "mention_or_search_snippet", 60
    return "weak_search_hit", 30


def build_rows(limit: int = 0, sleep_seconds: float = 0.05) -> list[dict]:
    data = load_json(SITE_DATA)
    authority = load_json(AUTHORITY)
    persons_auth = authority.get("persons") or {}
    scholars = data.get("scholars") or []
    rows = []
    checked = 0

    for scholar in scholars:
        pid = scholar.get("id") or ""
        person_auth = persons_auth.get(pid) or {}
        existing = clean_text(person_auth.get("wikipedia"))
        query = name_query(scholar)
        if existing:
            rows.append(
                {
                    "person_id": pid,
                    "name": query,
                    "total_talks": scholar.get("total_talks") or 0,
                    "status": "already_confirmed",
                    "candidate_title": "",
                    "candidate_url": existing,
                    "match_type": "curated_authority_ids",
                    "score": 100,
                    "snippet": "",
                    "review_status": "done",
                }
            )
            continue
        if not query:
            continue
        if limit and checked >= limit:
            break
        checked += 1
        try:
            candidates = wiki_search(query)
        except Exception as exc:
            rows.append(
                {
                    "person_id": pid,
                    "name": query,
                    "total_talks": scholar.get("total_talks") or 0,
                    "status": "lookup_error",
                    "candidate_title": "",
                    "candidate_url": "",
                    "match_type": type(exc).__name__,
                    "score": 0,
                    "snippet": clean_text(exc),
                    "review_status": "todo",
                }
            )
            continue
        if not candidates:
            rows.append(
                {
                    "person_id": pid,
                    "name": query,
                    "total_talks": scholar.get("total_talks") or 0,
                    "status": "no_hit",
                    "candidate_title": "",
                    "candidate_url": "",
                    "match_type": "",
                    "score": 0,
                    "snippet": "",
                    "review_status": "todo",
                }
            )
        for candidate in candidates[:3]:
            match_type, score = score_candidate(query, candidate)
            rows.append(
                {
                    "person_id": pid,
                    "name": query,
                    "total_talks": scholar.get("total_talks") or 0,
                    "status": "candidate" if score >= 60 else "weak_candidate",
                    "candidate_title": clean_text(candidate.get("title")),
                    "candidate_url": page_url(clean_text(candidate.get("title"))),
                    "match_type": match_type,
                    "score": score,
                    "snippet": strip_tags(candidate.get("snippet"))[:500],
                    "review_status": "todo",
                }
            )
        if sleep_seconds:
            time.sleep(sleep_seconds)
    rows.sort(key=lambda row: (-int(row["score"]), -int(row["total_talks"] or 0), row["name"], row["candidate_title"]))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit network lookups; 0 means all scholars without a curated Wikipedia URL.")
    parser.add_argument("--sleep", type=float, default=0.05, help="Delay between API calls.")
    args = parser.parse_args()

    rows = build_rows(limit=args.limit, sleep_seconds=args.sleep)
    write_csv(
        ANALYTICS / "wikipedia_authority_candidates.csv",
        rows,
        [
            "person_id",
            "name",
            "total_talks",
            "status",
            "candidate_title",
            "candidate_url",
            "match_type",
            "score",
            "snippet",
            "review_status",
        ],
    )
    confirmed = sum(1 for row in rows if row["status"] == "already_confirmed")
    candidates = sum(1 for row in rows if row["status"] == "candidate")
    print(f"wikipedia audit: {confirmed} confirmed links; {candidates} candidate rows")


if __name__ == "__main__":
    main()
