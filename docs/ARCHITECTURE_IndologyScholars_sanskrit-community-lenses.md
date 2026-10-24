_Created: 29-07-2026 · Last updated: 29-07-2026_

# ARCHITECTURE — Sanskrit community lenses

This architecture implements the
[decision-locked plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md).
It treats the five corpora as parallel observational lenses over related but
non-identical communities. Native records remain authoritative; the shared
layer consists of links, assertions, crosswalks, and corpus-relative measures.

## Architectural principles

1. **Preserve native units.** A presentation is not a message; a thread is not
   a VK post; a view is not participation.
2. **Preserve native identity.** Existing `PRES_*`, `Message-ID`, Atlas message
   IDs, Google Groups conversation/message IDs, and VK owner/post IDs remain
   canonical within their sources.
3. **Never put mutable interpretation into an ID.** Titles, person names,
   topics, Gumilev levels, and affiliations may change without changing the
   record ID.
4. **Separate attestation from resolution.** “Name as printed/sent” is source
   data; linking it to one cross-corpus person is a reviewed assertion.
5. **Separate source from derived data.** Adapters read but do not rewrite
   native stores. Common tables and figures are deterministic derived products.
6. **Layer, do not replace.** Local classifications, shared content, shared
   function, Gumilev, meso codes, and Renou coexist with explicit provenance.
7. **Pin everything.** Every output knows its source snapshot, pipeline commit,
   codebook version, model/ruleset version, and content hashes.
8. **Compare rates within lenses.** Cross-lens figures use proportions,
   distributions, change, or standardized rates with named denominators.

These principles adapt ACL Anthology's stable-ID, record-hierarchy,
attested-name, canonical-versus-derived, validation, and revision practices.
They do not copy ACL's publication ID grammar or file formats.

## Component boundaries

```text
native authoritative sources
  conferences.db / public exports
  nagari SQLite + mbox-derived outputs
  vk-ors SQLite + API/XLSX-derived outputs
  IndologyArchiveAtlas versioned feeds
  BVP authorized snapshot or public pilot
          │ read only
          ▼
community_lenses adapters
          │ canonical common assertions
          ▼
analytics_output/community_lenses/comparison.db
  + deterministic CSV/JSON exports
          │
          ├── review queues
          ├── validity report
          ├── quote register
          ├── figures
          └── frozen 2025 / partial 2026 packages
```

### Owning boundaries

| Component | Owner | Contract |
|---|---|---|
| Roerich/Zograf canonical records | IndologyScholars conference pipeline | Read existing IDs and metadata; no adapter-side correction |
| nagari messages and attachments | `nagari/nagari_group_archive/` | Read normalized DB/exports; rights status travels with records |
| ORS/VK posts and engagement | `vk-ors/vk_ors_archive/` | Read native post IDs and current metrics; do not re-fetch implicitly |
| INDOLOGY-L | IndologyArchiveAtlas | Consume a new compact comparison feed; never copy or edit the archive |
| BVP | `bvp/` source note/cache plus adapter | Comprehensive analytics require demonstrable coverage; pilot otherwise |
| Shared comparison | new `community_lenses/` package | Own schema, crosswalks, assertions, metrics, snapshots, and reports |
| Article | `article/` | Consume only frozen outputs; never become a source of data truth |

## Planned file layout

```text
community_lenses/
  __init__.py
  cli.py
  schema.py
  ids.py
  manifests.py
  taxonomy.py
  classify.py
  identity.py
  quotes.py
  metrics.py
  figures.py
  report.py
  snapshot.py
  adapters/
    __init__.py
    conferences.py
    nagari.py
    vk_ors.py
    indology_atlas.py
    bvp.py
  codebooks/
    intellectual_content.csv
    community_function.csv
    argument_level.csv
    taxonomy_crosswalk.csv
  schemas/
    source_manifest.schema.json
    comparison_record.schema.json
    annotation.schema.json
    quote.schema.json
bvp/
  README.md
  data/
    raw/                 # gitignored, if a lawful snapshot exists
    processed/           # compact derived outputs only
analytics_output/community_lenses/
  comparison.db
  tables/
  review/
  reports/
  figures/
article/comparison_snapshots/
  through-2025/
  partial-2026/
article/
  ppv_comparative_revision_outline_ru.md
tests/
  test_community_lenses_schema.py
  test_community_lenses_ids.py
  test_community_lenses_adapters.py
  test_community_lenses_taxonomy.py
  test_community_lenses_quotes.py
  test_community_lenses_snapshot.py
```

Raw source caches remain ignored. Compact normalized metadata, codebooks,
schemas, validation reports, and frozen derived packages may be versioned only
after separate delivery authorization.

## Common relational model

### `corpus`

| Field | Meaning |
|---|---|
| `corpus_id` | `conferences`, `nagari`, `vk_ors`, `indology_l`, or `bvp` |
| `title` | human-readable title |
| `medium` | conference, mailing list, Google Group, or social wall |
| `forum_orientation` | Russia-centred, Western-centred international, or India-centred |
| `native_unit` | presentation, message, thread, post, or event |
| `canonical_url` | source homepage |
| `rights_status` | source-specific rights/access statement |

`forum_orientation` describes the selected venue, not every contributor's
nationality. The author's BVP/INDOLOGY premises are stored as documented
selection assertions with `method=expert_judgment`, not as inferred person
attributes.

### `source_snapshot`

| Field | Meaning |
|---|---|
| `snapshot_id` | stable snapshot label |
| `corpus_id` | source lens |
| `coverage_start`, `coverage_end` | observed temporal coverage |
| `cutoff_date` | `2025-12-31` or a 2026 partial date |
| `coverage_status` | complete, partial, pilot, or unavailable |
| `source_version` | git SHA, export ID, file hash, or API retrieval token |
| `acquired_at` | retrieval timestamp |
| `source_sha256` | checksum of the consumed immutable input |
| `pipeline_commit` | code version used |
| `schema_version`, `codebook_version` | interpretation versions |
| `rights_basis` | public page, local archive, export, or upstream feed |

### `container`

A container preserves native grouping without forcing false symmetry.

| Lens | Container |
|---|---|
| conferences | annual event, programme session, or proceedings block |
| nagari | thread |
| ORS/VK | wall or year shard; a post remains a record |
| INDOLOGY-L | thread |
| BVP | thread/conversation |

Fields: `container_id`, `corpus_id`, `source_snapshot_id`,
`parent_container_id`, `container_type`, `source_native_id`, `title`,
`date_from`, `date_to`, and `source_url`.

### `record`

| Field | Meaning |
|---|---|
| `record_id` | namespaced shared key: `<corpus_id>:<source_record_id>` |
| `source_record_id` | untouched native stable ID |
| `container_id` | native grouping |
| `record_type` | presentation, message, post, comment, or announcement |
| `title_or_subject` | attested title/subject |
| `body_locator` | pointer to native text, not necessarily copied body |
| `created_at`, `language` | source values |
| `canonical_url` | stable source link where available |
| `content_sha256` | integrity hash, never the primary ID when a native ID exists |
| `status` | active, corrected, withdrawn, deleted, redacted, or unavailable |
| `is_partial_2026` | hard temporal separation |

Fallback identity for mail without a stable archive ID is a base32 SHA-256 of
the normalized RFC `Message-ID`. A content hash is used only when no immutable
native identifier exists, and the fallback method is recorded.

### `record_name`

Fields: `record_id`, `ordinal`, `role`, `name_as_source`,
`affiliation_as_source`, `source_account_id`, and nullable `person_id`.

`name_as_source` is never overwritten by normalized or transliterated forms.
Item-level affiliation is time-bound evidence, not a permanent person field.

### `record_relation`

Controlled predicates:

- `reply_to`
- `thread_member`
- `comment_on`
- `attachment_of`
- `revision_of`
- `duplicate_of`
- `cross_post_of`
- `derived_from`
- `presented_at`
- `participated_in`

Each row carries `subject_record_id`, `predicate`, `object_record_id`, and
`evidence_locator`.

### Person authority and review

`person` stores `person_id`, canonical display name, optional ORCID/Wikidata,
review status, reviewer, and review date.

`person_name` stores script, transliteration scheme, preferred status, and
evidence record. Names are not decomposed into mandatory first/last fields.

`person_match_assertion` stores source name/record, candidate person, method,
score, evidence, and status. Match priority:

1. explicit existing person ID;
2. ORCID or verified authority ID;
3. exact source identity plus manually verified alias;
4. exact name with compatible time-bound affiliation;
5. fuzzy/transliteration candidate → review only.

No threshold turns fuzzy candidates into automatic matches.

### Classification and crosswalks

`taxonomy_scheme` records every independent scheme:

- source-native conference L1/L2/meso;
- nagari native topics;
- ORS/VK native topics/hashtags;
- INDOLOGY-L Atlas topics/functions;
- BVP native labels, if present;
- shared intellectual content;
- shared community function;
- Gumilev argument level;
- Renou state and register.

`classification_assignment` fields:

`record_id`, `scheme_id`, `label_id`, `value`, `evidence_span`,
`method`, `method_version`, `confidence`, `review_status`, `reviewer`, and
`assigned_at`.

`taxonomy_crosswalk` is many-to-many:

`source_scheme`, `source_label`, `target_scheme`, `target_label`,
`mapping_relation`, `rationale`, `evidence_count`, `review_status`, and
`version`.

Allowed mapping relations are `exact`, `broad`, `narrow`, `related`, and
`unmapped`. Crosswalking never deletes the source assignment.

### Shared intellectual-content axis

The initial controlled labels are multi-valued:

- grammar and linguistics;
- texts and philology;
- literature and poetics;
- religion and philosophy;
- history and culture;
- manuscripts, epigraphy, and material culture;
- digital and computational work;
- teaching and learning resources;
- institutions and field history;
- other;
- unknown.

The codebook supplies definitions, inclusions, exclusions, examples from each
lens, version, and parent/child relationships. It may be refined through the
review sample without changing source-native labels.

### Shared community-function axis

The initial controlled labels are also multi-valued:

- research presentation or exposition;
- interpretation and analysis;
- identification or textual help;
- bibliographic request;
- resource sharing;
- teaching and learning;
- scholarly debate;
- event announcement;
- publication announcement or review;
- jobs, grants, or training;
- curation and public outreach;
- commemoration or obituary;
- administration or moderation;
- social/ritual exchange;
- other;
- unknown.

The function axis describes what the item does in its medium. It is not a
quality score.

### Gumilev argument scale

The canonical field is `argument_level`; `gumilyov_level` remains a legacy
alias only in existing exports.

- G1: individual text, author, source, term, object, or local problem;
- G2: explicit tradition, school, genre, large class, or durable historical
  line;
- G3: broad interregional, civilizational, comparative, or methodological
  synthesis;
- `not_applicable`: the item does not advance an identifiable scholarly frame;
- `unknown`: the item may be applicable but evidence is insufficient.

Announcements, bare resource links, greetings, and bibliography-only requests
must not be forced into G1. Because the existing G2/G3 boundary is the weak
reliability point, all G3 and a stratified G2 sample receive review.

### Provenance and corrections

`provenance_assertion` records:

`assertion_id`, `entity_type`, `entity_id`, `field_name`, `asserted_value`,
`source_record_id`, `source_locator`, `acquired_at`, `method`,
`tool_or_model_version`, `confidence`, and `review_status`.

`correction` records:

`correction_id`, `entity_id`, `field_name`, `old_value`, `proposed_value`,
`evidence_locator`, `decision`, `reviewer`, `decided_at`, and
`applied_version`.

Corrections are append-only assertions. Source-native records are not silently
rewritten.

## Adapter contract

Every adapter implements:

```python
class LensAdapter:
    corpus_id: str

    def source_manifest(self) -> SourceManifest: ...
    def iter_containers(self) -> Iterable[Container]: ...
    def iter_records(self) -> Iterable[Record]: ...
    def iter_names(self) -> Iterable[RecordName]: ...
    def iter_relations(self) -> Iterable[RecordRelation]: ...
    def iter_native_annotations(self) -> Iterable[Annotation]: ...
    def reconcile(self) -> ReconciliationReport: ...
```

Adapters are pure readers over an explicitly supplied snapshot. They may not
fetch a rolling source, mutate a native database, or trigger a model call.
Fetch/acquisition is a separate, explicit preflight command.

## Lens-specific mappings

### Roerich and Zograf

- Two series inside `corpus_id=conferences`.
- Annual meetings are explicit events.
- Presentation remains the record and existing `PRES_*` remains its
  `source_record_id`.
- Printed names/affiliations stay attested; normalized scholars link through
  existing `public_ids.json`, `authority_ids.json`, and curation tables.
- Existing theme, meso, `argument_level`, and Renou assignments are imported
  with their current method and reliability status.

### nagari

- Thread is the container; message is the record; attachment is an asset.
- Preserve `Message-ID`, `In-Reply-To`, `References`, timestamp/time zone,
  subject, sender display string, raw hash, and rights status.
- Read the current SQLite database and processed CSVs; do not reimplement mbox
  parsing, FTS, topic rules, or Markdown export.
- Exact quotations may identify authors, but unrelated contact/signature data
  never enters the quote register.

### ORS/VK

- The wall is a persistent container; post is the record; native owner/post ID
  is stable.
- Preserve timestamp, source URL, native engagement counts, edit/deletion
  status, hashtags, and attachment metadata.
- Engagement is reported only with its available denominator. Views absent in
  early years remain missing, not zero.
- The corpus has one publishing account; it does not support author-network
  claims without separately acquired comment data.

### INDOLOGY-L

- IndologyArchiveAtlas remains canonical.
- Extend its compact feed beyond Renou with versioned record, topic/function,
  aggregate, and optional identity-candidate tables.
- Thread is container; message is record; Atlas profiles and maps remain
  derived.
- `source_snapshot.source_version` pins the Atlas commit and every feed file
  hash.
- The forum is analyzed as Western-centred international by explicit study
  framing, while actual country/affiliation composition remains measured
  evidence.

### BVP

- Series is BVP; Google Groups conversation is container; message is record.
- Use native conversation/message path identifiers where stable; preserve
  source URL, timestamp, author display, subject/body, and reply chain.
- Acquisition uses public pages sequentially, without login. The scraper ports
  the Wisdomlib estate's generic hardening pattern into this repository:
  atomic state writes, skip-good resume, one bounded retry with jitter,
  adaptive pause-on-error, and persistent success/failure ledgers. It does not
  import `D:\Tools\wisdomlib-scrape` as a runtime dependency.
- Raw HTML and attachments live under ignored `bvp/data/raw/`. Canonical
  metadata and hashes are derived from a frozen manifest; acquisition never
  writes directly into article outputs.
- Coverage has distinct `listed`, `fetched`, and `parsed` stages. Set
  `coverage_status=complete` only when the public listing denominator,
  discovered conversation IDs, fetched conversations, parsed records, and
  explained exclusions reconcile. Otherwise use `partial` or `pilot` and
  suppress annual trend, person-share, or topic-share population claims.
- The forum is the principal India-centred hub selected by author expert
  judgment. That judgment is reported, not disguised as measured coverage.

## Quote register

Fields:

`quote_id`, `record_id`, `person_id`, `author_display`, `quote_verbatim`,
`omissions_marked`, `source_url`, `source_date`, `retrieved_at`,
`thread_subject`, `context_note`, `context_before_sha256`,
`context_after_sha256`, `public_access_checked_at`, `contact_data_removed`,
`rights_review_status`, and `article_claim_id`.

Rules:

- quotations are exact;
- ellipses or bracketed omissions are explicit;
- quoted material is short and necessary for the analytical claim;
- named behaviour is described only from observable source actions;
- email, telephone, address, and signature removal does not alter the quoted
  claim;
- deleted, unstable, or inaccessible context causes omission, not paraphrase.

The existing nagari publication policy remains binding: a quote may be selected
and registered, but it is non-exportable until the source-specific owner/rights
gate is recorded as approved. The user's preference for real attributed quotes
sets the article method; it does not silently erase an existing corpus-rights
gate.

## Metric contract

Every metric row carries:

`metric_id`, `corpus_id`, `period`, `numerator`, `denominator`,
`denominator_unit`, `value`, `missingness_note`, `source_snapshot_id`, and
`method_version`.

Permitted comparisons include:

- within-corpus topic/function share;
- within-corpus change across harmonized periods;
- messages per thread;
- repeat presentations per scholar;
- posts per year;
- engagement per available view;
- verified cross-lens participation share.

Forbidden headline comparisons include raw “activity” totals across talks,
messages, threads, and posts.

## Period contract

- pre-1990: narrative historical background only;
- 1990–2004: digital prehistory, mainly INDOLOGY-L;
- 2005–2010;
- 2011–2017;
- 2018–2025;
- 2026 partial.

The main inferential window is 2005–2025. Period boundaries are centralized in
one codebook and never reimplemented per adapter.

## Build-versus-reuse verdict

| Piece | Verdict |
|---|---|
| Conference database, stable IDs, classifications, snapshots | Reuse |
| nagari mbox parser, SQLite, topics, exports, rights work | Reuse |
| ORS/VK ingestion, metrics, topics, attachments | Reuse |
| INDOLOGY-L canonical archive and Renou feed | Reuse and extend feed |
| Renou classifier | Reuse with existing gold-review gate |
| Gumilev definitions and conference labels | Reuse; extend only with new validation |
| Common schema, function taxonomy, crosswalks, identities, quote register | Build |
| BVP source note and adapter | Build; comprehensive acquisition is a spike |
| ACL data or PDFs | Do not ingest |
| ACL organization standards | Adapt with explicit local differences |

## Related planning layers

- [Plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Roadmap](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Implementation](https://github.com/gasyoun/IndologyScholars/blob/main/docs/IMPLEMENTATION_IndologyScholars_sanskrit-community-lenses.md)
- [Verification](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_IndologyScholars_sanskrit-community-lenses.md)

_Dr. Mārcis Gasūns_
