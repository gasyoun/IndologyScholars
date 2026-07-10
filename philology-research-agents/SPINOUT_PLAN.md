# План выноса модуля агентов в отдельный репозиторий

> Составлено 2026-06-02. Текущее состояние: промпты готовы, пример прогона есть,
> профили редакторов (6 журналов) созданы. Ближайший шаг — Python-оркестратор на
> Anthropic SDK + анти-галлюцинационные тесты.

## Текущее состояние

```
philology-research-agents/
├── README.md              ✅ двуязычный, самодостаточный
├── orchestrator.md        ✅ конвейер из 6 агентов, глобальные правила
├── combined-prompt.md     ✅ всё-в-одном (вставить в system message)
├── agents/ (6 шт.)        ✅ 1-researcher, 2-source-critic, 3-verifier, 4-analyst, 5-synthesizer, 6-editor
├── shared/ (3 шт.)        ✅ conventions, evidence-scale, source-hierarchy
├── editors/ (6 шт.)       ✅ ppv, iij, vdi, vya, jaos, olz
├── examples/ (1 шт.)      ✅ example-arya-RU.md — прогон всех 6 агентов
└── tools/                 ⬜ vak-philology-parser.md (заменен на tools/vak_parser.py)
```

## Фаза 1 — Python-оркестратор (≈2–3 дня)

**Цель:** легкий Python-скрипт, прогоняющий 6 агентов последовательно через Anthropic API.

### Компоненты

1. **`orchestrator.py`** — главный скрипт
   - Принимает вопрос пользователя (аргумент командной строки или stdin)
   - Загружает промпты агентов из `agents/*.md`
   - Загружает профиль журнала из `editors/<journal>.md`
   - Прогоняет агентов 1→6 последовательно, каждый получает выход предыдущего
   - Выводит структурированный ответ в терминал / Markdown-файл

2. **`requirements.txt`** → `anthropic>=0.39.0`

3. **Конфигурация:**
   - `ANTHROPIC_API_KEY` из `.env`
   - Модель: `claude-sonnet-4-20250514` (по умолчанию) / `claude-opus-4-20250514` (для сложных тем)
   - Temperature: 0.0 (консистентность для науки)
   - Max tokens: 4096 на агента

### Prompt caching
- Агенты 1–2 разделяют `shared/*.md` и `orchestrator.md` → cache breakpoint перед первым агентом
- Экономия: ~60% токенов на повторяющийся контекст

### Анти-галлюцинационные тесты
- `tests/test_anti_fabrication.py`:
  1. Выдуманный DOI → агент 3 (Верификатор) должен пометить "проверить"
  2. Несуществующий шифр рукописи → "требует сверки"
  3. Конъектура без пометки `*` → агент 4 должен понизить до D
  4. Транслитерация с нарушением IAST → агент 6 должен исправить

## Фаза 2 — Вынос в отдельный репозиторий (≈1 день)

```bash
git filter-repo --subdirectory-filter philology-research-agents/
# или ручное копирование с сохранением истории
```

Новый репо: `github.com/gasyoun/philology-research-agents`

### Структура нового репо
```
philology-research-agents/
├── README.md
├── LICENSE
├── .env.example
├── requirements.txt
├── orchestrator.py         # Python-оркестратор
├── orchestrator.md         # Дизайн-контракт
├── combined-prompt.md
├── agents/
├── shared/
├── editors/
├── examples/
├── tests/
│   └── test_anti_fabrication.py
└── .github/
    └── workflows/
        └── test.yml        # CI: прогон тестов на PR
```

## Фаза 3 — Англоязычный пример + документация (≈1 день)

- `examples/example-sanskrit-etymology-EN.md` — полный прогон на английском
- Обновить README.md: badges, quickstart, API reference

## Решения (зафиксировать)

1. Модель по умолчанию — Sonnet (дешевле, быстрее); Opus — для сложных тем опционально
2. Temperature 0.0 — наука не терпит креативности
3. Prompt caching — обязателен для экономии
4. Тесты — must-pass перед любым релизом
5. Лицензия — MIT (как наиболее переносимая)
