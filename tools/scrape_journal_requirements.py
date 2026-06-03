"""Scrape publication requirements from VAK journal websites.

For each journal in the VAK list, attempt to find:
  - Author guidelines URL (правила для авторов)
  - Citation style (ГОСТ, APA, Chicago, etc.)
  - Page/character limits
  - Accepted languages
  - Review time
  - Required document formats

Strategy:
  1. Search journal name on eLIBRARY / direct web search → find official site
  2. Try common URL patterns: /rules/, /authors/, /для-авторов/
  3. Parse the page for structured requirements using regex
  4. Fall back to manual review note for unfound

Usage:
  python tools/scrape_journal_requirements.py                          # all journals from indology CSV
  python tools/scrape_journal_requirements.py --limit 10               # first 10 only
  python tools/scrape_journal_requirements.py --input vak_journals_philology.csv

Output:
  analytics_output/journal_requirements.csv
"""

import csv
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "analytics_output" / "vak_journals_indology.csv"
OUTPUT_PATH = ROOT / "analytics_output" / "journal_requirements.csv"
CACHE_DIR = ROOT / "html_cache" / "journal_sites"

USER_AGENT = "IndologyScholars/1.0 (research bot; gasyoun@gmail.com)"
REQUEST_DELAY = 1.0

# Common URL patterns on Russian academic journal sites
AUTHOR_GUIDE_PATTERNS = [
    "/pravila-dlya-avtorov",
    "/pravila-dlja-avtorov",
    "/dlya-avtorov",
    "/dlja-avtorov",
    "/authors",
    "/author-guidelines",
    "/submissions",
    "/requirements",
    "/trebovaniya",
    "/trebovanija",
    "/guide",
    "/rules",
    "/for-authors",
    "/info/authors",
    "/about/submissions",
]

# Patterns to extract from author guideline pages
REQUIREMENT_PATTERNS = {
    "citation_style": [
        (r"(?:стиль\s+цитирования|оформление\s+ссылок|библиографи[яи]|references?\s+style)[:\s]*([^.]+)", "ru"),
        (r"(ГОСТ\s*Р?\s*[\d\.-]+)", "ru"),
        (r"(APA|MLA|Chicago|Harvard|Vancouver)", "en"),
        (r"(ISO\s*\d+)", "en"),
    ],
    "page_limit": [
        (r"(?:объ[её]м|размер)\s*(?:статьи|рукописи)?[:\s]*(\d+[–-]?\d*\s*(?:стр|с\.|знак|тыс|а\.л\.|pages?))", "ru"),
        (r"(\d+[–-]?\d*\s*(?:pages?|words?))", "en"),
        (r"не\s+более\s+(\d+[–-]?\d*\s*(?:стр|с\.|знак|тыс|а\.л\.))", "ru"),
    ],
    "languages": [
        (r"(?:язык|language)[:\s]*([^.]+)", "ru"),
        (r"(?:принима[ею]т|публику[ею]т)\s*(?:статьи|рукописи)?\s*(?:на\s*)?([^.]+)", "ru"),
    ],
    "review_time": [
        (r"(?:срок|время|период)\s*рецензирования[:\s]*([^.]+)", "ru"),
        (r"review\s*(?:time|period|process)[:\s]*([^.]+)", "en"),
        (r"(\d+[–-]?\d*\s*(?:дн[ея]й|месяц|недел|week|month|day))", "ru"),
    ],
    "format_requirements": [
        (r"(?:формат|format)\s*(?:файла|статьи|file)?[:\s]*([^.]+)", "ru"),
        (r"(DOCX?|PDF|RTF|ODT|LaTeX|TeX|MS\s*Word)", "en"),
    ],
}


def fetch_url(url: str, timeout: int = 12) -> tuple[str | None, str]:
    """Fetch a URL. Returns (text, effective_url)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            effective_url = resp.geturl()
            for enc in ["utf-8", "windows-1251", "cp1251", "koi8-r"]:
                try:
                    return raw.decode(enc), effective_url
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace"), effective_url
    except Exception:
        return None, url


def search_journal_site(journal_name: str, issn: str) -> str | None:
    """Try to find the journal's official website."""
    # Clean journal name for search
    clean_name = re.sub(r"\s*\(.*?\)", "", journal_name)  # remove parenthetical notes
    clean_name = re.sub(r"\s+", " ", clean_name).strip()

    # Strategy 1: search eLIBRARY
    search_url = f"https://elibrary.ru/title_about_new.asp?id={urllib.parse.quote(issn)}"
    text, _ = fetch_url(search_url)
    if text and "title_about" in text:
        # Try to extract website URL
        m = re.search(r'https?://[^\s"\'<>]+', text)
        if m:
            return m.group(0).rstrip(".,;")

    # Strategy 2: direct domain guess from journal name
    # Many Russian journals are at <name>.ru or <name>.com
    name_slug = re.sub(r"[^a-zа-яё0-9]+", "", clean_name.lower())[:30]
    for suffix in [".ru", ".com", ".org", ".рф"]:
        url = f"https://{name_slug}{suffix}"
        text, eff_url = fetch_url(url, timeout=5)
        if text and len(text) > 500:
            return eff_url

    return None


def extract_requirements(text: str) -> dict:
    """Extract structured requirements from an author guidelines page."""
    if not text:
        return {}

    # Clean HTML tags
    text_clean = re.sub(r"<[^>]+>", " ", text)
    text_clean = re.sub(r"\s+", " ", text_clean)

    results = {}
    for field, patterns in REQUIREMENT_PATTERNS.items():
        for pattern, lang in patterns:
            m = re.search(pattern, text_clean, re.IGNORECASE)
            if m:
                results[field] = m.group(1).strip().rstrip(".,;: ")
                break

    return results


def find_author_guidelines(base_url: str) -> tuple[str | None, dict]:
    """Try common URL patterns to find the author guidelines page."""
    base = base_url.rstrip("/")

    for pattern in AUTHOR_GUIDE_PATTERNS:
        url = base + pattern
        text, _ = fetch_url(url, timeout=8)
        if text and len(text) > 1000:
            requirements = extract_requirements(text)
            if requirements:
                return url, requirements

    # Try homepage
    text, _ = fetch_url(base_url, timeout=8)
    if text:
        # Search for link to author guidelines on homepage
        for phrase in ["правила для авторов", "для авторов", "author guidelines", "submissions"]:
            idx = text.lower().find(phrase)
            if idx >= 0:
                snippet = text[max(0, idx - 200):idx + 500]
                links = re.findall(r'href="([^"]+)"', snippet)
                if links:
                    guide_url = links[0]
                    if not guide_url.startswith("http"):
                        guide_url = base + "/" + guide_url.lstrip("/")
                    guide_text, _ = fetch_url(guide_url, timeout=8)
                    if guide_text:
                        reqs = extract_requirements(guide_text)
                        return guide_url, reqs

        # Check the homepage itself
        reqs = extract_requirements(text)
        return base_url, reqs

    return None, {}


def scrape(journals: list[dict], limit: int | None = None) -> list[dict]:
    """Scrape requirements for a list of journals."""
    results = []
    journals_iter = journals[:limit] if limit else journals

    for i, j in enumerate(journals_iter):
        name = j["title"]
        issn = j["issn"]
        print(f"[{i+1}/{len(journals_iter)}] {name[:60]}...", end="", flush=True)

        # Find journal website
        site_url = search_journal_site(name, issn)

        if site_url:
            guide_url, reqs = find_author_guidelines(site_url)
            status = "found" if reqs else "no_guidelines"
            print(f" {status}")
        else:
            guide_url = ""
            reqs = {}
            status = "no_site"
            print(f" {status}")

        results.append({
            "journal": name[:100],
            "issn": issn,
            "site_url": site_url or "",
            "guide_url": guide_url or "",
            "citation_style": reqs.get("citation_style", ""),
            "page_limit": reqs.get("page_limit", ""),
            "languages": reqs.get("languages", ""),
            "review_time": reqs.get("review_time", ""),
            "format_requirements": reqs.get("format_requirements", ""),
            "status": status,
        })

        time.sleep(REQUEST_DELAY)

    return results


def main():
    limit = None
    input_path = DEFAULT_INPUT
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.startswith("--input="):
            input_path = Path(arg.split("=")[1])

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        print("Run tools/vak_parser.py first to generate the journal list.")
        sys.exit(1)

    with open(input_path, encoding="utf-8-sig", newline="") as f:
        journals = list(csv.DictReader(f))

    print(f"Loaded {len(journals)} journals from {input_path}")
    if limit:
        journals = journals[:limit]
        print(f"Limited to {limit}")

    results = scrape(journals, limit)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["journal", "issn", "site_url", "guide_url", "citation_style",
              "page_limit", "languages", "review_time", "format_requirements", "status"]
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    found = sum(1 for r in results if r["status"] == "found")
    no_guide = sum(1 for r in results if r["status"] == "no_guidelines")
    no_site = sum(1 for r in results if r["status"] == "no_site")
    print(f"\nResults: {found} found, {no_guide} no guidelines, {no_site} no site -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
