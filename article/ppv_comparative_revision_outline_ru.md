# План сравнительной редакции статьи ППВ — пятилинзовый контекст (H1899)

_Created: 06-08-2026 · Last updated: 05-09-2026_

Подготовил: Opus 5 (`claude-opus-5`), локальный проход H1899, ветка
`h1899-report-figures-snapshot` от `origin/codex/community-lenses-ask-plan`.
Ничего не закоммичено, не опубликовано и не отправлено.

Этот документ — **план правки**, а не текст статьи: прозу пишет H1900. Здесь
для каждого раздела названы предполагаемое утверждение, идентификаторы
свидетельств, рисунок/таблица, точные цитаты (где права позволяют),
контрсвидетельство и ограничение.

> Все ссылки ниже — **относительные и локальные по построению**: перечисленные
> артефакты (таблицы, рисунки, отчёты, снимки, реестры личностей и цитат) не
> закоммичены и не опубликованы, поэтому полного GitHub-адреса у них нет и быть
> не должно до снятия правового шлюза закрытой группы.

## Исходные правила распределения объёма

- **≈2/3 аналитического объёма — Рериховские/Зографские чтения.** Это главный
  объект статьи; остальные линзы дают сравнительный контекст.
- **≈1/3 — сравнительный контекст:** nagari (закрытая группа, PILOT),
  ORS/VK (стена сообщества, полное покрытие). INDOLOGY-L и BVP в этом снимке
  **отсутствуют как источники** и входят только как зафиксированные пробелы.
- Разделы существующей статьи (`article/ppv_submission_article.md`) сохраняются;
  сравнительный материал вставляется внутрь них, а не отдельной пятикорпусной
  главой (риск R12 — превращение статьи в обзор пяти корпусов).
- Отправленный вариант статьи и его анонимная копия **не редактируются**.

## Источники свидетельств

| Артефакт | Что содержит |
|---|---|
| [`analytics_output/community_lenses/tables/`](../analytics_output/community_lenses/tables/) | 7 замороженных таблиц метрик; каждая строка со своим числителем/знаменателем |
| [`analytics_output/community_lenses/figures/`](../analytics_output/community_lenses/figures/) | 6 рисунков + подписи (`captions.md`) |
| [`analytics_output/community_lenses/reports/comparison_validity.md`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/reports/comparison_validity.md) | отчёт о валидности, V1–V11 |
| [`analytics_output/community_lenses/reports/claims_ledger.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/reports/claims_ledger.csv) | реестр утверждений: вердикт + связь со свидетельством |
| [`comparison_snapshots/through-2025/`](comparison_snapshots/through-2025/) · [`partial-2026/`](comparison_snapshots/partial-2026/) | замороженные пакеты с манифестами SHA-256 |

Ни одно число в статье не берётся из чата или из промежуточного вывода: оно
цитируется по `metric_id` из замороженной таблицы.

---

## Аннотация / Abstract

- **Утверждение:** статья описывает двадцать лет российской конференционной
  индологии и помещает их в сравнительный контекст ещё двух наблюдаемых
  российских площадок.
- **Свидетельства:** `cl-conf-scale`, `cl-orientation-premise`.
- **Контрсвидетельство:** сравнение не охватывает западную и индийскую
  площадки — это надо сказать уже в аннотации, а не только в ограничениях.
- **Ограничение:** никаких утверждений о «российской индологии в целом».

## 1. Постановка задачи

- **Утверждение:** конференционная программа — наблюдаемый и полный по своему
  охвату след сообщества; другие площадки показывают иные формы активности,
  несводимые к докладам.
- **Свидетельства:** `cl-conf-scale`, `cl-orientation-premise`.
- **Рисунок/таблица:** [`lens_source_coverage.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/tables/lens_source_coverage.csv).
- **Правка к текущему тексту:** добавить один абзац о том, что «активность»
  измеряется в родных единицах (доклад / сообщение / пост) и никогда не
  суммируется между площадками.
- **Ограничение:** единица наблюдения — не человек.

## 2. Корпус и метод (главная методологическая правка)

- **Утверждения:** `cl-conf-scale`, `cl-2026-partial`, `cl-orientation-premise`.
- **Свидетельства:** `coverage.conferences`, `coverage.nagari`, `coverage.vk_ors`,
  `coverage.indology_l`, `coverage.bvp`; `activity.*.2026-partial`.
- **Рисунок/таблица:** [`fig1_activity_by_period.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig1_activity_by_period.svg),
  [`source_manifests.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/article/comparison_snapshots/through-2025/source_manifests.csv).
- **Что добавить:**
  1. таблицу пяти линз: родная единица, снимок, покрытие, число записей,
     основание прав;
  2. правило знаменателя: доля считается только внутри линзы;
  3. правило 2026: частичный год вынесен в отдельный пакет и не входит
     ни в один тренд;
  4. абзац о том, что «российская / западная / индийская» — **ориентация
     площадки** (посылка отбора корпуса), а не гражданство участников.
- **Контрсвидетельство:** полнота конференционной линзы — полнота базы программ,
  а не полнота научной жизни.
- **Ограничение:** nagari — PILOT; любые его доли описывают размеченный срез.

## 3. Масштаб и структура участия (Рериховские/Зографские чтения — ядро)

- **Утверждение:** `cl-conf-period-composition` — доля докладов периода
  2018–2025 выше доли 2005–2010 внутри той же линзы.
- **Свидетельства:** `activity.conferences.2005-2010`,
  `activity.conferences.2011-2017`, `activity.conferences.2018-2025`.
- **Рисунок:** [`fig1_activity_by_period.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig1_activity_by_period.svg) — верхняя панель.
- **Контрсвидетельство:** рост может отражать изменение практики учёта программ;
  различить это по имеющимся данным нельзя — сказать прямо.
- **Ограничение:** описательное сравнение долей; причинных формулировок нет.
- **Сравнительная вставка (≤1 абзац):** у ORS/VK и nagari своя динамика в своих
  единицах; кривые не накладываются друг на друга и не складываются.

## 4. Тематические профили и источник аффилиации

- **Утверждения:** `cl-conf-content-profile` (provisional),
  `cl-nagari-teaching` (provisional), `cl-vk-biblio-series` (supported).
- **Свидетельства:** `content.conferences.literature_poetics.taxonomy_crosswalk`,
  `content.conferences.religion_philosophy.taxonomy_crosswalk`,
  `content.nagari.texts_philology.taxonomy_crosswalk`,
  `function.nagari.teaching_learning.taxonomy_crosswalk`; цитата `Q-VK-22289`.
- **Рисунки:** [`fig2_intellectual_content.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig2_intellectual_content.svg),
  [`fig3_community_function.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig3_community_function.svg).
- **Обязательная оговорка в тексте:** кроссволк H1897 не прошёл человеческую
  проверку, поэтому общие тематические доли подаются как **предварительные**;
  родные тематические коды остаются принятым свидетельством.
- **Цитаты:** `Q-VK-22289` — статус прав `pending_review`: до подтверждения
  дословную цитату **не публиковать**; при отсутствии одобрения пример
  опускается, пересказ запрещён.
- **Ограничение:** знаменатель — записи, размеченные по данной оси, а не все.

## 5. Микрокейс как норма (второе ядро — люди и цитаты)

- **Утверждения:** `cl-conf-gumilev` (supported), `cl-crosslens-persons`
  (supported), `cl-nagari-quotes-gated` (supported).
- **Свидетельства:** `gumilev.conferences.G1.gumilyov_scale_csv_deepseek`,
  `gumilev.conferences.G3.gumilyov_scale_csv_deepseek_strict_scale_audit`,
  `overlap.conferences`, `overlap.nagari`; цитаты `Q-NG-PANINI-ASK`,
  `Q-NG-PANINI-ANSWER`.
- **Рисунки:** [`fig4_argument_level.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig4_argument_level.svg),
  [`fig5_person_overlap.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig5_person_overlap.svg).
- **Что можно сказать:** семь человек засвидетельствованы и в программе, и в
  закрытой группе (641 упоминание); пять кандидатов остались неоднозначными и
  исключены из счёта; ни одна связь не принята автоматически.
- **Чего нельзя:** называть этих людей в публикации по цитатам из закрытой
  группы — обе цитаты `non_exportable` до одобрения владельца группы.
- **Контрсвидетельство:** совпадение имён и замаскированных аккаунтов —
  вероятностное свидетельство; именно поэтому пять случаев не засчитаны.
- **Ограничение:** пересечение площадок ≠ миграция сообщества (`cl-no-migration`).

## 6. Обсуждение

- **Утверждения:** `cl-crosslens-gumilev` (out_of_scope), `cl-west-india-gap`
  (out_of_scope), `cl-renou-gate` (out_of_scope), `cl-no-migration`
  (expert_judgment).
- **Свидетельства:** `gumilev.nagari.G1.deterministic_ruleset_pilot`,
  `gumilev.vk_ors.unknown.deterministic_ruleset_pilot`, `coverage.indology_l`,
  `coverage.bvp`.
- **Рисунок:** [`fig6_orientation_contrast.svg`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/fig6_orientation_contrast.svg).
- **Ключевой абзац редакции:** сравнение «Россия — Запад — Индия» в этом снимке
  **не выполняется**: INDOLOGY-L заблокирован отсутствием атомарного снимка,
  BVP — отсутствием собранного корпуса. Это пробел доказательств, а не
  измеренный ноль, и статья должна сказать это прямо, а не обойти молчанием.
- **Ограничение:** межлинзовая шкала Гумилёва и слой Рену остаются вне
  публикуемых результатов.

## 7. Выводы

- **Утверждение:** конференционная линза даёт устойчивую, проверяемую картину
  двадцатилетней динамики; две другие российские площадки показывают, что
  учебно-обучающая и библиографическая активность живёт вне докладов.
- **Свидетельства:** `cl-conf-period-composition`, `cl-nagari-teaching`,
  `cl-vk-biblio-series`, `cl-crosslens-persons`.
- **Ограничение:** выводы описательные, внутрилинзовые и не обобщаются на
  сообщество, страну или дисциплину.

## Ограничения (отдельный подраздел, обязательный)

1. Родные единицы несопоставимы; общих итогов активности нет.
2. nagari — PILOT: только композиция размеченного среза.
3. INDOLOGY-L и BVP отсутствуют: западная и индийская ориентации не наблюдаемы.
4. Общие тематические оси — предварительные (кроссволк не проверен человеком).
5. Межлинзовая шкала Гумилёва — непубликуемый пилот.
6. Слой Рену — за gold-review шлюзом.
7. Цитаты: 3 зарегистрированы, 0 экспортируемых; пересказ вместо цитаты запрещён.
8. Ориентация площадки — экспертное суждение без p-значения.
9. 2026 год — частичный и вынесен в отдельный пакет.

## Подписи к рисункам

Готовые подписи (линза · родная единица · период · знаменатель · оговорка о
покрытии) — [`figures/captions.md`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/figures/captions.md).
В статье они используются **дословно**: подпись без знаменателя — дефект.

## Чего H1900 делать не должен

- Переписывать или перезаписывать `article/ppv_submission_article.md` и его
  анонимную копию.
- Повышать статус предварительного утверждения до подтверждённого.
- Публиковать дословную цитату со статусом прав `pending_review` или
  `non_exportable`.
- Вводить число, которого нет в замороженных таблицах.
- Давать причинную или репрезентативную интерпретацию описательным различиям.

_Dr. Mārcis Gasūns_
