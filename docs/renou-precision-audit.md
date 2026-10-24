# Renou classifier — precision audit

_Created: 10-07-2026 · Last updated: 19-07-2026_

The Renou état/register layer assigns Louis Renou's periodization of Sanskrit
literature to two independent corpora in this repository. Both layers are
metadata-first: they match **titles and subject lines** with regular expressions,
never full texts. This document records what that method actually costs, measured
on 10-07-2026, before any claim resting on the layer is published.

Measured by Opus 4.8 (`claude-opus-4-8`) against
[`generate_renou_layer.py`](https://github.com/gasyoun/IndologyScholars/blob/main/generate_renou_layer.py)
and the tables it emits. The scheme itself is defined in
[`RENOU.md`](https://github.com/gasyoun/SanskritLexicography/blob/master/RussianTranslation/RENOU.md),
which both layers cite as `source_url`.

---

## 1. What the two layers cover

| Layer | Unit | Corpus | Matched | Coverage |
| --- | --- | ---: | ---: | ---: |
| Conference | presentation | 1,362 presentations (Zograf + Roerich Readings, 2004–2026) | 781 presentations, 190 scholars | **57.3%** |
| Archive | message | 62,115 messages (INDOLOGY-L, 1990–2026) | 6,217 messages | **10.0%** |
| Archive | thread | 24,034 threads | 3,307 threads | **13.8%** |

Sources:
[`analytics_output/renou_coverage.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/renou_coverage.csv),
[`Indology/data/processed/renou_coverage.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/data/processed/renou_coverage.csv).

The 57.3% / 10.0% gap is **not** evidence that Russian conference papers engage
Renou's categories more than the international mailing list does. Russian abstract
titles conventionally name the genre or text; English list subject lines
(`Re: query`, `job posting`, `font problem`) frequently name nothing at all. The
gap measures title-writing convention at least as much as scholarly attention.

## 2. The defect: unanchored Cyrillic substrings

The register patterns interleave word-anchored Latin alternatives (`\b(bhasya|…)\b`)
with **unanchored Cyrillic stems** (`|бхашь|коммент|тика|вритт`). Latin alternatives
respect word boundaries; the Cyrillic ones do not. Any Russian word merely
*containing* the stem matches.

The anchoring is inconsistent in both directions: `пали\b` in `state:V` does carry
a trailing boundary, and a few Latin tokens (`jaina`, `vyākaraṇa`) sit unanchored
inside the Cyrillic run. Neither affects the argument below, but both indicate the
table was never audited as a whole.

The worst case is `тика` — intended as *ṭīkā*, a gloss — in the `bhasya` register:

| Matched term | Rows in `register:bhasya` | Share |
| --- | ---: | ---: |
| `тика` | 85 | 73% |
| `коммент` / `Коммент` | 13 | 11% |
| `Шанкар` / `шанкар` | 8 | 7% |
| `бхашь` | 7 | 6% |
| `вритт` | 2 | 2% |
| `Commentary` | 1 | 1% |

Of those 85 rows, 40 fire inside the **title** and 45 inside a **subject tag** —
the defect is present on both matching surfaces. Every one inspected is a false
positive. In titles it is swallowed by Эро·**тика**, прак·**тика**,
фоне·**тика**, семан·**тика**, грамма·**тика**, проблема·**тика**; in tags by
поэ·**тика** and герменев·**тика**.

The clearest case is «Эротика в Ригведе» — a paper on the **Ṛgveda**, assigned to
the *commentary* register because the Russian word for "erotica" ends in the
letters of *ṭīkā*.

`ману` (Manu) in `register:smrti` behaves identically: it fires inside
Ра·**ману**·джа (Rāmānuja) and **ману**скрипт.

### Mechanically detectable false positives

Counting only matches where **every** occurrence of a Cyrillic matched term sits
mid-word (preceded by another Cyrillic letter):

| Stratum | Matches | Mid-word hits | Share |
| --- | ---: | ---: | ---: |
| `register:bhasya` | 116 | 47 | **41%** |
| `register:smrti` | 13 | 5 | **38%** |
| `register:purana` | 40 | 9 | 22% |
| `register:sutra` | 31 | 6 | 19% |
| `state:I` | 99 | 9 | 9% |
| `register:tantra` | 51 | 4 | 8% |
| `state:III` | 140 | 9 | 6% |
| `state:IV` | 321 | 13 | 4% |
| `state:V` | 187 | 7 | 4% |
| `register:bauddha` | 156 | 5 | 3% |
| `register:kavya` | 297 | 4 | 1% |
| **All conference matches** | **1,706** | **121** | **7.1%** |

**7.1% is a floor, not an estimate.** The detector is deliberately conservative —
it ignores terms hitting at a word start, and it cannot see semantic false
positives at all. `сюжет` ("plot") → `kathā` and `commentary` → `bhāṣya` are
grammatically well-formed matches that are still wrong about what the paper is
about. Only human adjudication bounds the real error.

Two further error sources the table does not capture:

- **Tag-sourced matches (21 of a 150-item sample, 14%).** The matcher reads titles
  *and* subject tags, but only the title is exported. For those rows the evidence
  is invisible in `renou_presentation_matches.csv`.
- **Multi-label collisions.** A single presentation can take a register from one
  word and an état from another, independently wrong. «Сюжет о Трите» — a
  **Ṛgvedic** myth — carries `register:katha` (from *сюжет*) and `state:IV
  Classical` (from a `Poetry` tag). Both are wrong; the correct assignment is
  `state:I Vedic`.

## 3. The finding the layer was built to support

From [`renou_cross_site_state_comparison.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/renou_cross_site_state_comparison.csv):

| État | Archive threads | Conference presentations |
| --- | ---: | ---: |
| I — Vedic | 873 | 99 |
| II — Pāṇinian | 365 | **22** |
| III — Epic | 637 | 140 |
| IV — Classical | **179** | 321 |
| V — Buddhist / Jaina | 529 | 187 |

The two communities look near-inverted on the II/IV axis: the international list is
grammar-heavy and classical-light, the Russian readings the reverse. This is a
genuine, interesting, and *currently unsupportable* claim.

It survives §2 better than the register counts do — états I–V draw mostly on
proper names (Pāṇini, Mahābhārata, Kālidāsa) rather than generic vocabulary, and
their mid-word FP rates are 4–9%, not 41%. But the claim is not publishable until
precision is measured per stratum on **both** layers, because a 4% error on
`state:IV` and a 9% error on `state:I` do not cancel.

## 4. What happens next

A 150-item risk-stratified gold sample was drawn on 10-07-2026 and awaits
adjudication:

- Sheet builder:
  [`tools/build_renou_precision_sheet.py`](https://github.com/gasyoun/IndologyScholars/blob/main/tools/build_renou_precision_sheet.py)
  — seed `20260710`, deterministic, 90 conference + 60 archive items across 19
  strata, oversampling the five high-risk strata (`bhasya`, `katha`, `kavya`,
  `natya`, `state:IV`) to 16 items each.
- Scorer:
  [`tools/score_renou_precision.py`](https://github.com/gasyoun/IndologyScholars/blob/main/tools/score_renou_precision.py)
  — per-stratum precision with Wilson 95% CIs. Because the sample is
  risk-stratified rather than uniform, it reports the pooled figure and the
  **stratum-weighted corpus estimate** separately. Cite the weighted one.

The sheet is a personal working artifact under gitignored `review/`; it is
registered in
[`Uprava/REVIEW_SHEETS_INDEX.md`](https://github.com/gasyoun/Uprava/blob/main/REVIEW_SHEETS_INDEX.md).
Single annotator, no second rater — agreement statistics are therefore not
computable, and the audit reports precision only.

Until that pass lands, per the repository's own standing rule that *an unvalidated
classification is not published as `L2`*:

- Do not publish per-register counts as findings. `bhasya`, `smrti`, `purana` and
  `sutra` are known-defective.
- The état-level cross-site comparison may be shown as **exploratory**, labelled
  unvalidated, with this document linked.
- Fix the rule table before re-running: word-anchor the Cyrillic alternatives
  (`(?<![а-яё])тика(?![а-яё])` or an explicit stem list), and export the matched
  field (`title` vs `tag`) alongside the matched term.

The rule table is currently **duplicated** across three consumers — this repo's
`RULE_ROWS`, [`Indology/data/curation/renou_subject_rules.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/data/curation/renou_subject_rules.csv),
and the état pilot in
[`SanskritLexicography/RussianTranslation`](https://github.com/gasyoun/SanskritLexicography/tree/master/RussianTranslation).
A fix applied to one will not reach the others.

## 5. Fix landed (H459, 19-07-2026)

Measured by Sonnet 5 (`claude-sonnet-5`) against the same
[`generate_renou_layer.py`](https://github.com/gasyoun/IndologyScholars/blob/main/generate_renou_layer.py)
after applying the anchoring fix this document called for. Every bare
Cyrillic alternative in `RULE_ROWS` now carries a `(?<![а-яё])` left
lookbehind so it cannot fire mid-word; `тика` and `ману` — the two stems
responsible for the worst false positives above — additionally carry a
`(?![а-яё])` right lookahead, since both are complete Sanskrit-term
transliterations rather than Russian morphological prefixes (contrast
`коммент`→комментарий or `бхашь`→бхашья, which must stay open on the right
to match their declined continuations, and still do). The stray unanchored
Latin tokens sitting inside Cyrillic runs (`jaina`, `vyākaraṇa`, `kāvya`) were
dropped as pure redundancy with the already-anchored `\b(...)\b` Latin group
each duplicated. `пали` picked up the missing left boundary alongside its
existing trailing one.

**Acceptance test (the same predicate that measured the 7.1% floor in §2):
121 of 1,706 rows failed before the fix; 0 of 1,559 rows fail after.**

### Coverage before / after

| Layer | Metric | Before | After | Δ |
| --- | --- | ---: | ---: | ---: |
| Conference | matched presentations | 781 (57.3%) | 722 (53.0%) | −59 (−4.3 pts) |
| Conference | matched scholars | 190 | 177 | −13 |
| Archive (messages) | matched | 6,217 (10.0%) | 6,217 (10.0%) | 0 |
| Archive (threads) | matched | 3,307 (13.8%) | 3,307 (13.8%) | 0 |

The archive layer is unaffected by design: its rule table
([`Indology/data/curation/renou_subject_rules.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/data/curation/renou_subject_rules.csv))
carries no Cyrillic alternatives at all — INDOLOGY-L subject lines are
overwhelmingly English — so it never had this defect. Re-run and diffed
anyway per H459 scope item 4; both `renou_coverage.csv` outputs are recorded
byte-identical to their pre-fix state.

### Register/state axis, presentations lost (all confirmed false positives)

| Code | Before | After | Δ |
| --- | ---: | ---: | ---: |
| `register:bhasya` | 116 | 25 | −91 (−78%) |
| `register:smrti` | 13 | 4 | −9 (−69%) |
| `register:sutra` | 31 | 25 | −6 (−19%) |
| `register:purana` | 40 | 38 | −2 (−5%) |
| `state:I` | 99 | 92 | −7 (−7%) |
| `state:III` | 140 | 131 | −9 (−6%) |
| `state:IV` | 321 | 315 | −6 (−2%) |
| `state:V` | 187 | 182 | −5 (−3%) |
| `state:II` | 22 | 22 | 0 |

`тика` and `ману` — 85 and an unmeasured handful of the `bhasya`/`smrti`
matches respectively — now fire on **zero** presentations in the current
corpus: every occurrence in the live titles was the false positive this
document identified, none was a genuine standalone use. Spot-checked: «Эротика
в Ригведе: мужское и женское начало» now resolves to `state:I Vedic` +
`register:rgveda` (via «Ригвед» in the title) instead of `register:bhasya`
(via the removed «тика»).

### Also landed: `matched_field` export (scope item 2)

`renou_presentation_matches.csv` now carries `matched_field` (`title` | `tag`)
and `matched_field_text` (the literal tag string, empty for title matches).
The «Эротика в Ригведе» example above also now correctly shows a
`register:kavya` hit sourced from `matched_field=tag`,
`matched_field_text="Literature & Poetry"` — previously invisible evidence,
exactly the 14%-of-sample gap this document flagged.

### What did not land — and why

**Scope item 3 (deduplicate the rule table into one canonical file) is
intentionally not done.** It is gated behind the `@DECIDE` this document and
[H459](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H459-Sonnet_IndologyScholars_renou-rules-anchor-fix-and-dedupe_10.07.26.md)
both name — canonical home in `SanskritLexicography/RussianTranslation` next
to `RENOU.md`, or in `sanskrit-util` — and that ruling has not been made. The
table therefore still exists in the same three places (now anchored in one of
them, `RULE_ROWS`); a fix applied to `RULE_ROWS` still does not reach
`Indology/data/curation/renou_subject_rules.csv` or the `RussianTranslation`
état pilot. The archive table did not need the anchoring fix (see above), and
the `RussianTranslation` pilot was out of scope for this repo's session
entirely.

**A fourth, previously-unnoted duplicate:** `curation/renou_conference_rules.csv`
in this repo is seeded from `RULE_ROWS` by `generate_renou_layer.py`'s
`seed_rules()` — but only if the file does not already exist. Since it was
committed once at the layer's creation ([#66](https://github.com/gasyoun/IndologyScholars/pull/66))
and never touched again, it had silently drifted into a fourth, stale copy:
editing `RULE_ROWS` alone would have had **zero effect** on the actual pipeline
output, because `apply_rules()` reads the cached CSV, not the Python literal.
This fix deletes and lets it reseed on every session that touches the rule
table until scope item 3 resolves the dedup question properly; the safer
long-term fix (make `run()` always regenerate this file from `RULE_ROWS`, or
retire the seed-once behaviour once a canonical file is chosen) is left to
whoever executes step 3.

**Scope item 5 (raise coverage) was not attempted**, per its own explicit
gate ("only then") and the guardrail against loosening patterns to chase
coverage.

_Dr. Mārcis Gasūns_
