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
    # ---- batch 3 ----
    "Ю. М. Алиханова": ("кандидат филологических наук", "1970", "https://ru.wikipedia.org/wiki/Алиханова,_Юлия_Марковна", "high", "доцент ИСАА МГУ (1963–2016); дисс. «Трактат Анандавардханы о поэзии»; род. 1936 — проверить год смерти"),
    "Куликов Леонид Игоревич": ("кандидат филологических наук; PhD (Leiden)", "2001", "https://ru.wikipedia.org/wiki/Куликов,_Леонид_Игоревич", "high", "PhD Leiden 2001 «The Vedic -ya-presents»; род. 1964; ведийская лингвистика"),
    "Титлин Лев Игоревич": ("кандидат философских наук", "", "https://iphras.ru/titlin.htm", "high", "с.н.с. ИФ РАН; род. 1986; индийская/буддийская философия"),
    "C. В. Кулланда": ("кандидат исторических наук", "1988", "https://ru.wikipedia.org/wiki/Кулланда,_Сергей_Всеволодович", "high", "УМЕР 30.11.2020; род. 1954; скифология/иранистика"),
    # ---- batch 4 ----
    "А. В. Ложкина": ("кандидат философских наук", "2020", "https://iphras.ru/lozhkina.htm", "high", "ФЛАГ имени: реально Ложкина Анастасия Витальевна, род. 1992 (в БД 1989); ИФ РАН"),
    "Д. И. Жутаев": ("(степень не подтверждена; аспирант ИВ РАН)", "", "https://ru.wikipedia.org/wiki/Жутаев,_Дар_Игоревич", "medium", "ФЛАГ имени: реально ЖУТАЕВ ДАР Игоревич (не Дмитрий), род. 1969 (в БД 1968), УМЕР 01.02.2020; санскритолог/переводчик"),
    # ---- batch 5 ----
    "Ренковская Евгения Алексеевна": ("кандидат филологических наук", "2021", "https://istina.msu.ru/profile/Zumrutanka/", "high", "ИЯз РАН; дисс. по языку кумаони (25.02.2021)"),
    "Крылова Анастасия Сергеевна": ("кандидат филологических наук", "", "https://ivran.ru/persons/AnastasiyaKrylova", "high", "ИВ РАН; полевая лингвистика, индоарийские языки"),
    "Комиссаров Дмитрий Алексеевич": ("кандидат филологических наук", "2012", "https://www.hse.ru/org/persons/209813167/", "high", "доцент ИКВИА ВШЭ; род. 1977; хинди/санскрит"),
    # ---- batch 6 ----
    "Е. Д. Огнева": ("кандидат исторических наук", "1979", "https://ru.wikipedia.org/wiki/Огнева,_Елена_Дмитриевна", "high", "род. 1944; тибетология, иконография; Киев — проверить год смерти"),
    # ---- batch 7 ----
    "Крапивина Раиса Николаевна": ("кандидат исторических наук", "1983", "http://www.orientalstudies.ru/rus/index.php?option=com_personalities&Itemid=74&person=34", "high", "ФЛАГ имени: в BIOGRAPHICAL_DATA «Рада Нельсовна» НЕВЕРНО → Раиса Николаевна (Wikipedia/ИВР РАН); ИВР РАН тибетолог"),
    "Бабин Александр Николаевич": ("кандидат искусствоведения (аспирантура ГИИ 2019, требует подтверждения защиты)", "", "https://www.hse.ru/org/persons/224289991/", "medium", "ФЛАГ: искусствовед (индийская живопись), НЕ философ; ст. преп. ВШЭ"),
    # ---- pending (degree not confirmed via search; need manual / page fetch) ----
    "Д. Н. Лелюхин": ("", "", "https://www.ivran.ru/persons/931", "pending", "ИВ РАН, специалист по Артхашастре/др.-инд. государству; степень (вероятно к.и.н.) источником НЕ подтверждена"),
    "Смирнитская Анна Александровна": ("", "", "", "pending", "ИВ РАН, тамильский/дравидийские; степень не найдена"),
    "Гордийчук Николай Валентинович": ("", "", "https://www.ivran.ru/persons/GordijchukNikolajValentinovich", "pending", "ИВ РАН; степень не подтверждена в выдаче"),
    "Мехакян Арег Гайкович": ("", "", "", "pending", "ИВ РАН, junior; степень не найдена; ВОЗМОЖЕН дубль с «А. А. Мехакян»"),
    "А. А. Мехакян": ("", "", "", "pending", "ДУБЛЬ? сверить с «Мехакян Арег Гайкович» (А.Г. vs А.А.) — задача дедупликации"),
    "Кузина Елизавета Олеговна": ("", "", "", "pending", "РУДН, ученица Парибка; вероятно аспирант/недавняя к.филос.н."),
    "Уланский Евгений Александрович": ("", "", "https://istina.msu.ru/profile/ulanskiy/", "pending", "ИСАА МГУ, грамматика Панини; род. 1981; степень не подтверждена"),
    "Е. А. Юдицкая": ("", "", "", "pending", "ИВ РАН; не найдена"),
    "Гасунс Марцис Юрьевич": ("", "", "", "self", "АВТОР — заполнить самостоятельно"),
    "Минаева Маргарита Денисовна": ("", "", "", "pending", "род. 1999, ИКВИА ВШЭ — вероятно аспирант (без степени); ФЛАГ имени: в BIOGRAPHICAL_DATA «Мария Дмитриевна»"),
    "Молина Анна Вениаминовна": ("", "", "", "pending", "род. 1999, ИМЛИ РАН — вероятно аспирант (без степени)"),
    "Фивейская А. В.": ("", "", "", "pending", "род. 1993, ИСАА МГУ — вероятно аспирант"),
}


def main():
    rows = list(csv.DictReader(QUEUE.open(encoding="utf-8")))
    fields = rows[0].keys()
    if "note" not in fields:
        fields = list(fields) + ["note"]

    def norm(s: str) -> str:
        return s.replace("\xa0", " ").strip()

    batch_norm = {norm(k): v for k, v in BATCH.items()}
    matched = 0
    for r in rows:
        b = batch_norm.get(norm(r["display_name"]))
        if b:
            r["degree"], r["degree_year"], r["degree_source_url"], r["confidence"], note = b
            r["note"] = note
            matched += 1
    for r in rows:
        r.setdefault("note", "")
    with QUEUE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader(); w.writerows(rows)
    present = {norm(r["display_name"]) for r in rows}
    missing = [k for k in BATCH if norm(k) not in present]
    print(f"Applied {matched}/{len(BATCH)} batch rows to {QUEUE.name}")
    if missing:
        print("UNMATCHED display_names:", missing)


if __name__ == "__main__":
    main()
