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

## Reuse Note

Use `expanded_classification_deepseek.csv` as the current public classification
export. Use `classification_reliability_sample.csv` when documenting manual
quality control or planning a second human adjudication pass.
