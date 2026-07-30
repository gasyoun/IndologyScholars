_Created: 30-07-2026 · Last updated: 30-07-2026_

# Metadoc — ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md

Companion record for the
[roadmap](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_IndologyScholars_sanskrit-community-lenses_2026H2.md).
Records why it exists, how it was produced, and how it should be maintained;
does not duplicate the roadmap itself.

## Subject

- **Purpose:** sequence Wave 0–N of the five-lens comparison build (schema →
  manifests/feed → four adapters → BVP → crosswalk → identity/quotes → figures
  → article) so later handoffs (H1893–H1898+) execute against a fixed order
  instead of re-deriving it.
- **Audience:** the executing handoff worker each wave, and later maintainers
  of the comparison package.
- **Contract:** dated plain Markdown, full blob URLs, wave-by-wave deliverables
  and timeboxes.
- **Status:** active, local, uncommitted this pass (H1893 landed Wave 1A only).

## Provenance

- Authored alongside the
  [plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md)
  during the H1893 session (30-07-2026, Sonnet 5 `claude-sonnet-5`), which
  found the plan referencing a roadmap that did not yet exist and produced it
  as directly-related architecture documentation within H1893's scope.

## Ranked improvement backlog

| # | Improvement | Why | Status |
|---:|---|---|---|
| 1 | Replace Wave 1A's schema-only scope note with H1894/H1895 outputs once landed | Roadmap currently describes Wave 1 as a single block; H1893 only shipped the schema/codebook slice | Open — next session touching this roadmap should split/tick Wave 1 sub-items |
| 2 | Cross-check wave timeboxes against actual H1893 duration | Timeboxes were estimated, not measured | Open |

## Known limitations

- Not yet exercised past Wave 1A — later wave descriptions are still
  aspirational and may need revision once H1894/H1895 land.
- Local/uncommitted as of H1893; no public blob until a later session commits it.

## Intended use and known misuse

Use to sequence remaining community-lenses waves without re-deriving the
Wave 0→N order or re-opening the 25 rulings already locked in the sibling plan.
Do not treat wave numbers here as already-shipped status — check `.ai_state.md`
Completed entries and the handoffs registry for what has actually landed.

## Maintenance and sunset

Owned by whoever executes the next community-lenses wave. Sunsets when the
five-lens comparison package and Russian article revision (roadmap's stated
outcome) ship with their own verification record.

## Related documents

- [Plan](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.md)
  (+ its [metadoc](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_IndologyScholars_sanskrit-community-lenses_2026H2.meta.md))
- [Architecture](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md)
- [Implementation](https://github.com/gasyoun/IndologyScholars/blob/main/docs/IMPLEMENTATION_IndologyScholars_sanskrit-community-lenses.md)
- [Verification](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_IndologyScholars_sanskrit-community-lenses.md)
- [ACL standards adaptation](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ACL_STANDARDS_ADAPTATION_IndologyScholars_community-lenses.md)

## Revision history

| Date | Event | Author/model |
|---|---|---|
| 30-07-2026 | Metadoc created (backfill; roadmap authored 29-07-2026) | Dr. Mārcis Gasūns / Sonnet 5 (`claude-sonnet-5`) |

_Dr. Mārcis Gasūns_
