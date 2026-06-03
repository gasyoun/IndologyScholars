"""Parse Zograf sbornik PDF tables of contents and match articles to talks.

Downloads the 2 sbornik TOC PDFs (M005, M006) from orientalstudies.ru,
extracts text, parses author–article entries, and fuzzy-matches them
against presentation titles in the database.

Usage:
  pip install pymupdf
  python tools/parse_sbornik_toc.py               # download + parse + match
  python tools/parse_sbornik_toc.py --skip-download  # use cached PDFs
  python tools/parse_sbornik_toc.py --dry-run      # show PDF list, don't process

Output:
  analytics_output/publication_conversion.csv
"""

import csv
import difflib
import os
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
CACHE_DIR = ROOT / "html_cache" / "sborniki"
OUT_PATH = ROOT / "analytics_output" / "publication_conversion.csv"

USER_AGENT = "IndologyScholars/1.0 (research bot; gasyoun@gmail.com)"
SIMILARITY_THRESHOLD = 0.65  # difflib ratio for fuzzy match

# PDF media records with sbornik TOCs
SBORNIK_SOURCES = [
    {
        "media_id": "M005",
        "sbornik": "Зографский сборник. Вып. 2",
        "year": 2011,
        "url": "https://www.orientalstudies.ru/rus/images/pdf/b_vassilkov_co_2011b.pdf",
    },
    {
        "media_id": "M006",
        "sbornik": "Шабдапракаша. Зографский сборник. Вып. I",
        "year": 2011,
        "url": "https://www.orientalstudies.ru/rus/images/pdf/b_vassilkov_co_2011.pdf",
    },
]


def download_pdf(media_id: str, url: str) -> Path | None:
    """Download a PDF to the cache directory."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = CACHE_DIR / f"{media_id}.pdf"
    if local_path.exists():
        print(f"  [cached] {local_path}")
        return local_path

    print(f"  [download] {url[:80]}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            local_path.write_bytes(resp.read())
        print(f"  [saved] {local_path} ({local_path.stat().st_size} bytes)")
        return local_path
    except Exception as e:
        print(f"  [error] {e}")
        return None


def extract_text(pdf_path: Path) -> str:
    """Extract text from PDF using pymupdf (fitz)."""
    try:
        import fitz
    except ImportError:
        sys.exit("Install pymupdf: pip install pymupdf")

    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    doc.close()
    return text


def parse_toc_entries(text: str) -> list[tuple[str, str]]:
    """Parse author–article entries from sbornik table of contents text.

    Returns list of (author, title) tuples.
    """
    entries = []
    lines = text.split("\n")

    # Russian TOC format patterns:
    # "И.О. Фамилия. Название статьи"
    # "Фамилия И.О. Название статьи"
    author_pattern = re.compile(
        r"^([А-ЯЁ][а-яё]*(?:\s+[А-ЯЁ]\.)*\s+[А-ЯЁ][а-яё]+)\s*[\.]\s*(.+)"
    )
    initials_pattern = re.compile(
        r"^((?:[А-ЯЁ]\.\s*)+[А-ЯЁ][а-яё]+)\s*[\.]\s*(.+)"
    )

    current_author = None
    current_title = ""

    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Skip header/footer lines
        if any(hdr in line.lower() for hdr in ["содержание", "оглавление", "issn", "удк", "contents"]):
            continue
        if re.match(r"^\d+$", line):
            continue

        # Try to match author pattern
        m = author_pattern.match(line) or initials_pattern.match(line)
        if m:
            # Save previous entry
            if current_author and current_title:
                entries.append((current_author, current_title))
            current_author = m.group(1).strip()
            current_title = m.group(2).strip()
        elif current_author:
            # Continuation of multi-line title
            current_title += " " + line

    # Don't forget last entry
    if current_author and current_title:
        entries.append((current_author, current_title))

    return entries


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, remove punctuation, collapse whitespace."""
    title = title.lower().strip()
    title = re.sub(r"[«»\"'.,:;!?()\[\]–—-]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def fuzzy_match(talk_title: str, article: tuple[str, str]) -> float:
    """Compute similarity between a talk title and a sbornik article entry."""
    talk_norm = normalize_title(talk_title)
    # Match against article title, optionally with author context
    article_text = normalize_title(article[1])
    # Also try matching author+title combined
    full_text = normalize_title(f"{article[0]} {article[1]}")
    ratio1 = difflib.SequenceMatcher(None, talk_norm, article_text).ratio()
    ratio2 = difflib.SequenceMatcher(None, talk_norm, full_text).ratio()
    return max(ratio1, ratio2)


def match_against_db(articles: list[tuple[str, str]], sbornik: str, pdf_url: str) -> list[dict]:
    """Fuzzy-match sbornik articles against DB presentations."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT pr.presentation_id, pr.title, p.display_name, p.full_name_ru
                 FROM presentation pr
                 LEFT JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id AND pp.role = 'speaker'
                 LEFT JOIN person p ON pp.person_id = p.person_id""")
    talks = c.fetchall()
    conn.close()

    results = []
    for author, art_title in articles:
        best_ratio = 0.0
        best_talk = None
        for pid, talk_title, dname, fname in talks:
            if not talk_title:
                continue
            ratio = fuzzy_match(talk_title, (author, art_title))
            if ratio > best_ratio:
                best_ratio = ratio
                best_talk = (pid, talk_title, fname or dname or "", ratio)

        if best_talk and best_ratio >= SIMILARITY_THRESHOLD:
            results.append({
                "presentation_id": best_talk[0],
                "talk_title": best_talk[1],
                "article_author": author,
                "article_title": art_title,
                "sbornik": sbornik,
                "pdf_url": pdf_url,
                "confidence": round(best_ratio, 3),
            })

    return results


def run(dry_run: bool = False, skip_download: bool = False):
    if dry_run:
        print("PDF sources:")
        for s in SBORNIK_SOURCES:
            print(f"  {s['media_id']}: {s['sbornik']}")
        return

    all_results = []

    for src in SBORNIK_SOURCES:
        print(f"\n{'='*60}")
        print(f"{src['media_id']}: {src['sbornik']}")
        print(f"{'='*60}")

        pdf_path = None
        if not skip_download:
            pdf_path = download_pdf(src["media_id"], src["url"])
            if not pdf_path:
                continue
            time.sleep(1)

        if pdf_path:
            print("  Extracting text...")
            text = extract_text(pdf_path)
            print(f"  Extracted {len(text)} chars, {len(text.splitlines())} lines")

            articles = parse_toc_entries(text)
            print(f"  Parsed {len(articles)} author–article entries")
            for a, t in articles[:5]:
                print(f"    {a[:30]:30s} | {t[:50]}")

            results = match_against_db(articles, src["sbornik"], src["url"])
            print(f"  Matched {len(results)} articles to talks (threshold >= {SIMILARITY_THRESHOLD})")
            all_results.extend(results)

    # Write results
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["presentation_id", "talk_title", "article_author", "article_title",
              "sbornik", "pdf_url", "confidence"]
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_results)

    print(f"\n{'='*60}")
    print(f"Total matched: {len(all_results)} articles -> {OUT_PATH}")
    if all_results:
        print("\nTop matches:")
        for r in sorted(all_results, key=lambda x: -x["confidence"])[:10]:
            print(f"  [{r['confidence']:.2f}] {r['talk_title'][:50]:50s} ← {r['article_title'][:40]}")

    print(f"\nNext: rebuild site data with python generate_site_data.py")


if __name__ == "__main__":
    run(
        dry_run="--dry-run" in sys.argv,
        skip_download="--skip-download" in sys.argv,
    )
