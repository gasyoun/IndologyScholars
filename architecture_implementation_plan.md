# Architecture Implementation Plan

Date: 2026-05-21  
Based on: `architecture.md`  
Goal: implement architecture hardening in reviewable steps, starting with ID stability and moving toward provenance, schema versions, authority workflows, and safer generated outputs.

> This is a dated implementation record. For current build instructions and
> publication-state figures, see
> [docs/development-en.md](docs/development-en.md) or
> [docs/development.md](docs/development.md).

## 0. Implementation Status

Implemented on 2026-05-21:

1. ID stability audit tooling:
   - `scratch/export_presentation_id_manifest.py`
   - `scratch/compare_id_manifests.py`
2. Deterministic IDs in `build_and_populate_db.py`:
   - `presentation_id` now uses a stable hash;
   - `session_id` now uses a stable hash with local order disambiguation.
3. Generated audit artifacts:
   - `analytics_output/presentation_id_manifest.csv`
   - `analytics_output/id_stability_audit.json`
   - `analytics_output/id_stability_changed_ids.csv`
   - `analytics_output/id_migration_presentation.json`
   - `analytics_output/id_migration_presentation.csv`
4. Validation additions in `validate_publication.py`:
   - required ID audit artifacts;
   - manifest row count check against SQLite;
   - stable-key drift and duplicate-key checks.
5. Schema/version metadata:
   - `site_data.json` now includes `schema_version`, `generated`, and build metadata;
   - `analytics_output/data_quality_report.json` now includes `schema_version`, `generated`, and build metadata;
   - `datapackage.json` now includes `schema_version`, build metadata, and schemas for key resources;
   - `validate_publication.py` now checks schema metadata and required data package resources.
6. Provenance sidecars:
   - `analytics_output/field_provenance_biographical.csv`;
   - `analytics_output/field_provenance_authority.csv`;
   - `analytics_output/field_provenance_themes.csv`;
   - linked from generated download/data-quality pages and `datapackage.json`;
   - validated for non-empty provenance rows.
7. Authority validation hardening:
   - public person `sameAs` now requires `confidence` in `confirmed`, `manual`, or `high`;
   - person authority IDs are normalized only when their format is valid;
   - `validate_publication.py` checks person ORCID/Wikidata/VIAF/OpenAlex/Scholar/Scopus/ResearcherID/RINC/official URL formats;
   - `validate_publication.py` checks organization Wikidata/ROR/homepage formats and place Wikidata formats;
   - public scholar pages are checked so non-public authority records cannot emit `sameAs`.
8. Network and metrics layer:
   - `generate_analytics.py` now exports `analytics_output/network_nodes.csv`;
   - `generate_analytics.py` now exports `analytics_output/network_edges.csv`;
   - network nodes are typed as person, event, organization, or theme;
   - network edges use explicit `edge_type` values for participation, affiliation, theme, co-presentation, and same-session relations;
   - network CSVs are linked from `download-data.html`, declared in `datapackage.json`, and validated by `validate_publication.py`.
9. Publication file manifest:
   - `generate_publication_pages.py` now exports `analytics_output/publication_file_manifest.csv`;
   - `generate_publication_pages.py` now exports `analytics_output/publication_file_manifest.json`;
   - generated files include byte sizes and SHA-256 checksums;
   - the manifest is linked from `download-data.html`, declared in `datapackage.json`, and validated by `validate_publication.py`.
10. CI hardening:
   - `.github/workflows/validate_publication.yml` now installs `requirements.txt`;
   - CI compiles the ID manifest exporter and comparator;
   - CI runs a before/after database rebuild manifest comparison before generating publication artifacts;
   - `.github/workflows/rebuild_and_deploy.yml` now refreshes ID stability artifacts during deploy builds;
   - deploy commits and Pages artifacts now include `metrics-guide.html` and `networks.html`.
11. Stable ID regression tests:
   - `tests/test_stable_ids.py` covers canonical text normalization;
   - stable hash output is checked for determinism and expected hex length;
   - presentation/session ID prefixes are checked;
   - manifest comparison is tested for clean unchanged rebuilds and changed-ID detection;
   - `.github/workflows/validate_publication.yml` runs `python -m unittest discover -s tests`.

Verified:

- two consecutive rebuilds produced 895 rows both times;
- changed IDs for the same stable key: 0;
- missing stable keys after rebuild: 0;
- new stable keys after rebuild: 0;
- duplicate stable-key rows: 0;
- `python validate_publication.py` passed.
- schema/version validation passed for `site_data.json`, `data_quality_report.json`, and `datapackage.json`.
- provenance sidecar validation passed: biographical, authority, and theme provenance CSVs are non-empty.
- authority validation passed; confirmed records render public links, preferred-name-only records do not.
- network export validation passed: 271 node rows and 4561 edge rows were generated with expected node and edge types.
- publication file manifest validation passed: 605 generated files are listed with SHA-256 checksums.
- local CI-equivalent validation passed: compile, ID manifest before/after comparison, full generators, publication validation, and Pages artifact preparation.
- stable ID regression tests passed locally with `python -m unittest discover -s tests`.

## 1. Implementation Principles

1. Keep every phase small enough for one focused PR.
2. Change generators first; generated files are outputs, not editing targets.
3. Do not migrate IDs blindly. Measure current churn first.
4. Keep old compatibility paths during transitions when external CSVs depend on current IDs.
5. Add validation before relying on new architecture assumptions.
6. Prefer audit files and manifests over hidden in-code behavior.
7. Do not introduce external API enrichment in the architecture hardening phase.

## 2. Workstream Overview

| Workstream | Purpose | First deliverable |
| --- | --- | --- |
| ID stability | Stop rebuilds from invalidating joins | `presentation_id_manifest.csv` and churn audit |
| Deterministic IDs | Replace random presentation/session IDs | stable ID helpers and migration report |
| Provenance | Make derived fields auditable | provenance sidecars for selected fields |
| Schema versions | Make outputs reusable by external tools | `schema_version` in JSON + datapackage schemas |
| Authority workflow | Publish confirmed IDs only | coverage/review queues and confirmed-only `sameAs` |
| Validation | Catch regressions automatically | new checks in `validate_publication.py` |

## 3. Phase 1: ID Stability Audit

Priority: highest.  
Risk: low.  
Why first: it measures the problem without changing the production ID scheme.

### Files To Add

- `scratch/export_presentation_id_manifest.py`
- `scratch/compare_id_manifests.py`

### Files To Update

- `validate_publication.py` only if adding a non-blocking manifest existence check.
- `architecture.md` only if the audit finds a better stable-key formula.

### Manifest Fields

`analytics_output/presentation_id_manifest.csv` or scratch output should contain:

- `presentation_id`
- `series`
- `year`
- `event_id`
- `session_id`
- `title`
- `first_speaker`
- `all_speakers`
- `source_url`
- `source_snippet_hash`
- `stable_key_candidate`

### Implementation Steps

1. Write `export_presentation_id_manifest.py`.
2. Export manifest from current `conferences.db`.
3. Rebuild database once with unchanged inputs.
4. Export a second manifest.
5. Compare:
   - exact `presentation_id` matches;
   - stable-key matches;
   - missing/extra records;
   - duplicate stable-key candidates.
6. Write comparison summary to:
   - `analytics_output/id_stability_audit.json`
   - optionally `analytics_output/id_stability_audit.csv`

### Commands

```bash
python scratch/export_presentation_id_manifest.py --out scratch/manifest_before.csv
python build_and_populate_db.py
python scratch/export_presentation_id_manifest.py --out scratch/manifest_after.csv
python scratch/compare_id_manifests.py scratch/manifest_before.csv scratch/manifest_after.csv --out analytics_output/id_stability_audit.json
```

### Acceptance Criteria

- The scripts run without network access.
- The audit quantifies how many IDs changed.
- Duplicate stable-key candidates are listed explicitly.
- No production IDs are changed yet.

### Rollback

Delete the two scratch scripts and audit outputs. No pipeline behavior should change.

## 4. Phase 2: Stable ID Helper Layer

Priority: highest.  
Risk: low-medium.  
Why second: reusable helpers reduce migration mistakes.

### Files To Update

- `build_and_populate_db.py`
- optionally new helper module: `stable_ids.py`

### Recommended Helper API

```python
def canonical_text(value: str) -> str:
    ...

def stable_hash(*parts: object, length: int = 10) -> str:
    ...

def stable_presentation_id(series_slug, year, title, first_speaker, source_url, disambiguator=None) -> str:
    ...

def stable_session_id(series_slug, year, day_number, session_title, time_text, source_url, order=None) -> str:
    ...
```

### Implementation Steps

1. Add canonical normalization:
   - trim whitespace;
   - collapse internal whitespace;
   - lowercase;
   - normalize Unicode;
   - replace non-breaking spaces;
   - keep Cyrillic intact.
2. Add deterministic hash helper.
3. Add unit-like scratch checks with known inputs.
4. Do not switch the database to stable IDs yet unless Phase 1 shows no key-collision risk.

### Acceptance Criteria

- Same inputs always produce the same IDs.
- Empty or missing parts are handled explicitly.
- Hash length is documented.
- No production rebuild behavior changes unless intentionally enabled.

### Rollback

Remove helper functions/module. No generated files should depend on them yet.

## 5. Phase 3: Deterministic Presentation IDs

Priority: highest.  
Risk: medium-high.  
Why third: this is the core migration.

### Files To Update

- `build_and_populate_db.py`
- `scratch/youtube_match_videos.py`
- `scratch/theme_coding_baseline.py`
- `scratch/theme_coding_llm.py`
- `generate_analytics.py` if it assumes ID format
- `generate_publication_pages.py` if quality reports mention IDs
- `validate_publication.py`

### Files To Generate

- `analytics_output/id_migration_presentation.csv`
- `analytics_output/presentation_id_manifest.csv`

### Implementation Steps

1. Replace random `PRES_...` generation with `stable_presentation_id(...)`.
2. Keep prefix compatibility: continue using `PRES_`.
3. Add collision detection:
   - fail loudly if two distinct records want the same `presentation_id`;
   - add disambiguator only for proven duplicate cases.
4. Generate `id_migration_presentation.csv` during the first migration build.
5. Update video/theme scripts to treat `presentation_id` as stable, while keeping natural-key fallback.
6. Add validation:
   - no duplicate presentation IDs;
   - expected presentation count unchanged;
   - stable manifest exists;
   - optional: compare current manifest to a previous committed manifest.

### Commands

```bash
python build_and_populate_db.py
python generate_analytics.py
python generate_site_data.py
python generate_scholars_pages.py
python generate_publication_pages.py
python validate_publication.py
```

### Acceptance Criteria

- Presentation count remains unchanged.
- Two consecutive rebuilds produce identical `presentation_id` sets.
- Theme/video outputs can join on current IDs.
- `validate_publication.py` fails on duplicate IDs.

### Rollback

Revert `build_and_populate_db.py` ID-generation changes and regenerate. Keep audit/migration CSVs for diagnosis but do not publish them as truth.

## 6. Phase 4: Deterministic Session And Media IDs

Priority: medium.  
Risk: medium.  
Why after presentation IDs: presentation IDs are the urgent external-join problem.

### Files To Update

- `build_and_populate_db.py`
- media ingestion helpers
- validation checks

### Implementation Steps

1. Add `stable_session_id(...)`.
2. Replace random `SESS_...` and `SESS_R_...` generation.
3. Add `stable_media_id(...)` based on media URL or attached entity + URL.
4. Validate:
   - no duplicate sessions;
   - media rows remain attached to the correct entity.

### Acceptance Criteria

- Two rebuilds produce identical session and media ID sets.
- Existing page rendering is unchanged except IDs.
- YouTube/media links still appear where expected.

## 7. Phase 5: Provenance Sidecars

Priority: medium.  
Risk: low-medium.

### Files To Add

- `analytics_output/field_provenance_birth_years.csv`
- `analytics_output/field_provenance_themes.csv`
- `analytics_output/field_provenance_authority.csv`

### Files To Update

- `generate_analytics.py`
- `generate_publication_pages.py`
- `data-quality.html` via generator
- `datapackage.json` via generator

### Implementation Steps

1. Start with sidecars, not a SQLite schema migration.
2. Export provenance for:
   - birth/death years;
   - full names;
   - theme codes;
   - external identifiers;
   - media links.
3. Add links from generated data quality/download pages.
4. Document confidence values:
   - `confirmed`
   - `manual`
   - `inferred`
   - `heuristic`
   - `candidate`
   - `unknown`

### Acceptance Criteria

- Each sidecar is generated reproducibly.
- No candidate authority ID is published as public `sameAs`.
- Data quality page links the sidecars.

## 8. Phase 6: Schema Versions

Priority: medium.  
Risk: low.

### Files To Update

- `generate_site_data.py`
- `generate_publication_pages.py`
- `datapackage.json` generation
- `analytics_output/data_quality_report.json` generation
- `validate_publication.py`

### Implementation Steps

1. Define constants:

```python
DATA_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "2026-05-21"
```

2. Add `schema_version` and build metadata to JSON outputs:
   - `site_data.json`
   - `analytics_output/data_quality_report.json`
   - future audit/provenance JSONs.
3. Add resource schemas to `datapackage.json`.
4. Add validation that JSON outputs include `schema_version`.

### Acceptance Criteria

- JSON outputs declare schema version.
- CSV schemas are discoverable through `datapackage.json`.
- Validator catches missing schema metadata.

## 9. Phase 7: Authority Workflow Hardening

Priority: medium.  
Risk: low-medium.

### Files To Update

- `authority_ids.json`
- `publication_helpers.py`
- `generate_scholars_pages.py`
- `generate_publication_pages.py`
- `validate_publication.py`

### Implementation Steps

1. Normalize confirmed URL-like IDs before public display.
2. Keep candidate IDs out of public JSON-LD.
3. Generate:
   - `analytics_output/authority_coverage.csv`
   - `analytics_output/authority_review_queue.csv`
4. Add validation:
   - ORCID URL format;
   - Wikidata URL/QID format;
   - VIAF URL format;
   - ROR bare ID or URL policy;
   - no candidate confidence in public `sameAs`.
5. Add documentation to generated methodology or data source pages.

### Acceptance Criteria

- Confirmed external links render on profile pages.
- Candidate records remain internal.
- Authority coverage report is linked from data quality/download pages.

## 10. Phase 8: Network And Metrics Layer

Priority: lower.  
Risk: medium.

### Files To Add

- `analytics_output/network_nodes.csv`
- `analytics_output/network_edges.csv`

### Files To Update

- `generate_analytics.py`
- `generate_publication_pages.py`
- optional future `networks.html`

### Implementation Steps

1. Define network scopes:
   - person-person co-presentation;
   - person-person same session;
   - person-organization affiliation;
   - person-theme;
   - organization-theme.
2. Use explicit `edge_type`.
3. Use stable IDs only.
4. Document that these are participation networks, not citation networks.

### Acceptance Criteria

- All edges can be reproduced from SQLite.
- Edge weights and scope are documented.
- No bibliometric ranking is introduced.

## 11. Validation Roadmap

Add checks gradually to `validate_publication.py`.

### Phase 1 Checks

- required generated files exist;
- authority CSVs exist if implemented;
- `metrics-guide.html` exists if implemented.

### Phase 3 Checks

- `presentation_id` uniqueness;
- `presentation_id_manifest.csv` exists;
- repeated rebuild IDs are stable when comparison artifact is supplied.

### Phase 6 Checks

- JSON outputs include `schema_version`;
- `datapackage.json` includes schemas for key CSVs.

### Phase 7 Checks

- confirmed authority URLs are well-formed;
- public `sameAs` does not include candidate/ambiguous IDs.

## 12. Suggested PR Breakdown

### PR 1: Architecture Audit Tools

Scope:

- add manifest exporter;
- add manifest comparer;
- generate current churn audit.

Do not:

- change ID generation.

### PR 2: Stable ID Helpers

Scope:

- add canonical text/hash helpers;
- add local tests/scratch assertions;
- document chosen key formula.

Do not:

- switch production IDs yet.

### PR 3: Presentation ID Migration

Scope:

- switch presentation IDs to deterministic values;
- generate migration report;
- update joins and validators.

Do not:

- change person identity rules at the same time.

### PR 4: Provenance Sidecars

Scope:

- export provenance sidecars;
- link them from generated docs;
- document confidence values.

### PR 5: Schema Versions

Scope:

- add `schema_version`;
- update `datapackage.json`;
- validate schema metadata.

### PR 6: Authority Validation

Scope:

- validate authority URL formats;
- enforce confirmed-only public links;
- keep candidates in queues.

## 13. Review Checklist

Before merging each PR:

1. Does this edit a generator rather than generated HTML?
2. Does `python validate_publication.py` pass?
3. Did presentation/person counts change? If yes, is there an audit explanation?
4. Are generated CSV/JSON files deterministic?
5. Are candidate external IDs kept out of public JSON-LD?
6. Is every new output documented in `datapackage.json` or generated docs?
7. Can the change be rolled back without losing source data?

## 14. Immediate Next Implementation

Start with PR 1.

Concrete tasks:

1. Add `scratch/export_presentation_id_manifest.py`.
2. Add `scratch/compare_id_manifests.py`.
3. Run a before/after rebuild comparison.
4. Write `analytics_output/id_stability_audit.json`.
5. Update `architecture.md` only if the audit changes the recommended stable key.

Expected output:

- a visible measurement of ID churn;
- a list of duplicate stable-key candidates;
- enough evidence to implement deterministic IDs safely in PR 3.
