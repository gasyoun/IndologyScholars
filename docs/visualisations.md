# Интерактивные визуализации: Архитектура и сценарии использования / Interactive Visualizations: Architecture & Use Cases

[Открыть страницу визуализаций на сайте / Open visualisations page on the live site](https://gasyoun.github.io/IndologyScholars/findings/visualisations.html)

---

## 1. Концепция стабильных идентификаторов / Concept of Stable IDs

Для обеспечения строгой воспроизводимости и возможности академического цитирования, каждой визуализации в системе присвоен уникальный, постоянный и неизменяемый идентификатор (Stable ID). Эти идентификаторы жестко зафиксированы в разметке DOM и схеме метаданных, что позволяет:
- Ссылаться на конкретный интерактивный график в научных статьях (например, `https://.../visualisations.html#VIS_001_orbit_scatter`).
- Сохранять стабильность ссылок при будущих обновлениях данных или добавлении новых графиков.
- Проходить автоматическое тестирование на целостность структуры страницы.

To ensure rigorous scientific reproducibility and robust academic citation, every visualization in the system has been assigned a unique, permanent, and non-changing identifier (Stable ID). These IDs are hardcoded in the DOM structure and metadata schemas, enabling:
- Direct referencing of specific interactive plots in scholarly publications (e.g., `https://.../visualisations.html#VIS_001_orbit_scatter`).
- URL stability when data updates or new charts are added.
- Automated integrity tests to guarantee DOM structure persistence.

### Реестр визуализаций / Visualisation Registry

| Stable ID | Название (RU) | Name (EN) | Статус / Status |
| --- | --- | --- | --- |
| `VIS_001_orbit_scatter` | Орбита перекрёстной когорты | Cross-Cohort Orbit Scatter | **Live** (Интерактивный SVG / Interactive SVG) |
| `VIS_002_affiliation_opacity` | Временная шкала прозрачности аффилиаций | Affiliation Opacity Timeline | Teaser (В разработке / In Development) |
| `VIS_003_video_heatmap` | Тепловая карта видеопокрытия | Video Coverage Heatmap | Teaser (В разработке / In Development) |
| `VIS_004_keyword_alluvial` | Аллювиальный граф ключевых слов | Keyword Flow Alluvial | Teaser (В разработке / In Development) |

---

## 2. Сценарии использования / Scholarly Use Cases

### VIS_001_orbit_scatter: Анализ перекрестной активности когорт / Cross-Cohort Activity Analysis

**Описание / Description**:
Двухмерный график рассеяния, сопоставляющий количество докладов каждого ученого на Зографских чтениях (ось X) и Рериховских чтениях (ось Y). Диагональная линия обозначает идеальный паритет активности. Точки расцвечены по трем группам: только Зографские чтения (синий), только Рериховские чтения (розовый) и мосты — участники обеих конференций (оранжевый).

**Сценарии научного применения / Research Use Cases**:
1. **Идентификация «интеграторов академической среды» (Bridges / Мосты)**:
   - *RU*: Смещение точек относительно диагонали и их отдаление от начала координат позволяет быстро выделить ученых, формирующих единое индологическое поле. Исследователь может кликнуть на оранжевую точку, чтобы перейти в профиль «моста» и изучить, какие темы служат связующим звеном между санкт-петербургской и московской школами.
   - *EN*: Plotting scholars relative to the diagonal reveals actors who actively integrate the two distinct communities. Researchers can click on orange "bridge" nodes to explore their profiles and determine which academic topics act as thematic bridges between the St. Petersburg and Moscow schools.
2. **Анализ институциональных барьеров**:
   - *RU*: Плотные кластеры вдоль осей X и Y показывают степень институциональной или географической замкнутости. Исследователь может оценить, насколько жестко разделены аудитории двух крупнейших индологических чтений страны.
   - *EN*: Heavy clustering along the X and Y axes measures geographical or institutional insulation. Researchers can evaluate how strictly separated the participant bases of the two largest Indological forums remain.

---

### VIS_002_affiliation_opacity: Оценка прозрачности институциональных данных / Affiliation Opacity Chronology

**Описание / Description**:
Интерактивная шкала времени, отслеживающая эволюцию указания места работы участников в официальных программах. Хронологический срез классифицирует каждую аффилиацию по трем уровням: подтвержденное учреждение, только город (аффилиационная непрозрачность) и неизвестный статус.

**Сценарии научного применения / Research Use Cases**:
1. **Историко-социологический анализ академической прозрачности**:
   - *RU*: Позволяет исследователям проследить, как менялись стандарты научной редактуры программ с 2004 по 2026 годы. График помогает визуально доказать гипотезу о росте или снижении прозрачности данных в зависимости от институционального давления (например, требований РИНЦ).
   - *EN*: Enables sociologists of science to trace changes in editing standards and formatting conventions from 2004 to 2026. The visualization maps spikes or drops in data transparency against institutional shifts (e.g., Russian Science Citation Index requirements).
2. **Направленная верификация пропусков**:
   - *RU*: Выделение периодов высокой «городской непрозрачности» указывает кураторам архива, на каких исторических годах необходимо сосредоточить архивные изыскания для восстановления реальных мест работы индологов.
   - *EN*: Highlighting chronological bands of high "city-only" references guides archive curators on exactly which historical years require manual archival lookup to fill in actual institutions.

---

### VIS_003_video_heatmap: Анализ лакун видеодокументирования / Mapping Video Archiving Gaps

**Описание / Description**:
Тепловая матрица, сопоставляющая года проведения чтений и тематические рубрики (лингвистика, философия, история и т. д.), где интенсивность цвета отражает процент докладов, снабженных видеозаписью на YouTube.

**Сценарии научного применения / Research Use Cases**:
1. **Оценка сохранности цифрового наследия**:
   - *RU*: Наглядно демонстрирует, какие дисциплинарные области индологии наиболее полно представлены в мультимедийном пространстве, а какие (например, классическая текстология) остаются недокументированными. Это позволяет более эффективно распределять ресурсы при будущих видеозаписях конференций.
   - *EN*: Visually identifies which Indological subfields are well-represented in the digital media space and which (e.g., classical textual criticism) remain completely undocumented. This aids in better resource allocation for future video recording efforts.

---

### VIS_004_keyword_alluvial: Хронологический дрейф научной лексики / Thematic Flow & Terminology Drift

**Описание / Description**:
Аллювиальный граф (потоковая диаграмма Санкея), визуализирующий движение и слияние ключевых слов от периода к периоду (ранние 2000-е, 2010-е, 2020-е).

**Сценарии научного применения / Research Use Cases**:
1. **Картирование смены парадигм**:
   - *RU*: Исследователь может проследить, как традиционные текстологические термины (например, «манускрипт», «редакция») перетекали или вытеснялись современными междисциплинарными концептами («дискурс», «гендер») на протяжении 22 лет.
   - *EN*: Scholars can track how traditional philological and textual terms (e.g., "manuscript", "recension") morphed, split, or were superseded by contemporary interdisciplinary frameworks ("discourse", "gender") over more than two decades.
