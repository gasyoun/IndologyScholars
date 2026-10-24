# Affiliation org tail vs `authority_ids.json` (H3269)

_Created: 28-08-2026 · Last updated: 28-08-2026_

**Handoff:** [H3269](https://github.com/gasyoun/Uprava/blob/main/handoffs/H3269-Grok_IndologyScholars_affiliations-org-tail_21.08.26.md) · **Executor:** Grok 4.6 (`grok-4.6`)

Census + smallest mapping pass after A12 ([PR #253](https://github.com/gasyoun/IndologyScholars/pull/253)). Does **not** regenerate the co-authorship network ([H2367](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H2367-Grok_IndologyScholars_coauthorship-network-regen_07.08.26.md)).

Prove-with:

```text
python scratch/affiliation_residual_check.py
python -m pytest tests/test_affiliation_normalize.py -q
```

## Baseline (A12, 24-08-2026, still the 1388-mention denominator)

| Bucket | Mentions |
|---|---|
| Total affiliation mentions | 1388 |
| Not stated (`Не указана` / blank) | 337 |
| Org resolved WITH Q-ID/ROR | 374 |
| Org resolved WITHOUT Q-ID/ROR | 2 |
| Authority organisations | 35 (all with Wikidata/ROR) |
| Residual strings after org resolve | 675, of which almost all are city-only (geography tail) |

A12's named leftover (~5 mentions) was still open: МРЦ; УРАО, Нижний Новгород; Администрация Главы Республики Калмыкия, Элиста; ГБУ «Замок Шереметьева», онлайн; Наталья Афонасьевна НИ. This pass also saw **ММС, Москва** (same speaker as МРЦ) and the programme shorthand **НИ / ни** (8 mentions plus the name-leak row).

## Five mapping tries

1. **УРАО, Нижний Новгород** (1, Демичев 2012) → mapped to **УРАО** = Wikidata [Q4475813](https://www.wikidata.org/wiki/Q4475813), ROR `02d2yjc53` (item aliases include URAO / University of the Russian Academy of Education).
2. **ГБУ «Замок Шереметьева», онлайн** (1, Шалахов 2024) → mapped to **ГБУ Замок Шереметьева** = Wikidata [Q4523096](https://www.wikidata.org/wiki/Q4523096) (estate + Wikipedia describes the GBUK).
3. **Администрация Главы Республики Калмыкия, Элиста** (1, Корнеев 2025) → **unresolvable**. Legal entity ОГРН 1020800754270 exists; no Wikidata/ROR item for the administration (the office of Head of Kalmykia is a different entity).
4. **МРЦ** (1, Мехакян 2016) → **unresolvable**. Acronym with no clean authority match.
5. **ММС, Москва** (1, Мехакян 2025) → **unresolvable**. Same speaker, different acronym, still no clean authority match.

Mechanical (not a sixth Wikidata mint): programme shorthand **НИ / ни** = независимый исследователь. Maps 11 mentions (standalone НИ/ни, НИ/ни + Лозанна, and the name-leak `Наталья Афонасьевна НИ`) onto the existing canon **Независимые исследователи**. That bucket has no organisation Q-ID (occupation, not an org).

## After

Measured 28-08-2026 after the mapping (`python scratch/affiliation_residual_check.py`):

| Bucket | Before (A12) | After (H3269) |
|---|---|---|
| Org resolved WITH Q-ID/ROR | 374 | 376 (+УРАО, +Замок) |
| Org resolved WITHOUT Q-ID/ROR | 2 | 13 (prior independent strings + 11 НИ shorthand) |
| Authority organisations with Q-ID/ROR | 35 | 37 |
| City-name matched (not org-resolved) | (checker missed `city_aliases`, reported 0) | 648 |
| Named org-tail still unmapped | 5 + ММС | **3 mentions:** Администрация Главы Республики Калмыкия, Элиста; МРЦ; ММС, Москва |
| Other unresolved (geography aliases not in `city_aliases`) | mixed into the 675 | 11 mentions (Ижевск, Калиниград, С.-Петербург, Киев — Луцк, Кембридж ×2, Вена, Горный Алтай, Новгород, Великобритания) |

City-only strings stay in the geography/`geography.json` tail. The residual checker now reads `city_aliases` and does not hide institution-shaped leftovers that also contain a city token.

_Dr. Mārcis Gasūns_
