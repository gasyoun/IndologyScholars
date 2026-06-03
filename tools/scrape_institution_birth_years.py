"""Targeted scraper: find birth years from specific institutional staff pages.

For each scholar missing birth_year, try their known institution's staff directory.

Currently supported institutions:
  - hse.ru (НИУ ВШЭ) — staff search + profile pages
  - orient.spbu.ru (СПбГУ Востфак) — staff pages
  - ivran.ru (ИВ РАН) — person directory
  - orientalstudies.ru (ИВР РАН) — search

Usage:
  python tools/scrape_institution_birth_years.py           # all institutions
  python tools/scrape_institution_birth_years.py --dry-run  # show plan only
"""

import csv
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
OUT_FOUND = ROOT / "curation" / "birth_year_findings.csv"

USER_AGENT = "Mozilla/5.0 (compatible; IndologyScholars/1.0; gasyoun@gmail.com)"
DELAY = 1.0


def fetch(url: str, timeout: int = 12) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            for enc in ["utf-8", "windows-1251", "cp1251"]:
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_year(text: str) -> int | None:
    patterns = [
        r'<span[^>]*class="[^"]*bday[^"]*"[^>]*>(\d{4})',
        r'(?:родил[ася]+|род\.)\s*(?:в\s*)?(\d{4})',
        r'Дата\s+рождения.*?(\d{4})',
        r'Год\s+рождения.*?(\d{4})',
        r'\((\d{4})\s*[-–—]\s*\d{0,4}\)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 1920 <= year <= 2005:
                return year
    return None


# ── HSE (НИУ ВШЭ) ──────────────────────────────────────────────────

def scrape_hse(name: str) -> tuple[int | None, str]:
    """Search HSE staff directory and extract birth year from profile page."""
    # HSE staff search
    search_url = f"https://www.hse.ru/search/search.html?text={urllib.parse.quote(name)}&site=persons"
    html = fetch(search_url)
    if not html:
        return None, ""

    # Find person profile links
    links = re.findall(r'href="(/org/persons/\d+)"', html)
    for link in links[:3]:
        profile_url = f"https://www.hse.ru{link}"
        profile_html = fetch(profile_url)
        if not profile_html:
            continue
        # Verify name match
        if name.split()[-1].lower() not in profile_html.lower():
            continue
        year = extract_year(profile_html)
        if year:
            return year, profile_url

    return None, ""


# ── MSU IAAS (ИСАА МГУ) ────────────────────────────────────────────

def scrape_msu_iaas(name: str) -> tuple[int | None, str]:
    """Search MSU IAAS staff directory."""
    # IAAS staff page
    search_url = "https://iaas.msu.ru/about/staff/"
    html = fetch(search_url)
    if not html:
        return None, ""

    # Look for the name on the staff page
    surname = name.split()[-1].lower()
    links = re.findall(r'href="(/about/staff/[^"]+)"', html)
    for link in links[:10]:
        full_url = f"https://iaas.msu.ru{link}" if link.startswith("/") else link
        staff_html = fetch(full_url)
        if not staff_html:
            continue
        if surname not in staff_html.lower():
            continue
        year = extract_year(staff_html)
        if year:
            return year, full_url

    # Try individual staff search
    search_url = f"https://iaas.msu.ru/search/?q={urllib.parse.quote(name)}"
    html = fetch(search_url)
    if html:
        links = re.findall(r'href="(/[^"]+)"', html)
        for link in links[:5]:
            if "staff" not in link:
                continue
            full_url = f"https://iaas.msu.ru{link}"
            staff_html = fetch(full_url)
            if staff_html:
                year = extract_year(staff_html)
                if year:
                    return year, full_url

    return None, ""


# ── SPbU Oriental Faculty (Востфак СПбГУ) ──────────────────────────

def scrape_spbu_oriental(name: str) -> tuple[int | None, str]:
    """Search SPbU Oriental Faculty staff pages."""
    # Try direct search
    search_url = f"https://orient.spbu.ru/index.php/ru/component/search/?searchword={urllib.parse.quote(name)}&searchphrase=all"
    html = fetch(search_url)
    if not html:
        return None, ""
    links = re.findall(r'href="(/index\.php[^"]+)"', html)
    for link in links[:5]:
        full_url = f"https://orient.spbu.ru{link}"
        page = fetch(full_url)
        if page:
            year = extract_year(page)
            if year:
                return year, full_url
    return None, ""


# ── Main ────────────────────────────────────────────────────────────

def get_todo_list() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT p.person_id, COALESCE(p.full_name_ru, p.display_name, p.person_id) as name,
        p.person_id, COUNT(DISTINCT pp.presentation_id) as talks
    FROM person p JOIN presentation_person pp ON p.person_id=pp.person_id
    WHERE pp.role='speaker' AND (p.birth_year IS NULL OR p.birth_year=0)
    GROUP BY p.person_id ORDER BY talks DESC""")
    rows = c.fetchall()
    inst_p = ['РАН','университет','институт','музей','СПбГУ','МГУ','ВШЭ','РГГУ','РУДН','College','University','центр','школа']
    todo = []
    for pid, name, pid2, talks in rows:
        c.execute("""SELECT DISTINCT affiliation_text_raw FROM presentation_person
            WHERE person_id=? AND affiliation_text_raw NOT IN ('','Не указана')""", (pid,))
        affs = [r[0] for r in c.fetchall()]
        real = [a for a in affs if any(p in a for p in inst_p)]
        all_aff = ' | '.join(affs)
        todo.append({"person_id": pid, "full_name": name, "talks": talks, "affiliations": all_aff})
    conn.close()
    return todo


def guess_scraper(affiliations: str) -> str:
    aff = affiliations.lower()
    if "вшэ" in aff or "hse" in aff:
        return "hse"
    if "мгу" in aff or "iaas" in aff or "исаа" in aff:
        return "msu_iaas"
    if "спбгу" in aff or "spbu" in aff or "востфак" in aff:
        return "spbu_oriental"
    if "ивр" in aff or "orientalstudies" in aff:
        return "ivr"
    if "ив ран" in aff:
        return "ivran"
    if "санкт-петербург" in aff or "спб" in aff:
        return "spbu_oriental"  # try SPbU for SPb residents
    if "москва" in aff:
        return "hse"  # try HSE for Moscow residents
    return ""


def run(dry_run: bool = False):
    scholars = get_todo_list()
    print(f"Missing birth years: {len(scholars)}")
    if dry_run:
        for s in scholars:
            scraper = guess_scraper(s["affiliations"])
            if scraper:
                print(f"  {s['full_name'][:40]:40s} -> {scraper}")
        return

    found = []
    for s in scholars:
        name = s["full_name"]
        scraper_key = guess_scraper(s["affiliations"])
        if not scraper_key:
            continue

        print(f"  {name[:40]:40s} [{scraper_key}] ", end="", flush=True)
        year, url = None, ""

        if scraper_key == "hse":
            year, url = scrape_hse(name)
        elif scraper_key == "msu_iaas":
            year, url = scrape_msu_iaas(name)
        elif scraper_key == "spbu_oriental":
            year, url = scrape_spbu_oriental(name)

        if year:
            print(f"-> {year}  {url[:50]}")
            found.append({"person_id": s["person_id"], "full_name": name,
                         "talks": s["talks"], "best_affiliation": s["affiliations"],
                         "birth_year": year, "source_url": url})
        else:
            print("NOT FOUND")
        time.sleep(DELAY)

    if found:
        fields = ["person_id", "full_name", "talks", "best_affiliation", "birth_year", "source_url"]
        OUT_FOUND.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_FOUND, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(found)
        print(f"\nFound: {len(found)} -> {OUT_FOUND}")
        for s in found:
            print(f"  {s['full_name']} {s['birth_year']}  {s['source_url'][:60]}")
    else:
        print("\nNo new birth years found.")


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
