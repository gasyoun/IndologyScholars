# Design: Merging the Russian-Indologist Roster into the Corpus

**Status:** implemented (2026-06-10) · **Decision source:** roadmap session
2026-06-10.

**Implementation map:**
- Phase 1 seeder → `tools/build_non_participant_registry.py` →
  `curation/non_participant_indologists.csv` (94 rows).
- Phase 2 linker → `tools/link_roster_participants.py` →
  `analytics_output/roster_participant_links.csv` (100 links) + Q-ID injection
  into `authority_ids.json` (candidate).
- Phase 3 page → `generate_registry_page()` in `generate_publication_pages.py`
  → `indologists.html` (top-level, in nav + sitemap + validator).
- Phase 4 tests → `tests/test_non_participant_registry.py` (10 tests).
- Phase 5 enrichment (.ru, by runbook) — still pending.

**Resolved open questions:** the page is the top-level `indologists.html`
(not `indologists/registry.html`) to reuse the `known-relationships.html`
precedent and avoid sub-directory relative-path machinery; `registry_id` is a
deterministic `RIND_<sha1(surname|given|birth)[:8]>`; imperial-period figures
share the one registry (life-years convey the era).

## Decisions this design implements

1. **Merge the `scratch/` roster (197 indologists) into the main corpus.**
   People who presented at Zograf/Roerich link to their existing scholar
   profile and enrich it (Wikidata Q-ID, birth/death years). People who never
   presented are published as a **separate registry**, clearly distinguished
   from conference speakers.
2. **Conference statistics must not change.** The headline numbers
   (270 scholars · 1362 unique presentations · 1388 author participations)
   describe the *conference corpus*. Registry (non-participant) indologists are
   a parallel dataset and never enter those counts.
3. **No fabrication.** A registry row is published only with a source; an
   unverified Wikidata tie stays internal (`confidence != public`).

## Source data

| Source | Shape | Role in merge |
| --- | --- | --- |
| `scratch/wikipedia_indologists_expanded.json` | `people` (114, wiki/en.wiki-bridge) + `new_from_institutions` (83, from conf DB). Fields: `full_name`, `surname`, `given_name`, `birth_year`, `death_year`, `scientific_field`, `role`, `workplace`, `alma_mater`, `degree`, `wikidata_qid`, `is_indologist`. | Raw roster |
| `scratch/non_participants.md` | Curated report: ~100 participants vs ~94 non-participants, with life-years/field/role/affiliation/degree. | Human-verified split |
| `site_data.json` / `conferences.db` | 270 conference scholars with stable `person_id`. | Match target |
| `authority_ids.json` | Per-person `openalex`/`orcid`/`wikidata` + `confidence`. | Enrichment sink |
| `person_ids.json` / `public_ids.json` | Stable-ID policy. | ID namespace |

## Architecture

The roster splits into two flows on one question: *did this person present at
Zograf or Roerich?*

```
roster JSON ──► matcher (tests/test_indologist_matching.py) ──► is participant?
                                                              │
                          ┌───────────────────────────────────┴────────────┐
                          ▼ yes                                             ▼ no
        link to existing person_id;                      curation/non_participant_indologists.csv
        enrich authority_ids.json + birth/death          (curated, source-of-truth)
        via data_assertion (no new person row)                       │
                                                                      ▼
                                                   generate_registry_page.py ──► indologists/registry.html
```

### Flow A — participants (enrich, never duplicate)

- Reuse the existing fuzzy matcher (already 60-test covered) to map each roster
  person to a `person_id`. Surname + given-name with initial/ё-insensitive
  verification; reject near-collisions ("Иванов Вячеслав ≠ Иванов Владимир").
- For a confident match, **do not create a person row**. Instead:
  - Birth/death years → existing birth-year assertion path
    (`tools/apply_birth_years.py` style `data_assertion`), so provenance is
    preserved and the conference DB stays authoritative for participation.
  - Wikidata Q-ID → `authority_ids.json` under the matched `person_id` with
    `confidence='candidate'` until a human promotes it (same rule as the
    OpenAlex injector).
- Output an audit CSV (`analytics_output/roster_participant_links.csv`:
  `roster_full_name, matched_person_id, match_method, score, qid`) for review.

### Flow B — non-participants (new registry, isolated from stats)

- **Source of truth:** a curated `curation/non_participant_indologists.csv`
  (not the raw JSON), one row per person:
  `registry_id, full_name_ru, full_name_en, birth_year, death_year, field,
  role, affiliation, alma_mater, degree, wikidata_qid, orcid, source_url,
  status, note`.
  - `status ∈ {verified, candidate}`; `verified` requires a non-empty
    `source_url` (mirrors the genealogy anti-fabrication rule).
  - Seeded from `non_participants.md` + the roster JSON, then human-curated.
- **Generator:** `generate_registry_page.py` reads the CSV → renders
  `indologists/registry.html` through the standard `page_shell()` /
  `templates/base.html` (per CLAUDE.md rule 5 — published pages come from the
  main pipeline, never from `scratch/`). Sortable table; life-years; field;
  affiliation; outbound links to Wikidata/Wikipedia when present.
- **Cross-linking:** a short banner on the registry page explains it lists
  indologists who have *not* appeared in the Zograf/Roerich programs, with a
  link back to the speaker catalogue, and vice-versa.

## Stable-ID namespace

Registry people are **not** conference persons, so they must not draw from the
conference `person_id` space. Allocate a distinct prefix (e.g. `RIND_<n>` or a
hash of `surname+given+birth_year`) recorded in the CSV `registry_id` column.
This keeps `compare_id_manifests.py` / `export_presentation_id_manifest.py`
clean and prevents a registry person from ever being mistaken for a speaker.

## Keeping conference stats stable

- `generate_site_data.py` and the summary/validator continue to count only
  conference-derived persons. The registry is a *separate* JSON
  (`site_data_registry.json` or similar) consumed only by the registry page.
- Add a test asserting `total_scholars == 270`-style invariants are unaffected
  by the registry build (regression guard against accidental stat leakage).

## Validation & tests

- Extend `tests/` with: registry CSV schema validation (`status=verified`
  ⇒ `source_url`), ID-namespace uniqueness, and a "registry does not change
  conference summary numbers" guard.
- `validate_publication.py` learns about `indologists/registry.html`
  (sitemap + canonical) like other generated pages.
- Run order unchanged: build DB → `generate_site_data.py` →
  `generate_registry_page.py` → `validate_publication.py` → `pytest`.

## Provenance & uncertainty rules (carried over)

- Roster Wikidata ties enter `authority_ids.json` as `candidate`; public
  JSON-LD `sameAs` only for `confirmed`/`manual`/`high` (data_dictionary §4).
- Unknown life-years stay blank with `?`, never guessed.
- Registry status `candidate` rows render with a visible "needs source" marker
  and are excluded from any "verified indologist" claim.

## Reachability constraint

Q-ID/birth-year enrichment for roster people depends on Wikidata/ru.wiki, which
are unreachable from the automation host. Per the .ru runbook decision, the
maintainer runs `wikidata_enrich.py` and the ru-infobox fetch inside .ru; the
matcher, CSV curation, page generation, and tests run anywhere.

## Phased plan

1. **Curate the split.** Promote `non_participants.md` + roster JSON into
   `curation/non_participant_indologists.csv` with `registry_id` + `status`.
2. **Participant linker.** Matcher → `roster_participant_links.csv`; inject
   Q-ID/years into `authority_ids.json` (candidate) for confirmed links.
3. **Registry generator + page** through the main pipeline; sitemap/validator
   wiring; regression test for stat isolation.
4. **Enrichment pass** (.ru, by runbook): fill Q-IDs and life-years, then
   regenerate.

## Resolved decisions

- Registry URL: **top-level `indologists.html`** (mirrors `known-relationships.html`).
- `registry_id`: **deterministic** `RIND_<sha1(surname|given|birth)[:8]>`.
- Imperial-period figures: **share the one registry**; life-years convey the era.

## Remaining for the maintainer

- Phase 5 enrichment (`wikidata_enrich.py`, ru-infobox fetch) is .ru-gated and
  runs by runbook; it will raise Q-ID/life-year coverage and flip more
  `candidate` rows to `verified`.
- The 70 `candidate` rows need a human-supplied `source_url` before they count
  as verified.
