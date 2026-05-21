from __future__ import annotations

import csv
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
ANALYTICS = ROOT / "analytics_output"
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
        text(34, 32, "Рис. 4. Перекрестная когорта: баланс участия на двух площадках", "title"),
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
        text(34, 32, "Рис. 1. Обновление состава: новички, ядро и повторные участники", "title"),
        text(34, 56, "Столбцы показывают структуру участников по годам; линия — долю дебютантов.", "subtitle"),
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

        bar_w = plot_w / (xmax - xmin + 1) * 0.68
        prev_line = None
        for row in rows:
            x = left + (row["year"] - xmin + 0.5) / (xmax - xmin + 1) * plot_w
            bottom = top + plot_h
            for key in ["new", "repeat", "core"]:
                h = row[key] / max_total * plot_h
                body.append(rect(x - bar_w / 2, bottom - h, bar_w, h, colors[key]))
                bottom -= h
            line_y = top + plot_h - (row["newcomer_pct"] / 100) * plot_h
            if prev_line:
                body.append(line(prev_line[0], prev_line[1], x, line_y, "#8a4f7d", 2.2))
            body.append(circle(x, line_y, 3.5, "#8a4f7d"))
            prev_line = (x, line_y)

        for year in range(xmin, xmax + 1, 2):
            x = left + (year - xmin + 0.5) / (xmax - xmin + 1) * plot_w
            body.append(text(x, top + plot_h + 22, year, "axis", "middle"))
        body.append(rotated_text(left - 58, top + plot_h / 2, "участников", cls="small"))
        body.append(rotated_text(left + plot_w + 64, top + plot_h / 2, "доля новичков", angle=90, cls="small"))

    legend_y = 690
    legend = [
        ("новички", colors["new"]),
        ("прочие повторные", colors["repeat"]),
        ("ядро ≥5 докладов", colors["core"]),
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
        x += 210

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
        text(34, 32, "Рис. 3. Тематическая матрица L1 × L2", "title"),
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
    ymax = max(max(c.values()) for c in counts.values()) + 10
    body = [
        text(34, 32, "Рис. 2. Покрытие годом рождения зависит от частоты участия", "title"),
        text(34, 56, "Неизвестные годы рождения сконцентрированы среди разовых и редких участников.", "subtitle"),
        rect(left, top, plot_w, plot_h, "#ffffff", "#cfd8e3"),
    ]
    for y in range(0, ymax + 1, 20):
        yy = top + plot_h - y / ymax * plot_h
        body.append(line(left, yy, left + plot_w, yy, "#edf1f5"))
        body.append(text(left - 12, yy + 4, y, "axis", "end"))

    group_w = plot_w / len(buckets)
    bar_w = group_w * 0.28
    colors = {"known": "#2f6fbb", "unknown": "#b8554b"}
    for i, (label, _) in enumerate(buckets):
        cx = left + group_w * (i + 0.5)
        for j, group in enumerate(["known", "unknown"]):
            val = counts[group][label]
            h = val / ymax * plot_h
            x = cx + (j - 0.5) * bar_w * 1.25
            body.append(rect(x - bar_w / 2, top + plot_h - h, bar_w, h, colors[group]))
            body.append(text(x, top + plot_h - h - 6, val, "small", "middle"))
        body.append(text(cx, top + plot_h + 26, label, "axis", "middle"))
    body.append(text(left + plot_w / 2, height - 48, "Всего докладов/авторских участий у ученого", "axis", "middle"))
    body.append(text(left - 54, top + plot_h / 2, "ученых", "small", "middle"))

    legend_x, legend_y = 560, 110
    body.append(rect(legend_x - 16, legend_y - 24, 220, 78, "#ffffff", "#d8e0e8", 5, 0.94))
    body.append(rect(legend_x, legend_y - 10, 24, 14, colors["known"]))
    body.append(text(legend_x + 34, legend_y + 2, "год рождения известен", "small"))
    body.append(rect(legend_x, legend_y + 20, 24, 14, colors["unknown"]))
    body.append(text(legend_x + 34, legend_y + 32, "год рождения неизвестен", "small"))

    (OUT / "birth_year_coverage.svg").write_text(svg(width, height, body), encoding="utf-8")
    return counts


def write_notes(
    cross_counts: dict[str, int],
    dynamics: dict[str, list[dict[str, float]]],
    birth_counts: dict[str, Counter[str]],
) -> None:
    z2020 = next(r for r in dynamics["Zograf"] if r["year"] == 2020)
    z2021 = next(r for r in dynamics["Zograf"] if r["year"] == 2021)
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
    ]
    (OUT / "figure_notes.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    person_series = load_person_series()
    cross_counts = figure_cross_cohort(person_series)
    dynamics = figure_participant_dynamics(person_series)
    figure_theme_heatmap()
    birth_counts = figure_birth_year_coverage(person_series)
    write_notes(cross_counts, dynamics, birth_counts)
    print(f"Wrote figures to {OUT}")


if __name__ == "__main__":
    main()
