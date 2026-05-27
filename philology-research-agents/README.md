# Philology Research Agents · Филологическая исследовательская лаборатория

> A portable, tool-agnostic multi-agent prompt module for **evidence-based scholarship
> in linguistics, philology, and Oriental studies (esp. Indology)**.
>
> Портативный, не зависящий от инструмента модуль мультиагентных промптов для
> **доказательной работы в языкознании, филологии и востоковедении (в частности индологии)**.

---

## RU — Что это

Это модуль из шести системных промптов («агентов»), которые работают как единый
последовательный конвейер «исследовательской лаборатории внутри одной модели».
Он создан для гуманитарных дисциплин, где доказательством служат **первоисточники,
критические издания, рукописные свидетели, засвидетельствованность форм,
сравнительно-исторический метод и текстология**, а не выборки, p-значения и RCT.

Модуль происходит от общенаучного промпта (`../article/scientific_paper_prompt.md`),
но доказательная модель полностью переработана под филологию: см.
`shared/evidence-scale.md` и `shared/source-hierarchy.md`.

### Шесть агентов (конвейер)

| # | Агент | Назначение |
|---|-------|-----------|
| 1 | **Исследователь** | Вторичная литература, обзоры, состояние вопроса (Forschungsstand) |
| 2 | **Филолог-источниковед** | Первоисточники, критические издания, рукописные свидетели, редакции/рецензии, датировка, атрибуция, транслитерация |
| 3 | **Верификатор** | Существование и точность ссылок, чтений и шифров; маркировка вероятных галлюцинаций |
| 4 | **Критический аналитик** | Аргументативное и методологическое качество; шкала доказательности A–E |
| 5 | **Синтезатор** | Сводный вердикт, надёжность 1–10, уровень консенсуса |
| 6 | **Редактор-оформитель** | Терминология, нормализация транслитерации (IAST и др.), цитирование, References на латинице (правила ППВ/ГОСТ) |

### Как использовать

**Вариант A — всё в одной модели (проще всего).**
Скопируйте содержимое `combined-prompt.md` в системное сообщение (ChatGPT custom
instructions, Claude.ai Project instructions, system-промпт через API) и задавайте
вопросы. Модель сама прогонит все шесть ролей и выдаст структурированный ответ.

**Вариант B — по-агентно (точный контроль).**
Используйте `orchestrator.md` как ведущий промпт, затем подавайте на вход каждому
агенту (`agents/1-researcher.md` … `agents/6-editor.md`) выход предыдущего. Подходит
для API-оркестрации и для сложных тем, где нужен контроль на каждом шаге.

**Вариант C — выборочно.**
Любого агента можно вызвать отдельно: например, только `agents/2-source-critic.md`
для проверки рукописной традиции одного чтения или `agents/6-editor.md` для приведения
References к латинице под подачу в журнал.

### Как переносить в другой репозиторий

Модуль самодостаточен: нет внешних зависимостей, путей или кода, привязанного к
конкретному репозиторию. Скопируйте всю папку `philology-research-agents/` куда угодно.
Единственное, что стоит проверить при переносе, — целевой стиль цитирования в
`shared/conventions.md` и `agents/6-editor.md` (по умолчанию — ППВ «Письменные
памятники Востока»).

---

## EN — What this is

Six system prompts ("agents") that run as one sequential "research-lab-inside-a-model"
pipeline, built for the humanities — where evidence means **primary sources, critical
editions, manuscript witnesses, attestation, the comparative method, and textual
criticism**, not samples, p-values, and RCTs.

It descends from a general-science prompt (`../article/scientific_paper_prompt.md`),
but its evidence model has been fully rebuilt for philology: see
`shared/evidence-scale.md` and `shared/source-hierarchy.md`.

### Six agents (pipeline)

| # | Agent | Purpose |
|---|-------|---------|
| 1 | **Researcher** | Secondary literature, surveys, state of the question |
| 2 | **Source & Textual Critic** | Primary sources, critical editions, MS witnesses, recensions, dating, attribution, transliteration |
| 3 | **Verifier** | Existence & accuracy of references, readings, shelf-marks; flags likely hallucinations |
| 4 | **Critical Analyst** | Argumentative & methodological quality; A–E evidence scale |
| 5 | **Synthesizer** | Integrated verdict, 1–10 reliability, level of consensus |
| 6 | **Scholarly Editor** | Terminology, transliteration normalization (IAST etc.), citation, Latin-script References (ППВ/GOST) |

### How to use

- **A — one model (simplest):** paste `combined-prompt.md` into a system message and ask.
- **B — per agent (full control):** drive `orchestrator.md`, then feed each agent the
  previous agent's output. Good for API orchestration.
- **C — à la carte:** call any single agent on its own.

### Porting

Self-contained, no external dependencies. Copy the whole folder. On porting, just check
the target citation style in `shared/conventions.md` and `agents/6-editor.md`
(default: ППВ / *Pis'mennye pamiatniki Vostoka*).

---

## File map · Карта файлов

```
philology-research-agents/
├── README.md                 # this file · этот файл
├── orchestrator.md           # master prompt: lab framing, pipeline, output format
├── combined-prompt.md        # all-in-one, paste into any chat · всё-в-одном
├── agents/
│   ├── 1-researcher.md
│   ├── 2-source-critic.md    # Филолог-источниковед (new · новый)
│   ├── 3-verifier.md
│   ├── 4-analyst.md
│   ├── 5-synthesizer.md
│   └── 6-editor.md           # Редактор-оформитель (new · новый)
├── shared/
│   ├── source-hierarchy.md   # priority of source types in the humanities
│   ├── evidence-scale.md     # A–E redesigned + the "recency" correction
│   └── conventions.md        # anti-fabrication, transliteration, IDs, citation, tone
├── editors/                  # one journal = one editor profile · один журнал = один профиль
│   ├── README.md             # how to add a journal · как добавить журнал
│   └── ppv.md                # ППВ «Письменные памятники Востока» house style
└── examples/
    └── example-arya-RU.md    # worked run of all 6 agents · прогон всех 6 агентов
```

> **Editor is journal-specific.** Agent 6 supplies editor *behaviour*; a file in
> `editors/` supplies one journal's *house style*. The default profile is ППВ.
> **Редактор зависит от журнала.** Агент 6 задаёт *поведение*; файл в `editors/` —
> *стиль* одного журнала. Профиль по умолчанию — ППВ.

## License / Лицензия

Inherits the license of the host repository. · Наследует лицензию репозитория-носителя.
