"""Wikipedia bridge via en.wikipedia (RKN-resilient).

Why this exists
---------------
``ru.wikipedia.org/w/api.php`` is blocked from inside Russia (and is
unreachable from the maintainer's automation host as well). The doc-promised
``search_via_html()`` workaround never actually existed in
``expand_wikipedia_indologists.py`` — that script still calls the blocked
``action=query`` endpoints, so it cannot run today.

``en.wikipedia.org`` is *not* blocked, and every biography there exposes, in a
single cheap API call, both:

  * the Russian Wikipedia title via ``langlinks`` (lllang=ru) — in the exact
    ``"Surname, Given"`` form the rest of this pipeline keys on; and
  * the Wikidata Q-ID via ``pageprops`` (wikibase_item).

So en.wikipedia is used purely as an index that maps English biographies of
Russian indologists onto (ru-title, Q-ID) pairs. We then:

  * back-fill Q-IDs onto existing people who were scraped without one
    (the old QID regex almost never matched, so most records have qid="");
  * append genuinely new names (imperial-era / émigré indologists that the
    ru-language categories miss) as sparse candidates carrying a Q-ID, which
    ``wikidata_enrich.py`` can later flesh out where Wikidata is reachable.

The master file is updated **non-destructively** (atomic write, only additions
and qid back-fills) — re-running this can never wipe the hand-curated names the
way the documented "full cycle" does.

Output:
  * scratch/wikipedia_indologists_expanded.json  (master, updated in place)
  * scratch/enwiki_bridge_output.json            (raw bridge audit trail)

Usage:
  python scratch/enwiki_bridge.py            # Russian Indologists only
  python scratch/enwiki_bridge.py --wide     # + Soviet/Russian orientalists, India-filtered
  python scratch/enwiki_bridge.py --dry-run  # report only, write nothing
  python scratch/enwiki_bridge.py --no-cache # ignore the on-disk HTTP cache
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import scrape_common as sc

API = "https://en.wikipedia.org/w/api.php"
SCRATCH = Path(__file__).resolve().parent
MASTER = SCRATCH / "wikipedia_indologists_expanded.json"
BRIDGE_OUT = SCRATCH / "enwiki_bridge_output.json"

# en.wikipedia categories that collect Russian-sphere indologists.
# (Recon 2026-06: "Soviet indologists" / "Ukrainian Indologists" do NOT exist
#  on en.wikipedia; "Russian Indologists" is the live national bucket.)
EN_CATEGORIES = [
    "Category:Russian Indologists",
]

# --wide sweep: nationality-scoped Russian categories. "definitive" buckets are
# kept whole; the broad orientalist buckets are filtered to members that ALSO
# sit in an India-related category (see INDIA_CAT_TOKENS).
WIDE_SOURCES = [
    {"cat": "Category:Russian Indologists", "definitive": True},
    {"cat": "Category:Soviet orientalists", "definitive": False},
    {"cat": "Category:Russian orientalists", "definitive": False},
]

INDIA_CAT_TOKENS = (
    "indolog", "sanskrit", "dravid", "indo-aryan", "south asia", "hindi",
    "tamil", "bengali", "urdu", "vedic", "prakrit", "pali", "jain",
    "hindu studies", "scholars of hinduism", "history of india", "indian literature",
)


# ── en.wikipedia access ──────────────────────────────────────────────

def list_members(cat: str, *, use_cache: bool) -> list[dict]:
    """All ns=0 members of a category, following cmcontinue pagination."""
    members: list[dict] = []
    cont: str | None = None
    while True:
        params = {
            "action": "query", "list": "categorymembers", "cmtitle": cat,
            "cmlimit": "500", "cmnamespace": "0", "format": "json",
        }
        if cont:
            params["cmcontinue"] = cont
        data = sc.api_get(API, params, cache=use_cache, verbose=True)
        if not data:
            print(f"  [!] could not fetch members of {cat}")
            break
        members.extend(data.get("query", {}).get("categorymembers", []))
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
    return members


def fetch_ru_and_qid(pageids: list[int], *, use_cache: bool) -> dict[str, dict]:
    """Map en title → {'ru': ru-title, 'qid': Q-id} for the given page ids."""
    out: dict[str, dict] = {}
    for i in range(0, len(pageids), 50):
        chunk = pageids[i:i + 50]
        data = sc.api_get(API, {
            "action": "query", "pageids": "|".join(str(p) for p in chunk),
            "prop": "langlinks|pageprops", "lllang": "ru", "lllimit": "500",
            "ppprop": "wikibase_item", "format": "json",
        }, cache=use_cache, verbose=True)
        if not data:
            continue
        for p in data.get("query", {}).get("pages", {}).values():
            ru = next((l["*"] for l in p.get("langlinks", []) if l["lang"] == "ru"), "")
            qid = p.get("pageprops", {}).get("wikibase_item", "")
            out[p["title"]] = {"ru": ru, "qid": qid}
    return out


def fetch_page_categories(pageids: list[int], *, use_cache: bool) -> dict[str, set[str]]:
    """Map en title → set of its (lowercased) category titles."""
    out: dict[str, set[str]] = {}
    for i in range(0, len(pageids), 50):
        chunk = pageids[i:i + 50]
        cont: str | None = None
        while True:
            params = {
                "action": "query", "pageids": "|".join(str(p) for p in chunk),
                "prop": "categories", "cllimit": "500", "format": "json",
            }
            if cont:
                params["clcontinue"] = cont
            data = sc.api_get(API, params, cache=use_cache, verbose=True)
            if not data:
                break
            for p in data.get("query", {}).get("pages", {}).values():
                s = out.setdefault(p["title"], set())
                for c in p.get("categories", []):
                    s.add(c["title"].lower())
            cont = data.get("continue", {}).get("clcontinue")
            if not cont:
                break
    return out


def is_india_relevant(cats: set[str]) -> bool:
    """True if any en-category marks an India/Indology focus (used to keep
    indologists out of the broad Soviet/Russian orientalist buckets)."""
    return any(tok in c for c in cats for tok in INDIA_CAT_TOKENS)


def gather_members(*, wide: bool, use_cache: bool) -> list[dict]:
    """Collect the en biographies to resolve.

    Default: just ``Category:Russian Indologists``. With ``wide``: also the
    nationality-scoped orientalist buckets, but keep only members that ALSO sit
    in an India-related category (drops Arabists/Sinologists/etc.).
    """
    if not wide:
        members, seen = [], set()
        for cat in EN_CATEGORIES:
            ms = list_members(cat, use_cache=use_cache)
            print(f"  {cat}: {len(ms)} members")
            for m in ms:
                if m["pageid"] not in seen:
                    seen.add(m["pageid"])
                    members.append(m)
        return members

    definitive, candidates, seen = [], [], set()
    for src in WIDE_SOURCES:
        ms = list_members(src["cat"], use_cache=use_cache)
        print(f"  {src['cat']}: {len(ms)} members "
              f"({'all kept' if src['definitive'] else 'India-filtered'})")
        for m in ms:
            if m["pageid"] in seen:
                continue
            seen.add(m["pageid"])
            (definitive if src["definitive"] else candidates).append(m)

    kept = list(definitive)
    if candidates:
        cats = fetch_page_categories([m["pageid"] for m in candidates], use_cache=use_cache)
        for m in candidates:
            if is_india_relevant(cats.get(m["title"], set())):
                kept.append(m)
        print(f"  India-relevance filter: kept "
              f"{len(kept) - len(definitive)}/{len(candidates)} orientalist candidates")
    return kept


# ── name handling ────────────────────────────────────────────────────

def split_ru_title(ru_title: str) -> tuple[str, str, str]:
    """"Surname, Given Patronymic" → (surname, given, full_name)."""
    t = re.sub(r"\s+", " ", ru_title).strip()
    if "," in t:
        surname, given = t.split(",", 1)
        surname = surname.strip()
        given = re.sub(r"\s*\(.*?\)\s*", "", given).strip()
        return surname, given, f"{given} {surname}".strip()
    return t, "", t


def index_master(people: list[dict]) -> dict[str, int]:
    """normalized ru-title / full-name → index into people."""
    idx: dict[str, int] = {}
    for i, p in enumerate(people):
        for key in (p.get("wikipedia_title", ""), p.get("full_name", "")):
            k = sc.normalize_name(key)
            if k:
                idx.setdefault(k, i)
    return idx


# ── merge ────────────────────────────────────────────────────────────

def main() -> None:
    sc.setup_utf8()
    dry_run = "--dry-run" in sys.argv
    use_cache = "--no-cache" not in sys.argv
    wide = "--wide" in sys.argv

    print("=== en.wikipedia → ru-title + Q-ID bridge ===")
    print(f"(mode: {'WIDE — Russian Indologists + orientalist buckets' if wide else 'Russian Indologists only'})")
    if dry_run:
        print("(dry run: no files will be written)\n")

    # 1. enumerate categories
    members = gather_members(wide=wide, use_cache=use_cache)
    print(f"Unique en biographies: {len(members)}")

    if not members:
        print("\n[!] No members fetched — en.wikipedia unreachable? Aborting "
              "without touching the master file.")
        return

    # 2. resolve ru-title + Q-ID
    links = fetch_ru_and_qid([m["pageid"] for m in members], use_cache=use_cache)

    candidates = []
    for m in members:
        info = links.get(m["title"], {})
        candidates.append({
            "en_title": m["title"],
            "ru_title": info.get("ru", ""),
            "qid": info.get("qid", ""),
        })
    with_ru = [c for c in candidates if c["ru_title"]]
    en_only = [c for c in candidates if not c["ru_title"]]
    print(f"  with ru-langlink: {len(with_ru)}   en-only (no ru page): {len(en_only)}")

    # 3. merge into master (non-destructive)
    if not MASTER.exists():
        print(f"\n[!] {MASTER} not found — cannot merge.")
        return
    with open(MASTER, "r", encoding="utf-8") as f:
        master = json.load(f)
    people = master.get("people", [])
    idx = index_master(people)

    backfilled, matched, new_people = [], [], []
    for c in with_ru:
        surname, given, full = split_ru_title(c["ru_title"])
        key_title = sc.normalize_name(c["ru_title"])
        key_full = sc.normalize_name(full)
        hit = idx.get(key_title, idx.get(key_full))
        if hit is not None:
            matched.append(c["ru_title"])
            if c["qid"] and not people[hit].get("wikidata_qid"):
                people[hit]["wikidata_qid"] = c["qid"]
                backfilled.append((c["ru_title"], c["qid"]))
        else:
            new_people.append({
                "wikipedia_title": c["ru_title"],
                "surname": surname,
                "given_name": given,
                "full_name": full,
                "birth_year": None,
                "death_year": None,
                "scientific_field": "",
                "role": "индолог",
                "workplace": "",
                "alma_mater": "",
                "degree": "",
                "wikidata_qid": c["qid"],
                "is_indologist": True,
                "source": "enwiki",
                "en_title": c["en_title"],
            })

    # 4. report
    print(f"\n--- merge report ---")
    print(f"  matched existing people : {len(matched)}")
    print(f"  Q-IDs back-filled       : {len(backfilled)}")
    for ru, qid in backfilled:
        print(f"      + {qid}  {ru}")
    print(f"  NEW names (not in master): {len(new_people)}")
    for np in new_people:
        print(f"      + {np['full_name']}  [{np['wikidata_qid'] or 'no qid'}]")
    if en_only:
        print(f"  en-only (no ru page, not merged): {len(en_only)}")
        for c in en_only:
            print(f"      · {c['en_title']}  [{c['qid'] or 'no qid'}]")

    if dry_run:
        print("\n(dry run) master left unchanged.")
        return

    # 5. write
    people.extend(new_people)
    master["people"] = people
    master["total_people"] = len(people)
    master["description"] = (
        "Expanded list of Russian Indologists from Wikipedia "
        "(ru categories + full-text search + en.wikipedia bridge)"
    )
    sc.atomic_write_json(MASTER, master)
    sc.atomic_write_json(BRIDGE_OUT, {
        "description": "Raw en.wikipedia bridge output (en_title → ru_title, qid)",
        "source_categories": [s["cat"] for s in WIDE_SOURCES] if wide else EN_CATEGORIES,
        "total": len(candidates),
        "candidates": sorted(candidates, key=lambda c: c["en_title"]),
    })
    print(f"\nWrote {len(new_people)} new + {len(backfilled)} qid back-fills "
          f"to {MASTER.name}")
    print(f"Audit trail: {BRIDGE_OUT.name}")


if __name__ == "__main__":
    main()
