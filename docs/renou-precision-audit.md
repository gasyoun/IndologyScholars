# Renou classifier — precision audit

_Created: 10-07-2026 · Last updated: 10-07-2026_

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

_Dr. Mārcis Gasūns_
