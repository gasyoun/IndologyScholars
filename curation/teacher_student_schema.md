# `teacher_student.csv` — schema · схема

> Curated, evidence-backed advisor/mentor relationships between persons in the
> IndologyScholars corpus. **Verified** entries are the source of truth for the
> profile-page «учитель / ученики» renderings and for the genealogy track (#9).
>
> Курируемые, документированные отношения «научный руководитель / ученик»
> между людьми из корпуса IndologyScholars. Записи со статусом **`verified`**
> — источник истины для секции «учитель / ученики» в профилях и для трека
> генеалогии (#9).

This file is read by `pipeline/genealogy.py`. Candidate-generator output lives
separately in `analytics_output/lineage_candidates.csv` (heuristic suggestions
from `article/work_lineage_candidates.py`) and must be **manually verified**
before any row is copied here.

## Columns · Колонки

| # | Column | Required | Type | Notes |
|---|---|---|---|---|
| 1 | `student_normalized_key` | yes | string | matches `person.normalized_key` (lowercase, dotted initials, e.g. `александрова н в`) |
| 2 | `student_display_name` | yes | string | for readability, e.g. `Александрова Наталия Владимировна` |
| 3 | `advisor_normalized_key` | yes | string | same form as the student key |
| 4 | `advisor_display_name` | yes | string | |
| 5 | `relationship_type` | yes | enum | `advisor` / `supervisor` / `mentor` / `academic_lineage` / `lectured` (see below) |
| 6 | `period_start` | no | int (YYYY) | year the relationship began (e.g. enrolment year) |
| 7 | `period_end` | no | int (YYYY) | year of completion / defence |
| 8 | `evidence_url` | yes for `verified` | URL | a verifiable source: RGB dissertation catalogue, autoreferat, official biography, Wikipedia (sourced) |
| 9 | `evidence_note` | yes | string | one-line summary of the evidence (e.g. `dissercat: degree defended under …, 2001`) |
| 10 | `status` | yes | enum | `verified` / `candidate` / `disputed` |
| 11 | `added_date` | yes | YYYY-MM-DD | when the row was added |
| 12 | `notes` | no | string | free-form |

## `relationship_type` vocabulary · словарь типов

- `advisor` — научный руководитель кандидатской/докторской диссертации (the strongest tie).
- `supervisor` — руководитель магистерской или дипломной работы.
- `mentor` — задокументированный наставник без формального руководства.
- `academic_lineage` — известная преемственность: «учился у X в институте Y», без точной формальной роли.
- `lectured` — слушал лекции X (слабая связь; включать редко и с явным основанием).

## `status` vocabulary · статусы

- `verified` — есть `evidence_url` и/или цитата из надёжного источника; запись публикуема.
- `candidate` — правдоподобная гипотеза, требует проверки; не публикуется.
- `disputed` — есть противоречащие источники; запись содержит обе версии в `notes`.

## Encoding rules · правила

- UTF-8 без BOM, разделитель — запятая (`,`), переводы строк `\n` (LF).
- Поля с запятыми/кавычками — в двойных кавычках, внутренние кавычки удваиваются.
- Ключи **нормализуются строго в нижнем регистре с инициалами через точку**, как в `person.normalized_key` (например, `александрова н в`, не `Александрова Н.В.`).

## Anti-fabrication rule · правило «не выдумывать»

A row may be added with `status=verified` **only** if `evidence_url` points to a
real, independently checkable source for the specific advisor–student tie at the
specific period. If unsure, use `status=candidate` and record what is known in
`evidence_note`. Empty `evidence_url` + `status=verified` is invalid and rejected
by `pipeline/genealogy.py`.

Строка с `status=verified` допустима **только**, если `evidence_url` ведёт на
реально проверяемый источник конкретной связи руководитель–ученик в указанный
период. Если уверенности нет — `status=candidate` и краткое пояснение в
`evidence_note`. Пустой `evidence_url` при `status=verified` — ошибка и
отклоняется загрузчиком.

## Adding a row · как добавлять

1. Найти подходящего кандидата в `analytics_output/lineage_candidates.csv` или
   из собственных биографических источников.
2. Найти подтверждение (РГБ-каталог, автореферат, биография, надёжная статья).
3. Заполнить строку по схеме выше; для нелатинских URL — ссылка как есть.
4. Запустить `python -c "from pipeline.genealogy import load_relationships; load_relationships()"`
   — он провалидирует и поднимет ошибку при проблемах.
