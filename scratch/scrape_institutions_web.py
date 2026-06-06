"""Institutional website scraper for Russian indology centres.

Reaches the staff directories that the conference-DB proxy in
``scrape_institutions.py`` cannot see — i.e. indologists *employed* at an
institution who have never appeared at the Roerich/Zograf readings.

Three cooperating strategies, cheapest first:

  1. Static staff index — ivran.ru's ``/sotrudniki`` already lists every
     employee's name + person-page URL in plain HTML (no JS). Free, stdlib.
  2. Drupal JSON:API — ivran.ru runs Drupal; ``/jsonapi`` self-describes its
     resources, so person nodes (position, department, bio) come back as clean
     JSON with NO browser. Tried before any headless rendering.
  3. Headless render (Playwright) — fallback for person detail injected by
     JavaScript (the ``/persons/*`` template ships an empty ``#content`` div).

ENVIRONMENT
-----------
ivran.ru / orientalstudies.ru are unreachable from outside Russia and from the
maintainer's CI host, so run this on a machine inside .ru. Playwright is an
OPTIONAL dependency, lazily imported — the static-HTML and JSON:API paths work
without it:

    pip install playwright
    playwright install chromium

Self-test the browser machinery (uses a reachable page, not an institution):

    python scratch/scrape_institutions_web.py --self-test

Run the scrape (writes scratch/institutional_web_indologists.json):

    python scratch/scrape_institutions_web.py
    python scratch/scrape_institutions_web.py --institution "ИВ РАН" --no-cache
"""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

import scrape_common as sc

SCRATCH = Path(__file__).resolve().parent
ROOT = SCRATCH.parent
MASTER = SCRATCH / "wikipedia_indologists_expanded.json"
OUTPUT = SCRATCH / "institutional_web_indologists.json"

# Specialisation markers that mark an employee as in scope. Matched against the
# combined position/department/bio text (case-folded).
INDOLOGY_KEYWORDS = (
    "индолог", "индия", "индии", "санскрит", "хинди", "тамил", "бенгал",
    "дравид", "южной азии", "южная азия", "ведийск", "буддолог", "тибетолог",
    "урду", "пали", "пракрит",
)


# ── institution configs ──────────────────────────────────────────────
# `staff_url`     : plain-HTML index listing person links
# `person_prefix` : href fragment that identifies a person page
# `jsonapi`       : Drupal JSON:API base (None disables that path)
# `render`        : True if person detail needs a headless browser
INSTITUTIONS = [
    {
        "key": "ИВ РАН",
        "name": "Институт востоковедения РАН",
        "base": "https://www.ivran.ru",
        "staff_url": "https://www.ivran.ru/sotrudniki",
        "person_prefix": "/persons/",
        "jsonapi": "https://www.ivran.ru/jsonapi",
        "render": True,
    },
    # orientalstudies.ru (ИВР РАН) serves staff bios as server-rendered HTML;
    # set render=False once its staff index path is confirmed on-site.
    {
        "key": "ИВР РАН",
        "name": "Институт восточных рукописей РАН",
        "base": "https://www.orientalstudies.ru",
        "staff_url": "https://www.orientalstudies.ru/rus/index.php?option=com_personalities",
        "person_prefix": "index.php?option=com_personalities&Itemid=",
        "jsonapi": None,
        "render": False,
    },
]


# ── static HTML staff index ──────────────────────────────────────────

def extract_staff_links(html: str, person_prefix: str, base: str) -> list[dict]:
    """Parse a staff index page → [{name, url}] for every person link.

    Pure HTML, no JS: ivran.ru/sotrudniki lists each employee as
    ``<a href="/persons/EugeniaVanina">Ванина Е.Ю.</a>``.
    """
    out, seen = [], set()
    pat = re.compile(
        r'<a\b[^>]*\bhref="([^"]*' + re.escape(person_prefix) + r'[^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    for href, label in pat.findall(html):
        name = unescape(re.sub(r"<[^>]+>", " ", label)).replace("\xa0", " ")
        name = re.sub(r"\s+", " ", name).strip()
        if not name or len(name) < 3:
            continue
        url = href if href.startswith("http") else base.rstrip("/") + "/" + href.lstrip("/")
        if url in seen:
            continue
        seen.add(url)
        out.append({"name": name, "url": url})
    return out


def extract_person_detail(html: str) -> str:
    """Collapse a person page to its visible text for keyword scanning."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("\xa0", " ")
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_indologist(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in INDOLOGY_KEYWORDS)


# ── Drupal JSON:API (no browser) ─────────────────────────────────────

def discover_jsonapi_people(base_jsonapi: str, *, use_cache: bool) -> list[dict]:
    """Self-discover a person-like resource from a Drupal /jsonapi index.

    The index document lists every resource under ``links``; we pick the first
    whose key looks person-ish and page through it. Returns raw JSON:API
    resource objects (caller maps fields). Empty list if not a JSON:API site.
    """
    index = sc.get_json(base_jsonapi, cache=use_cache, verbose=True)
    if not index or "links" not in index:
        return []
    person_link = None
    for key, link in index["links"].items():
        if re.search(r"person|people|sotrudnik|staff|employee|node--person", key, re.I):
            person_link = link.get("href") if isinstance(link, dict) else link
            break
    if not person_link:
        return []
    people, url = [], person_link
    for _ in range(50):  # hard page cap
        doc = sc.get_json(url, cache=use_cache, verbose=True)
        if not doc:
            break
        people.extend(doc.get("data", []))
        url = doc.get("links", {}).get("next", {})
        url = url.get("href") if isinstance(url, dict) else url
        if not url:
            break
    return people


# ── Playwright (lazy, optional) ──────────────────────────────────────

def render_with_playwright(url: str, *, wait_selector: str | None = None,
                           timeout_ms: int = 15000) -> str | None:
    """Return fully rendered HTML, or None if Playwright is unavailable/fails."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("    [playwright not installed — skipping JS render. "
              "`pip install playwright && playwright install chromium`]")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=sc.USER_AGENT)
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    pass
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"    [playwright render failed: {e}]")
        return None


# ── master novelty check ─────────────────────────────────────────────

def load_master_name_keys() -> tuple[set[str], set[str]]:
    """Return (full-name keys, 'surname initial' keys) from the master file.

    The surname/initial key uses the master's EXPLICIT ``surname``/``given_name``
    fields (don't guess which token is the surname — master names are ordered
    "Given Patronymic Surname", staff lists "Surname I.O.").
    """
    full: set[str] = set()
    surn: set[str] = set()
    if not MASTER.exists():
        return full, surn
    with open(MASTER, "r", encoding="utf-8") as f:
        data = json.load(f)
    for bucket in ("people", "new_from_institutions"):
        for p in data.get(bucket, []):
            for field in ("full_name", "wikipedia_title"):
                k = sc.normalize_name(p.get(field, ""))
                if k:
                    full.add(k)
            s = sc.normalize_name(p.get("surname", ""))
            g = sc.normalize_name(p.get("given_name", ""))
            if s:
                surn.add(f"{s} {g[:1]}".strip())
    return full, surn


def staff_surname_initial_key(name: str) -> str:
    """'Ванина Е.Ю.' → 'ванина е' (staff lists put the surname first)."""
    parts = [p for p in re.split(r"[\s.]+", sc.normalize_name(name)) if p]
    if not parts:
        return ""
    surname = parts[0]
    initial = parts[1][0] if len(parts) > 1 else ""
    return f"{surname} {initial}".strip()


# ── orchestration ────────────────────────────────────────────────────

def scrape_institution(cfg: dict, *, use_cache: bool) -> list[dict]:
    print(f"\n=== {cfg['key']} — {cfg['name']} ===")
    found: dict[str, dict] = {}

    # 1. JSON:API (cheapest structured path)
    if cfg.get("jsonapi"):
        nodes = discover_jsonapi_people(cfg["jsonapi"], use_cache=use_cache)
        print(f"  JSON:API person nodes: {len(nodes)}")
        for n in nodes:
            attr = n.get("attributes", {}) if isinstance(n, dict) else {}
            name = attr.get("title") or attr.get("name") or ""
            blob = " ".join(str(v) for v in attr.values())
            if name and is_indologist(blob):
                found[sc.normalize_name(name)] = {
                    "name": name, "institution": cfg["key"],
                    "method": "jsonapi", "url": cfg["base"]}

    # 2. static staff index → person links
    staff_html = sc.http_get(cfg["staff_url"], cache=use_cache, verbose=True)
    if not staff_html:
        print("  [!] staff index unreachable (run inside .ru?).")
        return list(found.values())
    links = extract_staff_links(staff_html.decode("utf-8", "replace"),
                                cfg["person_prefix"], cfg["base"])
    print(f"  staff links in HTML index: {len(links)}")

    # 3. per-person detail (static, then JS-render fallback) → keyword filter
    for i, person in enumerate(links, 1):
        if sc.normalize_name(person["name"]) in found:
            continue
        body = sc.http_get(person["url"], cache=use_cache)
        html = body.decode("utf-8", "replace") if body else ""
        detail = extract_person_detail(html)
        if (not detail or not is_indologist(detail)) and cfg.get("render"):
            rendered = render_with_playwright(person["url"], wait_selector="#content")
            if rendered:
                detail = extract_person_detail(rendered)
        if is_indologist(detail):
            found[sc.normalize_name(person["name"])] = {
                "name": person["name"], "institution": cfg["key"],
                "method": "html/render", "url": person["url"]}
        if i % 25 == 0:
            print(f"    …checked {i}/{len(links)}")

    print(f"  indologists at {cfg['key']}: {len(found)}")
    return list(found.values())


def main() -> None:
    sc.setup_utf8()
    args = sys.argv[1:]

    if "--self-test" in args:
        print("Playwright self-test against a reachable page …")
        html = render_with_playwright("https://en.wikipedia.org/wiki/Indology",
                                      wait_selector="#firstHeading")
        if html and "Indology" in html:
            print(f"  OK — rendered {len(html)} bytes, headline found. "
                  "Browser machinery works.")
        else:
            print("  Playwright did not return rendered content "
                  "(not installed, or the page was unreachable).")
        return

    use_cache = "--no-cache" not in args
    only = None
    if "--institution" in args:
        only = args[args.index("--institution") + 1]

    master_full, master_surn = load_master_name_keys()

    all_found = []
    for cfg in INSTITUTIONS:
        if only and cfg["key"] != only:
            continue
        all_found.extend(scrape_institution(cfg, use_cache=use_cache))

    # novelty: which institutional indologists are NOT already in the master?
    for p in all_found:
        k = sc.normalize_name(p["name"])
        p["in_master"] = k in master_full or staff_surname_initial_key(p["name"]) in master_surn
    new_people = [p for p in all_found if not p["in_master"]]

    sc.atomic_write_json(OUTPUT, {
        "description": "Indologists found on institutional staff sites",
        "total": len(all_found),
        "new_not_in_master": len(new_people),
        "people": sorted(all_found, key=lambda p: (p["institution"], p["name"])),
    })
    print(f"\n=== summary ===")
    print(f"  total indologists found : {len(all_found)}")
    print(f"  NEW (not in master)     : {len(new_people)}")
    for p in new_people:
        print(f"      + {p['name']}  @ {p['institution']}  [{p['method']}]")
    print(f"  written to {OUTPUT.name}")


if __name__ == "__main__":
    main()
