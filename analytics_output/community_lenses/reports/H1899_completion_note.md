# H1899 — completion note: validity report, figures, frozen snapshots, Russian outline

_Created: 06-08-2026 · Last updated: 06-08-2026_

Executor: Opus 5 (`claude-opus-5`), 2026-08-06, worktree
`IndologyScholars-h1899-34220`, branch `h1899-report-figures-snapshot-34220` off
`origin/codex/community-lenses-ask-plan`. **Local-only per the handoff fence: nothing
committed, pushed, published or submitted in this repository.**

## Generated paths

| Path | What it is |
|---|---|
| `community_lenses/metrics.py` | denominator-aware metric tables + the V9 validator |
| `community_lenses/figures.py` | the six core figures (hand-written SVG) + caption validator |
| `community_lenses/report.py` | `comparison_validity.md` + `claims_ledger.csv` + claim validator |
| `community_lenses/snapshot.py` | freeze / verify / compare for the two frozen packages |
| `community_lenses/cli.py` | 17 verification subcommands (V1–V11) |
| `analytics_output/community_lenses/tables/*.csv` | 7 frozen metric tables (58 rows) |
| `analytics_output/community_lenses/figures/*.svg` | `fig1`…`fig6` + `captions.md` / `captions.json` |
| `analytics_output/community_lenses/reports/comparison_validity.md` | the validity report (V1–V11 evidence classes) |
| `analytics_output/community_lenses/reports/claims_ledger.csv` | 14 claims, every one evidence-linked |
| `article/comparison_snapshots/through-2025/` | frozen package, 38 files, 27 270 records |
| `article/comparison_snapshots/partial-2026/` | frozen package, 38 files, 427 records |
| `article/ppv_comparative_revision_outline_ru.md` | the Russian revision outline for H1900 |
| `tests/test_community_lenses_metrics.py` · `tests/test_community_lenses_snapshot.py` | 40 new tests |

One compatibility fix outside the owned set: `community_lenses/adapters/nagari.py` —
the canonical `nagari/data/nagari.db` was not on the adapter's candidate path list, so
the lens silently degraded to `unavailable` while a real 193 MB database sat on disk.

## Exact test and gate results

| Command | Result |
|---|---|
| `pytest -q tests/test_community_lenses_metrics.py tests/test_community_lenses_snapshot.py` | **40 passed** |
| `pytest -q` (repo-wide, excluding the two source-blocked adapter files) | **347 passed** |
| `pytest -q tests/test_community_lenses_adapters.py` | **2 failed** (nagari duplicate Message-IDs, IndologyScholars#169 — see below) |
| `pytest -q tests/test_bvp_adapter.py` | **1 failed** — BVP source absent on this machine (pre-existing, H1896 queued) |
| `cli validate-manifests` (V1) · `validate-schema` / `roundtrip-check` (V2) · `reconcile` (V3) | PASSED |
| `cli validate-cutoff` (V4) | PASSED — through-2025 27 270 · partial-2026 427 · undated 2 (in neither) |
| `cli crosswalk-report` (V5) · `identity-report` (V7) · `validate-quotes` (V8) | PASSED |
| `cli validate-metrics` (V9) · `figures` (V10) · `validate-claims` (V10) | PASSED |
| `cli verify-snapshot` ×2 · `rebuild-check` ×2 (V11) | PASSED — content-identical except `created_at` |
| `python validate_publication.py` (V12) · `git diff --check` | PASSED / clean |

The two nagari adapter failures are the **known** IndologyScholars#169 defect: the raw
mbox carries 2 duplicated Message-IDs and `build.populate_corpus` correctly refuses
them. H1898 hid the failure by deleting its local db copy, which also degraded the lens
to a silent false `unavailable` for every later session. The path fix keeps the lens
usable and makes the defect loud; the durable repair is dedupe at extraction inside the
nagari adapter (upstream H1895 / #169 scope), mirroring what
`identity.dedupe_fixture` already does downstream.

## Suppressed and provisional claims

- **Suppressed entirely (`out_of_scope`)**: cross-lens Gumilev distribution (pilot
  unreviewed, V6 threshold evidence absent); any Russia–West–India magnitude comparison
  (INDOLOGY-L blocked on H1894, BVP blocked on H1896 — gaps, not zeros); any Renou
  comparison (gold-review gate binding).
- **Provisional**: conference and nagari shared-axis content/function profiles — the
  H1897 crosswalk is a pending proposal, native labels remain the accepted evidence.
- **Expert judgment (no p-value, no representativeness)**: forum orientation
  (Russia/West/India-centred); the refusal to read coincident cross-platform activity
  as community migration.
- **Rights-gated**: 3 registered quotes, **0 exportable** — 2 nagari rows forced
  `non_exportable`, 1 VK row `pending_review`. Cross-lens person links (7 persons,
  641 mentions) derive from a closed group and stay unpublished.

## Snapshot hashes

| Package | Files | Records | Manifest roll-up SHA-256 (first 16) |
|---|---:|---:|---|
| `through-2025` | 38 | 27 270 | `e4f100f48f7c947c` |
| `partial-2026` | 38 | 427 | `1a5e15454fd52f52` |

Per-file SHA-256 lives in each package's `manifest.json` / `manifest.txt`. Both packages
re-froze into a temporary destination byte-identically except the documented `created_at`
field; an existing destination is refused, never overwritten (R13).

## Landing split (06-08-2026) — what became public and what did not

A human authorised landing this work on `codex/community-lenses-ask-plan`. Because
`IndologyScholars` is a public repository and the nagari rights gate is unresolved, the
payload was split rather than pushed whole:

**Landed (aggregate-only, no personal data, no closed-group text):** the five new
modules + the nagari path fix, the four test files and their explicitly synthetic
fixture, the 7 metric tables, the 6 figures and captions, `comparison_validity.md`,
`claims_ledger.csv`, this note, and the Russian revision outline.

**Withheld — stays local until the closed-group rights gate is approved:**

| Withheld | Why |
|---|---|
| `article/comparison_snapshots/**` | `records.csv` carries 18 572 nagari message-IDs with timestamps, `access_class=restricted` — publishing it exposes closed-group traffic metadata |
| `curation/community_person_links.csv` · `curation/community_quotes.csv` | named persons, masked accounts and verbatim closed-group quotes (H1898's own instruction) |
| `analytics_output/community_lenses/reports/identity_quote_evidence.md` | names the 7 accepted persons and their accounts |

Consequence, stated plainly: the *generator* and its manifests are public and any
authorised holder of the sources can rebuild both packages byte-identically, but the
frozen packages themselves are **not** published and remain worktree-resident. That
keeps the H1899 data-loss exposure open for those three items specifically — see
`.ai_state.md`.

## First section H1900 should revise

**§2 «Корпус и метод»** — it is the only section whose current text is *wrong* rather
than merely incomplete once five lenses exist: it needs the five-lens source table, the
per-lens denominator rule, the 2026-partial separation rule, and the sentence that
Russia/West/India name **forum orientation**, not participant nationality. Every later
section depends on those definitions. Evidence to hand: `coverage.*` rows in
`lens_source_coverage.csv`, `activity.*.2026-partial`, and
`fig1_activity_by_period.svg`.

_Dr. Mārcis Gasūns_
