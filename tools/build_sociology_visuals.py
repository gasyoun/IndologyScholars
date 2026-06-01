"""Build static SVG visuals for sociology and gatekeeping pages."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "img"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2004, 2027))
BG = "#101513"
PANEL = "#17201c"
BORDER = "#304139"
TEXT = "#eef6f0"
MUTED = "#a8b7ae"
SOFT = "#7f9187"
ACCENT = "#7ccf9b"
BLUE = "#76a9ff"
ORANGE = "#f6b352"
RED = "#f87171"
PURPLE = "#c084fc"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_svg(path: str, width: int, height: int, body: str) -> None:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<rect width="{width}" height="{height}" fill="{BG}"/>
{body}
</svg>
"""
    (OUT / path).write_text(svg, encoding="utf-8", newline="\n")


def label(x: float, y: float, text: str, size: int = 14, color: str = TEXT, weight: int = 400, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{esc(text)}</text>'
    )


def pill(x: float, y: float, text: str, color: str, width: int | None = None) -> str:
    w = width or max(94, len(text) * 7 + 24)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="24" rx="8" fill="{color}" opacity="0.18"/>'
        f'<text x="{x + 12}" y="{y + 16}" fill="{color}" font-family="Inter, Arial, sans-serif" '
        f'font-size="12" font-weight="700">{esc(text)}</text>'
    )


def load_scholars() -> list[dict]:
    return json.loads((ROOT / "site_data_scholars.json").read_text(encoding="utf-8"))


def build_senior_absence_timeline() -> None:
    scholars = {row["id"]: row for row in load_scholars()}
    audit = read_csv("analytics_output/senior_absence_audit.csv")
    bio = {row["person_id"]: row for row in read_csv("curation/senior_biographical_verification.csv")}
    cohorts: dict[str, set[str]] = defaultdict(set)
    for row in audit:
        cohorts[row["person_id"]].add(row["cohort"])

    people = []
    for pid, flags in cohorts.items():
        scholar = scholars.get(pid)
        if not scholar:
            continue
        order = 0 if "absent_after_2022" in flags else 1
        people.append((order, int(scholar.get("last_year") or 0), scholar["full_name_ru"], pid, flags))
    people.sort(key=lambda item: (item[0], item[1], item[2]))

    left = 290
    top = 88
    cell = 34
    row_h = 38
    width = left + len(YEARS) * cell + 210
    height = top + len(people) * row_h + 88
    parts = [
        label(28, 34, "Частые участники старшего поколения: видимость в архиве", 24, TEXT, 800),
        label(28, 58, "Точки показывают годы с докладами; серые зоны отделяют пост-2022 контекст и программу 2026 года.", 14, MUTED),
    ]

    for idx, year in enumerate(YEARS):
        x = left + idx * cell
        fill = "#23332c" if year >= 2023 else "#17201c"
        if year == 2026:
            fill = "#392222"
        parts.append(f'<rect x="{x}" y="{top - 28}" width="{cell - 2}" height="{len(people) * row_h + 26}" fill="{fill}" opacity="0.85"/>')
        if idx % 2 == 0 or year in (2022, 2026):
            parts.append(label(x + 15, top - 10, str(year), 11, SOFT, 600, "middle"))

    parts.append(pill(left + (2023 - YEARS[0]) * cell, top - 58, "после 2022", ACCENT, 118))
    parts.append(pill(left + (2026 - YEARS[0]) * cell, top - 58, "2026", RED, 70))
    parts.append(label(left + len(YEARS) * cell + 22, top - 10, "Внешняя проверка", 12, SOFT, 700))

    for r, (_order, _last, name, pid, flags) in enumerate(people):
        y = top + r * row_h
        scholar = scholars[pid]
        bio_row = bio.get(pid, {})
        status = bio_row.get("external_status", "review")
        group_color = ACCENT if "absent_after_2022" in flags else RED
        if flags == {"absent_in_2026"}:
            group_label = "2026"
        elif "absent_after_2022" in flags and "absent_in_2026" in flags:
            group_label = "post-2022 + 2026"
        else:
            group_label = "post-2022"

        parts.append(f'<line x1="28" y1="{y + 18}" x2="{width - 30}" y2="{y + 18}" stroke="{BORDER}" stroke-width="1" opacity="0.45"/>')
        parts.append(label(28, y + 13, name, 13, TEXT, 650))
        parts.append(label(28, y + 31, f"{scholar.get('birth_year') or '?'}; last {scholar.get('last_year')}", 11, MUTED))
        parts.append(pill(190, y - 3, group_label, group_color, 86 if group_label == "2026" else 132))

        year_series: dict[int, set[str]] = defaultdict(set)
        for talk in scholar.get("talks", []):
            year = int(talk.get("year") or 0)
            if year in YEARS:
                year_series[year].add(talk.get("series") or "")
        for idx, year in enumerate(YEARS):
            x = left + idx * cell + 16
            if year in year_series:
                series = year_series[year]
                color = ORANGE if len(series) > 1 else (BLUE if "Zograf Readings" in series else ACCENT)
                parts.append(f'<circle cx="{x}" cy="{y + 17}" r="6.5" fill="{color}"/>')
            else:
                parts.append(f'<circle cx="{x}" cy="{y + 17}" r="2" fill="{BORDER}" opacity="0.75"/>')
        status_text = {
            "active_or_current_profile": "active profile",
            "external_activity_after_2022": "active after 2022",
            "biographical_profile_no_death_marker": "bio source",
            "needs_stronger_biographical_source": "needs source",
        }.get(status, status)
        status_color = RED if "needs" in status else ACCENT
        parts.append(pill(left + len(YEARS) * cell + 18, y + 5, status_text, status_color, 138))

    parts.append(label(28, height - 36, "Смысл: отсутствие в программе и биографический статус разведены. Пост-2022 и 2026 читаются как разные проверочные гипотезы.", 13, MUTED))
    parts.append(label(28, height - 16, "Цвет точек: Зографские чтения, Рериховские чтения, обе площадки в один год.", 12, SOFT))
    write_svg("senior_absence_timeline.svg", width, height, "\n".join(parts))


def build_generation_lifecycle() -> None:
    scholars = load_scholars()
    first_bins = [(2004, 2010, "2004-2010"), (2011, 2016, "2011-2016"), (2017, 2022, "2017-2022"), (2023, 2026, "2023-2026")]
    last_bins = [(2004, 2010, "last 2004-2010"), (2011, 2016, "last 2011-2016"), (2017, 2022, "last 2017-2022"), (2023, 2026, "last 2023-2026")]
    matrix = Counter()
    for s in scholars:
        first = int(s.get("first_year") or 0)
        last = int(s.get("last_year") or 0)
        fb = next((label_ for lo, hi, label_ in first_bins if lo <= first <= hi), None)
        lb = next((label_ for lo, hi, label_ in last_bins if lo <= last <= hi), None)
        if fb and lb:
            matrix[(fb, lb)] += 1
    max_value = max(matrix.values()) if matrix else 1
    width, height = 930, 430
    left, top = 210, 105
    cell_w, cell_h = 150, 60
    parts = [
        label(28, 34, "Жизненный цикл присутствия в конференционном архиве", 24, TEXT, 800),
        label(28, 58, "Сколько участников впервые появились в одном периоде и когда последний раз видны в корпусе.", 14, MUTED),
    ]
    for c, (_lo, _hi, fb) in enumerate(first_bins):
        parts.append(label(left + c * cell_w + cell_w / 2, top - 18, fb, 12, MUTED, 700, "middle"))
    for r, (_lo, _hi, lb) in enumerate(last_bins):
        parts.append(label(28, top + r * cell_h + 35, lb, 12, MUTED, 700))
    for r, (_lo, _hi, lb) in enumerate(last_bins):
        for c, (_flo, _fhi, fb) in enumerate(first_bins):
            value = matrix[(fb, lb)]
            intensity = 0.12 + 0.75 * (value / max_value)
            x = left + c * cell_w
            y = top + r * cell_h
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 8}" rx="8" fill="{ACCENT}" opacity="{intensity:.2f}"/>')
            parts.append(label(x + cell_w / 2 - 4, y + 34, str(value), 20, TEXT, 800, "middle"))
    parts.append(label(28, height - 44, "Читать по строкам и столбцам: верхний правый угол — быстро исчезнувшие ранние участники; нижний правый — новые участники, видимые сейчас.", 13, MUTED))
    parts.append(label(28, height - 22, "Это не биография, а только наблюдаемое присутствие в двух конференционных сериях.", 12, SOFT))
    write_svg("sociology_generation_lifecycle.svg", width, height, "\n".join(parts))


def build_review_dashboard() -> None:
    coauthors = len(read_csv("analytics_output/coauthorship_review.csv"))
    absence = len(read_csv("analytics_output/senior_absence_audit.csv"))
    bio = len(read_csv("curation/senior_biographical_verification.csv"))
    robustness = len(read_csv("analytics_output/network_robustness_checks.csv"))
    items = [
        ("Соавторства", coauthors, "строк с несколькими именами", BLUE),
        ("Отсутствия", absence, "старших участников в очереди", RED),
        ("Биографии", bio, "внешних проверок", ACCENT),
        ("Сети", robustness, "моделей/ограничений", ORANGE),
    ]
    width, height = 920, 290
    parts = [
        label(28, 34, "Где нужен человек", 24, TEXT, 800),
        label(28, 58, "Эта панель отделяет вычисления от мест, где нужен редакторский или биографический контроль.", 14, MUTED),
    ]
    card_w = 204
    for i, (title, value, subtitle, color) in enumerate(items):
        x = 28 + i * (card_w + 16)
        y = 92
        parts.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="128" rx="10" fill="{PANEL}" stroke="{BORDER}"/>')
        parts.append(label(x + 18, y + 30, title, 15, TEXT, 750))
        parts.append(label(x + 18, y + 76, str(value), 38, color, 800))
        parts.append(label(x + 18, y + 104, subtitle, 12, MUTED))
    parts.append(pill(28, 242, "review-first", RED, 112))
    parts.append(label(156, 258, "Страница должна показывать не только вывод, но и очередь человеческой проверки.", 13, MUTED))
    write_svg("sociology_review_dashboard.svg", width, height, "\n".join(parts))


def build_hypothesis_matrix() -> None:
    rows = [
        ("Политический / трансграничный контекст", "сильная гипотеза", "не главный механизм"),
        ("Локальные личные отношения и программная селекция", "требует осторожности", "сильная гипотеза"),
        ("Биографический уход / смерть", "проверять внешне", "проверять внешне"),
        ("Активность вне архива", "ищем подтверждения", "критически важно"),
        ("Ошибка корпуса / неполная программа", "контроль данных", "контроль данных"),
    ]
    width, height = 980, 430
    left, top = 330, 100
    col_w, row_h = 280, 54
    parts = [
        label(28, 34, "Две разные гипотезы отсутствия", 24, TEXT, 800),
        label(28, 58, "Пост-2022 исчезновения и кейс 2026 года не должны объясняться одним механизмом.", 14, MUTED),
        label(left + col_w / 2, top - 24, "После 2022", 15, ACCENT, 800, "middle"),
        label(left + col_w + col_w / 2, top - 24, "Программа 2026", 15, RED, 800, "middle"),
    ]
    color_map = {
        "сильная гипотеза": ACCENT,
        "не главный механизм": SOFT,
        "требует осторожности": ORANGE,
        "проверять внешне": BLUE,
        "ищем подтверждения": BLUE,
        "критически важно": RED,
        "контроль данных": PURPLE,
    }
    for r, (topic, after, in2026) in enumerate(rows):
        y = top + r * row_h
        parts.append(label(28, y + 32, topic, 13, TEXT, 650))
        for c, value in enumerate([after, in2026]):
            x = left + c * col_w
            color = color_map[value]
            parts.append(f'<rect x="{x}" y="{y}" width="{col_w - 12}" height="{row_h - 10}" rx="9" fill="{color}" opacity="0.18" stroke="{color}" stroke-opacity="0.35"/>')
            parts.append(label(x + 18, y + 29, value, 13, color, 750))
    parts.append(label(28, height - 38, "Смысл для рецензента: gatekeeping-гипотеза становится сильнее только после исключения биографических и внешне-активностных альтернатив.", 13, MUTED))
    write_svg("gatekeeping_hypothesis_matrix.svg", width, height, "\n".join(parts))


def build_network_layers() -> None:
    rows = read_csv("analytics_output/network_robustness_checks.csv")
    rows = [r for r in rows if r.get("edge_types_included") != "all"]
    width, height = 980, 430
    left, top = 315, 88
    max_edges = max(int(r["current_edge_count"]) for r in rows) if rows else 1
    parts = [
        label(28, 34, "Сеть не одна: разные типы связи дают разные вопросы", 24, TEXT, 800),
        label(28, 58, "Одинаковый графический язык не должен смешивать совместный доклад, одну сессию, тему и институцию.", 14, MUTED),
    ]
    row_h = 38
    for i, r in enumerate(rows):
        y = top + i * row_h
        model = r["network_model"].replace("_", " ")
        edge_type = r["edge_types_included"]
        count = int(r["current_edge_count"])
        bar_w = 520 * (count / max_edges)
        color = [BLUE, ACCENT, ORANGE, RED, PURPLE, "#60a5fa", "#f472b6"][i % 7]
        parts.append(label(28, y + 19, model, 13, TEXT, 650))
        parts.append(label(180, y + 19, edge_type, 11, MUTED))
        parts.append(f'<rect x="{left}" y="{y + 4}" width="530" height="24" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="24" rx="8" fill="{color}" opacity="0.78"/>')
        parts.append(label(left + 544, y + 21, str(count), 12, TEXT, 700))
    parts.append(label(28, height - 46, "Выводы о гейткипинге должны переживать проверку на тип связи: co-presentation, co-session, person-event, person-theme и др.", 13, MUTED))
    parts.append(label(28, height - 24, "Иначе визуально убедительная сеть может отвечать не на тот вопрос.", 12, SOFT))
    write_svg("gatekeeping_network_layers.svg", width, height, "\n".join(parts))


def main() -> None:
    build_senior_absence_timeline()
    build_generation_lifecycle()
    build_review_dashboard()
    build_hypothesis_matrix()
    build_network_layers()
    print("Built sociology/gatekeeping SVG visuals.")


if __name__ == "__main__":
    main()
