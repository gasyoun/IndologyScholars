"""Cross-reference Wikipedia Indologists against conference participation database.

Loads Wikipedia list and site_data_scholars.json, matches names,
generates scratch/non_participants.md with analysis.
"""

import json
import re
import sys
from pathlib import Path

# Cyrillic to a Windows console (cp1251/cp866) prints as mojibake without this;
# the .md output was always correct UTF-8, only the progress echo was garbled.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
WIKI_JSON = SCRATCH / "wikipedia_indologists_expanded.json"
SCHOLARS_JSON = ROOT / "site_data_scholars.json"
OUTPUT_MD = SCRATCH / "non_participants.md"


def normalize(s: str) -> str:
    """Normalize name for matching: lowercase, ё→е, remove special chars."""
    s = s.lower().replace("ё", "е").strip()
    s = re.sub(r"[^а-яa-z -]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def match_score(wiki_person: dict, conf_person: dict) -> int:
    """Score the match between a Wikipedia entry and a conference entry.
    Returns 0-100. Requires surname match + first name verification."""
    w_surname = normalize(wiki_person.get("surname", ""))
    w_given_full = normalize(wiki_person.get("given_name", ""))
    w_given_parts = [p for p in w_given_full.split() if len(p) > 1]
    w_first_name = w_given_parts[0] if w_given_parts else ""

    c_full = normalize(conf_person.get("full_name_ru", ""))
    c_display = normalize(conf_person.get("display_name", ""))

    if not w_surname or len(w_surname) < 2:
        return 0

    # Split conf name parts
    c_parts = c_full.split() if c_full else c_display.split()
    if not c_parts:
        return 0

    # Conference data format: "Фамилия Имя Отчество" — surname is FIRST
    if len(c_parts) >= 2:
        c_surname = c_parts[0]
        c_first = c_parts[1] if len(c_parts) > 1 else ""
    else:
        c_surname = c_parts[0] if c_parts else ""
        c_first = ""

    # 1. Exact full name match (highest confidence)
    w_full = normalize(wiki_person.get("full_name", ""))
    if w_full and (w_full == c_full or w_full == c_display):
        return 100

    # 2. Surname must match
    if w_surname != c_surname:
        # Try fuzzy: surname is contained
        if len(w_surname) >= 5 and w_surname in c_surname:
            pass  # continue to given name check
        elif len(c_surname) >= 5 and c_surname in w_surname:
            pass  # continue
        else:
            return 0

    # 3. Verify first name
    if not w_first_name:
        # No first name in wiki — can't verify, lower confidence
        if w_surname == c_surname:
            return 40
        return 20

    # Check if first names match
    if w_first_name == c_first:
        return 95  # exact first name match
    # Check if one starts with the other (at least 2 chars)
    if c_first and len(c_first) >= 2 and w_first_name.startswith(c_first):
        return 88
    if c_first and w_first_name[:2] == c_first[:2] and len(w_first_name) >= 2:
        return 85  # same first 2+ letters
    # Initial match: same first letter AND one of them is just an initial
    if len(c_first) == 1 and c_first == w_first_name[0]:
        return 80  # "В." matches "Вячеслав"
    if len(w_first_name) == 1 and w_first_name == c_first[0]:
        return 80  # "В" matches "Владимир"
    # Name might be in different order (display_name often has initials)
    if len(w_first_name) >= 3 and w_first_name in " ".join(c_parts):
        return 78

    # Surname matches but first name doesn't — likely different person
    return 0


def load_conf_data() -> list[dict]:
    with open(SCHOLARS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_wiki_data() -> list[dict]:
    with open(WIKI_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    people = list(data.get("people", []))

    # Also include institutional additions that aren't in Wikipedia categories.
    # Skip initials-only entries (not real people, just partial data from conference DB).
    extra = data.get("new_from_institutions", [])
    for ep in extra:
        full_name = ep.get("full_name", "").strip()
        # Skip initials-only names like "А. В. Осокин" or "Ч. Санчай"
        if re.match(r'^[А-ЯЁ]\.\s*[А-ЯЁ]\.?\s*\S+', full_name):
            continue
        if len(full_name.split()) < 2:
            continue
        if not any(
            normalize(p.get("full_name", "")) == normalize(full_name)
            for p in people
        ):
            people.append({
                "wikipedia_title": full_name,
                "surname": full_name.split()[0],
                "given_name": " ".join(full_name.split()[1:]),
                "full_name": full_name,
                "birth_year": None,
                "death_year": None,
                "scientific_field": "",
                "role": "",
                "workplace": ep.get("institution", ""),
                "alma_mater": "",
                "degree": "",
                "wikidata_qid": "",
                "is_indologist": True,
                "source": ep.get("source", "conference_db"),
            })
    return people


def classify_participation(wiki: dict, conf: list[dict]) -> tuple[bool, dict | None]:
    best_score = 0
    best_match = None
    for c in conf:
        score = match_score(wiki, c)
        if score > best_score:
            best_score = score
            best_match = c
    return best_score >= 80, best_match


def affiliation_short(wiki: dict) -> str:
    wp = wiki.get("workplace", "")
    if not wp:
        return "-"
    if "Институт востоковедения РАН" in wp:
        return "ИВ РАН"
    if "ИСАА" in wp:
        return "ИСАА МГУ"
    if "МГУ" in wp:
        return "МГУ"
    if "РГГУ" in wp:
        return "РГГУ"
    if "ИМЛИ" in wp:
        return "ИМЛИ РАН"
    if "языкознания" in wp.lower():
        return "Ин-т языкознания РАН"
    if "РАН" in wp:
        m = re.search(r"(Институт\s+[а-яё]+\s+РАН)", wp, re.IGNORECASE)
        if m:
            return m.group(1)
        return wp[:50]
    if "университет" in wp.lower():
        return wp[:50]
    return wp[:50]


def role_short(wiki: dict) -> str:
    """Return concise role from Wikipedia infobox."""
    role = wiki.get("role", "").lower()
    sphere = wiki.get("scientific_field", "").lower()

    # Check for linguist-indologist
    if "лингвист" in role and "индолог" in role:
        return "лингвист-индолог"
    if "лингвист" in role:
        return "лингвист"
    if "историк" in role:
        return "историк"
    if "философ" in role:
        return "философ"
    if "филолог" in role:
        return "филолог"
    if "востоковед" in role:
        return "востоковед"
    if "ориенталист" in role:
        return "ориенталист"
    if "индолог" in role:
        return "индолог"
    if "ученый" in role or "учёный" in role:
        if "индолог" in sphere:
            return "индолог"
        return "учёный"
    if "перевод" in role:
        return "переводчик"
    if "этнограф" in role:
        return "этнограф"
    if "драв" in role:
        return "дравидолог"
    # Fallback: check sphere
    if "индолог" in sphere:
        return "индолог"
    if not role:
        return "—"
    return role[:40]


def years_str(wiki: dict) -> str:
    b = wiki.get("birth_year")
    d = wiki.get("death_year")
    if b and d:
        return f"{b}–{d}"
    if b:
        return f"{b}–"
    if d:
        return f"?–{d}"
    return "?"


def is_older_gen(wiki: dict) -> bool:
    b = wiki.get("birth_year")
    d = wiki.get("death_year")
    if d and d < 2004:
        return True
    if b and b < 1915:
        return True
    if b and b < 1935 and d and d < 2004:
        return True
    return False


def clean_field(val: str) -> str:
    """Clean HTML artifacts from extracted field values."""
    val = re.sub(r"\.mw-parser-output[^{]*\{[^}]*\}", " ", val)
    val = re.sub(r"\s*\d+\s*", " ", val)
    val = re.sub(r"\[\s*вд\s*\]", "", val)
    val = re.sub(r"\(\s*\)", "", val)
    val = re.sub(r"\s+и\s+$", "", val)
    val = re.sub(r"\s+", " ", val)
    return val.strip().rstrip(",;")


def generate_md(wiki_people: list[dict], conf_data: list[dict]) -> str:
    participants = []
    non_participants_alive = []
    non_participants_dead = []

    for w in wiki_people:
        found, match = classify_participation(w, conf_data)
        if found:
            participants.append((w, match))
        else:
            if is_older_gen(w):
                non_participants_dead.append(w)
            else:
                non_participants_alive.append(w)

    participants.sort(key=lambda x: -(x[1].get("total_talks", 0) if x[1] else 0))
    non_participants_alive.sort(key=lambda x: normalize(x.get("surname", "")))
    non_participants_dead.sort(key=lambda x: normalize(x.get("surname", "")))

    lines = []
    lines.append("# Русские индологи: участие в Рериховских и Зографских чтениях")
    lines.append("")
    lines.append(
        "Сопоставление списка индологов из Википедии "
        "(категории [Индологи России](https://ru.wikipedia.org/wiki/Категория:Индологи_России) "
        "и [Санскритологи России](https://ru.wikipedia.org/wiki/Категория:Санскритологи_России)) "
        "с базой докладов [Рериховских и Зографских чтений](https://gasyoun.github.io/IndologyScholars) "
        "за 2004–2026 гг."
    )
    lines.append("")

    # ---- Section 1: Non-participants (alive, significant) ----
    lines.append("## 1. Никогда не участвовали — значимые отсутствия")
    lines.append("")
    lines.append(
        "Индологи, которые могли бы участвовать (родились после ~1935, "
        "были живы в период конференций 2004–2026), но ни разу не выступали."
    )
    lines.append("")
    lines.append("| № | ФИО | Годы | Сфера | Роль | Место работы | Альма-матер | Степень |")
    lines.append("|---|-----|------|-------|------|-------------|------------|--------|")

    for i, w in enumerate(non_participants_alive, 1):
        name = w.get("full_name", w.get("wikipedia_title", "?"))
        yrs = years_str(w)
        sphere = clean_field(w.get("scientific_field", "—"))
        role = role_short(w)
        aff = affiliation_short(w)
        alma = clean_field(w.get("alma_mater", "—"))[:50]
        deg = clean_field(w.get("degree", "—"))[:60]
        lines.append(f"| {i} | **{name}** | {yrs} | {sphere} | {role} | {aff} | {alma} | {deg} |")

    lines.append("")
    lines.append(f"**Всего: {len(non_participants_alive)} человек.**")
    lines.append("")

    # ---- Section 2: Non-participants (deceased before conferences) ----
    lines.append("## 2. Не участвовали — умерли до 2004 г. или раннее поколение")
    lines.append("")
    lines.append("| № | ФИО | Годы | Сфера | Роль | Место работы |")
    lines.append("|---|-----|------|-------|------|-------------|")

    for i, w in enumerate(non_participants_dead, 1):
        name = w.get("full_name", w.get("wikipedia_title", "?"))
        yrs = years_str(w)
        sphere = clean_field(w.get("scientific_field", "—"))
        role = role_short(w)
        aff = affiliation_short(w)
        lines.append(f"| {i} | {name} | {yrs} | {sphere} | {role} | {aff} |")

    lines.append("")
    lines.append(f"**Всего: {len(non_participants_dead)} человек.**")
    lines.append("")

    # ---- Section 3: Participants ----
    lines.append("## 3. Участвовали хотя бы раз")
    lines.append("")
    lines.append("| № | ФИО | Зограф | Рерих | Всего | Годы | Поколение |")
    lines.append("|---|-----|--------|-------|-------|------|----------|")

    for i, (w, c) in enumerate(participants, 1):
        name = c.get("full_name_ru", c.get("display_name", "?"))
        z = c.get("zograf_talks", 0)
        r = c.get("roerich_talks", 0)
        t = c.get("total_talks", 0)
        first = c.get("first_year", "?")
        last = c.get("last_year", "?")
        gen = c.get("generation_label_ru", "—")
        lines.append(f"| {i} | {name} | {z} | {r} | {t} | {first}–{last} | {gen} |")

    lines.append("")
    lines.append(f"**Всего: {len(participants)} человек.**")
    lines.append("")

    # ---- Section 4: Commonality analysis ----
    lines.append("## 4. Что общего у отсутствующих")
    lines.append("")

    npa = non_participants_alive
    isaa_count = sum(1 for w in npa if "исаа" in (w.get("alma_mater", "") + w.get("workplace", "")).lower())
    ivran_count = sum(1 for w in npa if "востоковедения" in w.get("workplace", "").lower() or "ИВ РАН" in w.get("workplace", ""))
    linguist_count = sum(1 for w in npa if "лингвист" in w.get("role", "").lower())
    historian_count = sum(1 for w in npa if "историк" in w.get("role", "").lower())
    msu_alumni = sum(1 for w in npa if "мгу" in w.get("alma_mater", "").lower())
    spbu_alumni = sum(1 for w in npa if "лгу" in w.get("alma_mater", "").lower() or "спбгу" in w.get("alma_mater", "").lower())
    isaa_alumni = sum(1 for w in npa if "исаа" in w.get("alma_mater", "").lower())
    no_dates = sum(1 for w in npa if w.get("birth_year") is None)
    has_wikidata = sum(1 for w in npa if w.get("wikidata_qid"))

    lines.append(f"### Демография (N={len(npa)} живых, без участия)")
    lines.append("")
    lines.append(f"| Параметр | Кол-во |")
    lines.append(f"|----------|--------|")
    lines.append(f"| Связь с ИСАА (выпускники или сотрудники) | {isaa_alumni} |")
    lines.append(f"| Связь с ИВ РАН (место работы) | {ivran_count} |")
    lines.append(f"| Связь с Институтом языкознания РАН | {sum(1 for w in npa if 'языкознания' in w.get('workplace', '').lower())} |")
    lines.append(f"| Выпускники МГУ | {msu_alumni} |")
    lines.append(f"| Выпускники ЛГУ/СПбГУ | {spbu_alumni} |")
    lines.append(f"| Лингвисты (включая лингвист-индолог) | {linguist_count} |")
    lines.append(f"| Историки | {historian_count} |")
    lines.append(f"| С Wikidata Q-ID | {has_wikidata} |")
    lines.append(f"| Без года рождения | {no_dates} |")
    lines.append("")

    lines.append("### Ключевые фигуры среди отсутствующих")
    lines.append("")
    # List the most notable non-participants
    notable = [
        "**Глушкова И.П.** (ИВ РАН, рук. МПГ «Под небом Южной Азии») — умышленно избегает.",
        "**Ванина Е.Ю.** (ИВ РАН, зав. сектором) — сотрудничает с Глушковой.",
        "**Алаев Л.Б.** (ИВ РАН, 1932–2023) — классик индологии, оппонент Глушковой.",
        "**Эдельман Д.И.** (Ин-т языкознания РАН, 1930–) — иранист и индолог.",
        "**Топоров В.Н.** (1928–2005) — славист и индолог, московско-тартуская школа.",
        "**Столяров А.А.** (ИВ РАН/РГГУ) — собственный семинар «Белые пятна».",
        "**Захарьин Б.А.** (ИСАА, 1942–) — лингвист-индолог, кафедра индийской филологии.",
        "**Серебряный С.Д.** (ИМЛИ/РГГУ) — критик «советской парадигмы».",
        "**Бонгард-Левин Г.М.** (1933–2008) — академик, историк Индии.",
        "**Гринцер П.А.** (1928–2009) — литературовед, специалист по эпосу.",
        "**Зализняк А.А.** (1935–2017) — академик, лингвист (индология — не основная специализация).",
        "**Пятигорский А.М.** (1929–2009) — философ, востоковед, эмигрировал.",
        "**Челышев Е.П.** (1921–2020) — академик, литературовед-индолог.",
        "**Бухарин М.Д.** (1971–) — историк Древнего Востока, академик РАН.",
    ]
    for n in notable:
        lines.append(f"- {n}")
    lines.append("")

    lines.append("### Возможные объяснения")
    lines.append("")
    lines.append(
        "1. **Альтернативные площадки**. Глушкова И.П. создала междисциплинарную "
        "проект-группу «Под небом Южной Азии»; Столяров А.А. — семинар "
        "«Белые пятна в изучении Южной Азии». Это самостоятельные научные "
        "платформы, альтернативные Рериховским/Зографским чтениям."
    )
    lines.append(
        "2. **Московская школа vs Петербургская**. Рериховские чтения проходят "
        "в Москве (ИВ РАН), Зографовские — в Петербурге (ИВР РАН). "
        "Часть московских индологов не участвует в петербургских чтениях, "
        "но неприсутствие и на московских указывает на более глубокий разрыв."
    )
    lines.append(
        "3. **Поколенческий разрыв**. Старшее поколение (Алаев, Эдельман, "
        "Топоров, Бонгард-Левин) сформировалось в советский период и "
        "не включилось в постсоветскую конференционную сеть."
    )
    lines.append(
        "4. **Идейное размежевание**. Алаев, Серебряный, Глушкова занимали "
        "критическую позицию по отношению к «советской парадигме» "
        "в индологии и к её институциональным наследникам."
    )
    lines.append(
        "5. **Узкая специализация**. Эдельман — прежде всего иранист; "
        "Топоров — славист; Зализняк — русист; для них индология — "
        "смежная, а не основная область."
    )
    lines.append(
        "6. **Эмиграция**. Пятигорский А.М. с 1974 г. жил в Великобритании."
    )
    lines.append("")

    # ---- Section 5: Summary ----
    lines.append("## 5. Сводная статистика")
    lines.append("")
    lines.append(f"| Показатель | Значение |")
    lines.append(f"|-----------|---------|")
    lines.append(f"| Всего индологов из Википедии | **{len(wiki_people)}** |")
    lines.append(f"| Участвовали в чтениях | **{len(participants)}** |")
    lines.append(f"| Не участвовали (живы) | **{len(non_participants_alive)}** |")
    lines.append(f"| Не участвовали (умерли до 2004 / раннее поколение) | **{len(non_participants_dead)}** |")
    lines.append(f"| Из 270 участников чтений — есть в вики-категориях | **{len(participants)}** |")
    lines.append("")

    # ---- Section 6: Sources ----
    lines.append("## 6. Источники")
    lines.append("")
    lines.append("- [Категория:Индологи России](https://ru.wikipedia.org/wiki/Категория:Индологи_России) — Wikipedia")
    lines.append("- [Категория:Санскритологи России](https://ru.wikipedia.org/wiki/Категория:Санскритологи_России) — Wikipedia")
    lines.append("- [Архив Рериховских и Зографских чтений](https://gasyoun.github.io/IndologyScholars) — М.Ю. Гасунс")
    lines.append("- Скрипты: `scratch/expand_wikipedia_indologists.py`, `scratch/crossref_nonparticipants.py`")
    lines.append("")

    return "\n".join(lines)


def main():
    print("=== Cross-referencing Wikipedia Indologists vs Conference Database ===")

    wiki_people = load_wiki_data()
    conf_data = load_conf_data()

    print(f"Wikipedia people: {len(wiki_people)}")
    print(f"Conference scholars: {len(conf_data)}")

    found_count = 0
    for w in wiki_people:
        found, match = classify_participation(w, conf_data)
        if found:
            found_count += 1
            z = match.get("zograf_talks", 0)
            r = match.get("roerich_talks", 0)
            conf_name = match.get("full_name_ru", match.get("display_name", ""))
            status = "BOTH" if z > 0 and r > 0 else ("Z" if z > 0 else "R")
            print(f"  MATCH: {w['full_name']} -> {conf_name} (Z:{z} R:{r} {status})")
        else:
            print(f"  NO:    {w['full_name']}")

    print(f"\nMatched: {found_count}, Not matched: {len(wiki_people) - found_count}")

    md_content = generate_md(wiki_people, conf_data)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Markdown saved to: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
