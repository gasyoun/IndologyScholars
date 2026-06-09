# Wikidata Batch Creation Guide for IndologyScholars

## Goal

Map the 270 scholars in the IndologyScholars archive to Wikidata Q-IDs.
Once mapped, every scholar becomes discoverable via:
- Wikidata Query Service (SPARQL)
- Google Knowledge Graph
- Scholia profiles
- Wikipedia infoboxes
- VIAF (harvested from Wikidata automatically)

## Current State

| Metric | Value |
|--------|-------|
| Total scholars | 270 |
| With Wikidata Q-ID | 1 (0.4%) |
| With ORCID | 1 (0.4%) |
| With VIAF | 0 |
| With OpenAlex | 0 |
| OpenAlex candidates found | 122 scholars with at least one API result (review pending) |

## Step 1: OpenAlex → Wikidata pipeline

OpenAlex author entities cross-reference Wikidata. For each confirmed
OpenAlex match, extract the Wikidata ID from the OpenAlex response.

1. Run: `python scratch/openalex_author_candidates.py`
   (Output: `analytics_output/openalex_author_candidates.csv`)
2. For each row with `relevance_score >= 0.6`:
   - Open the OpenAlex URL: `https://api.openalex.org/authors/<id>`
   - Check `ids.wikidata` field — if present, the Wikidata Q-ID is known
   - If `ids.orcid` is present, note it for `authority_ids.json`
3. Add confirmed matches to `authority_ids.json`:
   ```json
   "PERS_XXXX": {
     "openalex": "A1234567890",
     "orcid": "0000-0001-2345-6789",
     "wikidata": "Q123456",
     "confidence": "confirmed",
     "checked_at": "2026-06-03"
   }
   ```

## Step 2: Create missing Wikidata items (top 50 scholars)

For scholars without a Wikidata item, create one via QuickStatements v2.

### Minimum required properties per scholar

| Property | ID | Value |
|----------|----|-------|
| Label (ru) | — | Full name in Russian |
| Label (en) | — | Latin transliteration |
| instance of | P31 | Q5 (human) |
| occupation | P106 | Q8088479 (Indologist) |
| field of work | P101 | Q8088479 (Indology) |
| date of birth | P569 | From `site_data.json` birth_year |
| employer | P108 | From `site_data.json` all_affiliations |
| country of citizenship | P27 | Q159 (Russia) |

### QuickStatements v2 batch format

Go to https://quickstatements.toolforge.org/

Example batch for one scholar (tab-separated):
```
CREATE
LAST	Len	"Васильков Ярослав Владимирович"
LAST	Lru	"Васильков Ярослав Владимирович"
LAST	Len	"Yaroslav V. Vasilkov"
LAST	P31	Q5
LAST	P106	Q8088479
LAST	P101	Q8088479
LAST	P569	+1943-00-00T00:00:00Z/9
LAST	P108	Q4201571
LAST	P27	Q159
LAST	S887	Q126692818
```

### Source attribution

Use `stated in (P248) = IndologyScholars (Q126692818)` or
`reference URL (P854) = https://gasyoun.github.io/IndologyScholars/s/<slug>.html`

This ensures the provenance points back to the archive.

## Step 3: After Wikidata items exist

1. **VIAF** — VIAF harvests from Wikidata automatically (takes ~2 weeks)
2. **OpenAlex** — OpenAlex cross-references Wikidata; re-run the candidates script
3. **RDF dump** — The `indology_knowledge_graph.ttl` should include `owl:sameAs` links to Wikidata Q-IDs
4. **Scholia** — Scholia (https://scholia.toolforge.org/) will automatically generate researcher profiles

## Priority Queue (top 20 by talks)

These scholars should get Wikidata items first — they appear in the most
international literature and benefit most from identifier disambiguation:

1. Scan `site_data.json` for scholars with `total_talks >= 10`
2. Check `authority_ids.json` — if no `wikidata` field, create item
3. Use `full_name_ru`, `birth_year`, and `all_affiliations` from `site_data.json`

## Automation (optional)

`tools/scrape_birth_years.py` already queries Wikipedia for birth years.
A companion tool can:
1. Read `site_data.json` for scholars without Wikidata
2. Generate QuickStatements batch for bulk import
3. Use Pywikibot to create items programmatically

## Verification

After creating Wikidata items:
```bash
# Check coverage
python -c "
import json
with open('authority_ids.json') as f: a = json.load(f)
persons = a.get('persons', {})
wd = sum(1 for v in persons.values() if v.get('wikidata'))
print(f'Wikidata coverage: {wd} / {len(persons)} ({100*wd/len(persons):.1f}%)')
"
```
