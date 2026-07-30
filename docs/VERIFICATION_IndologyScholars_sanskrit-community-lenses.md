_Created: 29-07-2026 · Last updated: 29-07-2026_

# VERIFICATION — Sanskrit community lenses

This verification contract proves the Wave 1 outputs specified in the
[roadmap](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md)
and built through the
[implementation sequence](https://github.com/gasyoun/IndologyScholars/blob/main/docs/IMPLEMENTATION_IndologyScholars_sanskrit-community-lenses.md).
Passing code tests alone is insufficient: source completeness, classification
validity, identity evidence, quotation context, and denominator discipline are
publication gates.

## Gate summary

| Gate | Pass condition | Failure consequence |
|---|---|---|
| V1 Source manifests | all included inputs pinned, hashed, and coverage-labeled | halt affected adapter |
| V2 Schema and IDs | unique stable IDs, valid references, deterministic round-trip | halt whole build |
| V3 Adapter reconciliation | native counts reconcile exactly or explained refresh is within 1% | halt affected adapter |
| V4 Temporal separation | no 2026 record in the through-2025 package | halt whole build |
| V5 Taxonomy preservation | every native label retained; every crosswalk typed and versioned | suppress affected comparison |
| V6 Classification validity | declared agreement threshold met on stratified samples | label pilot/provisional or suppress |
| V7 Identity | every accepted cross-lens link has deterministic or human evidence | exclude unverified links |
| V8 Quotations | exact, contextual, stable, rights-approved, contact-clean | omit failed quote; no paraphrase |
| V9 Metrics | every value names numerator, denominator, unit, missingness, snapshot | suppress affected metric/figure |
| V10 Figures and report | deterministic regeneration and claim traceability | no article revision |
| V11 Snapshot | complete SHA-256 manifest and byte-stable unchanged rebuild | no release/article revision |
| V12 Existing project health | current publication and relevant satellite tests stay green | fix regression before proceeding |

## V1 — source manifests

For each lens verify:

- canonical source and owner;
- native unit;
- coverage dates;
- cutoff date;
- coverage status;
- source version or immutable export ID;
- input file hash;
- acquisition timestamp;
- access and rights basis;
- adapter, schema, and codebook versions.

Specific rules:

- conference inputs pin the IndologyScholars commit and frozen file hashes;
- nagari and ORS/VK pin the local normalized DB/export hashes;
- INDOLOGY-L pins the IndologyArchiveAtlas commit and every feed-file hash;
- BVP is `complete` only when the public listing denominator, discovered IDs,
  fetched pages, parsed records, exclusions, and failures reconcile; otherwise
  it is `partial` or `pilot`;
- no source silently refreshes during a build.

Pass command:

```powershell
python -m community_lenses.cli validate-manifests
```

Expected result: zero missing required fields, zero hash mismatches, zero
`mixed_snapshot` sources.

## V2 — schema, IDs, and round-trip

Checks:

1. unique primary keys;
2. all foreign keys resolve;
3. controlled enumerations contain no unknown literal values;
4. source IDs are preserved byte-for-byte;
5. titles, names, and labels are absent from identity-generation inputs when a
   stable native ID exists;
6. SQLite → deterministic CSV → reload preserves row content;
7. unchanged rebuild produces identical ordered exports.

Commands:

```powershell
python -m pytest -q tests/test_community_lenses_schema.py tests/test_community_lenses_ids.py
python -m community_lenses.cli validate-schema
python -m community_lenses.cli roundtrip-check
```

Any existing `PRES_*` ID change is a whole-build failure.

## V3 — adapter reconciliation

Each adapter emits a reconciliation table:

`native_table`, `native_count`, `adapted_count`, `difference`,
`difference_reason`, and `status`.

Expected baseline classes:

- conferences: presentations, participations, people, events;
- nagari: messages, threads, members, reply links, attachments;
- ORS/VK: posts, dated posts, hashtags, attachments, engagement availability;
- INDOLOGY-L: messages, threads, author strings, replies, topic/function rows;
- BVP: listed, discovered, fetched, parsed, excluded, retry, and failure totals.

Commands:

```powershell
python -m community_lenses.cli build --cutoff 2025-12-31
python -m community_lenses.cli reconcile
python -m pytest -q tests/test_community_lenses_adapters.py tests/test_indology_feed_snapshot.py tests/test_bvp_adapter.py
```

Exact reconciliation is required for frozen file inputs. A live-source
difference up to 1% is acceptable only when the new retrieval timestamp and
new records explain it and the snapshot is then refrozen. Larger or unexplained
drift parks that adapter.

## V4 — temporal separation

Checks:

- `through-2025` has `created_at <= 2025-12-31T23:59:59` in the record's source
  timezone;
- every 2026 record has `is_partial_2026=1`;
- the main trend periods end in 2025;
- figures do not combine partial 2026 with earlier annual rates;
- pre-1990 material appears only in historical context, not the common digital
  observation table.

Commands:

```powershell
python -m community_lenses.cli validate-cutoff --cutoff 2025-12-31
python -m pytest -q tests/test_community_lenses_snapshot.py
```

Tolerance: zero leaking records.

## V5 — source-native labels and crosswalks

Checks:

- every native assignment exists independently of shared assignments;
- every source-native label appears in the crosswalk inventory, including
  explicit `unmapped`;
- mapping relation is one of `exact`, `broad`, `narrow`, `related`, or
  `unmapped`;
- no many-to-many source relation is flattened into one unsupported exact
  mapping;
- Renou state/register, meso, and Gumilev remain separate schemes;
- codebooks define inclusion, exclusion, examples, and version.

Commands:

```powershell
python -m pytest -q tests/test_community_lenses_taxonomy.py tests/test_community_lenses_crosswalk.py
python -m community_lenses.cli crosswalk-report
```

Acceptance: 100% label inventory coverage; zero untyped mappings; all
publication-used mappings reviewed.

## V6 — classification validity

### Shared intellectual content and community function

Construct a deterministic stratified sample:

- at least 40 records from each complete lens;
- all BVP pilot records or at least 40 if a complete export exists;
- proportional representation by period and common native classes;
- oversample low-confidence, multi-label, `other`, and `unknown` records.

Report:

- raw agreement;
- per-label precision/recall/F1 against reviewed labels;
- Cohen's kappa where prevalence permits;
- Gwet's AC1 and bootstrap confidence interval;
- confusion matrix by lens.

Publication threshold:

- raw agreement at least 80%;
- Gwet AC1 at least 0.70 overall;
- no article-critical label below 0.70 precision.

If the threshold fails, keep native labels, mark shared labels provisional, and
suppress cross-lens topic/function claims that depend on the failed class.

### Gumilev argument level

- preserve existing conference values and reliability report;
- include all proposed cross-lens G3;
- oversample cross-lens G2;
- include a balanced sample of G1, `not_applicable`, and `unknown`;
- separately score applicability and G1/G2/G3 level.

Cross-lens Gumilev publication threshold:

- applicability precision at least 0.90;
- raw level agreement at least 80%;
- Gwet AC1 at least 0.67;
- every accepted G3 reviewed.

If the threshold fails, retain conference Gumilev results and report the other
lenses only as a non-comparable pilot.

Commands:

```powershell
python -m community_lenses.cli build-review-samples
python -m community_lenses.cli score-classification --reviewed analytics_output/community_lenses/review/classification_sample_reviewed.csv
python -m pytest -q tests/test_community_lenses_classification.py
```

No model-only score counts as human validation.

## V7 — person identity

Accepted links require one of:

- existing canonical person ID;
- exact ORCID or verified authority identifier;
- manually accepted alias with evidence;
- manually reviewed exact name plus compatible time-bound affiliation.

Checks:

- fuzzy and transliteration-only candidates remain pending;
- rejected pairs remain in the negative-decision ledger;
- source names and scripts remain unchanged;
- no nationality is inferred from name, email domain, script, or forum;
- claimed Russian INDOLOGY-L cases have attested records and an explicit
  verification state.

Commands:

```powershell
python -m pytest -q tests/test_community_lenses_identity.py
python -m community_lenses.cli identity-report
```

Acceptance: 100% evidence coverage for accepted links and zero automatically
accepted fuzzy links.

## V8 — exact quotation and rights gate

For every article-used quotation verify:

1. the source URL opens at review time;
2. author, date, thread subject, and record ID match;
3. quoted bytes match the source span after only explicitly marked omissions;
4. before/after context hashes match;
5. the quote supports the associated claim;
6. unrelated email, telephone, postal, and signature data are absent;
7. rights status is approved for that source;
8. a removed/deleted message is omitted from publication.

Source-specific rules:

- nagari quotes remain non-exportable until the existing owner/rights gate is
  explicitly approved;
- BVP pilot quotes require public stable URLs and context review;
- private/export-only BVP content requires the export's rights terms;
- VK and INDOLOGY-L public visibility does not remove context and contact-data
  checks.

Commands:

```powershell
python -m pytest -q tests/test_community_lenses_quotes.py tests/test_community_lenses_rights.py
python -m community_lenses.cli validate-quotes
```

Acceptance: 100% of exported quotes pass. Failed quotes are omitted and logged;
they are not paraphrased.

## V9 — metrics and denominator discipline

Every metric must expose:

- numerator;
- denominator;
- denominator unit;
- period;
- missingness;
- source snapshot;
- calculation method and version.

Reject:

- a single total of talks + messages + threads + posts;
- early VK views represented as zero;
- BVP proportions from a pilot;
- cross-lens person overlap that includes pending matches;
- 2026 in 2005–2025 trends.

Commands:

```powershell
python -m pytest -q tests/test_community_lenses_metrics.py
python -m community_lenses.cli validate-metrics
```

Acceptance: zero metric rows without denominators; zero prohibited
combinations.

## V10 — figures, validity report, and claims ledger

Checks:

- all six planned figures regenerate from frozen tables;
- figure captions state lens, native unit, period, denominator, and coverage
  caveat;
- BVP completeness status is visible;
- Russia–West–India labels are forum orientations, not person nationalities;
- every article claim points to one or more metric, quote, or expert-judgment
  rows;
- author expert judgments are visibly marked and not assigned p-values.

Commands:

```powershell
python -m community_lenses.cli figures --snapshot through-2025
python -m community_lenses.cli report
python -m community_lenses.cli validate-claims
```

Acceptance: deterministic figure hashes on unchanged inputs; zero unlinked
article claims.

## V11 — snapshot reproducibility

Snapshot contents:

- schema and codebooks;
- source manifest;
- compact common tables;
- review/validity summaries;
- quote register containing only approved exportable quotes;
- figures;
- claims ledger;
- data dictionary;
- machine and human manifests.

Commands:

```powershell
python -m community_lenses.cli freeze --cutoff 2025-12-31 --name through-2025
python -m community_lenses.cli freeze --from 2026-01-01 --name partial-2026
python -m community_lenses.cli verify-snapshot article/comparison_snapshots/through-2025
python -m community_lenses.cli verify-snapshot article/comparison_snapshots/partial-2026
```

Acceptance:

- all listed SHA-256 hashes match;
- no unlisted file appears;
- rebuild into a new temporary directory is byte-identical except the explicit
  creation timestamp field;
- existing snapshot directories are never overwritten.

## V12 — existing project health

Run from the repository root:

```powershell
python -m pytest
python -m unittest discover -s tests
python validate_publication.py
python tools/fetch_indology_feed.py
python generate_renou_layer.py
python -m pytest -q tests/test_renou_layer.py
```

nagari smoke:

```powershell
python nagari/scripts/audit_publish_surface.py
Push-Location nagari
python -m nagari_group_archive.ingest --limit 300
python scripts/run_pipeline.py --skip-ingest
Pop-Location
```

ORS/VK smoke:

```powershell
Push-Location vk-ors
python -m vk_ors_archive.ingest --limit 300
python -m vk_ors_archive.insights
python -m vk_ors_archive.page
Pop-Location
```

Use temporary/output-specific paths where the command supports them. Inspect
the worktree afterward and exclude unrelated regenerated churn. Under the
current fence, do not commit or push even when all gates pass.

## Risks and required spikes

| ID | Risk | Severity | Detection | Pinned response |
|---|---|---:|---|---|
| R1 | Native units create false comparability | High | metric/figure review | retain source-specific denominators and small multiples |
| R2 | BVP listing pagination is incomplete or changes | High | crawl reconciliation | preserve checkpoints and gap ledger; publish only measured-coverage results |
| R3 | Exact quotations conflict with corpus rights | High | quote rights status | keep selected row non-exportable or omit; never paraphrase |
| R4 | Shared taxonomy erases local meaning | High | crosswalk audit | preserve native labels and non-exact relations |
| R5 | Gumilev G2/G3 remains unreliable outside talks | High | stratified scoring | conference-only result plus labeled pilot |
| R6 | Name matching creates false cross-platform people | High | identity evidence audit | review-only fuzzy candidates |
| R7 | “West” and “India” become nationality claims | High | claims ledger | treat as forum orientation; measure affiliations separately |
| R8 | Rolling INDOLOGY feed mixes versions | High | manifest/hash check | atomic manifest-first fetch or park adapter |
| R9 | Renou false positives contaminate article | High | existing gold gate | do not publish Renou comparison until adjudicated |
| R10 | 2026 partial data leak into trends | High | cutoff test | zero-tolerance build failure |
| R11 | Partial BVP crawl appears as full corpus in charts | High | completeness-dependent query test | suppress population figures unless crawl reconciliation passes |
| R12 | Article becomes a five-corpus survey and loses PPV focus | Medium | outline allocation audit | keep roughly two-thirds of analysis on conferences |
| R13 | Snapshot script overwrites prior evidence | High | destination-exists test | fail closed; mint a new snapshot name |
| R14 | Full test run produces unrelated generated churn | Medium | post-test git status | inspect and exclude; never clean user files destructively |

Required spikes before an affected architecture is considered hardened:

1. **BVP acquisition spike:** prove public listing enumeration/pagination,
   server-rendered field extraction, resume behavior, and coverage
   reconciliation on a bounded crawl.
2. **INDOLOGY feed spike:** prove the expanded Atlas feed is atomic,
   schema-versioned, and compact.
3. **Cross-lens Gumilev spike:** validate applicability and G1/G2/G3 on a
   stratified pilot before bulk assignment.
4. **Quote-rights spike:** resolve nagari's existing owner gate before any
   nagari quotation is exportable.

None of these is a blocking decision for Wave 1 because each has a pinned
fallback. They are blocking evidence gates for the corresponding publication
claim.

## Autonomy-readiness checklist

- [x] Every Wave 1 deliverable has an architecture contract.
- [x] Every Wave 1 deliverable has ordered file-level steps.
- [x] Every Wave 1 deliverable has an acceptance criterion.
- [x] Every Wave 1 deliverable has identified risks.
- [x] BVP incomplete-crawl behavior is pinned.
- [x] Identity ambiguity behavior is pinned.
- [x] Classification ambiguity behavior is pinned.
- [x] Quotation failure behavior is pinned.
- [x] 2026 separation is zero-tolerance.
- [x] Existing assets are reused rather than rebuilt.
- [x] No blocking decision marker remains.
- [x] Commit/push/publication authority is explicitly forbidden for this span.

**Gate verdict:** PASS for local autonomous execution. Handoff registration and
public delivery remain intentionally unwired because the approved minting and
delivery mechanisms push to remote repositories.

## Related planning layers

- [Plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Roadmap](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Architecture](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md)
- [Implementation](https://github.com/gasyoun/IndologyScholars/blob/main/docs/IMPLEMENTATION_IndologyScholars_sanskrit-community-lenses.md)

_Dr. Mārcis Gasūns_
