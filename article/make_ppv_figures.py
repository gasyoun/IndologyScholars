from __future__ import annotations

import csv
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
ANALYTICS = ROOT / "analytics_output"
HYP = ROOT / "article" / "hypothesis_output"
OUT = ROOT / "article" / "figures"


SERIES_RU = {
    "Zograf Readings": "Зографские",
    "Roerich Readings": "Рериховские",
}

L1_RU = {
    "literature": "литература",
    "philosophy": "философия",
    "religion": "религиоведение",
    "history": "история",
    "linguistics": "лингвистика",
    "art_archaeology": "искусство/арх.",
    "ethnography": "этнография",
    "tibetology": "тибетология",
    "pedagogy_applied": "педагогика",
    "other": "прочее",
}

L2_RU = {
    "vedic": "вед.",
    "classical": "класс.",
    "medieval": "среднев.",
    "colonial": "колон.",
    "modern": "нов.",
    "contemporary": "совр.",
    "unspecified": "н/о",
}

L1_ORDER = [
    "literature",
    "philosophy",
    "religion",
    "history",
    "linguistics",
    "art_archaeology",
    "ethnography",
    "tibetology",
    "pedagogy_applied",
    "other",
]

L2_ORDER = [
    "vedic",
    "classical",
    "medieval",
    "colonial",
    "modern",
    "contemporary",
    "unspecified",
]

CITY_TOKENS = {
    "москва",
    "санкт-петербург",
    "санкт петербург",
    "спб",
    "с.-петербург",
    "петербург",
    "калининград",
    "новосибирск",
    "казань",
    "екатеринбург",
    "владивосток",
    "уфа",
    "томск",
    "элиста",
    "улан-удэ",
    "ялта",
    "нижний новгород",
    "пермь",
    "воронеж",
    "ростов-на-дону",
    "красноярск",
    "иркутск",
    "пенза",
    "дели",
    "тель-авив",
}

INST_TOKENS = [
    "ран",
    "университет",
    "институт",
    "ивр",
    "ив ",
    "маэ",
    "музей",
    "рггу",
    "вшэ",
    "спбгу",
    "мгу",
    "рудн",
    "кафедр",
    "академи",
    "центр",
    "library",
    "university",
    "institute",
    "museum",
    "лаборатор",
    "школа",
    "семинар",
    "фонд",
    "общество",
]


def svg(width: int, height: int, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        "<style>\n"
        "text{font-family:Arial,'Liberation Sans',sans-serif;fill:#1f2933}"
        ".small{font-size:12px}.axis{font-size:13px}.label{font-size:12px}"
        ".title{font-size:20px;font-weight:700}.subtitle{font-size:13px;fill:#52616b}"
        ".tick{stroke:#c9d2dc;stroke-width:1}.grid{stroke:#edf1f5;stroke-width:1}"
        "</style>\n"
        + "\n".join(body)
        + "\n</svg>\n"
    )


def line(x1, y1, x2, y2, stroke="#8b98a5", width=1, dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
    )


def rect(x, y, w, h, fill, stroke="none", rx=0, opacity=1.0) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>'
    )


def text(x, y, value, cls="small", anchor="start", weight: str | None = None) -> str:
    weight_attr = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"'
        f'{weight_attr}>{escape(str(value))}</text>'
    )


def rotated_text(x, y, value, angle=-90, cls="small", anchor="middle") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}" '
        f'transform="rotate({angle} {x:.1f} {y:.1f})">{escape(str(value))}</text>'
    )


def circle(x, y, r, fill, stroke="#ffffff", width=1.2, opacity=0.88) -> str:
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>'
    )


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def norm_affiliation(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def is_city_only_affiliation(value: str) -> bool:
    n = norm_affiliation(value)
    if not n:
        return True
    core = n
    for city in CITY_TOKENS:
        core = re.sub(rf"[ ,(]+{re.escape(city)}[ ,)]*$", "", core).strip(" ,()")
    if not core or core in CITY_TOKENS:
        return True
    if any(token in n for token in INST_TOKENS):
        return False
    if len(n) <= 18 and "," not in n and " " not in n:
        return True
    return False


def short_name(name: str) -> str:
    parts = name.replace("\xa0", " ").split()
    if not parts:
        return name
    if len(parts) >= 3 and len(parts[0]) > 2:
        return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
    return " ".join(parts[:3])


def series_short(series: str) -> str:
    return "Zograf" if "Zograf" in series else "Roerich"


@dataclass
class PersonSeries:
    person_id: str
    name: str
    series: str
    n: int
    first_year: int
    last_year: int
    birth_year: int | None


def load_person_series() -> dict[str, dict[str, PersonSeries]]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        """
        select
            pp.person_id,
            p.display_name,
            es.series_name_en,
            count(*) as n,
            min(e.year),
            max(e.year),
            p.birth_year
        from presentation_person pp
        join person p using(person_id)
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        group by pp.person_id, es.series_name_en
        """
    ).fetchall()
    out: dict[str, dict[str, PersonSeries]] = defaultdict(dict)
    for pid, name, series, n, first, last, birth in rows:
        key = series_short(series)
        out[pid][key] = PersonSeries(pid, name, key, n, first, last, birth)
    return out


def load_person_years() -> dict[tuple[str, str], set[int]]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        """
        select distinct pp.person_id, es.series_name_en, e.year
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        """
    ).fetchall()
    years: dict[tuple[str, str], set[int]] = defaultdict(set)
    for pid, series, year in rows:
        years[(series_short(series), pid)].add(year)
    return years


def figure_cross_cohort(person_series: dict[str, dict[str, PersonSeries]]) -> dict[str, int]:
    width, height = 980, 700
    margin = dict(left=86, right=48, top=82, bottom=84)
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    xmax, ymax = 16, 13

    def sx(x):
        return margin["left"] + x / xmax * plot_w

    def sy(y):
        return margin["top"] + (1 - y / ymax) * plot_h

    points = []
    for pid, data in person_series.items():
        if "Zograf" not in data or "Roerich" not in data:
            continue
        z = data["Zograf"].n
        r = data["Roerich"].n
        total = z + r
        balance = (z - r) / total
        first = min(data["Zograf"].first_year, data["Roerich"].first_year)
        last = max(data["Zograf"].last_year, data["Roerich"].last_year)
        if balance >= 0.33:
            orient = "Zograf-oriented"
            color = "#2f6fbb"
        elif balance <= -0.33:
            orient = "Roerich-oriented"
            color = "#b8554b"
        else:
            orient = "balanced"
            color = "#657482"
        points.append((z, r, total, balance, first, last, data["Zograf"].name, orient, color))

    body = [
        text(34, 32, "Перекрестная когорта: баланс участия на двух площадках", "title"),
        text(
            34,
            56,
            "39 участников, выступавших и на Зографских, и на Рериховских чтениях; диагональ означает равный вклад.",
            "subtitle",
        ),
        rect(margin["left"], margin["top"], plot_w, plot_h, "#ffffff", "#cfd8e3"),
    ]

    for x in range(0, xmax + 1, 2):
        body.append(line(sx(x), margin["top"], sx(x), margin["top"] + plot_h, "#edf1f5"))
        body.append(text(sx(x), margin["top"] + plot_h + 22, x, "axis", "middle"))
    for y in range(0, ymax + 1, 2):
        body.append(line(margin["left"], sy(y), margin["left"] + plot_w, sy(y), "#edf1f5"))
        body.append(text(margin["left"] - 14, sy(y) + 4, y, "axis", "end"))
    body.append(line(sx(0), sy(0), sx(13), sy(13), "#7f8c99", 1.4, "6 5"))
    body.append(text(margin["left"] + plot_w / 2, height - 30, "Докладов на Зографских чтениях", "axis", "middle"))
    body.append(rotated_text(24, margin["top"] + plot_h / 2, "Докладов на Рериховских чтениях", cls="axis"))

    # Draw points first.
    for z, r, total, balance, first, last, name, orient, color in sorted(points, key=lambda p: p[2]):
        radius = 4.2 + math.sqrt(total) * 1.45
        body.append(circle(sx(z), sy(r), radius, color))

    # Keep labels sparse: the figure should show the shape, not become a name index.
    label_plan = [
        ("Вертоградова", -12, -12, "end"),
        ("Рыжакова", 10, -8, "start"),
        ("Лысенко", 10, -8, "start"),
        ("Цветкова", -10, -12, "end"),
        ("Александрова", -10, -12, "end"),
        ("Тавастшерна", -10, -12, "end"),
        ("Дубянский", -10, 18, "end"),
        ("Корнеева", 10, 18, "start"),
    ]
    for needle, dx, dy, anchor in label_plan:
        match = next((p for p in points if needle in p[6]), None)
        if not match:
            continue
        z, r, total, balance, first, last, name, orient, color = match
        body.append(text(sx(z) + dx, sy(r) + dy, short_name(name), "label", anchor))

    legend_x, legend_y = 685, 94
    body.append(rect(legend_x - 16, legend_y - 22, 252, 100, "#ffffff", "#d8e0e8", 5, 0.94))
    for i, (label, color) in enumerate(
        [
            ("Зограф-ориентированные", "#2f6fbb"),
            ("сбалансированные", "#657482"),
            ("Рерих-ориентированные", "#b8554b"),
        ]
    ):
        y = legend_y + i * 26
        body.append(circle(legend_x, y, 6.5, color))
        body.append(text(legend_x + 16, y + 4, label, "small"))

    counts = Counter(p[7] for p in points)
    body.append(text(34, height - 14, f"Итог: {counts['balanced']} сбалансированных, {counts['Roerich-oriented']} рерих-ориентированных, {counts['Zograf-oriented']} зограф-ориентированных.", "subtitle"))
    (OUT / "cross_cohort_balance.svg").write_text(svg(width, height, body), encoding="utf-8")
    return dict(counts)


def figure_participant_dynamics(person_series: dict[str, dict[str, PersonSeries]]) -> dict[str, list[dict[str, float]]]:
    person_years = load_person_years()
    summaries: dict[str, list[dict[str, float]]] = {}
    width, height = 1120, 760
    body = [
        text(34, 32, "Обновление состава: новички, ретроспективное ядро и повторные участники", "title"),
        text(34, 56, "Столбцы показывают структуру участников по годам; линия — долю дебютантов и не соединяет лакуны.", "subtitle"),
    ]
    colors = {"new": "#7aa6d8", "core": "#2f6fbb", "repeat": "#aeb8c4"}
    panel_specs = [("Zograf", 90), ("Roerich", 420)]
    all_years = sorted({year for years in person_years.values() for year in years})
    xmin, xmax = min(all_years), max(all_years)
    max_total = 60
    plot_w, plot_h = 930, 230
    left = 96

    for series, top in panel_specs:
        rows = []
        for year in all_years:
            pids = [pid for (s, pid), years in person_years.items() if s == series and year in years]
            if not pids:
                continue
            new = repeat = core = 0
            for pid in pids:
                first = min(person_years[(series, pid)])
                total = person_series[pid][series].n
                if first == year:
                    new += 1
                elif total >= 5:
                    core += 1
                else:
                    repeat += 1
            rows.append(
                {
                    "year": year,
                    "new": new,
                    "repeat": repeat,
                    "core": core,
                    "total": len(pids),
                    "newcomer_pct": 100 * new / len(pids),
                }
            )
        summaries[series] = rows

        body.append(text(left, top - 14, "Зографские чтения" if series == "Zograf" else "Рериховские чтения", "axis", weight="700"))
        body.append(rect(left, top, plot_w, plot_h, "#ffffff", "#cfd8e3"))
        for y in range(0, max_total + 1, 15):
            yy = top + plot_h - (y / max_total) * plot_h
            body.append(line(left, yy, left + plot_w, yy, "#edf1f5"))
            body.append(text(left - 12, yy + 4, y, "axis", "end"))
        for pct in [0, 50, 100]:
            yy = top + plot_h - (pct / 100) * plot_h
            body.append(text(left + plot_w + 12, yy + 4, f"{pct}%", "axis", "start"))

        markers = [(2020, "COVID", 14, 5, "start")]
        if series == "Zograf":
            markers.extend([(2024, "", 14, 5, "start"), (2026, "", 30, -5, "end")])
        for year, label, dy, dx, anchor in markers:
            if xmin <= year <= xmax:
                x = left + (year - xmin + 0.5) / (xmax - xmin + 1) * plot_w
                body.append(line(x, top, x, top + plot_h, "#d6a36a", 1.1, "4 4"))
                if label:
                    body.append(text(x + dx, top + dy, label, "axis", anchor))

        bar_w = plot_w / (xmax - xmin + 1) * 0.68
        prev_line = None
        prev_year = None
        for row in rows:
            x = left + (row["year"] - xmin + 0.5) / (xmax - xmin + 1) * plot_w
            bottom = top + plot_h
            for key in ["new", "repeat", "core"]:
                h = row[key] / max_total * plot_h
                body.append(rect(x - bar_w / 2, bottom - h, bar_w, h, colors[key]))
                bottom -= h
            line_y = top + plot_h - (row["newcomer_pct"] / 100) * plot_h
            if prev_line and prev_year is not None and row["year"] == prev_year + 1:
                body.append(line(prev_line[0], prev_line[1], x, line_y, "#8a4f7d", 2.2))
            body.append(circle(x, line_y, 3.5, "#8a4f7d"))
            prev_line = (x, line_y)
            prev_year = row["year"]

        for year in range(xmin, xmax + 1, 2):
            x = left + (year - xmin + 0.5) / (xmax - xmin + 1) * plot_w
            body.append(text(x, top + plot_h + 22, year, "axis", "middle"))
        body.append(rotated_text(left - 58, top + plot_h / 2, "участников", cls="small"))
        body.append(rotated_text(left + plot_w + 64, top + plot_h / 2, "доля новичков", angle=90, cls="small"))

    legend_y = 690
    legend = [
        ("новички", colors["new"]),
        ("прочие повторные", colors["repeat"]),
        ("ретросп. ядро ≥5 докл.", colors["core"]),
        ("доля новичков", "#8a4f7d"),
    ]
    x = 96
    for label, color in legend:
        if label == "доля новичков":
            body.append(line(x, legend_y - 5, x + 26, legend_y - 5, color, 2.2))
            body.append(circle(x + 13, legend_y - 5, 3.5, color))
        else:
            body.append(rect(x, legend_y - 16, 24, 14, color))
        body.append(text(x + 34, legend_y - 4, label, "small"))
        x += 230

    (OUT / "participant_dynamics.svg").write_text(svg(width, height, body), encoding="utf-8")
    return summaries


def load_theme_rows() -> list[dict[str, str]]:
    with (ANALYTICS / "theme_codes_final.csv").open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def figure_theme_heatmap() -> dict[str, dict[tuple[str, str], int]]:
    rows = load_theme_rows()
    counts: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    for row in rows:
        series = row["series"]
        key = (row["l1"], row["l2"])
        counts[series][key] += 1
        totals[series] += 1

    width, height = 1180, 730
    body = [
        text(34, 32, "Тематическая матрица L1 × L2", "title"),
        text(34, 56, "Интенсивность ячейки — доля всех докладов данной площадки; подписи даны для ячеек ≥4%.", "subtitle"),
    ]
    cell_w, cell_h = 62, 42
    panel_tops = {"Zograf Readings": 116, "Roerich Readings": 116}
    panel_lefts = {"Zograf Readings": 172, "Roerich Readings": 690}
    max_share = 0.16

    def color(share: float) -> str:
        t = min(1, share / max_share)
        r0, g0, b0 = (242, 246, 250)
        r1, g1, b1 = (47, 111, 187)
        r = round(r0 + (r1 - r0) * t)
        g = round(g0 + (g1 - g0) * t)
        b = round(b0 + (b1 - b0) * t)
        return f"rgb({r},{g},{b})"

    for series in ["Zograf Readings", "Roerich Readings"]:
        left = panel_lefts[series]
        top = panel_tops[series]
        body.append(text(left, top - 42, SERIES_RU[series], "axis", weight="700"))
        for j, l2 in enumerate(L2_ORDER):
            body.append(text(left + j * cell_w + cell_w / 2, top - 12, L2_RU[l2], "small", "middle"))
        for i, l1 in enumerate(L1_ORDER):
            body.append(text(left - 10, top + i * cell_h + cell_h / 2 + 4, L1_RU[l1], "small", "end"))
            for j, l2 in enumerate(L2_ORDER):
                c = counts[series][(l1, l2)]
                share = c / totals[series] if totals[series] else 0
                x = left + j * cell_w
                y = top + i * cell_h
                body.append(rect(x, y, cell_w - 2, cell_h - 2, color(share), "#ffffff"))
                if share >= 0.04:
                    txt_color = "#ffffff" if share > 0.09 else "#1f2933"
                    body.append(
                        f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4:.1f}" '
                        f'class="small" text-anchor="middle" fill="{txt_color}">{share*100:.0f}%</text>'
                    )

    # Compact legend.
    lx, ly = 172, 655
    for k in range(0, 6):
        share = k / 5 * max_share
        body.append(rect(lx + k * 42, ly, 42, 14, color(share)))
    body.append(text(lx, ly + 34, "0%", "small"))
    body.append(text(lx + 252, ly + 34, f"{max_share*100:.0f}%+", "small", "end"))
    (OUT / "theme_heatmap_l1_l2.svg").write_text(svg(width, height, body), encoding="utf-8")
    return counts


def figure_birth_year_coverage(person_series: dict[str, dict[str, PersonSeries]]) -> dict[str, Counter[str]]:
    buckets = [("1", lambda n: n == 1), ("2", lambda n: n == 2), ("3–4", lambda n: 3 <= n <= 4), ("5+", lambda n: n >= 5)]
    counts = {"known": Counter(), "unknown": Counter()}
    for data in person_series.values():
        total = sum(ps.n for ps in data.values())
        birth = next((ps.birth_year for ps in data.values() if ps.birth_year is not None), None)
        group = "known" if birth is not None else "unknown"
        for label, pred in buckets:
            if pred(total):
                counts[group][label] += 1
                break

    width, height = 860, 520
    left, top, plot_w, plot_h = 110, 92, 640, 310
    ymax = 100
    body = [
        text(34, 32, "Покрытие годом рождения зависит от частоты участия", "title"),
        text(34, 56, "Неизвестные годы рождения сконцентрированы среди разовых и редких участников.", "subtitle"),
        rect(left, top, plot_w, plot_h, "#ffffff", "#cfd8e3"),
    ]
    for y in range(0, ymax + 1, 25):
        yy = top + plot_h - y / ymax * plot_h
        body.append(line(left, yy, left + plot_w, yy, "#edf1f5"))
        body.append(text(left - 12, yy + 4, f"{y}%", "axis", "end"))

    group_w = plot_w / len(buckets)
    bar_w = group_w * 0.46
    colors = {"known": "#2f6fbb", "unknown": "#b8554b"}
    for i, (label, _) in enumerate(buckets):
        cx = left + group_w * (i + 0.5)
        total = counts["known"][label] + counts["unknown"][label]
        bottom = top + plot_h
        for group in ["unknown", "known"]:
            val = counts[group][label]
            share = (val / total * 100) if total else 0
            h = share / ymax * plot_h
            body.append(rect(cx - bar_w / 2, bottom - h, bar_w, h, colors[group]))
            if share >= 8:
                body.append(text(cx, bottom - h / 2 + 4, f"{share:.0f}%", "small", "middle"))
            bottom -= h
        body.append(text(cx, top + plot_h - 100 / ymax * plot_h - 8, f"n={total}", "small", "middle"))
        body.append(text(cx, top + plot_h + 26, label, "axis", "middle"))
    body.append(text(left + plot_w / 2, height - 48, "Всего докладов/авторских участий у ученого", "axis", "middle"))
    body.append(rotated_text(left - 72, top + plot_h / 2, "доля ученых", cls="small"))

    legend_x, legend_y = 560, 110
    body.append(rect(legend_x - 16, legend_y - 24, 220, 78, "#ffffff", "#d8e0e8", 5, 0.94))
    body.append(rect(legend_x, legend_y - 10, 24, 14, colors["known"]))
    body.append(text(legend_x + 34, legend_y + 2, "год рождения известен", "small"))
    body.append(rect(legend_x, legend_y + 20, 24, 14, colors["unknown"]))
    body.append(text(legend_x + 34, legend_y + 32, "год рождения неизвестен", "small"))

    (OUT / "birth_year_coverage.svg").write_text(svg(width, height, body), encoding="utf-8")
    return counts


def figure_closedness_forest() -> list[dict[str, str]]:
    rows = load_csv_rows(HYP / "appendix_g_diff_ci.csv")
    order = ["Ядро ≥5, п.п.", "Удержание, п.п.", "Разовые, п.п.", "Джини"]
    rows = sorted(rows, key=lambda row: order.index(row["metric"]) if row["metric"] in order else 99)

    width, height = 980, 430
    left, top, plot_w = 230, 96, 600
    row_gap = 58
    x_min, x_max = -25, 25

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    body = [
        text(34, 32, "Различия метрик закрытости: Рерих минус Зограф", "title"),
        text(
            34,
            56,
            "Точки — оценка различия, линии — bootstrap 95% CI; пересечение нуля означает описательный, но не строгий эффект.",
            "subtitle",
        ),
        rect(left, top - 34, plot_w, 270, "#ffffff", "#cfd8e3"),
    ]

    for tick in [-20, -10, 0, 10, 20]:
        x = sx(tick)
        body.append(line(x, top - 34, x, top + 236, "#d6dde6" if tick == 0 else "#edf1f5", 1.4 if tick == 0 else 1))
        body.append(text(x, top + 258, tick, "axis", "middle"))
    body.append(text(left + plot_w / 2, top + 294, "Разница, процентные пункты; для Джини показано значение ×100", "axis", "middle"))

    for i, row in enumerate(rows):
        metric = row["metric"]
        y = top + i * row_gap
        scale = 100 if metric == "Джини" else 1
        point = float(row["diff"]) * scale
        ci_low = float(row["ci_low"]) * scale
        ci_high = float(row["ci_high"]) * scale
        label = "Джини ×100" if metric == "Джини" else metric.replace(", п.п.", "")
        body.append(text(left - 18, y + 4, label, "axis", "end", weight="700" if i == 0 else None))
        body.append(line(sx(ci_low), y, sx(ci_high), y, "#657482", 3))
        body.append(line(sx(ci_low), y - 6, sx(ci_low), y + 6, "#657482", 1.6))
        body.append(line(sx(ci_high), y - 6, sx(ci_high), y + 6, "#657482", 1.6))
        color = "#b8554b" if point > 0 else "#2f6fbb"
        body.append(circle(sx(point), y, 6.5, color))
        body.append(text(left + plot_w + 18, y + 4, f"{point:+.1f} [{ci_low:+.1f}; {ci_high:+.1f}]", "small"))
        body.append(text(left + plot_w + 18, y + 22, f"p_boot={float(row['p_boot']):.3f}", "label"))

    body.append(text(34, height - 22, "Чтение: положительные значения означают большую величину метрики у Рериха; отрицательные — у Зографа.", "subtitle"))
    (OUT / "closedness_forest.svg").write_text(svg(width, height, body), encoding="utf-8")
    return rows


def figure_geographic_gravity() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    dist_rows = load_csv_rows(HYP / "geographic_presentation_distribution.csv")
    retention_rows = load_csv_rows(HYP / "geographic_speaker_retention.csv")

    width, height = 1060, 540
    body = [
        text(34, 32, "Географическое притяжение и возвращаемость участников", "title"),
        text(34, 56, "Левая панель — доля докладов по городским группам; правая — доля ученых, вернувшихся хотя бы в другой год.", "subtitle"),
    ]

    city_order = [
        ("SPb", "СПб"),
        ("Moscow", "Москва"),
        ("Regions/Foreign", "регионы/\nзарубежье"),
    ]
    left, top = 96, 118
    cell_w, cell_h = 142, 76
    max_share = 75.0

    def heat_color(share: float) -> str:
        t = min(1, share / max_share)
        r0, g0, b0 = (241, 246, 250)
        r1, g1, b1 = (47, 111, 187)
        return f"rgb({round(r0 + (r1 - r0) * t)},{round(g0 + (g1 - g0) * t)},{round(b0 + (b1 - b0) * t)})"

    body.append(text(left, top - 44, "Доля докладов", "axis", weight="700"))
    for j, (_, label_value) in enumerate(city_order):
        x = left + 126 + j * cell_w + cell_w / 2
        for k, part in enumerate(label_value.split("\n")):
            body.append(text(x, top - 16 + k * 13, part, "small", "middle"))

    matrix = {}
    for row in dist_rows:
        matrix[row["city"]] = row
    for i, (series_label, pct_key, count_key) in enumerate(
        [("Зографские", "zograf_pct", "zograf_talks"), ("Рериховские", "roerich_pct", "roerich_talks")]
    ):
        y = top + i * cell_h
        body.append(text(left + 110, y + cell_h / 2 + 4, series_label, "axis", "end"))
        for j, (city_key, _) in enumerate(city_order):
            row = matrix.get(city_key, {})
            share = float(row.get(pct_key, 0) or 0)
            talks = int(row.get(count_key, 0) or 0)
            x = left + 126 + j * cell_w
            body.append(rect(x, y, cell_w - 2, cell_h - 2, heat_color(share), "#ffffff"))
            body.append(text(x + cell_w / 2, y + 33, f"{share:.1f}%", "axis", "middle", weight="700"))
            body.append(text(x + cell_w / 2, y + 53, f"n={talks}", "small", "middle"))

    bar_left, bar_top, bar_w, bar_h = 650, 118, 310, 260
    body.append(text(bar_left, bar_top - 44, "Возвращаемость по городским группам", "axis", weight="700"))
    body.append(rect(bar_left, bar_top, bar_w, bar_h, "#ffffff", "#cfd8e3"))
    for yv in [0, 20, 40, 60]:
        yy = bar_top + bar_h - yv / 70 * bar_h
        body.append(line(bar_left, yy, bar_left + bar_w, yy, "#edf1f5"))
        body.append(text(bar_left - 12, yy + 4, f"{yv}%", "axis", "end"))
    bar_colors = {"Moscow": "#b8554b", "SPb": "#2f6fbb", "Regions/Foreign": "#708090"}
    group_w = bar_w / len(city_order)
    retention_by_city = {row["city"]: row for row in retention_rows}
    for i, (city_key, label_value) in enumerate(city_order):
        row = retention_by_city.get(city_key, {})
        value = float(row.get("retention_pct", 0) or 0)
        total = int(row.get("total_speakers", 0) or 0)
        h = value / 70 * bar_h
        x = bar_left + group_w * i + group_w * 0.25
        body.append(rect(x, bar_top + bar_h - h, group_w * 0.5, h, bar_colors[city_key]))
        body.append(text(x + group_w * 0.25, bar_top + bar_h - h - 8, f"{value:.1f}%", "small", "middle", weight="700"))
        body.append(text(x + group_w * 0.25, bar_top + bar_h + 22, label_value.replace("\n", " "), "small", "middle"))
        body.append(text(x + group_w * 0.25, bar_top + bar_h + 40, f"n={total}", "label", "middle"))

    body.append(text(96, height - 40, "Ключевой контраст: петербургская площадка почти паритетна для двух столиц, московская — преимущественно московская.", "subtitle"))
    (OUT / "geographic_gravity.svg").write_text(svg(width, height, body), encoding="utf-8")
    return dist_rows, retention_rows


def figure_affiliation_transparency() -> dict[str, list[dict[str, float]]]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        """
        select es.series_name_en, e.year, pp.affiliation_text_raw
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        """
    ).fetchall()

    by_series_year: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"city": 0, "total": 0}))
    for series_name, year, aff in rows:
        series = series_short(series_name)
        by_series_year[series][int(year)]["total"] += 1
        if is_city_only_affiliation(aff or ""):
            by_series_year[series][int(year)]["city"] += 1

    summary: dict[str, list[dict[str, float]]] = {}
    for series, years in by_series_year.items():
        summary[series] = []
        for year in sorted(years):
            total = years[year]["total"]
            city = years[year]["city"]
            summary[series].append({"year": year, "city": city, "total": total, "pct": 100 * city / total if total else 0.0})

    width, height = 980, 500
    left, top, plot_w, plot_h = 92, 96, 760, 300
    xmin, xmax = 2004, 2026

    def sx(year: float) -> float:
        return left + (year - xmin) / (xmax - xmin) * plot_w

    def sy(value: float) -> float:
        return top + plot_h - value / 100 * plot_h

    body = [
        text(34, 32, "Прозрачность аффилиаций: город вместо учреждения", "title"),
        text(34, 56, "Доля авторских участий, где в программе указан только город или пустая аффилиация.", "subtitle"),
        rect(left, top, plot_w, plot_h, "#ffffff", "#cfd8e3"),
    ]
    for yv in [0, 25, 50, 75, 100]:
        yy = sy(yv)
        body.append(line(left, yy, left + plot_w, yy, "#edf1f5"))
        body.append(text(left - 12, yy + 4, f"{yv}%", "axis", "end"))
    for year in range(xmin, xmax + 1, 2):
        x = sx(year)
        body.append(line(x, top, x, top + plot_h, "#f3f6f9"))
        body.append(text(x, top + plot_h + 22, year, "axis", "middle"))

    colors = {"Zograf": "#2f6fbb", "Roerich": "#b8554b"}
    labels = {"Zograf": "Зографские", "Roerich": "Рериховские"}
    for series in ["Zograf", "Roerich"]:
        prev = None
        for row in summary.get(series, []):
            x = sx(row["year"])
            y = sy(row["pct"])
            if prev is not None:
                body.append(line(prev[0], prev[1], x, y, colors[series], 2.2))
            body.append(circle(x, y, 4.6, colors[series]))
            prev = (x, y)

    legend_x, legend_y = 710, 118
    body.append(rect(legend_x - 18, legend_y - 24, 206, 78, "#ffffff", "#d8e0e8", 5, 0.94))
    for i, series in enumerate(["Zograf", "Roerich"]):
        y = legend_y + i * 28
        body.append(line(legend_x, y, legend_x + 28, y, colors[series], 2.2))
        body.append(circle(legend_x + 14, y, 4.6, colors[series]))
        pooled_city = sum(row["city"] for row in summary.get(series, []))
        pooled_total = sum(row["total"] for row in summary.get(series, []))
        pooled = 100 * pooled_city / pooled_total if pooled_total else 0.0
        body.append(text(legend_x + 40, y + 4, f"{labels[series]}: {pooled:.1f}%", "small"))

    body.append(text(34, height - 26, "График поддерживает источниковедческий тезис: разрыв создается форматом программы, а не обязательно биографией участников.", "subtitle"))
    (OUT / "affiliation_transparency.svg").write_text(svg(width, height, body), encoding="utf-8")
    return summary


def figure_zograf_era_l2() -> list[dict[str, str]]:
    rows = load_csv_rows(HYP / "era_themes_l2.csv")
    rows = sorted(rows, key=lambda row: L2_ORDER.index(row["theme_l2"]) if row["theme_l2"] in L2_ORDER else 99)

    width, height = 980, 500
    left, top, plot_w, plot_h = 92, 96, 760, 300
    ymax = 40
    body = [
        text(34, 32, "Зографские чтения до и после 2025 г.: хронологический профиль", "title"),
        text(34, 56, "Сравнение эры Василькова (до 2024) и эры Альбедиль — Иванова (2025–2026) по периодам L2.", "subtitle"),
        rect(left, top, plot_w, plot_h, "#ffffff", "#cfd8e3"),
    ]
    for yv in [0, 10, 20, 30, 40]:
        yy = top + plot_h - yv / ymax * plot_h
        body.append(line(left, yy, left + plot_w, yy, "#edf1f5"))
        body.append(text(left - 12, yy + 4, f"{yv}%", "axis", "end"))

    colors = {"vasilkov_pct": "#2f6fbb", "albedil_pct": "#d49a3a"}
    group_w = plot_w / len(rows)
    bar_w = group_w * 0.32
    for i, row in enumerate(rows):
        cx = left + group_w * (i + 0.5)
        for j, key in enumerate(["vasilkov_pct", "albedil_pct"]):
            value = float(row[key])
            h = value / ymax * plot_h
            x = cx + (j - 0.5) * bar_w * 1.25
            body.append(rect(x - bar_w / 2, top + plot_h - h, bar_w, h, colors[key]))
            if row["theme_l2"] in {"classical", "unspecified"}:
                body.append(text(x, top + plot_h - h - 7, f"{value:.1f}", "label", "middle"))
        body.append(text(cx, top + plot_h + 24, L2_RU.get(row["theme_l2"], row["theme_l2"]), "axis", "middle"))

    legend_x, legend_y = 650, 118
    body.append(rect(legend_x - 18, legend_y - 24, 252, 78, "#ffffff", "#d8e0e8", 5, 0.94))
    body.append(rect(legend_x, legend_y - 10, 24, 14, colors["vasilkov_pct"]))
    body.append(text(legend_x + 34, legend_y + 2, "до 2025", "small"))
    body.append(rect(legend_x, legend_y + 20, 24, 14, colors["albedil_pct"]))
    body.append(text(legend_x + 34, legend_y + 32, "2025–2026", "small"))
    body.append(text(34, height - 28, "Главное изменение: снижение классического периода и рост тем без жесткой хронологической привязки.", "subtitle"))
    (OUT / "zograf_era_l2_shift.svg").write_text(svg(width, height, body), encoding="utf-8")
    return rows


def write_notes(
    cross_counts: dict[str, int],
    dynamics: dict[str, list[dict[str, float]]],
    birth_counts: dict[str, Counter[str]],
    closedness_rows: list[dict[str, str]],
    geography: tuple[list[dict[str, str]], list[dict[str, str]]],
    affiliation_summary: dict[str, list[dict[str, float]]],
    era_l2_rows: list[dict[str, str]],
) -> None:
    z2020 = next(r for r in dynamics["Zograf"] if r["year"] == 2020)
    z2021 = next(r for r in dynamics["Zograf"] if r["year"] == 2021)
    dist_rows, retention_rows = geography
    pooled_affiliation = {
        series: 100 * sum(row["city"] for row in rows) / sum(row["total"] for row in rows)
        for series, rows in affiliation_summary.items()
        if sum(row["total"] for row in rows)
    }
    lines = [
        "# Figure Notes",
        "",
        "Generated by `article/make_ppv_figures.py` from `conferences.db` and `analytics_output/theme_codes_final.csv`.",
        "",
        "## Cross-Cohort Balance",
        "",
        f"- Balanced: {cross_counts.get('balanced', 0)}.",
        f"- Roerich-oriented: {cross_counts.get('Roerich-oriented', 0)}.",
        f"- Zograf-oriented: {cross_counts.get('Zograf-oriented', 0)}.",
        "",
        "## Participant Dynamics",
        "",
        f"- Zograf 2020 newcomers: {z2020['new']} of {z2020['total']} ({z2020['newcomer_pct']:.1f}%).",
        f"- Zograf 2021 newcomers: {z2021['new']} of {z2021['total']} ({z2021['newcomer_pct']:.1f}%).",
        "",
        "## Birth-Year Coverage",
        "",
        f"- Known birth year bucket counts: {dict(birth_counts['known'])}.",
        f"- Unknown birth year bucket counts: {dict(birth_counts['unknown'])}.",
        "",
        "## Closedness Forest",
        "",
        *[
            f"- {row['metric']}: diff={row['diff']}, 95% CI [{row['ci_low']}, {row['ci_high']}], p_boot={row['p_boot']}."
            for row in closedness_rows
        ],
        "",
        "## Geographic Gravity",
        "",
        *[
            f"- {row['city']}: Zograf {row['zograf_pct']}% ({row['zograf_talks']} talks), Roerich {row['roerich_pct']}% ({row['roerich_talks']} talks)."
            for row in dist_rows
        ],
        *[
            f"- Retention {row['city']}: {row['retention_pct']}% ({row['returning_speakers']}/{row['total_speakers']})."
            for row in retention_rows
        ],
        "",
        "## Affiliation Transparency",
        "",
        f"- Pooled city-only / empty rate: Zograf {pooled_affiliation.get('Zograf', 0.0):.1f}%, Roerich {pooled_affiliation.get('Roerich', 0.0):.1f}%.",
        "",
        "## Zograf Era L2 Shift",
        "",
        *[
            f"- {row['theme_l2']}: before 2025 {row['vasilkov_pct']}%, 2025-2026 {row['albedil_pct']}%."
            for row in era_l2_rows
        ],
        "",
    ]
    (OUT / "figure_notes.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    person_series = load_person_series()
    cross_counts = figure_cross_cohort(person_series)
    dynamics = figure_participant_dynamics(person_series)
    figure_theme_heatmap()
    birth_counts = figure_birth_year_coverage(person_series)
    closedness_rows = figure_closedness_forest()
    geography = figure_geographic_gravity()
    affiliation_summary = figure_affiliation_transparency()
    era_l2_rows = figure_zograf_era_l2()
    write_notes(cross_counts, dynamics, birth_counts, closedness_rows, geography, affiliation_summary, era_l2_rows)
    print(f"Wrote figures to {OUT}")


if __name__ == "__main__":
    main()
