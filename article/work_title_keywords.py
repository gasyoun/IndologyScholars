"""Keyword analysis for presentation titles.

This is a lexical layer next to the hand/LLM-assisted thematic rubrication.
It asks a different question: not "which category does this title belong to?",
but "which terms, objects, text types, places, and problem words structure the
language of the programmes?".

Outputs:
  article/hypothesis_output/title_keyword_terms.csv
  article/hypothesis_output/title_keyword_bigrams.csv
  article/hypothesis_output/title_keyword_contrasts.csv
  article/hypothesis_output/title_keyword_period_trends.csv
  article/hypothesis_output/title_keyword_period_trends_by_series.csv
  article/hypothesis_output/title_keyword_ethnography_diagnostics.csv
  article/hypothesis_output/title_keyword_linguistics_subfields.csv
  article/hypothesis_output/title_keyword_linguistics_subfield_titles.csv
  article/hypothesis_output/title_keyword_microseries.csv
  article/hypothesis_output/title_keyword_microseries_titles.csv
  article/hypothesis_output/title_keyword_theme_terms.csv
  article/hypothesis_output/title_keyword_nodes.csv
  article/hypothesis_output/title_keyword_cooccurrence_edges.csv
  article/hypothesis_output/title_keyword_report.md
  analytics_output/presentation_tags.csv
  article/figures/title_keyword_contrast.svg
  article/figures/title_keyword_period_trend.svg
"""
from __future__ import annotations

import csv
import datetime as dt
import itertools
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from html import escape
from pathlib import Path

import pymorphy3


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DB = ROOT / "conferences.db"
ANALYTICS = ROOT / "analytics_output"
OUT = ROOT / "article" / "hypothesis_output"
FIG = ROOT / "article" / "figures"

from title_normalization import canonical_title


STOP_WORDS = {
    "а",
    "без",
    "бы",
    "быть",
    "был",
    "была",
    "были",
    "в",
    "во",
    "вопрос",
    "вопросы",
    "год",
    "гг",
    "для",
    "до",
    "его",
    "ее",
    "еще",
    "же",
    "за",
    "из",
    "и",
    "или",
    "их",
    "как",
    "к",
    "ли",
    "на",
    "над",
    "не",
    "некоторый",
    "некоторые",
    "но",
    "о",
    "об",
    "один",
    "она",
    "они",
    "он",
    "опыт",
    "от",
    "по",
    "под",
    "при",
    "проблема",
    "проблемы",
    "раз",
    "роль",
    "с",
    "со",
    "тема",
    "темы",
    "то",
    "у",
    "это",
    "этот",
    "являться",
    "шри",
    "онлайн",
    "a",
    "an",
    "and",
    "as",
    "at",
    "between",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

GENERIC_ACADEMIC = {
    "анализ",
    "аспект",
    "аспекты",
    "введение",
    "вклад",
    "возможность",
    "значение",
    "изучение",
    "интерпретация",
    "исследование",
    "материал",
    "материалы",
    "место",
    "наблюдение",
    "особенность",
    "особенности",
    "подход",
    "попытка",
    "пример",
    "рассмотрение",
    "связь",
    "сравнение",
    "структура",
    "уточнение",
    "феномен",
}

CANONICAL = {
    "бхакть": "бхакти",
    "бхагавадгит": "бхагавадгита",
    "вастувидье": "вастувидья",
    "ведд": "ведды",
    "вишн": "вишну",
    "дравидийский": "дравидология",
    "общедравидийский": "дравидология",
    "парибхаш": "парибхаша",
    "парибхаши": "парибхаша",
    "старотамильский": "тамильский",
    "южноиндийский": "южная_индия",
    "бенгали": "бенгальский",
    "лалитавистар": "лалитавистара",
    "паниня": "панини",
    "пасть": "пали",
    "пуран": "пураны",
    "пурана": "пураны",
    "рамаян": "рамаяна",
    "танк": "танка",
    "шив": "шива",
    "абхинавагупт": "абхинавагупта",
    "тагора": "тагор",
    "урд": "урду",
    "санскритский": "санскрит",
    "санскрит": "санскрит",
    "палийский": "пали",
    "буддийский": "буддизм",
    "буддистский": "буддизм",
    "индийский": "индия",
    "древнеиндийский": "древнеиндийский",
    "тибетский": "тибет",
    "тамильский": "тамильский",
    "ведийский": "ведийский",
    "средневековый": "средневековый",
    "классический": "классический",
    "колониальный": "колониальный",
    "современный": "современный",
    "религиозный": "религия",
    "религиоведческий": "религия",
    "философский": "философия",
    "литературный": "литература",
    "лингвистический": "лингвистика",
    "исторический": "история",
}

STRUCTURAL_TERMS = {
    "ив_ран",
    "ивр_ран",
    "кабинет",
    "коллекция",
    "маэ_ран",
    "москва",
    "санкт-петербург",
    "собрание",
}

PROTECTED_PHRASES = [
    (re.compile(r"\bю\.\s*н\.\s*рерих[а-яё]*\b", re.IGNORECASE), "юрий_рерих"),
    (re.compile(r"\bюрий\s+николаевич\s+рерих[а-яё]*\b", re.IGNORECASE), "юрий_рерих"),
    (re.compile(r"\bюрий\s+рерих[а-яё]*\b", re.IGNORECASE), "юрий_рерих"),
    (re.compile(r"\bюжн[а-яё]*\s+инд[а-яё]*\b", re.IGNORECASE), "южная_индия"),
    (re.compile(r"\bмир[аы]\s+баи\b", re.IGNORECASE), "мира_баи"),
    (re.compile(r"\bивр\s+ран\b", re.IGNORECASE), "ивр_ран"),
    (re.compile(r"\bив\s+ран\b", re.IGNORECASE), "ив_ран"),
    (re.compile(r"\bмаэ\s+ран\b", re.IGNORECASE), "маэ_ран"),
    (re.compile(r"\bинститут[а-яё]*\s+востоковеден[а-яё]*\s+ран\b", re.IGNORECASE), "институт_востоковедения_ран"),
]

DISPLAY_TERMS = {
    "абхинавагупта": "Абхинавагупта",
    "артхавинишчай-сутра": "Артхавинишчая-сутра",
    "атхарвавед": "Атхарваведа",
    "азия": "Азия",
    "бенгалия": "Бенгалия",
    "бхагавадгита": "Бхагавадгита",
    "будда": "Будда",
    "васубандха": "Васубандху",
    "вивекананда": "Вивекананда",
    "вишну": "Вишну",
    "ганди": "Ганди",
    "гуджарат": "Гуджарат",
    "девибхагават": "Девибхагавата",
    "иванова": "Иванов",
    "ив_ран": "ИВ РАН",
    "ивр_ран": "ИВР РАН",
    "индия": "Индия",
    "институт_востоковедения_ран": "Институт востоковедения РАН",
    "калькутта": "Калькутта",
    "катманду": "Катманду",
    "карнатака": "Карнатака",
    "кашмир": "Кашмир",
    "керала": "Керала",
    "китай": "Китай",
    "кришна": "Кришна",
    "кумарила": "Кумарила",
    "лалитавистара": "Лалитавистара",
    "ланка": "Шри-Ланка",
    "маэ_ран": "МАЭ РАН",
    "минаев": "Минаев",
    "мира_баи": "Мира Баи",
    "монголия": "Монголия",
    "москва": "Москва",
    "непал": "Непал",
    "одисса": "Орисса",
    "панини": "Панини",
    "парибхаша": "парибхаша",
    "поталака": "Поталака",
    "рамагит": "Рамагита",
    "рамакришна": "Рамакришна",
    "раманудж": "Рамануджа",
    "рамаяна": "Рамаяна",
    "ран": "РАН",
    "рабиндранат": "Рабиндранат",
    "рерих": "Рерих",
    "ригведа": "Ригведа",
    "санкт-петербург": "Санкт-Петербург",
    "тагор": "Тагор",
    "тамилнад": "Тамилнад",
    "тибет": "Тибет",
    "химачал-прадеш": "Химачал-Прадеш",
    "шакьямуни": "Шакьямуни",
    "шамбала": "Шамбала",
    "шанкара": "Шанкара",
    "шива": "Шива",
    "юрий": "Юрий",
    "юрий_рерих": "Юрий Рерих",
    "южная_индия": "Южная Индия",
}

DISPLAY_BIGRAMS = {
    "буддизм индия": "буддизм Индии",
    "буддизм ранний": "ранний буддизм",
    "буддизм текст": "буддийские тексты",
    "древний индия": "Древняя Индия",
    "драма санскрит": "санскритская драма",
    "индия санскрит": "Индия и санскрит",
    "индия средневековый": "средневековая Индия",
    "индия текст": "индийские тексты",
    "индия история": "история Индии",
    "индия источник": "источники по Индии",
    "индия культура": "культура Индии",
    "индия современный": "современная Индия",
    "индия традиция": "традиция Индии",
    "индия традиционный": "традиционная Индия",
    "индия философия": "философия Индии",
    "история индия": "история Индии",
    "кабинет рерих": "Кабинет Рериха",
    "кабинет юрий_рерих": "Кабинет Юрия Рериха",
    "канон пали": "палийский канон",
    "москва санкт-петербург": "Москва и Санкт-Петербург",
    "пали канон": "палийский канон",
    "рабиндранат тагор": "Рабиндранат Тагор",
    "санскрит драма": "санскритская драма",
    "поэзия тамильский": "тамильская поэзия",
    "тамильский поэзия": "тамильская поэзия",
    "текст традиционный": "традиционный текст",
    "традиционный индия": "традиционная Индия",
    "южная_индия индия": "Южная Индия",
}

LINGUISTIC_APPROACHES = {
    "language_system": "языковедческий анализ",
    "text_philology": "филология текста",
}

LANGUAGE_SYSTEM_MARKERS = {
    "алфавит",
    "глагол",
    "грамматика",
    "диалект",
    "звук",
    "залог",
    "знак",
    "корень",
    "корпус",
    "лексика",
    "лексикализация",
    "лексикография",
    "морфология",
    "панини",
    "парибхаша",
    "письменность",
    "праформа",
    "родство",
    "семантика",
    "синтаксис",
    "словарь",
    "слово",
    "словообразование",
    "термин",
    "терминология",
    "топоним",
    "транскрипция",
    "фонема",
    "фонетический",
    "форма",
    "этимология",
    "язык",
}

TEXT_PHILOLOGY_MARKERS = {
    "библия",
    "датировка",
    "комментарий",
    "манускрипт",
    "надпись",
    "перевод",
    "прочтение",
    "реконструкция",
    "рукопись",
    "сутра",
    "текст",
    "фрагмент",
    "эпиграфический",
}

MINI_SERIES = [
    {
        "code": "tibetology_himalaya",
        "label": "Тибетология / гималайский контур",
        "markers": {
            "амдый",
            "балтистан",
            "гималайский",
            "ладакх",
            "лхасскома",
            "танка",
            "тханка",
            "тибет",
            "тибетско-русско-английский",
            "шангшунг",
        },
        "patterns": [r"тибет", r"тханк", r"\bтанк[аи]?\b", r"амдо", r"ладакх", r"балтистан", r"шангшунг"],
    },
    {
        "code": "dravidology_south_india",
        "label": "Дравидология / южноиндийский контур",
        "markers": {
            "дравидология",
            "карнатака",
            "керала",
            "намбудири",
            "тамильский",
            "телугу",
            "южная_индия",
        },
        "patterns": [r"дравид", r"тамил", r"телугу", r"керал", r"карнатак", r"тулунаду", r"намбудири", r"южн[а-я]+ инд"],
    },
    {
        "code": "vedic_studies",
        "label": "Ведийские исследования",
        "markers": {"атхарвавед", "брахманический", "ведийский", "ригведа", "праваргья"},
        "patterns": [r"ведийск", r"ригвед", r"атхарвавед", r"праварг", r"agny", r"\bвед[аы]\b"],
    },
    {
        "code": "sanskrit_grammar_panini",
        "label": "Санскритская грамматика / Панини",
        "markers": {
            "варна",
            "грамматика",
            "лексикография",
            "панини",
            "парибхаша",
            "синтаксис",
            "спхота",
        },
        "patterns": [r"панин", r"граммат", r"парибхаш", r"лексикограф", r"спхот", r"санскрит.*(граммат|лексик|синтакс|глагол|имперфект)"],
    },
    {
        "code": "pali_early_buddhism",
        "label": "Пали и ранний буддизм",
        "markers": {"джатака", "канон", "пали", "сатипаттхан", "сутта"},
        "patterns": [r"\bпали\b", r"\bпал\.", r"pali", r"sutta", r"сатипат", r"ранн[а-я]+ будд"],
    },
    {
        "code": "bengal_bhakti_modernity",
        "label": "Бенгалия, бхакти и современность",
        "markers": {"баул", "бенгалия", "бенгальский", "вайшнавизм", "рамакришна", "тагор", "чайтанья"},
        "patterns": [r"бенгал", r"баул", r"чайтан", r"рамакришн", r"тагор", r"вайшнав"],
    },
    {
        "code": "hindi_urdu_new_indo_aryan",
        "label": "Новые индоарийские языки: хинди, урду, бенгали",
        "markers": {"куллуи", "урду", "хинди"},
        "patterns": [r"хинди", r"урду", r"куллуи", r"бенгали\b"],
    },
    {
        "code": "nepal_newar_kathmandu",
        "label": "Непал и неварский контур",
        "markers": {"дхара", "катманду", "маччхендранатх", "неварский", "непал", "непальский", "хити"},
        "patterns": [r"непал", r"невар", r"катманду", r"маччхендранатх", r"\bхити\b", r"\bдхара\b"],
    },
    {
        "code": "museum_collections",
        "label": "Музейные собрания и коллекции",
        "markers": {"ив_ран", "ивр_ран", "кабинет", "коллекция", "маэ_ран", "рукопись", "собрание", "танка"},
        "patterns": [r"собран", r"коллекц", r"маэ", r"ивр\s+ран", r"ив\s+ран", r"кабинет", r"рукопис"],
    },
    {
        "code": "roerich_studies",
        "label": "Рериховедение и Кабинет Ю. Н. Рериха",
        "markers": {"кабинет", "рерих", "юрий_рерих"},
        "patterns": [r"рерих", r"кабинет[^.]{0,70}рерих"],
    },
    {
        "code": "china_mongolia_inner_asia",
        "label": "Китай, Монголия и Центральная Азия",
        "markers": {"китай", "китайский", "монгольский", "ойрат", "шангшунг"},
        "patterns": [r"китай", r"монгол", r"ойрат", r"центральн[а-я]+ ази", r"шангшунг", r"шанси"],
    },
    {
        "code": "ethnography_performance",
        "label": "Этнография, ритуал и перформанс",
        "markers": {
            "адиваси",
            "баул",
            "ведды",
            "драма",
            "каста",
            "обряд",
            "племя",
            "ритуал",
            "танец",
            "театр",
            "фольклор",
        },
        "patterns": [r"этнограф", r"ритуал", r"обряд", r"каст", r"плем", r"адиваси", r"ведд", r"танец", r"театр", r"фольклор", r"перформанс", r"чхау"],
    },
]

SERIES_RU = {
    "Zograf Readings": "Зограф",
    "Roerich Readings": "Рерих",
}

THEME_LABELS = {
    "art_archaeology": "искусство и археология",
    "ethnography": "этнография",
    "history": "история",
    "linguistics": "лингвистика",
    "literature": "литература",
    "other": "прочее",
    "pedagogy_applied": "прикладные сюжеты",
    "philosophy": "философия",
    "religion": "религия",
    "tibetology": "тибетология",
}

PERIODS = [
    ("2004-2010", 2004, 2010),
    ("2011-2017", 2011, 2017),
    ("2018-2022", 2018, 2022),
    ("2023-2026", 2023, 2026),
]

TOKEN_RE = re.compile(r"[а-яёa-z][а-яёa-z_-]{2,}", re.IGNORECASE)
MORPH = pymorphy3.MorphAnalyzer()


def period_bucket(year: int) -> str:
    for label, start, end in PERIODS:
        if start <= year <= end:
            return label
    return "other"


def normalize_title_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower().replace("ё", "е")).strip()


def protect_phrases(title: str) -> str:
    protected = title or ""
    for pattern, replacement in PROTECTED_PHRASES:
        protected = pattern.sub(f" {replacement} ", protected)
    return protected


def display_term(term: object) -> str:
    value = str(term)
    return DISPLAY_TERMS.get(value, value)


def display_bigram(bigram: object) -> str:
    raw = str(bigram)
    return DISPLAY_BIGRAMS.get(raw, " ".join(display_term(part) for part in raw.split()))


@lru_cache(maxsize=20000)
def normalize_token(token: str) -> str:
    token = token.lower().replace("ё", "е").strip("-")
    if not token:
        return ""
    if "_" in token:
        return token
    if re.fullmatch(r"[a-z][a-z-]+", token):
        return token
    parsed = MORPH.parse(token)[0]
    lemma = parsed.normal_form.replace("ё", "е")
    return CANONICAL.get(lemma, lemma)


def tokenize(title: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(protect_phrases(title or "")):
        token = normalize_token(raw)
        if not token or len(token) < 3:
            continue
        if re.fullmatch(r"[ivxlcdm]+", token):
            continue
        if re.search(r"(ович|евич|овна|евна|ична)$", token):
            continue
        if token in STOP_WORDS or token in GENERIC_ACADEMIC:
            continue
        tokens.append(token)
    return tokens


def read_theme_rows() -> tuple[dict[str, dict[str, str]], dict[tuple[str, str, str], dict[str, str]]]:
    path = ANALYTICS / "theme_codes_final.csv"
    if not path.exists():
        return {}, {}
    with path.open("r", encoding="utf-8", newline="") as f:
        by_id = {}
        by_title = {}
        for row in csv.DictReader(f):
            by_id[row["presentation_id"]] = row
            key = (str(row.get("year", "")), row.get("series", ""), normalize_title_key(row.get("title", "")))
            by_title.setdefault(key, row)
        return by_id, by_title


def load_title_rows() -> list[dict[str, object]]:
    con = sqlite3.connect(DB)
    theme_by_id, theme_by_title = read_theme_rows()
    rows = []
    for presentation_id, title, year, series, calendar_date, day_label in con.execute(
        """
        select pr.presentation_id, pr.title, e.year, es.series_name_en, ed.calendar_date, ed.day_label_raw
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        order by e.year, es.series_name_en, pr.presentation_id
        """
    ):
        raw_title = title or ""
        title = canonical_title(presentation_id, raw_title)
        tokens = tokenize(title)
        theme_key = (str(year), series, normalize_title_key(raw_title))
        theme_row = theme_by_id.get(presentation_id) or theme_by_title.get(theme_key, {})
        weekday = ""
        if calendar_date:
            weekday = dt.date.fromisoformat(str(calendar_date)).strftime("%A")
        rows.append(
            {
                "presentation_id": presentation_id,
                "title": title or "",
                "year": int(year),
                "period": period_bucket(int(year)),
                "series": series,
                "calendar_date": calendar_date or "",
                "weekday": weekday,
                "day_label": day_label or "",
                "tokens": tokens,
                "unique_tokens": sorted(set(tokens)),
                "bigrams": [f"{a} {b}" for a, b in zip(tokens, tokens[1:]) if a != b],
                "l1": theme_row.get("l1", ""),
                "l2": theme_row.get("l2", ""),
                "theme_match": bool(theme_row),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def term_frequencies(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    dfs: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    docs: Counter[str] = Counter()
    for row in rows:
        series = str(row["series"])
        totals[series] += len(row["tokens"])
        docs[series] += 1
        counts[series].update(row["tokens"])
        dfs[series].update(row["unique_tokens"])
        counts["ALL"].update(row["tokens"])
        dfs["ALL"].update(row["unique_tokens"])
        totals["ALL"] += len(row["tokens"])
        docs["ALL"] += 1

    out = []
    for group in sorted(counts):
        for term, count in counts[group].most_common():
            df = dfs[group][term]
            out.append(
                {
                    "group": group,
                    "term": term,
                    "count": count,
                    "document_frequency": df,
                    "title_share_pct": round(100 * df / docs[group], 2) if docs[group] else 0.0,
                    "per_1000_tokens": round(1000 * count / totals[group], 2) if totals[group] else 0.0,
                }
            )
    return out


def bigram_frequencies(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    docs: Counter[str] = Counter()
    for row in rows:
        series = str(row["series"])
        counts[series].update(row["bigrams"])
        counts["ALL"].update(row["bigrams"])
        docs[series] += 1
        docs["ALL"] += 1
    out = []
    for group in sorted(counts):
        for bigram, count in counts[group].most_common():
            if count < 2:
                continue
            out.append(
                {
                    "group": group,
                    "bigram": bigram,
                    "display_bigram": display_bigram(bigram),
                    "count": count,
                    "per_100_titles": round(100 * count / docs[group], 2) if docs[group] else 0.0,
                }
            )
    return out


def contrast_terms(rows: list[dict[str, object]], min_df: int = 3, alpha: float = 0.5) -> list[dict[str, object]]:
    df_by_series = {"Zograf Readings": Counter(), "Roerich Readings": Counter()}
    docs_by_series = Counter()
    for row in rows:
        series = str(row["series"])
        if series not in df_by_series:
            continue
        docs_by_series[series] += 1
        df_by_series[series].update(row["unique_tokens"])

    terms = sorted(set(df_by_series["Zograf Readings"]) | set(df_by_series["Roerich Readings"]))
    out = []
    n_z = docs_by_series["Zograf Readings"]
    n_r = docs_by_series["Roerich Readings"]
    for term in terms:
        z = df_by_series["Zograf Readings"][term]
        r = df_by_series["Roerich Readings"][term]
        if z + r < min_df:
            continue
        logit_z = math.log((z + alpha) / (n_z - z + alpha))
        logit_r = math.log((r + alpha) / (n_r - r + alpha))
        se = math.sqrt(1 / (z + alpha) + 1 / (r + alpha))
        z_score = (logit_z - logit_r) / se if se else 0.0
        out.append(
            {
                "term": term,
                "zograf_df": z,
                "roerich_df": r,
                "zograf_title_share_pct": round(100 * z / n_z, 2) if n_z else 0.0,
                "roerich_title_share_pct": round(100 * r / n_r, 2) if n_r else 0.0,
                "log_odds_zograf_minus_roerich": round(logit_z - logit_r, 4),
                "z_score": round(z_score, 3),
                "distinctive_for": "Zograf" if z_score > 0 else "Roerich",
            }
        )
    return sorted(out, key=lambda row: abs(float(row["z_score"])), reverse=True)


def period_trends(rows: list[dict[str, object]], min_df: int = 3, alpha: float = 0.5) -> list[dict[str, object]]:
    early = {"2004-2010", "2011-2017"}
    late = {"2018-2022", "2023-2026"}
    df = {"early": Counter(), "late": Counter()}
    docs = Counter()
    for row in rows:
        bucket = "early" if row["period"] in early else "late" if row["period"] in late else ""
        if not bucket:
            continue
        docs[bucket] += 1
        df[bucket].update(row["unique_tokens"])
    out = []
    for term in sorted(set(df["early"]) | set(df["late"])):
        e = df["early"][term]
        l = df["late"][term]
        if e + l < min_df:
            continue
        logit_e = math.log((e + alpha) / (docs["early"] - e + alpha))
        logit_l = math.log((l + alpha) / (docs["late"] - l + alpha))
        se = math.sqrt(1 / (e + alpha) + 1 / (l + alpha))
        z_score = (logit_l - logit_e) / se if se else 0.0
        out.append(
            {
                "term": term,
                "early_df": e,
                "late_df": l,
                "early_title_share_pct": round(100 * e / docs["early"], 2) if docs["early"] else 0.0,
                "late_title_share_pct": round(100 * l / docs["late"], 2) if docs["late"] else 0.0,
                "log_odds_late_minus_early": round(logit_l - logit_e, 4),
                "z_score": round(z_score, 3),
                "trend": "late" if z_score > 0 else "early",
            }
        )
    return sorted(out, key=lambda row: abs(float(row["z_score"])), reverse=True)


def period_trends_by_series(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for series in SERIES_RU:
        subset = [row for row in rows if row["series"] == series]
        for trend_row in period_trends(subset):
            out.append({"series": series, **trend_row})
    return out


def ethnography_diagnostics(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    scopes = {
        "strict_l1_all": [row for row in rows if row["l1"] == "ethnography"],
        "zograf_friday_all": [
            row for row in rows if row["series"] == "Zograf Readings" and row.get("weekday") == "Friday"
        ],
        "zograf_friday_strict_ethnography": [
            row
            for row in rows
            if row["series"] == "Zograf Readings" and row.get("weekday") == "Friday" and row["l1"] == "ethnography"
        ],
    }
    for scope, scope_rows in scopes.items():
        diagnostics.append(
            {
                "scope": scope,
                "l1": "ALL",
                "count": len(scope_rows),
                "share_pct": 100.0,
            }
        )
        l1_counts = Counter(str(row["l1"] or "uncoded") for row in scope_rows)
        for l1, count in l1_counts.most_common():
            diagnostics.append(
                {
                    "scope": scope,
                    "l1": l1,
                    "count": count,
                    "share_pct": round(100 * count / len(scope_rows), 2) if scope_rows else 0.0,
                }
            )
    return diagnostics


def structural_contexts(rows: list[dict[str, object]]) -> dict[str, str]:
    variant_patterns = [
        ("ИВР РАН", re.compile(r"\bивр\s+ран\b|индийск[а-яё]+\s+фонд[а-яё]+\s+ивр\s+ран", re.IGNORECASE)),
        ("ИВ / Институт востоковедения РАН", re.compile(r"\bив\s+ран\b|институт[а-яё]*\s+востоковеден[а-яё]*\s+ран", re.IGNORECASE)),
        ("МАЭ РАН", re.compile(r"\bмаэ\s+ран\b", re.IGNORECASE)),
        ("Кабинет Ю. Н. Рериха", re.compile(r"кабинет[^.]{0,70}рерих|рерих[^.]{0,70}кабинет", re.IGNORECASE)),
        ("И. П. Минаева", re.compile(r"минаев", re.IGNORECASE)),
        ("А. М. и Л. А. Мервартов", re.compile(r"мерварт", re.IGNORECASE)),
        ("Кхубрама Кхушдиля", re.compile(r"кхубрам|кхушдил", re.IGNORECASE)),
        ("тамильские рукописи", re.compile(r"тамильск[а-яё]+\s+рукопис", re.IGNORECASE)),
        ("тханки / танки", re.compile(r"тханк|танк", re.IGNORECASE)),
    ]
    contexts: dict[str, str] = {}
    for term, matcher in {
        "собрание": re.compile(r"собран", re.IGNORECASE),
        "коллекция": re.compile(r"коллекц", re.IGNORECASE),
    }.items():
        counts: Counter[str] = Counter()
        for row in rows:
            title = normalize_title_key(str(row["title"]))
            if not matcher.search(title):
                continue
            matched = False
            for label, pattern in variant_patterns:
                if pattern.search(title):
                    counts[label] += 1
                    matched = True
            if not matched:
                counts["без уточнения в заголовке"] += 1
        missing = counts.pop("без уточнения в заголовке", 0)
        items = [f"{label}: {count}" for label, count in counts.most_common(6)]
        if missing:
            items.append(f"без уточнения в заголовке: {missing}")
        contexts[term] = ", ".join(items)
    return contexts


def row_matches_spec(row: dict[str, object], spec: dict[str, object]) -> tuple[bool, list[str]]:
    tokens = set(row["unique_tokens"])
    title_key = normalize_title_key(str(row["title"]))
    matched = sorted(tokens & set(spec.get("markers", set())))
    for pattern in spec.get("patterns", []):
        if re.search(str(pattern), title_key, flags=re.IGNORECASE):
            matched.append(f"re:{pattern}")
    return bool(matched), matched


def linguistics_subfields(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    classified: list[dict[str, object]] = []
    for row in rows:
        if row["l1"] != "linguistics":
            continue
        tokens = set(row["unique_tokens"])
        title_key = normalize_title_key(str(row["title"]))
        language_score = len(tokens & LANGUAGE_SYSTEM_MARKERS)
        philology_score = len(tokens & TEXT_PHILOLOGY_MARKERS)
        if re.search(r"перевод|комментар|текст|надпис|рукопис|фрагмент|эпиграф|реконструкц|прочтен", title_key):
            philology_score += 2
        if re.search(r"граммат|синтакс|семантик|этимолог|диалект|лексик|фонем|залог|словообраз", title_key):
            language_score += 2
        approach = "text_philology" if philology_score > language_score else "language_system"
        classified.append({**row, "approach": approach, "language_score": language_score, "philology_score": philology_score})

    out: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    total = len(classified)
    for approach, label in LINGUISTIC_APPROACHES.items():
        subset = [row for row in classified if row["approach"] == approach]
        term_counts = Counter()
        for row in subset:
            term_counts.update(row["unique_tokens"])
            detail_rows.append(
                {
                    "approach": approach,
                    "label": label,
                    "presentation_id": row["presentation_id"],
                    "year": row["year"],
                    "series": row["series"],
                    "l1": row["l1"],
                    "l2": row["l2"],
                    "title": row["title"],
                    "language_score": row["language_score"],
                    "philology_score": row["philology_score"],
                }
            )
        examples = "; ".join(str(row["title"]) for row in subset[:3])
        out.append(
            {
                "approach": approach,
                "label": label,
                "count": len(subset),
                "share_pct": round(100 * len(subset) / total, 2) if total else 0.0,
                "zograf_count": sum(1 for row in subset if row["series"] == "Zograf Readings"),
                "roerich_count": sum(1 for row in subset if row["series"] == "Roerich Readings"),
                "top_terms": ", ".join(display_term(term) for term, _ in term_counts.most_common(12)),
                "examples": examples,
            }
        )
    detail_rows.sort(key=lambda row: (str(row["approach"]), int(row["year"]), str(row["series"]), str(row["title"])))
    return out, detail_rows


def microseries(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    for spec in MINI_SERIES:
        matched_rows = []
        for row in rows:
            matched, matched_terms = row_matches_spec(row, spec)
            if not matched:
                continue
            matched_rows.append(row)
            details.append(
                {
                    "microseries": spec["code"],
                    "label": spec["label"],
                    "presentation_id": row["presentation_id"],
                    "year": row["year"],
                    "series": row["series"],
                    "l1": row["l1"],
                    "l2": row["l2"],
                    "title": row["title"],
                    "matched_terms": "|".join(matched_terms),
                }
            )
        term_counts = Counter()
        l1_counts = Counter()
        for row in matched_rows:
            term_counts.update(row["unique_tokens"])
            l1_counts[str(row["l1"] or "uncoded")] += 1
        zograf_count = sum(1 for row in matched_rows if row["series"] == "Zograf Readings")
        roerich_count = sum(1 for row in matched_rows if row["series"] == "Roerich Readings")
        summary.append(
            {
                "microseries": spec["code"],
                "label": spec["label"],
                "count": len(matched_rows),
                "zograf_count": zograf_count,
                "roerich_count": roerich_count,
                "dominant_series": "Zograf" if zograf_count > roerich_count else "Roerich" if roerich_count > zograf_count else "balanced",
                "top_terms": ", ".join(display_term(term) for term, _ in term_counts.most_common(12)),
                "l1_distribution": "; ".join(
                    f"{THEME_LABELS.get(l1, l1)}: {count}" for l1, count in l1_counts.most_common(6)
                ),
                "examples": "; ".join(str(row["title"]) for row in matched_rows[:3]),
            }
        )
    summary.sort(key=lambda row: (int(row["count"]), int(row["zograf_count"]) + int(row["roerich_count"])), reverse=True)
    details.sort(key=lambda row: (str(row["microseries"]), int(row["year"]), str(row["series"])))
    return summary, details


def theme_terms(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    docs: Counter[tuple[str, str]] = Counter()
    for row in rows:
        for axis in ["l1", "l2"]:
            value = str(row.get(axis, ""))
            if not value:
                continue
            key = (axis, value)
            docs[key] += 1
            grouped[key].update(row["unique_tokens"])
    out = []
    for (axis, value), counter in sorted(grouped.items()):
        for term, count in counter.most_common(12):
            if count < 2:
                continue
            out.append(
                {
                    "axis": axis,
                    "category": value,
                    "term": term,
                    "document_frequency": count,
                    "category_title_share_pct": round(100 * count / docs[(axis, value)], 2),
                }
            )
    return out


def cooccurrence(rows: list[dict[str, object]], top_n_terms: int = 120) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    df = Counter()
    for row in rows:
        df.update(row["unique_tokens"])
    top_terms = {term for term, count in df.most_common(top_n_terms) if count >= 3}
    pair_counts = Counter()
    for row in rows:
        terms = sorted(set(row["unique_tokens"]) & top_terms)
        for a, b in itertools.combinations(terms, 2):
            pair_counts[(a, b)] += 1

    n_docs = len(rows)
    node_rows = [
        {
            "term": term,
            "document_frequency": count,
            "title_share_pct": round(100 * count / n_docs, 2),
        }
        for term, count in df.most_common(top_n_terms)
        if count >= 3
    ]
    edge_rows = []
    for (a, b), count in pair_counts.most_common():
        if count < 3:
            continue
        pmi = math.log((count * n_docs) / (df[a] * df[b]))
        edge_rows.append(
            {
                "term_a": a,
                "term_b": b,
                "display_pair": display_bigram(f"{a} {b}"),
                "cooccurrence_titles": count,
                "pmi": round(pmi, 3),
                "term_a_df": df[a],
                "term_b_df": df[b],
            }
        )
    return node_rows, edge_rows[:250]


def svg(width: int, height: int, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        "<style>"
        "text{font-family:Arial,'Liberation Sans',sans-serif;fill:#1f2933}"
        ".title{font-size:20px;font-weight:700}.sub{font-size:13px;fill:#52616b}"
        ".axis{font-size:12px}.label{font-size:11px}"
        "</style>\n"
        + "\n".join(body)
        + "\n</svg>\n"
    )


def text(x: float, y: float, value: object, cls: str = "axis", anchor: str = "start", weight: str | None = None) -> str:
    weight_attr = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{weight_attr}>'
        f"{escape(str(value))}</text>"
    )


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none") -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="{stroke}"/>'


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = "#cfd8e3", width: float = 1.0) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"/>'


def write_contrast_svg(contrast_rows: list[dict[str, object]]) -> None:
    zograf = [row for row in contrast_rows if row["distinctive_for"] == "Zograf"][:12]
    roerich = [row for row in contrast_rows if row["distinctive_for"] == "Roerich"][:12]
    selected = list(reversed(roerich)) + zograf
    width, height = 1080, 760
    left, top, plot_w, row_h = 260, 82, 660, 24
    max_abs = max(abs(float(row["z_score"])) for row in selected) if selected else 1.0
    max_abs = max(3.0, math.ceil(max_abs))

    def sx(value: float) -> float:
        return left + plot_w / 2 + value / max_abs * (plot_w / 2)

    body = [
        text(34, 32, "Ключевые слова заголовков: контраст площадок", "title"),
        text(34, 56, "Log-odds по document frequency: слева термины Рериха, справа термины Зографа.", "sub"),
        rect(left, top - 22, plot_w, row_h * len(selected) + 34, "#ffffff", "#cfd8e3"),
    ]
    zero = sx(0)
    body.append(line(zero, top - 22, zero, top + row_h * len(selected) + 12, "#8b98a5", 1.2))
    body.append(text(zero - 8, top - 32, "0", "axis", "end"))
    body.append(text(left, top - 32, "Рерих", "axis", "start", "700"))
    body.append(text(left + plot_w, top - 32, "Зограф", "axis", "end", "700"))

    for i, row in enumerate(selected):
        y = top + i * row_h
        value = float(row["z_score"])
        x0, x1 = sx(0), sx(value)
        color = "#2f6fbb" if value > 0 else "#b8554b"
        body.append(line(x0, y, x1, y, color, 8))
        anchor = "end" if value < 0 else "start"
        label_x = x1 - 10 if value < 0 else x1 + 10
        body.append(text(label_x, y + 4, display_term(row["term"]), "axis", anchor, "700" if abs(value) >= 2 else None))
        body.append(text(left + plot_w + 18, y + 4, f"{row['zograf_df']} / {row['roerich_df']}", "label"))

    body.append(text(left + plot_w + 18, top - 32, "df Z/R", "label"))
    body.append(text(34, height - 22, "Показаны термины с наибольшим абсолютным z-score; generic academic words удалены.", "sub"))
    (FIG / "title_keyword_contrast.svg").write_text(svg(width, height, body), encoding="utf-8")


def write_trend_svg(trend_rows: list[dict[str, object]]) -> None:
    late = [row for row in trend_rows if row["trend"] == "late"][:12]
    early = [row for row in trend_rows if row["trend"] == "early"][:12]
    selected = list(reversed(early)) + late
    width, height = 1080, 760
    left, top, plot_w, row_h = 260, 82, 660, 24
    max_abs = max(abs(float(row["z_score"])) for row in selected) if selected else 1.0
    max_abs = max(3.0, math.ceil(max_abs))

    def sx(value: float) -> float:
        return left + plot_w / 2 + value / max_abs * (plot_w / 2)

    body = [
        text(34, 32, "Ключевые слова заголовков: сдвиг по периодам", "title"),
        text(34, 56, "Log-odds по document frequency: слева 2004-2017, справа 2018-2026.", "sub"),
        rect(left, top - 22, plot_w, row_h * len(selected) + 34, "#ffffff", "#cfd8e3"),
    ]
    zero = sx(0)
    body.append(line(zero, top - 22, zero, top + row_h * len(selected) + 12, "#8b98a5", 1.2))
    body.append(text(zero - 8, top - 32, "0", "axis", "end"))
    body.append(text(left, top - 32, "2004-2017", "axis", "start", "700"))
    body.append(text(left + plot_w, top - 32, "2018-2026", "axis", "end", "700"))

    for i, row in enumerate(selected):
        y = top + i * row_h
        value = float(row["z_score"])
        x0, x1 = sx(0), sx(value)
        color = "#2f6fbb" if value > 0 else "#b8554b"
        body.append(line(x0, y, x1, y, color, 8))
        anchor = "end" if value < 0 else "start"
        label_x = x1 - 10 if value < 0 else x1 + 10
        body.append(text(label_x, y + 4, display_term(row["term"]), "axis", anchor, "700" if abs(value) >= 2 else None))
        body.append(text(left + plot_w + 18, y + 4, f"{row['early_df']} / {row['late_df']}", "label"))

    body.append(text(left + plot_w + 18, top - 32, "df early/late", "label"))
    body.append(text(34, height - 22, "Показаны термины с наибольшим абсолютным z-score; римские числительные и служебные слова удалены.", "sub"))
    (FIG / "title_keyword_period_trend.svg").write_text(svg(width, height, body), encoding="utf-8")


def top_terms(rows: list[dict[str, object]], n: int = 15) -> str:
    return ", ".join(display_term(row["term"]) for row in rows[:n])


def top_structural_terms(all_terms: list[dict[str, object]], n: int = 12) -> str:
    terms = [row for row in all_terms if row["term"] in STRUCTURAL_TERMS]
    return top_terms(terms, n)


def plural_ru_titles(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "заголовок"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "заголовка"
    return "заголовков"


def write_report(
    rows: list[dict[str, object]],
    term_rows: list[dict[str, object]],
    bigram_rows: list[dict[str, object]],
    contrast_rows: list[dict[str, object]],
    trend_rows: list[dict[str, object]],
    series_trend_rows: list[dict[str, object]],
    ethno_rows: list[dict[str, object]],
    linguistics_rows: list[dict[str, object]],
    microseries_rows: list[dict[str, object]],
    theme_term_rows: list[dict[str, object]],
    edge_rows: list[dict[str, object]],
) -> None:
    valid = [row for row in rows if row["tokens"]]
    theme_matched = sum(1 for row in rows if row.get("theme_match"))
    z_terms = [row for row in contrast_rows if row["distinctive_for"] == "Zograf"]
    r_terms = [row for row in contrast_rows if row["distinctive_for"] == "Roerich"]
    late_terms = [row for row in trend_rows if row["trend"] == "late"]
    early_terms = [row for row in trend_rows if row["trend"] == "early"]
    series_trends = {
        series: [row for row in series_trend_rows if row["series"] == series]
        for series in SERIES_RU
    }
    all_terms = [row for row in term_rows if row["group"] == "ALL"]
    all_bigrams = [row for row in bigram_rows if row["group"] == "ALL"]
    structural_context = structural_contexts(rows)
    ethno_lookup = {(row["scope"], row["l1"]): row for row in ethno_rows}
    friday_distribution = [
        row
        for row in ethno_rows
        if row["scope"] == "zograf_friday_all" and row["l1"] != "ALL"
    ]
    linguistics_total = sum(int(row["count"]) for row in linguistics_rows)
    l1_counts = Counter(str(row.get("l1", "")) for row in rows if row.get("l1"))
    l1_terms: dict[str, list[str]] = {}
    for category, _ in l1_counts.most_common():
        terms = [
            display_term(row["term"])
            for row in theme_term_rows
            if row["axis"] == "l1" and row["category"] == category
        ][:10]
        if terms:
            l1_terms[category] = terms

    lines = [
        "# Анализ ключевых слов в заголовках выступлений",
        "",
        "Сгенерировано скриптом `article/work_title_keywords.py` из `conferences.db`.",
        "",
        "## Корпус и обработка",
        "",
        f"- Выступления: {len(rows)}.",
        f"- Заголовки хотя бы с одним содержательным токеном: {len(valid)}.",
        f"- Заголовки, сопоставленные с тематической рубрикацией: {theme_matched}.",
        "- Обработка: русская лемматизация через `pymorphy3`, ручная нормализация индологических терминов, удаление служебных и общенаучных слов.",
        "",
        "## Частотное ядро",
        "",
        f"- Самые частые леммы: {top_terms(all_terms, 20)}.",
        f"- Самые частые биграммы: {', '.join(display_bigram(row['bigram']) for row in all_bigrams[:15])}.",
        f"- Институционально-источниковедческий след, который лучше интерпретировать отдельно от предметного словаря: {top_structural_terms(all_terms) or 'нет заметного ядра'}.",
        f"- Для слов `собрание` и `коллекция` обязательно указывать объект: собрание ({structural_context.get('собрание') or 'контекст не выявлен'}); коллекция ({structural_context.get('коллекция') or 'контекст не выявлен'}).",
        "",
        "## Контраст площадок",
        "",
        f"- Слова, сильнее связанные с Зографскими чтениями: {top_terms(z_terms, 15)}.",
        f"- Слова, сильнее связанные с Рериховскими чтениями: {top_terms(r_terms, 15)}.",
        "",
        "## Динамика по периодам",
        "",
        f"- Более поздний слой (2018-2026 относительно 2004-2017): {top_terms(late_terms, 15)}.",
        f"- Более ранний слой (2004-2017 относительно 2018-2026): {top_terms(early_terms, 15)}.",
        "",
        "## Динамика по периодам внутри площадок",
        "",
    ]
    for series, label in SERIES_RU.items():
        s_rows = series_trends[series]
        s_late = [row for row in s_rows if row["trend"] == "late"]
        s_early = [row for row in s_rows if row["trend"] == "early"]
        lines.append(f"- {label}, поздний слой: {top_terms(s_late, 12)}.")
        lines.append(f"- {label}, ранний слой: {top_terms(s_early, 12)}.")
    lines += [
        "",
        "## Аудит тематической рубрикации",
        "",
        "Ключевые слова можно использовать как проверку L1/L2-кодов: рубрика задает крупную область, а леммы показывают, за счет каких текстов, языков, жанров и имен эта область фактически набирается.",
        "",
    ]
    for category, terms in list(l1_terms.items())[:10]:
        label = THEME_LABELS.get(category, category)
        count = l1_counts[category]
        lines.append(f"- {label} ({count} {plural_ru_titles(count)}): {', '.join(terms)}.")
    lines += [
        "",
        "## Лингвистика как зонтичная рубрика",
        "",
        f"Рубрика `linguistics` оставлена как зонтичная ({linguistics_total} {plural_ru_titles(linguistics_total)}), но внутри нее полезно развести два разных исследовательских подхода.",
        "",
    ]
    for row in linguistics_rows:
        count = int(row["count"])
        lines.append(
            f"- {row['label']} ({count} {plural_ru_titles(count)}; Зограф: {row['zograf_count']}, Рерих: {row['roerich_count']}): {row['top_terms']}."
        )
    lines += [
        "",
        "Языковедческий анализ описывает устройство языка: грамматику, семантику, этимологию, синтаксис, диалекты, лексику и терминологию. Филология текста работает иначе: ее единицей чаще становится перевод, комментарий, рукопись, фрагмент, надпись, реконструкция или история чтения текста. В таблице их лучше держать под общим зонтиком, но в интерпретации не смешивать.",
        "",
        "## Мини-серии поверх рубрик",
        "",
        "Мини-серия здесь означает устойчивый предметно-языковой или корпусный контур, который проходит сквозь несколько L1-рубрик. Один заголовок может принадлежать нескольким мини-сериям.",
        "",
    ]
    for row in microseries_rows[:12]:
        count = int(row["count"])
        lines.append(
            f"- {row['label']} ({count} {plural_ru_titles(count)}; Зограф: {row['zograf_count']}, Рерих: {row['roerich_count']}): {row['top_terms']}."
        )
    micro_lookup = {row["microseries"]: row for row in microseries_rows}
    dravid = micro_lookup.get("dravidology_south_india")
    tibet = micro_lookup.get("tibetology_himalaya")
    if dravid and tibet:
        lines += [
            "",
            f"Для аргумента важно, что строгая рубрика `tibetology` ({l1_counts.get('tibetology', 0)} {plural_ru_titles(l1_counts.get('tibetology', 0))}) расширяется до тибетолого-гималайского контура в {tibet['count']} {plural_ru_titles(int(tibet['count']))}. Симметрично этому дравидология / южноиндийский контур дает {dravid['count']} {plural_ru_titles(int(dravid['count']))}, причем ядро заметно сильнее связано с Зографскими чтениями (Зограф: {dravid['zograf_count']}, Рерих: {dravid['roerich_count']}). Поэтому дравидологию лучше показывать не как подслучай литературы или религии, а как самостоятельную мини-серию Зографского корпуса.",
        ]
    strict_ethno = ethno_lookup.get(("strict_l1_all", "ALL"), {"count": 0})
    friday_all = ethno_lookup.get(("zograf_friday_all", "ALL"), {"count": 0})
    friday_ethno = ethno_lookup.get(("zograf_friday_strict_ethnography", "ALL"), {"count": 0})
    friday_dist = ", ".join(
        f"{THEME_LABELS.get(str(row['l1']), row['l1'])}: {row['count']}"
        for row in friday_distribution[:7]
    )
    lines += [
        "",
        "## Примечание к этнографии",
        "",
        f"Строгая L1-рубрика `ethnography` дает {strict_ethno['count']} заголовок: это нижняя граница, а не весь этнографический контур конференции. Для Зографских чтений календарные пятницы дают {friday_all['count']} выступлений; из них только {friday_ethno['count']} имеют L1=`ethnography`, тогда как остальные распределены по смежным рубрикам: {friday_dist}.",
        "",
        "Для статьи лучше развести два показателя: узкую предметную этнографию и широкий пятничный этнографо-перформативный контур, куда попадают ритуал, фольклор, театр/танец, материальная культура, музейные коллекции и локальные традиции. Это снимает видимое противоречие между малым числом `ethnography` и фактической программной ролью пятницы.",
        "",
        "## Лексические связки",
        "",
        "Формат строк: два термина, число совместных появлений, затем коэффициент совместной специфичности.[^pmi]",
        "",
    ]
    for row in edge_rows[:20]:
        pair = display_bigram(f"{row['term_a']} {row['term_b']}")
        lines.append(
            f"- {pair}: {row['cooccurrence_titles']} раз, {row['pmi']}."
        )
    lines += [
        "",
        "## Как это развивает аргументацию",
        "",
        "### 1. Контраст площадок через словарь заголовков",
        "",
        "Сравнение площадок через крупные рубрики показывает дисциплинарный профиль, но может скрывать разные исследовательские языки внутри одной и той же рубрики. Лексический контраст уточняет этот уровень: Зографские чтения чаще проявляют словарь языков, школ, авторских корпусов и современной индийской проблематики, тогда как Рериховские чтения сильнее маркируются именем Рериха, древностью, пали, изображениями, культами, пуранами, Китаем, Монголией и музейно-источниковедческим словарем. Поэтому аргумент становится двухэтажным: площадки отличаются не только тем, сколько у них религии, литературы или истории, но и тем, какими словами эти области описываются.",
        "",
        "### 2. Диахрония как контроль реального сдвига и источникового эффекта",
        "",
        "Общая динамика словаря нужна не только для рассказа о смене интересов. Она работает как контроль качества данных: рост слов вроде `Москва`, `Санкт-Петербург`, `ИВР РАН`, `МАЭ РАН`, `собрание`, `коллекция` может означать не тематическую моду, а изменение состава программ, музейных блоков или качества извлечения заголовков. Поэтому каждый диахронный вывод следует проверять в двух разрезах: общий корпус и отдельно Зограф/Рерих. Если слово растет в обоих разрезах, это сильнее похоже на общий сдвиг поля; если только в одном, это может быть эффект конкретной площадки, года, пятничного блока или источника.",
        "",
        "### 3. Лексические связки как мезоуровень между рубрикой и отдельным докладом",
        "",
        "Совместные появления терминов дают материал не для декоративной сети, а для проверки устойчивых тематических сцеплений. Узел показывает повторяющийся термин, ребро — что два термина регулярно оказываются в одном заголовке; вес ребра можно считать либо простым числом заголовков, либо коэффициентом совместной специфичности. Так сеть показывает не только популярные слова, но и характерные пары: например, `тамильская поэзия`, `санскритская драма`, `ранний буддизм`, `собрание МАЭ РАН`. Это полезно для аргумента о внутренней структуре поля: крупная рубрика распадается на связки текстов, языков, регионов, жанров, коллекций и исследовательских традиций.",
        "",
        "[^pmi]: PMI, pointwise mutual information, показывает, насколько часто два термина встречаются вместе по сравнению с ожидаемой случайной совместной встречаемостью. Положительное значение означает специфическую связку; около нуля — обычную совместную частотность популярных слов.",
        "",
    ]
    (OUT / "title_keyword_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    rows = load_title_rows()

    token_rows = [
        {
            "presentation_id": row["presentation_id"],
            "year": row["year"],
            "period": row["period"],
            "series": row["series"],
            "calendar_date": row["calendar_date"],
            "weekday": row["weekday"],
            "l1": row["l1"],
            "l2": row["l2"],
            "title": row["title"],
            "tokens": "|".join(row["tokens"]),
            "unique_tokens": "|".join(row["unique_tokens"]),
            "bigrams": "|".join(row["bigrams"]),
            "theme_match": row["theme_match"],
        }
        for row in rows
    ]
    presentation_tag_rows = [
        {
            "presentation_id": row["presentation_id"],
            "tags": "|".join(row["tokens"]),
        }
        for row in rows
    ]
    term_rows = term_frequencies(rows)
    bigram_rows = bigram_frequencies(rows)
    contrast_rows = contrast_terms(rows)
    trend_rows = period_trends(rows)
    series_trend_rows = period_trends_by_series(rows)
    ethno_rows = ethnography_diagnostics(rows)
    linguistics_rows, linguistics_title_rows = linguistics_subfields(rows)
    microseries_rows, microseries_title_rows = microseries(rows)
    theme_term_rows = theme_terms(rows)
    node_rows, edge_rows = cooccurrence(rows)

    write_csv(OUT / "title_keyword_tokens.csv", token_rows)
    write_csv(ANALYTICS / "presentation_tags.csv", presentation_tag_rows)
    write_csv(OUT / "title_keyword_terms.csv", term_rows)
    write_csv(OUT / "title_keyword_bigrams.csv", bigram_rows)
    write_csv(OUT / "title_keyword_contrasts.csv", contrast_rows)
    write_csv(OUT / "title_keyword_period_trends.csv", trend_rows)
    write_csv(OUT / "title_keyword_period_trends_by_series.csv", series_trend_rows)
    write_csv(OUT / "title_keyword_ethnography_diagnostics.csv", ethno_rows)
    write_csv(OUT / "title_keyword_linguistics_subfields.csv", linguistics_rows)
    write_csv(OUT / "title_keyword_linguistics_subfield_titles.csv", linguistics_title_rows)
    write_csv(OUT / "title_keyword_microseries.csv", microseries_rows)
    write_csv(OUT / "title_keyword_microseries_titles.csv", microseries_title_rows)
    write_csv(OUT / "title_keyword_theme_terms.csv", theme_term_rows)
    write_csv(OUT / "title_keyword_nodes.csv", node_rows)
    write_csv(OUT / "title_keyword_cooccurrence_edges.csv", edge_rows)
    write_contrast_svg(contrast_rows)
    write_trend_svg(trend_rows)
    write_report(
        rows,
        term_rows,
        bigram_rows,
        contrast_rows,
        trend_rows,
        series_trend_rows,
        ethno_rows,
        linguistics_rows,
        microseries_rows,
        theme_term_rows,
        edge_rows,
    )
    print(f"Wrote title keyword outputs to {OUT}")
    print(f"Wrote keyword figures to {FIG}")


if __name__ == "__main__":
    main()
