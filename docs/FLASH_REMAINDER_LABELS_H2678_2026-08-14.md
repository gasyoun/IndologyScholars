# Flash remainder labels (H2678) — 14-08-2026

_Created: 14-08-2026 · Last updated: 14-08-2026_

Wave-1 Indology remainder on the existing `deepseek-v4-flash` scripts from
[IndologyScholars#222](https://github.com/gasyoun/IndologyScholars/pull/222).
No model-default flip. Rights/publish stayed human: published
`theme_codes_final*.csv` / `expanded_classification_deepseek.csv` were not
rewritten.

## Remainder inventory

| Script | Input the script already reads | Already labelled | Remainder before this pass | This pass | After | Disposition |
|---|---|---:|---:|---:|---:|---|
| [scratch/theme_coding_llm.py](https://github.com/gasyoun/IndologyScholars/blob/main/scratch/theme_coding_llm.py) | [analytics_output/theme_review_queue.csv](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/theme_review_queue.csv) (34 current-id titles) | 0 of those 34 in `theme_codes_llm.csv` (860 legacy `PRES_R_*` rows) | 34 | 34 schema-valid | 0 | completed |
| [scratch/theme_coding_llm_v2.py](https://github.com/gasyoun/IndologyScholars/blob/main/scratch/theme_coding_llm_v2.py) | same 34-row queue | 14 already in `theme_codes_llm_v2.csv` | 20 | 20 schema-valid | 0 | completed |
| [article/work_expanded_classification_deepseek.py](https://github.com/gasyoun/IndologyScholars/blob/main/article/work_expanded_classification_deepseek.py) | `conferences.db` titled presentations (1362) | 1677 valid work rows (316 extras no longer in the live titled set) | 1 (`PRES_f4113dc86a`) | 1 valid | 0 vs live DB | completed; **not published** (`--limit 2000`) |
| [philology-research-agents/orchestrator.py](https://github.com/gasyoun/IndologyScholars/blob/main/philology-research-agents/orchestrator.py) | a single question on stdin / argv | n/a | none | 0 | n/a | **parked** — per-question pipeline, no unlabeled remainder corpus |

Parked leftovers (not this script's remainder):

- 35 legacy `PRES_R_*` ids still in `theme_codes_baseline.csv` but absent from `theme_codes_llm.csv`. After the classification-id remapping those ids are not what `theme_review_queue.csv` feeds. Do not invent a remapper here.
- 1 pre-existing v2 row `PRES_117aeb7260` (`Тема уточняется`) has `l1=unspecified`, which is outside the v2 five-class L1 list. It was already in `theme_codes_llm_v2.csv` before this pass; resume skipped it. Not rewritten.
- `WORK_CSV` still holds 316 valid extras that the current titled-presentation query no longer returns. Left in the checkpoint. Publish stays human.

## n + $

New labels written this pass: **55** (34 theme-v1 + 20 theme-v2 + 1 work_expanded).

| Meter | Value |
|---|---|
| JSONL calls | 8 ([analytics_output/deepseek_flash_calls.jsonl](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/deepseek_flash_calls.jsonl)) |
| JSONL ok / fail | 4 / 4 |
| JSONL logged USD (successful usage only) | **$0.004982** |
| Script-printed USD (includes tokens from failed JSON parses) | **$0.010436** |
| Model | `deepseek-v4-flash` on every call (resolved id, not a new default) |

Honest spend line: report **$0.0104** as the session upper bound. Four failed parses (empty / unterminated JSON on the first 20-row theme-v1 batch and one v2 attempt) billed tokens that the first JSONL writes recorded as `$0` because usage was attached only after a successful parse. The logger now keeps usage on parse failure; that fix cannot retroactively recover the four failed rows.

Schema-valid % on **new** writes: **55/55 (100%)**. work_expanded accepted `PRES_f4113dc86a` (`Адиваси. Загадочное племя тода`) as `ethnography` / `contemporary` / `unspecified` / `fundamental` / Gumilyov L1.

## What the scripts were allowed to do

- Resume by `presentation_id` (already wired).
- `--limit` / `--no-merge` on the theme scripts so a merge from the 895-row legacy baseline cannot shrink the published 1362-row finals.
- Shrink-guard inside `merge_and_summarize` if someone omits `--no-merge`.
- `max_tokens` raised to **32768** (plan D12) after the first 20-row theme-v1 batch returned empty JSON at 4000. Same cap on work_expanded classify + audit.
- JSONL every call via [tools/deepseek_call_log.py](https://github.com/gasyoun/IndologyScholars/blob/main/tools/deepseek_call_log.py). No API key in the log.

Not done, by fence:

- No rewrite of `theme_codes_final.csv`, `theme_codes_final_v2.csv`, `expanded_classification_deepseek.csv`, or `article/hypothesis_output/*`.
- No nagari / vk-ors / unpublished dump.
- No Systema L13 default flip.
- No research-agent invented question batch.

## How to resume

```text
python scratch/theme_coding_llm.py --no-merge
python scratch/theme_coding_llm_v2.py --no-merge
python article/work_expanded_classification_deepseek.py --limit 2000
```

Empty todo is a successful no-op. Publishing the work_expanded checkpoint still requires a human to run **without** `--limit` after an elevated-scale audit.

_Dr. Mārcis Gasūns_
