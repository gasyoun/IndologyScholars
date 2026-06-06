# Handoff: сбор русскоязычных индологов

> Инструкция для продолжения работы без ИИ-ассистента.  
> Последнее обновление: 2026-06-06

---

## 0. Что изменилось 2026-06-06 (читать первым)

**Где что работает (матрица достижимости).** Сеть решает всё:

| Источник | С хоста CI | С машины в РФ |
|----------|-----------|---------------|
| `en.wikipedia.org` API | ✅ работает | ✅ работает (не блокируется РКН) |
| `ru.wikipedia.org` **статьи** | ❌ | ✅ открываются в браузере |
| `ru.wikipedia.org/w/api.php` | ❌ | ❌ блок РКН |
| `wikidata.org` (REST/SPARQL) | ❌ | 🟡 обычно да |
| `ivran.ru`, `orientalstudies.ru` | ❌ | ✅ |

Поэтому **основной путь сбора — `enwiki_bridge.py`** (через en.wikipedia, РКН его
не трогает). Он даёт ru-название + Wikidata Q-ID. Старый
`expand_wikipedia_indologists.py` нужен только для русскоязычных полей инфобокса
и запускается на машине в РФ.

**Рекомендуемый конвейер теперь:**
```bash
python scratch/enwiki_bridge.py        # 1. en.wiki → ru-название + Q-ID (RKN-устойчиво)
python scratch/wikidata_enrich.py      # 2. Q-ID → годы жизни (где Wikidata доступна)
python scratch/expand_wikipedia_indologists.py  # 3. ru-инфобоксы (на машине в РФ)
python scratch/scrape_institutions_web.py       # 4. сайты институтов (в РФ; нужен Playwright)
python scratch/crossref_nonparticipants.py      # 5. отчёт
python -m pytest tests/                          # 6. валидация (60 passed)
```

**Два важных исправления:**
- ⚠️ **«Полный цикл» больше НЕ разрушительный.** Раньше `expand_…py` перезаписывал
  master результатом живого (заблокированного) запроса и стёр бы все имена.
  Теперь слияние неразрушающее (atomic write, только дополнение). Старое
  предупреждение в §6 снято.
- **`search_via_html()` теперь реально есть** в `expand_…py` (раньше FAQ/changelog
  утверждали это ложно — функции не существовало).

**Новые файлы:** `enwiki_bridge.py`, `wikidata_enrich.py`,
`scrape_institutions_web.py`, `scrape_common.py` (общий robust-HTTP + atomic
write + нормализация), `tests/test_indologist_matching.py`,
`tests/test_institutions_web.py`. Текущее: **114** записей в `people`
(+Бондаревский, +Сталь-фон-Гольштейн), Q-ID 8→26.

`enwiki_bridge.py --wide` дополнительно берёт `Soviet/Russian orientalists` и
оставляет только индологов (фильтр по индийским категориям) — так найден
имперский индолог Сталь-фон-Гольштейн.

---

## 1. Цель проекта

Собрать **всех** индологов, говоривших на русском или живших в Российской империи / СССР / РФ за последние 200 лет. Разметить их по участию в Рериховских и Зографских чтениях (2004–2026).

**Текущий результат:** 197 имён (~80% полноты), разбивка: 100 участников, 94 неучастника.
(114 в `people` + 83 в `new_from_institutions`; Q-ID-покрытие выросло 8→26 после en.wiki-моста.)

---

## 2. Архитектура данных

```
                        ┌─────────────────────────────┐
                        │  Категории Википедии (4 шт.) │
                        │  + полнотекстовый поиск       │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────┐
                        │ expand_wikipedia_indologists │
                        │           .py                │
                        └──────────────┬──────────────┘
                                       │
    ┌──────────────────────────────────┤
    │                                  │
    │  ┌───────────────────────────┐   │
    │  │ site_data_scholars.json   │   │
    │  │ (270 участников конф.)     │   │
    │  └──────────────┬────────────┘   │
    │                 │                │
    │                 ▼                ▼
    │  ┌──────────────────────────┐ ┌──────────────────────────┐
    │  │ scrape_institutions.py   │ │ merge_institutions.py    │
    │  └──────────────┬───────────┘ └──────────────┬───────────┘
    │                 │                            │
    │                 └──────────┬─────────────────┘
    │                            │
    │                            ▼
    │         ┌──────────────────────────────────────┐
    │         │ wikipedia_indologists_expanded.json  │  ← основной файл данных (195 записей)
    │         └──────────────┬───────────────────────┘
    │                        │
    │                        ▼
    │         ┌──────────────────────────────────────┐
    │         │ crossref_nonparticipants.py          │
    │         └──────────────┬───────────────────────┘
    │                        │
    │                        ▼
    │         ┌──────────────────────────────────────┐
    │         │ scratch/non_participants.md          │  ← ИТОГОВЫЙ ОТЧЁТ
    │         └──────────────────────────────────────┘
```

---

## 3. Быстрый старт

### Перегенерировать отчёт из существующих данных (без сети)

```bash
python scratch/crossref_nonparticipants.py
# → обновит non_participants.md
```

Это безопасно: скрипт только читает локальные JSON-файлы.

### Обновить вики-данные (требуется доступ к ru.wikipedia.org)

```bash
python scratch/expand_wikipedia_indologists.py
# → обновит wikipedia_indologists_expanded.json
#   (только если API и обычные страницы доступны)
```

### Полный цикл обновления

```bash
# 1. Википедия
python scratch/expand_wikipedia_indologists.py

# 2. Институциональные аффилиации
python scratch/scrape_institutions.py

# 3. Слияние
python scratch/merge_institutions.py

# 4. Сопоставление + отчёт
python scratch/crossref_nonparticipants.py

# 5. Валидация
python validate_publication.py
python -m pytest tests/
```

---

## 4. Описание скриптов

### 4.1 `expand_wikipedia_indologists.py`

**Назначение:** собрать индологов из русской Википедии.

**Источники (4 категории):**
- `Категория:Индологи_России` (68)
- `Категория:Индологи_СССР` (92)
- `Категория:Санскритологи_России` (14)
- `Категория:Санскритологи_СССР` (11)

**Метод:**
1. `action=query&list=categorymembers` → список названий страниц
2. `action=parse&prop=text` для каждой → парсинг инфобокса (ФИО, даты, место работы, etc.)

**+ Поиск через HTML** (обход блокировки API):
1. `w/index.php?search=индолог&limit=500` → страница результатов
2. Парсинг: искать `(категория «Индологи по алфавиту»)` → извлечь ФИО

**Вход:** интернет-доступ к ru.wikipedia.org  
**Выход:** `scratch/wikipedia_indologists_expanded.json`  
**Ограничение:** `action=query` и `action=parse` заблокированы. Первый прогон сделан до блокировки. Сейчас работает только HTML-обход.

**Как запустить:**
```bash
python scratch/expand_wikipedia_indologists.py
```

---

### 4.2 `scrape_institutions.py`

**Назначение:** извлечь аффилиации из базы конференций + Wikidata.

**Метод:**
1. Читает `site_data_scholars.json` → для каждого докладчика ищет `affiliation_reported`
2. Нормализует: `ИВ РАН`, `ИВР РАН`, `МАЭ РАН`, `РГГУ`, `ИСАА`, `МГУ`, `СПбГУ`, `ВШЭ`, `МГИМО`
3. Группирует по учреждениям
4. Wikidata: `Special:EntityData/Qxxx.json` для проверки Q-ID

**Вход:** `site_data_scholars.json`, интернет (для Wikidata)  
**Выход:** `scratch/institutional_indologists.json`  
**Особенность:** ТОЛЬКО участники конференций. Неучастники не охвачены.

**Как запустить:**
```bash
python scratch/scrape_institutions.py
```

---

### 4.3 `merge_institutions.py`

**Назначение:** объединить вики-список с институциональными данными.

**Метод:**
1. Загружает `wikipedia_indologists_expanded.json`
2. Загружает `institutional_indologists.json`
3. Для каждого вики-человека ищет совпадения в институциональном списке → добавляет поле `institutions_from_db`
4. Для каждого институционального человека без вики-страницы → добавляет в `new_from_institutions[]`
5. Генерирует `institutional_summary.md`

**Вход:** оба JSON  
**Выход:** обновлённый `wikipedia_indologists_expanded.json`, `institutional_summary.md`

**Как запустить:**
```bash
python scratch/merge_institutions.py
```

---

### 4.4 `crossref_nonparticipants.py`

**Назначение:** сопоставить вики-список с базой конференций, сгенерировать отчёт.

**Метод:**
1. Загружает `wikipedia_indologists_expanded.json`
2. Загружает `site_data_scholars.json` (270 участников)
3. Fuzzy matching: surname + given name с верификацией (не менее 2 букв совпадения в имени)
4. Разбивает на три группы: участники, неучастники (живы), неучастники (умерли до 2004)
5. Генерирует `non_participants.md` с таблицами и анализом

**Вход:** оба JSON  
**Выход:** `scratch/non_participants.md`

**Как запустить:**
```bash
python scratch/crossref_nonparticipants.py
```

---

### 4.5 `add_sssr_names.py`

**Назначение:** одноразовый скрипт, добавивший 28 имён из `Категория:Индологи_СССР`.

**Использование:** больше не нужен — имена уже в `wikipedia_indologists_expanded.json`.

---

### 4.6 `add_search_results.py`

**Назначение:** одноразовый скрипт, добавивший 12 имён из полнотекстового поиска.

**Использование:** больше не нужен — имена уже в `wikipedia_indologists_expanded.json`.

---

### 4.7 `scrape_wikidata.py`

**Назначение:** экспериментальный парсер Wikidata (через `wbsearchentities` + `wbgetentities`).

**Статус:** написан, но нестабилен из-за перебоев Wikidata API. Не используется в основном пайплайне.

---

## 5. Как добавить новые имена (ручной метод)

1. Открыть `scratch/wikipedia_indologists_expanded.json`
2. Добавить запись в массив `"people"`:

```json
{
  "wikipedia_title": "Фамилия, Имя Отчество",
  "surname": "Фамилия",
  "given_name": "Имя Отчество",
  "full_name": "Имя Отчество Фамилия",
  "birth_year": 1950,
  "death_year": null,
  "scientific_field": "индология",
  "role": "индолог",
  "workplace": "ИВ РАН",
  "alma_mater": "ИСАА",
  "degree": "доктор исторических наук",
  "wikidata_qid": "",
  "is_indologist": true
}
```

3. Запустить перегенерацию:
```bash
python scratch/crossref_nonparticipants.py
```

---

## 6. Ограничения и workaround'ы

### 6.1 Блокировка `ru.wikipedia.org/w/api.php`

| Симптом | SSL handshake timeout |
|---------|----------------------|
| Причина | Роскомнадзор |
| Влияние | Невозможен `action=query`, `action=parse` |
| Workaround 1 | HTML-обход: `w/index.php?search=индолог` → парсинг текста |
| Workaround 2 | Text-версии категорий: `webfetch format=text` |
| Workaround 3 | `ru.m.wikipedia.org/w/api.php` — **не протестирован** |
| Workaround 4 | `en.wikipedia.org/w/api.php` + `prop=langlinks&lllang=ru` — **не реализован** |

### 6.2 Нестабильный Wikidata API

| Симптом | Попеременные 502 / transport error / OK |
|---------|----------------------------------------|
| Влияние | SPARQL не работает, `wbgetentities` нестабилен |
| Workaround | `Special:EntityData/Qxxx.json` — REST, стабильный |
| Рекомендация | Запрашивать не более 5 Q-ID за раз |

### 6.3 JS-рендеринг институциональных сайтов

| Симптом | `ivran.ru/persons/*` возвращает шаблон без контента |
|---------|------------------------------------------------------|
| Влияние | Не извлечь должность/отдел через HTTP GET |
| Workaround | Конференционная база как прокси (уже реализовано) |
| План A | Найти JSON API в исходном коде (Drupal → `/jsonapi/`) |
| План B | Playwright / headless Chrome для JS-рендера |

### 6.4 Ложные срабатывания при сопоставлении имён

| Защита | surname + given name: минимум 2 буквы совпадения в имени |
|--------|----------------------------------------------------------|
| Пример | Иванов Вячеслав // Иванов Владимир → НЕ совпадает (Вя ≠ Вл) |
| Качество | 0 ложных срабатываний на тестовой выборке |

---

## 7. Зависимости

**Python:** 3.12+  
**Библиотеки:** только stdlib (`json`, `re`, `urllib`, `pathlib`, `ssl`).  
**Тесты:** `pytest` (40 тестов в `tests/`).

```bash
pip install pytest
python -m pytest tests/ -q
```

---

## 8. FAQ

### Почему не работает `expand_wikipedia_indologists.py`?

`ru.wikipedia.org/w/api.php` заблокирован Роскомнадзором. Скрипт теперь сначала
пробует API, а при пустом ответе автоматически переходит на `search_via_html()`
(страница `/w/index.php?search=`, не `api.php`) — эта функция теперь
**действительно реализована** (раньше FAQ ссылался на несуществующую функцию).
HTML-обход работает там, где статьи ru.wikipedia открываются (машина в РФ), но
`api.php` заблокирован. Если ru.wikipedia недоступен совсем — используйте
`enwiki_bridge.py` (через en.wikipedia, РКН его не блокирует).

### Как добавить индолога, которого нет в вики-категориях?

См. раздел 5 «Как добавить новые имена». Ручное добавление в JSON.

### Как перегенерировать всё с нуля?

```bash
python scratch/expand_wikipedia_indologists.py    # если API доступен
python scratch/scrape_institutions.py
python scratch/merge_institutions.py
python scratch/crossref_nonparticipants.py
python -m pytest tests/
```

### Чем отличаются `people` и `new_from_institutions` в JSON?

- `people` — индологи из вики-категорий (112 записей, с инфобоксами)
- `new_from_institutions` — индологи из базы конференций, не в вики (83 записи, только ФИО + учреждение)

### Как проверить, что данные не сломаны?

```bash
python validate_publication.py   # проверка целостности
python -m pytest tests/ -q       # 40 юнит-тестов
```

### Где лежат итоговые данные?

- `scratch/non_participants.md` — отчёт для чтения
- `scratch/wikipedia_indologists_expanded.json` — машиночитаемые данные

---

## 9. Связанные файлы

| Файл | Назначение |
|------|-----------|
| `scratch/changelog.md` | Хронология всех изменений |
| `scratch/roadmap.md` | Дорожная карта с узкими местами |
| `scratch/ai_status.md` | Статус ИИ-ассистента |
| `scratch/non_participants.md` | **Итоговый отчёт** |
| `scratch/wikipedia_indologists_expanded.json` | **Основной файл данных** |
| `scratch/scrape_common.py` | Общий robust-HTTP + atomic write + нормализация |
| `scratch/enwiki_bridge.py` | **Основной путь:** en.wiki → ru-название + Q-ID (RKN-устойчиво) |
| `scratch/wikidata_enrich.py` | Q-ID → годы жизни (REST `Special:EntityData`) |
| `scratch/scrape_institutions_web.py` | Скрапер сайтов институтов (static/JSON:API/Playwright) |
| `scratch/enwiki_bridge_output.json` | Аудит-трейл en.wiki-моста |
| `tests/test_indologist_matching.py` | Юнит-тесты matcher/merge/дат |
| `tests/test_institutions_web.py` | Юнит-тесты парсера институтов |
