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

## Generated Resources

| File | Rows | Description |
| --- | ---: | --- |
| `data/curation/first_review_notes.csv` | 25 | Human-editable review intake for importing first-review notes. |
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
| `data/processed/interpretive_guardrails.csv` | 6 | Responsible-claims guardrails for interpreting reply, co-participation, volume, archive, and author-normalization outputs. |
| `data/processed/messages.csv` | 62112 | Analyzed message metadata with cleaned subjects, topic labels, thread length, and author display strings. |
| `data/processed/messages_clean.csv` | 62112 | Message metadata with conservative normalized author labels and author audit fields. |
| `data/processed/messages_raw.csv` | 62112 | Harvested message metadata aligned from Pipermail HTML indexes and monthly mbox headers. |
| `data/processed/monthly_counts.csv` | 426 | Message volume by archive month. |
| `data/processed/months.csv` | 426 | Generated atlas output. |
| `data/processed/named_coparticipation_network_summary.csv` | 47102 | Named co-participation network summary by topic. |
| `data/processed/named_reply_network_summary.csv` | 24544 | Named direct-reply network summary by decade, topic, and confidence. |
| `data/processed/network_edges.csv` | 40703 | Undirected co-participation edges: two authors appear in the same thread. |
| `data/processed/noisy_subjects.csv` | 397 | Generated atlas output. |
| `data/processed/parse_issues.csv` | 8 | Generated atlas output. |
| `data/processed/reply_edges.csv` | 42741 | Directed reply edges resolved from In-Reply-To, References, or conservative thread inference. |
| `data/processed/reply_network_edges.csv` | 20782 | Aggregated directed reply edge weights by source, target, and confidence. |
| `data/processed/review_import_audit.csv` | 25 | Audit trail for importing human review notes into curated case metadata. |
| `data/processed/search_authors.json` | 3150 | Static search index for conservative author summaries. |
| `data/processed/search_messages_sample.json` | 4064 | Compact metadata-only message sample for static search. |
| `data/processed/search_threads.json` | 250 | Static search index for generated thread pages and case-study candidate status. |
| `data/processed/search_topics.json` | 12 | Static search index for topic profiles. |
| `data/processed/skipped_mbox_rows.csv` | 9 | Extra mbox rows skipped during subject-based archive alignment. |
| `data/processed/thread_explorer_index.csv` | 250 | Index of generated static thread explorer pages for case-study candidates. |
| `data/processed/threads.csv` | 24033 | Reconstructed thread-level metadata. |
| `data/processed/topic_decade_counts.csv` | 48 | Topic message counts by decade. |
| `data/processed/topic_year_counts.csv` | 405 | Topic message counts by year. |
| `data/processed/yearly_counts.csv` | 37 | Message volume by year. |

