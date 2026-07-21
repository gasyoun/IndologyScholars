# История изменений (Changelog)

Все заметные изменения в этом проекте будут отражены в данном файле.

Этот проект представляет собой высокоточный академический конвейер для оцифровки, интеллектуального анализа и визуализации истории российской индологической науки.

## [Unreleased]

## [1.3.0] - 2026-07-21

### Changed
- **`Indology/` (атлас архива рассылки INDOLOGY-L, 1990–2026) выделен в
  отдельный репозиторий [`gasyoun/IndologyArchiveAtlas`](https://github.com/gasyoun/IndologyArchiveAtlas)
  (H460)**, вместе с полной историей коммитов (`git filter-repo`) и
  собственным ежемесячным workflow/Pages-деплоем. Этот сайт теперь читает
  только маленький односторонний фид (`tools/fetch_indology_feed.py`,
  ~5 МБ) для кросс-сайтового сравнения Рену
  ([`generate_renou_layer.py`](https://github.com/gasyoun/IndologyScholars/blob/main/generate_renou_layer.py))
  вместо прямого чтения дерева `Indology/`; старый путь `/IndologyArchive/`
  теперь редиректит на Pages нового репозитория.

### Fixed
- **Рукопись A25 ([`article/ppv_submission_article.md`](https://github.com/gasyoun/IndologyScholars/blob/main/article/ppv_submission_article.md)) несла два несовместимых снимка корпуса одновременно (H1376).**
  Абстракты, §2–§3 и G-шкала §5 стояли на снимке A (1362 доклада, 890 Зограф + 472 Рерих,
  1388 участий), а §4 (таблицы дисциплин и периодов, сумма колонки Зографа 880, «1161 из
  1352» в сводной строке, 1378 участий) и §7 — на устаревшем снимке B; мезо-уровневые
  счетчики §5 не совпадали ни с одним. Все таблицы и прозаические цифры регенерированы из
  зафиксированного снимка [`article/snapshots/2026-07-17`](https://github.com/gasyoun/IndologyScholars/tree/main/article/snapshots/2026-07-17)
  (он теперь назван в §2 как источник воспроизводимости); редакционная переклассификация
  двух докладов G3→G2 заявлена один раз в §5 и последовательно проведена всюду
  (G1 = 1146, G2 = 207, G3 = 9); ожидание нулевой модели исправлено на 131 (sd 3.9, z −23);
  доля «только город» — на 70.3% (что снимает и расхождение A25↔A26). Числовой гейт
  [`article/check_ppv_numbers.py`](https://github.com/gasyoun/IndologyScholars/blob/main/article/check_ppv_numbers.py),
  который в двух CI-workflow рапортовал «no drifts» при живых противоречиях, расширен
  покрытием сводной строки §4, вывода §7, знаменателя аффилиаций, сумм колонок обеих
  тематических таблиц, мезо-блока, ожидания нулевой модели и долей «только город», плюс
  проверяемый реестр редакционных переклассификаций; расширенный гейт доказуемо падает на
  тексте до правки (25 дрейфов, exit 1) и проходит после (0, exit 0).
- **Все интерактивные графики на страницах с встроенным JS были пусты на живом сайте
  (тепловая карта, топ-авторы, темы, сеть ответов, книгохранилище — «не загружены»).**
  Причина — продакшн-минификатор
  [`prepare_pages_artifact.py`](https://github.com/gasyoun/IndologyScholars/blob/main/prepare_pages_artifact.py):
  `minify_html` схлопывал `\s+` → ` ` по всему документу, включая тело inline `<script>`.
  После удаления переводов строк первый же строчный комментарий `// …` «съедал» весь
  остаток однострочного скрипта, поэтому определялись только функции до первого комментария,
  а ни один график не отрисовывался. Исправление: `minify_html` больше не трогает содержимое
  блоков `<script>`/`<style>` (минифицируется только разметка вокруг них); регрессия закрыта
  двумя тестами в
  [`tests/test_pages_artifact_coverage.py`](https://github.com/gasyoun/IndologyScholars/blob/main/tests/test_pages_artifact_coverage.py).
- **Тот же минификатор портил `https://`-ссылки в отдельных `.js` (страницы учёных и карта).**
  `minify_js` в [`prepare_pages_artifact.py`](https://github.com/gasyoun/IndologyScholars/blob/main/prepare_pages_artifact.py)
  вырезал комментарии приёмом `//.*?\n` → `\n`, который срабатывал и на `//` **внутри строк**:
  из `assets/js/main.js` пропадали ссылки ORCID/Wikidata, из `assets/js/charts.js` — URL тайлов
  подложки карты (`basemaps.cartocdn.com`). Исправление: `minify_js` больше не трогает
  внутристрочное содержимое (регулярка не отличает код от строк/regex/шаблонных литералов) —
  удаляются только строки-целиком-комментарии `//` и пустые строки, переводы строк сохраняются.
  Регрессия закрыта двумя тестами (включая проверку реальных ссылок в shipped-ассетах).

### Added
- **Каждый файл Markdown-зеркала теперь ссылается на оригинальный тред в Google
  Groups.** `export_md.py` добавляет `google_groups_url()` — строит
  документированную deep-ссылку `https://groups.google.com/d/msgid/nagari/<Message-Id>`
  по стартовому сообщению треда (проверено вживую: ведёт прямо на реальный тред без
  авторизации), выводится как `source_url:` во front-matter и кликабельной строкой
  под заголовком `# тема`. **Найдено и предотвращено при подготовке:** прямая
  публикация каждого `Message-Id` сама по себе утекла бы PII мимо редактора —
  часть почтовых серверов строит `Message-Id` из локальной части адреса
  отправителя, деанонимизируя маскированное имя; измерено 14/2 928 тредов (0.5%),
  `google_groups_url()` сверяет `Message-Id` с адресом отправителя и опускает
  ссылку именно для этих 14, не отказываясь от функции целиком.
  `scripts/audit_publish_surface.py` научен пропускать строки `source_url:`/msgid
  (иначе ~2 900 ложных срабатываний на непрозрачных, но email-подобных токенах);
  повторный прогон чист, 0 утечек.
- **Ретроспектива: тредовые ссылки — «Легендарные треды», поиск и «Заметные файлы»
  теперь кликабельны.** По решению владельца (17-07-2026, в чате) опубликован
  редактированный Markdown-зеркал `nagari/md/` (2 928 тредов, ~69 МБ) — `page.py`
  теперь прокидывает `gm_thrid` через `thread_md_url()` в `notable`, `threads`
  (поиск) и `book_top`; для книгохранилища URL ищется по `gm_thrid` треда, а не по
  теме сообщения-обёртки (106/367 строк `book_index.csv` расходятся с темой
  стартового сообщения треда). `_template.py` оборачивает ячейки темы/файла в
  `<a href>`. `scripts/audit_publish_surface.py` перед публикацией повторно
  подтвердил 0 утечек адресов и в странице, и в свежесобранном зеркале. Заполняет
  ранее заведённый пустой стаб
  [H1143](https://github.com/gasyoun/Uprava/blob/main/handoffs/H1143-Sonnet_IndologyScholars_nagari-md-mirror-publish_17.07.26.md).
- **Книгохранилище: учебный архив для студентов — опубликовано 134 файла (81.1 МБ).**
  По решению владельца («publish all … for education purposes», 17-07-2026) из 413 книжных
  вложений выложено всё, что правомерно открыть: **работы владельца (bucket A, 95)**,
  **общественное достояние (B, 24)** и **свободно распространяемые документы (B-cand/C-cand,
  15)** — по правовой переписи
  [H1142](https://github.com/gasyoun/Uprava/blob/main/handoffs/H1142-Fable_IndologyScholars_nagari-attachment-rights-triage-census_17.07.26.md).
  Страница `/nagari/books/` с секциями по основаниям; построена
  [`build_books_portal.py`](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/scripts/build_books_portal.py)
  из `nagari/reports/nagari_attachment_rights.csv`; файлы лежат в `nagari/site/books/`
  (точечное исключение из ignore-правила). Заменяет `build_pd_books_portal.py` (был только bucket B).
- **НЕ опубликовано — 279 файлов в авторском праве третьих лиц** (учебная цель разрешения не
  заменяет, сайт GitHub Pages — открытый веб, не «только для студентов»): D-author (169 — работы
  участников списка, разрешение авторов получаемо по запросу), D-third (62 — словари/статьи/
  монографии третьих лиц), E (45 — не идентифицировано) и 3 файла типографского слоя над
  текстом Зализняка (текст в авторском праве). Полные 986 МБ извлечённых блобов остаются в
  `nagari/data/attachments/` под общим ignore-правилом.

## [1.2.1] - 2026-07-17

### Added
- **Публикация ретроспективы «20 лет Обществу ревнителей санскрита».** Страница
  `nagari/site/index.html` (18 729 сообщений, 2 928 тредов, 605 авторов, 2 333
  участника, 2005-06-15 — 2026-07-10) выведена на GitHub Pages по адресу
  `/nagari/` через алиас `nagari/site` → `nagari` в `prepare_pages_artifact.py`
  (по образцу `Indology` → `IndologyArchive`). Конвейер перезапущен целиком:
  0 ошибок разбора на 1,88 ГБ `topics.mbox`.
- **`nagari/scripts/audit_publish_surface.py`** — аудит поверхности публикации
  (read-only, ненулевой код возврата при утечке). Проверяет три вещи: адреса на
  странице, адреса в Markdown-зеркале, наличие вложений-блобов на диске.

### Changed
- `.gitignore`: из `nagari/site/` опубликован ровно один файл (`index.html`);
  зеркало `nagari/md/` и база остаются закрытыми.

### Security
- Аудит зафиксировал: на странице **0** сторонних адресов (редактирование
  работает), но в Markdown-зеркале — **1 290** различных сторонних адресов в
  **42 421** вхождении. Зеркало не публикуется, пока `export_md.py` не начнет
  редактировать адреса так же, как это уже делает `page.py`. 2 030 вложений
  (367 книжных файлов) не извлекаются: конвейер хранит только метаданные, права
  на них не проверялись.
- **Исправлено (H1104, [PR #104](https://github.com/gasyoun/IndologyScholars/pull/104)):**
  редактор адресов вынесен из `page.py` в общий `nagari_group_archive/redact.py`
  и применён в `export_md.py` к телам сообщений, цитируемым блокам ответа,
  подписям, именам отправителей/участников и темам. `audit_publish_surface.py`
  теперь показывает `[md ] no third-party addresses found` (было 1 290 / 42 421).
  Публикация самого зеркала — отдельное человеческое решение (имена, аффилиации
  и цитируемая переписка закрытого списка остаются в тексте); вложения по-прежнему
  не извлекаются. Sonnet 5 (`claude-sonnet-5`).

## [1.2.0] - 2026-07-17

### Added
- **A26 data paper: депозит-готовый пакет Zenodo (H1072).** Заморожен снимок
  `article/snapshots/2026-07-17/` (`tools/freeze_article_data.py`, 19 позиций,
  SHA-256 `manifest.txt`); версия датасета `2026.07.17` вписана в
  `article/zenodo_metadata.json` (статус переведен из «заморожено org-wide» в
  «deposit-ready», заморозка истекла 15-07-2026); `CITATION.cff` синхронизирован
  (v1.2.0, дата 17-07-2026, каноническое название датасета). В
  `article/data_paper_draft.md` §5.4/§7 плейсхолдер DOI разделён на явные
  слоты concept/version (`10.5281/zenodo.PENDING`), название датасета
  гармонизировано между статьёй, Zenodo-метаданными и `CITATION.cff`, байлайн
  с диакритикой. Кросс-модельная κ переподтверждена из
  `analytics_output/interrater_crossmodel_claude.csv`
  (L1 κ=0,670 [0,554–0,776]; argument κ=0,553 [0,400–0,694]) — единственная
  ранее не машинно-проверенная цифра; ворота
  `article/check_data_paper_numbers.py` (19 утверждений), `validate_publication.py`
  и pytest (147) зеленые. Сам депозит Zenodo — человеческий шаг (логин MG),
  вынесен в Uprava GTD. Fable 5 (`claude-fable-5`).

### Changed
- **Решение D1 принято (10-07-2026): границы индологии ратифицированы.** Четыре
  кода, добавленные в этапе 1 со `status=proposed` — `literature`, `linguistics`,
  `ethnography`, `history_of_indology` — переведены в `core`. Таксономия:
  зонтичная `indology` + 13 предметных кодов + служебный `unattested`. Разметка
  персон не изменилась (те же 607 строк `person_discipline` на 268 персон): статус
  кода — метаданные справочника, а не признак отнесения. Кода социологии/политологии
  по-прежнему нет; `modern_society_politics` продолжает отображаться на `ethnography`
  с уверенностью 0,6, и это остаётся отдельной развилкой.

### Added
- **Архив гуглгруппы «Общество ревнителей санскрита» (H829).** Воспроизводимый
  конвейер `nagari/nagari_group_archive` (только стандартная библиотека) над
  экспортом Google Takeout закрытого списка `nagari@googlegroups.com` (2005–2026):
  18 729 сообщений, 2 928 тредов, 2 333 участника, 2 030 вложений, 0 ошибок разбора.
  Стадии: `ingest` (mbox → SQLite + FTS5), `insights` (4 слоя анализа — хронология,
  сети ответов/совместного участия, темы + NLP по телам, санскрит + книгохранилище),
  `export_md` (Markdown-зеркало по тредам), `page` (самодостаточная страница
  «20 лет Обществу ревнителей санскрита»). Сырой дамп, БД, `md/`, `site/`, `data/`
  под `.gitignore`; публикация — только после `/publish-safety-check` (закрытый список).
- **Разделы «Индология в России» и «Санскритология в России» (этап 1, H473).**
  Две посадочные страницы, генерируемые из БД: `indologiya-v-rossii.html` —
  зонтичный раздел, `sanskritologiya-v-rossii.html` — фасет над тем же спайном
  персон (решение R5), а не вторая база. Обе в `sitemap.xml` и в навигации.
- **Просопографический спайн схемы:** таблицы `discipline`, `person_discipline`,
  `work`, `work_discipline`, `person_role`, `relation` в `pipeline/schema.py`.
  `work` создаётся пустой и наполняется на этапе 4.
- **Таксономия дисциплин v0** — `curation/disciplines.csv` (плоская, с
  `parent_discipline_id`, чтобы решение D1 меняло строки, а не схему). Девять
  кодов стартового набора плюс четыре со `status=proposed`
  (`literature`, `linguistics`, `ethnography`, `history_of_indology`), без
  которых стартовый набор покрывал лишь 203 из 268 персон.
- **Разметка 268 персон:** 607 строк `person_discipline` — 267 персон с
  дисциплиной, одна (директор ИВР РАН, только институциональные приветствия)
  помечена служебным кодом `unattested` с `confidence = 0.0` вместо выдуманной
  дисциплины. Источники: курируемый кроссволк
  `curation/meso_discipline_crosswalk.csv` над `meso_codes_deepseek.csv` и
  ручная разметка `curation/person_disciplines.csv`. `keyword_filtering.py`
  сознательно не использован (риск P1: незаякорённые основы, ошибка ≥ 7,1%).
- `tests/test_discipline_spine.py` — 14 регрессионных тестов на инварианты
  спайна (полнота разметки, изоляция сентинела, границы уверенности,
  идемпотентность `data_assertion`).

### Changed
- **Шаблон персоны раздвоен по `death_year`** (решение R4): 26 персон с известным
  годом смерти получают мемориальный очерк, 242 — сухую карточку-реестр со
  ссылкой на политику персональных данных. Пустой `death_year` трактуется как
  «не установлено», а не «жив»; ни одна карточка-реестр не печатает дат смерти.
- Дисциплины выведены на карточку персоны; отнесения с уверенностью ниже 0,8
  помечаются знаком «(?)».

### Fixed
- **`data_assertion` больше не сирота.** Таблица создавалась только скриптом
  `scratch/provenance_audit_prototype.py` и выживала лишь потому, что `.db`
  закоммичен, — при этом `generate_site_data.py` безусловно читает из неё, так
  что сборка после `rm conferences.db` падала. Теперь `init_db` создаёт её через
  `CREATE TABLE IF NOT EXISTS` и никогда не дропает; сборка печатает громкое
  предупреждение, если 803 курируемые строки провенанса отсутствуют.
- **Риск P4 снят: расхождение 268/270 объяснено.** Коммит `52b05255f`
  (30-06-2026) пересобрал БД и в том же коммите поправил README: две курируемые
  склейки личностей плюс три переименования карточек-инициалов дают −5 +3 = −2.
  README уже был верен; устаревшие «270» вычищены из `ROADMAP.md`,
  `docs/ROADMAP_2026.md`, `docs/roster-merge-design.md`, `docs/wikidata-guide.md`
  и `docs/onboarding-zograf-contributor-ru.md`.

### Documentation
- Documented the scope decision that the PPV article remains a two-venue study
  of the main long-running Zograf and Roerich Readings, not a three-venue
  comparison.
- Added `docs/sementsov-readings-context-note.md` to classify Sementsov Readings
  as a newer, marginal contextual venue outside the measured corpus; the Paribok
  PDF is retained only as qualitative context, not row-level evidence.
- Renamed the docs index entry to `Семенцовские чтения вне корпуса / Sementsov
  Readings outside corpus`.

### Changed
- Added a manuscript-scope sentence to `article/ppv_submission_article.md`
  clarifying that newer and specialized initiatives, including Sementsov
  Readings, remain outside the corpus because the article is limited to the two
  main long-term venues.
- Refreshed Phase-5 roster audit artifacts without promoting unsupported
  candidates: `scratch/non_participants.md` now classifies
  Stal-fon-Golstein in the pre-2004 group, and
  `analytics_output/roster_participant_links.csv` no longer marks already
  present Q-IDs as pending injection.
- Synchronized public snapshot counts in README/development/cover-letter
  text to the validator-required 270 speaker profiles and 165 Zograf-only
  profiles.
- Recorded a follow-up Phase-5 retry: Wikidata and ru.wikipedia enrichment
  remain blocked on this host, so the next supported enrichment pass must run
  on a network where those endpoints are reachable.
- Added `docs/external-phase5-enrichment-runbook.md` with from-zero instructions
  for running the Wikidata/ru.wikipedia enrichment on an external reachable host.
- Added `tools/run_external_phase5_enrichment.py`, a one-command external-host
  runner for safe Phase-5 Wikidata/ru.wikipedia enrichment, validation, and
  optional source-only commit/push.

## [1.1.0] - 2026-07-14

_(Backfilled 14-07-2026, H790 changelog-backfill pass, Sonnet 5
(`claude-sonnet-5`) — real research/data deliverables merged since the H473
entry above that had no changelog record.)_

### Added
- **H484 Phase 2 — historical prosopography layer** (decision A1, variant A,
  [#79](https://github.com/gasyoun/IndologyScholars/pull/79)). Indologists who
  never presented at the Zograf/Roerich readings now load into the single
  `person` spine via a `person_kind` discriminator
  (`conference_participant` | `historical`) instead of a parallel
  `historical_person` table (would have broken roadmap R5); historical
  figures carry no `presentation_person` rows so every published
  speaker count stays 268. New `pipeline/historical.py` seeder from
  `curation/historical_persons.csv`; new
  `tools/resolve_historical_wikidata.py` pinned-QID resolver emits 26
  figures (all with `death_year` + sourced `data_assertion`) and 82
  `person_role` rows; 17 pre-1918 `RIND_` rows migrated (not duplicated).
- **D1 ruled** — the four proposed discipline codes
  (`literature`/`linguistics`/`ethnography`/`history_of_indology`) promoted
  `proposed`→`core` in `curation/disciplines.csv`
  ([#87](https://github.com/gasyoun/IndologyScholars/pull/87)).
- **A26 data paper** — re-verified every figure against committed data and
  completed the scholarly sections for Zenodo pre-staging
  ([H674](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H674-Fable_IndologyScholars_a26-data-paper-figures-verify.md),
  [#90](https://github.com/gasyoun/IndologyScholars/pull/90)): schema
  figures 10→19 tables (+ the new historical `person_kind` layer, 26
  figures), OpenAlex candidates 122→181 persons (496 rows),
  identifier-coverage table refreshed to 2026-07-11, network edge types
  5→6 (`organization_theme`), CSV exports 40+→100+; retargeted from
  *Journal of Open Humanities Data* to *Research Data Journal for the
  Humanities and Social Sciences* (Brill) per the locked authorship
  decision; added the dual-licensing statement (Apache-2.0 code / CC BY
  4.0 derived metadata), a data-availability statement, a name-heuristic
  false-positive limitation, and cross-model agreement figures (L1
  κ=0.670, argument-level κ=0.553) with the human-IRR caveat;
  `check_data_paper_numbers.py` machine-verified claims 10→19.
- **H829 — Nagari archive**: searchable archive + 20-year retrospective of
  the closed «Общество ревнителей санскрита» Google Group
  ([#93](https://github.com/gasyoun/IndologyScholars/pull/93)).
  Reproducible stdlib-only pipeline over the Google Takeout mbox dump
  (2005–2026): 18,729 messages, 2,928 threads, 2,333 members, 2,030
  attachments, 0 parse errors. `ingest.py` (mbox→SQLite+FTS5, diacritics
  folded), `insights.py` (4 analysis layers: timeline/activity,
  thread+co-participation networks, topic taxonomy + body NLP, Sanskrit
  terms + book index), `export_md.py` (per-thread Markdown mirror, 22
  year-folders), and a self-contained interactive HTML retrospective page
  (SVG charts, light/dark, client-side thread search).
- Mockups: landing-dashboard reskin in the "sustainable direction"
  (H660/H563 fan-out,
  [#88](https://github.com/gasyoun/IndologyScholars/pull/88)) — token-level
  CSS reskin (moss-and-clay light / system dark), non-destructive
  (`mockups/` only, live `index.html` untouched).

### Fixed
- **H496/H718** — internal link/anchor integrity + FAIR metadata pass
  ([#84](https://github.com/gasyoun/IndologyScholars/pull/84),
  [#92](https://github.com/gasyoun/IndologyScholars/pull/92)): fixed
  patronymic-suffixed surnames stealing the patronymic initial and the
  given-name-first key parse for `-вич`/`-вна` surnames; deleted the
  stale orphaned `gumilyov/level-0.html` page; remapped 5 dangling
  `slug_redirects.json` rows so old published scholar URLs redirect
  instead of 404ing; restored `location.hash` scroll-to-anchor after the
  `hypotheses.html` dynamic card render (33 deep links were landing at
  page top); added version + author ORCID to `CITATION.cff` and fixed a
  wrong-org repository URL.
- Fixed a build crash from a stale `normalized_key` for «Коссович» that had
  frozen deploys since H484/H496
  ([#83](https://github.com/gasyoun/IndologyScholars/pull/83)).
- Hardened the deploy pipeline: 4 pages 404ing were missing from the Pages
  artifact allowlist ([#81](https://github.com/gasyoun/IndologyScholars/pull/81));
  orphaned generated pages are now pruned via `git add -A`.
- `.gitignore` — scoped the `check_*.py`/`fix_*.py` ignore rule to
  `scratch/`/`article/` only, so equivalently-named tracked tool scripts
  elsewhere stop disappearing from `git status`.

## [1.0.1] - 2026-07-10

_(Backfilled 14-07-2026, H790 changelog-backfill pass, Sonnet 5
(`claude-sonnet-5`) — the pre-H473 window: 129 non-bot commits / 51 merged
PRs between the `v1.0.0` tag (2026-05-31) and the H473 commit (2026-07-10)
that had no changelog record at all. The `[1.0.0] - 2026-06-13` section
above only ever marked "released the current state as version 1" — it
documented nothing from the four weeks of work that actually followed it.
Dependency-bump PRs (#18, #22, #42, #43, #45, #46, #50) are omitted as
routine, matching the convention used for the other Tier-2 repos in this
handoff.)_

### Fixed
- **Statistical-methodology bugs in the survival/agreement analysis**
  ([#33](https://github.com/gasyoun/IndologyScholars/pull/33),
  [#34](https://github.com/gasyoun/IndologyScholars/pull/34),
  [#36](https://github.com/gasyoun/IndologyScholars/pull/36)): Kaplan-Meier
  now censors single-appearance scholars instead of treating them as
  duration-0 events (twice — the shared curve estimator, then
  `cohort_survival.csv` specifically); Cohen's-kappa bootstrap CI no longer
  returns a spurious 1.0 from degenerate resamples.
- **Security hardening** ([#24](https://github.com/gasyoun/IndologyScholars/pull/24),
  [#26](https://github.com/gasyoun/IndologyScholars/pull/26),
  [#27](https://github.com/gasyoun/IndologyScholars/pull/27),
  [#30](https://github.com/gasyoun/IndologyScholars/pull/30),
  [#32](https://github.com/gasyoun/IndologyScholars/pull/32)): fixed
  CodeQL high-severity alerts (names/gender no longer logged in the
  gender-inference QA report; a bad-tag-filter that caused `clean_html`
  data loss was rewritten and hardened); `scrape_wikidata.py` now verifies
  TLS certificates; Jinja autoescape enabled on page-render environments.
- **Data-pipeline correctness** ([#28](https://github.com/gasyoun/IndologyScholars/pull/28),
  [#29](https://github.com/gasyoun/IndologyScholars/pull/29),
  [#58](https://github.com/gasyoun/IndologyScholars/pull/58),
  [#59](https://github.com/gasyoun/IndologyScholars/pull/59),
  [#60](https://github.com/gasyoun/IndologyScholars/pull/60),
  [#68](https://github.com/gasyoun/IndologyScholars/pull/68)):
  `extract_infobox` now captures rows that carry attributes; a
  timeline-chunk drift traced to the rebuild bot never committing the
  chunks was fixed at the source; the INDOLOGY archive layer got a
  Python-3.11 metadata fix, malformed-mbox-header tolerance, a topic
  decade-heatmap fix, and an author topic-filter fix.
- Stopped committing the pickle NLP cache; normalized `.gitignore`
  ([#35](https://github.com/gasyoun/IndologyScholars/pull/35)). Removed
  dead log-rank p-value code in `work_appendix_g.py`
  ([#31](https://github.com/gasyoun/IndologyScholars/pull/31)).

### Added
- **Restored 3 unpushed `ai-wip` commits that existed only on a local
  machine** ([#23](https://github.com/gasyoun/IndologyScholars/pull/23)):
  gender-classification validation + tests
  (`tools/validate_gender_inference.py`), inter-rater reliability tooling
  (`tools/compute_interrater_agreement.py`, blind/key sample split), a
  data-paper number-check CI gate (`article/check_data_paper_numbers.py`),
  a shared Kaplan-Meier `_km_curve` estimator, persons-data-policy docs
  (RU+EN), and LOD knowledge-graph expansion
  (`indology_knowledge_graph.ttl`).
- **Phase 1 birth-year/affiliation research**
  ([#37](https://github.com/gasyoun/IndologyScholars/pull/37)–[#41](https://github.com/gasyoun/IndologyScholars/pull/41)):
  `docs/ROADMAP_2026.md`; recalibrated Phase 1 to treat birth years (not
  affiliations) as the real gap; birth-year auto-scouting found 0/39
  auto-resolvable with bias concentrated in ~6 recurring names; 22
  organization Q-IDs + 15 city geocodes added; 5 birth-year resolutions
  (2 new + 3 dedup-merges).
- **A25 submission checklist** ([#47](https://github.com/gasyoun/IndologyScholars/pull/47)–[#49](https://github.com/gasyoun/IndologyScholars/pull/49)):
  filled ORCID in the submission-render HTML + checklist, synced the HTML
  author block to the submitted `.md`.
- **INDOLOGY archive atlas** ([#51](https://github.com/gasyoun/IndologyScholars/pull/51)–[#57](https://github.com/gasyoun/IndologyScholars/pull/57),
  [#61](https://github.com/gasyoun/IndologyScholars/pull/61)): new
  `IndologyArchive` atlas tracked, published, linked from the portal, and
  cached in the PWA offline shell; a Renou classification layer added to
  the atlas data; a monthly archive updater; clickable Renou data
  downloads.
- **Dashboard + Renou conference layer** ([#62](https://github.com/gasyoun/IndologyScholars/pull/62)–[#67](https://github.com/gasyoun/IndologyScholars/pull/67)):
  dashboard CSV download links, clickable table entries (audited for
  coverage); the Renou classification layer extended to the main-site
  conference data with a cross-site (archive vs. conference) comparison.
- **A53 — Renou classifier precision audit (research finding, blocked)**
  ([#75](https://github.com/gasyoun/IndologyScholars/pull/75)):
  `generate_renou_layer.py`'s rule table anchors Latin alternatives with
  `\b` but leaves Cyrillic stems unanchored — `тика` (intended as *ṭīkā*)
  matches inside Эро**тика**/прак**тика**/семан**тика**/грамма**тика**,
  producing **85 of 116** `bhasya`-register matches as false positives
  (73%; every one inspected). Corpus-wide floor: **7.1%** of all 1,706
  conference matches are mechanically-detectable false positives — a floor,
  not an estimate, since the detector cannot see semantic errors. This
  blocks the archive-vs-conference Renou état-II/IV disciplinary-profile
  claim (365 vs 22 archive threads, 179 vs 321 conference) from publication
  until precision is measured per stratum. Registered as `A53`, blocked.
  Added `docs/renou-precision-audit.md`, `tools/build_renou_precision_sheet.py`
  (seeded, risk-stratified 150-item gold sample), and
  `tools/score_renou_precision.py` (per-stratum precision, Wilson 95% CIs).
  Recovered 418 lines of `Indology/indology_archive_research/insights.py`
  and 7 derived tables/figures that existed uncommitted on a stale local
  branch, one `git checkout` from being lost — re-applied source-only via
  `/branch-contention-recover`; corrected the GTD hub row that had
  mis-flagged that tree as disposable regen churn
  ([gasyoun/Uprava@950f030](https://github.com/gasyoun/Uprava/commit/950f030)).

### Engine
- `generate_publication_pages.py`'s `CITATION.cff` generator now reads the
  released version from `git describe --tags --abbrev=0` instead of a
  hardcoded `"1.0.0"` — found because the [1.1.0] bump above was silently
  reverted by the very next auto-rebuild commit
  ([`7de400187`](https://github.com/gasyoun/IndologyScholars/commit/7de400187)),
  which regenerates `CITATION.cff` from that same hardcoded template on
  every push.

## [1.0.0] - 2026-06-13

### Changed
- Released the current changelog state as version 1.

## [1.12.0] — 2026-06-10

### Сбор отметок голосования: «кто как проголосовал»

Страница `voting.html` остаётся статической (GitHub Pages не принимает данные),
но теперь у неё есть путь сдачи отметок преподавателю и инструмент сведения
ответов с привязкой к личности (email обязателен).

### Добавлено

*   **Кнопка «Отправить преподавателю»** в `voting.html` (генератор
    `generate_voting_page()`): требует email, копирует JSON отметок в буфер и
    открывает форму преподавателя. Адрес формы — константа
    `VOTE_TEACHER_FORM_URL` в `generate_publication_pages.py` (пустая = только
    копирование с подсказкой вставить JSON в форму). Рекомендованный приёмник —
    Яндекс Форма с полями email / имя / «JSON выгрузки».
*   **`tools/merge_votes.py`** — сводит выгрузки в таблицы «кто как проголосовал»:
    `analytics_output/votes/votes_by_talk.csv` (по докладу: сколько слушали/
    понравилось и поимённо кто + комментарии) и `votes_by_respondent.csv`
    (по студенту). Принимает папку `.json/.csv` выгрузок или CSV ответов
    Яндекс Формы (`--json-column "JSON выгрузки"`); дубли одного email по
    докладу схлопываются по последней выгрузке.

### Документация

*   `docs/voting-admin-collection-options.md` — реализованный путь (Яндекс Форма
    + кнопка + `merge_votes.py`).
*   `docs/how-to-vote-2026.md` — шаг «Отправить преподавателю» для студентов.

## [1.11.0] — 2026-06-10

### Слияние ростера индологов в корпус

Реализован дизайн `docs/roster-merge-design.md`: ростер русскоязычных индологов
(`scratch/`) влит в корпус — участники чтений обогащаются, неучастники
публикуются отдельным реестром, изолированным от конференционной статистики.

### Добавлено

*   **Реестр индологов вне программы — `indologists.html`:** новая страница
    (генератор `generate_registry_page()` в `generate_publication_pages.py`)
    с сортируемой таблицей 94 русскоязычных индологов, ни разу не выступавших
    на Зографских/Рериховских чтениях. Записи без подтверждённого источника
    помечены `(?)`. Подключена в навигацию, sitemap, валидатор и pages-артефакт.
*   **Кураторский источник `curation/non_participant_indologists.csv`** (94 строки,
    15 колонок). Сид-генератор `tools/build_non_participant_registry.py` —
    классифицирует ростер существующим матчером (`scratch/crossref_nonparticipants.py`),
    пишет неучастников с детерминированным `registry_id` (`RIND_<sha1>`,
    namespace не пересекается с `PERS_*`), неразрушающее слияние. Правило
    «не выдумывать»: `status=verified` требует непустого `source_url`
    (24 verified, 70 candidate).
*   **Линкер участников `tools/link_roster_participants.py`** — сопоставляет
    100 участников-индологов с `person_id`, пишет
    `analytics_output/roster_participant_links.csv` и инжектит Wikidata Q-ID в
    `authority_ids.json` с `confidence='candidate'` (2 новых Q-ID; годы рождения
    выводятся для ручной сверки, не применяются автоматически).
*   **Тесты `tests/test_non_participant_registry.py`** (10): схема реестра,
    уникальность/детерминизм `registry_id`, изоляция namespace, гард
    «участник не попадает в реестр», неизменность числа докладчиков (270),
    ссылочная целостность линков. Всего pytest 70/70.

### Документация

*   **`docs/ru-enrichment-runbook.md`** — runbook Phase 5 (запуск изнутри РФ):
    таблица достижимости, шаги Wikidata-обогащения годов жизни, ru-инфобоксов,
    Playwright-скрапинга институтов, OpenAlex, идемпотентного пересева реестра,
    rebuild/validate/commit.
*   `docs/roster-merge-design.md` — статус «implemented», карта реализации,
    разрешённые open-questions (URL `indologists.html`, `RIND_<sha1>`,
    имперский период в общем реестре).
*   `docs/development.md` / `development-en.md` — runbook в таблице техдокументов.
*   `ROADMAP.md`, `.ai_state.md` — отметка о реализации.

### Исправлено

*   **Идемпотентность пересева реестра (Phase-5 гард):**
    `tools/build_non_participant_registry.py` теперь дедуплицирует не только по
    `registry_id`, но и по нормализованному имени. Поскольку `registry_id`
    включает год рождения, обогащение, заполняющее пустой год, иначе
    перехешировало бы человека в новый id и добавило дубль. Новый тест
    `test_no_duplicate_names_in_registry` (pytest 71/71).

## [1.10.0] — 2026-06-10

### Интернационализация, контроль авторитетов и LOD

Трек после подачи ППВ: связать корпус с международной инфраструктурой
(Wikidata, OpenAlex, ORCID), подготовить англоязычный data paper и заморозить
снимок для DOI. **Актуальный корпус: 270 учёных, 1362 уникальных доклада,
1388 авторских участий, 2004–2026, 41 учёный перекрёстной когорты, 165 только
Зографских, 64 только Рериховских** (`site_data_summary.json`, 2026-06-04).

### Добавлено

*   **Сбор русскоязычных индологов за ~200 лет (`scratch/`-подпроект, HEAD-коммит):**
    самостоятельный модуль ростера русскоязычных индологов и кросс-сверки с
    участием в Зографских/Рериховских чтениях. **197 индологов** (114 из
    вики-категорий + en.wiki-моста, 83 из базы конференций), Q-ID-покрытие
    выросло с 8 до 26, **60 тестов** проходят. Скраперы: `enwiki_bridge.py`
    (RKN-устойчивый путь en.wikipedia → ru-название + Wikidata Q-ID, режим
    `--wide` по советским/российским ориенталистам), `expand_wikipedia_indologists.py`
    (неразрушающее слияние, реальный `search_via_html()`), `wikidata_enrich.py`
    (Q-ID → годы жизни через REST `Special:EntityData`), `scrape_institutions_web.py`
    (static → Drupal JSON:API → Playwright), `scrape_common.py` (общий
    retry/backoff HTTP + кэш + atomic writes). Собственные `scratch/roadmap.md`,
    `scratch/changelog.md`, `scratch/ai_status.md`, `scratch/handoff.md`.
*   **Сопоставление авторов с OpenAlex:** `scratch/openalex_author_candidates.py`
    + `scratch/resume_openalex.py` (возобновляемый обход) опрашивают OpenAlex
    Authors API по кириллическому ФИО и латинской транслитерации, скорят
    кандидатов (RU-аффилиация +0.4, совпадение фамилии +0.2, ≥3 работы +0.2)
    и пишут `analytics_output/openalex_author_candidates.csv` — **122 учёных
    с ≥1 кандидатом, статус ручной сверки `todo`**.
*   **Инъекция авторитетов:** `tools/inject_openalex_matches.py` переносит
    высокоуверенные (≥0.8) совпадения в `authority_ids.json` с
    `confidence='candidate'` (никогда `confirmed` без ручной сверки), доставая
    ORCID/Wikidata из ответа OpenAlex.
*   **Wikidata QuickStatements:** `tools/generate_wikidata_batch.py` отбирает
    топ-N учёных по числу докладов без Q-ID и генерит v2-батч
    (`analytics_output/wikidata_batch.txt`) с ISO-9-транслитерацией латинских
    имён: P31 (человек), P106 (индолог), P101 (индология), P569, P27, P108 и
    референс `S854` на страницу профиля. Руководство — `docs/wikidata-guide.md`.
*   **Англоязычный data paper:** `article/data_paper_draft.md` — описание
    корпуса (модель данных, происхождение полей, классификация L1/L2 + G1–G3,
    видео-привязки, авторитетные идентификаторы, форматы SQLite/CSV/JSON/RDF,
    Frictionless Data Package). **Целевой журнал — Research Data Journal for
    the Humanities and Social Sciences (Brill).**
*   **Linked Open Data:** перегенерирован `indology_knowledge_graph.ttl`
    (`generate_lod.py`) с Wikidata Q-ID для городов и тем.
*   **Wikidata Q-ID в гео-данных:** `assets/data/geography.json` дополнен
    Q-ID для городов и тематических рубрик.
*   **Inter-rater reliability:** `tools/build_interrater_sample.py` +
    `tools/compute_interrater_agreement.py` (+ `build_classification_reliability_sample.py`)
    — выборка и расчёт согласованности для классификации.
*   **Замороженный снимок для DOI:** `tools/freeze_article_data.py` создаёт
    `article/snapshots/2026-06-03/` под депозицию.
*   **Пример анализа:** `notebooks/example_analysis.py` — воспроизводимый
    разбор корпуса для внешних исследователей.

### Документация

*   `CLAUDE.md` дополнен: Wikidata Q-ID в `geography.json` (п. 4), раздел
    интернационализации данных (п. 6: wikidata-guide, data paper, notebook),
    снимок для DOI и inter-rater инструменты (п. 7).
*   **`docs/roster-merge-design.md`** — дизайн слияния ростера русскоязычных
    индологов в корпус: участники обогащаются (Q-ID, годы жизни) без
    дублирования person-строк, неучастники публикуются отдельной
    страницей-реестром, изолированной от конференционной статистики.
*   `docs/development.md` / `development-en.md` — новый раздел
    «Интернационализация и контроль авторитетов» + регистрация wikidata-guide,
    data paper и дизайна слияния в таблице техдокументов.
*   `data_dictionary.md` — `openalex_author_candidates.csv`, `wikidata_batch.txt`
    и `indology_knowledge_graph.ttl` добавлены в раздел Authority Outputs.
*   `ROADMAP.md`, `.ai_state.md`, `CHANGELOG.md` — данная запись.

### Исправлено

*   **`tools/generate_wikidata_batch.py` — неверные Q-ID и структура источника.**
    `Q8088479` оказался вообще не «индологией», а служебной категорией
    `Category:1198 establishments`. Исправлено: `P106 (род занятий)` →
    `Q18524037` (профессия «индолог»), `P101 (область деятельности)` →
    `Q625510` (область «индология»). Удалён фиктивный `P248 stated-in`
    `Q126692818` (на деле — видеоигра 2024 г.); страница профиля теперь
    цитируется как **референс** `S854` на ключевых утверждениях (а не как
    отдельные statement-ы `P248`/`P854`). `P108 (работодатель)` больше не
    получает строковых значений в item-поле — статья пишется только при
    наличии Q-ID, дубли работодателя дедуплицируются. Батч перегенерирован.
    Отправка в QuickStatements — по-прежнему только после ручной сверки
    122 кандидатов.
*   **`tools/inject_openalex_matches.py`:** выход с ошибкой при отсутствии
    `requests` (раньше падал позже); `checked_at` теперь проставляется
    текущей датой, а не зашитой `2026-06-03`.

## [1.9.2] — 2026-06-02

### Pre-submission gate (ППВ) — финал

*   **Статья готова к подаче:** 35 195 знаков, 0 drifts, обезличенная копия синхронизирована,
    `check_anonymity.py` passed, cover letter обновлён. Закрыты issues #19 (баг соавторов),
    #20 (генеалогические связи), #21 (caveat программ + описания рисунков).

### Добавлено

*   **Генеалогический граф в networks.html:** 20 teacher-student edges из `teacher_student.csv`
    встроены в `network_data.json` через `generate_network_json.py`. Новый пресет
    «Генеалогия» в networks.html с зелёным dashed-стилем. Секция «Генеалогия» в боковой
    панели при клике на учёного.
*   **Аудит city-to-institution:** `tools/city_trajectory_audit.py` — 719 city-меток
    проанализированы, 165 (22.9%) сопоставлены с институцией (±3 года), 554 (77.1%)
    остаются непрозрачными. Выводы подтверждают тезис статьи об аффилиационной непрозрачности.
    `analytics_output/city_trajectory_audit.csv` + `city_trajectory_summary.csv`.
*   **Парсер Перечня ВАК:** `tools/vak_parser.py` — читает Excel-файл ВАК, фильтрует
    филологию (5.9.x / 10.01.x), генерит `editors/<journal>.md` профили. Вход: `.xlsx`,
    выход: `analytics_output/vak_journals.csv` + профили журналов.
*   **Скрапер дат рождения:** `tools/scrape_birth_years.py` — обходит Wikipedia,
    Dissercat, eLIBRARY и институциональные сайты в поиске годов рождения.
    `tools/apply_birth_years.py` — применяет находки к БД через `data_assertion`.
*   **План выноса модуля агентов:** `philology-research-agents/SPINOUT_PLAN.md` —
    3-фазный план: Python-оркестратор на Anthropic SDK → отдельный репозиторий →
    англоязычный пример + CI.

### Изменено

*   **Сайт/UX — 6 правок:**
    *   `positionTooltip()` helper — tooltip clamp на всех визуализациях (scatter, geo,
        bubble, arc, hierarchy, forest, heatmap, alluvial, opacity).
    *   Клик по городу на карте аффилиаций → страница города (`cities/{slug}.html`).
    *   `.profile-facts` CSS — 3-колоночная горизонтальная вёрстка (Аффилиации/Города/Статусы).
    *   «Соавторы (0)» скрыты (уже было реализовано).
    *   «засвидетельствованный профиль» для 1 доклада (уже было реализовано).
*   **Статья ППВ:** добавлен caveat о расхождении программ и факта (офлайн→онлайн, отмены);
    добавлены inline-ссылки на рисунки (рис. 1, 4, 5, 6, Г1); расширены подписи к
    иллюстрациям с пояснениями для нематематиков.
*   **`docs/tmp*` → `.gitignore`:** авторские рабочие заметки исключены из трекинга.
*   **Пересборка БД:** `conferences.db` пересобрана с нуля, 270 учёных, 1362 доклада.
    `generate_network_json.py` расширен инъекцией генеалогических рёбер.

### Документация

*   `ROADMAP.md` полностью переписан: NOW → ✅, NEXT обновлён с детальным статусом,
    добавлена таблица новых инструментов.
*   `CHANGELOG.md` — данная запись.

## [1.9.1] — 2026-06-01

### Изменено

*   **Структурирование внесетевых связей (Curation Curation)**:
    *   Добавлен темпоральный столбец `temporal` в `curation/known_relationships.csv`, в схему `generate_publication_pages.py`, `datapackage.json` и `data_dictionary.md`.
    *   Все временные/статусные маркеры (`"сначала"`, `"затем"`, `"ранее (взаимодействие завершено)"`) перенесены из типов/ярлыков связей в новый структурированный столбец `temporal`.
    *   Ярлыки связей стандартизованы (например, `"ученица сначала"` / `"ученица затем"` приведены к `"ученица"`), а `"раньше работал на"` исправлено на `"работал у"`, чтобы отделить смысловую связь от её временного состояния.
    *   Статусы сомнительных или требующих источника связей (`needs_source`) переведены в подтверждённые (`confirmed`) на основании прямого указания редактора, с соответствующим основанием `"Согласно редактору"`.
    *   Интерактивная таблица на странице [known-relationships.html](known-relationships.html) дополнена новой колонкой «Период / время».

## [1.9.0] — 2026-06-01

### Добавлено

*   **Внесетевые связи (Known Relationships)**: добавлены `curation/known_relationships.csv` (межличностные и академические связи) и интерактивная страница [known-relationships.html](known-relationships.html) для отображения межличностных отношений, не выводимых напрямую из сети соавторства/соприсутствия.
*   **Верификация выпускников Восточного факультета СПбГУ**: добавлен воспроизводимый кураторский фильтр `curation/eastern_faculty_alumni.csv` и скрипт генерации кандидатов [tools/extract_eastern_faculty_alumni.py](tools/extract_eastern_faculty_alumni.py).
*   **Двуязычная социология и гейткипинг**: реализованы полноценные английские версии аналитических страниц `sociology-en.html` и `gatekeeping-en.html` для внешнего рецензирования.
*   **Отметки слушателя по докладам**: создана статичная страница [voting.html](voting.html) для клиентского ведения локальных отметок «прослушано» (heard) и «понравилось» (liked) с выгрузкой в CSV/JSON.

### Изменено

*   **Редакционная и доказательная политика**: добавлены русский [docs/sociology-gatekeeping-editorial-decisions-ru.md](docs/sociology-gatekeeping-editorial-decisions-ru.md) и английский [docs/sociology-gatekeeping-editorial-decisions.md](docs/sociology-gatekeeping-editorial-decisions.md) мета-документы, фиксирующие стандарты доказательности, правила именования людей и разведение механизмов отсутствия (после 2022 и в 2026 гг.).
*   **Обновление документации**:
    *   [data_dictionary.md](data_dictionary.md) расширен описанием `known-relationships.html`, `voting.html` и новыми кураторскими таблицами.
    *   [docs/development.md](docs/development.md) и [docs/development-en.md](docs/development-en.md) обновлены: добавлены разделы по внесетевым связям и верификации выпускников, а также новые скрипты и документы в карты путей.
    *   [docs/README.md](docs/README.md) дополнен ссылками на новые редакционные регламенты.

## [1.8.9] — 2026-05-29

### Добавлено

*   **Модуль `philology-research-agents/`**: портативный пакет из шести агентов-промптов для доказательной работы в филологии, языкознании и востоковедении. Содержит шесть журнальных профилей редактора (ППВ, IIJ, ВДИ, ВЯ, JAOS, OLZ), Haiku-промпт для парсинга Перечня ВАК с выводом в CSV/JSON, общий блок шкалы доказательности A–E под филологию и рабочий пример прогона. Модуль самодостаточен и спроектирован для выноса в отдельный репозиторий.
*   **Генеалогический трек (issue #9)**: введены `curation/teacher_student.csv` (курируемые связи руководитель/ученик), `curation/teacher_student_schema.md` (двенадцатиколоночная схема с правилом «не выдумывать»: `status=verified` требует `evidence_url`), `pipeline/genealogy.py` (загрузчик с построчной валидацией) и `article/work_lineage_candidates.py` (эвристический генератор кандидатов по со-авторству и возрастному разрыву). Загрузчик пока не подключён к `site_data.json` — отдельный шаг.
*   **Анонимная копия статьи**: `article/ppv_submission_article_anonymous.md` — submission-вариант без шапки автора и без пред-УДК черновика, для двойного слепого рецензирования; 0 author-маркеров, числа синхронизированы с основной версией.
*   **`ROADMAP.md`**: интегрированный дорожный документ Now / Next / Later со связями на GitHub-issues (метка `roadmap`).

### Изменено

*   **`article/check_ppv_numbers.py` переработан**: hardcoded список замен (привязанный к очень старым числам 220/895) заменён на phrase-based динамическую сверку. Используются регулярные выражения по каждой метрике (агрегаты, серия-уровень, цензурированный 2025-блок, Зографские чтения 2026 г., G1/G2/G3); снапшот расширен полями `g_levels`, `events`, `program_years`, `cross_cohort_pct` из `expanded_classification_deepseek.csv`; ненулевой код возврата при любом расхождении блокирует pre-submission gate.
*   **Числа `article/ppv_submission_article.md` синхронизированы с пересобранной БД**: 286 → 270 уникальных учёных, 1350 → 1351 доклад, 1377 → 1378 авторских участий, 1155 → 1156 G1-микрокейсов; серия-уровень (Зограф 221→206 / 878→879 / 900→901; Рерих 106→105; производное 327→311); доли разовых, доли ядра, удержания и индексы Джини на серии и в общем; полный цензурированный блок «по 2025 г.» (202→187, 820→821, 839→840, 32.2%→35.8%, 42.6%→36.9%, 57.4%→63.1%, 0.521→0.510).
*   **Метаданные автора EN в `ppv_submission_article.md`**: заполнены три прочерка `____` (ученая степень → Candidate of Sciences in Philology; рабочий адрес → Usacheva St. 21-285, Obninsk, Kaluga Oblast, 249030, Russia; ORCID → 0000-0003-4513-884X); исправлен ошибочный город «Moscow» → «Obninsk».
*   **`article/ppv_cover_letter.md` приведено в соответствие со статьёй**: title заменён на точное соответствие («Двадцать лет российской индологии: Зографские и Рериховские чтения (2004–2026)»), числа 895/220 → 1351/1378/270, город автора «Москва» → «Обнинск», плейсхолдеры степени, ORCID и даты заполнены, удалена ссылка на «анализ дожития когорт» (метод не вошёл в submission-версию), снят устаревший хедж «Научная жизнь / обзорно-аналитическая» (объём 36 005 знаков укладывается в категорию «статья»).

### Документация

*   `README.md`, `README_EN.md`, `docs/development.md`, `docs/development-en.md`: обновлён публичный снапшот под пересобранную БД (270 профилей / 1351 доклад / 1378 авторских участий / 165 только Зографских / 64 только Рериховских, дата 29 мая 2026 г.); карта файлов `philology-research-agents/README.md` показывает все шесть редакторских профилей.
*   `docs/development.md` и `docs/development-en.md` расширены: новая подсекция «Сверка чисел статьи / Article numbers consistency» в разделе валидации, новая секция «Генеалогический трек / Genealogy track», строка модуля `philology-research-agents/` в таблице технических документов.

### Pre-submission gate (ППВ)

*   Все технические компоненты гейта зелёные: `validate_publication.py` passed, `pytest` 44 passed, `check_ppv_numbers.py` 0 расхождений, объём статьи 36 005 знаков в пределах лимита категории «статья» (≤ 40 000), 8 иллюстраций ≥ 300 dpi + список подписей подтверждены. Закрыты восемь связанных issues: #3 ссылочный аппарат, #4 аннотации и ключевые слова, #5 метаданные автора, #6 обезличивание, #7 пересборка БД и сверка чисел, #8 pre-submission gate, #11 валидатор sitemap-индекса, #12 сверка чисел и harden `check_ppv`. Дополнительно закрыт #10 (четыре стартовых редакторских профиля модуля).

---

## [1.8.8] - 2026-05-27

### Оптимизация и тестирование (Фазы 5 и 6)

*   **Сверка чисел в статье ППВ**: Проведена автоматическая сверка актуальных статистических метрик в базе данных `conferences.db` со статьей `ppv_submission_article.md`. Зафиксировано 0 расхождений.
*   **Тесты схемы данных**: Добавлен новый набор тестов `tests/test_site_data_schema.py` для контроля целостности JSON-схемы `site_data_summary.json` и синхронности чанков по годам.
*   **Очистка репозитория**: Удалено 13 устаревших отладочных скриптов (`fix_*.py` и `check_*.py`), а маски для аналогичных временных файлов внесены в `.gitignore`.
*   **Очистка сборки (`make clean`)**: В Makefile добавлен кроссплатформенный Python-сценарий для очистки производных сборочных HTML-страниц и JSON-файлов.
*   **Lazy-load поискового индекса**: Оптимизирована страница `search.html` — загрузка тяжелого индекса `search-index.json` (1.1 MB) теперь происходит только по фокусу на поисковую строку, клику или вводу запроса, снижая первоначальный объем загружаемых данных на мобильных устройствах.
*   **Тесты нормализации заголовков**: Реализован тестовый файл `tests/test_title_normalization.py` для предотвращения регрессий в механизмах очистки названий докладов (удаление пометок онлайн/зум, времени начала, нормализация регистров собственных имен).

---

## [1.8.7] - 2026-05-27

### Интерфейс архива и визуализация

*   **Ускоренный таймлапс на пустых датах (`spacetime.html`)**: Переработан механизм автовоспроизведения (play) с переходом на динамический таймаут. Периоды времени без докладов автоматически пролистываются в 6 раз быстрее (200 мс вместо 1200 мс). Обеспечено синхронное обновление списка докладов внизу и точек на карте на каждом шаге.
*   **Римская нумерация рубрик в хронике (`spacetime-timeline.html`)**: Внедрена автоматическая привязка римских порядковых номеров (от `I` до `XX`) ко всем историческим рубрикам. Порядковый номер теперь отображается рядом с именем рубрики в левой колонке (например, `... (III)`) и стилизован с помощью специального CSS-класса `.roman-numeral` (зеленый акцентный цвет, полужирное начертание, шрифт с засечками Georgia).

---

## [1.8.6] - 2026-05-25

### Документация

*   `README.md` сделан основным русским пользовательским описанием коллекции; инструкции для сборки из него вынесены.
*   Добавлены параллельные пользовательская и техническая английские версии: `README_EN.md` и `docs/development-en.md`; русская техническая версия находится в `docs/development.md`.
*   Технический аудит классификации перенесен в документацию разработчика и снабжен английской версией; руководство проверки РИНЦ также доступно на двух языках.
*   Устаревшие входные документы и датированные планы теперь явно ссылаются на актуальные руководства и не представляются как текущая публикационная сводка.
*   Датированные планы, старые session-state/handoff-файлы, прежний аналитический снимок и временные отладочные выгрузки перемещены в `archive/`; Pages-артефакт теперь включает обе версии README и актуальный каталог документации.

### Интерфейс архива

*   Главная страница переведена на спокойную рабочую композицию: каталог, фильтры и результаты доступны в первом экране, а метрики и выводы следуют ниже.
*   На мобильных экранах каталог отображается карточками без горизонтального переполнения; фильтры снабжены подписями, вкладки поддерживают доступное переключение.
*   Общая оболочка публикационных страниц получила компактную навигацию и нейтральную палитру; отдельный поиск показывает число результатов и сохраняет запрос в URL.
*   Техническая формулировка об аудите классификации больше не возвращается на публичную главную при пересборке сайта.

---

## [1.8.5] — 2026-05-25

### Добавлено

*   Общий слой публичной нормализации метаданных: городские пометы больше не выдаются за институциональные аффилиации, а подтвержденные траектории применяются только в указанном временном интервале.
*   Реестр датированных подтвержденных аффилиаций `curation/verified_affiliation_spans.csv`; первым зафиксирован непрерывный интервал С. С. Тавастшерны в СПбГУ, на Восточном факультете.
*   Короткая плашка `Видео` на карточках и отдельных страницах докладов, для которых сопоставлена сохранившаяся запись.

### Исправлено

*   Общая защита от попадания начальной институциональной пометы в публичное название доклада: конструкция вида `(СПбГУ). Название` публикуется как аффилиация и чистое название.
*   Публичное название доклада М. Ю. Гасунса 2006 г. нормализовано до `«Дхатупатхе»` с явным примечанием о форме `«Дхатупати»` в официальной программе.
*   Видеоархив сохранен как самостоятельный раздел, пункт навигации, поисковый слой и часть sitemap; статус `Видео` дополняет, а не заменяет каталог записей.
*   На главной и странице выводов показана редакционная пауза: выводы статьи относятся к корпусу `220 / 895 / 899`, тогда как расширенный каталог сайта уже содержит `289 / 1350 / 1377` и требует нового расчета гипотез.

---

## [1.8.4] — 2026-05-25

### Добавлено

*   Отдельная страница `classification-criteria.html` с обновленными критериями тематических рубрик, мезоуровней и уровней аргумента L1-L3, а также публичный журнал экспертных решений `analytics_output/classification_overrides.csv`.
*   Постоянные HTML-страницы для каждого доклада в каталоге `presentations/`, доступные из поиска, конференций и тематических подборок.

### Исправлено

*   Восемь проверенных докладов Зографских чтений 2024 г. переклассифицированы по дисциплине, мезосериям и масштабу аргумента: частные кейсы больше не принимаются за региональное обобщение только из-за географического маркера.
*   Слово `Онлайн` исключено из публичных названий докладов и отображается как самостоятельная метка формата.
*   Карточки докладов теперь показывают мезоуровни и ведут на индивидуальные страницы с обоснованием экспертной классификации.

---

## [1.8.3] — 2026-05-24

### Добавлено

*   Страница `generations/` с поименным распределением по десятилетиям рождения: когорта Василькова (1940-е), когорта Толчельникова (2000-е) и отдельная группа участников без проверенного года рождения.
*   Метаданные официального обновления программы (`Последнее обновление`) на годовых страницах конференций, включая Зографские чтения 2023 г. (`22.05.2023`).

### Исправлено

*   Парсер восстановил пропущенные и склеенные записи программ, включая два доклада М. Ю. Гасунса из Обнинска (2023, 2024), переносы строк 2022/2026 гг. и соавторские строки без аффилиации.
*   Исключены ложные докладчики, возникавшие из имен и биографических дат внутри заголовков; исправлена ошибочная подстановка Пушкаревой как Коковой.
*   Актуальный корпус сайта: **289 участников, 1350 уникальных докладов, 1377 авторских участий**, 40 участников обеих площадок, 183 только на Зографских и 66 только на Рериховских чтениях.
*   Подачная статья помечена как требующая повторной разметки расширенного корпуса; прежние численные выводы больше не считаются готовыми к подаче.

---

## [1.8.1] — 2026-05-24

### Добавлено

*   Страницы именованных сюжетов `topics/ramayana.html` и `topics/mahabharata.html` с устойчивыми URL, списком явных упоминаний в названиях докладов, годами, авторами и ссылками на программы.
*   Поиск по названиям докладов на главной теперь сохраняет запрос в URL (`?talks=...`) и раскрывает найденные доклады, а не только строки участников.

### Исправлено

*   Публичное отображение названий нормализует написание имен собственных: `Рамаяна`, `Махабхарата`, `Индия` в соответствующих падежах.
*   Склеенный фрагмент программы Зографских чтений 2023 г. больше не создает ложного тематического совпадения для Рамаяны.

---

## [1.8.0] — 2026-05-24

### Добавлено

*   **Опция 4: Сплошное демографическое обновление рукописи:**
    *   Спектр возраста и биографий расширен до 100% покрытия: решено **0 отсутствующих дат рождения** среди всех 220 ученых архива.
    *   В рукопись статьи [ppv_draft.md](file:///c:/Users/user/Documents/GitHub/IndologyScholars/article/ppv_draft.md) интегрирован сплошной демографический анализ, опровергнувший селективное завышение старения (реальная медиана Зографа-2025 составила **47.5 лет** вместо 55).
    *   Статистически доказано омоложение входа новых исследователей на сплошном массиве когорты ($\rho = -0.19$, $p = 0.0048$; Краскел-Уоллис $p = 0.0199$).
    *   Переписана и дополнена таблица Приложения А (38 ученых перекрестного ядра) и методологическая сноска 2.
    *   Скомпилированы обновленные форматы рукописи [ppv_draft.html](file:///c:/Users/user/Documents/GitHub/IndologyScholars/article/ppv_draft.html) и [ppv_draft.docx](file:///c:/Users/user/Documents/GitHub/IndologyScholars/article/ppv_draft.docx).

*   **Опция 3: Интерактивная визуализация сетей связей (Vis.js UX Upgrade):**
    *   Создан JSON-компилятор [generate_network_json.py](file:///c:/Users/user/Documents/GitHub/IndologyScholars/generate_network_json.py) для упаковки CSV-экспортов сети (266 узлов, 4704 ребер) в компактный [network_data.json](file:///c:/Users/user/Documents/GitHub/IndologyScholars/analytics_output/network_data.json).
    *   Разработан премиальный интерактивный интерфейс [networks.html](file:///c:/Users/user/Documents/GitHub/IndologyScholars/networks.html) на базе Vis.js с быстрыми пресетами (Коллаборации, Экосистема, Соприсутствие, Участие), динамической фильтрацией связей/узлов, мгновенным поиском ученых, интерактивным сайдбаром деталей со ссылками на профили.
    *   Устаревший Canvas-рендер на главной [index.html](file:///c:/Users/user/Documents/GitHub/IndologyScholars/index.html) полностью переведен на Vis.js, добавлена двуязычная локализация и адаптивный тизер с прямой ссылкой на полную интерактивную сеть.
    *   Интегрирован предохранитель в сборочный пайплайн [generate_publication_pages.py](file:///c:/Users/user/Documents/GitHub/IndologyScholars/generate_publication_pages.py), предотвращающий автоматическую перезапись `networks.html` стандартным шаблоном.

---

## [1.7.2] — 2026-05-24

### Исправлено

*   Синхронизированы базовые числа сайта, статьи и документации: 220 учёных, 895 уникальных докладов, 899 авторских участий, 38 участников перекрестной когорты, 129 только в Зографских чтениях и 53 только в Рериховских.
*   `article/ppv_draft.md` обновлена до версии 0.7: пересчитаны метрики закрытости, таблицы доверительных интервалов, приложение А и формулировки выводов.
*   `article/check_ppv_numbers.py` обновлён под текущие контрольные значения и теперь выводит совмещённые метрики корпуса.

---

## [1.7.1] — 2026-05-21 (вечер)

### Добавлено

**Статья (`article/ppv_draft.md`) — заполнение приложений:**
*   **Приложение Б** — сводная статистика по 20 годам (2004–2026): % дебютантов и медианный возраст по каждой серии. Спайслено из `article/ppv_draft_appendix_b.md`. Ключевая тенденция: дебютанты обрушились со 100% (2004) до 10–11% (2021–2022) при росте медианного возраста до 57–59 лет (2025–2026); рекурренция дебютантов в 2025–2026 (Рерих 38.9%, Зограф 31.7%) требует комментария.
*   **Приложение В** — 3 сводные таблицы (L1 дисциплина, L2 период, L4 характер) + репрезентативная выборка из 30 докладов с уверенностью ≥ 0,8. Полный CSV-список из 895 кодированных записей передан в редакцию как `article/supplementary_theme_codes.csv`.
*   **§7 сноска ^2^** — методологический отказ от OpenAlex first-publication-year proxy для оценки года рождения: опыт показал систематическое занижение на 30–50 лет для учёных с советским стажем (база не индексирует публикации до ~2010 г.). Эксперимент задокументирован в `scratch/fetch_openalex_birthyears*.py` как archive.

**Восстановление CI/Deploy конвейера** (был сломан на ≥15 коммитах подряд, начиная с ~2026-05-19):
*   `requirements.txt` создан (`requests`, `beautifulsoup4`, `pypdf`) — без него `actions/setup-python@v5` с `cache: 'pip'` падал до выполнения любого Python-шага.
*   `validate_publication.py` сделан slug-redirect-aware: следует `<link rel="canonical">` от страниц-редиректов к slug-страницам, проверяет, что целевой slug существует. Раньше любая PERS_<hash>.html, ставшая редиректом по slug-переименованию, считалась «отсутствующей канонической страницей» и валила сборку.
*   `environment: github-pages` объявлен на deploy-job (требование `actions/deploy-pages@v4`).
*   `pypdf` добавлен в зависимости — `build_and_populate_db.py` без него молча пропускал `html_cache/zograf_2026.pdf` и недополучал 17 учёных / 60 докладов.

**Очистка наследия:**
*   `legacy_redirects.json` обнулён: 7 PERS_<hash>-редиректов, оставшихся от прошлых dedup-слияний, удалены. Валидатор больше не «прощает» orphan-канонические страницы — любая будущая орфанная PERS_<hash>.html завалит проверку.

**Авто-патч `index.html` для краулеров и no-JS читателей:**
*   `generate_publication_pages.py` теперь в конце `main()` вызывает `patch_index_stats(data)`. Функция через regex обновляет четыре `#stat-*-count` блока (учёные, доклады, годы, ядро), описание `stat-years-desc`, а также годовые диапазоны (`(2004–YYYY гг.)` и английский вариант) в meta description, sub-heading и заголовках графиков. До этого `index.html` содержал жёстко зашитые числа 188/707/22/30/2025; JS заменял их при загрузке из `site_data.json`, но краулеры без JS-исполнения (Yandex, social-card scrapers, WebFetch) видели старые значения.
*   `index.html` добавлен в `git add` workflow-а, чтобы бот коммитил пропатченную версию.

**Интеграция YouTube-статистики (172 видео):**
*   Добавлена пятая карточка на главной странице (`#card-youtube`) с числом видеозаписей Зографских чтений на YouTube. Источник — `analytics_output/youtube_playlist_summary.csv` (2023: 68, 2024: 56, 2025: 36, дополнительная подборка: 12).
*   `patch_index_stats()` расширен: читает CSV, суммирует и инлайнит число в `#stat-youtube-count`. При отсутствии CSV карточка остаётся со значением по умолчанию 172.
*   В статье обновлён §4.4: вместо «более ста единиц видеозаписей» теперь приведены точные цифры (68/56/36 по основным плейлистам + 12 в дополнительной подборке = 172) и зафиксирована тенденция к сокращению охвата (68→56→36 за 2023–2025).
*   Удалён `analytics_output/youtube_stats.csv` (содержал только error-стабы от неудачной попытки автоматического скрейпа); рабочие данные были и остаются в `analytics_output/youtube_playlist_summary.csv`.
*   `article/ppv_corr.md` (рабочий список авторских правок) добавлен в `.gitignore`.

**Конвейер per-lecture YouTube-привязок (заготовлен; готов к запуску при наличии API-ключа):**
*   `scratch/youtube_fetch_videos.py` — ручной запуск, читает `YOUTUBE_API_KEY` из `.env`, обходит YouTube Data API v3 (`playlistItems.list`) по каждому плейлисту из `youtube_playlist_summary.csv`, выгружает `analytics_output/youtube_video_list.csv` (один ряд на видео: id, url, title, year, position, published_at). Бюджет квоты ~16 единиц на полный обход; бесплатный лимит — 10 000 единиц/сутки.
*   `scratch/youtube_match_videos.py` — нечёткое сопоставление заголовков видео с докладами текущей БД (`difflib.SequenceMatcher`, без внешних зависимостей). Пишет `analytics_output/video_presentation_mapping.csv` с колонками `video_id, video_url, video_title, year, title_hint, speaker_hint, similarity, status, presentation_id_snapshot`. Маппинг ключуется по *естественным* признакам (year + title_hint + speaker_hint), а не по `presentation_id`, поскольку последний переcоздаётся как `uuid.uuid4().hex[:8]` на каждой сборке.
*   `build_and_populate_db.py:ingest_video_media()` запускается в каждой сборке: для строк со статусом `auto` / `manual_confirmed` повторно ищет лучшее соответствие в текущей БД и вставляет запись в таблицу `media` (`attached_to_type=presentation`, `media_type=video`, `media_url=YouTube URL`).
*   `generate_site_data.py` подтягивает медиа per-presentation в массив `talks[*].videos`; `generate_scholars_pages.py:talk_card()` рендерит ссылку `▶ YouTube` под каждым докладом на странице учёного.
*   Подтверждено end-to-end на тестовой одной-строке фикстуре; коммит-готовый `video_presentation_mapping.csv` сейчас пуст (только заголовок), ждёт реального запуска `fetch_videos.py` с API-ключом.
*   **Замеченный долг (тот же корень, что у `theme_codes_final.csv`)**: `presentation_id` нестабилен между сборками; любой внешний CSV с этим ключом устаревает на следующем CI-прогоне. `theme_codes_final.csv` (895 LLM-кодов) сейчас имеет нулевое пересечение с актуальными ID. Долгосрочное решение — детерминированные ID (хеш от `year+series+title+first_speaker`), отложено на следующую сессию.

**Документация:**
*   `README.md` и `README_RU.md` обновлены: 213 → 220 учёных, 732 → 899 авторских участий, 32 → 38 в перекрестной когорте, 119 → 129 петербургских, 62 → 53 московских; добавлена отметка о расширении до 2026 г.
*   `HANDOFF.md` — итоги вечерней сессии (десять пунктов) для следующего собеседника.

### Итоговое состояние БД и сайта на конец сессии

*   **БД:** 220 учёных, 899 авторских участий (895 уникальных докладов), 2004–2026 (Зограф 2004–2026, Рерих 2007–2025), 38 в перекрестной когорте.
*   **Деплой:** `https://gasyoun.github.io/IndologyScholars/` возвращает актуальные числа и для JS-рендера, и для статического HTML. CI зелёный end-to-end впервые с 2026-05-19.

---

## [1.7.0] — 2026-05-21

### Добавлено

**Интеграция XLVII Зографских чтений 2026:**
*   Поддержка PDF-формата программ: `build_and_populate_db.py` теперь читает программы через `read_program_text(year, conference)` с приоритетом `{conf}_{year}.html`, затем `{conf}_{year}.pdf` (через `pypdf`). Тестовый случай: `html_cache/zograf_2026.pdf` (XLVII, 26–29 мая 2026).
*   Расширены регулярные выражения для разбора соавторов: `TALK_REGEX_COAUTHORS` (общая аффилиация через запятую) и `TALK_REGEX_TWO_AFFIL` (две разные аффилиации). Со-докладчикам присваивается роль `coauthor` и инкрементальный `author_order`.
*   Сидированы записи Зографа-2026 в `zograf-roerich-db.md`: P028 (Posts), E2026 (Events), D2026_1…4 (EventDays), DV2026_*_1 (EventDayVenues).
*   Исправлен баг параллельного учёта дня: строка-заголовок «26 — 29 мая 2026» больше не засчитывается как day 1 (введён фильтр диапазонных дат).
*   База данных выросла: 22 события Зографа (был 21), 18 Рерих, 220 учёных, 895 докладов, 38 пересекающихся.

**Аналитика для ретроспективы 2004–2026:**
*   `analytics_output/closedness_metrics.csv` — 6 метрик закрытости (one-talk-wonder, core 5+, Gini, retention, медиана/максимум) с разбивкой Zograf / Roerich / Combined.
*   `analytics_output/newcomer_rate_by_year.csv` — доля новичков в каждом году каждой серии.
*   `analytics_output/cohort_survival.csv` — выживаемость когорт дебютантов по годам с момента дебюта.
*   `analytics_output/online_share_by_year.csv` — доля онлайн-докладов по годам (с явным override для COVID-2020 как 100% онлайн).
*   `analytics_output/online_repeaters_2020_plus.csv` — учёные с ≥2 онлайн-докладов после 2020 (всего 3).
*   `analytics_output/theme_codes_baseline.csv` — keyword-baseline кодирование 895 докладов по четырём осям (L1 дисциплина / L2 период / L3 материал / L4 фундаментальный/прикладной/методический). 36.8% попали в `unspec` и требуют второго прохода (LLM или ручной).
*   `analytics_output/theme_review_queue.csv` — 860 спорных заголовков на ручную/LLM-сверку.
*   `analytics_output/rinc_lookup_queue.csv` — 160 учёных без даты рождения, ранжированных по числу докладов; для каждого готов OpenAlex API URL.
*   `analytics_output/zograf_2026_affiliation_audit.csv` — построчная верификация риторики «профильные академические учреждения России и зарубежья» против фактического состава Зографа-2026.

**Скрипты в `scratch/`:**
*   `verify_zograf_2026_claim.py` — верификация call for papers против реального состава программы.
*   `closedness_metrics.py` — 6 метрик закрытости + Gini.
*   `online_offline_analysis.py` — H6: проверка, открыл ли онлайн-формат состав.
*   `theme_coding_baseline.py` — keyword-baseline тематической разметки 895 докладов.
*   `rinc_proxy_skeleton.py` — заготовка для извлечения года первой публикации через OpenAlex/РИНЦ.

**Безопасность:**
*   `.gitignore` дополнен: `.env`, `.env.*`, `*.secret`, `*api_key*`, `*api-key*`.

**Документация:**
*   `.ai_state.md` (журнал сессии) с текущим тезисом статьи в ППВ, семью гипотезами H1–H7, очередью задач и фиксацией промежуточных результатов.

### Ключевые цифровые выводы (для ретроспективной статьи в ППВ)

*   **Закрытость:** Рерихи (91 учёный) меньше Зографа (167), но БОЛЬШАЯ доля ядра ≥5 докл. (31.9% против 24.0%) и БОЛЬШАЯ retention (61.5% против 56.3%). Подтверждает H5.
*   **Тематика (baseline, требует LLM-уточнения):** Tibetology и History в Рерихах в 2× больше; Philosophy — в Зографе. Поддерживает H1+H7.
*   **Онлайн H6:** Zograf 2020 = 100% (COVID) → 2026 = 1.7%. Только 3 человека стабильно онлайн с 2020+. Подтверждает: онлайн НЕ открыл состав.
*   **Зограф-2026 vs риторика:** 31.7% подтверждённо академических, 28.3% дебютанты без истории, 1.7% явно независимых; 2 школьных учителя в программе. Сама публикуемая программа не указывает институт ни у кого — критерий «профильные академические» в публикуемом виде непроверяем.

### LLM-фаза тематической разметки (DeepSeek)

*   `scratch/theme_coding_llm.py` — запускает DeepSeek API (модель `deepseek-chat`) пакетами по 20 заголовков, читает ключ из `.env` (не коммитится). Возобновляемый (skip уже размеченных presentation_id).
*   Прогон по 860 строкам очереди завершён успешно: 0 неудачных батчей, ~78K input tokens, ~60K output tokens, стоимость ~$0.087.
*   `analytics_output/theme_codes_llm.csv` (860) — кодирование L1/L2/L3/L4 + confidence + одна фраза обоснования.
*   `analytics_output/theme_codes_final.csv` (895) — слияние baseline ∪ LLM с приоритетом LLM.
*   `analytics_output/theme_codes_uncertain.csv` (26) — заголовки с confidence<0.6; в основном это data-quality лакуны в программах 2022 г. (пустые / короткие заголовки).

### Уточнённые тематические выводы (после LLM)

*   **L1 (дисциплина) — асимметрия школ подтверждена:**
    *   Зограф (n=540): literature 22.0%, **philosophy 21.7%**, religion 20.9%, linguistics 11.3%
    *   Рерихи (n=355): religion 25.4%, literature 19.2%, **history 15.8%**, philosophy 12.1%, art_archaeology 9.6%
    *   Расхождения 2×: philosophy (Z 21.7% vs R 12.1%), history (R 15.8% vs Z 8.0%), art_archaeology (R 9.6% vs Z 4.6%), tibetology (R 3.1% vs Z 1.5%).

*   **L2 (период) — Рерихи зафиксированы на «золотом веке»:**
    *   Рерихи: medieval 38.9% + classical 34.9% = **74%** «золотого века».
    *   Зограф: classical 34.1% + medieval 22.4% = 56%; modern+contemporary+colonial = **28%** (vs 17% у Рериха). Зограф значительно более распределён по периодам.

*   **L4 (характер) — гипотеза о расправе с прикладниками НЕ подтверждается:**
    *   На обеих площадках fundamental 93–94%, applied 4–5%, methodological 2–2.3%. Тематический состав программ практически идентичен по характеру. Отказы по «прикладному характеру» отдельных авторов происходят на этапе подачи, не на уровне системного фильтра по программе.

---

## [1.6.0] — 2026-05-18

### Добавлено
*   **Интерактивная гео-пространственная визуализация:**
    *   Реализован рендеринг SVG-карты Евразии с привязкой реальных географических координат (`lat`/`lon`) к 33 городам в Python пайплайне `generate_site_data.py`.
    *   Добавлены CSS-анимации свечения узлов, интерактивные тултипы и линии гравитационного притяжения к основным академическим центрам (Москва, СПб).
    *   Сделан бесшовный переход из узла на карте прямо к фильтрации исследователей по выбранному городу.
*   **Рейтинг научно-исследовательских институтов (Leaderboard):**
    *   Внедрена нормализация и кластеризация различных вариантов написания институтов (ИВР РАН, МГУ, ВШЭ, СПбГУ).
    *   Добавлен топ-10 рейтинг по объему научных докладов и количеству уникальных ученых с перекрестной фильтрацией по клику.
*   **Семантическое облако тегов (N-Gram Word Cloud):**
    *   Добавлен лексический экстрактор в Python пайплайне для выделения наиболее частотных академических терминов (за исключением стоп-слов RU/EN).
    *   Реализована динамическая визуализация топ-60 терминов с градиентной окраской и CSS масштабированием в интерфейсе.
    *   Подключена связка с механизмом полнотекстового поиска (Full-text Search).
*   **CI/CD Автоматизация:**
    *   В процесс `GitHub Actions` добавлен автоматический рендеринг и пуш статичных HTML-страниц (213 профилей) для каждого отдельного исследователя.

## [1.5.0] — 2026-05-18

### Добавлено
*   **Статические страницы ученых (Индивидуальные академические профили):**
    *   Реализован Python-генератор `generate_scholars_pages.py` для автоматической сборки 213 статичных премиальных HTML-страниц (в каталоге `scholars/`) для каждого участника конференции.
    *   Каждая страница содержит персональный glassmorphic-профиль, хронологическую историю докладов, полную траекторию смены аффилиаций и городов, а также интеллектуальные перекрестные ссылки.
*   **Перекрестная навигация и интерактивная фильтрация:**
    *   Интегрирован бесшовный переход из каталога по клику на имя ученого на его индивидуальную статичную HTML-страницу с сохранением фокуса.
    *   Все аффилиации ученого в каталоге и его докладах стали интерактивными: клик по аффилиации мгновенно фильтрует каталог по соответствующему научному центру.
    *   Географические города докладов стали кликабельными тегами, выполняющими автоматический перекрестный поиск и фильтрацию всего каталога докладчиков по выбранному региону.
*   **Аналитический блок карьерной траектории (Впервые и последний раз на чтениях):**
    *   В карточку детальной информации ученого добавлен премиальный блок «Профиль карьеры», показывающий точный год первого и последнего доклада отдельно для Зографских и Рериховских чтений.
*   **Тематическая классификация докладов:**
    *   Разработан алгоритм автоматической классификации докладов на пять ключевых тематических категорий: *История науки и архивы (AcademicHistory)*, *Лингвистика и филология (Linguistics)*, *Философия и религия (Philosophy)*, *Искусство и литература (Art)*, *История и этнография (History)*.
    *   В детальное описание доклада интегрированы цветные тематические бейджи.
    *   Добавлен интеллектуальный анализ профиля исследований: определение междисциплинарности докладчика (склонность менять научные темы) и его доминантной научной области.
*   **Расширенные фильтры (Неактивные когорты):**
    *   На главной панели реализованы два новых расширенных фильтра:
        *   *«Никогда не выступали на Зографских чт.»* (позволяет мгновенно выделить чисто московское ядро исследователей).
        *   *«Никогда не выступали на Рериховских чт.»* (позволяет отфильтровать чисто петербургскую когорту индологов).
*   **Расширенный блок SVG-визуализаций на вкладке «Статистический анализ»:**
    *   Спроектирован и внедрен горизонтальный SVG-график демографического распределения индологов по возрастным группам: *Молодые ученые (<35)*, *Средний возраст (35-50)*, *Старшие ученые (50-70)*, *Почетные ученые (70+)*.
    *   Создан интерактивный сегментированный график гендерного состава научного сообщества (Male vs Female) с динамическим расчетом процентного соотношения и красивой локализацией.
*   **Расширение и обновление технической документации:**
    *   Полностью обновлён главный англоязычный файл README.md и русскоязычная документация README_RU.md с отражением новых метрик базы данных (213 уникальных ученых, 732 доклада, 32 участника перекрестной когорты).
    *   Добавлен новый комплексный раздел **«Сценарии использования (Use Cases)»**, содержащий 6 детальных практических кейсов (просопографический профиль, академическая миграция, междисциплинарный охват, демографический мониторинг, гео-картирование и региональные когорты).
*   **Интерактивный граф научных связей (Force-Directed Network Graph):**
    *   Разработан физический движок (на чистом HTML5 Canvas и JS) для построения динамического графа коллабораций ученых на основе их совместного участия в одних и тех же секциях (Session-level Collaborations).
    *   Узлы графа раскрашены по доминирующим научным темам, а их размер отражает общую публикационную активность ученого.
    *   Внедрена интерактивная система двойной навигации: клик на узел (ученого) в графе автоматически переключает интерфейс на вкладку «Каталог востоковедов» и фильтрует список по выбранному имени.

---

## [1.4.0] — 2026-05-18

### Добавлено
*   **Обогащение просопографических данных (Годы жизни и полные ФИО):**
    *   Проведен глубокий библиографический поиск в открытых источниках (академические архивы, некрополи, сайты ИВ РАН, ИВР РАН, СПбГУ) для устранения лакун в биографиях.
    *   Интегрированы точные годы жизни (годы рождения и смерти) для всех 188 ученых; для ныне живущих отображается только год рождения.
    *   Восстановлены полные имена, отчества и оригинальные написания для всех 23 ученых, по которым ранее отсутствовали эти сведения в архивных программах конференций.
*   **Сектор географического анализа (Гео-аффилиации):**
    *   Создана специализированная таблица `place` в схеме базы данных SQLite и алгоритм парсинга городов (Москва, Санкт-Петербург, Краснодар, Пенза, Казань, Элиста, Новосибирск, Нижний Новгород и др.) из строк аффилиаций.
    *   Разработан интерактивный горизонтальный SVG-график географического распределения докладов по городам на вкладке «Статистический анализ» с плавной адаптацией под русский и английский языки.
*   **Интерактивное отображение биографических данных:**
    *   На интерактивной веб-панели (`index.html`) годы жизни элегантно отображаются рядом с именем ученого в формате `(род. YYYY)` или `(YYYY–YYYY)` на русском и `(b. YYYY)` или `(YYYY–YYYY)` на английском языке.
    *   Имена ученых в каталоге теперь выводятся в полном, развернутом виде по умолчанию, сохраняя академическую точность.

---

## [1.3.0] — 2026-05-18

### Добавлено
*   **Глубокий научно-аналитический анализ (Просопография):** 
    *   Создан Python-модуль `scratch/analyse_scholars.py` для комплексного анализа участников индологических конференций.
    *   Сформирован научно-аналитический маркдаун-отчет `indologists_scholarly_analysis.md`, содержащий классификацию ученых, динамику аффилиаций и биобиблиографическую находимость в сети Интернет.
*   **Единообразие ФИО (Инициалы Фамилия):**
    *   Интегрированы регулярные выражения для автоматического приведения всех имен на веб-панели к строгому академическому стандарту *«Инициалы Фамилия»* (например, `В. В. Вертоградова`).
    *   Сформирован просопографический список ученых, по которым отсутствуют полные имена в исходных программах для дальнейших изысканий.
*   **Хронометрический анализ докладов (Календарные дни недели):**
    *   Внедрен динамический расчет дней недели на основе точных календарных дат проведения докладов с локализацией на русском и английском языках (например, `Понедельник` / `Monday`).
    *   Дни недели и даты интегрированы в детальный просмотр каждого ученого и в общую хронологическую ленту.
*   **Очередность докладов (Позиционный ранг доклада):**
    *   Разработан алгоритм вычисления порядкового индекса выступления внутри научных секций.
    *   Реализованы автоматические почетные маркеры: `🥇 Открывающий доклад` (первое выступление секции, задающее научный тон) и `🎖️ Закрывающий доклад` (завершающее выступление, подводящее итоги заседания).
*   **Социально-статусный анализ участников:**
    *   Проведен автоматизированный аудит архивных текстов аффилиаций с классификацией докладчиков на категории: **«Молодые ученые» (Студенты, аспиранты, магистранты)** и **«Независимые исследователи (НИ)»** без официальной институциональной привязки.
    *   Разработан трекер динамики смены официального места работы (аффилиации) индологов между конференциями разных лет.

---

## [1.1.0] — 2026-05-18

### Добавлено
*   **Двуязычная локализация (RU / EN):** Реализован бесшовный переключатель языков на интерактивной панели (`index.html`). По умолчанию интерфейс загружается на русском языке без английских слов. Переключение на английскую версию переводит все заголовки, фильтры, элементы таблиц, карточки метрик, легенды графиков и детализированные описания в реальном времени.
*   **Файл состояния ИИ (`ai_state.json`):** Добавлен структурированный JSON-манифест метаданных, фиксирующий архитектуру, контрольные метрики базы данных, состав сгенерированных ресурсов и конфигурацию локализации для последующих сессий парного программирования.
*   **Русская документация (`README_RU.md`):** Написано подробное руководство на русском языке, описывающее архитектуру базы данных, DDL-схемы таблиц, структуру конвейера парсинга, интеграцию с календарями и порядок развёртывания.
*   **Автоматическое логирование версий:** Сформирован данный файл `CHANGELOG.md`.

### Исправлено
*   **Исключение ValueError при разборе времени:** Устранена ошибка парсинга в `build_and_populate_db.py` при обработке некорректных временных разделителей (например, замена точек на двоеточия в таймингах докладов вида `14.30` -> `14:30` перед вызовом `int()`).

---

## [1.0.0] — 2026-05-18

### Добавлено
*   **База данных `conferences.db`:** Построена полностью нормализованная реляционная база данных SQLite, содержащая 114 дней конференций, 188 уникальных докладчиков и 707 презентаций.
*   **Модуль парсинга и сборки БД (`build_and_populate_db.py`):**
    *   Созданы парсеры для 21 года «Зографских чтений» и 18 лет «Рериховских чтений».
    *   Внедрены интеллектуальные регулярные выражения для извлечения имен докладчиков, их аффилиаций и названий научных докладов.
    *   Реализована эвристика нормализации имен для сопоставления участников, отсекающая инициалы, лишние пробелы и дублирующие записи.
*   **Аналитический движок (`generate_analytics.py`):**
    *   Проведен автоматический расчет перекрывающихся когорт (30 докладчиков, посетивших оба форума).
    *   Сформированы три целевых научных CSV-отчета в папке `analytics_output/`.
    *   Сгенерирован маркдаун-отчет `indology_scholars_analytics.md` с детальными статистическими таблицами.
*   **Интерактивный веб-интерфейс (`index.html`):**
    *   Построена потрясающая темная визуальная панель с эффектом стеклянного размытия (glassmorphism) и адаптируемой сеткой.
    *   Внедрен динамический каталог востоковедов с пагинацией, фильтрацией по конференциям и мгновенным поиском.
    *   Создана детальная интерактивная хронология конференций в виде вертикального таймлайна с раскрывающимися списками.
    *   Реализованы интерактивные SVG-графики годовой динамики публикационной активности и гео-сродства.
*   **Модуль сериализации (`generate_site_data.py`):** Сборка реляционных таблиц SQLite в высокопроизводительный статический JSON-объект `site_data.json` для работы клиентского фронтенда.
