"""Generate a Gemini Flash paste batch for enriching authority_ids.json.

Run whenever you want to seed Wikidata QIDs, ROR IDs, official URLs, and
English alternative names for the places and institutions that drive
schema.org/Place and schema.org/ResearchOrganization JSON-LD on the public
site (city pages, institution pages, `sameAs` linkages).

Workflow:
  1. python generate_seo_handoff.py
  2. Open the generated gemini_handoff/seo_authority_<date>.md
  3. Paste into gemini.google.com (subscription / free tier — no API key needed)
  4. Save Gemini's fenced ```jsonl reply to
       gemini_handoff/seo_authority_<date>.reply.jsonl
     (you can save the entire raw reply; the importer extracts the fenced block)
  5. python import_seo_handoff.py gemini_handoff/seo_authority_<date>.reply.jsonl

The importer is non-destructive: it only fills missing fields and skips
items whose `key` doesn't match anything currently in use.
"""

import datetime as dt
from collections import defaultdict
from pathlib import Path

from publication_helpers import load_authority_overrides, load_site_data
from generate_publication_pages import normalize_affiliation, timeline_records

HANDOFF_DIR = Path("gemini_handoff")
TODAY = dt.date.today().isoformat()


PROMPT_HEADER = """# SEO authority enrichment — Gemini Flash paste batch

Generated: {today}
Target file: `authority_ids.json` (sections: `places`, `organizations`)
Already-enriched items are SKIPPED in the lists below.

---

You are enriching authority records for a Russian Indology research archive
(Zograf Readings + Roerich Readings, since 2004). The enriched data feeds
schema.org/Place and schema.org/ResearchOrganization JSON-LD blocks on the
public site so search engines (Yandex, Google) can resolve scholar
affiliations to authoritative entities.

**For each item below, reply with ONE JSON object per line, inside a single
```jsonl fenced block. Reply NOTHING outside the fenced block.**

Rules:
1. Set unknown fields to `null`. **Do NOT guess.** A missing field is far
   better than a wrong Wikidata QID.
2. `wikidata` is a bare Q-number (e.g. `"Q649"`), no URL prefix.
3. `ror` is a bare ROR identifier (e.g. `"02nps9w79"`), no URL prefix.
4. `url` is the canonical homepage. Prefer https. No trailing slash unless
   the site requires one.
5. `alternateName` is a list of 0–3 widely-used variants. Do NOT repeat the
   `key`, `name_en`, or `full_name_ru` inside `alternateName`.
6. Keep `key` exactly as written in the lists below — it is the lookup
   identifier in `authority_ids.json`.

**Place schema:**
```
{{"item_type":"place","key":"<exact Cyrillic name>","name_en":"<English canonical>","alternateName":[...],"wikidata":"Q...","country":"<English country>","country_ru":"<Russian country>"}}
```

**Organization schema (Russian academic institutions):**
```
{{"item_type":"organization","key":"<exact short name>","full_name_ru":"<full Russian name>","name_en":"<English canonical name>","alternateName":[...],"url":"https://...","wikidata":"Q...","ror":"<ROR id>"}}
```

"""


def collect_places(data):
    """Return ordered list of (city_ru, city_en) seen in geography_stats."""
    seen = []
    for item in data.get("geography_stats") or []:
        ru = item.get("ru")
        if not ru or ru in {"Не указана", "Not specified"}:
            continue
        seen.append((ru, item.get("en") or ""))
    return seen


def collect_organizations(records):
    """Return ordered list of (normalized_name, presentation_count)."""
    counts = defaultdict(int)
    for record in records:
        name = normalize_affiliation(record.get("affiliation"))
        if name and name != "Независимые исследователи":
            counts[name] += 1
    return [(name, count) for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def build_markdown(places_to_ask, orgs_to_ask):
    lines = [PROMPT_HEADER.format(today=TODAY)]

    if places_to_ask:
        plural = "s" if len(places_to_ask) != 1 else ""
        lines.append(f"## Places to enrich ({len(places_to_ask)} item{plural})\n")
        for ru, en in places_to_ask:
            hint = f" — currently displayed in the archive as **{en}**" if en else ""
            lines.append(f"- `{ru}`{hint}")
        lines.append("")
    else:
        lines.append("## Places — all enriched, nothing to do.\n")

    if orgs_to_ask:
        plural = "s" if len(orgs_to_ask) != 1 else ""
        lines.append(f"## Organizations to enrich ({len(orgs_to_ask)} item{plural})\n")
        for name, count in orgs_to_ask:
            plural_rec = "s" if count != 1 else ""
            lines.append(f"- `{name}` — {count} presentation record{plural_rec} in archive")
        lines.append("")
    else:
        lines.append("## Organizations — all enriched, nothing to do.\n")

    lines.append("---")
    lines.append("Reply with a single fenced ```jsonl block, one JSON object per item.")
    lines.append("")
    return "\n".join(lines)


def main():
    HANDOFF_DIR.mkdir(exist_ok=True)
    data = load_site_data("site_data.json")
    records = timeline_records(data)
    authority = load_authority_overrides()

    place_keys_filled = set(authority.get("places") or {})
    org_keys_filled = set(authority.get("organizations") or {})

    all_places = collect_places(data)
    all_orgs = collect_organizations(records)

    places_to_ask = [(ru, en) for ru, en in all_places if ru not in place_keys_filled]
    orgs_to_ask = [(name, count) for name, count in all_orgs if name not in org_keys_filled]

    markdown = build_markdown(places_to_ask, orgs_to_ask)
    out_path = HANDOFF_DIR / f"seo_authority_{TODAY}.md"
    out_path.write_text(markdown, encoding="utf-8", newline="\n")

    print(f"Wrote handoff to {out_path}")
    print(f"  places  needing enrichment: {len(places_to_ask)} / {len(all_places)} total")
    print(f"  orgs    needing enrichment: {len(orgs_to_ask)} / {len(all_orgs)} total")
    print()
    if not places_to_ask and not orgs_to_ask:
        print("Nothing to ask Gemini about — authority_ids.json already covers everything in use.")
        return
    reply_path = HANDOFF_DIR / f"seo_authority_{TODAY}.reply.jsonl"
    print("Next steps:")
    print(f"  1. open  {out_path}")
    print("  2. paste the entire file into gemini.google.com")
    print(f"  3. save Gemini's reply (raw text is fine) to  {reply_path}")
    print(f"  4. run   python import_seo_handoff.py {reply_path}")


if __name__ == "__main__":
    main()
