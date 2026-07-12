# ROADMAP — IndologyScholars

_Created: 27-05-2026 · Last updated: 10-07-2026_

> Integrated roadmap across data/DB, generated site, the ППВ article, and the
> `philology-research-agents` module. Three horizons: **Now / Next / Later**.
> Составлено 2026-05-27, обновлено 2026-06-10. Текущий статус — **ППВ подан;
> активный трек — интернационализация данных (Wikidata/OpenAlex/LOD) и
> сбор русскоязычных индологов.**
>
> Это живой документ. Пункты уровня **Now** заведены как GitHub issues
> (`gh issue list --label roadmap`); Next/Later описаны здесь и поднимаются в issues по
> мере приближения.

**TL;DR (EN).** ППВ article submitted. Active sprint: **expand the
Russian-indologist roster** (`scratch/` sub-project — 197 indologists, 60 tests)
and wire authority control (OpenAlex → Wikidata/ORCID, 122 candidates pending
human review). English **data paper** drafted (`article/data_paper_draft.md`),
target **Research Data Journal for the Humanities and Social Sciences (Brill)**;
DOI snapshot frozen in `article/snapshots/`. Long-range: video-archive, agents
module spinout, international ППВ translation.

**Актуальный корпус (2026-07-10):** 268 учёных · 1362 уникальных доклада ·
1388 авторских участий · 2004–2026 · 41 перекрёстной когорты · 163 только
Зографских · 64 только Рериховских.

---

## Обозначения

- 🅰️ статья ППВ · 🅳 данные/БД · 🅼 модуль агентов · 🅢 сайт · 🅜 методология
- Статус: ⬜ не начато · 🟡 в работе · ✅ сделано · ⚠️ риск/блокер

---

## NOW — активный спринт: сбор русскоязычных индологов + контроль авторитетов

Приоритет выбран редактором: **расширение ростера русскоязычных индологов**
(подпроект `scratch/`) с параллельной привязкой к международным
идентификаторам.

A. 🅳 🟡 **Ростер русскоязычных индологов (`scratch/`) → слияние в корпус.**
   197 индологов (114 вики/en.wiki-мост + 83 база конференций), Q-ID 8→26, 60 тестов.
   **Решение: влить ростер в основной корпус** — участники связываются с профилями,
   **неучастники выносятся отдельной страницей-реестром** (отличной от докладчиков).
   - ✅ Дизайн слияния: `docs/roster-merge-design.md` (участники → обогащение, неучастники → реестр)
   - ✅ Реализовано: `curation/non_participant_indologists.csv` (94), линкер участников (100, +2 Q-ID), страница `indologists.html`, 10 тестов, build+validate зелёные
   - ✅ Runbook Phase 5: `docs/ru-enrichment-runbook.md` (Wikidata годы, ru-инфобоксы, институты, идемпотентный re-seed)
   - ⬜ Phase 5 прогон (.ru, по runbook): Q-ID/годы жизни → `candidate`→`verified`
   - ⬜ P0 `wikidata_enrich.py` → годы жизни 13 записям, перегенерировать crossref (где Wikidata доступна)
   - ⬜ P0 `scrape_institutions_web.py` + Playwright → институц. имена (по runbook, запуск внутри .ru)
   - ⬜ P1 `expand_wikipedia_indologists.py` → ru-инфобоксы новым именам (где ru.wiki-статьи открываются)
   - ⬜ P1 Ручной добор имперского периода (~15 имён)
   - ⬜ P2 Постсоветские республики через en.wiki нац-категории + мост
   - Детальный план: `scratch/roadmap.md`, статус: `scratch/ai_status.md`
B. 🅳 🟡 **Контроль авторитетов (OpenAlex → Wikidata/ORCID).**
   - ✅ 122 кандидата OpenAlex найдены (`analytics_output/openalex_author_candidates.csv`)
   - ⬜ Ручная сверка 122 кандидатов (статус `todo` → `confirmed`)
   - ⬜ Инъекция при `relevance_score ≥ 0.8` (порог подтверждён), `confidence='candidate'`
   - ✅ Исправлены Q-ID в `generate_wikidata_batch.py`: P106 → `Q18524037` (профессия «индолог»), P101 → `Q625510` (область), удалён фиктивный `Q126692818`, источник как референс `S854`
   - ⬜ Отправить Wikidata-батч **только после** полной сверки 122 кандидатов
   - Руководство: `docs/wikidata-guide.md`
C. 🅳🅜 🟡 **Англоязычный data paper.**
   - ✅ Черновик `article/data_paper_draft.md` — **единоличное авторство (Gasūns)**, инструменты в acknowledgements
   - ✅ Замороженный снимок `article/snapshots/2026-06-03/` (`tools/freeze_article_data.py`)
   - ⬜ Подача в **Research Data Journal for the Humanities and Social Sciences (Brill)**
   - ⬜ **DOI на Zenodo** через GitHub-release; версия датасета — **датированная на каждый снимок** (CITATION.cff бампится при freeze)
   - ⬜ Inter-rater agreement в methods (`tools/compute_interrater_agreement.py`)
D. 🅜 ✅ **Runbook для .ru-шагов.** `docs/ru-enrichment-runbook.md` — пошагово:
   Wikidata годы жизни, ru-инфобоксы, Playwright-скрапинг институтов, OpenAlex,
   идемпотентный re-seed реестра, rebuild/validate/commit. Прогон — за редактором
   изнутри .ru.

---

## ✅ ЗАВЕРШЕНО — ППВ: подан

Категория подачи — **«статья» (≤ 40 000 знаков)**. Версия
`article/ppv_submission_article.md` — **35 195 знаков**.

1. 🅰️ ✅ **Ссылочный аппарат ППВ.** 5 внутритекстовых ссылок `(Автор Год)`, «Литература»
   в формате `Автор Год –`, латинский References.
2. 🅰️ ✅ **Аннотации и ключевые слова.** RU 982 зн., EN 993 зн., keywords 8 RU + 8 EN.
3. 🅰️ ✅ **Метаданные автора.** ФИО полностью, степень, должность, адрес с индексом,
   e-mail, ORCID — RU и EN.
4. 🅰️ ✅ **Обезличивание.** `ppv_submission_article_anonymous.md` пересобрана,
   `check_anonymity.py` passed, числа синхронизированы.
5. 🅰️🅳 ✅ **Пересборка БД и сверка чисел.** БД пересобрана, `check_ppv_numbers.py` → 0 drifts.
6. 🅰️🅜 ✅ **Pre-submission gate.** `validate_publication.py` passed, `pytest` 40/40,
   иллюстрации 300 dpi, cover letter обновлён.

**Результат:** статья, обезличенная копия, DOCX, иллюстрации, cover letter — всё готово.

---

## NEXT — после подачи (≈1–3 месяца): углубление

7. 🅳🅜 🟡 **Генеалогия и сети (заявленный «top track»).**
   - ✅ 20 teacher-student edges в `network_data.json` + пресет «Генеалогия» в networks.html
   - ✅ `tools/city_trajectory_audit.py` — 719 city-меток, 165 сопоставлено с институцией (22.9%)
   - ⬜ Связать траектории с профилями учёных на сайте
8. 🅳 🟡 **Покрытие и качество данных.**
   - ✅ Баг соавторов исправлен (`presentation_person_exclusions.csv`)
   - ✅ Bengal taxonomy избыточность устранена
   - ✅ `tools/scrape_birth_years.py` + `tools/apply_birth_years.py` — скрапер дат
   - ⬜ 33 учёных без дат рождения (30 city-only, 3 с институциями)
   - ⬜ Фильтрация мусорных ключевых слов
9. 🅜 ⬜ **Публикационная конверсия.** Какие доклады стали статьями/сборниками.
10. 🅼 🟡 **Перечень ВАК.**
    - ✅ `tools/vak_parser.py` — парсер Excel в CSV + генератор `editors/*.md`
    - ⬜ Загрузить актуальный .xlsx с сайта ВАК и прогнать
11. 🅼 🟡 **Зрелость модуля агентов.**
    - ✅ `philology-research-agents/SPINOUT_PLAN.md` — 3-фазный план выноса
    - ⬜ Python-оркестратор на Anthropic SDK + анти-галлюцинационные тесты
12. 🅢 🟡 **Сайт/UX.**
    - ✅ `positionTooltip()` — tooltip clamp на всех визуализациях
    - ✅ Клик по городу на карте → страница города
    - ✅ `.profile-facts` горизонтальная вёрстка (3 колонки)
    - ✅ «Соавторы (0)» скрыты (уже было)
    - ✅ «засвидетельствованный профиль» для 1 доклада (уже было)
    - ⬜ Фильтр «выпускник Востфака» — ждёт ручной верификации alumni
    - ⬜ Страница ключевых слов
13. 🅳 ✅ **Качество данных.** Баг соавторов, Bengal taxonomy, связи в CSV — всё сделано.
14. 🅜 🟡 **Наукометрия и новые фичи.**
    - ✅ Caveat о программах + inline-ссылки на рисунки в статье
    - ✅ Расширенные подписи к иллюстрациям
    - ⬜ Наукометрические расширения (eLIBRARY, OpenAlex, ORCID)

---

## VISUALISATION ROADMAP — что ещё можно добавить

Подробный рабочий список живёт в `article/visual.md`. Текущий набор визуализаций
на `findings/visualisations.html` — 9 интерактивных SVG/карт (VIS_001–VIS_010).

---

## LATER — стратегическое (6–12 месяцев)

15. 🅜 **Видеоархив и цифровая доступность.**
16. 🅳 🟡 **Воспроизводимость и открытые данные.** DOI на датасет — снимок
    заморожен (`article/snapshots/2026-06-03/`), data paper в работе (см. NOW-C);
    осталась Zenodo-депозиция и подача в Research Data Journal (Brill).
17. 🅼 **Вынос модуля агентов в отдельный репозиторий.** (План: `SPINOUT_PLAN.md`)
18. 🅰️ **Международная версия статьи.** Профиль `editors/iij.md` готов.
19. 🅳 **Расширение корпуса.** Другие индологические площадки.

20. 🅰️ **Международная версия статьи.** Исходник: `article/ppv_submission_article.md`.
    Целевой журнал: Indo-Iranian Journal (Brill) — профиль `editors/iij.md` готов.
    Задачи: (1) машинный перевод (DeepL/Claude), (2) адаптация References под
    Chicago author-date, (3) контекст для международной аудитории,
    (4) рецензия носителем. Оценка: ~1 неделя. Статус: отложено до подачи ППВ.

---

## Новые инструменты (2026-06-10)

| Инструмент | Назначение |
|------------|-----------|
| `scratch/enwiki_bridge.py` | en.wikipedia → ru-название + Wikidata Q-ID (RKN-устойчив) |
| `scratch/wikidata_enrich.py` | Q-ID → годы жизни (REST `Special:EntityData`) |
| `scratch/scrape_institutions_web.py` | Скрапер сайтов институтов (static→JSON:API→Playwright) |
| `scratch/openalex_author_candidates.py` + `resume_openalex.py` | Поиск кандидатов OpenAlex по ФИО |
| `tools/inject_openalex_matches.py` | Инъекция совпадений OpenAlex → `authority_ids.json` (candidate) |
| `tools/generate_wikidata_batch.py` | QuickStatements v2-батч (⚠️ исправить Q-ID до отправки) |
| `tools/freeze_article_data.py` | Замороженный снимок корпуса для DOI |
| `tools/build_interrater_sample.py` / `compute_interrater_agreement.py` | Inter-rater reliability |

### Инструменты предыдущего спринта (2026-06-02)

| Инструмент | Назначение |
|------------|-----------|
| `tools/city_trajectory_audit.py` | Аудит city→institution (719 меток, 22.9% matched) |
| `tools/vak_parser.py` | Парсер Excel-перечня ВАК → CSV + профили журналов |
| `tools/scrape_birth_years.py` | Скрапер дат рождения (Wikipedia, Dissercat, eLIBRARY) |
| `tools/apply_birth_years.py` | Применение найденных дат к БД |

## Сквозные принципы (из CLAUDE.md)

- `site_data.json` и сгенерированные HTML/CSV/JSON — **производные**; править генератор и
  пересобирать, не сами артефакты.
- Сохранять явную неопределённость: открытая аффилиация — `(?)`; невалидированная
  классификация не публикуется как `L2`.
- Перед публикацией: `python validate_publication.py` и `pytest`.

_Dr. Mārcis Gasūns_
