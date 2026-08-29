# IndologyScholars: архив докладов по российской индологии

_Created: 24-04-2026 · Last updated: 29-08-2026_

[English version](https://github.com/gasyoun/IndologyScholars/blob/main/README_EN.md) | [Документация для разработчиков](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development.md)

**IndologyScholars** — открытый навигационный архив программ двух российских
индологических форумов: Зографских чтений в Санкт-Петербурге и Рериховских
чтений в Москве. Архив связывает докладчиков, названия докладов, годы участия,
зафиксированные аффилиации, тематические рубрики и доступные видеозаписи.
Рядом с ядром корпуса живут спутники: закрытая гуглгруппа «Общество ревнителей
санскрита» (`nagari/`), публичная VK-стена того же сообщества (`vk-ors/`) и
выделенный атлас рассылки INDOLOGY-L.

[Открыть сайт](https://gasyoun.github.io/IndologyScholars/)

## Состав архива

Опубликованная выборка докладчиков (снимок `site_data.json`, актуален на
23 июля 2026 г.) содержит:

| Показатель | Значение |
| --- | ---: |
| Профили докладчиков | 268 |
| Уникальные доклады | 1362 |
| Авторские участия | 1388 |
| Программные годы | 22, с 2004 по 2026 г. |
| Участники обеих площадок | 41 |
| Только Зографские чтения | 163 |
| Только Рериховские чтения | 64 |

В архив включены Зографские чтения 2004-2026 гг. и Рериховские чтения
2007-2025 гг. Программа Зографских чтений 2026 г. учитывается как
предварительно опубликованная программа. Отдельно от счётчика докладчиков
ведётся **исторический просопографический слой** (26 фигур; `person_kind =
historical`).

## Что можно найти

- [Главный каталог](https://gasyoun.github.io/IndologyScholars/) с поиском по
  именам, докладам, городам и институциям.
- [Реестр научных гипотез](https://gasyoun.github.io/IndologyScholars/hypotheses.html) — многомерный фильтр по 35 гипотезам российской индологии с 7 наукометрическими шкалами и HSL glassmorphism дизайном.
- [Интерактивные визуализации](https://gasyoun.github.io/IndologyScholars/findings/visualisations.html) —
  визуальный дашборд: пересечение когорт Зограф × Рерих, траектории аффилиаций и тепловые карты.
- [Сетевую карту](https://gasyoun.github.io/IndologyScholars/networks.html)
  соавторства и совместного присутствия в программах.
- [Linked Open Data (LOD) Граф](https://gasyoun.github.io/IndologyScholars/indology_knowledge_graph.ttl) — машиночитаемый RDF/Turtle граф знаний для семантического веба (Semantic Web), описывающий ученых (foaf:Person) и события (schema:Event).
- [Конференции](https://gasyoun.github.io/IndologyScholars/conferences/) с
  переходом к отдельным годам и программам.
- [Тематические подборки](https://gasyoun.github.io/IndologyScholars/themes/)
  и [поколенческие когорты](https://gasyoun.github.io/IndologyScholars/generations/).
- Обзорные очерки [«Индология в России»](https://gasyoun.github.io/IndologyScholars/indologiya-v-rossii.html)
  и [«Санскритология в России»](https://gasyoun.github.io/IndologyScholars/sanskritologiya-v-rossii.html) —
  нарративные разделы, помещающие корпус в контекст истории дисциплины.
- [Поиск по коллекции](https://gasyoun.github.io/IndologyScholars/search.html),
  включая отдельные страницы докладов и ссылки на видео, когда запись найдена.
- [Реестр индологов вне программ](https://gasyoun.github.io/IndologyScholars/indologists.html) —
  неучастники конференций, связанные с корпусом через enrichment.
- [«20 лет Обществу ревнителей санскрита»](https://gasyoun.github.io/IndologyScholars/nagari/) —
  ретроспектива закрытой гуглгруппы (`nagari/`; исходник прав-ограничен).
- [VK-архив «Общество ревнителей санскрита»](https://github.com/gasyoun/IndologyScholars/tree/main/vk-ors) —
  стена vk.com, SQLite+FTS5 и четырёхслойный анализ (`vk-ors/`).
- [INDOLOGY Archive Atlas](https://gasyoun.github.io/IndologyArchiveAtlas/) —
  атлас публичной рассылки INDOLOGY-L, **выделен** в отдельный репозиторий
  [`gasyoun/IndologyArchiveAtlas`](https://github.com/gasyoun/IndologyArchiveAtlas)
  (H460). Старый путь
  […/IndologyScholars/IndologyArchive/](https://gasyoun.github.io/IndologyScholars/IndologyArchive/)
  на этом сайте перенаправляет на новый Pages; для Renou-сравнения здесь
  остаётся односторонний feed (`tools/fetch_indology_feed.py`).

## Как читать сведения

- Аффилиация передается по официальной программе или по отдельно проверенному
  источнику. Городская помета не считается названием институции.
- Если подтвержденная аффилиация имеет открытую дату окончания и следующая
  программа не дает новой институции, продолжение показывается как
  предположение с пометой `(?)`. Явная новая аффилиация или дата окончания
  прекращает такой перенос.
- Уровни `L1`-`L3` описывают масштаб заявленного аргумента в названии доклада,
  а не качество работы, репутацию докладчика или значимость темы. См.
  [критерии классификации](https://gasyoun.github.io/IndologyScholars/classification-criteria.html).
- Годы жизни, ученые степени и внешние идентификаторы публикуются только при
  наличии проверяемого источника; пробелы сохраняются как пробелы.

## Данные и цитирование

Готовые для скачивания наборы, форматы файлов и ограничения собраны на
[странице данных](https://gasyoun.github.io/IndologyScholars/download-data.html).
Описание метода доступно на странице
[методологии](https://gasyoun.github.io/IndologyScholars/methodology.html), а
известные ограничения - на странице
[ограничений](https://gasyoun.github.io/IndologyScholars/known-limitations.html).

Для ссылки на проект используйте
[рекомендации по цитированию](https://gasyoun.github.io/IndologyScholars/how-to-cite.html)
или файл [CITATION.cff](https://github.com/gasyoun/IndologyScholars/blob/main/CITATION.cff).

## Документация

- [Разработка и воспроизводимость, на русском](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development.md)
- [Development and reproducibility, in English](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development-en.md)
- [Технический аудит классификации](https://github.com/gasyoun/IndologyScholars/blob/main/docs/classification-audit.md)
- [Словарь данных](https://github.com/gasyoun/IndologyScholars/blob/main/data_dictionary.md)

Исторические аналитические тексты и рукописи в репозитории могут описывать
более ранние снимки корпуса; актуальными для сайта являются опубликованные
страницы и выгрузки данных.

## Как этот репозиторий связан с остальными

Архив — часть организационного «хребта» из примерно 85 репозиториев; ниже — что
он отдаёт наружу, кто это читает и куда записывать находки.

- **Что производит.** Просопографический слой докладов: перекрёстную таблицу
  мезо-код → дисциплина
  [`curation/meso_discipline_crosswalk.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/meso_discipline_crosswalk.csv)
  (50 сопоставлений с оценкой уверенности), справочник дисциплин
  [`curation/disciplines.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/disciplines.csv)
  и ручные назначения
  [`curation/person_disciplines.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/person_disciplines.csv).
  Внутри репозитория их читает
  [`pipeline/disciplines.py`](https://github.com/gasyoun/IndologyScholars/blob/main/pipeline/disciplines.py),
  собирая таблицу `person_discipline`.
- **Кто читает.** Перекрёстная таблица зарегистрирована как ребро графа в
  [PROJECT_INTERLINKS.md](https://github.com/gasyoun/Uprava/blob/main/PROJECT_INTERLINKS.md)
  и [interlinks_edges.tsv](https://github.com/gasyoun/Uprava/blob/main/interlinks_edges.tsv)
  (26-08-2026): её не следует пересобирать заново в соседних репозиториях.
  **С 29-08-2026 (решение F5c) у неё есть и зарегистрированные потребители** —
  [`csl-atlas`](https://github.com/gasyoun/csl-atlas) и
  [`kosha`](https://github.com/gasyoun/kosha), строки `consumes` со статусом `proposed`.
  ⚠️ **Статус `proposed` — не украшение:** замер 29-08-2026 (`git grep -il
  meso_discipline_crosswalk|person_disciplines|disciplines.csv`) показывает, что **ни один из
  них таблицу пока не читает**. Строки держатся на *намерении*, признанном решением F5
  обязательным: брать эту перекрёстную таблицу, а не собирать свою таксономию дисциплин
  русской индологии заново, и никогда не откатываться к `keyword_filtering.py` с его
  погрешностью ≥ 7,1 %. **Условие снятия:** если к следующей переписи связности ни один из
  них так и не будет её читать, обе строки-потребителя удаляются; строка-производитель
  остаётся в любом случае. До этого момента отсутствие чтения — известное датированное
  состояние, а не дефект.
  Из соседей архив сам потребляет ленту
  [`gasyoun/IndologyArchiveAtlas`](https://github.com/gasyoun/IndologyArchiveAtlas)
  (`feed/*.csv` → `tools/fetch_indology_feed.py`).
- **Куда писать находки.** Инфраструктура и процесс →
  [Uprava/FINDINGS.md](https://github.com/gasyoun/Uprava/blob/main/FINDINGS.md);
  санскритские данные →
  [SanskritLexicography/FINDINGS.md](https://github.com/gasyoun/SanskritLexicography/blob/master/FINDINGS.md).
  Своих реестров этот репозиторий не держит.
- **Общий код.** Прежде чем писать нормализатор, транскриптор или парсер —
  [SHARED_CODE.md](https://github.com/gasyoun/github-spine/blob/main/SHARED_CODE.md).
- **Что уже существует.**
  [FEATURES_INDEX.md](https://github.com/gasyoun/SanskritLexicography/blob/master/FEATURES_INDEX.md).
- **Что делать дальше.**
  [GTD_NEXT_ACTIONS.md](https://github.com/gasyoun/Uprava/blob/main/GTD_NEXT_ACTIONS.md).

## Лицензия

Код, шаблоны и валидаторы распространяются по [Apache-2.0](https://github.com/gasyoun/IndologyScholars/blob/main/LICENSE).
Нормализованные метаданные и производные CSV/JSON/SQLite-выгрузки доступны для
повторного использования по CC-BY-4.0 с указанием архива. Кэшированные
программы конференций, цитаты из источников и сторонние материалы сохраняют
права исходных правообладателей; подробнее см. [reuse-rights](https://github.com/gasyoun/IndologyScholars/blob/main/docs/reuse-rights.md).

_Dr. Mārcis Gasūns_
