"""
Baseline keyword-rules для тематической разметки докладов на 4 осях:
  L1 — дисциплина (linguistics, philosophy, literature, history, religion, tibetology)
  L2 — период    (vedic, classical, medieval, colonial, modern, contemporary)
  L3 — материал  (text, fieldwork, archive, artefact, image)
  L4 — характер  (fundamental, applied, methodological)

Это первый проход — keyword baseline. Низкая уверенность? → сразу в очередь
ручной валидации. Финальная разметка должна быть LLM-кодирование + ручная
сверка спорных (по решению автора). Этот скрипт даёт BASELINE и список
заголовков, требующих LLM/ручной обработки.

Выводы:
  analytics_output/theme_codes_baseline.csv — все 895 заголовков с метками + confidence
  analytics_output/theme_review_queue.csv   — спорные (confidence<0.5) → ручная сверка
"""

import sys
import csv
import re
import sqlite3
from collections import Counter

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

DB = "conferences.db"
OUT_DIR = "analytics_output"


L1_RULES = {
    "linguistics": [
        r"грамматик", r"\bПанин", r"этимолог", r"лексик", r"синтакс",
        r"морфолог", r"\bязык", r"диалект", r"бенгал", r"\bхинди\b",
        r"санскрит(?!.*текст)", r"императив", r"имперфект", r"кодировк",
    ],
    "philosophy": [
        r"философ", r"эпистемолог", r"мадхьямак", r"йогачар", r"адвайта",
        r"веданта", r"санкхь", r"вайшешик", r"\bньяя", r"даршан",
        r"теория познани", r"шива(?:изм|итск)", r"пратьякша", r"прамана",
        r"монизм", r"нигилизм", r"бхакти", r"сотериолог",
    ],
    "literature": [
        r"эпос", r"\bМБХ\b", r"\bРамаян", r"кавь", r"махакавь", r"Панчатантр",
        r"роман", r"повес", r"проз", r"поэзи", r"поэтик", r"Тагор",
        r"Шанкхадхар", r"Латакамел", r"\bРушди", r"фольклор",
        r"\bЙога-?ва?сишт", r"\bЛил", r"клише", r"сюжет(?!.*ступ)",
        r"тема", r"^образ", r"мотив", r"литератур",
    ],
    "history": [
        r"истори", r"архив", r"архео", r"эпиграф", r"нумизмат",
        r"источник", r"датировк", r"путеш", r"Мерварт", r"Сталь-Гольштейн",
        r"Bibliotheca Buddhica", r"коллекци", r"библиотек",
        r"\bкупц", r"диаспор", r"Голод в Бенгал", r"диафильм",
    ],
    "religion": [
        r"буддизм", r"будди[йс]", r"ритуал", r"паломнич", r"индуи",
        r"храм", r"бог", r"божеств", r"ведий", r"Веда", r"упанишад",
        r"Праваргь", r"\bПатм", r"Дипанкар", r"Гаруд", r"Шакти",
        r"\bТримурти", r"Самьяк", r"мадига", r"агхори", r"сикх",
        r"погреб", r"мифолог", r"\bмиф\b", r"архетип", r"сотериолог",
        r"Брахмалок", r"\bдхарм", r"шиваит", r"тантр", r"бхакти",
    ],
    "tibetology": [
        r"тибет", r"Тибет", r"Камалашил", r"хэшан", r"Махаян",
        r"Дипанкар", r"Абхисамаяаланкар",
    ],
    "ethnography": [
        r"антрополог", r"этнограф", r"племен", r"Адиваси", r"тода",
        r"мадига", r"межкультурн", r"проектная деятельност",
    ],
    "art_archaeology": [
        r"архитектур", r"шикхар", r"Ступ(?!.*пракрит)", r"иконограф",
        r"художни", r"скульпт", r"живопис", r"\bхудожник", r"\bтело",
        r"визуальност", r"перформанс", r"\bЭрмитаж", r"памятник",
    ],
    "pedagogy_applied": [
        r"преподаван", r"средн[её]й школ", r"урок[еа]х", r"методик",
        r"переводч", r"практик(?:а|и) преподав",
    ],
}

L2_RULES = {
    "vedic": [r"ведий", r"\bВед[аы]\b", r"упанишад", r"Праваргь"],
    "classical": [
        r"Панин", r"Калидас", r"Махабхарат", r"\bМБХ\b", r"эпос",
        r"\bРамаян", r"санкхь", r"мадхьямак", r"йогачар", r"Шанкар",
        r"Бхававивек", r"Абхинавагупт", r"кавь", r"махакавь",
    ],
    "medieval": [
        r"средневеков", r"Рамананд", r"Тулсидас", r"Каби[рп]", r"бхакти",
        r"тантр", r"Шанкхадхар", r"Гулабра[ое]", r"Джив[аы] Госвами",
    ],
    "colonial": [
        r"колониал", r"Сталь-Гольштейн", r"Мерварт", r"Bibliotheca",
        r"Петров.*1814", r"Новикова", r"XVIII", r"XIX", r"послевоен",
    ],
    "modern": [
        r"\bРушди", r"Тагор", r"совреме", r"диаспор", r"Рамбхадрачарь",
        r"\bхинди", r"\bбенгал", r"2026", r"художниц", r"Парс",
    ],
}

L3_RULES = {
    "text": [
        r"текст", r"трактат", r"коммент", r"перевод", r"рукопис",
        r"источник.{0,10}(?:ист|тек|пись)", r"\bMБХ\b", r"\bтрактат",
    ],
    "fieldwork": [
        r"полев", r"антрополог", r"этнограф", r"межкультурн",
        r"проектная", r"перформанс", r"визуальност", r"практик",
    ],
    "archive": [
        r"архив", r"библиотек", r"коллекци", r"\bЭрмитаж", r"МАЭ",
        r"Bibliotheca", r"диафильм", r"рукопис",
    ],
    "artefact": [
        r"архитектур", r"шикхар", r"Ступ", r"памятник", r"монет",
        r"скульпт", r"иконограф", r"храм", r"релье[фб]", r"диафильм",
    ],
}

L4_RULES = {
    "applied": [
        r"преподаван", r"средн[её]й школ", r"урок[еа]х", r"методик",
        r"проектная деятельност", r"межкультурн", r"практик(?:а|и) преподав",
    ],
    "methodological": [
        r"библиограф", r"источниковед", r"методолог", r"подход",
        r"компаратив(?:ный|ист)", r"\bхроник", r"\bобзор", r"перспектив",
        r"в свете", r"в оптике", r"к проблеме",
    ],
    # fundamental is the default
}


def _match_rule_set(title, rules):
    """Return (best_category, n_hits_per_cat). Highest hits wins."""
    if not title:
        return (None, {})
    scores = {}
    for cat, patterns in rules.items():
        hits = sum(1 for p in patterns if re.search(p, title, re.IGNORECASE))
        if hits:
            scores[cat] = hits
    if not scores:
        return (None, scores)
    best = max(scores.items(), key=lambda x: x[1])
    return (best[0], scores)


def code_title(title):
    l1, l1_scores = _match_rule_set(title, L1_RULES)
    l2, l2_scores = _match_rule_set(title, L2_RULES)
    l3, l3_scores = _match_rule_set(title, L3_RULES)
    l4, l4_scores = _match_rule_set(title, L4_RULES)
    if l4 is None:
        l4 = "fundamental"

    # Confidence: based on number of rules and clearness of winner
    def conf(scores, best):
        if not scores or best is None:
            return 0.0
        total = sum(scores.values())
        winner_hits = scores[best]
        margin = winner_hits / total
        # Strong if there's at least 2 hits and >=70% margin
        strong = winner_hits >= 2 and margin >= 0.7
        return round(min(1.0, 0.4 + 0.3 * winner_hits + 0.3 * margin), 2)

    return {
        "l1": l1,
        "l1_conf": conf(l1_scores, l1),
        "l2": l2,
        "l2_conf": conf(l2_scores, l2),
        "l3": l3,
        "l3_conf": conf(l3_scores, l3),
        "l4": l4,
        "l4_conf": conf(l4_scores, l4),
    }


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT pres.presentation_id, pres.title, e.event_id, e.year, es.series_name_en
          FROM presentation pres
          JOIN session s ON s.session_id = pres.session_id
          JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
          JOIN event_day ed ON ed.event_day_id = edv.event_day_id
          JOIN event e ON e.event_id = ed.event_id
          JOIN event_series es ON es.event_series_id = e.event_series_id
    """)
    rows = cur.fetchall()

    out_all = []
    review_queue = []
    for pres_id, title, ev_id, year, series in rows:
        codes = code_title(title or "")
        out_all.append({
            "presentation_id": pres_id,
            "event_id": ev_id,
            "year": year,
            "series": series,
            "title": title,
            **codes,
        })
        min_conf = min(codes["l1_conf"], codes["l2_conf"], codes["l3_conf"])
        if min_conf < 0.5 or codes["l1"] is None or codes["l3"] is None:
            review_queue.append({
                "presentation_id": pres_id,
                "year": year,
                "series": series,
                "title": title,
                "l1_baseline": codes["l1"],
                "l1_conf": codes["l1_conf"],
                "l2_baseline": codes["l2"],
                "l3_baseline": codes["l3"],
                "l4_baseline": codes["l4"],
            })

    fields_all = list(out_all[0].keys()) if out_all else []
    with open(f"{OUT_DIR}/theme_codes_baseline.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_all)
        w.writeheader()
        w.writerows(out_all)
    if review_queue:
        with open(f"{OUT_DIR}/theme_review_queue.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(review_queue[0].keys()))
            w.writeheader()
            w.writerows(review_queue)

    # Summary stats
    l1_counter = Counter(r["l1"] for r in out_all)
    print(f"\nИтого размечено: {len(out_all)} докладов")
    print(f"В очереди на ручную/LLM-сверку: {len(review_queue)}")
    print(f"\nL1 (дисциплина) распределение:")
    for cat, n in l1_counter.most_common():
        print(f"  {cat or 'unspec':25s}: {n:4d} ({100*n/len(out_all):4.1f}%)")

    # By series
    print(f"\nL1 распределение по сериям:")
    by_series = defaultdict(Counter)
    for r in out_all:
        by_series[r["series"]][r["l1"]] += 1
    for series, ctr in sorted(by_series.items()):
        total = sum(ctr.values())
        print(f"\n  -- {series} (n={total}) --")
        for cat, n in ctr.most_common():
            print(f"    {cat or 'unspec':25s}: {n:4d} ({100*n/total:4.1f}%)")

    conn.close()


if __name__ == "__main__":
    from collections import defaultdict
    main()
