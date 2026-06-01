# IndologyScholars Data Dictionary

[Documentation index](docs/README.md) | [Development guide](docs/development-en.md) | [Русская техническая документация](docs/development.md)

Date: 2026-05-25  
Dataset schema version: 1.0.0  
Pipeline version: 2026-05-25

This dictionary describes the reusable data outputs produced by the IndologyScholars build pipeline. The canonical machine-readable resource list is `datapackage.json`; this document adds interpretation notes, stable-ID policy, and column semantics for high-value CSV/JSON outputs.

## 1. Build Pipeline Outputs

| Path | Type | Producer | Purpose |
| --- | --- | --- | --- |
| `conferences.db` | SQLite | `build_and_populate_db.py` | Normalized relational database for series, events, sessions, presentations, people, venues, media, and participation links. |
| `site_data.json` | JavaScript payload | `generate_site_data.py` | Dashboard payload with scholars, timeline data, summary counts, chart inputs, and build metadata. |
| `search-index.json` | JSON | `generate_publication_pages.py` | Static search index for generated pages. |
| `datapackage.json` | JSON | `generate_publication_pages.py` | Frictionless-style metadata, resource list, license, stats, and schemas for key outputs. |
| `CITATION.cff` | YAML/CFF | `generate_publication_pages.py` | Citation metadata for dataset and software reuse. |
| `docs/reuse-rights.md` | Markdown | manual | Rights split for code, derived metadata, cached source material, and article drafts. |
| `docs/institutional-scope.md` | Markdown | manual | Boundary note for city labels, programme affiliations, and verified institutional spans. |
| `docs/classification-reliability-packet.md` | Markdown | manual + generated sample | Classification codebook, review layers, deterministic sample, and ambiguity rules. |
| `docs/scientometrics-sociology.md` | Markdown | manual + generated review index | Responsible metrics stance, sociology-of-science additions, and manual-review rules. |
| `analytics_output/data_quality_report.json` | JSON | `generate_publication_pages.py` | Machine-readable quality checks and review samples. |
| `analytics_output/human_review_index.csv` | CSV | `tools/build_human_review_index.py` | Unified curator-facing index of all open human-review items. |
| `analytics_output/human_review_summary.json` | JSON | `tools/build_human_review_index.py` | Summary counts for the unified human-review index. |
| `analytics_output/scientometrics_guardrails.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Index of the eight scientometrics and sociology-of-science guardrail outputs. |
| `analytics_output/scientometrics_guardrails_summary.json` | JSON | `tools/build_scientometrics_guardrails.py` | Summary counts for the guardrail package. |
| `analytics_output/scientometrics_claim_registry.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Allowed claim families, required evidence, and forbidden overclaims. |
| `analytics_output/coverage_bias_audit.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Per-source authority/index coverage bias audit. |
| `analytics_output/negative_evidence_log.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Reviewable no-hit and rejected-filter evidence for identity matching. |
| `analytics_output/conference_role_taxonomy.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Conference-program role taxonomy for credit and role claims. |
| `analytics_output/event_ecology_audit.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Event/session/venue/format/media coverage audit for conference ecology. |
| `analytics_output/network_robustness_checks.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Typed network-model sensitivity and forbidden-inference checks. |
| `analytics_output/inter_rater_reliability_plan.csv` | CSV | `tools/build_scientometrics_guardrails.py` | Double-coding plan and minimum reliability rules. |
| `analytics_output/fair_reuse_maturity_audit.csv` | CSV | `tools/build_scientometrics_guardrails.py` | FAIR and reuse maturity evidence checklist. |
| `analytics_output/coauthorship_review.csv` | CSV | `generate_analytics.py` | Review queue for source-backed multi-person presentation lines before public coauthorship claims. |
| `analytics_output/senior_absence_audit.csv` | CSV | `generate_analytics.py` | Senior-generation absence review after 2022 and in the 2026 programme. |
| `curation/senior_biographical_verification.csv` | CSV | manual curation / `tools/build_sociology_visuals.py` | External biographical and activity sources used to test whether senior-generation absence rows can be explained biographically. |
| `curation/known_relationships.csv` | CSV | manual curation / `generate_publication_pages.py` | Known non-network relationships between participants, kept as a reviewable explanatory layer rather than inferred coauthorship. |
| `curation/eastern_faculty_alumni.csv` | CSV | manual curation / `generate_site_data.py` | Candidate filter for SPbU Oriental Faculty alumni; rows require source-backed confirmation before strong claims. |
| `analytics_output/publication_file_manifest.csv` | CSV | `generate_publication_pages.py` | Generated file manifest with byte sizes and SHA-256 checksums. |
| `analytics_output/publication_file_manifest.json` | JSON | `generate_publication_pages.py` | JSON version of the generated file manifest with build metadata. |
| `curation/presentation_person_exclusions.csv` | CSV | manual curation / `build_and_populate_db.py` | Source-backed removals of machine-parsed presentation-person links after human review. |
| `curation/verified_affiliation_spans.csv` | CSV | manual curation / `generate_site_data.py` | Source-backed dated institutional trajectories; open continuations inferred into later programme gaps are visibly marked `(?)`. |

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
| `curation/verified_affiliation_spans.csv` | Verified institutional trajectories; city-only programme markers remain geography, while an open trajectory continued beyond its starting evidence is marked `(?)` until contradicted. |
| `curation/known_relationships.csv` | Manual relationship layer for mentorship, family, employment, and other ties that are not reducible to conference co-presence. |
| `curation/eastern_faculty_alumni.csv` | Curated candidate list powering the dashboard filter for SPbU Oriental Faculty alumni. |
| `analytics_output/classification_reliability_sample.csv` | Deterministic review sample for classification reliability checks; rows marked `queued_for_manual_review` are a review queue rather than adjudicated facts. |
| `analytics_output/human_review_index.csv` | Unified open-work register for authority IDs, RINC/OpenAlex/Wikipedia candidates, identity aliases, birth-year gaps, classification, spacetime, affiliation, lineage, and data-quality review items. |
| `analytics_output/scientometrics_guardrails.csv` | Machine-readable index for the claim, coverage, negative-evidence, role, event-ecology, network, inter-rater, and FAIR review layers. |

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

### Human Review Index

`analytics_output/human_review_index.csv` is the single recommended place to
start manual checking. It is generated from the specialized queues, but it does
not replace them; each row keeps `source_file` and `source_row` so the reviewer
can return to the original evidence context.

| Column | Meaning |
| --- | --- |
| `domain` | Review area, such as `authority_identity`, `theme_classification`, or `spacetime_index`. |
| `priority` | Lower number means earlier human review. |
| `source_file` | Original queue, audit CSV, or JSON quality report. |
| `source_row` | Header-aware source row number where available. |
| `record_id` | Local person/presentation ID or external candidate identifier. |
| `label` | Human-readable person name, presentation title, or candidate label. |
| `status` | Current open review status. Completed/accepted rows are filtered out. |
| `reason` | Why this row needs a human decision. |
| `evidence_url` | First available search/profile URL to inspect. |
| `reviewer` | Person or process that performed the check. |
| `checked_at` | Review date. |
| `note` | Domain-specific context carried from the source queue. |

### Scientometrics Guardrails

The guardrail package extends the human-review workflow from individual data
cleaning tasks to interpretation control. The central index is
`analytics_output/scientometrics_guardrails.csv`; each row points to one
generated output and states why a human needs to review that layer.

| Output | Meaning |
| --- | --- |
| `analytics_output/scientometrics_claim_registry.csv` | Claim registry: allowed claim, allowed scope, required evidence, forbidden overclaim, and minimum review artifact. |
| `analytics_output/coverage_bias_audit.csv` | Coverage bias audit for ORCID, Wikidata, VIAF, OpenAlex, Wikipedia, RINC/eLIBRARY, Google Scholar, official URLs, and any external ID. |
| `analytics_output/negative_evidence_log.csv` | Generated negative-evidence candidates from RINC/eLIBRARY no-match notes, Wikipedia no-hit rows, and zero-score OpenAlex candidates. |
| `analytics_output/conference_role_taxonomy.csv` | Source-backed role vocabulary for presenter, chair, organizer, committee, invited, editorial, memorial, and discussant claims. |
| `analytics_output/event_ecology_audit.csv` | Coverage audit for event themes, formats, sessions, chairs, venues, raw affiliations, normalized organizations, and media. |
| `analytics_output/network_robustness_checks.csv` | Typed network specifications and sensitivity checks so edge semantics are not collapsed. |
| `analytics_output/inter_rater_reliability_plan.csv` | Planned double-coding layers and reliability metrics for classification-dependent claims. |
| `analytics_output/fair_reuse_maturity_audit.csv` | FAIR/reuse checklist for stable IDs, metadata, access, schemas, provenance, rights, limits, and guardrail documentation. |

Rows with `review_status=pass` are evidence already present at build time.
Rows with `review`, `needs_source_mapping`, or `planned_double_code` remain
human-review work and are surfaced through `human_review_index.csv`.

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
| `analytics_output/coauthorship_review.csv` | Review queue for all remaining multi-person presentation records. |
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
| `organization_theme` | A normalized organization is linked to a broad theme through presentations by affiliated scholars. |
| `person_person_copresentation` | Two scholars appear on the same presentation record after curated exclusions. This still needs human interpretation before being called durable coauthorship. |
| `person_person_same_session` | Two scholars appear in the same session. This is co-presence, not proof of collaboration. |

These are participation networks, not citation networks or comprehensive publication networks. Organization-theme edges describe observed conference-program affiliation context; they do not claim an institution's complete research profile.

### `senior_absence_audit.csv`

| Column | Meaning |
| --- | --- |
| `cohort` | `absent_after_2022` or `absent_in_2026`. |
| `person_id` | Local person identifier. |
| `display_name` | Public display name from the local database. |
| `birth_year` | Local curated birth year; used only to define the senior-generation screen. |
| `first_year`, `last_year` | First and last observed programme years in the archive. |
| `talks_before_threshold` | Talk count before the relevant threshold. |
| `talks_after_threshold` | Talk count after the threshold or in 2026. |
| `living_status_basis` | Why the row is treated as a living-status review candidate; this is not a public biographical assertion. |
| `review_status` | Always `review` until independently checked. |
| `interpretation_note` | Plain-language caution for publication use. |

### `senior_biographical_verification.csv`

| Column | Meaning |
| --- | --- |
| `person_id`, `display_name` | Local person identifier and public name. |
| `cohort_scope` | Absence mechanism being checked: post-2022 absence or 2026 programme absence. |
| `external_status` | Curated evidence status, such as current profile, post-2022 external activity, no death marker in a biographical profile, or need for a stronger source. |
| `source_title`, `source_url`, `source_date` | External source used for the current verification row. |
| `checked_at` | Date of the local curation check. |
| `interpretation_note` | How the row may and may not be used in public argumentation. |

### `known_relationships.csv`

| Column | Meaning |
| --- | --- |
| `relation_id` | Stable local relation row ID. |
| `source_person_id`, `target_person_id` | Local person IDs when the people are already present in the archive. |
| `source_name`, `target_name` | Human-readable names retained for review and for rows awaiting ID resolution. |
| `relation_type` | Normalized relation category, such as `scientific_supervisor`, `teacher_of`, `student_of`, `spouse`, or `worked_for`. |
| `relation_label_ru`, `relation_label_en` | Public labels for the relation. |
| `direction` | `directed` for mentorship/work ties or `undirected` for reciprocal ties such as spouse. |
| `certainty`, `temporal`, `status` | Curation certainty, temporal/chronological details (such as `сначала`, `затем`, or `ранее`), and review status. |
| `source_note`, `source_url` | Editorial note and optional public source used for verification. |
| `added_at`, `updated_at` | Local curation dates. |

### `eastern_faculty_alumni.csv`

| Column | Meaning |
| --- | --- |
| `person_id`, `display_name` | Person ID and public name used by the dashboard filter. |
| `status` | Review state; the initial rows are candidates until a source directly confirms alumni status. |
| `source_url`, `source_note` | External source and/or note explaining why the row is included. |
| `checked_at`, `curator_note` | Local curation date and free-form reviewer note. |

The review queue can be reproduced with `tools/extract_eastern_faculty_alumni.py`. By default the script only emits heuristic candidates from local corpus snippets. With `--use-gemini` and `GEMINI_API_KEY`, it asks Gemini to classify the same snippets, but affiliation remains a candidate signal rather than proof of graduation.

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

Mapped video records remain searchable in the video catalogue and also set the public `Видео` status on the associated presentation page and card.

## 7. Theme Coding Outputs

| Path | Meaning |
| --- | --- |
| `analytics_output/theme_codes_baseline.csv` | Baseline rule-derived theme coding. |
| `analytics_output/theme_codes_llm.csv` | LLM-assisted theme coding output when available. |
| `analytics_output/theme_codes_final.csv` | Final selected theme coding. |
| `analytics_output/theme_codes_uncertain.csv` | Theme records requiring review. |
| `analytics_output/theme_review_queue.csv` | Generated review queue for uncertain or low-confidence theme classifications. |

The complete `L1`-`L3` classification pass and strict review of preliminary
elevated levels are documented in `docs/classification-audit.md`.

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
| `s/*.html` | Generated scholar profiles. |
| `conferences/*.html` | Conference event pages. |
| `p/*.html` | Permanent pages for individual presentation records, including classification and video status. |
| `themes/*.html` | Theme landing pages. |
| `sociology.html`, `sociology-en.html` | Russian and English field-sociology overview pages. |
| `gatekeeping.html`, `gatekeeping-en.html` | Russian and English gatekeeping-hypothesis pages. |
| `known-relationships.html` | Curated extra-network relationships and personal/academic ties. |
| `voting.html` | Client-side listener talk marks (heard/liked) with CSV/JSON export. |
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
| `classification-criteria.html` | Public criteria for themes, meso-levels, argument scale, and metadata normalization. |
| `videos/*.html` | Standalone recording catalogue retained alongside presentation-level `Видео` badges. |

## 10. Reuse Guidance

1. Use `presentation_id` for joins only after checking `presentation_id_manifest.csv`.
2. Use `datapackage.json` for machine-readable resource metadata and schemas.
3. Use provenance sidecars when citing or reusing curated/derived fields.
4. Treat `candidate`, `heuristic`, and `unknown` confidence values as review targets.
5. Do not interpret same-session network edges as collaboration without independent evidence.
6. Cite both the original conference program and this archive when making claims about exact historical wording.
