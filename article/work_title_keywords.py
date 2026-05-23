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
  article/hypothesis_output/title_keyword_theme_terms.csv
  article/hypothesis_output/title_keyword_nodes.csv
  article/hypothesis_output/title_keyword_cooccurrence_edges.csv
  article/hypothesis_output/title_keyword_report.md
  article/figures/title_keyword_contrast.svg
  article/figures/title_keyword_period_trend.svg
"""
from __future__ import annotations

import csv
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
DB = ROOT / "conferences.db"
ANALYTICS = ROOT / "analytics_output"
OUT = ROOT / "article" / "hypothesis_output"
FIG = ROOT / "article" / "figures"


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
    "лалитавистар": "лалитавистара",
    "паниня": "панини",
    "пуран": "пураны",
    "пурана": "пураны",
    "рамаян": "рамаяна",
    "танк": "танка",
    "шив": "шива",
    "абхинавагупт": "абхинавагупта",
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
    "ивр",
    "кабинет",
    "коллекция",
    "маэ",
    "москва",
    "ран",
    "санкт-петербург",
    "собрание",
}

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

TOKEN_RE = re.compile(r"[а-яёa-z][а-яёa-z-]{2,}", re.IGNORECASE)
MORPH = pymorphy3.MorphAnalyzer()


def period_bucket(year: int) -> str:
    for label, start, end in PERIODS:
        if start <= year <= end:
            return label
    return "other"


def normalize_title_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower().replace("ё", "е")).strip()


@lru_cache(maxsize=20000)
def normalize_token(token: str) -> str:
    token = token.lower().replace("ё", "е").strip("-")
    if not token:
        return ""
    if re.fullmatch(r"[a-z][a-z-]+", token):
        return token
    parsed = MORPH.parse(token)[0]
    lemma = parsed.normal_form.replace("ё", "е")
    return CANONICAL.get(lemma, lemma)


def tokenize(title: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(title or ""):
        token = normalize_token(raw)
        if not token or len(token) < 3:
            continue
        if re.fullmatch(r"[ivxlcdm]+", token):
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
    for presentation_id, title, year, series in con.execute(
        """
        select pr.presentation_id, pr.title, e.year, es.series_name_en
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        order by e.year, es.series_name_en, pr.presentation_id
        """
    ):
        tokens = tokenize(title or "")
        theme_key = (str(year), series, normalize_title_key(title or ""))
        theme_row = theme_by_id.get(presentation_id) or theme_by_title.get(theme_key, {})
        rows.append(
            {
                "presentation_id": presentation_id,
                "title": title or "",
                "year": int(year),
                "period": period_bucket(int(year)),
                "series": series,
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
        body.append(text(label_x, y + 4, row["term"], "axis", anchor, "700" if abs(value) >= 2 else None))
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
        body.append(text(label_x, y + 4, row["term"], "axis", anchor, "700" if abs(value) >= 2 else None))
        body.append(text(left + plot_w + 18, y + 4, f"{row['early_df']} / {row['late_df']}", "label"))

    body.append(text(left + plot_w + 18, top - 32, "df early/late", "label"))
    body.append(text(34, height - 22, "Показаны термины с наибольшим абсолютным z-score; римские числительные и служебные слова удалены.", "sub"))
    (FIG / "title_keyword_period_trend.svg").write_text(svg(width, height, body), encoding="utf-8")


def top_terms(rows: list[dict[str, object]], n: int = 15) -> str:
    return ", ".join(str(row["term"]) for row in rows[:n])


def top_structural_terms(all_terms: list[dict[str, object]], n: int = 12) -> str:
    terms = [row for row in all_terms if row["term"] in STRUCTURAL_TERMS]
    return top_terms(terms, n)


def write_report(
    rows: list[dict[str, object]],
    term_rows: list[dict[str, object]],
    bigram_rows: list[dict[str, object]],
    contrast_rows: list[dict[str, object]],
    trend_rows: list[dict[str, object]],
    theme_term_rows: list[dict[str, object]],
    edge_rows: list[dict[str, object]],
) -> None:
    valid = [row for row in rows if row["tokens"]]
    theme_matched = sum(1 for row in rows if row.get("theme_match"))
    z_terms = [row for row in contrast_rows if row["distinctive_for"] == "Zograf"]
    r_terms = [row for row in contrast_rows if row["distinctive_for"] == "Roerich"]
    late_terms = [row for row in trend_rows if row["trend"] == "late"]
    early_terms = [row for row in trend_rows if row["trend"] == "early"]
    all_terms = [row for row in term_rows if row["group"] == "ALL"]
    all_bigrams = [row for row in bigram_rows if row["group"] == "ALL"]
    l1_counts = Counter(str(row.get("l1", "")) for row in rows if row.get("l1"))
    l1_terms: dict[str, list[str]] = {}
    for category, _ in l1_counts.most_common():
        terms = [
            str(row["term"])
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
        f"- Самые частые биграммы: {', '.join(row['bigram'] for row in all_bigrams[:15])}.",
        f"- Институционально-источниковедческий след, который лучше интерпретировать отдельно от предметного словаря: {top_structural_terms(all_terms) or 'нет заметного ядра'}.",
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
        "## Аудит тематической рубрикации",
        "",
        "Ключевые слова можно использовать как проверку L1/L2-кодов: рубрика задает крупную область, а леммы показывают, за счет каких текстов, языков, жанров и имен эта область фактически набирается.",
        "",
    ]
    for category, terms in list(l1_terms.items())[:10]:
        label = THEME_LABELS.get(category, category)
        count = l1_counts[category]
        lines.append(f"- {label} ({count} заголовков): {', '.join(terms)}.")
    lines += [
        "",
        "## Лексические связки",
        "",
    ]
    for row in edge_rows[:20]:
        lines.append(
            f"- {row['term_a']} + {row['term_b']}: {row['cooccurrence_titles']} заголовков, PMI={row['pmi']}."
        )
    lines += [
        "",
        "## Как это развивает аргументацию",
        "",
        "1. Тематическая рубрикация отвечает на вопрос о дисциплинарной области; ключевые слова отвечают на вопрос о языке проблематизации.",
        "2. Этот слой показывает собственные имена, корпуса текстов, языки, жанры, места и институциональные следы, которые рубрикация неизбежно сглаживает.",
        "3. Контраст площадок можно проверять не только через доли крупных рубрик, но и через конкретный словарь заголовков.",
        "4. Диахронный анализ словаря помогает отличать реальное тематическое смещение от изменения состава мероприятий или источников данных.",
        "5. Лексические связки дают материал для сетевой визуализации: узлы — термины, ребра — совместное появление в заголовках, вес — число заголовков или PMI.",
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
    term_rows = term_frequencies(rows)
    bigram_rows = bigram_frequencies(rows)
    contrast_rows = contrast_terms(rows)
    trend_rows = period_trends(rows)
    theme_term_rows = theme_terms(rows)
    node_rows, edge_rows = cooccurrence(rows)

    write_csv(OUT / "title_keyword_tokens.csv", token_rows)
    write_csv(OUT / "title_keyword_terms.csv", term_rows)
    write_csv(OUT / "title_keyword_bigrams.csv", bigram_rows)
    write_csv(OUT / "title_keyword_contrasts.csv", contrast_rows)
    write_csv(OUT / "title_keyword_period_trends.csv", trend_rows)
    write_csv(OUT / "title_keyword_theme_terms.csv", theme_term_rows)
    write_csv(OUT / "title_keyword_nodes.csv", node_rows)
    write_csv(OUT / "title_keyword_cooccurrence_edges.csv", edge_rows)
    write_contrast_svg(contrast_rows)
    write_trend_svg(trend_rows)
    write_report(rows, term_rows, bigram_rows, contrast_rows, trend_rows, theme_term_rows, edge_rows)
    print(f"Wrote title keyword outputs to {OUT}")
    print(f"Wrote keyword figures to {FIG}")


if __name__ == "__main__":
    main()
