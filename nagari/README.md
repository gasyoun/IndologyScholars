_Created: 12-07-2026 · Last updated: 12-07-2026_

# nagari_group_archive — архив «Общество ревнителей санскрита» (2005–2026)

Воспроизводимый разбор закрытой гуглгруппы `nagari@googlegroups.com` из экспорта
Google Takeout в поисковую базу + аналитику + юбилейную страницу
**«20 лет Обществу ревнителей санскрита: история гуглгруппы»**.

Родственник по духу пакету
[Indology/indology_archive_research](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/README.md)
(атлас публичного списка INDOLOGY-L), но источник здесь — *закрытый* список,
экспортированный целиком, поэтому доступны **тела писем и метаданные вложений**, а
не только заголовки.

## Что внутри

| Стадия | Модуль | Делает |
|---|---|---|
| 1 | [ingest.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/ingest.py) | `topics.mbox` → SQLite (`messages`, `attachments`, `members`) + индекс `messages_fts` (FTS5, unicode61, диакритика свёрнута — `atman` находит `ātman`) |
| 2 | [insights.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/insights.py) | 4 слоя анализа → CSV в `data/processed/` + `data/site_data.json` |
| 3 | [export_md.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/export_md.py) | Markdown-зеркало: один `.md` на тред в `md/<год>/` для grep/Obsidian |
| 4 | [page.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/page.py) + [_template.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/_template.py) | самодостаточная HTML-страница (без CDN): нарратив + интерактивные SVG-графики + поиск |

### Четыре слоя анализа

1. **Хронология и активность** — сообщения/треды/авторы по годам и месяцам,
   вступления участников, тепловая карта год×месяц, сезонность.
2. **Треды и сети** — восстановление тредов по `X-GM-THRID`, направленная сеть
   ответов (`In-Reply-To`), сеть совместного участия, самые активные авторы.
3. **Темы и NLP по телам** — таксономия тем группы по ключевым словам над
   темой+телом, тренды тем, частотные термины (слой, который INDOLOGY-L пропустил
   за отсутствием тел).
4. **Санскрит и книгохранилище** — частоты деванагари и IAST, инвентарь вложений,
   индекс книг/сканов (PDF/DjVu/…), треды о шрифтах и юникоде.

## Запуск

Зависимостей нет — только стандартная библиотека Python 3.11+ (SQLite с FTS5).

```sh
cd nagari
python scripts/run_pipeline.py                 # ingest → insights → md → page
python scripts/run_pipeline.py --skip-ingest   # пересобрать анализ/страницу из готовой БД
python -m nagari_group_archive.ingest --limit 300   # быстрая проверка разбора
```

Сырой дамп читается из `--dump` (по умолчанию — копия в основном чекауте
IndologyScholars) и **никогда не изменяется**.

## Приватность и публикация

Это была **закрытая** группа (2 333 участника — третьи лица). Поэтому:

- **Сырой дамп, БД, `md/`, `site/` и `data/` — под `.gitignore` и в репозиторий не
  попадают.** Коммитится только код конвейера.
- В готовой странице **адреса почты не публикуются**: узлы сети — анонимные
  индексы; любые e-mail-подобные подписи и адреса в темах/именах файлов
  маскируются до `local@…`. Имена участников показываются (по решению владельца).
- Перед любой публикацией (GitHub Pages, samskrtam.ru) страница проходит
  `/publish-safety-check` — GO/NO-GO по третьим лицам, правам и утечкам.

## Оговорки (перенесены из атласа INDOLOGY-L)

- Связь ответа — это разговор, **а не влияние**.
- Совместное участие в теме — **не соавторство**.
- Счётчик сообщений — **не мера учёности**.
- Видимость в архиве — не представительность поля.
- Разные подписи и ники одного человека **здесь не объединены** в одну личность
  (нормализация авторов — отдельная задача).

_Auto-generated pipeline; page rendered by Opus 4.8 (`claude-opus-4-8`)._

_Dr. Mārcis Gasūns_
