_Created: 29-07-2026 · Last updated: 29-07-2026_

# ROADMAP — Sanskrit community lenses, 2026 H2

This roadmap executes the
[decision-locked plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md).
Roerich and Zograf remain the article's primary object. nagari, ORS/VK,
INDOLOGY-L, and BVP are comparison lenses, and ACL Anthology supplies data
organization standards rather than records.

## Outcome

By the end of Wave 1, a fresh task can reproduce one frozen 2005–2025
comparison package plus a separate 2026-partial package, inspect why every row
and label exists, regenerate the figures, audit every quotation in context,
and draft the revised Russian article from a detailed outline without
reopening architectural decisions.

## Wave 0 — preflight and source contract

**Timebox:** 30–60 minutes.

Deliverables:

1. A source-health report for all five lenses.
2. Frozen upstream identifiers, file hashes, counts, coverage dates, access
   state, and rights status.
3. A confirmed output directory that does not overwrite current corpus assets.
4. A BVP crawl manifest with a source-health result, discovered/fetched/parsed
   counts, failures, coverage dates, and an explicit completeness status.

Unblocks:

- prevents silent refresh drift;
- proves which BVP claims may be quantitative;
- fixes the 2025 cutoff before any classification or figure work.

Acceptance:

- every lens has a manifest row;
- 2026 is a separate snapshot;
- no live source or rolling branch is consumed without its resolved version;
- no source cache is accidentally staged for publication.

## Wave 1 — frozen comparison package and article foundation

**Timebox:** one 5–8-hour autonomous execution span.

### Wave 1A — shared schema and codebooks

Deliverables:

- versioned common schema;
- stable corpus/record/annotation/identity/provenance contracts;
- intellectual-content, community-function, and Gumilev codebooks;
- source-native and Renou crosswalk tables with `exact`, `broad`, `narrow`,
  `related`, and `unmapped` relations;
- explicit `unknown` and `not_applicable` semantics.

Unblocks:

- all five adapters;
- deterministic validation;
- corpus-relative metrics without flattening units.

Acceptance:

- schemas load;
- IDs are unique and referentially valid;
- existing `PRES_*`, message, and VK IDs remain unchanged;
- native classifications survive round-trip even when unmapped.

### Wave 1B — adapters for existing four lenses

Deliverables:

- conference adapter from the current database/public exports;
- nagari adapter from its existing SQLite/CSV outputs;
- ORS/VK adapter from its existing SQLite/CSV outputs;
- INDOLOGY-L adapter from versioned IndologyArchiveAtlas feeds;
- one normalized observation table plus relations, names, annotations,
  corpus-specific metrics, and provenance assertions.

Unblocks:

- synchronized activity and topic comparisons;
- verified cross-lens identity candidates;
- quote selection and Gumilev sampling.

Acceptance:

- adapter row counts reconcile with each native source;
- all output records point back to native IDs and source locators;
- no raw source is copied into the common canonical layer;
- unavailable optional feeds fail soft with a manifest warning.

### Wave 1C — BVP public scraper and adapter

Deliverables:

- a BVP source note recording the public Google Groups access model, current
  conversation count, chronology, rules, and extraction constraints;
- a sequential, resumable public scraper with atomic checkpoints, bounded
  retries, adaptive backoff, and persistent failure ledgers;
- a reusable BVP adapter over the frozen scrape manifest;
- raw HTML and attachments kept local and ignored by Git;
- no full-corpus trend claim until enumeration, fetch, and parse coverage
  reconcile without unexplained gaps.

Unblocks:

- India-centred qualitative comparison immediately;
- quantitative BVP trends only when coverage completeness is demonstrated.

Acceptance:

- every included thread/message has a stable native locator;
- quotations are exact and contextual;
- contact details and signatures are excluded;
- coverage status is machine-readable as `complete`, `partial`, or `pilot`,
  with observed denominators and gap counts.

### Wave 1D — annotations, people, and quotations

Deliverables:

- layered assignments for source-native topic, shared content, shared
  community function, Gumilev argument level, and Renou;
- a stratified review sample emphasizing Gumilev G2/G3 and ambiguous
  function classes;
- verified person links plus a fuzzy review queue;
- a quote register with exact text, author, date, thread context, stable URL,
  retrieval date, and omission/redaction notes.

Unblocks:

- Russia–West–India comparisons;
- named examples that remain auditable;
- validity estimates for model/rule-assisted coding.

Acceptance:

- fuzzy identities never auto-merge;
- non-claim items receive Gumilev `not_applicable`;
- quote records contain no unrelated email, telephone, postal, or signature
  data;
- the existing Renou gold-review gate remains visible and is not bypassed.

### Wave 1E — report, figures, snapshot, and Russian outline

Deliverables:

1. comparison validity report;
2. source and coverage table;
3. six core figures:
   - activity by native unit and period;
   - intellectual-content small multiples;
   - community-function profiles;
   - Gumilev distribution on applicable records;
   - platform/lens overlap for verified people;
   - Russia-centred, Western-centred, and India-centred contrast with explicit
     coverage notes;
4. frozen 31-12-2025 data package with SHA-256 manifest;
5. separate 2026-partial package;
6. detailed Russian revision outline keyed to the existing PPV sections;
7. claims ledger marking every proposed claim as supported, provisional,
   expert judgment, or out of scope.

Unblocks:

- Wave 2 prose revision;
- independent checking of article numbers and quotations.

Acceptance:

- every figure regenerates from frozen tables;
- every numerator states its native denominator;
- the BVP completeness status is visible on every affected figure;
- the submitted article remains unchanged;
- the outline keeps Roerich/Zograf central rather than giving all lenses equal
  space.

## Wave 2 — Russian article revision

**Start condition:** Wave 1 passes the
[verification contract](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_IndologyScholars_sanskrit-community-lenses.md).

Deliverables:

- a new `article/ppv_comparative_revision_draft_ru.md`;
- revised abstract, methods, comparative results, discussion, limitations,
  figure captions, and source/quotation notes;
- a response map showing what changed from
  `article/ppv_submission_article.md`;
- updated numerical checker and manuscript export.

Article balance:

- approximately two thirds Roerich/Zograf analysis;
- approximately one third comparative context across the four other social
  lenses;
- ACL standards remain in the data/methods section, not as empirical findings.

Wave 2 must not begin from audit chat or mutable outputs. It reads only the
frozen package, validity report, claims ledger, and approved outline.

## Wave 3 — hardening and optional publication

Deliverables:

- second-reader quotation/context audit;
- adjudicated Gumilev and function samples;
- expanded BVP crawl and pagination recovery, if public enumeration can be
  demonstrated safely;
- article-ready supplement and data dictionary;
- DOI/release/website changes only after separate explicit authorization.

This wave is optional for the local analysis but required before a public data
release that contains named quotations or person-level cross-platform links.

## Non-goals

- A census of all Sanskrit scholarship in Russia, the West, or India.
- Equal weighting of the five lenses.
- Migration claims based only on coincident platform activity.
- A single raw activity count across talks, messages, threads, and posts.
- Automatic nationality inference.
- Automatic fuzzy identity merges.
- Full-text NLP of INDOLOGY-L if the canonical Atlas release remains
  metadata-first.
- Republishing mailing-list or VK attachments.
- Treating ACL Anthology as a sixth corpus, publication bridge, bibliography
  mirror, or PDF source.
- Replacing local taxonomies or Renou with one universal classifier.
- Editing or overwriting the submitted PPV article during Wave 1.

## Dependency map

```text
source manifests
  → shared schema and codebooks
    → four existing adapters
    → BVP checkpointed public scraper and adapter
      → annotations / identities / quote register
        → validity report and figures
          → frozen package and Russian outline
            → article revision
```

## Handoff status

The plan is executable, but no H-number is minted because the approved
`/handoff-mint` tool pushes immediately and the author explicitly prohibited
pushes in this span. Launch with:

```text
Read C:\Users\user\Documents\GitHub\IndologyScholars-ask-community-lenses\docs\PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md and execute it.
```

_Dr. Mārcis Gasūns_
