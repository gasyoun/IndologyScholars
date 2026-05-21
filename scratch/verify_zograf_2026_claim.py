"""
Верификация риторики Зографа-2026:
«В работе конференции примут участия ученые-индологи из профильных
академических учреждений России и зарубежья.»

Проверяется доля участников, чьи аффилиации:
  A) ВЕРИФИЦИРОВАННО академические профильные (РАН институты, профильные ВУЗы);
  B) ПОГРАНИЧНЫЕ — государственный музей/архив не-восточный, региональный ВУЗ
     без индологической кафедры;
  C) НЕ-академические — школа, независимый исследователь, отсутствие учреждения;
  D) НЕИЗВЕСТНО — в программе только город, в БД исторических аффилиаций нет.
"""

import sys
import csv
import sqlite3
from collections import defaultdict, Counter

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

DB = "conferences.db"

# Категории профильных академических учреждений (whitelist).
ACADEMIC_RAS = {
    "ИВР РАН", "СПбФ ИВ РАН", "ИВ РАН", "ИФ РАН", "Институт философии РАН",
    "МАЭ РАН", "МАЭ", "Кунсткамера", "ИМЛИ РАН", "ИЯЗ РАН", "ИЯ РАН",
    "Институт языкознания РАН", "ИЭА РАН", "Институт этнологии",
    "ИВИ РАН", "ИНИОН РАН", "ЦИИ ИВ РАН",
}
ACADEMIC_UNI = {
    "СПбГУ", "Восточный факультет СПбГУ", "ИСАА МГУ", "МГУ", "РГГУ",
    "НИУ ВШЭ", "ИКВИА НИУ ВШЭ", "ВШЭ", "РУДН", "КФУ", "УрФУ", "ПГУ",
    "РГПУ", "РГПУ им. Герцена", "Институт философии человека РГПУ",
    "СПбГИК", "СПбДА", "Государственный Эрмитаж",  # музей с восточным фондом
    "Гентский университет", "Ghent", "Гент",
    "Тель-Авивский университет", "Тель-Авив",
    "Delhi University", "JNU", "Дели",
}
ACADEMIC_TOKENS = [
    "РАН", "СПбГУ", "МГУ", "РГГУ", "НИУ ВШЭ", "ВШЭ", "РУДН", "КФУ",
    "УрФУ", "ПГУ", "РГПУ", "ИКВИА", "ИВР", "ИВ ", "ИФ ", "МАЭ", "ИМЛИ",
    "ИЯЗ", "ИЭА", "ЦИИ", "Кунсткамера", "Эрмитаж",
    "университет", "Ghent", "JNU",
]
NON_ACADEMIC_TOKENS = [
    "школ", "независимый", "ни / ", " ни ", "независим",
]


def classify_affiliation(affil_raw: str, historical_affils: list[str]) -> tuple[str, str]:
    """Return (category, evidence). category ∈ {A,B,C,D}."""
    if not affil_raw:
        return ("D", "пусто")

    # 2026 program records only the city in parens. We must cross-reference with
    # the historical affiliations of the same person from prior years.
    affil_norm = affil_raw.strip()

    # Step 1: program-line evidence. Some 2026 entries list only "Москва", "СПб" etc.
    # — these are NOT institutional. Treat program line as too thin and consult history.
    city_only = bool(_is_city_only(affil_norm))

    # Step 2: build a unified evidence string from program + history.
    history = " | ".join(historical_affils)
    evidence_blob = affil_norm + " || " + history

    # Non-academic markers (school, independent researcher) — strongest signal.
    low = evidence_blob.lower()
    if any(tok in low for tok in NON_ACADEMIC_TOKENS):
        return ("C", evidence_blob[:160])
    if "средн" in low and "школ" in low:
        return ("C", evidence_blob[:160])

    # Academic markers — substring search.
    for tok in ACADEMIC_TOKENS:
        if tok in evidence_blob:
            return ("A", evidence_blob[:160])

    # Border / unknown
    if city_only and not history.strip():
        return ("D", f"только город '{affil_norm}', истории нет")
    return ("B", evidence_blob[:160])


def _is_city_only(s: str) -> bool:
    cities = {
        "Москва", "Санкт-Петербург", "СПб", "Питер",
        "Казань", "Калининград", "Новгород", "Екатеринбург", "Пенза",
        "Тель-Авив", "Дели", "Гент", "Патмос", "Фронт-Ройал",
        "Москва - Патмос", "Москва – Патмос",
    }
    return s in cities or all(part.strip() in cities for part in s.split(","))


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT pp.presentation_id, pers.person_id, pers.display_name, pers.full_name_ru,
               pp.affiliation_text_raw, pres.title, pres.is_online,
               pp.role, pp.author_order,
               ed.day_number, ed.calendar_date
          FROM presentation_person pp
          JOIN person pers ON pers.person_id = pp.person_id
          JOIN presentation pres ON pres.presentation_id = pp.presentation_id
          JOIN session s ON s.session_id = pres.session_id
          JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
          JOIN event_day ed ON ed.event_day_id = edv.event_day_id
          JOIN event e ON e.event_id = ed.event_id
         WHERE e.event_id = 'E2026'
         ORDER BY ed.day_number, s.session_id, pp.author_order
    """)
    rows = cur.fetchall()

    print(f"Total 2026 participation rows: {len(rows)}")

    # For each person, fetch historical affiliations from prior events
    out_path = "analytics_output/zograf_2026_affiliation_audit.csv"
    categories = Counter()
    out_rows = []

    for r in rows:
        pres_id, pid, display, fullname, affil2026, title, online, role, order_idx, day_n, day_date = r

        # Fetch historical affils for this person from non-2026 events
        cur.execute("""
            SELECT DISTINCT pp.affiliation_text_raw, e.year, es.series_name_en
              FROM presentation_person pp
              JOIN presentation pres ON pres.presentation_id = pp.presentation_id
              JOIN session s ON s.session_id = pres.session_id
              JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
              JOIN event_day ed ON ed.event_day_id = edv.event_day_id
              JOIN event e ON e.event_id = ed.event_id
              JOIN event_series es ON es.event_series_id = e.event_series_id
             WHERE pp.person_id = ? AND e.event_id != 'E2026'
             ORDER BY e.year DESC
        """, (pid,))
        hist = cur.fetchall()
        hist_strs = [f"{a} ({y} {s})" for (a, y, s) in hist if a]

        cat, evidence = classify_affiliation(affil2026 or "", [a for (a, _, _) in hist if a])
        categories[cat] += 1

        out_rows.append({
            "day": day_n,
            "date": day_date,
            "person_display": display,
            "full_name": fullname or "",
            "role": role,
            "order": order_idx,
            "affil_2026": affil2026 or "",
            "is_online": online or 0,
            "category": cat,
            "history_count": len(hist_strs),
            "history_sample": " | ".join(hist_strs[:3]),
            "title": (title or "")[:140],
        })

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print(f"\nWrote {out_path} ({len(out_rows)} rows)")
    print("\nCategory breakdown:")
    total = sum(categories.values())
    for c in ["A", "B", "C", "D"]:
        n = categories[c]
        pct = 100 * n / total if total else 0
        label = {
            "A": "Профильные академические (РАН/ВУЗы)",
            "B": "Пограничные / нестандартные",
            "C": "НЕ-академические (школа, независимый)",
            "D": "Только город, без аффилиации",
        }[c]
        print(f"  [{c}] {label}: {n}/{total} ({pct:.1f}%)")

    # Который процент НЕ соответствует риторике "профильных академических"?
    not_compliant = categories["B"] + categories["C"] + categories["D"]
    print(f"\nНЕ соответствует риторике 'профильные академические учреждения': "
          f"{not_compliant}/{total} ({100*not_compliant/total:.1f}%)")

    # Список конкретных НЕ-академических случаев (категория C)
    print("\n--- Категория C (НЕ-академические) ---")
    for r in out_rows:
        if r["category"] == "C":
            print(f"  {r['person_display']} | program: '{r['affil_2026']}' | hist: {r['history_sample']}")

    print("\n--- Категория D (только город, нет истории) ---")
    for r in out_rows:
        if r["category"] == "D":
            print(f"  {r['person_display']} | program: '{r['affil_2026']}'")

    print(f"\n--- Категория B (пограничные/нестандартные, sample) ---")
    b_rows = [r for r in out_rows if r["category"] == "B"]
    for r in b_rows[:15]:
        print(f"  {r['person_display']} | program: '{r['affil_2026']}' | hist: {r['history_sample'][:120]}")

    conn.close()


if __name__ == "__main__":
    main()
