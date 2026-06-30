# INDOLOGY Archive Research Map

Reproducible metadata-first analysis of the INDOLOGY mailing-list archive:

https://list.indology.info/pipermail/indology/

Current standalone appendix version: `0.1.0`. Version history is tracked in
`CHANGELOG.md`; the plain version string is stored in `VERSION` and exposed as
`indology_archive_research.__version__`.

The project harvests monthly archive metadata, reconstructs thread grouping,
labels subject lines with an interpretable topic taxonomy, and produces summary
tables plus publication-ready figures. Full message-body NLP is intentionally
out of scope for v1, but message download links and email headers are preserved
so that a later content layer can be added.

## Quick Start

Create or reuse a Python environment with the packages in `requirements.txt`,
then run a small validation slice:

```sh
python scripts/run_pipeline.py --start-year 2026 --end-year 2026 --insecure
```

Run the whole archive:

```sh
python scripts/run_pipeline.py --start-year 1990 --end-year 2026 --insecure
```

The `--insecure` flag disables TLS certificate verification for this archive
host. It is useful on Windows systems where certificate revocation checks can
stall or fail for `list.indology.info`.

## Outputs

- `data/raw/` - cached HTML and monthly gzip mbox downloads.
- `data/processed/messages.csv` - one row per parsed message.
- `data/processed/threads.csv` - one row per reconstructed thread.
- `data/processed/months.csv` - one row per archive month from the index.
- `data/processed/topic_year_counts.csv` - topic counts by year.
- `data/processed/author_eras.csv` - author activity by decade.
- `data/processed/network_edges.csv` - co-participation edges within threads.
- `data/processed/author_aliases.csv` - public author-normalization audit table.
- `data/processed/authors_needing_review.csv` - ambiguous author strings not merged automatically.
- `data/processed/messages_clean.csv` - message metadata with normalized author fields.
- `data/processed/reply_edges.csv` - directed reply rows from `In-Reply-To`, `References`, and thread inference.
- `data/processed/reply_network_edges.csv` - aggregated directed reply network.
- `data/processed/count_mismatch_audit.csv` - documentation of archive/mbox count quirks.
- `data/processed/dataset_manifest.csv` - downloadable dataset index.
- `data_dictionary.md` - plain-English documentation of table families, identifiers, review fields, and caveats.
- `datapackage.json` - machine-readable metadata for public CSV/JSON/report/dashboard resources.
- `CITATION.cff` - citation metadata for `INDOLOGY-L Archive Atlas, 1990-2026`.
- `data/processed/atlas_*.csv` - guided atlas tables for timeline, topics, list functions, people, and replies.
- `data/processed/case_study_candidates.csv` - automatically selected thread candidates for close reading.
- `data/processed/thread_explorer_index.csv` - index of generated local thread-explorer pages.
- `data/processed/curated_case_studies.csv` - review table for turning candidates into curated public examples.
- `data/curation/first_review_notes.csv` - human-editable review intake seeded from the first-review shortlist.
- `data/processed/case_review_queue.csv` - English-only review queue for all 250 case-study candidates.
- `data/processed/first_review_shortlist.csv` - balanced first-pass shortlist for beginning human review.
- `data/processed/case_review_queue_philological.csv` - review packet for philological-substance candidates.
- `data/processed/case_review_queue_infrastructure.csv` - review packet for infrastructure-history candidates.
- `data/processed/case_review_queue_unassigned.csv` - review packet for candidates needing manual track assignment.
- `data/processed/curated_case_summary.csv` - summary by curation status, track, and case type.
- `data/processed/review_import_audit.csv` - audit trail for review-note imports.
- `data/processed/human_review_index.csv` - unified review queue for author, case-study, count, noisy-subject, and reply-network checks.
- `data/processed/human_review_summary.json` - summary counts for the unified review queue.
- `data/processed/interpretive_guardrails.csv` - responsible-claims guardrails for interpreting atlas outputs.
- `data/processed/named_reply_network_summary.csv` - named direct-reply evidence by decade, topic, and confidence.
- `data/processed/named_coparticipation_network_summary.csv` - named co-participation evidence by topic.
- `data/processed/search_threads.json` - static search index for generated thread pages.
- `data/processed/search_authors.json` - static search index for conservative author summaries.
- `data/processed/search_topics.json` - static search index for topic profiles.
- `data/processed/search_messages_sample.json` - compact metadata-only message sample for search.
- `reports/validation.md` - coverage and spot-check validation.
- `reports/research_report.md` - narrative report: `INDOLOGY-L as Scholarly Infrastructure, 1990-2026`.
- `reports/interpretive_guardrails.md` - readable cautions about supported claims and overclaims.
- `reports/first_review_worksheet.md` - Markdown worksheet for reviewing the balanced first-pass shortlist.
- `dashboard/index.html` - standalone guided atlas with indologist-facing questions.
- `dashboard/search.html` - static search and browse page for subjects, authors, topics, years, functions, messages, and thread pages.
- `dashboard/curated.html` - English-only case-study curation workflow with philological and infrastructure tracks.
- `figures/` - generated PNG visualizations.

## Notebook

`notebooks/indology_archive_research_map.ipynb` is a lightweight notebook
front-end for the same pipeline. It calls the reusable Python modules rather
than duplicating analysis logic.

## Respectful People Analysis

Author data comes from public mailing-list postings. The default outputs avoid
judgmental rankings and present people as participants in public scholarly
conversation: activity by era, topic participation, and thread co-presence.
Author normalization is conservative: exact display-name groups are confirmed,
email-like labels are left for review, and every public mapping is auditable in
`author_aliases.csv`.

## Network Layers

`network_edges.csv` is the broad undirected co-participation network: two people
appeared in the same thread. `reply_edges.csv` is the stricter directed network:
one message is resolved as replying to another message when headers or thread
structure support that inference.

## Guided Atlas

The guided atlas translates the archive into six entry points: what changed over
time, what was discussed, what work the list did, who participated, who replied
to whom, and which threads are worth close reading. It is intentionally cautious:
case-study rows are candidates for human review, and people summaries are not
rankings of scholarly importance.

## Thread Explorer

The thread explorer generates one static page per selected case-study candidate
under `dashboard/threads/`. Each page shows only metadata and subject lines:
chronology, participants, public Pipermail links, reply-confidence evidence, and
unresolved reply-like messages. Use `curated_case_studies.csv` to add human
notes before presenting a generated candidate as a curated example.

## Static Search

`dashboard/search.html` lets readers search and browse the atlas by thread
subject, author, year, topic, list function, candidate type, and compact message
metadata. It reads the generated `search_*.json` files and keeps case-study
status visible as `candidate` unless a row is manually changed in
`curated_case_studies.csv`.

## Curated Cases And Named Networks

`dashboard/curated.html` separates unreviewed candidates from manually selected,
rejected, or needs-more-review cases. Suggested tracks distinguish philological
substance from infrastructure history and include a short basis for each
suggestion. Split review packets make it possible to review philological,
infrastructure, and unassigned candidates in separate passes. The first-review
shortlist is a balanced starting set, not a ranking of importance; human review
fields are intentionally empty until edited. `reports/first_review_worksheet.md`
turns that shortlist into repeated review prompts for consistent human notes.
Named
network summaries are public-archive metadata only:
`named_reply_network_summary.csv` records direct-reply evidence and flags
self-reply rows, while `named_coparticipation_network_summary.csv` records
shared-thread evidence.

## Review Round Trip

The curation loop is: generated shortlist -> fill
`data/curation/first_review_notes.csv` -> import notes -> regenerate atlas.

```sh
python -m indology_archive_research.review_import --output-dir . --seed
python -m indology_archive_research.review_import --output-dir . --dry-run
python -m indology_archive_research.review_import --output-dir .
python -m indology_archive_research.curation --output-dir .
python -m indology_archive_research.search --output-dir .
python -m indology_archive_research.publication --output-dir .
python -m indology_archive_research.validate --output-dir .
```

The importer ignores empty intake cells and does not overwrite non-empty curated
fields unless run with `--force`. All attempted changes are recorded in
`data/processed/review_import_audit.csv`.

## Publication Metadata Layer

The standalone appendix borrows public-data practices from the main
`IndologyScholars` site without merging the two projects. Run the publication
metadata layer after search/curation outputs exist:

```sh
python -m indology_archive_research.publication --output-dir .
python -m indology_archive_research.public_metadata --output-dir .
python -m indology_archive_research.publication --output-dir .
python -m indology_archive_research.validate --output-dir .
```

This creates `data_dictionary.md`, `datapackage.json`, `CITATION.cff`,
`human_review_index.csv`, `human_review_summary.json`,
`interpretive_guardrails.csv`, and `reports/interpretive_guardrails.md`.
`human_review_index.csv` is a queue for human attention, not a list of errors.
The guardrails state the core public-interpretation limits: reply edges are not
influence, co-participation is not collaboration, message count is not
importance, archive visibility is not field representativeness, and author
normalization is an audit layer rather than an authority file.
