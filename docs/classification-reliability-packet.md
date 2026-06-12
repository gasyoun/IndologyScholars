# Classification Reliability Packet

[Development notes](development-en.md) | [Technical audit](classification-audit-en.md)

This packet is the citation-facing reliability note for the thematic and
argument-scale classification used in the public archive and PPV article.

## Frozen Artifact

- Final export: `analytics_output/expanded_classification_deepseek.csv`
- Frozen prompt version: `expanded-corpus-v1-2026-05-25`
- Strict review version: `scale-audit-v2-2026-05-25`
- Current rows: 1352 unique presentations
- Current G-scale distribution: G1 = 1161, G2 = 182, G3 = 9

## Codebook

The coding unit is the public presentation title, not the full paper, author
biography, or inferred disciplinary identity.

`theme_l1` records a broad disciplinary rubric. It is a navigation layer, not a
claim that the talk belongs exclusively to one discipline.

`period_l2` records the historical or cultural period visible in the title.
Unspecified titles remain unspecified rather than being inferred from the
speaker's known specialization.

`gumilyov_level` records the scale of the argument visible in the title:

| Level | Meaning | Boundary Rule |
| --- | --- | --- |
| G1 | Micro-case: one text, author, source, term, object, or local problem. | A region, language, period, or named tradition does not by itself raise the level. |
| G2 | Tradition, school, genre, large class of phenomena, or durable historical line. | Requires an explicit supra-case framing in the title. |
| G3 | Interregional, civilizational, comparative, or methodological synthesis. | Reserved for titles that announce a genuinely broad frame. |

## Review Layers

The final file is not a raw model output. It has three review layers:

- a controlled vocabulary pass in `article/work_expanded_classification_deepseek.py`;
- a strict second pass for all elevated preliminary G2/G3 assignments, logged
  in `analytics_output/expanded_gumilyov_elevated_audit.csv`;
- explicit expert overrides in `classification_overrides.py` and
  `analytics_output/classification_overrides.csv`.

The deterministic review sample is
`analytics_output/classification_reliability_sample.csv`. It includes all G3
records, all expert override records, and a fixed series-by-level sample of G1
and G2 records. Rows marked `queued_for_manual_review` are not adjudicated
facts; they are the next review queue.

## Ambiguity Rules

These cases must be treated conservatively:

- title names a region or language but remains about one textual or lexical
  object;
- title says "tradition" but the actual claim is one source or author;
- title compares two named objects without a wider comparative model;
- title belongs to a broad discipline, but the argument scale remains local.

When in doubt, the scale is lowered rather than elevated.

## Inter-Rater Reliability Design

`tools/build_interrater_sample.py` produces a truly blind coding sheet
(`analytics_output/interrater_sample_blind.csv`) and a separate answer key
(`analytics_output/interrater_sample_key.csv`) joined only at scoring time
by `tools/compute_interrater_agreement.py`. The sample (seed 20260612,
n=100) is stratified: a census of all argument-level-3 items, an oversample
of 30 level-2 items, and a random level-1 fill — a simple random sample
from a corpus that is ~86% G1 would leave the contested elevated levels
unmeasurable. Reported statistics: percentage agreement, Cohen's κ with
bootstrap 95% CIs (interpreted on the Landis & Koch 1977 bands),
Krippendorff's α, and Gwet's AC1 (the skewed level distribution makes raw
κ prevalence-sensitive).

The strict second pass over elevated G2/G3 assignments was performed by the
same model under a different adjudication prompt; it is a same-model
consistency check, not independent verification. Independent verification
is what the blind sample exists for.

### Cross-model agreement (2026-06-12)

As a sanity check preceding the human pass, the blind sample was coded by a
second LLM family (Claude, Anthropic `claude-fable-5`), from
title/year/series only, against the existing DeepSeek-assisted
classifications (`analytics_output/interrater_crossmodel_claude.csv`):

| Axis | % agree | Cohen's κ [95% CI] | Krippendorff's α | Gwet's AC1 [95% CI] |
| --- | ---: | ---: | ---: | ---: |
| L1 theme | 76.0% | 0.670 [0.554, 0.776] | 0.669 | 0.719 [0.617, 0.813] |
| Argument level | 76.0% | 0.553 [0.400, 0.694] | 0.554 | 0.672 [0.551, 0.783] |

Per-stratum agreement on the argument level: G1 86.4%, G2 63.3%, G3 54.5%.
The G2/G3 boundary is the weak point; the most frequent confusions were
G2→G1 (×10) and G3→G2 (×5), consistent with the conservative "when in
doubt, lower" rule. This is **cross-model agreement, not human inter-rater
reliability**; the human second-coder pass on the same blind sheet is the
statistic to report at submission.

## Reuse Note

Use `expanded_classification_deepseek.csv` as the current public classification
export (canonical argument-scale column: `argument_level`; `gumilyov_level`
is a legacy alias documented in `data_dictionary.md`). Use
`classification_reliability_sample.csv` when documenting manual quality
control or planning a second human adjudication pass.
