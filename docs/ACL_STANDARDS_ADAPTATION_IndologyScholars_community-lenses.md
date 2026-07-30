_Created: 30-07-2026 · Last updated: 30-07-2026_

# ACL Anthology standards — what H1893 adopted and what it rejected

[Community-lenses architecture](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md)
names the ACL Anthology as the model for how a large, heterogeneous,
multi-source scholarly corpus can stay internally consistent over time. H1893
implements the `community_lenses/` schema and codebook contracts against that
model. This note is the explicit adopted/rejected ledger required by the
handoff so a later wave does not have to re-derive why each choice was made.

## Adopted

| ACL Anthology practice | How `community_lenses/` adapts it |
|---|---|
| Stable, permanent record IDs that never encode mutable metadata | `record_id = "<corpus_id>:<source_record_id>"` (`community_lenses/ids.py`); IDs never embed a title, name, topic, or classification (`ARCHITECTURE.md` §"record"). |
| Explicit record hierarchy (volume → paper) | `container` → `record`, generalized per lens (session/thread/wall/thread/thread) instead of one fixed hierarchy shape. |
| Canonical vs. derived separation (XML source vs. generated site) | Native adapters (later waves) are read-only; `community_lenses/` tables are an explicit derived layer with `source_snapshot` provenance on every row. |
| Attested-name handling (author string as printed, not force-normalized) | `record_name.name_as_source` is never overwritten by a normalized/transliterated form; no mandatory first/last decomposition (`ARCHITECTURE.md` §"record_name"). |
| Structured provenance/versioning on every derived artifact | `source_snapshot` + `provenance_assertion` capture source version, retrieval time, hash, and schema/codebook version per `schema.py`. |
| Schema validation before publication | `schema.validate_schema` (FK/integrity check) plus `build.validate_build` (ID/reference integrity, controlled values, native/derived mixing, rights defaults) — see `tests/test_community_lenses_*`. |
| Deterministic serialization for reproducible builds | `build.canonical_json`/`dump_database` sort rows and keys so an unchanged rebuild is byte-identical (`tests/test_community_lenses_fixtures.py::test_deterministic_rebuild_produces_byte_identical_dump`). |
| Pinned, versioned snapshots rather than a rolling live corpus | `source_snapshot.source_version`/`source_sha256`/`cutoff_date`/`coverage_status`; `validate_no_mixed_snapshot` fails closed on any blended snapshot. |

## Rejected

| ACL Anthology practice | Why H1893 does not copy it |
|---|---|
| ACL's publication-shaped ID grammar (venue/year/paper-number) | Presentations, messages, threads, and posts are not publications; forcing a publication ID grammar onto them would fabricate false comparability across native units that the architecture explicitly forbids (`ARCHITECTURE.md` §"Architectural principles" #1, #8). |
| ACL's XML/BibTeX file formats | The repository's existing pipeline is Python/SQLite/CSV; `ARCHITECTURE.md` states XML/YAML is not required, and introducing a second serialization format here would duplicate `pipeline/schema.py`'s conventions for no benefit. |
| Ingesting ACL's own data or PDFs | Out of scope entirely — ACL is a design reference, not a data source (`ARCHITECTURE.md` §"Build-versus-reuse verdict": "ACL data or PDFs: Do not ingest"). |
| One universal record schema shared verbatim across every venue type | ACL's own model is paper-centric; this corpus spans a conference programme, two mailing lists, a social-media wall, and (pending) a forum, so `container_type`/`record_type`/`native_unit` stay lens-specific rather than flattened into one ACL-style paper record. |
| Single global classification taxonomy replacing venue-native categories | ACL does not need to reconcile five independently classified corpora; `taxonomy_scheme` keeps every native scheme first-class and routes cross-lens comparison only through an explicitly typed, reviewable `taxonomy_crosswalk` (`ARCHITECTURE.md` §"Classification and crosswalks"). |

## Boundary this note does not cross

This ledger documents the schema/codebook-level adaptation only. It does not
adjudicate any specific crosswalk mapping, assign any classification, merge
any cross-lens identity, or select any quotation — those decisions belong to
H1894/H1895 and are explicitly out of H1893's scope (see the handoff's
"Boundaries and guardrails").

## Related planning layers

- [Plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Roadmap](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md)
- [Architecture](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md)
- [Implementation](https://github.com/gasyoun/IndologyScholars/blob/main/docs/IMPLEMENTATION_IndologyScholars_sanskrit-community-lenses.md)
- [Verification](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_IndologyScholars_sanskrit-community-lenses.md)

_Dr. Mārcis Gasūns_
