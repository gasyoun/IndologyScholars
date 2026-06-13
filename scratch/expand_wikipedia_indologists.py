"""Scraper: expand list of Russian Indologists from ru.wikipedia.

Fetches members of Категория:Индологи России + Санскритологи России and, for
each biography, extracts structured infobox data.
Output: scratch/wikipedia_indologists_expanded.json

ENVIRONMENT NOTE (read before running)
--------------------------------------
``ru.wikipedia.org/w/api.php`` is RKN-blocked from inside Russia and is
unreachable from the maintainer's automation host. From a blocked network this
script's API calls return nothing. Two consequences shaped this file:

  * ``search_via_html()`` now really exists (older docs claimed it did): it hits
    the *article* search page ``/w/index.php?search=`` instead of the blocked
    ``api.php``, which stays reachable when only the API endpoint is blocked.
  * ``main()`` is **non-destructive**: it MERGES into the existing master file
    and never shrinks it. Re-running on a blocked network can no longer wipe the
    hand-curated names (the old version overwrote the file with the empty live
    result — see scratch/handoff.md for the cautionary note).

For an RKN-resilient discovery path that needs no ru.wikipedia access at all,
use ``enwiki_bridge.py`` (en.wikipedia → ru-title + Q-ID). This script remains
the way to pull the *Russian-language* infobox fields, and is best run on a
machine where ru.wikipedia article pages load.
"""

import json
import re
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

import scrape_common as sc

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
OUTPUT = SCRATCH / "wikipedia_indologists_expanded.json"
API = "https://ru.wikipedia.org/w/api.php"
ARTICLE_BASE = "https://ru.wikipedia.org/w/index.php"   # search workaround
ARTICLE_WIKI = "https://ru.wikipedia.org/wiki/"         # article HTML (RKN-OK)
SKIP_PREFIXES = ("Проект:", "Категория:", "Шаблон:", "Обсуждение:", "Википедия:")


def api_request(params: dict, timeout: int = 20) -> dict:
    """Robust API GET (retry/backoff/cache). Returns {} when unreachable."""
    return sc.api_get(API, params, timeout=timeout, verbose=True) or {}


class _TextExtractor(HTMLParser):
    """Strip markup with the stdlib HTML parser instead of regexes.

    Regex-based tag stripping is fragile (it misses upper-case ``<SCRIPT>``
    tags, comments spanning newlines, malformed end tags, etc. — see CodeQL
    ``py/bad-tag-filter``). The parser handles those cases correctly. To keep
    :func:`clean_html`'s downstream normalisation unchanged, every tag becomes
    a single space (a word separator, as the old ``<[^>]+>`` substitution did),
    ``<script>``/``<style>`` bodies are dropped, comments are dropped, and
    entity references are re-emitted verbatim so the existing entity-collapsing
    regexes still apply.
    """

    _SKIP = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        else:
            self._parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if tag not in self._SKIP:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            if self._skip_depth:
                self._skip_depth -= 1
        self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(f"&#{name};")

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_markup(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.get_text()


def clean_html(value: str) -> str:
    value = _strip_markup(value)
    value = re.sub(r"\.mw-parser-output[^{]*\{[^}]*\}", " ", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"&[a-z]+;", " ", value)
    value = re.sub(r"&#?\d+;", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_infobox(text: str) -> dict:
    info = {}
    if not text:
        return info

    ib = re.search(
        r'<table[^>]*class="[^"]*infobox[^"]*"[^>]*>(.*?)</table>',
        text, re.DOTALL | re.IGNORECASE,
    )
    if not ib:
        return info

    rows = re.findall(r"<tr>(.*?)</tr>", ib.group(1), re.DOTALL)
    for row in rows:
        lm = re.search(r"<th[^>]*>(.*?)</th>", row, re.DOTALL)
        vm = re.search(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if lm and vm:
            label = clean_html(lm.group(1)).strip().rstrip(":")
            val = clean_html(vm.group(1)).strip()
            if label and val and len(label) < 80:
                info[label] = val
    return info


def fetch_article_html(title: str) -> str:
    """Fetch the rendered ARTICLE page (not api.php).

    Under RKN only ``/w/api.php`` is blocked — the article URL still loads — so
    this is how infobox fields are obtained on a machine inside Russia. The
    existing ``extract_infobox()`` parses this full-page HTML just as well as
    the action=parse fragment. (Untested from the CI host: ru.wikipedia is
    unreachable here; verify on a .ru machine.)
    """
    url = ARTICLE_WIKI + urllib.parse.quote(title.replace(" ", "_"))
    body = sc.http_get(url, verbose=True)
    return body.decode("utf-8", "replace") if body else ""


def parse_page(title: str) -> dict | None:
    """Extract infobox data for a person page.

    Tries ``action=parse`` first; if the API is blocked (empty result), falls
    back to fetching the article HTML directly, which stays reachable when only
    api.php is blocked.
    """
    result = api_request({
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
    }, timeout=15)

    html = result.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        html = fetch_article_html(title)
    if not html:
        return None

    info = extract_infobox(html)

    # Build person record
    surname = ""
    given = ""
    full_name = ""
    birth = None
    death = None

    title_clean = clean_html(title)
    if "," in title_clean:
        parts = title_clean.split(",", 1)
        surname = parts[0].strip()
        given = re.sub(r"\s*\(.*?\)\s*", "", parts[1]).strip()
        full_name = f"{given} {surname}"
    else:
        full_name = title_clean

    # Extract birth/death years from date fields
    for key in info:
        key_lower = key.lower()
        if "рождени" in key_lower:
            m = re.search(r"(\d{4})", str(info[key]))
            if m:
                birth = int(m.group(1))
        if "смерт" in key_lower:
            m = re.search(r"(\d{4})", str(info[key]))
            if m:
                death = int(m.group(1))

    # Gather core fields (case-insensitive)
    def field(*names):
        for n in names:
            if n in info:
                return info[n]
            for k, v in info.items():
                if k.lower() == n.lower():
                    return v
        return ""

    sphere = field("научная сфера", "Научная сфера")
    role = field("род деятельности", "Род деятельности")
    workplace = field("место работы", "Место работы")
    alma_mater = field("альма-матер", "Альма-матер")
    degree = field("учёная степень", "Учёная степень")

    # Wikidata Q-ID
    q_match = re.search(r'wikibase-itemid["\s]*[:=]["\s]*["\']?(Q\d+)', html)
    wikidata = q_match.group(1) if q_match else ""
    # Alt: from URL patterns
    if not wikidata:
        q_match2 = re.search(r'href="[^"]*\?curid=\d+[^"]*"[^>]*>.*?Q-?ID', html)
        q_match3 = re.search(r'"(?:https?:)?//www\.wikidata\.org/(?:wiki|entity)/(Q\d+)"', html)
        if q_match3:
            wikidata = q_match3.group(1)

    # Check if indologist from categories
    is_indologist = "индолог" in sphere.lower() or "индолог" in role.lower()

    return {
        "wikipedia_title": title,
        "surname": surname,
        "given_name": given,
        "full_name": full_name,
        "birth_year": birth,
        "death_year": death,
        "scientific_field": sphere,
        "role": role,
        "workplace": workplace,
        "alma_mater": alma_mater,
        "degree": degree,
        "wikidata_qid": wikidata,
        "is_indologist": is_indologist,
    }


def search_via_html(query: str = "индолог", limit: int = 500) -> list[str]:
    """API-block workaround: parse the *article* search page, not api.php.

    ``/w/index.php?search=`` stays reachable when only the ``/w/api.php``
    endpoint is RKN-blocked, because the block targets the API specifically.
    Returns ns0 article titles from the search-result headings. This is the
    function older docs/changelogs referenced but that was never actually
    present — it exists now.
    """
    url = ARTICLE_BASE + "?" + urllib.parse.urlencode({
        "search": query, "limit": str(limit), "ns0": "1", "fulltext": "1",
    })
    body = sc.http_get(url, verbose=True)
    if not body:
        print("  [!] HTML search page unreachable (ru.wikipedia fully blocked?).")
        return []
    html = body.decode("utf-8", "replace")
    titles, seen = [], set()
    # <div class="mw-search-result-heading"><a href="/wiki/..." title="Title">
    for m in re.finditer(r'mw-search-result-heading[^>]*>\s*<a[^>]*\btitle="([^"]+)"', html):
        title = m.group(1).strip()
        if not title or title in seen:
            continue
        if any(title.startswith(p) for p in SKIP_PREFIXES):
            continue
        seen.add(title)
        titles.append(title)
    print(f"  HTML search: {len(titles)} candidate pages")
    return titles


def search_for_indologists() -> list[str]:
    """Full-text search for indologist pages, then filter by categories.

    Finds pages that contain 'индолог' in text but may not be listed
    in the parent category (newly created, not yet categorized, etc.).
    Falls back to the HTML search page when the API endpoint is blocked.
    """
    print("  Searching Wikipedia for 'индолог' ...")
    search_result = api_request({
        "action": "query",
        "list": "search",
        "srsearch": "индолог",
        "srnamespace": "0",
        "srlimit": "500",
        "format": "json",
    })
    hits = search_result.get("query", {}).get("search", [])
    if not hits:
        print("  API search returned nothing — falling back to HTML search ...")
        return search_via_html()

    # Batch query: get categories for all found pages
    page_ids = [str(h["pageid"]) for h in hits]
    print(f"  Found {len(page_ids)} search hits, checking categories ...")

    # Split into chunks of 50 (API limit)
    indologist_titles = []
    for chunk_start in range(0, len(page_ids), 50):
        chunk = page_ids[chunk_start : chunk_start + 50]
        cat_result = api_request({
            "action": "query",
            "pageids": "|".join(chunk),
            "prop": "categories",
            "cllimit": "500",
            "format": "json",
        })
        pages = cat_result.get("query", {}).get("pages", {})
        for _pid, page in pages.items():
            cats = [c["title"] for c in page.get("categories", [])]
            # Keep only Russian/SSSR indologist categories
            has_indolog = any(
                "индолог" in c.lower()
                and ("росси" in c.lower() or "ссср" in c.lower() or "советск" in c.lower())
                for c in cats
            )
            if has_indolog:
                title = page.get("title", "")
                if title and not any(title.startswith(p) for p in SKIP_PREFIXES):
                    indologist_titles.append(title)

    print(f"  Verified indologists: {len(indologist_titles)}")
    return indologist_titles


def merge_into_master(parsed: list[dict]) -> tuple[dict, int, int]:
    """Merge freshly parsed records into the existing master, NEVER shrinking.

    New people are appended; existing people only get their *empty* fields
    filled (curated values are never clobbered). A blocked run yields an empty
    ``parsed`` and therefore changes nothing — the old destructive overwrite is
    gone. Returns (master, added, enriched_people).
    """
    if OUTPUT.exists():
        with open(OUTPUT, "r", encoding="utf-8") as f:
            master = json.load(f)
    else:
        master = {"people": []}
    people = master.get("people", [])

    index: dict[str, int] = {}
    for i, p in enumerate(people):
        for key in (p.get("wikipedia_title", ""), p.get("full_name", "")):
            k = sc.normalize_name(key)
            if k:
                index.setdefault(k, i)

    added = enriched = 0
    for rec in parsed:
        keys = [sc.normalize_name(rec.get("wikipedia_title", "")),
                sc.normalize_name(rec.get("full_name", ""))]
        hit = next((index[k] for k in keys if k in index), None)
        if hit is None:
            people.append(rec)
            for k in keys:
                if k:
                    index.setdefault(k, len(people) - 1)
            added += 1
        else:
            tgt = people[hit]
            touched = False
            for field, val in rec.items():
                if val in (None, "", []):
                    continue
                if tgt.get(field) in (None, "", []):
                    tgt[field] = val
                    touched = True
            enriched += touched

    master["people"] = people
    master["total_people"] = len(people)
    master["description"] = (
        "Expanded list of Russian Indologists from Wikipedia "
        "(ru categories + full-text search + en.wikipedia bridge)"
    )
    return master, added, enriched


def main():
    sc.setup_utf8()
    print("=== Expanding Wikipedia Indologist list ===")

    # Collect all unique person titles from both categories
    seen = set()
    titles = []

    for cat in ["Категория:Индологи_России", "Категория:Санскритологи_России"]:
        print(f"Fetching: {cat}")
        members = api_request({
            "action": "query",
            "list": "categorymembers",
            "cmtitle": cat,
            "cmlimit": "500",
            "format": "json",
        }).get("query", {}).get("categorymembers", [])

        for m in members:
            if m["ns"] != 0:
                continue
            title = m["title"]
            if any(title.startswith(p) for p in SKIP_PREFIXES):
                continue
            full_lower = title.lower()
            if "категория" in full_lower or "шаблон" in full_lower:
                continue
            if title not in seen:
                seen.add(title)
                titles.append(title)

    print(f"Category members: {len(titles)}")

    # Also search for indologists not in category lists
    search_titles = search_for_indologists()
    for t in search_titles:
        if t not in seen:
            seen.add(t)
            titles.append(t)

    print(f"Unique person pages (categories + search): {len(titles)}")

    # Parse each page
    parsed = []
    for i, title in enumerate(titles):
        print(f"  [{i+1:3d}/{len(titles)}] {title}")
        result = parse_page(title)
        if result:
            parsed.append(result)
        time.sleep(0.15)

    # Merge non-destructively into the master (never shrink, atomic write)
    master, added, enriched = merge_into_master(parsed)
    if added or enriched:
        sc.atomic_write_json(OUTPUT, master)
        print(f"\nMerged: +{added} new, {enriched} enriched. "
              f"Master now has {master['total_people']} people → {OUTPUT}")
    elif parsed:
        print(f"\nNothing to merge — all {len(parsed)} parsed records already "
              f"present and complete. Master unchanged.")
    else:
        print(f"\n[!] Fetched 0 records (ru.wikipedia API and HTML both "
              f"unreachable). Master left UNCHANGED at "
              f"{len(master.get('people', []))} people. Use enwiki_bridge.py "
              f"for an RKN-resilient discovery path.")

    # Quick summary
    alive = [p for p in parsed if p["death_year"] is None and p["birth_year"] is not None]
    deceased = [p for p in parsed if p["death_year"] is not None]
    no_dates = [p for p in parsed if p["birth_year"] is None and p["death_year"] is None]
    indologists = [p for p in parsed if p["is_indologist"]]
    print(f"  Alive: {len(alive)}, Deceased: {len(deceased)}, No dates: {len(no_dates)}")
    print(f"  Indologists by field/role: {len(indologists)}")
    print(f"  With ИСАА alma mater: {sum(1 for p in parsed if 'ИСАА' in p.get('alma_mater', ''))}")
    print(f"  With ИВ РАН workplace: {sum(1 for p in parsed if 'востоковедения' in p.get('workplace', '').lower())}")
    print(f"  Linguists (лингвист): {sum(1 for p in parsed if 'лингвист' in p.get('role', '').lower())}")


if __name__ == "__main__":
    main()
