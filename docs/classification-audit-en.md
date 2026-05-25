# Technical Audit of Talk Classification

[Русская версия](classification-audit.md) | [Development and reproducibility](development-en.md)

Classification pass date: 2026-05-25  
Coding prompt version: `expanded-corpus-v1-2026-05-25`  
Strict review version: `scale-audit-v2-2026-05-25`

## Audit Scope

All 1350 unique talks received disciplinary theme codes, meso-level
categories, and an argument-scale level from `L1` to `L3`, using controlled
vocabularies. An unprocessed or invalid record is not assigned `L2` by
default: publication is allowed only after a complete valid pass.

## Review of Elevated Levels

All 270 preliminary `L2`/`L3` assignments were submitted to a separate strict
audit. According to `analytics_output/expanded_gumilyov_elevated_audit.csv`,
the second pass changed 81 assignments: 80 levels were lowered and one was
raised (`L2 -> L3`). Two disputed `L3` cases were then editorially assigned to
`L2`.

Compared with the initial classification pass, the final export differs in
83 rows: 82 levels are lower than initially assigned and one is higher. The
final distribution is:

| Level | Talks | Share |
| --- | ---: | ---: |
| `L1` | 1155 | 85.6% |
| `L2` | 185 | 13.7% |
| `L3` | 10 | 0.7% |

## Artifacts

| Path | Purpose |
| --- | --- |
| `article/work_expanded_classification_deepseek.py` | Script for initial coding, strict review, and editorial decisions. |
| `analytics_output/expanded_classification_deepseek_work.csv` | Initial pass before strict review. |
| `analytics_output/expanded_gumilyov_elevated_audit.csv` | Decision log for preliminary `L2`/`L3` records. |
| `analytics_output/expanded_classification_deepseek.csv` | Final classification of all talks. |
| `article/hypothesis_output/expanded_classification_summary.md` | Summary distribution of levels and meso-level categories. |
| `analytics_output/classification_overrides.csv` | Small manual control set of public examples. |

## Interpretation

The level describes the scale of the argument stated in a title, not the
quality of a talk, the geographic extent of its material, or its author's
standing. A region, language, period, pair of compared objects, or the word
"tradition" does not by itself raise a case study to `L2` or `L3`.
