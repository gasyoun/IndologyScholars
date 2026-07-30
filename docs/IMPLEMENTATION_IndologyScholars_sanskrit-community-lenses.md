_Created: 29-07-2026 · Last updated: 29-07-2026_

# IMPLEMENTATION — Sanskrit community lenses, Wave 1

This file-level sequence executes the
[architecture](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md)
and must be read through the
[PLAN index](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md).
It is ordered for a 5–8-hour autonomous span. Steps may be shortened by
reusing existing outputs, but they may not be reordered across dependency
boundaries.

## Execution preamble

Work in an isolated worktree based on current `origin/main`. Re-read the root
and subsystem `.ai_state.md` files and Uprava GTD before editing. Never touch
the dirty shared checkout.

The execution task may create local files and run read-only/public acquisition
checks. Under the current authority it may not commit, push, open a PR, merge,
deploy, publish, or mint an H-number. It must not overwrite
`article/ppv_submission_article.md`.

## Step 0 — preflight and immutable inputs

**Files read:**

- `.ai_state.md`
- `README.md`
- `datapackage.json`
- `data_dictionary.md`
- `conferences.db`
- `site_data_scholars.json`
- `analytics_output/theme_codes_final_v2.csv`
- `analytics_output/gumilyov_scale.csv`
- `analytics_output/field_provenance_themes.csv`
- `curation/person_aliases.csv`
- `curation/renou_conference_rules.csv`
- `nagari/README.md`
- `nagari/.ai_state.md`
- `vk-ors/README.md`
- `vk-ors/.ai_state.md`
- `docs/persons-data-policy.md`
- `docs/reuse-rights.md`
- `docs/renou-precision-audit.md`

**Files created:**

- `analytics_output/community_lenses/reports/source_health.md`
- `analytics_output/community_lenses/tables/source_inventory.csv`

**Actions:**

1. Record current git commit and all input file SHA-256 hashes.
2. Reproduce native counts without modifying native stores.
3. Mark each source `complete`, `partial`, `pilot`, `unavailable`, or
   `mixed_snapshot`.
4. Probe the public BVP source once and record the result.
5. Initialize or resume the bounded BVP crawl from its atomic checkpoint and
   record discovered, fetched, parsed, retry, and failure counts.
6. Split records at 31-12-2025; record 2026 separately.

**Acceptance:** all five lenses have inventory rows; no mixed INDOLOGY feed is
accepted; BVP has an explicit measured-coverage verdict.

## Step 1 — package skeleton, schemas, and stable IDs

**Files created:**

- `community_lenses/__init__.py`
- `community_lenses/schema.py`
- `community_lenses/ids.py`
- `community_lenses/manifests.py`
- `community_lenses/cli.py`
- `community_lenses/schemas/source_manifest.schema.json`
- `community_lenses/schemas/comparison_record.schema.json`
- `community_lenses/schemas/annotation.schema.json`
- `community_lenses/schemas/quote.schema.json`
- `tests/test_community_lenses_schema.py`
- `tests/test_community_lenses_ids.py`

**Actions:**

1. Implement the tables defined in ARCHITECTURE in a derived SQLite database.
2. Use `record_id = corpus_id + ":" + source_record_id`; never alter the
   source ID.
3. Provide deterministic fallback hashing only for records without immutable
   native IDs.
4. Enforce foreign keys, controlled status values, unique keys, and ISO dates.
5. Implement deterministic CSV export order.
6. Add `schema_version=1.0.0`.

**Acceptance:** schema creation, load, serialize, reload, and unchanged rebuild
are deterministic; duplicate IDs and broken references fail loudly.

## Step 2 — source manifests and atomic INDOLOGY feed

**Files created or modified:**

- `community_lenses/manifests.py`
- `community_lenses/adapters/__init__.py`
- `community_lenses/adapters/indology_atlas.py`
- `tools/fetch_indology_feed.py`
- `tests/test_indology_feed_snapshot.py`

**Required upstream proposal in IndologyArchiveAtlas:**

- `feed/manifest.json`
- `feed/atlas_timeline.csv`
- `feed/atlas_topic_profiles.csv`
- `feed/atlas_list_functions.csv`
- `feed/atlas_records_public.csv` or an equivalent compact per-record metadata
  feed

**Actions:**

1. Extend the local fetcher to request a versioned manifest first.
2. Download into a temporary staging directory.
3. Verify file list, byte counts, hashes, schema version, and upstream commit.
4. Replace the local cache atomically only after all files validate.
5. Preserve the existing five Renou exports and their consumers.
6. If the new feed is not yet upstream, retain the old Renou feed, mark the
   broader adapter unavailable, and continue without inventing records.

**Acceptance:** interrupted or partial downloads cannot produce a mixed local
snapshot; the old `generate_renou_layer.py` flow stays functional.

## Step 3 — conference adapter

**Files created:**

- `community_lenses/adapters/conferences.py`
- `tests/test_community_lenses_adapters.py`

**Sources reused:**

- `pipeline/schema.py`
- `conferences.db`
- `site_data_scholars.json`
- `public_ids.json`
- `authority_ids.json`
- `analytics_output/theme_codes_final_v2.csv`
- `analytics_output/gumilyov_scale.csv`
- `analytics_output/meso_codes_deepseek.csv`
- `generate_renou_layer.py` outputs

**Actions:**

1. Load annual events, presentations, participations, attested names, and
   affiliations.
2. Preserve every `PRES_*` ID.
3. Map Roerich and Zograf to separate series under the conference lens.
4. Import existing native, meso, Gumilev, and Renou assignments with their
   methods, versions, confidence, and current review state.
5. Do not recompute biography or person IDs.

**Acceptance:** presentation, participation, event, and person totals reconcile
exactly with the frozen conference source; no canonical record changes.

## Step 4 — nagari and ORS/VK adapters

**Files created:**

- `community_lenses/adapters/nagari.py`
- `community_lenses/adapters/vk_ors.py`
- `tests/test_community_lenses_rights.py`

**Sources reused:**

- `nagari/nagari_group_archive/ingest.py`
- `nagari/nagari_group_archive/taxonomy.py`
- `nagari/nagari_group_archive/insights.py`
- `nagari/nagari_group_archive/redact.py`
- `vk-ors/vk_ors_archive/ingest.py`
- `vk-ors/vk_ors_archive/insights.py`

**Actions:**

1. Read existing SQLite/CSV outputs; do not reimplement mbox or XLSX parsing.
2. Preserve nagari message/thread/reply IDs and rights status.
3. Preserve VK owner/post IDs, hashtags, attachments, and missing-view
   semantics.
4. Import hashtags as native self-classification and keyword topics as a
   separate derived assignment.
5. Keep nagari source-local actors unlinked until curated.
6. Represent VK as one publishing account; do not fabricate an author network.

**Acceptance:** native totals reconcile; no body or attachment leaks into
public exports; missing engagement values remain missing rather than zero.

## Step 5 — BVP adapter and source contract

**Files created:**

- `bvp/README.md`
- `bvp/scrape.py`
- `bvp/fetch_hardening.py`
- `community_lenses/adapters/bvp.py`
- `tests/test_bvp_adapter.py`
- `analytics_output/community_lenses/reports/bvp_source_assessment.md`

**Actions:**

1. Record the public group description, access settings, posting rules, current
   visible conversation count, and earliest verified archive date.
2. Discover public conversation URLs and persist stable conversation IDs in an
   atomic checkpoint; accept seed URLs from existing nagari and ORS/VK links.
3. Fetch conversation pages sequentially, skip existing good captures, retry
   once with jitter, pause adaptively after repeated network errors, and keep
   append-only success/failure ledgers.
4. Parse native conversation/message IDs, source URLs, attested author names,
   timestamps, subjects, exact bodies, reply structure where exposed, and raw
   SHA-256 hashes into a derived manifest.
5. Keep the BVP taxonomy, identity namespace, and rights decisions separate
   from nagari.
6. Keep raw HTML and attachments in ignored local storage. Exact article quotes
   require stable URLs, context review, and removal of unrelated contact data.
7. Compute `listed`, `discovered`, `fetched`, `parsed`, `failed`, and
   `excluded` counts. Unless these reconcile against a public listing
   denominator, set `coverage_status=partial` or `pilot` and disable
   completeness-dependent outputs.

**Acceptance:** the adapter is complete for its declared coverage status;
partial data cannot accidentally pass a completeness-dependent query; an
interrupted run resumes without re-fetching good captures.

## Step 6 — codebooks and crosswalks

**Files created:**

- `community_lenses/taxonomy.py`
- `community_lenses/codebooks/intellectual_content.csv`
- `community_lenses/codebooks/community_function.csv`
- `community_lenses/codebooks/argument_level.csv`
- `community_lenses/codebooks/taxonomy_crosswalk.csv`
- `tests/test_community_lenses_taxonomy.py`

**Actions:**

1. Encode definitions, inclusions, exclusions, examples, and versions.
2. Import every source-native label before mapping.
3. Map source-native labels to shared axes with many-to-many relation types.
4. Import Renou states/registers as their own schemes.
5. Do not map Renou to a single shared topic where the relation is only broad
   or related.
6. Keep `unknown`, `other`, and `not_applicable` distinct.

**Acceptance:** all source labels survive round-trip; every crosswalk row has
relation, rationale, version, and review state; unmapped labels are reported.

## Step 7 — classification and Gumilev extension pilot

**Files created:**

- `community_lenses/classify.py`
- `analytics_output/community_lenses/review/classification_sample.csv`
- `analytics_output/community_lenses/reports/classification_validity.md`
- `tests/test_community_lenses_classification.py`

**Actions:**

1. Apply native labels and exact deterministic rules first.
2. Generate model-assisted suggestions only in a separate proposal column,
   recording model ID, prompt/ruleset version, confidence, and rationale.
3. Build a stratified review sample by lens, period, native class, and
   uncertainty.
4. Reuse conference `argument_level` as canonical existing evidence.
5. For other lenses, run only a pilot on records that make identifiable
   scholarly claims.
6. Label announcements, bare resource links, greetings, and bibliography-only
   requests `not_applicable`.
7. Publish cross-lens Gumilev distributions only if the pilot meets the
   verification threshold; otherwise report conference results plus a
   non-comparable pilot.

**Acceptance:** no model suggestion becomes accepted without the documented
decision rule; all G3 and an oversample of G2 are reviewable; source-native
labels remain independent.

## Step 8 — people and cross-lens identity

**Files created:**

- `community_lenses/identity.py`
- `curation/community_person_links.csv`
- `analytics_output/community_lenses/review/person_match_candidates.csv`
- `tests/test_community_lenses_identity.py`

**Actions:**

1. Reuse existing conference person IDs and accepted aliases.
2. Preserve all source-local names and source account IDs.
3. Link only exact authority IDs or manually accepted aliases automatically.
4. Emit exact-name/affiliation and fuzzy/transliteration candidates for review.
5. Record negative decisions so rejected candidates do not recur.
6. Verify the named Russian INDOLOGY-L cases supplied by the author from
   attested records; treat the list as a hypothesis, not a hard-coded census.
7. Never infer nationality from name or script.

**Acceptance:** no fuzzy link is accepted automatically; every accepted link
has evidence and reviewer; person overlap figures use accepted links only.

## Step 9 — exact quotation register

**Files created:**

- `community_lenses/quotes.py`
- `curation/community_quotes.csv`
- `analytics_output/community_lenses/review/quote_context_review.csv`
- `tests/test_community_lenses_quotes.py`

**Actions:**

1. Select short exact quotations tied to planned article claims.
2. Preserve author, date, subject/thread, stable URL, retrieval date, and
   before/after context hashes.
3. Mark ellipses and omissions explicitly.
4. Strip unrelated email, telephone, postal, and signature details without
   rewriting the quoted claim.
5. Require source-specific rights status.
6. Keep nagari quotes non-exportable until its existing owner/rights gate is
   explicitly approved.
7. Omit unstable, deleted, contextless, or unapproved quotes; never replace
   them with paraphrases.

**Acceptance:** exported quote text is byte-identical to its reviewed source
span after explicit marked omissions; every quote passes context and rights
review.

## Step 10 — metrics, figures, and validity report

**Files created:**

- `community_lenses/metrics.py`
- `community_lenses/figures.py`
- `community_lenses/report.py`
- `analytics_output/community_lenses/tables/*.csv`
- `analytics_output/community_lenses/figures/*.{svg,png,pdf}`
- `analytics_output/community_lenses/reports/comparison_validity.md`
- `analytics_output/community_lenses/reports/claims_ledger.csv`
- `tests/test_community_lenses_metrics.py`

**Actions:**

1. Centralize period bins and the 31-12-2025 cutoff.
2. Emit every metric with numerator, denominator, denominator unit,
   missingness, and source snapshot.
3. Generate the six figures specified in ROADMAP.
4. Suppress completeness-dependent BVP charts when status is `pilot`.
5. Mark each proposed claim `supported`, `provisional`, `expert_judgment`, or
   `out_of_scope`.
6. Keep the article's conference core visually and analytically dominant.

**Acceptance:** no cross-lens raw activity total is treated as comparable;
figures regenerate deterministically; all claims trace to frozen tables.

## Step 11 — freeze and outline

**Files created:**

- `community_lenses/snapshot.py`
- `article/comparison_snapshots/through-2025/`
- `article/comparison_snapshots/partial-2026/`
- `article/ppv_comparative_revision_outline_ru.md`
- `tests/test_community_lenses_snapshot.py`

**Actions:**

1. Copy only approved compact derived assets into each snapshot.
2. Produce machine-readable `manifest.json` plus a human-readable
   `manifest.txt`, both with SHA-256 hashes.
3. Record source versions, schema/codebook versions, pipeline commit, and
   creation timestamp.
4. Make snapshot creation fail if the destination already exists; never ask to
   overwrite or recursively delete it.
5. Write a detailed Russian outline mapped to current PPV sections, planned
   claims, figures, quotations, limitations, and evidence rows.
6. Do not create the revised prose draft in Wave 1.

**Acceptance:** unchanged inputs produce identical content hashes apart from
explicit creation metadata; 2026 records cannot enter the through-2025
package; submitted PPV files remain unchanged.

## Step 12 — full verification and state

**Files modified:**

- `.ai_state.md`
- `data_dictionary.md`
- `datapackage.json`
- `.gitignore`

**Actions:**

1. Document new assets and their source/derived status.
2. Ignore raw BVP exports and temporary acquisition caches.
3. Run the exact command matrix in VERIFICATION.
4. Record pass/fail counts, known limitations, and next steps in `.ai_state.md`.
5. Do not commit or push under the current authority.

**Acceptance:** all mechanical gates pass or the affected adapter is explicitly
parked under the autonomy contract; no blocking decision marker remains.

## Timebox fallback

If the 8-hour cap is reached:

1. preserve completed Steps 0–6;
2. finish a deterministic four-lens package;
3. keep BVP as a documented pilot;
4. ship the review queues, validity report, and Russian outline skeleton;
5. do not leave partially trusted identity or quotation exports enabled.

The minimum acceptable Wave 1 is a valid schema, synchronized manifests,
four working adapters, a BVP source assessment/pilot, codebooks, review queues,
and a claims-validity report. Figures and the full outline are next in priority;
article prose is never pulled forward to compensate.

## Related planning layers

- [Plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Roadmap](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Architecture](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md)
- [Verification](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_IndologyScholars_sanskrit-community-lenses.md)

_Dr. Mārcis Gasūns_
