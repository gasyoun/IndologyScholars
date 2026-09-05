_Created: 15-08-2026 · Last updated: 05-09-2026_

# Runbook: Phase-5 enrichment (run inside Russia)

Phase 5 of [roster-merge-design.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/roster-merge-design.md). The CI/automation
host can only reach `en.wikipedia.org`; the data sources that fill Q-IDs, life
years, and institutional affiliations are reachable only from a host **inside
Russia**. This runbook is the procedure the maintainer runs there; everything
else (matching, CSV curation, page generation, tests) runs anywhere.

Goal: raise Q-ID and life-year coverage on the roster, discover institution-only
indologists, and flip `candidate` registry rows to `verified`.

## Reachability (from the automation host vs inside .ru)

| Endpoint | Automation host | Inside .ru | Used by |
| --- | --- | --- | --- |
| `en.wikipedia.org` API | ✅ | ✅ | `enwiki_bridge.py` (already run) |
| `ru.wikipedia.org` `api.php` | ❌ RKN | ❌ RKN | — (avoid) |
| `ru.wikipedia.org/wiki/` articles | ❌ | ✅ | `expand_wikipedia_indologists.py` |
| Wikidata `Special:EntityData/*.json` (REST) | ❌ | ✅ | `wikidata_enrich.py` |
| Wikidata SPARQL / `wbgetentities` | ❌ | flaky | — (avoid; use REST) |
| `ivran.ru` / `orientalstudies.ru` | ❌ | ✅ | `scrape_institutions_web.py` |
| `api.openalex.org` | ✅ | ✅ | `resume_openalex.py` (optional) |

Safety properties relied on throughout: every enrichment script **fills empty
fields only** (curated values are never overwritten) and writes **atomically**
(`scrape_common.atomic_write_json`), so an RKN-induced mid-run SSL drop cannot
corrupt the master roster. Unreachable items are skipped and reported, not
guessed.

## Prerequisites

```
git pull origin main                 # start from the pushed state
python -m pip install -r requirements.txt
# optional, only for institutional JS-rendered pages:
python -m pip install playwright
python -m playwright install chromium
```

Do not commit `.env`, API keys, or `html_cache/` dumps (already git-ignored).

## Step 1 — Wikidata life years (highest value, lowest effort)

Turns each roster Q-ID into birth/death years via the stable REST endpoint.
Without this, dated scholars (e.g. Бётлингк, d. 1904) are mis-filed as living.

```
python scratch/wikidata_enrich.py --dry-run     # report what would be filled
python scratch/wikidata_enrich.py               # fill empty birth/death years
```

Writes in place to `scratch/wikipedia_indologists_expanded.json`. Re-runnable;
already-filled and curated values are untouched.

## Step 2 — ru.wikipedia infobox fields and new names

```
python scratch/expand_wikipedia_indologists.py
```

Non-destructive merge into the same master file: pulls Russian-language infobox
fields (field, role, workplace, alma mater, degree) and any new category members
reachable via the article-search workaround. On a blocked network it adds
nothing and never shrinks the file.

## Step 3 — institutional staff directories (optional)

Finds indologists *employed* at a centre who never presented at the readings.

```
python scratch/scrape_institutions_web.py --self-test    # verify browser machinery
python scratch/scrape_institutions_web.py                # writes scratch/institutional_web_indologists.json
```

Then **review** the JSON and fold genuinely new indologists into the roster's
`new_from_institutions` list in `scratch/wikipedia_indologists_expanded.json`
(this merge is a manual curation step — the scraper output is a candidate list,
not auto-trusted). Re-run Step 1 afterward to date any new Q-IDs.

## Step 4 — OpenAlex candidate refresh (optional)

```
python scratch/resume_openalex.py                 # append new candidates to the CSV
# review analytics_output/openalex_author_candidates.csv (mark rows confirmed)
python tools/inject_openalex_matches.py            # inject >=0.8 as confidence='candidate'
```

## Step 5 — rebuild the merge artifacts

After any of Steps 1–4 changed the roster or authority data:

```
python scratch/crossref_nonparticipants.py            # refresh scratch/non_participants.md
python tools/build_non_participant_registry.py        # append newly-discovered non-participants (idempotent)
python tools/link_roster_participants.py              # refresh links + inject new Q-IDs (candidate)
```

The seeder is idempotent: it dedupes by `registry_id` **and** by normalized
name, so a newly-filled birth year (which changes the id hash) does not append a
duplicate. It only **appends** new people — it does not rewrite existing rows.

### Curate the registry (the human step)

`curation/non_participant_indologists.csv` is the source of truth. For rows that
enrichment can now support, fill `source_url` and set `status=verified`:

- a row with a `wikidata_qid` already carries a `source_url`
  (`https://www.wikidata.org/wiki/<QID>`) and is seeded as `verified`;
- a `candidate` row becomes `verified` only when you add a real `source_url`.

Never set `status=verified` without a non-empty `source_url` — the test suite
enforces this.

## Step 6 — regenerate the site, validate, test

```
python generate_publication_pages.py     # rebuilds indologists.html + sitemap
python validate_publication.py           # must print "Publication validation passed."
python -m pytest -q                      # must be green
```

(Only run `python build_and_populate_db.py` first if *conference* data changed;
pure roster/registry enrichment does not need a DB rebuild.)

## Step 7 — commit and push (source only)

Commit the curated/source inputs; leave generated HTML and the sitemap for CI's
auto-rebuild (the established split).

```
git add scratch/wikipedia_indologists_expanded.json scratch/non_participants.md \
        curation/non_participant_indologists.csv \
        analytics_output/roster_participant_links.csv \
        analytics_output/openalex_author_candidates.csv \
        authority_ids.json
git commit -m "data: phase-5 roster enrichment (life years, infoboxes, institutions)"
git pull --rebase origin main            # CI may have auto-rebuilt; replay on top
git push origin main
```

Do **not** `git add -A`: the build leaves ~1,500 CRLF-churn HTML files that CI
owns. Stage explicit paths only.

## Acceptance checks

- `validate_publication.py` passes and `pytest` is green.
- The registry's verified count rose: compare the footnote on `indologists.html`
  (or `awk -F, 'NR>1 && $14=="verified"' curation/non_participant_indologists.csv | wc -l`)
  against the previous run.
- No duplicate names appeared in the registry (the `test_no_duplicate_names_in_registry`
  guard catches this; re-run pytest if you hand-edited the CSV).
- Spot-check that no `verified` row lacks a `source_url`.

_Dr. Mārcis Gasūns_
