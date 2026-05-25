# SciGuide Integration — Gemini Flash Implementation Plan

Generated: 2026-05-21  
Target repository: `C:\Users\user\Documents\GitHub\IndologyScholars`  
Primary roadmap: `../plans/sciguide.md`

Use this file as a Gemini Flash handoff. The task is to turn the SciGuide-inspired roadmap into a conservative first implementation sprint for `IndologyScholars`.

---

## Role

You are Gemini Flash acting as a careful implementation planner for a static digital humanities archive. You should propose a concrete, low-risk implementation sequence and, if asked to write code later, make changes only through the project generators rather than hand-editing generated HTML.

The project is a generated static site and dataset about Russian Indological conference participation:

- 226 scholars.
- 899 presentation-person records.
- 895 presentation rows in SQLite.
- 40 events from Zograf Readings and Roerich Readings.
- Main local files:
  - `conferences.db`
  - `site_data.json`
  - `authority_ids.json`
  - `generate_publication_pages.py`
  - `generate_scholars_pages.py`
  - `generate_site_data.py`
  - `generate_analytics.py`
  - `validate_publication.py`
  - `analytics_output/data_quality_report.json`
  - `../plans/sciguide.md`

---

## Non-Negotiable Constraints

1. Do not copy or paraphrase long passages from SciGuide. Use original wording and cite SciGuide links only as references.
2. Do not add bibliometric rankings of people. This archive measures participation in a conference corpus, not scholarly quality.
3. Do not use OpenAlex to estimate birth years. This method has already been tested and rejected in `../session/HANDOFF.md`.
4. Do not automate scraping of eLIBRARY/RINC. Treat RINC as a manual review workflow or official data-source workflow only.
5. Do not hand-edit generated pages such as `methodology.html`, `data-sources.html`, `known-limitations.html`, `how-to-cite.html`, `download-data.html`, `themes/*.html`, `cities/*.html`, or `institutions/*.html` unless explicitly asked. Update `generate_publication_pages.py` and regenerate.
6. Do not break existing JSON-LD, sitemap, search index, or validation.
7. External identifiers must be treated as assertions with provenance: source, confidence, and checked date.
8. Keep the first sprint small enough to review in one PR.

---

## Current Architecture Notes

1. `generate_publication_pages.py` generates:
   - `download-data.html`
   - `data-quality.html`
   - `methodology.html`
   - `data-sources.html`
   - `known-limitations.html`
   - `how-to-cite.html`
   - `sitemap.xml`
   - `datapackage.json`
   - search index and collection pages.
2. `generate_publication_pages.py:generate_publication_docs()` currently contains short static bodies for methodology, sources, limitations, and citation pages.
3. `generate_scholars_pages.py:profile_structured_data()` already adds `sameAs` from `authority_ids.json` for `orcid`, `wikidata`, `viaf`, and `url`.
4. `authority_ids.json` already supports persons, organizations, and places, but person records are mostly `preferred_latin_name` only.
5. `generate_publication_pages.py:organization_structured_data()` and city/institution page generators already consume organization/place authority data.
6. Existing `data-quality.html` is generated from `analytics_output/data_quality_report.json`.
7. `README_RU.md` can have encoding display issues in PowerShell unless read with UTF-8 output; be careful.

---

## First Sprint Objective

Implement the minimal SciGuide-inspired layer that improves methodological clarity and authority readiness without doing risky automatic enrichment.

The first sprint should deliver:

1. clearer generated documentation pages;
2. an explicit guide to interpreting local metrics;
3. an authority coverage report;
4. external-link rendering for confirmed person identifiers;
5. validation steps that prove the site still builds.

---

## Recommended File Changes

### 1. Update `generate_publication_pages.py`

Implement the documentation layer in the generator.

#### 1.1 Expand `generate_publication_docs()`

Replace the current short bodies with richer but concise original text:

- `methodology.html`
  - Add "Data, metadata, derived fields".
  - Explain:
    - primary source program pages;
    - extracted presentation records;
    - normalized persons;
    - normalized affiliations;
    - broad theme labels;
    - derived analytics.
  - State that presentation themes do not equal a person's complete research profile.

- `data-sources.html`
  - Add source cards:
    - Zograf Readings program materials;
    - Roerich Readings program materials;
    - curated seed data in `zograf-roerich-db.md`;
    - authority overrides in `authority_ids.json`;
    - optional external references: ORCID, Wikidata, ROR, VIAF, OpenAlex, RINC/eLIBRARY.
  - Clearly distinguish primary corpus sources from external enrichment sources.

- `known-limitations.html`
  - Add limitations:
    - initials and name ambiguity;
    - transliteration variants;
    - historical affiliations;
    - broad theme classification;
    - OpenAlex coverage gaps for Soviet/Russian humanities;
    - RINC/eLIBRARY manual-review constraint;
    - unstable `presentation_id` risk if still true.

- `how-to-cite.html`
  - Keep citation guidance, but add a short note:
    - cite the dataset/site for conference corpus analysis;
    - cite original conference programs for claims about original event wording;
    - include access date for web pages.

#### 1.2 Add `metrics-guide.html`

Add a new generated documentation page:

- title: `How To Read The Metrics`
- purpose: explain local participation metrics.
- include cards for:
  - `total_talks`;
  - `series overlap`;
  - `newcomer rate`;
  - `institution bridge`;
  - `theme diversity`;
  - `online/video coverage`, if relevant.
- state explicitly: these are participation and corpus-coverage metrics, not quality rankings.

Update:

- navigation in `page_shell()` if needed;
- `generate_sitemap()` to include `metrics-guide.html`;
- `en.html` landing cards if there is a suitable place;
- any static publication links on the homepage only if generated by script. If homepage links are manually embedded in `index.html`, leave them for a separate patch unless necessary.

#### 1.3 Add authority coverage outputs

Add a small function, for example:

```python
def generate_authority_coverage(data, authority):
    ...
```

Write:

- `analytics_output/authority_coverage.csv`
- `analytics_output/authority_review_queue.csv`

Recommended fields for `authority_coverage.csv`:

- `person_id`
- `display_name`
- `full_name_ru`
- `preferred_latin_name`
- `total_talks`
- `has_orcid`
- `has_wikidata`
- `has_viaf`
- `has_openalex`
- `has_rinc`
- `has_google_scholar`
- `has_official_url`
- `has_any_external_id`
- `authority_confidence`
- `checked_at`

Recommended fields for `authority_review_queue.csv`:

- `priority_rank`
- `person_id`
- `display_name`
- `full_name_ru`
- `total_talks`
- `reason`
- `suggested_query`
- `review_status`

Queue ranking:

1. persons with many talks and no external ID;
2. persons with initials-only display names;
3. persons with no preferred Latin name;
4. persons with existing ID but missing confidence/checked_at.

Do not query external APIs in this first sprint. Generate only local coverage and review queues.

#### 1.4 Extend `data-quality.html`

Add a card or section that links to:

- `analytics_output/authority_coverage.csv`
- `analytics_output/authority_review_queue.csv`

If adding detailed authority checks to `data_quality_report.json` is too large for the first sprint, just add the links and summary counts from the CSV generation function.

---

### 2. Update `generate_scholars_pages.py`

#### 2.1 Broaden `sameAs`

Currently `sameAs` uses `orcid`, `wikidata`, `viaf`, and `url`. Extend accepted person authority keys to include:

- `openalex`
- `google_scholar`
- `official_url`
- `scopus_author_id` converted to a stable Scopus author URL only if the format is confidently known;
- `researcher_id` converted to a profile URL only if confidently known;
- `rinc_author_id` only if there is a stable public URL pattern and the value is confirmed.

Conservative rule: if a field is not already a URL and the public URL pattern is uncertain, do not emit it in `sameAs`.

#### 2.2 Render external links on profile pages

Add a compact "External identifiers" card or row if a person has confirmed authority links.

Suggested labels:

- ORCID
- Wikidata
- VIAF
- OpenAlex
- Google Scholar
- Official profile
- RINC/eLIBRARY, only if confirmed URL exists

Only show links that are present. Do not show empty placeholders.

#### 2.3 Confidence behavior

If a person authority record has `confidence` and it is not one of `confirmed`, `manual`, or `high`, avoid showing it as a public link. It may still appear in internal coverage CSV.

---

### 3. Update `authority_ids.json` cautiously

Do not mass-edit all person records.

Optional first-sprint change:

- update top-level `description` to document supported person fields;
- do not invent identifiers;
- preserve existing entries.

If adding `confidence`, `source`, or `checked_at` to existing `preferred_latin_name`-only records would create noisy churn, do not do it in the first sprint.

---

### 4. Do Not Implement Yet

Keep these for later phases:

1. OpenAlex API candidate lookup.
2. RINC manual review instruction page.
3. Deterministic `presentation_id` migration.
4. Network graph pages.
5. Full JSON Schema for `authority_ids.json`.
6. Citation metrics or h-index fields.
7. Any automated external enrichment that changes public profile pages without manual confirmation.

---

## Suggested Implementation Order

1. Read `../plans/sciguide.md`.
2. Inspect:
   - `generate_publication_pages.py`
   - `generate_scholars_pages.py`
   - `authority_ids.json`
   - `site_data.json` summary structure
3. Patch `generate_publication_pages.py`:
   - expanded docs;
   - add `metrics-guide.html`;
   - add sitemap entry;
   - add authority coverage CSV generation;
   - link authority outputs from `data-quality.html`.
4. Patch `generate_scholars_pages.py`:
   - broaden `sameAs`;
   - add profile external-links block.
5. Run:

```bash
python generate_publication_pages.py
python generate_scholars_pages.py
python validate_publication.py
```

If the project convention requires a full rebuild, run:

```bash
python build_and_populate_db.py
python generate_analytics.py
python generate_site_data.py
python generate_scholars_pages.py
python generate_publication_pages.py
python validate_publication.py
```

6. Inspect generated files:
   - `methodology.html`
   - `data-sources.html`
   - `known-limitations.html`
   - `metrics-guide.html`
   - `data-quality.html`
   - `analytics_output/authority_coverage.csv`
   - `analytics_output/authority_review_queue.csv`
   - one or two `scholars/*.html` pages with authority links.
7. Report:
   - changed source files;
   - generated files;
   - validation results;
   - follow-up tasks left out of scope.

---

## Acceptance Criteria

The implementation is acceptable if:

1. `metrics-guide.html` is generated and present in `sitemap.xml`.
2. `methodology.html`, `data-sources.html`, and `known-limitations.html` explain the SciGuide-inspired methodology in original wording.
3. `authority_coverage.csv` and `authority_review_queue.csv` are generated from local data only.
4. Person profile JSON-LD still validates structurally and emits only URL-like `sameAs` entries.
5. No RINC scraping or OpenAlex birth-year logic is added.
6. `validate_publication.py` passes.
7. Existing homepage/dashboard behavior is not changed except for safe navigation links if implemented.

---

## Expected Gemini Flash Output

If you are only asked to plan, return:

1. a short implementation summary;
2. exact files to edit;
3. function-level change list;
4. test commands;
5. risks and mitigations;
6. what to defer.

If you are asked to implement in a code-capable environment, make a small patch following this plan and report changed files plus validation output.

Do not produce a broad rewrite. Keep the first sprint practical, reviewable, and boring in the best possible way.
