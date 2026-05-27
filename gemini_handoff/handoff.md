# Visualisation roadmap handoff — Gemini Flash 3.5

Generated: 2026-05-28  
Repository: `C:\Users\user\Documents\GitHub\IndologyScholars`

## Context

We updated the IndologyScholars visualisation roadmap after reviewing the existing site,
article figures, analytics outputs, and public pages.

The user wanted to know what visualisations can still be added, then made decisions about
priority, public uncertainty, language, wording, and dependencies. No new visualisation
code has been implemented yet; only documentation/roadmap files were updated.

## Files already changed in this session

- `article/visual.md` — now the detailed visualisation roadmap.
- `ROADMAP.md` — now includes a concise "VISUALISATION ROADMAP" section and the user's
  locked decisions.

Current working tree status relevant to this handoff:

- `M ROADMAP.md`
- `M article/visual.md`
- `?? gemini_handoff/handoff.md`

## Locked decisions

1. Primary next use case: strengthen the ППВ article first, then add a differentiated
   public-site layer.
2. First public target page: `findings/`.
3. `findings/` visualisations should ship one after another, not as one large bundle.
4. Sequence after the ППВ gate:
   - cross-cohort orbit scatter;
   - affiliation opacity timeline;
   - video heatmap;
   - keyword/meso alluvial.
5. Exploratory L2/meso charts may go public if they carry a visible caveat.
6. New public visualisations should be bilingual from the start.
7. City-only programme rows should use the stronger frame: **affiliation opacity** /
   **аффилиационная непрозрачность**.
8. `needs_review` video mappings may be public as explicit uncertainty.
9. New JS dependencies are acceptable for Sankey/alluvial charts, but they must be
   vendored locally, not loaded from a CDN.

## Existing visualisation surface

Already available as article/static figures:

- participant dynamics and newcomer rate;
- birth-year coverage and age at debut;
- L1 x L2 thematic heatmap;
- cross-cohort balance;
- null-model overlap and retention;
- session-level network bridges;
- geographic gravity;
- closedness forest;
- affiliation transparency;
- Zograf era L2 shift;
- title-keyword contrasts and period trends.

Already available on the public site:

- dashboard charts for annual growth, cohort distribution, geography, generations,
  gender, institutions, word cloud, and a compact Vis.js network;
- full `networks.html` Vis.js graph with presets, filters, search, and node details;
- `spacetime.html` / `spacetime-timeline.html` Leaflet and timeline views;
- `findings/index.html` visual hypothesis cards;
- city, institution, theme, meso, Gumilyov, video, and keyword landing pages;
- downloadable network, classification, video, provenance, and quality CSV/JSON files.

## Important source files to read first

Read these before proposing or coding anything:

1. `article/visual.md` — detailed roadmap and settled sequence.
2. `ROADMAP.md` — top-level project priority context.
3. `generate_publication_pages.py` — public site generator; `findings/index.html` is
   generated here. Do not hand-edit generated HTML as the durable solution.
4. `article/make_ppv_figures.py` — publication figure generator.
5. `article/figures/figure_notes.md` — current computed figure notes.
6. `article/hypothesis_output/hypothesis_workup.md` — tested hypotheses and outputs.
7. `data_dictionary.md` — interpretation and reuse guidance for generated CSV/JSON.

Useful data outputs:

- `article/hypothesis_output/network_bridges_session.csv`
- `article/hypothesis_output/geographic_presentation_distribution.csv`
- `article/hypothesis_output/geographic_speaker_retention.csv`
- `article/hypothesis_output/video_mapping_status.csv`
- `article/hypothesis_output/video_availability_by_year.csv`
- `article/hypothesis_output/video_availability_by_l1.csv`
- `article/hypothesis_output/title_keyword_*.csv`
- `analytics_output/video_presentation_mapping.csv`
- `analytics_output/field_provenance_themes.csv`
- `curation/verified_affiliation_spans.csv`
- `analytics_output/network_nodes.csv`
- `analytics_output/network_edges.csv`

## Implementation guardrails

- The project treats `site_data.json`, generated HTML, generated CSV/JSON, and public
  pages as derived artifacts. Make durable changes in source generators and rebuild.
- Keep the ППВ article figure set argument-bearing. Do not add decorative charts before
  submission unless needed by an editor/reviewer.
- Bilingual public UI is required for the new `findings/` visualisation work.
- Public L2/meso views need visible "classification under review" caveats and links to
  provenance/review queues.
- City-only rows are not verified affiliations. Present them as affiliation opacity.
- `needs_review` video mappings can be shown publicly only as uncertainty, not as
  confirmed evidence.
- If adding a Sankey/alluvial library, vendor the dependency locally and document it. Do
  not rely on CDN loading for the static site.
- Keep CSV/JSON inputs downloadable and citeable; each visual should have a clear data
  source and caveat.

## Suggested next work

### Step 1 — ППВ figure gate

Before coding new public interactives:

1. Rebuild/check the data used by the ППВ article.
2. Verify numbers and captions.
3. Keep optional supplement candidates separate from the submission core:
   - affiliation opacity by year;
   - cross-cohort orbit scatter.

### Step 2 — First `findings/` visual: cross-cohort orbit scatter

Goal: public bilingual interactive on `findings/` showing bridge-orbit structure.

Expected design/data:

- X axis: Zograf talks.
- Y axis: Roerich talks.
- Diagonal: balanced participation.
- Color: institution/trajectory group where defensible.
- Size: active span or total activity.
- Click/links: scholar profile pages.
- Caveat: participation balance is observed programme evidence, not complete scholarly
  biography.

### Step 3 — Second `findings/` visual: affiliation opacity timeline

Goal: show verified institution vs city-only vs empty/unknown vs tentative `(?)` states by
year and series.

Use strong wording: affiliation opacity / аффилиационная непрозрачность.

### Step 4 — Third `findings/` visual: video heatmap

Goal: show video coverage by year, series, and theme with status categories:

- `auto`
- `needs_review`
- `skip`

Important: `needs_review` should be displayed as explicit uncertainty.

### Step 5 — Fourth `findings/` visual: keyword/meso alluvial

Goal: show evolution of title keyword clusters, meso codes, and period trends.

Dependency policy:

- use a dedicated library only if it materially improves the chart;
- vendor locally;
- document the dependency;
- keep source CSV/JSON available.

## Validation expectation

For documentation-only changes, `git diff --check` is enough. For generator/site changes,
run the relevant project gates mentioned in `ROADMAP.md`, especially:

- `python validate_publication.py`
- `python -m unittest tests.test_stable_ids`

If generated artifacts are rebuilt, inspect the diff carefully because this repository has
many generated files and a dirty working tree can be normal.
