"""Scraper: find missing birth years via web search and institutional pages.

For scholars missing birth_year in the database, try:
  1. Wikipedia (ru.wikipedia.org) — most reliable
  2. Institutional staff pages (ИВР РАН, ИВ РАН, МАЭ РАН, СПбГУ)
  3. General web search patterns (поиск по имени + индолог/востоковед)

Usage:
  python tools/scrape_birth_years.py             # all missing scholars
  python tools/scrape_birth_years.py --dry-run    # show plan only
  python tools/scrape_birth_years.py --limit 5    # first 5 only

Output:
  curation/birth_year_findings.csv   — found birth years
  curation/birth_year_missing.csv    — still missing (for manual search)
"""

import csv
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
OUT_FOUND = ROOT / "curation" / "birth_year_findings.csv"
OUT_MISSING = ROOT / "curation" / "birth_year_missing.csv"

USER_AGENT = "IndologyScholars/1.0 (research bot; gasyoun@gmail.com)"
REQUEST_DELAY = 1.5  # seconds between requests


def get_missing_scholars() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT p.person_id, p.full_name_ru, p.display_name,
                 GROUP_CONCAT(pp.affiliation_text_raw, ' | ') as affs,
                 COUNT(DISTINCT pp.presentation_id) as talks
    FROM person p
    JOIN presentation_person pp ON p.person_id = pp.person_id
    WHERE pp.role='speaker' AND (p.birth_year IS NULL OR p.birth_year = 0)
    GROUP BY p.person_id
    ORDER BY talks DESC""")

    scholars = []
    for pid, fname, dname, affs_str, talks in c.fetchall():
        name = fname or dname or pid
        affs = list(set((affs_str or '').split(' | ')))
        inst_patterns = ['РАН', 'университет', 'институт', 'музей', 'СПбГУ', 'МГУ', 'ВШЭ', 'РГГУ', 'РУДН', 'College', 'University', 'центр', 'школа']
        real = [a for a in affs if any(p in a for p in inst_patterns)]
        cities = [a for a in affs if a not in real]
        best_aff = real[0] if real else (cities[0] if cities else 'N/A')

        scholars.append({
            "person_id": pid,
            "full_name": name,
            "talks": talks,
            "best_affiliation": best_aff,
            "all_affiliations": affs_str,
            "has_institution": len(real) > 0,
        })
    conn.close()
    return scholars


def fetch_url(url: str, timeout: int = 12) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            for enc in ['utf-8', 'windows-1251', 'cp1251', 'koi8-r']:
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode('utf-8', errors='replace')
    except Exception as e:
        return None


def extract_birth_year(text: str) -> int | None:
    """Extract birth year using multiple patterns, ordered by reliability."""
    patterns = [
        # Wikipedia infobox microformat (most reliable)
        r'<span[^>]*class="[^"]*bday[^"]*"[^>]*>(\d{4})',
        # Russian prose patterns
        r'Дата\s+рождения.*?(\d{4})',
        r'Год\s+рождения.*?(\d{4})',
        r'(?:родил[ася]+|род\.)\s*(?:в\s*)?(\d{4})',
        r'(\d{4})\s*г\.?\s*р\.',
        r'(\d{4})\s*года?\s*рождения',
        # Parenthesized year ranges: (1943—2021)
        r'\((\d{4})\s*[-–—]\s*\d{0,4}\)',
        r'\((\d{4})\s*[-–—]\s*\)',
        # English patterns
        r'born\s*(?:in\s*)?(\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 1920 <= year <= 2005:
                return year
    return None


def try_wikipedia(name: str) -> tuple[int | None, str]:
    """Search Russian Wikipedia for a scholar."""
    slug = name.strip().replace(' ', '_')
    url = f"https://ru.wikipedia.org/wiki/{urllib.parse.quote(slug)}"
    html = fetch_url(url)
    if html:
        # Skip disambiguation/redirect/search pages
        if 'Википедия:Поиск' not in html and 'Результаты поиска' not in html:
            year = extract_birth_year(html)
            if year:
                return year, url

    # Try search with fewer terms (last name only)
    parts = name.strip().split()
    if len(parts) > 1:
        short_name = parts[0]
        search_url = f"https://ru.wikipedia.org/w/index.php?search={urllib.parse.quote(short_name)}"
        html = fetch_url(search_url)
        if html and ('результатов' in html.lower() or 'поиск' in html.lower()):
            # Search returned results — try first matching link
            links = re.findall(r'<a[^>]*href="(/wiki/[^"]+)"[^>]*>([^<]+)</a>', html)
            for link, title in links[:5]:
                # Check if the name parts match
                if all(part in title for part in parts[:2]):
                    page_url = f"https://ru.wikipedia.org{link}"
                    page_html = fetch_url(page_url)
                    if page_html:
                        year = extract_birth_year(page_html)
                        if year:
                            return year, page_url

    return None, ""


def try_dissercat(name: str) -> tuple[int | None, str]:
    """Search Dissercat for PhD thesis abstracts (always include birth year)."""
    # Search with field keywords to filter false positives
    search_url = f"https://www.dissercat.com/search?q={urllib.parse.quote(name + ' филолог')}"
    html = fetch_url(search_url)
    if not html:
        # Fallback: just name
        search_url = f"https://www.dissercat.com/search?q={urllib.parse.quote(name)}"
        html = fetch_url(search_url)

    if not html:
        return None, ""

    # Find author profile links
    links = re.findall(r'href="(/author/\d+)"', html)
    if not links:
        links = re.findall(r'href="(/content/[^"]+)"', html)

    for link in links[:3]:
        page_url = f"https://www.dissercat.com{link}"
        page_html = fetch_url(page_url)
        if not page_html:
            continue

        # Verify field relevance: skip if not philology/linguistics/history
        field_ok = any(kw in page_html.lower() for kw in [
            'филолог', 'лингвист', 'языкозна', 'индолог', 'востоковед',
            'санскрит', 'литератур', 'текстолог', 'philolog', 'linguist',
            'oriental', 'истори', 'философ', 'культуролог', 'этнограф'
        ])
        if not field_ok:
            continue

        year = extract_birth_year(page_html)
        if year:
            return year, page_url
    return None, ""


def try_elibrary(name: str) -> tuple[int | None, str]:
    """Search eLIBRARY for author profiles."""
    search_url = f"https://elibrary.ru/authors.asp?pfullname={urllib.parse.quote(name)}"
    html = fetch_url(search_url, timeout=15)
    if html:
        # eLIBRARY uses author IDs in URLs
        links = re.findall(r'href="(author_profile\.asp\?id=\d+)"', html)
        for link in links[:2]:
            page_url = f"https://elibrary.ru/{link}"
            page_html = fetch_url(page_url, timeout=15)
            if page_html:
                year = extract_birth_year(page_html)
                if year:
                    return year, page_url
    return None, ""


def try_orientalstudies(name: str) -> tuple[int | None, str]:
    """Search ИВР РАН website."""
    search_url = f"https://www.orientalstudies.ru/rus/index.php?option=com_search&searchword={urllib.parse.quote(name)}&searchphrase=all"
    html = fetch_url(search_url)
    if html:
        page_links = re.findall(r'href="(/rus/index\.php\?option=com_content[^"]+)"', html)
        for link in page_links[:2]:
            page_url = f"https://www.orientalstudies.ru{link}"
            page_html = fetch_url(page_url)
            if page_html:
                year = extract_birth_year(page_html)
                if year:
                    return year, page_url
    return None, ""


def scrape_scholar(scholar: dict) -> tuple[int | None, str]:
    """Try all sources for one scholar. Priority chain."""
    name = scholar["full_name"]

    # 1. Wikipedia (most reliable, but only notable scholars)
    year, url = try_wikipedia(name)
    if year:
        return year, url
    time.sleep(REQUEST_DELAY)

    # 2. Institutional page (if affiliation suggests one)
    affs = (scholar["all_affiliations"] or "").lower()
    if any(kw in affs for kw in ["ивр", "иностран", "orientalstudies"]):
        year, url = try_orientalstudies(name)
        if year:
            return year, url
        time.sleep(REQUEST_DELAY)

    # 3. Dissercat (PhD thesis abstracts — most reliable for Russian academics)
    year, url = try_dissercat(name)
    if year:
        return year, url
    time.sleep(REQUEST_DELAY)

    # 4. eLIBRARY (author profiles)
    year, url = try_elibrary(name)
    if year:
        return year, url

    return None, ""


def run(dry_run: bool = False, limit: int | None = None):
    scholars = get_missing_scholars()
    print(f"Scholars missing birth year: {len(scholars)}")
    print(f"  With known institution: {sum(1 for s in scholars if s['has_institution'])}")
    print(f"  City-only affiliation:  {sum(1 for s in scholars if not s['has_institution'])}")
    print(f"  Sources: Wikipedia -> institutional sites -> Dissercat -> eLIBRARY")
    print()

    if limit:
        scholars = scholars[:limit]

    if dry_run:
        print("[Dry run — no HTTP requests]")
        for s in scholars:
            print(f"  {s['full_name'][:50]:50s} | {s['talks']} talks | {s['best_affiliation'][:40]}")
        return

    found = []
    still_missing = []

    for i, scholar in enumerate(scholars):
        name = scholar["full_name"]
        print(f"[{i+1}/{len(scholars)}] {name} ({scholar['talks']} talks) — ", end="", flush=True)

        year, source = scrape_scholar(scholar)

        if year:
            print(f"FOUND {year} at {source[:60]}")
            found.append({**scholar, "birth_year": year, "source_url": source})
        else:
            print("NOT FOUND")
            still_missing.append(scholar)

        time.sleep(REQUEST_DELAY)

    # Write results
    OUT_FOUND.parent.mkdir(parents=True, exist_ok=True)

    if found:
        found_fields = ["person_id", "full_name", "talks", "best_affiliation", "birth_year", "source_url"]
        with open(OUT_FOUND, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=found_fields, extrasaction='ignore')
            w.writeheader()
            w.writerows(found)
        print(f"\n{'='*60}")
        print(f"FOUND: {len(found)} birth years -> {OUT_FOUND}")
        for s in found:
            print(f"  {s['full_name'][:45]:45s} {s['birth_year']}  {s['source_url'][:50]}")

    if still_missing:
        missing_fields = ["person_id", "full_name", "talks", "best_affiliation", "all_affiliations"]
        with open(OUT_MISSING, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=missing_fields, extrasaction='ignore')
            w.writeheader()
            w.writerows(still_missing)
        print(f"\nSTILL MISSING: {len(still_missing)} -> {OUT_MISSING}")
        print("\nSuggested manual search queries:")
        for s in still_missing[:10]:
            name = s['full_name']
            print(f"  '{name} год рождения'  |  '{name} диссертация'  |  '{name} индолог'")

    print(f"\nTo apply findings to the database, run:")
    print(f"  python tools/apply_birth_years.py")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    run(dry_run=dry_run, limit=limit)
