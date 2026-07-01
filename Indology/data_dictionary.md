# INDOLOGY-L Archive Atlas Data Dictionary

This document describes the generated public-data layer for `INDOLOGY-L Archive Atlas, 1990-2026`. The atlas is a separate research appendix/tool under `Indology/`; it is not merged into the main Russian conference-archive site.

## Source And Scope

- Source archive: https://list.indology.info/pipermail/indology/
- Coverage target: November 1990 through June 2026.
- Method: metadata-first parsing of monthly archive indexes and monthly mbox headers.
- Out of scope for v1: full message-body NLP and redistribution of message bodies.
- Stable archive anchors: `archive_id`, `archive_url`, `message_id`, `thread_root_id`, and generated local `page_path` values where available.

## Major Table Families

### Messages

`messages_raw.csv`, `messages.csv`, and `messages_clean.csv` move from harvested archive/index metadata to analyzed and author-normalized message metadata. Key provenance fields include `archive_id`, `archive_year`, `archive_month`, `archive_url`, `message_id`, `in_reply_to`, `references`, `date`, subject fields, and topic/list-function labels.

### Authors

`author_aliases.csv`, `authors_needing_review.csv`, and `excluded_author_artifacts.csv` are audit layers. `normalized_author` is a conservative display label, not an authority-file identity. `status`, `confidence`, and `evidence` explain whether a raw author string was confirmed, left for review, or treated as an artifact.

### Replies

`reply_edges.csv` records directed reply evidence from `message_id`, `in_reply_to`, `references`, and conservative thread fallback. Confidence values distinguish exact header matches from lower-confidence inference. `reply_network_edges.csv` aggregates those directed rows.

### Networks

`named_reply_network_summary.csv` is a named direct-reply evidence summary. `named_coparticipation_network_summary.csv` and `network_edges.csv` are co-participation evidence: two authors appear in the same thread. Co-participation is not collaboration.

### Atlas

`atlas_timeline.csv`, `atlas_topic_profiles.csv`, `atlas_list_functions.csv`, `atlas_people_summary.csv`, `atlas_reply_summary.csv`, and `case_study_candidates.csv` translate raw metadata into indologist-facing questions about time, topics, list functions, participation, replies, and candidate threads for close reading.

### Renou

`data/curation/renou_subject_rules.csv` adapts the Louis Renou I-V state axis and register lattice from `RENOU.md` into human-editable subject-line matching rules. `renou_messages.csv` keeps one row per message with optional `renou_states` and `renou_registers`; `renou_message_matches.csv` is the sparse evidence table; `renou_thread_matches.csv`, `renou_state_summary.csv`, `renou_register_summary.csv`, and `renou_coverage.csv` aggregate the layer. Empty Renou fields mean not classified by this layer, not negative evidence.

### Search

`search_threads.json`, `search_authors.json`, `search_topics.json`, and `search_messages_sample.json` feed the static search page. Message search remains compact metadata, not full text.

### Curation

`curated_case_studies.csv`, `case_review_queue.csv`, split review packets, `first_review_shortlist.csv`, `data/curation/first_review_notes.csv`, and `review_import_audit.csv` support the curation round-trip. Generated rows remain `candidate` until manually reviewed.

### Validation

`parse_issues.csv`, `count_mismatch_audit.csv`, `skipped_mbox_rows.csv`, `noisy_subjects.csv`, `human_review_index.csv`, `human_review_summary.json`, `interpretive_guardrails.csv`, `reports/validation.md`, and `reports/interpretive_guardrails.md` make parsing quirks, review needs, and responsible-claims limits visible.

## Review Fields

Human-facing review fields include `curation_status`, `review_track`, `review_decision`, `public_note`, `why_it_matters`, `curator_comments`, `manual_reviewer`, `manual_review_date`, `priority`, `reason`, and `note`. Empty review fields mean not yet reviewed, not negative evidence.

## Caveats

- Reply edges are not influence.
- Message counts are not scholarly importance.
- Archive visibility is not field representativeness.
- Author normalization is a reproducible audit layer, not a biographical authority file.
- Case-study candidates are generated reading suggestions, not a canon of important threads.
- The Renou layer is subject-line classification for mailing-list discussions, not dictionary headword tagging.

## Generated Resources

| File | Rows | Description |
| --- | ---: | --- |
| `data/curation/first_review_notes.csv` | 25 | Human-editable review intake for importing first-review notes. |
| `data/curation/renou_subject_rules.csv` | 25 | Human-editable Renou state/register subject matching rules. |
| `data/processed/atlas_list_functions.csv` | 44 | Readable categories for what work the mailing list performed by decade. |
| `data/processed/atlas_people_summary.csv` | 3150 | Conservative person-level participation summary using normalized author labels. |
| `data/processed/atlas_reply_summary.csv` | 4 | Directed reply reconstruction counts by confidence level. |
| `data/processed/atlas_timeline.csv` | 37 | Year-by-year atlas summary for volume, threads, authors, dominant topics, and list functions. |
| `data/processed/atlas_topic_profiles.csv` | 12 | Topic profiles with time span, thread counts, author counts, and dominant list functions. |
| `data/processed/author_aliases.csv` | 3283 | Public author-normalization audit table, one row per raw author string. |
| `data/processed/author_eras.csv` | 4275 | Generated atlas output. |
| `data/processed/authors_needing_review.csv` | 888 | Ambiguous author strings retained without identity merging. |
| `data/processed/case_review_queue.csv` | 250 | English-only review queue for all generated case-study candidates. |
| `data/processed/case_review_queue_infrastructure.csv` | 16 | Review packet for case-study candidates suggested as infrastructure history. |
| `data/processed/case_review_queue_philological.csv` | 37 | Review packet for case-study candidates suggested as philological substance. |
| `data/processed/case_review_queue_unassigned.csv` | 197 | Review packet for case-study candidates without an automatic track suggestion. |
| `data/processed/case_study_candidates.csv` | 250 | Data-driven thread candidates for close reading and human curation. |
| `data/processed/count_mismatch_audit.csv` | 8 | Documentation of months where archive index and mbox counts differ. |
| `data/processed/curated_case_studies.csv` | 250 | Review-ready curation table seeded from generated case-study candidates. |
| `data/processed/curated_case_summary.csv` | 14 | Aggregate counts by curation status, track, and case type. |
| `data/processed/excluded_author_artifacts.csv` | 2 | Mail-client/list artifacts excluded from person-level analysis. |
| `data/processed/first_review_shortlist.csv` | 25 | Balanced first-pass shortlist for starting human case-study review. |
| `data/processed/human_review_index.csv` | 1921 | Unified reviewer-facing queue for author, case-study, count, noisy-subject, and reply-network checks. |
| `data/processed/human_review_summary.json` | 5 | Machine-readable summary of the unified human review index. |
| `data/processed/interpretive_guardrails.csv` | 7 | Responsible-claims guardrails for interpreting reply, co-participation, volume, archive, and author-normalization outputs. |
| `data/processed/messages.csv` | 72338 | Analyzed message metadata with cleaned subjects, topic labels, thread length, and author display strings. |
| `data/processed/messages_clean.csv` | 72338 | Message metadata with conservative normalized author labels and author audit fields. |
| `data/processed/messages_raw.csv` | 72338 | Harvested message metadata aligned from Pipermail HTML indexes and monthly mbox headers. |
| `data/processed/monthly_counts.csv` | 426 | Message volume by archive month. |
| `data/processed/months.csv` | 426 | Generated atlas output. |
| `data/processed/named_coparticipation_network_summary.csv` | 47103 | Named co-participation network summary by topic. |
| `data/processed/named_reply_network_summary.csv` | 24546 | Named direct-reply network summary by decade, topic, and confidence. |
| `data/processed/network_edges.csv` | 40703 | Undirected co-participation edges: two authors appear in the same thread. |
| `data/processed/noisy_subjects.csv` | 397 | Generated atlas output. |
| `data/processed/parse_issues.csv` | 8 | Generated atlas output. |
| `data/processed/renou_coverage.csv` | 2 | Coverage counts for the sparse Renou subject-line layer. |
| `data/processed/renou_export_index.csv` | 75 | Index of filtered Renou state/register CSV downloads. |
| `data/processed/renou_message_matches.csv` | 9110 | Sparse message-level Renou state/register matches with matched terms and confidence. |
| `data/processed/renou_messages.csv` | 62115 | Row-per-message sparse Renou state/register index derived from subject-line evidence. |
| `data/processed/renou_register_atharva_messages.csv` | 66 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_atharva_summary.csv` | 22 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_atharva_threads.csv` | 46 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_bauddha_messages.csv` | 92 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_bauddha_summary.csv` | 26 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_bauddha_threads.csv` | 46 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_bhasya_messages.csv` | 293 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_bhasya_summary.csv` | 63 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_bhasya_threads.csv` | 154 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_brahmana_messages.csv` | 93 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_brahmana_summary.csv` | 22 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_brahmana_threads.csv` | 47 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_epic_messages.csv` | 563 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_epic_summary.csv` | 104 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_epic_threads.csv` | 336 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_epig_messages.csv` | 355 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_epig_summary.csv` | 89 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_epig_threads.csv` | 208 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_hors_inde_messages.csv` | 13 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_hors_inde_summary.csv` | 5 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_hors_inde_threads.csv` | 12 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_jaina_messages.csv` | 365 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_jaina_summary.csv` | 101 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_jaina_threads.csv` | 288 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_karika_messages.csv` | 17 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_karika_summary.csv` | 3 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_karika_threads.csv` | 8 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_katha_messages.csv` | 174 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_katha_summary.csv` | 49 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_katha_threads.csv` | 115 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_kavya_messages.csv` | 518 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_kavya_summary.csv` | 102 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_kavya_threads.csv` | 254 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_natya_messages.csv` | 124 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_natya_summary.csv` | 25 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_natya_threads.csv` | 72 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_purana_messages.csv` | 160 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_purana_summary.csv` | 37 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_purana_threads.csv` | 90 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_rgveda_messages.csv` | 523 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_rgveda_summary.csv` | 61 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_rgveda_threads.csv` | 283 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_smrti_messages.csv` | 77 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_smrti_summary.csv` | 23 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_smrti_threads.csv` | 41 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_summary.csv` | 935 | Renou register-axis summary by year, topic, and list function. |
| `data/processed/renou_register_sutra_messages.csv` | 108 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_sutra_summary.csv` | 25 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_sutra_threads.csv` | 67 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_tantra_messages.csv` | 211 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_tantra_summary.csv` | 60 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_tantra_threads.csv` | 122 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_upanisad_messages.csv` | 144 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_upanisad_summary.csv` | 28 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_upanisad_threads.csv` | 79 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_vyakarana_messages.csv` | 649 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_vyakarana_summary.csv` | 81 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_vyakarana_threads.csv` | 324 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_yajus_messages.csv` | 24 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_yajus_summary.csv` | 9 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_register_yajus_threads.csv` | 13 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_i_messages.csv` | 1528 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_i_summary.csv` | 146 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_i_threads.csv` | 873 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_ii_messages.csv` | 724 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_ii_summary.csv` | 91 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_ii_threads.csv` | 365 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_iii_messages.csv` | 1215 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_iii_summary.csv` | 137 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_iii_threads.csv` | 637 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_iv_messages.csv` | 323 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_iv_summary.csv` | 68 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_iv_threads.csv` | 179 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_summary.csv` | 581 | Renou I-V state-axis summary by year, topic, and list function. |
| `data/processed/renou_state_v_messages.csv` | 751 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_v_summary.csv` | 139 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_state_v_threads.csv` | 529 | Filtered Renou state/register CSV export used by the clickable dashboard tables. |
| `data/processed/renou_thread_matches.csv` | 3307 | Thread-level rollup of sparse Renou state/register matches. |
| `data/processed/reply_edges.csv` | 42743 | Directed reply edges resolved from In-Reply-To, References, or conservative thread inference. |
| `data/processed/reply_network_edges.csv` | 20783 | Aggregated directed reply edge weights by source, target, and confidence. |
| `data/processed/review_import_audit.csv` | 25 | Audit trail for importing human review notes into curated case metadata. |
| `data/processed/search_authors.json` | 3150 | Static search index for conservative author summaries. |
| `data/processed/search_messages_sample.json` | 4066 | Compact metadata-only message sample for static search. |
| `data/processed/search_threads.json` | 250 | Static search index for generated thread pages and case-study candidate status. |
| `data/processed/search_topics.json` | 12 | Static search index for topic profiles. |
| `data/processed/skipped_mbox_rows.csv` | 12 | Extra mbox rows skipped during subject-based archive alignment. |
| `data/processed/thread_explorer_index.csv` | 250 | Index of generated static thread explorer pages for case-study candidates. |
| `data/processed/threads.csv` | 24034 | Reconstructed thread-level metadata. |
| `data/processed/topic_decade_counts.csv` | 48 | Topic message counts by decade. |
| `data/processed/topic_year_counts.csv` | 405 | Topic message counts by year. |
| `data/processed/yearly_counts.csv` | 37 | Message volume by year. |

