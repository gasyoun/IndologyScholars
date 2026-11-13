# -*- coding: utf-8 -*-
"""build_scan_priority_md.py — сборка итогового library/libfl-scan-priority.md.

Входы:
  library/libfl-scan-candidates.csv — перебор (rubric,section,record_id,citation,url)
  scratch/libfl-scan-scores.csv     — уникальные записи + оси/скоринг
  scratch/demand_index.csv, scratch/rarity_seeds.txt — факты истории ОРС (для раздела «Критерии»)

Выход: library/libfl-scan-priority.md
  1) Метод и критерии интересности (с числами истории выкладок)
  2) Топ-100 к немедленному сканированию
  3) Сводка по секциям/рубрикам
  4) Исчерпывающие таблицы по рубрикам (все записи, сортировка по score)

Запуск: python build_scan_priority_md.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "library" / "libfl-scan-candidates.csv"
SCORES = Path(__file__).resolve().parent / "libfl-scan-scores.csv"
OUT = ROOT / "library" / "libfl-scan-priority.md"

SECTION_TITLES = {
    "1": "① Языкознание / санскрит",
    "2": "② Индийская литература",
    "3": "③ Индия — гуманитарный контекст",
    "4": "④ Индия — прикладное",
    "5": "⑤ Широкое востоковедение",
}

MAX_CIT = 150  # усечение цитат в таблицах


def trunc(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    if len(s) > MAX_CIT:
        s = s[: MAX_CIT - 1].rstrip() + "…"
    return s.replace("|", "\\|")


def main():
    scores = {}
    order = []
    with SCORES.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            scores[r["record_id"]] = r
            order.append(r["record_id"])

    rubric_rows = defaultdict(list)  # rubric -> [record_id]
    rubric_section = {}
    total_rows = 0
    all_ids = set()
    with CAND.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rubric_rows[r["rubric"]].append(r["record_id"])
            rubric_section[r["rubric"]] = r["section"]
            total_rows += 1
            all_ids.add(r["record_id"])

    # исключённые по library/libfl-scan-exclusions.txt: есть в переборе, нет в скоринге
    excluded_ids = all_ids - set(scores)
    excl_lines = []
    excl_path = ROOT / "library" / "libfl-scan-exclusions.txt"
    if excl_path.exists():
        excl_lines = [
            ln.rstrip() for ln in excl_path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")
        ]

    n_unique = len(scores)
    ia_true = sum(1 for r in scores.values() if r["ia_hit"] == "True")
    ia_false = sum(1 for r in scores.values() if r["ia_hit"] == "False")
    ia_unk = sum(1 for r in scores.values() if r["ia_hit"] not in ("True", "False"))
    dli_true = sum(1 for r in scores.values() if r["dli_hit"] == "True")
    dli_false = sum(1 for r in scores.values() if r["dli_hit"] == "False")
    mentions = sum(1 for r in scores.values() if r["mentions"] and r["mentions"] != "0")
    y1960 = sum(1 for r in scores.values() if r["year"] and r["year"].isdigit() and int(r["year"]) <= 1960)

    sec_stats = defaultdict(lambda: {"rubrics": 0, "rows": 0, "uniq": set()})
    for rub, ids in rubric_rows.items():
        sec = rubric_section[rub]
        sec_stats[sec]["rubrics"] += 1
        sec_stats[sec]["rows"] += len(ids)
        sec_stats[sec]["uniq"].update(ids)

    L = []
    A = L.append
    A("# Книги Иностранки на сканирование — приоритеты для выкладок ОРС")
    A("")
    A("_Created: 13-11-2026 · Last updated: 13-11-2026 · Источники: [libfl-rubrics.md](libfl-rubrics.md) (рубрики) · [libfl-scan-candidates.csv](libfl-scan-candidates.csv) (перебор каталога 12–13.11.2026) · `scratch/libfl-scan-scores.csv` (оси и score)_")
    A("")
    A("**Назначение.** Исчерпывающий список книг фонда РБИ («Иностранка») по рубрикам "
      "libfl-rubrics.md, у которых **нет электронного издания** (серый бейдж на странице записи "
      "— в отличие от зелёного «Читать в библиотеке»), — кандидаты на сканирование и выкладку "
      "в Обществе ревнителей санскрита. Сверху — топ-100 для немедленного сканирования, ниже — "
      "сводка и исчерпывающие таблицы по каждой рубрике.")
    A("")
    A("## Как это считалось (метод)")
    A("")
    A(f"- **Перебор.** 120 рубрик (все строки таблиц + смежные рубрики из всех 5 секций "
      f"libfl-rubrics.md), вежливый режим (PoW-handshake, ≥1.2 с/запрос). Фильтр-кандидат: "
      f"`filter[]=topic_facet:\"…\"` **+** `filter[]=-MethodOfAccess:\"4002\"` — комплемент "
      f"«Удалённый доступ» (= есть электронная копия). Итог: **{total_rows} строк** "
      f"рубрика×запись, **{n_unique} уникальных записей** без электронного издания.")
    A("- **Критерий интересности — гибрид 40/30/30** (интервью grill-with-docs, 12-11-2026):")
    A("  - **спрос 40%** — percentile `year_ratio` (лайки книжного поста ÷ среднее лайков книжных "
      "постов того же года) по упоминаниям книги в истории ОРС (399 книжных doc-постов VK, "
      "2015–2026; после чистки от слайпов каталожных полей libfl — 305 контекстных упоминаний); "
      "матчинг — по не-стоп-токенам (без «словарь/грамматика/москва/sanskrit» и т.п.): "
      "≥3 токенов либо ≥2 с одним ≥10 символов; неупомянутые индологические книги берут "
      "медианный процентиль своего жанра, неупомянутые вне индологии — консервативные 0.30;")
    A("  - **канон 30%** — жанровый вес по заглавию: словари 1.00, учебники/грамматика 0.90, "
      "эпос/переводы 0.85, веды 0.80, буддология 0.65, общая индология 0.50, прочее 0.40, "
      "диссертации 0.10 (вкл. англ. [Diss.]/Thesis) — по долям аудиторного интереса истории "
      "(словари 21.3% + учебники 15.3% + эпос 8.8% ≈ 45% книжных лайков; диссертации 0.8%). "
      "**Индологический гейт:** бонус жанра действует только для книг об Индостане/санскрите "
      "(по заглавию); для прочих тем потолок 0.35 — японский Wörterbuch или Chontal dictionary "
      "не должны стоять рядом с Кочергиной;")
    A("  - **редкость 30%** — нет в archive.org (+0.5), нет в DLI (+0.2), год ≤ 1960 (+0.2), "
      "есть в «Очереди изданий на оцифровку в Иностранке» 2021 или тредах «Ищу книгу» (+0.1).")
    A("- **Внешняя проверка полная, пачками:** archive.org advancedsearch (пачки по 20 заголовков) "
      "+ зеркало DLI (`collection:digitallibraryindia`), затем **точная индивидуальная верификация "
      f"топ-{min(400, n_unique)}** (AND-запрос `title:(w1 AND w2 …)`) — пакетный проход даёт "
      "false negatives (типичный пример — Dowson/Monier-Williams «нет на IA» при фактическом "
      "наличии). Ниже топ-400 возможны остаточные false negatives по IA/DLI.")
    A("- **Точность матчинга спроса:** ≥3 длинных токена заглавия в тексте поста (или ≥2 с одним "
      "≥10 символов); лайки нормированы по году (2022 avg 67.5, 2023 avg 56.8 — иначе год "
      "пика искажает процентили).")
    A("- **Ограничения.** robots.txt `/Search/**` обойдён вежливо по явному решению пользователя; "
      "записи без извлечённого заглавия (погрешность парсера выдачи) верифицировать не удалось — "
      "оси у них консервативные.")
    A("")
    A("## Топ-100 к немедленному сканированию")
    A("")
    A("| # | score | спрос | канон | редкость | IA | DLI | год | Издание | Запись |")
    A("|---:|---:|---:|---:|---:|:-:|:-:|--:|---|---|")
    for rid in order[:100]:
        r = scores[rid]
        ia = "✅" if r["ia_hit"] == "True" else ("—" if r["ia_hit"] == "" else "❌")
        dli = "✅" if r["dli_hit"] == "True" else ("—" if r["dli_hit"] == "" else "❌")
        A(f"| {r['rank']} | {r['score']} | {r['axis_demand']} | {r['axis_canon']} | "
          f"{float(r['axis_rarity']):.1f} | {ia} | {dli} | {r['year'] or '—'} | "
          f"{trunc(r['citation'])} | [↗]({r['url']}) |")
    A("")
    A("_Легенда IA/DLI: ❌ = проверено, в интернете не найдено (бонус к редкости); "
      "✅ = найдено (сканировать не нужно — есть чем выложить); — = не проверено._")
    # серийные блоки: соседние строки top-100 с одним и тем же началом цитаты и годом
    runs, cur = [], None
    for rid in order[:100]:
        cit, yr = scores[rid]["citation"], scores[rid]["year"]
        key = (cit[:45], yr)
        if cur and cur["key"] == key:
            cur["n"] += 1
        else:
            cur = {"key": key, "n": 1, "label": cit[:70], "from": int(scores[rid]["rank"])}
            runs.append(cur)
    blocks = [r for r in runs if r["n"] >= 3]
    if blocks:
        A("")
        A("**Серийные блоки в топе** (многотомники идут подряд — это один проект сканирования, "
          "не 15 разных):")
        for r in blocks:
            A(f"- №{r['from']}–{r['from'] + r['n'] - 1} — {r['label']}… ({r['n']} позиций)")
    A("")
    A("## Сводка по секциям")
    A("")
    A("| Секция | Рубрик | Строк рубрика×запись | Уникальных кандидатов | Без IA | Без DLI | С упоминаниями в ОРС | Год ≤ 1960 |")
    A("|---|--:|--:|--:|--:|--:|--:|--:|")
    for sec in sorted(SECTION_TITLES):
        st = sec_stats.get(sec)
        if not st:
            continue
        ids = st["uniq"]
        sub = [scores[i] for i in ids if i in scores]
        A(f"| {SECTION_TITLES[sec]} | {st['rubrics']} | {st['rows']} | {len(ids)} | "
          f"{sum(1 for r in sub if r['ia_hit'] == 'False')} | "
          f"{sum(1 for r in sub if r['dli_hit'] == 'False')} | "
          f"{sum(1 for r in sub if r['mentions'] not in ('', '0'))} | "
          f"{sum(1 for r in sub if r['year'] and r['year'].isdigit() and int(r['year']) <= 1960)} |")
    A("")
    A(f"**Итого:** {total_rows} строк рубрика×запись в переборе; после исключений — "
      f"{n_unique} уникальных кандидатов без электронного издания. Внешняя проверка: "
      f"**нет на archive.org — {ia_false}**, найдено там — {ia_true}; "
      f"**нет в DLI — {dli_false}**, найдено — {dli_true}; "
      f"не проверено — {ia_unk} (записи без извлечённого заглавия). Топ-400 проверен "
      f"индивидуальными точными запросами (без пакетных false negatives). "
      f"С упоминаниями в истории ОРС — {mentions}; изданий ≤ 1960 г. — {y1960}.")
    A("")
    if excluded_ids or excl_lines:
        A(f"## Исключено из сканирования — {len(excluded_ids)} записей")
        A("")
        A("Основание — [libfl-scan-exclusions.txt](libfl-scan-exclusions.txt) (правка от "
          "13-11-2026; строки фильтруют и топ, и исчерпывающие таблицы):")
        A("")
        for ln in excl_lines:
            pat, _, reason = ln.partition("\t")
            A(f"- `{pat}` — {reason or 'причина не указана'}")
        A("")
        if excluded_ids:
            A("Затронутые записи перебора: " +
              ", ".join(f"`{i}`" for i in sorted(excluded_ids)) + ".")
            A("")
    A("")
    A("## Исчерпывающие таблицы по рубрикам")
    A("")
    A("_Все кандидаты без электронного издания, по каждой рубрике всех 5 секций, "
      "сортировка внутри — по score. IA: ❌ нет в интернете, ✅ есть, — не проверялось. "
      "Полный машинный вариант — [libfl-scan-candidates.csv](libfl-scan-candidates.csv) "
      "+ `scratch/libfl-scan-scores.csv`._")
    A("")

    # группировка рубрик по секциям, внутри — по имени
    by_sec = defaultdict(list)
    for rub in rubric_rows:
        by_sec[rubric_section[rub]].append(rub)

    for sec in sorted(SECTION_TITLES):
        A(f"### {SECTION_TITLES[sec]}")
        A("")
        for rub in sorted(by_sec[sec]):
            ids = rubric_rows[rub]
            ids_in = [i for i in ids if i in scores]
            uniq = sorted(set(ids_in), key=lambda i: float(scores.get(i, {}).get("score") or 0), reverse=True)
            n_excl = len(set(ids) - set(ids_in))
            tail = f", исключено {n_excl}" if n_excl else ""
            A(f"#### {rub} — {len(ids)} строк в переборе, {len(uniq)} кандидатов{tail}")
            A("")
            A("| score | IA | DLI | год | Издание | Запись |")
            A("|--:|:-:|:-:|--:|---|---|")
            for rid in uniq:
                r = scores.get(rid)
                if not r:
                    continue
                ia = "✅" if r["ia_hit"] == "True" else ("—" if r["ia_hit"] == "" else "❌")
                dli = "✅" if r["dli_hit"] == "True" else ("—" if r["dli_hit"] == "" else "❌")
                A(f"| {r['score']} | {ia} | {dli} | {r['year'] or '—'} | "
                  f"{trunc(r['citation'])} | [↗]({r['url']}) |")
            A("")

    A("---")
    A("")
    A("_Интервью: grill-with-docs, 12–13-11-2026. Решения: полный перебор 5 секций; "
      "гибрид 40/30/30; полная пакетная внешняя проверка; вежливый обход `/Search`; "
      "выдача — этот файл; топ-100; таблицы + смежные рубрики._")
    A("")
    A("_к.ф.н. М.Ю. Гасунс_")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"-> {OUT} ({OUT.stat().st_size} bytes, {len(L)} lines)")


if __name__ == "__main__":
    main()
