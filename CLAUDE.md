# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**IndologyScholars** is a comprehensive digital humanities platform and ETL pipeline integrating two decades of Russian Indological conference programs (Zograf Readings in St. Petersburg and Roerich Readings in Moscow). The system extracts, deduplicates, and analyzes 220 scholars across 899 presentations, compiling a normalized SQLite database, generating scientific analytics, and deploying an interactive bilingual web portal with 220 static scholar profile pages and real-time data visualization.

---

## System Architecture

The system follows a **strict five-phase separation of concerns**:

### Phase 1: HTML Cache (`html_cache/`)
Raw HTML program snapshots cached locally from institutional portals (IOM RAS, IAS RAS). Guarantees hermetic builds immune to server restructuring.

### Phase 2: Data Ingestion (`build_and_populate_db.py`)
Primary assembly engine:
- **Schema Compilation:** 12 normalized SQLite tables enforcing referential integrity (3NF)
- **Seed Ingestion:** Parses metadata from `zograf-roerich-db.md` (venues, coordinates, event calendars)
- **HTML Parsing:** Extracts sessions, speaker names, affiliations, titles from cached HTML
- **Identity Matching:** Advanced regex deduplication engine mapping name variations (e.g., "В.В. Вертоградова" → "Victoria Vertogradova" → "Vertogradova V.") into unique person records with lifespan tracking

**Database Schema:** 12 tables (event_series, place, organization, venue, event, event_day, event_day_venue, session, presentation, person, presentation_person, media) with full referential integrity.

### Phase 3: Analytics (`generate_analytics.py`)
Computes cross-conference affinity indices, cohort overlapping, and generates CSV datasets to `analytics_output/`. Identifies the 38-scholar overlap cohort presenting at both conferences.

### Phase 4: Static Profile Generation (`generate_scholars_pages.py`)
Generates 220 individual SEO-optimized glassmorphic HTML cards under `scholars/` (e.g., `scholars/PERS_f074f69f.html`). Each profiles career chronology, institutional transitions, regional mobility, and thematic coverage.

### Phase 5: Web Portal (`index.html` + `site_data.json`)
Single-page application (vanilla CSS/JS):
- **Bilingual Core:** Defaults to Russian; toggle swaps entire UI state (metrics, charts, labels) to English in real-time
- **Cross-filtering:** Click any affiliation or city tag to instant-filter the 220-scholar directory with pagination
- **Interactive Charts:** Five SVG analytics visualizations (demographics, gender, career timeline, institutional distribution, semantic word cloud)

---

## Core Commands & Development Workflow

### Full Pipeline Rebuild (Local)
Execute in sequence to rebuild the entire platform from scratch:

```bash
python build_and_populate_db.py        # Compile schema, ingest HTML, deduplicate persons
python generate_analytics.py           # Compute statistics, export CSVs to analytics_output/
python generate_site_data.py           # Serialize SQL entries into JS payload
python generate_scholars_pages.py      # Generate 220 static profile pages
python -m http.server 8000             # Launch local server at http://localhost:8000
```

### Incremental Development

**Rebuild database only:**
```bash
python build_and_populate_db.py
```

**Regenerate static pages (after DB changes):**
```bash
python generate_scholars_pages.py
```

**Regenerate analytics (after DB changes):**
```bash
python generate_analytics.py
```

**Update web payload (after analytics):**
```bash
python generate_site_data.py
```

### Fetch Latest Conference Programs (Crawling)
```bash
python fetch_latest_programs.py        # Query institutional portals, cache new programs to html_cache/
```

### Utilities

**Validate Publication Data:**
```bash
python validate_publication.py
```

**Generate Publication Pages:**
```bash
python generate_publication_pages.py
```

**SEO Handoff (for external analytics):**
```bash
python generate_seo_handoff.py         # Generate seo_authority_*.jsonl
python import_seo_handoff.py           # Import SEO analytics back into database
```

---

## Directory Structure

| Path | Purpose |
|------|---------|
| `.github/workflows/` | GitHub Actions: `rebuild_and_deploy.yml` (scheduled 2×/year: June 20, Dec 20 UTC); `validate_publication.yml` |
| `analytics_output/` | Generated CSV reports & `data_quality_report.json` |
| `article/` | Scientific manuscript (`ppv_draft.md`), figures, appendices, and hypothesis-testing code (`work_ppv_hypotheses.py`) |
| `assets/` | CSS, JS libraries, theme files |
| `cities/` | Generated city profile pages (10+ static HTML files) |
| `conferences/` | Conference metadata or landing pages |
| `gemini_handoff/` | SEO authority handoff data (`.reply.jsonl` format) |
| `html_cache/` | Cached HTML snapshots from institutional portals |
| `institutions/` | Generated institution profile pages (15+ static HTML files) |
| `scholars/` | 220 static scholar profile HTML cards (auto-generated) |
| `scratch/` | Development scripts (non-production, safe to modify) |
| `themes/` | CSS theme or template definitions |
| `zograf-roerich-db.md` | Seed metadata source (venues, coords, calendar events) |
| `conferences.db` | SQLite database (primary data store) |
| `site_data.json` | High-performance JS payload for browser (auto-generated) |
| `index.html` | Main web portal SPA entry point |

---

## Data Files & Artifacts

### Primary Artifacts
- **`conferences.db`** — SQLite database with 12 normalized tables. Primary source of truth after ingestion.
- **`site_data.json`** — JS object serialization of SQL queries. ~200KB payload. Client-side rendering reads this.
- **`person_ids.json`** — Deduplication mapping: raw name → canonical `person_id`. Used for cross-linking Zograf ↔ Roerich presenters.
- **`authority_ids.json`** — Authority URIs and external identifiers.
- **`search-index.json`** — Full-text search index.

### Generated Outputs (Auto-created after each pipeline run)
- `scholars/*.html` — 220 individual scholar profile pages
- `cities/*.html` — City profile aggregate pages
- `institutions/*.html` — Institution profile pages
- `analytics_output/*.csv` — Scientific datasets (affiliation_leaderboard.csv, overlap_cohort.csv, etc.)
- `indology_scholars_analytics.md` — Analytics summary report

---

## Key Data Structures & Schemas

### Database Schema (12 Tables)
```
event_series → event → event_day → event_day_venue → session → presentation → presentation_person → person
                                                                                              ↑
                                                                                       organization
                                                                                              ↑
                                                                                         place
                                                                                       (venues)
```

**Critical columns:**
- `person.person_id` — UUID primary key (stable across runs)
- `person.normalized_key` — Lowercase Latin name for dedup matching
- `presentation_person.affiliation_text_raw` — Original Cyrillic affiliation string
- `presentation_person.city_tag` — Parsed city for filtering

### Name Deduplication Logic
In `build_and_populate_db.py`, the `normalize_person_name()` function applies regex patterns to map:
- Initials-Lastname (В.В. Вертоградова, В. В. Вертоградова)
- Lastname Firstname (Вертоградова Виктория)
- Lastname-with-suffix (Шалыгина-Кочеткова)
- Latin transliterations (Victoria Vertogradova)

All variations hash to one `normalized_key` and merge into a single `person` record with `display_name` preserving original rendering.

### Presentation_Person Junction Table
Stores the many-to-many relationship between `presentation` and `person`:
- **`role`** — Speaker type (author, co-author, moderator, etc.)
- **`affiliation_text_raw`** — Exactly as parsed from HTML (e.g., "ИВ РАН, СПб")
- **`organization_id`** — FK to canonicalized organization (nullable; null = unknown)
- **`city_tag`** — Extracted city for UI filtering
- **`order_in_session`** — Speaker sequence in session (for reconstructing session lists)

---

## Development Guidelines

### General Practices
- **Session State:** Maintain `.ai_state.md` across Claude Code runs (use `ai_state.json` as JSON fallback). Check off micro-milestones, document blockers.
- **Micro-Commits:** Prefix with `ai-wip:` after logical sub-tasks (schema fix, dedup improvement, UI tweak).
- **Encoding:** All Python scripts must include:
  ```python
  sys.stdout.reconfigure(encoding='utf-8')
  sys.stderr.reconfigure(encoding='utf-8')
  ```
- **Subprocess:** Pass `encoding='utf-8'` to every `subprocess.run()` call reading `gh api` or external output.

### Database Modifications
1. **Schema changes:** Edit the DDL in `build_and_populate_db.py` (in the schema compilation function).
2. **Rebuild from scratch:** Always run `python build_and_populate_db.py` after schema edits to regenerate `conferences.db`.
3. **Downstream regeneration:** After DB changes, regenerate all downstream artifacts in order:
   - `generate_analytics.py`
   - `generate_site_data.py`
   - `generate_scholars_pages.py`

### Adding New Features
- **New filter on UI:** Add column to `presentation_person` or `person`, then modify `generate_site_data.py` to serialize it into JS payload. Update `index.html` filter logic.
- **New analytics:** Add SQL query to `generate_analytics.py`, output CSV to `analytics_output/`, and update `indology_scholars_analytics.md`.
- **New static page type:** Add generator script following pattern of `generate_scholars_pages.py`.

### Testing Workflow
1. Rebuild database: `python build_and_populate_db.py`
2. Check DB integrity: `sqlite3 conferences.db "PRAGMA foreign_key_check;"`
3. Regenerate artifacts: `python generate_analytics.py && python generate_site_data.py && python generate_scholars_pages.py`
4. Launch local server: `python -m http.server 8000`
5. Open browser to `http://localhost:8000` and test filtering, cross-links, bilingual toggle, profile pages

---

## Deployment & CI/CD

### GitHub Actions Workflows

**`rebuild_and_deploy.yml`** — Scheduled twice yearly:
- **June 20 00:00 UTC:** After Zograf Readings spring event
- **December 20 00:00 UTC:** After Roerich Readings winter event
- Also runs on `push` to `main` (except README/CHANGELOG/ai_state.json changes)
- Can be triggered manually via workflow_dispatch

**Steps:**
1. Fetch latest programs (`fetch_latest_programs.py`)
2. Rebuild database (`build_and_populate_db.py`)
3. Generate analytics (`generate_analytics.py`)
4. Generate site data (`generate_site_data.py`)
5. Generate scholar pages (`generate_scholars_pages.py`)
6. Commit updates to `main`
7. Deploy via GitHub Pages to `https://gasyoun.github.io/IndologyScholars/`

**`validate_publication.yml`** — Publication validation (on-demand or scheduled)

### Deployment Destination
Live site: **https://gasyoun.github.io/IndologyScholars/**

---

## Common Tasks & Troubleshooting

### Q: Database schema error after running pipeline
**A:** Run `sqlite3 conferences.db "PRAGMA foreign_key_check;"` to identify constraint violations. Check `build_and_populate_db.py` for missing FK values or out-of-order insertions.

### Q: Scholar profile page has wrong affiliation
**A:** Check `person_ids.json` — the dedup mapping may have incorrectly merged two people. Edit manually to split them, then regenerate pages.

### Q: New conference program cached but not imported
**A:** Run `python build_and_populate_db.py` to re-scan `html_cache/` and ingest new programs.

### Q: Bilingual toggle not working
**A:** Check `site_data.json` is present and recent. Regenerate with `python generate_site_data.py`. Verify `index.html` has translation map loaded.

### Q: GitHub Actions deployment failed
**A:** Check workflow logs at https://github.com/gasyoun/IndologyScholars/actions. Common causes: network timeout on `fetch_latest_programs.py`, encoding errors in Python (missing `reconfigure(encoding='utf-8')`), or missing dependency (`pip install requests beautifulsoup4`).

---

## External Dependencies

- **Python 3.8+**
- **Libraries:** `requests`, `beautifulsoup4` (for `fetch_latest_programs.py`)
- **Browser:** Modern ES6-compatible (tested on Chrome, Firefox, Safari)
- **GitHub:** gh CLI (for deployment workflow)

---

## Key Files to Know

| File | Purpose | Owned by Phase |
|------|---------|--------|
| `build_and_populate_db.py` | Schema + ingestion engine | Phase 2 |
| `generate_analytics.py` | Statistical analysis & CSV export | Phase 3 |
| `generate_scholars_pages.py` | Static HTML card generation | Phase 4 |
| `generate_site_data.py` | JS payload serialization | Phase 5 |
| `fetch_latest_programs.py` | Web crawler for new programs | Utility |
| `zograf-roerich-db.md` | Seed metadata source | Input |
| `index.html` | Main SPA entry point | Phase 5 |
| `assets/` | CSS, JS libraries | Phase 5 |

---

## Context for Future Sessions

This is a **production digital humanities platform** serving academic research. Changes should:
1. Preserve referential integrity (no orphaned FKs)
2. Maintain bilingual consistency (any new text must support both Russian ↔ English toggle)
3. Not break existing scholar profile URLs (permalinks are `scholars/PERS_<uuid>.html`)
4. Document schema changes in `.ai_state.md` for auditing
