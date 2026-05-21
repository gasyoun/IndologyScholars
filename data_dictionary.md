# IndologyScholars Data Dictionary

Date: 2026-05-22  
Dataset schema version: 1.0.0  
Pipeline version: 2026-05-21

This dictionary describes the reusable data outputs produced by the IndologyScholars build pipeline. The canonical machine-readable resource list is `datapackage.json`; this document adds interpretation notes, stable-ID policy, and column semantics for high-value CSV/JSON outputs.

## 1. Build Pipeline Outputs

| Path | Type | Producer | Purpose |
| --- | --- | --- | --- |
| `conferences.db` | SQLite | `build_and_populate_db.py` | Normalized relational database for series, events, sessions, presentations, people, venues, media, and participation links. |
| `site_data.json` | JavaScript payload | `generate_site_data.py` | Dashboard payload with scholars, timeline data, summary counts, chart inputs, and build metadata. |
| `search-index.json` | JSON | `generate_publication_pages.py` | Static search index for generated pages. |
| `datapackage.json` | JSON | `generate_publication_pages.py` | Frictionless-style metadata, resource list, license, stats, and schemas for key outputs. |
| `CITATION.cff` | YAML/CFF | `generate_publication_pages.py` | Citation metadata for dataset and software reuse. |
| `analytics_output/data_quality_report.json` | JSON | `generate_publication_pages.py` | Machine-readable quality checks and review samples. |
| `analytics_output/publication_file_manifest.csv` | CSV | `generate_publication_pages.py` | Generated file manifest with byte sizes and SHA-256 checksums. |
| `analytics_output/publication_file_manifest.json` | JSON | `generate_publication_pages.py` | JSON version of the generated file manifest with build metadata. |

## 2. Stable Identifier Policy

Presentation and session identifiers are deterministic. They are derived from stable source-level evidence rather than random UUID fragments.

| ID family | Prefix | Scope | Notes |
| --- | --- | --- | --- |
| Person | `PERS_` | Scholar/person identity | Based on local identity normalization and curated merge logic. |
| Session | `SESS_` | Conference session | Stable hash with local order disambiguation where needed. |
| Presentation | `PRES_` | Presentation/talk record | Stable hash from series, year, normalized title, first speaker, and source URL. |
| Event | mixed current IDs | Conference event/year | Current event IDs are stable within the local database. |

### ID Audit Files

| Path | Purpose |
| --- | --- |
| `analytics_output/presentation_id_manifest.csv` | Current manifest for all presentation records. Use this for stable joins and rebuild audits. |
| `analytics_output/id_stability_audit.json` | Before/after rebuild comparison summary. A clean unchanged rebuild should report zero changed IDs, zero missing stable keys, zero new stable keys, and zero duplicate stable-key rows. |
| `analytics_output/id_stability_changed_ids.csv` | CSV detail file for changed IDs. In a clean unchanged rebuild it contains only the header. |
| `analytics_output/id_migration_presentation.csv` | Migration map from earlier presentation IDs to deterministic IDs. |
| `analytics_output/id_migration_presentation.json` | JSON version of the migration report. |

### `presentation_id_manifest.csv`

| Column | Meaning |
| --- | --- |
| `presentation_id` | Stable local presentation ID. |
| `series` | Conference series label. |
| `year` | Event year. |
| `event_id` | Local event ID. |
| `session_id` | Stable local session ID. |
| `title` | Presentation title as parsed/normalized for the archive. |
| `first_speaker` | First listed speaker for stable-key construction and review. |
| `all_speakers` | Pipe-separated speaker list. |
| `source_url` | Source program URL or local source reference when available. |
| `source_snippet_hash` | Short hash of the source snippet, used for drift detection without repeating long source text. |
| `stable_key_candidate` | Natural-key hash used by the manifest comparator. |

## 3. Provenance Sidecars

Provenance sidecars document where curated or derived fields came from and how confident the pipeline is.

| Path | Scope |
| --- | --- |
| `analytics_output/field_provenance_biographical.csv` | Person names, display names, birth/death years, and profile fields. |
| `analytics_output/field_provenance_authority.csv` | External authority identifiers and organization/place authority data. |
| `analytics_output/field_provenance_themes.csv` | Generated presentation theme labels and theme review candidates. |

Common columns:

| Column | Meaning |
| --- | --- |
| `entity_type` | Entity class, such as person, presentation, organization, or place. |
| `entity_id` | Local stable or database ID. |
| `field` | Field being documented. |
| `value` | Published or generated value. |
| `source` | Source category, such as parsed program, authority override, generated heuristic, or manual curation. |
| `source_url` | Source URL when available. |
| `confidence` | Confidence category. |
| `checked_at` | Review/check date when available. |
| `reviewer` | Reviewer or process name when available. |
| `notes` | Additional review notes. |

Confidence values used in the project:

| Value | Interpretation |
| --- | --- |
| `confirmed` | Human-confirmed or high-trust curated value. |
| `manual` | Manual override or manual curation. |
| `high` | High-confidence derived value. |
| `inferred` | Inferred from source structure or repeated evidence. |
| `heuristic` | Rule-based generated value; useful but reviewable. |
| `candidate` | Candidate value that should not be treated as public truth. |
| `unknown` | Source or confidence is not yet known. |

## 4. Authority Outputs

| Path | Purpose |
| --- | --- |
| `authority_ids.json` | Curated authority override source used by generators. |
| `analytics_output/authority_coverage.csv` | Per-scholar authority coverage report. |
| `analytics_output/authority_review_queue.csv` | Prioritized review queue for missing or incomplete authority data. |
| `analytics_output/rinc_lookup_queue.csv` | Review queue for RINC/eLIBRARY lookup work. |

Public JSON-LD `sameAs` links are emitted only for public-confidence records: `confirmed`, `manual`, or `high`. Candidate or preferred-name-only authority records remain internal and should not appear as public external identity assertions.

## 5. Network Exports

| Path | Purpose |
| --- | --- |
| `analytics_output/network_nodes.csv` | Typed node list for person, event, organization, and theme network analysis. |
| `analytics_output/network_edges.csv` | Weighted typed edges with year and conference series context. |
| `networks.html` | Human-readable explanation of network scope and interpretation limits. |

### `network_nodes.csv`

| Column | Meaning |
| --- | --- |
| `node_id` | Namespaced node ID, such as `person:PERS_...` or `theme:History`. |
| `node_type` | One of `person`, `event`, `organization`, `theme`. |
| `label` | Display label. |
| `local_id` | Underlying local ID or normalized label. |
| `weight` | Observed participation or assignment frequency. |

### `network_edges.csv`

| Column | Meaning |
| --- | --- |
| `source` | Source node ID. |
| `target` | Target node ID. |
| `edge_type` | Explicit relation type. |
| `year` | Event year for the observation. |
| `series` | Conference series label. |
| `weight` | Aggregated edge weight for the same source, target, type, year, and series. |

Edge types:

| Edge type | Meaning |
| --- | --- |
| `person_event` | A scholar appears in a conference event. |
| `person_organization` | A scholar is linked to a normalized affiliation observed in a program. |
| `person_theme` | A scholar is linked to a broad title-derived theme. |
| `person_person_copresentation` | Two scholars appear on the same presentation record. |
| `person_person_same_session` | Two scholars appear in the same session. This is co-presence, not proof of collaboration. |

These are participation networks, not citation networks or comprehensive publication networks.

## 6. Analytics CSVs

| Path | Meaning |
| --- | --- |
| `analytics_output/total_indologists.csv` | Master scholar participation list. |
| `analytics_output/zograf_only_indologists.csv` | Scholars observed only in Zograf Readings within the indexed archive. |
| `analytics_output/roerich_only_indologists.csv` | Scholars observed only in Roerich Readings within the indexed archive. |
| `analytics_output/age_cohort_trend.csv` | Median age by conference event for speakers with known birth year. |
| `analytics_output/newcomer_rate_by_year.csv` | Newcomer rate by year/series. |
| `analytics_output/cohort_survival.csv` | Cohort return/survival metrics across conference years. |
| `analytics_output/debut_timing.csv` | First-observed participation timing by scholar. |
| `analytics_output/closedness_metrics.csv` | Local participation closedness/repeat-participation metrics. |
| `analytics_output/online_share_by_year.csv` | Share of online/video-linked records by year where available. |
| `analytics_output/online_repeaters_2020_plus.csv` | Repeat online/video participation after 2020. |
| `analytics_output/youtube_video_list.csv` | Parsed YouTube video list where available. |
| `analytics_output/youtube_playlist_summary.csv` | Summary counts for YouTube playlist sources. |
| `analytics_output/video_presentation_mapping.csv` | Mapping between video records and presentation records. |

## 7. Theme Coding Outputs

| Path | Meaning |
| --- | --- |
| `analytics_output/theme_codes_baseline.csv` | Baseline rule-derived theme coding. |
| `analytics_output/theme_codes_llm.csv` | LLM-assisted theme coding output when available. |
| `analytics_output/theme_codes_final.csv` | Final selected theme coding. |
| `analytics_output/theme_codes_uncertain.csv` | Theme records requiring review. |
| `analytics_output/theme_review_queue.csv` | Generated review queue for uncertain or low-confidence theme classifications. |

Theme labels are navigational aids derived primarily from presentation titles. They should not be treated as a fine-grained content-analysis taxonomy without review.

## 8. Specialized Review Outputs

| Path | Meaning |
| --- | --- |
| `analytics_output/zograf_2026_affiliation_audit.csv` | Affiliation audit for Zograf 2026. |
| `analytics_output/zograf_2026_no_affiliation.md` | Human-readable notes for Zograf 2026 records lacking affiliation data. |
| `analytics_output/no_affiliation_history.md` | Historical no-affiliation notes. |
| `missing_birth_years.md` | Scholars missing birth-year metadata, used for review rather than public identity assertions. |
| `indology_scholars_analytics.md` | Human-readable analytical report generated from CSV outputs. |

## 9. Public HTML Outputs

| Path | Purpose |
| --- | --- |
| `index.html` | Main dashboard. |
| `scholars/*.html` | Generated scholar profiles. |
| `conferences/*.html` | Conference event pages. |
| `themes/*.html` | Theme landing pages. |
| `cities/*.html` | City/geography pages. |
| `institutions/*.html` | Institution pages. |
| `download-data.html` | Download links for reusable files. |
| `data-quality.html` | Data quality report page. |
| `methodology.html` | Methodology notes. |
| `data-sources.html` | Source and authority notes. |
| `known-limitations.html` | Known limitations and interpretation warnings. |
| `how-to-cite.html` | Citation guidance. |
| `metrics-guide.html` | Metric interpretation guide. |
| `networks.html` | Network export interpretation guide. |

## 10. Reuse Guidance

1. Use `presentation_id` for joins only after checking `presentation_id_manifest.csv`.
2. Use `datapackage.json` for machine-readable resource metadata and schemas.
3. Use provenance sidecars when citing or reusing curated/derived fields.
4. Treat `candidate`, `heuristic`, and `unknown` confidence values as review targets.
5. Do not interpret same-session network edges as collaboration without independent evidence.
6. Cite both the original conference program and this archive when making claims about exact historical wording.
