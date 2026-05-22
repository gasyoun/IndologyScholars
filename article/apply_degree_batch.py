"""Apply a verified/looked-up degree batch into degree_lookup_queue.csv.

Edit BATCH below, run, then the author verifies the 'verified' column.
Matches by display_name. Does NOT touch conferences.db (DB integration is a
later step once rows are verified). Read/writes only the queue CSV.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

QUEUE = Path(__file__).resolve().parent / "hypothesis_output" / "degree_lookup_queue.csv"

# display_name -> (degree, degree_year, source_url, confidence, note)
BATCH = {
    "Лысенко Виктория Георгиевна": ("доктор философских наук", "", "https://ru.wikipedia.org/wiki/Лысенко,_Виктория_Георгиевна", "high", "проф.; зам. пред. экспертного совета ВАК по философии"),
    "Шохин Владимир Кириллович": ("доктор философских наук", "", "https://iphras.ru/shokhin.htm", "high", "проф.; зав. сектором философии религии ИФ РАН"),
    "Рыжакова Светлана Игоревна": ("доктор исторических наук", "", "https://iea-ras.ru/?page_id=6695", "high", "вед. науч. сотр. ИЭА РАН, проф. РГГУ"),
    "Дубянский Александр Михайлович": ("кандидат филологических наук", "1974", "https://ru.wikipedia.org/wiki/Дубянский,_Александр_Михайлович", "high", "УМЕР 18.11.2020 — добавить death_year"),
    "Вигасин Алексей Алексеевич": ("доктор исторических наук", "1995", "https://ru.wikipedia.org/wiki/Вигасин,_Алексей_Алексеевич", "high", "проф. (1998); дисс. о социальной структуре Древней Индии"),
    "Лидова Наталья Ростиславовна": ("кандидат филологических наук", "1991", "http://imli.ru/index.php/institut/sotrudniki/1156-lidova-natalya-rostislavovna", "high", "дисс. «Натьяшастра и истоки древнеиндийской драмы», ИМЛИ"),
    "В. В. Вертоградова": ("доктор филологических наук", "", "https://www.ivran.ru/persons/147", "high", "ЖИВА (corr.md): death_year НЕ ставить; вед. науч. сотр. ИВ РАН"),
    "Тавастшерна Сергей Сергеевич": ("кандидат филологических наук", "2009", "https://www.orient.spbu.ru/index.php/ru/o-fakultete/sotrudniki/item/tavastsherna-sergej-sergeevich", "high", "дисс. «Происхождение и развитие лингвистической традиции в Индии»"),
    "Цветкова Светлана Олеговна": ("кандидат филологических наук", "", "https://orient.spbu.ru/index.php/en/about-faas/academics/item/tsvetkova-svetlana-olegovna", "high", "доцент, зав. каф. индийской филологии СПбГУ (хинди)"),
    "Вечерина Ольга Павловна": ("кандидат исторических наук", "1998", "https://istina.msu.ru/workers/419301481/", "medium", "ФЛАГ: corr.md даёт 1960–2023, в БД birth_year=1963; дисс. «Ювелирный бизнес в Индии»"),
    # ---- batch 2 ----
    "Александрова Наталия Владимировна": ("кандидат исторических наук", "1989", "https://www.hse.ru/org/persons/210188843", "high", "ст. науч. сотр. ИКВИА НИУ ВШЭ; ранее ИВ РАН с 1988"),
    "Канаева Наталия Алексеевна": ("доктор философских наук", "2021", "https://www.hse.ru/staff/nkanaeva/", "high", "к.филос.н. 1990 → д.филос.н. 2021 (ИФ РАН); доцент ВШЭ"),
    "Воробьева Дарья Николаевна": ("кандидат искусствоведения", "2013", "https://sias.ru/institute/persons/3743.html", "high", "ст. науч. сотр. ГИИ; искусство Индии раннего средневековья"),
    "А. Г. Гурия": ("кандидат филологических наук", "", "https://istina.msu.ru/workers/111004308/", "medium", "науч. сотр. каф. индийской филологии ИСАА МГУ; год защиты не уточнён"),
    "Корнеева Наталья Афанасьевна": ("кандидат исторических наук", "", "https://www.dissercat.com/content/istochnikovedcheskii-analiz-vishnu-smriti-problemy-khronologii-i-perevoda", "high", "дисс. «Источниковедческий анализ Вишну-смрити», ВАК 07.00.09; ИВ РАН"),
}


def main():
    rows = list(csv.DictReader(QUEUE.open(encoding="utf-8")))
    fields = rows[0].keys()
    if "note" not in fields:
        fields = list(fields) + ["note"]
    matched = 0
    for r in rows:
        b = BATCH.get(r["display_name"])
        if b:
            r["degree"], r["degree_year"], r["degree_source_url"], r["confidence"], note = b
            r["note"] = note
            matched += 1
    for r in rows:
        r.setdefault("note", "")
    with QUEUE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader(); w.writerows(rows)
    missing = [k for k in BATCH if k not in {r["display_name"] for r in rows}]
    print(f"Applied {matched}/{len(BATCH)} batch rows to {QUEUE.name}")
    if missing:
        print("UNMATCHED display_names:", missing)


if __name__ == "__main__":
    main()
