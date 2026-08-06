"""The six core comparison figures (H1899, Wave 1E), drawn from FROZEN tables.

Figures are generated as hand-written SVG — the same convention as
`article/make_ppv_figures.py`, and the only way to keep byte-identical
regeneration (no plotting-library version string, no embedded creation date).

Two rules bind every figure here:

1. **Read the CSV, never the database.** A figure that re-queried the live
   build could silently disagree with the numbers a reader checks in
   `analytics_output/community_lenses/tables/`.
2. **Every panel and caption states lens, native unit, period, denominator and
   coverage caveat.** A lens whose coverage is `unavailable` is drawn as a
   NAMED GAP panel, never as a zero bar, and a `pilot`/`partial` lens carries
   its status inside the panel title.

Roerich/Zograf (the `conferences` lens) is the article's primary object and is
always drawn first, in the emphasis colour, at full width.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from . import metrics

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "figures"
CAPTIONS_PATH = FIGURES_DIR / "captions.md"
CAPTIONS_JSON = FIGURES_DIR / "captions.json"

FIGURE_VERSION = "h1899-figures-1.0.0"

LENS_LABEL = {
    "conferences": "Рериховские/Зографские чтения (conferences)",
    "nagari": "nagari (закрытая Google-группа)",
    "vk_ors": "ORS/VK (стена сообщества)",
    "indology_l": "INDOLOGY-L",
    "bvp": "BVP (Bharatiya Vidvat Parishad)",
}
LENS_ORDER = ("conferences", "nagari", "vk_ors", "indology_l", "bvp")

EMPHASIS = "#123a6b"      # conferences — the primary object
SECONDARY = "#6b8fbc"     # other observable lenses
PILOT = "#b0824a"         # pilot/partial coverage
GAP = "#9a9a9a"           # unavailable lens: a named gap, never a zero
BG = "#ffffff"
GRID = "#d8d8d8"
INK = "#1b1b1b"

FIGURE_IDS = (
    "fig1_activity_by_period",
    "fig2_intellectual_content",
    "fig3_community_function",
    "fig4_argument_level",
    "fig5_person_overlap",
    "fig6_orientation_contrast",
)


class FigureError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Minimal deterministic SVG primitives
# ---------------------------------------------------------------------------

def _svg_open(width: int, height: int, title: str, desc: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
        f"<title id=\"t\">{escape(title)}</title>",
        f"<desc id=\"d\">{escape(desc)}</desc>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{BG}"/>',
    ]


def _text(x: float, y: float, content: str, size: int = 12, weight: str = "normal",
          anchor: str = "start", fill: str = INK) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'fill="{fill}">{escape(content)}</text>'
    )


def _rect(x: float, y: float, w: float, h: float, fill: str) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" fill="{fill}"/>'


def _line(x1: float, y1: float, x2: float, y2: float, stroke: str = GRID) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="1"/>'


def _lens_colour(coverage_status: str, lens: str) -> str:
    if coverage_status == "unavailable":
        return GAP
    if coverage_status in metrics.NON_POPULATION_COVERAGE:
        return PILOT
    return EMPHASIS if lens == "conferences" else SECONDARY


def _panel_title(lens: str, unit: str, coverage: str, denominator: str, denominator_name: str) -> str:
    status = {"complete": "полное покрытие", "pilot": "PILOT", "partial": "PARTIAL",
              "unavailable": "НЕТ ДАННЫХ"}.get(coverage, coverage)
    return f"{LENS_LABEL.get(lens, lens)} · ед. = {unit} · {status} · N({denominator_name})={denominator or '—'}"


def _gap_panel(x: float, y: float, width: float, height: float, lens: str, note: str) -> list[str]:
    return [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'fill="none" stroke="{GAP}" stroke-width="1" stroke-dasharray="5 4"/>',
        _text(x + width / 2, y + height / 2 - 4, f"{LENS_LABEL.get(lens, lens)}: НЕТ НАБЛЮДЕНИЯ",
              size=12, weight="bold", anchor="middle", fill=GAP),
        _text(x + width / 2, y + height / 2 + 13, note[:110], size=10, anchor="middle", fill=GAP),
    ]


# ---------------------------------------------------------------------------
# Figure 1 — activity by native unit and period
# ---------------------------------------------------------------------------

def figure_activity(tables: dict[str, list[dict]]) -> tuple[str, str]:
    rows = tables["activity_by_period"]
    coverage = {row["lens"]: row for row in tables["lens_source_coverage"]}
    lenses = [lens for lens in LENS_ORDER if any(r["lens"] == lens for r in rows)]
    gaps = [lens for lens in LENS_ORDER if lens not in lenses]

    periods = list(metrics.TREND_PERIODS)
    panel_h, gap_h, top = 150, 30, 96
    width = 1000
    height = top + len(lenses) * (panel_h + gap_h) + len(gaps) * 70 + 90

    out = _svg_open(
        width, height,
        "Рис. 1. Активность по родным единицам и периодам",
        "Small multiples: one panel per lens, each with its own native unit and "
        "its own denominator. Native units are never summed across lenses.",
    )
    out.append(_text(24, 34, "Рис. 1. Активность по периодам — каждая линза в своей родной единице", 16, "bold"))
    out.append(_text(24, 56, "Знаменатель у каждой панели свой (датированные записи этой линзы). "
                             "Единицы НЕ складываются между линзами.", 11))
    out.append(_text(24, 74, "Тренд — только 2005–2025; 2026 показан отдельной штриховой полосой как ЧАСТИЧНЫЙ.", 11))

    y = top
    for lens in lenses:
        lens_rows = {r["period"]: r for r in rows if r["lens"] == lens}
        trend = [lens_rows[p] for p in periods if p in lens_rows]
        partial = lens_rows.get(metrics.PARTIAL_PERIOD)
        info = coverage.get(lens, {})
        colour = _lens_colour(info.get("coverage_status", ""), lens)
        denominator = trend[0]["denominator"] if trend else ""
        out.append(_text(24, y - 6, _panel_title(
            lens, info.get("native_unit", ""), info.get("coverage_status", ""),
            denominator, "датированные записи"), 12, "bold"))

        counts = [int(r["numerator"] or 0) for r in trend]
        partial_count = int(partial["numerator"] or 0) if partial else 0
        peak = max(counts + [partial_count, 1])
        bar_w = (width - 120) / (len(counts) + 1.6)
        base = y + panel_h - 26
        out.append(_line(80, base, width - 30, base, INK))
        for index, (period, count) in enumerate(zip(periods, counts)):
            bar_h = (count / peak) * (panel_h - 52)
            x = 88 + index * bar_w
            out.append(_rect(x, base - bar_h, bar_w * 0.72, bar_h, colour))
            out.append(_text(x + bar_w * 0.36, base - bar_h - 5, str(count), 10, anchor="middle"))
            out.append(_text(x + bar_w * 0.36, base + 14, period, 9, anchor="middle"))
        if partial:
            x = 88 + len(counts) * bar_w
            bar_h = (partial_count / peak) * (panel_h - 52)
            out.append(
                f'<rect x="{x:.1f}" y="{base - bar_h:.1f}" width="{bar_w * 0.72:.1f}" '
                f'height="{bar_h:.1f}" fill="none" stroke="{colour}" stroke-width="1.5" '
                f'stroke-dasharray="4 3"/>'
            )
            out.append(_text(x + bar_w * 0.36, base - bar_h - 5, str(partial_count), 10, anchor="middle"))
            out.append(_text(x + bar_w * 0.36, base + 14, "2026 ЧАСТ.", 9, anchor="middle", fill=PILOT))
        out.append(_text(24, base, "0", 9, anchor="end"))
        y += panel_h + gap_h

    for lens in gaps:
        note = coverage.get(lens, {}).get("missingness", "источник недоступен")
        out.extend(_gap_panel(88, y - 10, width - 120, 54, lens, note))
        y += 70

    out.append(_text(24, height - 30,
                     "Числитель — записи линзы в периоде; знаменатель — датированные записи той же линзы. "
                     "Пунктир = pilot/частичное покрытие.", 10))
    out.append("</svg>")

    caption = (
        "Рис. 1. Активность по периодам, по одной панели на линзу. Родная единица: "
        + "; ".join(
            f"{LENS_LABEL.get(lens, lens)} — {coverage.get(lens, {}).get('native_unit', '?')}"
            for lens in lenses
        )
        + ". Период тренда 2005–2025 (бины ARCHITECTURE); 2026 показан отдельно как ЧАСТИЧНЫЙ "
          "и никогда не смешивается с годовыми темпами. Знаменатель каждой панели — "
          "датированные записи той же линзы; между линзами величины не складываются. "
        + ("Отсутствующие линзы: " + ", ".join(LENS_LABEL.get(l, l) for l in gaps) +
           " — явные пробелы наблюдения, а не нули. " if gaps else "")
        + "BVP: покрытие `unavailable`, поэтому ни один количественный тренд по BVP не показан."
    )
    return "\n".join(out) + "\n", caption


# ---------------------------------------------------------------------------
# Figures 2–4 — shared-axis small multiples
# ---------------------------------------------------------------------------

def _axis_figure(
    tables: dict[str, list[dict]],
    table_name: str,
    number: str,
    title_ru: str,
    subtitle_ru: str,
    axis_note: str,
) -> tuple[str, str]:
    rows = [r for r in tables[table_name] if str(r["value"]).strip()]
    empty = [r for r in tables[table_name] if not str(r["value"]).strip()]
    coverage = {row["lens"]: row for row in tables["lens_source_coverage"]}
    lenses = [lens for lens in LENS_ORDER if any(r["lens"] == lens for r in rows)]
    missing = [lens for lens in LENS_ORDER if lens not in lenses]

    panel_w, width = 470, 1000
    per_lens_rows = {lens: [r for r in rows if r["lens"] == lens] for lens in lenses}
    panel_heights = {lens: 46 + 20 * len(per_lens_rows[lens]) for lens in lenses}
    height = 110 + sum(panel_heights.values()) + 24 * len(lenses) + 40 * len(missing) + 70

    out = _svg_open(width, height, f"{number}. {title_ru}", axis_note)
    out.append(_text(24, 34, f"{number}. {title_ru}", 16, "bold"))
    out.append(_text(24, 56, subtitle_ru, 11))
    out.append(_text(24, 74, axis_note, 11))

    y = 104
    for lens in lenses:
        info = coverage.get(lens, {})
        lens_rows = sorted(per_lens_rows[lens], key=lambda r: -float(r["value"] or 0))
        denominator = lens_rows[0]["denominator"] if lens_rows else ""
        colour = _lens_colour(info.get("coverage_status", ""), lens)
        out.append(_text(24, y, _panel_title(lens, info.get("native_unit", ""),
                                             info.get("coverage_status", ""), denominator,
                                             "записи с этой осью"), 12, "bold"))
        y += 16
        for row in lens_rows:
            share = float(row["value"] or 0)
            label = row["metric_id"].split(".")[2]
            out.append(_text(28, y + 11, label[:34], 10))
            out.append(_rect(250, y + 2, share * panel_w, 12, colour))
            out.append(_text(254 + share * panel_w, y + 12,
                             f"{row['numerator']}/{row['denominator']} ({share:.1%})", 9))
            y += 20
        y += 24

    for lens in missing:
        reason = next((r["missingness"] for r in empty if r["lens"] == lens),
                      coverage.get(lens, {}).get("missingness", "нет данных"))
        out.extend(_gap_panel(28, y - 6, width - 60, 34, lens, reason))
        y += 40

    out.append(_text(24, height - 26,
                     "Доли считаются от записей ТОЙ ЖЕ линзы, размеченных по этой оси; "
                     "не от всех записей и не от суммы линз.", 10))
    out.append("</svg>")

    caption = (
        f"{number}. {title_ru}. Доля = записи с меткой / записи той же линзы, размеченные по этой оси "
        "(знаменатель указан в каждой панели). "
        + "; ".join(
            f"{LENS_LABEL.get(lens, lens)}: единица {coverage.get(lens, {}).get('native_unit', '?')}, "
            f"покрытие {coverage.get(lens, {}).get('coverage_status', '?')}"
            for lens in lenses
        )
        + ". " + axis_note
        + (" Линзы без данных по этой оси: " + ", ".join(LENS_LABEL.get(l, l) for l in missing) +
           " — пробел наблюдения, не ноль." if missing else "")
    )
    return "\n".join(out) + "\n", caption


def figure_intellectual_content(tables) -> tuple[str, str]:
    return _axis_figure(
        tables, "intellectual_content_by_lens", "Рис. 2",
        "Интеллектуальное содержание — малые кратные по линзам",
        "Общая ось получена через кроссволк H1897; каждая метка — ДОПОЛНИТЕЛЬНОЕ утверждение "
        "рядом с родной меткой, review_status=pending.",
        "Кроссволк не принят человеком: доли — предложения, а не утверждённая классификация.",
    )


def figure_community_function(tables) -> tuple[str, str]:
    return _axis_figure(
        tables, "community_function_by_lens", "Рис. 3",
        "Профили общественной функции",
        "Функция сообщества по общей оси; знаменатель — записи линзы, размеченные по этой оси.",
        "Отсутствие оси у линзы означает, что кроссволк для её родного словаря не даёт "
        "функциональной проекции — сравнение по этой линзе подавлено.",
    )


def figure_argument_level(tables) -> tuple[str, str]:
    return _axis_figure(
        tables, "argument_level_by_lens", "Рис. 4",
        "Шкала Гумилёва (argument_level) на применимых записях",
        "Конференции — принятое существующее свидетельство; остальные линзы — детерминированный "
        "ПИЛОТ без человеческой проверки.",
        "Порог валидности V6 не проверен: межлинзовое распределение Гумилёва НЕ публикуется, "
        "пилотные доли приведены только как внутрилинзовая композиция.",
    )


# ---------------------------------------------------------------------------
# Figure 5 — verified cross-lens people
# ---------------------------------------------------------------------------

def figure_person_overlap(tables: dict[str, list[dict]]) -> tuple[str, str]:
    rows = tables["person_overlap"]
    coverage = {row["lens"]: row for row in tables["lens_source_coverage"]}
    lenses = [lens for lens in LENS_ORDER if any(r["lens"] == lens for r in rows)]
    missing = [lens for lens in LENS_ORDER if lens not in lenses]

    width, height = 1000, 150 + 46 * len(lenses) + 44 * len(missing) + 80
    out = _svg_open(width, height, "Рис. 5. Пересечение площадок по проверенным персонам",
                    "Only accepted identity links; ambiguous candidates are never counted.")
    out.append(_text(24, 34, "Рис. 5. Проверенные персоны, засвидетельствованные более чем в одной линзе", 16, "bold"))
    out.append(_text(24, 56, "Учитываются ТОЛЬКО принятые связи личности; неоднозначные кандидаты "
                             "не входят ни в один счёт.", 11))
    out.append(_text(24, 74, "Знаменатель — персоны, связанные внутри той же линзы.", 11))

    y = 110
    scale = 620
    peak = max([int(r["denominator"] or 0) for r in rows] + [1])
    for lens in lenses:
        row = next(r for r in rows if r["lens"] == lens)
        info = coverage.get(lens, {})
        colour = _lens_colour(info.get("coverage_status", ""), lens)
        linked = int(row["denominator"] or 0)
        cross = int(row["numerator"] or 0)
        out.append(_text(24, y + 12, LENS_LABEL.get(lens, lens)[:38], 11))
        out.append(_rect(300, y + 2, (linked / peak) * scale, 14, SECONDARY))
        out.append(_rect(300, y + 2, (cross / peak) * scale, 14, colour))
        out.append(_text(306 + (linked / peak) * scale, y + 13,
                         f"кросс-линзовых {cross} из {linked} связанных персон", 9))
        y += 46

    for lens in missing:
        out.extend(_gap_panel(300, y - 4, scale, 32, lens,
                              coverage.get(lens, {}).get("missingness", "источник недоступен")))
        y += 44

    out.append(_text(24, height - 40,
                     "Тёмная часть столбца — персоны с принятой межлинзовой связью; светлая — все "
                     "связанные персоны линзы.", 10))
    out.append(_text(24, height - 24,
                     "Связи выведены из членства в ЗАКРЫТОЙ группе: именные межплощадочные "
                     "утверждения не экспортируются до одобрения прав nagari.", 10))
    out.append("</svg>")

    excluded = rows[0]["missingness"] if rows else ""
    lens_units = "; ".join(
        f"{LENS_LABEL.get(lens, lens)}: родная единица {coverage.get(lens, {}).get('native_unit', '?')}, "
        f"покрытие {coverage.get(lens, {}).get('coverage_status', '?')}"
        for lens in lenses
    )
    caption = (
        "Рис. 5. Проверенные межлинзовые персоны. " + lens_units + ". "
        "Числитель — персоны с ПРИНЯТОЙ связью, "
        "засвидетельствованные в данной линзе; знаменатель — все персоны, связанные внутри "
        "той же линзы (единица — персона). " + excluded + ". Неоднозначные кандидаты исключены "
        "по построению; ни одна связь не принята автоматически. Совпадение площадок не является "
        "утверждением о миграции сообщества."
    )
    return "\n".join(out) + "\n", caption


# ---------------------------------------------------------------------------
# Figure 6 — Russia / West / India orientation contrast
# ---------------------------------------------------------------------------

ORIENTATION_RU = {
    "russia_centred": "Россия-центричные площадки",
    "western_centred": "Западно-центричные площадки",
    "india_centred": "Индия-центричные площадки",
}


def figure_orientation(tables: dict[str, list[dict]]) -> tuple[str, str]:
    rows = tables["orientation_contrast"]
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(metrics.LENS_ORIENTATION[row["lens"]], []).append(row)

    width = 1000
    height = 130 + sum(40 + 26 * len(v) for v in grouped.values()) + 90
    out = _svg_open(width, height, "Рис. 6. Контраст ориентаций площадок",
                    "Forum orientation is a corpus-selection premise (expert judgment), "
                    "never a nationality claim and never a representativeness claim.")
    out.append(_text(24, 34, "Рис. 6. Россия / Запад / Индия — ОРИЕНТАЦИЯ ПЛОЩАДОК, не национальность", 16, "bold"))
    out.append(_text(24, 56, "Метка ориентации — посылка отбора корпуса (экспертное суждение автора); "
                             "p-значения к ней не применяются.", 11))
    out.append(_text(24, 74, "Показано наблюдаемое покрытие каждой площадки, а не доля сообщества.", 11))

    y = 112
    for orientation in ("russia_centred", "western_centred", "india_centred"):
        entries = grouped.get(orientation, [])
        out.append(_text(24, y, ORIENTATION_RU[orientation], 13, "bold"))
        y += 20
        for row in entries:
            observable = str(row["numerator"]).strip()
            colour = _lens_colour(row["coverage_status"], row["lens"])
            if observable:
                out.append(_text(40, y + 12, LENS_LABEL.get(row["lens"], row["lens"])[:40], 10))
                out.append(_rect(320, y + 2, min(int(observable) / 20000 * 560, 560), 12, colour))
                out.append(_text(326 + min(int(observable) / 20000 * 560, 560), y + 12,
                                 f"{observable} × {row['native_unit']} · {row['coverage_status']}", 9))
            else:
                out.append(_text(40, y + 12, LENS_LABEL.get(row["lens"], row["lens"])[:40], 10, fill=GAP))
                out.append(_text(320, y + 12, "НЕТ НАБЛЮДЕНИЯ — источник недоступен (пробел, не ноль)",
                                 10, fill=GAP))
            y += 26
        y += 20

    out.append(_text(24, height - 46,
                     "Западная и индийская ориентации в этом снимке НЕ наблюдаемы: INDOLOGY-L "
                     "заблокирован на H1894, BVP — на H1896.", 10))
    out.append(_text(24, height - 28,
                     "Поэтому никакого сравнения «Россия против Запада и Индии» по величинам "
                     "здесь не делается: это зафиксированный пробел доказательств.", 10))
    out.append("</svg>")

    caption = (
        "Рис. 6. Контраст ориентаций площадок. Ориентация описывает ФОРУМ (посылка отбора корпуса, "
        "экспертное суждение), а не гражданство участников; она не несёт p-значения и не претендует "
        "на репрезентативность России, «Запада» или Индии. Числитель — наблюдаемые записи "
        "площадки; знаменатель — записи снимка ТОЙ ЖЕ линзы (доля сообщества не вычисляется). "
        "В текущем снимке наблюдаемы только "
        "Россия-центричные площадки (conferences — presentation; nagari — message, PILOT; "
        "vk_ors — post); западная (INDOLOGY-L) и индийская (BVP) ориентации отсутствуют как "
        "источники и показаны явными пробелами наблюдения, а не нулями."
    )
    return "\n".join(out) + "\n", caption


# ---------------------------------------------------------------------------
# Build / write
# ---------------------------------------------------------------------------

BUILDERS = {
    "fig1_activity_by_period": figure_activity,
    "fig2_intellectual_content": figure_intellectual_content,
    "fig3_community_function": figure_community_function,
    "fig4_argument_level": figure_argument_level,
    "fig5_person_overlap": figure_person_overlap,
    "fig6_orientation_contrast": figure_orientation,
}


def build_all(tables: dict[str, list[dict]]) -> dict[str, tuple[str, str]]:
    return {figure_id: BUILDERS[figure_id](tables) for figure_id in FIGURE_IDS}


def write_all(
    tables: dict[str, list[dict]] | None = None,
    directory: Path = FIGURES_DIR,
    tables_dir: Path = metrics.TABLES_DIR,
) -> list[Path]:
    if tables is None:
        tables = {name: metrics.read_table(name, tables_dir) for name in metrics.TABLE_NAMES}
    built = build_all(tables)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    captions: dict[str, str] = {}
    for figure_id in FIGURE_IDS:
        svg, caption = built[figure_id]
        path = directory / f"{figure_id}.svg"
        path.write_text(svg, encoding="utf-8")
        captions[figure_id] = caption
        written.append(path)

    lines = [
        "# Подписи к рисункам — пятилинзовое сравнение (H1899)",
        "",
        "_Created: 06-08-2026 · Last updated: 06-08-2026_",
        "",
        f"Сгенерировано `community_lenses/figures.py` ({FIGURE_VERSION}) из замороженных таблиц "
        "`analytics_output/community_lenses/tables/`. Каждая подпись называет линзу, родную "
        "единицу, период, знаменатель и оговорку о покрытии.",
        "",
    ]
    for figure_id in FIGURE_IDS:
        lines.append(f"## {figure_id}")
        lines.append("")
        lines.append(captions[figure_id])
        lines.append("")
    lines.append("_Dr. Mārcis Gasūns_")
    CAPTIONS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CAPTIONS_JSON.write_text(
        json.dumps(captions, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.extend([CAPTIONS_PATH, CAPTIONS_JSON])
    return written


def validate_captions(captions: dict[str, str], tables: dict[str, list[dict]]) -> list[str]:
    """V10: every caption states lens, native unit, period/denominator and a coverage caveat."""
    errors: list[str] = []
    units = {row["native_unit"] for row in tables["lens_source_coverage"] if row["native_unit"]}
    for figure_id, caption in sorted(captions.items()):
        if not any(unit in caption for unit in units):
            errors.append(f"{figure_id}: caption names no native unit")
        if "знаменател" not in caption.lower() and "Числитель" not in caption:
            errors.append(f"{figure_id}: caption states no denominator")
        if not any(word in caption for word in ("покрыти", "PILOT", "пробел", "unavailable", "ЧАСТИЧН")):
            errors.append(f"{figure_id}: caption carries no coverage caveat")
        if "bvp" not in caption.lower() and "BVP" not in caption:
            # Only figures that involve lens comparison must show BVP status.
            if figure_id in ("fig1_activity_by_period", "fig6_orientation_contrast"):
                errors.append(f"{figure_id}: BVP completeness status not visible")
    return errors


def main() -> int:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    tables = {name: metrics.read_table(name) for name in metrics.TABLE_NAMES}
    written = write_all(tables)
    captions = json.loads(CAPTIONS_JSON.read_text(encoding="utf-8"))
    errors = validate_captions(captions, tables)
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    if errors:
        print(f"\nV10 caption validation FAILED with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("\nV10 caption validation: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
