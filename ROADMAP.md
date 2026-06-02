# ROADMAP — IndologyScholars

> Integrated roadmap across data/DB, generated site, the ППВ article, and the
> `philology-research-agents` module. Three horizons: **Now / Next / Later**.
> Составлено 2026-05-27, обновлено 2026-06-02. Текущий статус — **ППВ готов к подаче ✅**.
>
> Это живой документ. Пункты уровня **Now** заведены как GitHub issues
> (`gh issue list --label roadmap`); Next/Later описаны здесь и поднимаются в issues по
> мере приближения.

**TL;DR (EN).** ППВ article is submission-ready (35 195 chars, 0 drifts, anonymous copy
synced, cover letter updated). Next: genealogy graph in networks.html deployed,
city-to-institution trajectory audit created, VAK parser and birth-year scraper ready.
Long-range: video-archive, dataset DOI, agents module spinout, international article.

---

## Обозначения

- 🅰️ статья ППВ · 🅳 данные/БД · 🅼 модуль агентов · 🅢 сайт · 🅜 методология
- Статус: ⬜ не начато · 🟡 в работе · ✅ сделано · ⚠️ риск/блокер

---

## NOW — ППВ: ✅ ГОТОВО К ПОДАЧЕ

Категория подачи — **«статья» (≤ 40 000 знаков)**. Текущая версия
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
16. 🅳 **Воспроизводимость и открытые данные.** DOI на датасет.
17. 🅼 **Вынос модуля агентов в отдельный репозиторий.** (План: `SPINOUT_PLAN.md`)
18. 🅰️ **Международная версия статьи.** Профиль `editors/iij.md` готов.
19. 🅳 **Расширение корпуса.** Другие индологические площадки.

20. 🅰️ **Международная версия статьи.** Исходник: `article/ppv_submission_article.md`.
    Целевой журнал: Indo-Iranian Journal (Brill) — профиль `editors/iij.md` готов.
    Задачи: (1) машинный перевод (DeepL/Claude), (2) адаптация References под
    Chicago author-date, (3) контекст для международной аудитории,
    (4) рецензия носителем. Оценка: ~1 неделя. Статус: отложено до подачи ППВ.

---

## Новые инструменты (2026-06-02)

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
