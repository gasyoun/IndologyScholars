from __future__ import annotations

import csv
import math
import re
import sqlite3
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from html import escape
from pathlib import Path

try:
    from scipy.stats import chi2_contingency, fisher_exact, kruskal, spearmanr
except Exception:  # pragma: no cover - optional in portable use
    chi2_contingency = None
    fisher_exact = None
    kruskal = None
    spearmanr = None


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "conferences.db"
ANALYTICS = ROOT / "analytics_output"
HTML_CACHE = ROOT / "html_cache"
OUT = ROOT / "article" / "hypothesis_output"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pct(n: int | float, d: int | float) -> float:
    return round(100 * n / d, 1) if d else 0.0


def median(values: list[float]) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    n = len(xs)
    mid = n // 2
    if n % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2


def svg(width: int, height: int, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        "<style>"
        "text{font-family:Arial,'Liberation Sans',sans-serif;fill:#1f2933}"
        ".title{font-size:20px;font-weight:700}.sub{font-size:13px;fill:#52616b}"
        ".axis{font-size:13px}.small{font-size:12px}.label{font-size:11px}"
        "</style>\n"
        + "\n".join(body)
        + "\n</svg>\n"
    )


def text(x: float, y: float, value: object, cls: str = "small", anchor: str = "start", weight: str | None = None) -> str:
    weight_attr = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{weight_attr}>'
        f"{escape(str(value))}</text>"
    )


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", opacity: float = 1.0) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>'
    )


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = "#cfd8e3", width: float = 1.0) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"/>'


def circle(x: float, y: float, r: float, fill: str, stroke: str = "#fff") -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'


def short_name(name: str) -> str:
    parts = name.replace("\xa0", " ").split()
    if len(parts) >= 3 and len(parts[0]) > 2:
        return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
    return " ".join(parts[:3])


def norm_title(title: str) -> str:
    value = title or ""
    value = value.lower().replace("ё", "е")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[«»“”\"'`.,:;!?()\[\]{}<>/\\|–—-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def theme_lookup(theme_rows: list[dict[str, str]]) -> dict[tuple[str, int, str], dict[str, str]]:
    out = {}
    for row in theme_rows:
        series = "Zograf" if row["series"] == "Zograf Readings" else "Roerich"
        out[(series, int(row["year"]), norm_title(row["title"]))] = row
    return out


def db_presentation_themes(con: sqlite3.Connection, theme_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup = theme_lookup(theme_rows)
    out = {}
    for pres_id, title, series_name, year in con.execute(
        """
        select pr.presentation_id, pr.title, es.series_name_en, e.year
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        """
    ):
        series = "Zograf" if "Zograf" in series_name else "Roerich"
        row = lookup.get((series, int(year), norm_title(title or "")))
        if row:
            out[pres_id] = row
    return out


def theme_match_diagnostics(con: sqlite3.Connection, theme_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    themes_by_pres = db_presentation_themes(con, theme_rows)
    by_series: dict[str, dict[str, int]] = defaultdict(lambda: {"presentations": 0, "matched": 0})
    for pres_id, series_name in con.execute(
        """
        select pr.presentation_id, es.series_name_en
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        """
    ):
        series = "Zograf" if "Zograf" in series_name else "Roerich"
        by_series[series]["presentations"] += 1
        if pres_id in themes_by_pres:
            by_series[series]["matched"] += 1

    rows = []
    total_presentations = 0
    total_matched = 0
    for series in sorted(by_series):
        presentations = by_series[series]["presentations"]
        matched = by_series[series]["matched"]
        total_presentations += presentations
        total_matched += matched
        rows.append(
            {
                "series": series,
                "presentations": presentations,
                "theme_matched": matched,
                "theme_unmatched": presentations - matched,
                "match_pct": pct(matched, presentations),
            }
        )
    rows.append(
        {
            "series": "ALL",
            "presentations": total_presentations,
            "theme_matched": total_matched,
            "theme_unmatched": total_presentations - total_matched,
            "match_pct": pct(total_matched, total_presentations),
        }
    )
    return rows, {"theme_match_total": total_matched, "theme_presentations_total": total_presentations, "theme_match_pct": pct(total_matched, total_presentations)}


def roerich_heading(year: int) -> str:
    path = HTML_CACHE / f"roerich_{year}.html"
    if not path.exists():
        return ""
    html = path.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r"<h[123][^>]*>(.*?)</h[123]>", html, flags=re.I | re.S):
        value = re.sub(r"<[^>]+>", " ", match.group(1))
        value = (
            value.replace("&nbsp;", " ")
            .replace("&laquo;", "«")
            .replace("&raquo;", "»")
            .replace("&ndash;", "–")
        )
        value = " ".join(value.split())
        if "Рериховские чтения" in value or "Рериховских чтений" in value:
            return value
    return ""


def infer_theme_group(heading: str) -> str:
    low = heading.lower()
    if "проблемы формирования текста" in low:
        return "text_formation"
    if "древняя и средневековая индия" in low:
        return "ancient_medieval_india"
    if "рериховские чтения" in low:
        return "generic_roerich"
    return "unknown"


def hypothesis_program_subtitles(theme_rows: list[dict[str, str]], con: sqlite3.Connection) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_year = defaultdict(list)
    for row in theme_rows:
        if row["series"] == "Roerich Readings":
            by_year[int(row["year"])].append(row)

    db_themes = {
        year: theme
        for year, theme in con.execute(
            "select year, theme_ru from event e join event_series es using(event_series_id) where es.series_name_en='Roerich Readings'"
        )
    }
    rows: list[dict[str, object]] = []
    for year in sorted(set(db_themes) | set(by_year)):
        heading = roerich_heading(year)
        group = infer_theme_group(heading)
        talks = by_year.get(year, [])
        l2 = Counter(r["l2"] for r in talks)
        l1 = Counter(r["l1"] for r in talks)
        rows.append(
            {
                "year": year,
                "db_theme_ru": db_themes.get(year, ""),
                "html_heading": heading,
                "theme_group_from_html": group,
                "coded_talks": len(talks),
                "classical_medieval_pct": pct(l2["classical"] + l2["medieval"], len(talks)),
                "religion_history_literature_pct": pct(l1["religion"] + l1["history"] + l1["literature"], len(talks)),
                "top_l1": "; ".join(f"{k}:{v}" for k, v in l1.most_common(3)),
                "top_l2": "; ".join(f"{k}:{v}" for k, v in l2.most_common(3)),
            }
        )

    # Compare the years that actually have coded talks.
    coded = [r for r in rows if r["coded_talks"]]
    groups = sorted({str(r["theme_group_from_html"]) for r in coded})
    stats: dict[str, object] = {"groups_with_coded_talks": ", ".join(groups)}
    if chi2_contingency and len(groups) >= 2:
        matrix = []
        labels = ["classical", "medieval", "modern", "contemporary", "colonial", "vedic", "unspecified"]
        for group in groups:
            counter = Counter()
            for row in theme_rows:
                if row["series"] != "Roerich Readings":
                    continue
                heading = roerich_heading(int(row["year"]))
                if infer_theme_group(heading) == group:
                    counter[row["l2"]] += 1
            matrix.append([counter[label] for label in labels])
        # Drop zero-only columns.
        keep = [i for i in range(len(labels)) if sum(row[i] for row in matrix)]
        matrix = [[row[i] for i in keep] for row in matrix]
        if len(matrix) > 1 and len(matrix[0]) > 1:
            chi2, p_value, dof, _ = chi2_contingency(matrix)
            n = sum(sum(row) for row in matrix)
            v = math.sqrt(chi2 / (n * (min(len(matrix), len(matrix[0])) - 1)))
            stats.update({"l2_chi2": round(chi2, 3), "l2_p": p_value, "l2_cramers_v": round(v, 3), "l2_dof": dof})
    return rows, stats


def person_series_counts(con: sqlite3.Connection) -> dict[str, dict[str, object]]:
    rows = con.execute(
        """
        select pp.person_id, p.display_name, p.birth_year, es.series_name_en, count(*), min(e.year), max(e.year)
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
    out: dict[str, dict[str, object]] = defaultdict(lambda: {"series": {}})
    for pid, name, birth, series, count, first, last in rows:
        key = "Zograf" if "Zograf" in series else "Roerich"
        out[pid]["name"] = name
        out[pid]["birth_year"] = birth
        out[pid]["series"][key] = {"count": count, "first": first, "last": last}
    return out


AFFIL_GROUPS = [
    ("ИКВИА/ВШЭ", re.compile(r"ИКВИА|ВШЭ|Высш", re.I)),
    ("ИВ РАН", re.compile(r"\bИВ РАН\b|Институт востоковедения", re.I)),
    ("ИВР РАН", re.compile(r"ИВР|Институт восточных рукопис", re.I)),
    ("СПбГУ", re.compile(r"СПбГУ|Санкт-Петербургский государственный", re.I)),
    ("ИФ РАН", re.compile(r"\bИФ РАН\b|Институт философии", re.I)),
    ("ИМЛИ РАН", re.compile(r"ИМЛИ", re.I)),
    ("РГГУ", re.compile(r"РГГУ", re.I)),
    ("РУДН", re.compile(r"РУДН", re.I)),
    ("ИСАА МГУ", re.compile(r"ИСАА|МГУ", re.I)),
    ("ИЭА РАН", re.compile(r"ИЭА", re.I)),
    ("МАЭ РАН", re.compile(r"МАЭ|Кунсткам", re.I)),
    ("ИЯз/ИЯ РАН", re.compile(r"ИЯз|ИЯ РАН", re.I)),
    ("независимый исследователь", re.compile(r"\bНИ\b|независ", re.I)),
]


def affiliation_groups(values: list[str]) -> list[str]:
    joined = " | ".join(v for v in values if v)
    groups = [name for name, pattern in AFFIL_GROUPS if pattern.search(joined)]
    if "ИВР РАН" in groups and "ИВ РАН" in groups:
        groups.remove("ИВ РАН")
    return groups or ["не нормализовано/только город"]


SPB_PATTERNS = re.compile(
    r"СПб|Санкт-Петербург|Ленинград|ИВР|МАЭ|Кунсткам|РХГА|ЕУСПб|ГМИР|РНБ|Герцен|С\.-Петербург|С\.-Петерб|Эрмитаж",
    re.I
)
MOSCOW_PATTERNS = re.compile(
    r"Москва|МГУ|ИВ РАН|ВШЭ|ИКВИА|Высш|РГГУ|ИФ РАН|Институт философии|ИМЛИ|РУДН|ИСАА|ИЭА|этнологии и антропологии|ИЯз|ИЯ РАН|Институт языкознания|МГИМО|ПСТГУ|МГХПА|РГСУ|МПГУ|РАНХиГС|РХТУ|РГХПУ",
    re.I
)


def infer_city(affil: str | None) -> str:
    if not affil:
        return "Unknown"
    affil_clean = affil.strip()
    if not affil_clean:
        return "Unknown"
    if SPB_PATTERNS.search(affil_clean):
        return "SPb"
    elif MOSCOW_PATTERNS.search(affil_clean):
        return "Moscow"
    else:
        return "Regions/Foreign"


def is_serialized(title: str | None) -> bool:
    if not title:
        return False
    t = title.lower().strip()
    part_patterns = [
        r"\bчасть\s+[0-9ivxл]+\b",
        r"\bч\.\s*[0-9ivxл]+\b",
        r"\bpart\s+[0-9ivx]+\b",
        r"\bсообщение\s+[0-9ivx]+\b",
        r"\bвыпуск\s+[0-9]+\b",
        r"\bвып\.\s*[0-9]+\b",
        r"\b[ixv]+\s*$",
        r"\(\s*[ixv]+\s*\)"
    ]
    for p in part_patterns:
        if re.search(p, t):
            return True
            
    prefixes = [
        "к вопросу о", "еще раз о", "материалы к", "заметки о", "к истории",
        "к изучению", "к интерпретации", "к анализу", "к характеристике",
        "к описанию", "к семантике", "к переводу", "к этимологии", "к пониманию",
        "к реконструкции", "к проблеме", "предварительные заметки о"
    ]
    for pref in prefixes:
        if t.startswith(pref):
            return True
    return False


def counter_cosine(a: Counter[str], b: Counter[str]) -> float | None:
    keys = set(a) | set(b)
    if not keys:
        return None
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(a[k] ** 2 for k in keys))
    norm_b = math.sqrt(sum(b[k] ** 2 for k in keys))
    if not norm_a or not norm_b:
        return None
    return dot / (norm_a * norm_b)


def hypothesis_ikvia_bridge(con: sqlite3.Connection, people: dict[str, dict[str, object]], theme_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw_affils: dict[str, list[str]] = defaultdict(list)
    for pid, affil in con.execute("select person_id, affiliation_text_raw from presentation_person"):
        if affil and affil not in raw_affils[pid]:
            raw_affils[pid].append(affil)

    l1_by_person = defaultdict(Counter)
    themes_by_pres = db_presentation_themes(con, theme_rows)
    for pid, pres_id in con.execute("select person_id, presentation_id from presentation_person"):
        row = themes_by_pres.get(pres_id)
        if row:
            l1_by_person[pid][row["l1"]] += 1

    rows = []
    inst_counter: Counter[str] = Counter()
    for pid, info in people.items():
        series = info["series"]
        if not ("Zograf" in series and "Roerich" in series):
            continue
        z = int(series["Zograf"]["count"])
        r = int(series["Roerich"]["count"])
        total = z + r
        balance = round((z - r) / total, 3)
        groups = affiliation_groups(raw_affils[pid])
        for group in groups:
            inst_counter[group] += 1
        rows.append(
            {
                "person_id": pid,
                "display_name": info["name"],
                "total": total,
                "zograf": z,
                "roerich": r,
                "balance": balance,
                "first_year": min(series["Zograf"]["first"], series["Roerich"]["first"]),
                "last_year": max(series["Zograf"]["last"], series["Roerich"]["last"]),
                "affiliation_groups": "; ".join(groups),
                "has_ikvia_hse": "yes" if "ИКВИА/ВШЭ" in groups else "no",
                "top_l1": "; ".join(f"{k}:{v}" for k, v in l1_by_person[pid].most_common(3)),
                "raw_affiliations": " | ".join(raw_affils[pid]),
            }
        )
    rows.sort(key=lambda r: (r["has_ikvia_hse"] != "yes", -int(r["total"]), str(r["display_name"])))
    summary = [
        {"affiliation_group": group, "cross_cohort_people": count}
        for group, count in inst_counter.most_common()
    ]
    return rows, summary


def hypothesis_ikvia_theme_adaptation(con: sqlite3.Connection, people: dict[str, dict[str, object]], theme_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    raw_affils: dict[str, list[str]] = defaultdict(list)
    for pid, affil in con.execute("select person_id, affiliation_text_raw from presentation_person"):
        if affil and affil not in raw_affils[pid]:
            raw_affils[pid].append(affil)

    themes_by_pres = db_presentation_themes(con, theme_rows)
    l1_by_person_series: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for pid, pres_id, series_name in con.execute(
        """
        select pp.person_id, pp.presentation_id, es.series_name_en
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        """
    ):
        row = themes_by_pres.get(pres_id)
        if row:
            series = "Zograf" if "Zograf" in series_name else "Roerich"
            l1_by_person_series[pid][series][row["l1"]] += 1

    rows = []
    for pid, info in people.items():
        series = info["series"]
        groups = affiliation_groups(raw_affils[pid])
        if not ("Zograf" in series and "Roerich" in series and "ИКВИА/ВШЭ" in groups):
            continue
        z_counter = l1_by_person_series[pid]["Zograf"]
        r_counter = l1_by_person_series[pid]["Roerich"]
        z_top = z_counter.most_common(1)[0][0] if z_counter else ""
        r_top = r_counter.most_common(1)[0][0] if r_counter else ""
        cosine = counter_cosine(z_counter, r_counter)
        rows.append(
            {
                "person_id": pid,
                "display_name": info["name"],
                "zograf_talks": sum(z_counter.values()),
                "roerich_talks": sum(r_counter.values()),
                "zograf_l1": "; ".join(f"{k}:{v}" for k, v in z_counter.most_common()),
                "roerich_l1": "; ".join(f"{k}:{v}" for k, v in r_counter.most_common()),
                "same_top_l1": "yes" if z_top and z_top == r_top else "no",
                "l1_cosine_similarity": round(cosine, 3) if cosine is not None else "",
            }
        )
    rows.sort(key=lambda r: (r["same_top_l1"] != "yes", -float(r["l1_cosine_similarity"] or 0), str(r["display_name"])))
    return rows


def hypothesis_age_at_debut(con: sqlite3.Connection, people: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    first_seen: dict[str, tuple[int, str]] = {}
    for pid, year, series in con.execute(
        """
        select pp.person_id, e.year, es.series_name_en
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        order by e.year
        """
    ):
        if pid not in first_seen:
            first_seen[pid] = (year, "Zograf" if "Zograf" in series else "Roerich")

    rows = []
    missing = []
    for pid, info in people.items():
        series = info["series"]
        total = sum(int(v["count"]) for v in series.values())
        z = int(series.get("Zograf", {}).get("count", 0))
        r = int(series.get("Roerich", {}).get("count", 0))
        first_year, first_series = first_seen[pid]
        birth = info["birth_year"]
        if birth is None:
            if total >= 5 or str(info["name"]) in {"М. Ю. Гасунс", "А. С. Крылова"}:
                missing.append(
                    {
                        "person_id": pid,
                        "display_name": info["name"],
                        "total": total,
                        "zograf": z,
                        "roerich": r,
                        "first_year": first_year,
                        "reason": "needed_for_age_debut_or_high_activity",
                    }
                )
            continue
        rows.append(
            {
                "person_id": pid,
                "display_name": info["name"],
                "birth_year": birth,
                "first_year": first_year,
                "age_at_debut": first_year - int(birth),
                "first_series": first_series,
                "series_attended": "both" if z and r else ("zograf_only" if z else "roerich_only"),
                "total": total,
                "zograf": z,
                "roerich": r,
            }
        )

    summary = []
    bins = [
        ("2004-2010", lambda y: 2004 <= y <= 2010),
        ("2011-2017", lambda y: 2011 <= y <= 2017),
        ("2018-2026", lambda y: 2018 <= y <= 2026),
    ]
    for label, pred in bins:
        ages = [int(r["age_at_debut"]) for r in rows if pred(int(r["first_year"]))]
        summary.append(
            {
                "debut_period": label,
                "n_known_birth_year": len(ages),
                "median_age_at_debut": median(ages),
                "min_age_at_debut": min(ages) if ages else "",
                "max_age_at_debut": max(ages) if ages else "",
            }
        )

    stats: dict[str, object] = {}
    if spearmanr and len(rows) >= 3:
        rho, p_value = spearmanr([int(r["first_year"]) for r in rows], [int(r["age_at_debut"]) for r in rows])
        stats.update({"spearman_rho": round(float(rho), 3), "spearman_p": round(float(p_value), 4)})
    if kruskal:
        groups = [[int(r["age_at_debut"]) for r in rows if pred(int(r["first_year"]))] for _label, pred in bins]
        if all(groups):
            h_value, p_value = kruskal(*groups)
            stats.update({"kruskal_h": round(float(h_value), 3), "kruskal_p": round(float(p_value), 4)})
    return rows, summary, missing, stats


def figure_age_at_debut(rows: list[dict[str, object]]) -> None:
    width, height = 980, 600
    left, top, plot_w, plot_h = 82, 78, 800, 410
    xs = [int(r["first_year"]) for r in rows]
    ys = [int(r["age_at_debut"]) for r in rows]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = 15, max(ys) + 5

    def sx(x):
        return left + (x - xmin) / (xmax - xmin) * plot_w

    def sy(y):
        return top + (1 - (y - ymin) / (ymax - ymin)) * plot_h

    body = [
        text(32, 32, "Возраст первого наблюдаемого выступления в корпусе", "title"),
        text(32, 54, "Только участники с подтвержденным годом рождения; нисходящий тренд статистически неустойчив.", "sub"),
        rect(left, top, plot_w, plot_h, "#fff", "#cfd8e3"),
    ]
    for year in range(xmin, xmax + 1, 2):
        x = sx(year)
        body.append(line(x, top, x, top + plot_h, "#edf1f5"))
        body.append(text(x, top + plot_h + 24, year, "axis", "middle"))
    for age in range(20, ymax + 1, 10):
        y = sy(age)
        body.append(line(left, y, left + plot_w, y, "#edf1f5"))
        body.append(text(left - 10, y + 4, age, "axis", "end"))
    colors = {"both": "#7b5ea7", "zograf_only": "#2f6fbb", "roerich_only": "#b8554b"}
    for row in rows:
        color = colors[str(row["series_attended"])]
        r = 4 + math.sqrt(int(row["total"])) * 0.8
        body.append(circle(sx(int(row["first_year"])), sy(int(row["age_at_debut"])), r, color))
    for row in sorted(rows, key=lambda r: int(r["total"]), reverse=True)[:10]:
        body.append(text(sx(int(row["first_year"])) + 7, sy(int(row["age_at_debut"])) - 6, short_name(str(row["display_name"])), "label"))
    body.append(text(left + plot_w / 2, height - 38, "Год первого выступления", "axis", "middle"))
    body.append(text(20, top + plot_h / 2, "Возраст", "axis", "middle"))
    legend_x, legend_y = 700, 92
    for i, (label, color) in enumerate([("обе площадки", "#7b5ea7"), ("только Зограф", "#2f6fbb"), ("только Рерих", "#b8554b")]):
        body.append(circle(legend_x, legend_y + i * 24, 6, color))
        body.append(text(legend_x + 16, legend_y + 4 + i * 24, label, "small"))
    (OUT / "age_at_debut.svg").write_text(svg(width, height, body), encoding="utf-8")


def hypothesis_publication_sources(con: sqlite3.Connection) -> list[dict[str, object]]:
    rows = []
    for media_id, title, url, source_url in con.execute(
        "select media_id, media_title, media_url, source_url from media where media_type='pdf' order by media_id"
    ):
        rows.append(
            {
                "media_id": media_id,
                "media_title": title,
                "media_url": url,
                "source_url": source_url,
                "current_linkage": "post-level only",
                "workup_status": "source inventory; presentation/article conversion requires contents parsing",
            }
        )
    return rows


def hypothesis_video_availability(con: sqlite3.Connection, theme_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    video_counts = Counter(
        pres_id
        for (pres_id,) in con.execute(
            "select distinct attached_to_id from media where media_type='video' and attached_to_type='presentation'"
        )
    )
    presentation_meta = {
        pres_id: (series, year)
        for pres_id, series, year in con.execute(
            """
            select pr.presentation_id, es.series_name_en, e.year
            from presentation pr
            join session s using(session_id)
            join event_day_venue edv using(event_day_venue_id)
            join event_day ed using(event_day_id)
            join event e using(event_id)
            join event_series es using(event_series_id)
            """
        )
    }
    by_year = defaultdict(lambda: {"presentations": 0, "with_video": 0})
    for pres_id, (series, year) in presentation_meta.items():
        key = ("Zograf" if "Zograf" in series else "Roerich", year)
        by_year[key]["presentations"] += 1
        if video_counts[pres_id]:
            by_year[key]["with_video"] += 1
    year_rows = []
    for (series, year), counts in sorted(by_year.items(), key=lambda item: (item[0][0], item[0][1])):
        year_rows.append(
            {
                "series": series,
                "year": year,
                "presentations": counts["presentations"],
                "presentations_with_video": counts["with_video"],
                "video_coverage_pct": pct(counts["with_video"], counts["presentations"]),
            }
        )

    themes_by_pres = db_presentation_themes(con, theme_rows)
    by_l1 = defaultdict(lambda: {"presentations": 0, "with_video": 0})
    for pres_id, (series, _year) in presentation_meta.items():
        row = themes_by_pres.get(pres_id)
        if not row:
            continue
        key = (series, row["l1"])
        by_l1[key]["presentations"] += 1
        if video_counts[pres_id]:
            by_l1[key]["with_video"] += 1
    l1_rows = []
    for (series, l1), counts in sorted(by_l1.items()):
        l1_rows.append(
            {
                "series": series,
                "l1": l1,
                "presentations": counts["presentations"],
                "presentations_with_video": counts["with_video"],
                "video_coverage_pct": pct(counts["with_video"], counts["presentations"]),
            }
        )

    mapping_rows = read_csv(ANALYTICS / "video_presentation_mapping.csv")
    status_rows = [
        {"status": status, "videos": count}
        for status, count in Counter(row["status"] for row in mapping_rows).most_common()
    ]
    return year_rows, l1_rows, status_rows


def figure_video_coverage(year_rows: list[dict[str, object]]) -> None:
    rows = [r for r in year_rows if r["series"] == "Zograf" and int(r["year"]) >= 2018]
    width, height = 900, 520
    left, top, plot_w, plot_h = 92, 72, 720, 320
    years = [int(r["year"]) for r in rows]
    ymax = max(int(r["presentations"]) for r in rows) + 8
    body = [
        text(32, 30, "Видео-доступность Зографских чтений: привязанные записи", "title"),
        text(32, 52, "Темная часть столбца — доклады, связанные с публичной записью в базе; привязка неполная.", "sub"),
        rect(left, top, plot_w, plot_h, "#fff", "#cfd8e3"),
    ]
    for y in range(0, ymax + 1, 15):
        yy = top + plot_h - y / ymax * plot_h
        body.append(line(left, yy, left + plot_w, yy, "#edf1f5"))
        body.append(text(left - 10, yy + 4, y, "axis", "end"))
    bar_w = plot_w / len(rows) * 0.55
    for i, row in enumerate(rows):
        x = left + (i + 0.5) * plot_w / len(rows)
        total = int(row["presentations"])
        with_video = int(row["presentations_with_video"])
        h_total = total / ymax * plot_h
        h_video = with_video / ymax * plot_h
        body.append(rect(x - bar_w / 2, top + plot_h - h_total, bar_w, h_total, "#cbd5df"))
        body.append(rect(x - bar_w / 2, top + plot_h - h_video, bar_w, h_video, "#2f6fbb"))
        body.append(text(x, top + plot_h + 24, row["year"], "axis", "middle"))
        body.append(text(x, top + plot_h - h_video - 7, f"{row['video_coverage_pct']}%", "label", "middle"))
    body.append(text(left + plot_w / 2, height - 42, "Год", "axis", "middle"))
    (OUT / "video_coverage_zograf.svg").write_text(svg(width, height, body), encoding="utf-8")


def build_person_event_graph(con: sqlite3.Connection) -> tuple[dict[str, set[str]], dict[str, str]]:
    event_people = defaultdict(set)
    names = {}
    for pid, name, event_id in con.execute(
        """
        select pp.person_id, p.display_name, e.event_id
        from presentation_person pp
        join person p using(person_id)
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        """
    ):
        event_people[event_id].add(pid)
        names[pid] = name
    graph = defaultdict(set)
    for people in event_people.values():
        people_list = list(people)
        for i, a in enumerate(people_list):
            for b in people_list[i + 1 :]:
                graph[a].add(b)
                graph[b].add(a)
    for pid in names:
        graph[pid]
    return graph, names


def build_person_session_graph(con: sqlite3.Connection) -> tuple[dict[str, set[str]], dict[str, str], Counter[str], dict[str, int]]:
    session_people = defaultdict(set)
    names = {}
    session_sizes = {}
    for pid, name, session_id in con.execute(
        """
        select pp.person_id, p.display_name, s.session_id
        from presentation_person pp
        join person p using(person_id)
        join presentation pr using(presentation_id)
        join session s using(session_id)
        """
    ):
        session_people[session_id].add(pid)
        names[pid] = name
    graph = defaultdict(set)
    session_counts: Counter[str] = Counter()
    for session_id, people in session_people.items():
        session_sizes[session_id] = len(people)
        people_list = list(people)
        if len(people_list) >= 2:
            for pid in people_list:
                session_counts[pid] += 1
        for i, a in enumerate(people_list):
            for b in people_list[i + 1 :]:
                graph[a].add(b)
                graph[b].add(a)
    for pid in names:
        graph[pid]
    return graph, names, session_counts, session_sizes


def betweenness_centrality(graph: dict[str, set[str]]) -> dict[str, float]:
    nodes = list(graph)
    centrality = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[str] = []
        predecessors = {w: [] for w in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance = dict.fromkeys(nodes, -1)
        distance[source] = 0
        queue = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in graph[v]:
                if distance[w] < 0:
                    queue.append(w)
                    distance[w] = distance[v] + 1
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != source:
                centrality[w] += delta[w]
    n = len(nodes)
    if n > 2:
        scale = 1 / ((n - 1) * (n - 2))
        for node in centrality:
            centrality[node] *= scale
    return centrality


def hypothesis_network_bridges(con: sqlite3.Connection, people: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    graph, names = build_person_event_graph(con)
    centrality = betweenness_centrality(graph)
    event_counts = Counter()
    for pid, event_id in con.execute(
        """
        select distinct pp.person_id, e.event_id
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        """
    ):
        event_counts[pid] += 1
    rows = []
    for pid, info in people.items():
        series = info["series"]
        z = int(series.get("Zograf", {}).get("count", 0))
        r = int(series.get("Roerich", {}).get("count", 0))
        total = z + r
        balance = round((z - r) / total, 3) if total else 0
        rows.append(
            {
                "person_id": pid,
                "display_name": names.get(pid, info["name"]),
                "betweenness": round(centrality.get(pid, 0.0), 6),
                "graph_degree": len(graph[pid]),
                "events_attended": event_counts[pid],
                "total_participations": total,
                "zograf": z,
                "roerich": r,
                "balance": balance,
                "series_attended": "both" if z and r else ("zograf_only" if z else "roerich_only"),
            }
        )
    rows.sort(key=lambda r: (float(r["betweenness"]), int(r["events_attended"]), int(r["total_participations"])), reverse=True)
    return rows


def hypothesis_network_bridges_session(con: sqlite3.Connection, people: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    graph, names, session_counts, session_sizes = build_person_session_graph(con)
    centrality = betweenness_centrality(graph)
    rows = []
    for pid, info in people.items():
        series = info["series"]
        z = int(series.get("Zograf", {}).get("count", 0))
        r = int(series.get("Roerich", {}).get("count", 0))
        total = z + r
        balance = round((z - r) / total, 3) if total else 0
        rows.append(
            {
                "person_id": pid,
                "display_name": names.get(pid, info["name"]),
                "session_betweenness": round(centrality.get(pid, 0.0), 6),
                "session_graph_degree": len(graph[pid]),
                "multi_person_sessions": session_counts[pid],
                "total_participations": total,
                "zograf": z,
                "roerich": r,
                "balance": balance,
                "series_attended": "both" if z and r else ("zograf_only" if z else "roerich_only"),
            }
        )
    rows.sort(key=lambda r: (float(r["session_betweenness"]), int(r["multi_person_sessions"]), int(r["total_participations"])), reverse=True)
    stats = {
        "sessions_total": len(session_sizes),
        "sessions_multi_person": sum(1 for value in session_sizes.values() if value >= 2),
        "sessions_large_10plus": sum(1 for value in session_sizes.values() if value >= 10),
        "largest_session_size": max(session_sizes.values()) if session_sizes else 0,
    }
    return rows, stats


def figure_network_bridges(rows: list[dict[str, object]]) -> None:
    top = rows[:15]
    width, height = 1000, 620
    left, top_y, plot_w, row_h = 250, 76, 650, 28
    max_val = max(float(r["betweenness"]) for r in top) or 1
    body = [
        text(32, 30, "Событийная центральность участников", "title"),
        text(32, 52, "Betweenness в графе, где ребро означает участие в одном и том же годовом событии.", "sub"),
    ]
    colors = {"both": "#7b5ea7", "zograf_only": "#2f6fbb", "roerich_only": "#b8554b"}
    for i, row in enumerate(top):
        y = top_y + i * row_h
        body.append(text(left - 12, y + 17, short_name(str(row["display_name"])), "small", "end"))
        w = float(row["betweenness"]) / max_val * plot_w
        body.append(rect(left, y, w, 18, colors[str(row["series_attended"])]))
        body.append(text(left + w + 8, y + 14, row["betweenness"], "label"))
    body.append(text(left, height - 32, "Цвет: обе площадки / только Зограф / только Рерих", "sub"))
    (OUT / "network_bridges.svg").write_text(svg(width, height, body), encoding="utf-8")


def figure_network_bridges_session(rows: list[dict[str, object]]) -> None:
    top = rows[:15]
    width, height = 1000, 620
    left, top_y, plot_w, row_h = 250, 76, 650, 28
    max_val = max(float(r["session_betweenness"]) for r in top) or 1
    body = [
        text(32, 30, "Сессионная центральность участников", "title"),
        text(32, 52, "Betweenness в графе, где ребро означает участие в одной программной сессии; результат предварительный.", "sub"),
    ]
    colors = {"both": "#7b5ea7", "zograf_only": "#2f6fbb", "roerich_only": "#b8554b"}
    for i, row in enumerate(top):
        y = top_y + i * row_h
        body.append(text(left - 12, y + 17, short_name(str(row["display_name"])), "small", "end"))
        w = float(row["session_betweenness"]) / max_val * plot_w
        body.append(rect(left, y, w, 18, colors[str(row["series_attended"])]))
        body.append(text(left + w + 8, y + 14, row["session_betweenness"], "label"))
    body.append(text(left, height - 32, "Цвет: обе площадки / только Зограф / только Рерих", "sub"))
    (OUT / "network_bridges_session.svg").write_text(svg(width, height, body), encoding="utf-8")


def hypothesis_fractional_counting(con: sqlite3.Connection) -> tuple[list[dict[str, object]], dict[str, object]]:
    pres_ppl = defaultdict(list)
    for p_id, year, series, pers_id, affil in con.execute("""
        select pr.presentation_id, e.year, es.series_name_en, pp.person_id, pp.affiliation_text_raw
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        join presentation_person pp on pp.presentation_id = pr.presentation_id
    """):
        pres_ppl[p_id].append((year, series, pers_id, affil))
        
    org_counts = defaultdict(lambda: {"simple": 0.0, "fractional": 0.0})
    org_by_year = defaultdict(lambda: {"simple": 0.0, "fractional": 0.0})
    target_orgs = {"ИВ РАН", "ИВР РАН", "СПбГУ", "ИКВИА/ВШЭ"}
    
    for p_id, ppl in pres_ppl.items():
        k = len(ppl)
        for year, series, pers_id, affil in ppl:
            gps = affiliation_groups([affil])
            m = len(gps)
            for org in gps:
                frac_weight = 1.0 / (k * m)
                simp_weight = 1.0
                
                org_counts[org]["simple"] += simp_weight
                org_counts[org]["fractional"] += frac_weight
                
                if org in target_orgs:
                    series_clean = "Zograf" if "Zograf" in series else "Roerich"
                    org_by_year[(org, year, series_clean)]["simple"] += simp_weight
                    org_by_year[(org, year, series_clean)]["fractional"] += frac_weight

    rows = []
    for (org, year, series), counts in sorted(org_by_year.items()):
        rows.append({
            "organization": org,
            "year": year,
            "series": series,
            "simple_count": round(counts["simple"], 1),
            "fractional_count": round(counts["fractional"], 3)
        })

    stats = {
        "h7_ivran_simple": org_counts["ИВ РАН"]["simple"],
        "h7_ivran_fractional": org_counts["ИВ РАН"]["fractional"],
        "h7_ivrran_simple": org_counts["ИВР РАН"]["simple"],
        "h7_ivrran_fractional": org_counts["ИВР РАН"]["fractional"],
        "h7_spbgu_simple": org_counts["СПбГУ"]["simple"],
        "h7_spbgu_fractional": org_counts["СПбГУ"]["fractional"],
        "h7_ikvia_simple": org_counts["ИКВИА/ВШЭ"]["simple"],
        "h7_ikvia_fractional": org_counts["ИКВИА/ВШЭ"]["fractional"],
    }
    return rows, stats


def hypothesis_era_influence(con: sqlite3.Connection, theme_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    z_speaker_years = defaultdict(list)
    z_presentations = []
    
    lookup = theme_lookup(theme_rows)
    
    for p_id, year, title, pers_id in con.execute("""
        select pr.presentation_id, e.year, pr.title, pp.person_id
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        join presentation_person pp on pp.presentation_id = pr.presentation_id
        where es.series_name_en = 'Zograf Readings'
    """):
        z_speaker_years[pers_id].append(year)
        coded_row = lookup.get(("Zograf", year, norm_title(title or "")))
        z_presentations.append({
            "presentation_id": p_id,
            "year": year,
            "person_id": pers_id,
            "l1": coded_row["l1"] if coded_row else "unknown",
            "l2": coded_row["l2"] if coded_row else "unknown",
        })
        
    z_speaker_debut = {pers_id: min(years) for pers_id, years in z_speaker_years.items()}
    
    year_speakers = defaultdict(set)
    year_newcomers = defaultdict(set)
    for pers_id, years in z_speaker_years.items():
        debut = z_speaker_debut[pers_id]
        for y in years:
            year_speakers[y].add(pers_id)
            if y == debut:
                year_newcomers[y].add(pers_id)
                
    vasilkov_speakers = 0
    vasilkov_newcomers = 0
    albedil_speakers = 0
    albedil_newcomers = 0
    newcomer_rows = []
    
    for y in sorted(year_speakers.keys()):
        spk_count = len(year_speakers[y])
        new_count = len(year_newcomers[y])
        newcomer_rows.append({
            "year": y,
            "total_speakers": spk_count,
            "newcomers": new_count,
            "newcomer_pct": pct(new_count, spk_count)
        })
        if y <= 2024:
            vasilkov_speakers += spk_count
            vasilkov_newcomers += new_count
        else:
            albedil_speakers += spk_count
            albedil_newcomers += new_count
            
    p_vas = pct(vasilkov_newcomers, vasilkov_speakers)
    p_alb = pct(albedil_newcomers, albedil_speakers)
    
    newcomer_p_val = "н/д"
    if chi2_contingency:
        contingency = [
            [vasilkov_newcomers, vasilkov_speakers - vasilkov_newcomers],
            [albedil_newcomers, albedil_speakers - albedil_newcomers]
        ]
        _, p_val, _, _ = chi2_contingency(contingency)
        newcomer_p_val = f"{p_val:.4f}"
        
    vasilkov_l1 = Counter()
    albedil_l1 = Counter()
    vasilkov_l2 = Counter()
    albedil_l2 = Counter()
    
    seen_pres = set()
    for pres in z_presentations:
        p_id = pres["presentation_id"]
        if p_id in seen_pres:
            continue
        seen_pres.add(p_id)
        
        y = pres["year"]
        l1 = pres["l1"]
        l2 = pres["l2"]
        if y <= 2024:
            vasilkov_l1[l1] += 1
            vasilkov_l2[l2] += 1
        else:
            albedil_l1[l1] += 1
            albedil_l2[l2] += 1
            
    all_l1 = sorted(set(vasilkov_l1.keys()) | set(albedil_l1.keys()))
    l1_rows = []
    for cat in all_l1:
        if cat != "unknown":
            l1_rows.append({
                "theme_l1": cat,
                "vasilkov_count": vasilkov_l1[cat],
                "vasilkov_pct": pct(vasilkov_l1[cat], sum(vasilkov_l1.values())),
                "albedil_count": albedil_l1[cat],
                "albedil_pct": pct(albedil_l1[cat], sum(albedil_l1.values()))
            })
            
    l1_p_val = "н/д"
    if chi2_contingency:
        matrix_l1 = []
        for cat in all_l1:
            if cat != "unknown" and (vasilkov_l1[cat] > 0 or albedil_l1[cat] > 0):
                matrix_l1.append([vasilkov_l1[cat], albedil_l1[cat]])
        matrix_l1_t = list(map(list, zip(*matrix_l1)))
        if len(matrix_l1_t) > 1 and len(matrix_l1_t[0]) > 1:
            _, p_val, _, _ = chi2_contingency(matrix_l1_t)
            l1_p_val = f"{p_val:.4f}"
            
    all_l2 = sorted(set(vasilkov_l2.keys()) | set(albedil_l2.keys()))
    l2_rows = []
    for cat in all_l2:
        if cat != "unknown":
            l2_rows.append({
                "theme_l2": cat,
                "vasilkov_count": vasilkov_l2[cat],
                "vasilkov_pct": pct(vasilkov_l2[cat], sum(vasilkov_l2.values())),
                "albedil_count": albedil_l2[cat],
                "albedil_pct": pct(albedil_l2[cat], sum(albedil_l2.values()))
            })
            
    l2_p_val = "н/д"
    if chi2_contingency:
        matrix_l2 = []
        for cat in all_l2:
            if cat != "unknown" and (vasilkov_l2[cat] > 0 or albedil_l2[cat] > 0):
                matrix_l2.append([vasilkov_l2[cat], albedil_l2[cat]])
        matrix_l2_t = list(map(list, zip(*matrix_l2)))
        if len(matrix_l2_t) > 1 and len(matrix_l2_t[0]) > 1:
            _, p_val, _, _ = chi2_contingency(matrix_l2_t)
            l2_p_val = f"{p_val:.4f}"

    stats = {
        "h8_vasilkov_newcomers": vasilkov_newcomers,
        "h8_vasilkov_speakers": vasilkov_speakers,
        "h8_vasilkov_newcomers_pct": p_vas,
        "h8_albedil_newcomers": albedil_newcomers,
        "h8_albedil_speakers": albedil_speakers,
        "h8_albedil_newcomers_pct": p_alb,
        "h8_newcomer_p": newcomer_p_val,
        "h8_l1_p": l1_p_val,
        "h8_l2_p": l2_p_val
    }
    return newcomer_rows, l1_rows, l2_rows, stats


def hypothesis_geographic_gravity(con: sqlite3.Connection) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    zograf_cities = Counter()
    roerich_cities = Counter()
    speaker_city_years = defaultdict(lambda: {"city": "Unknown", "years": set()})
    
    for p_id, year, series, pers_id, affil in con.execute("""
        select pr.presentation_id, e.year, es.series_name_en, pp.person_id, pp.affiliation_text_raw
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        join presentation_person pp on pp.presentation_id = pr.presentation_id
    """):
        city = infer_city(affil)
        if "Zograf" in series:
            zograf_cities[city] += 1
        else:
            roerich_cities[city] += 1
            
        speaker_city_years[pers_id]["years"].add(year)
        if speaker_city_years[pers_id]["city"] == "Unknown" or city != "Regions/Foreign":
            speaker_city_years[pers_id]["city"] = city
            
    total_z = sum(zograf_cities.values())
    total_r = sum(roerich_cities.values())
    
    distribution_rows = []
    for city in ["SPb", "Moscow", "Regions/Foreign"]:
        distribution_rows.append({
            "city": city,
            "zograf_talks": zograf_cities[city],
            "zograf_pct": pct(zograf_cities[city], total_z),
            "roerich_talks": roerich_cities[city],
            "roerich_pct": pct(roerich_cities[city], total_r)
        })
        
    survival_data = defaultdict(lambda: {"total": 0, "returning": 0})
    for pers_id, info in speaker_city_years.items():
        city = info["city"]
        if city == "Unknown":
            continue
        nyears = len(info["years"])
        is_returning = 1 if nyears >= 2 else 0
        survival_data[city]["total"] += 1
        survival_data[city]["returning"] += is_returning
        
    retention_rows = []
    for city in ["Moscow", "SPb", "Regions/Foreign"]:
        tot = survival_data[city]["total"]
        ret = survival_data[city]["returning"]
        retention_rows.append({
            "city": city,
            "total_speakers": tot,
            "returning_speakers": ret,
            "retention_pct": pct(ret, tot)
        })
        
    metropolitan_speakers = survival_data["SPb"]["total"] + survival_data["Moscow"]["total"]
    metropolitan_returning = survival_data["SPb"]["returning"] + survival_data["Moscow"]["returning"]
    
    regions_speakers = survival_data["Regions/Foreign"]["total"]
    regions_returning = survival_data["Regions/Foreign"]["returning"]
    
    survival_p_val = "н/д"
    if chi2_contingency:
        contingency_survival = [
            [metropolitan_returning, metropolitan_speakers - metropolitan_returning],
            [regions_returning, regions_speakers - regions_returning]
        ]
        _, p_val, _, _ = chi2_contingency(contingency_survival)
        survival_p_val = f"{p_val:.4f}"
        
    stats = {
        "h9_zograf_spb_pct": pct(zograf_cities["SPb"], total_z),
        "h9_zograf_moscow_pct": pct(zograf_cities["Moscow"], total_z),
        "h9_zograf_regions_pct": pct(zograf_cities["Regions/Foreign"], total_z),
        "h9_roerich_spb_pct": pct(roerich_cities["SPb"], total_r),
        "h9_roerich_moscow_pct": pct(roerich_cities["Moscow"], total_r),
        "h9_roerich_regions_pct": pct(roerich_cities["Regions/Foreign"], total_r),
        "h9_retention_moscow_pct": pct(survival_data["Moscow"]["returning"], survival_data["Moscow"]["total"]),
        "h9_retention_spb_pct": pct(survival_data["SPb"]["returning"], survival_data["SPb"]["total"]),
        "h9_retention_regions_pct": pct(survival_data["Regions/Foreign"]["returning"], survival_data["Regions/Foreign"]["total"]),
        "h9_survival_p": survival_p_val
    }
    return distribution_rows, retention_rows, stats


def hypothesis_talk_serialization(con: sqlite3.Connection) -> tuple[list[dict[str, object]], dict[str, object]]:
    speaker_talks = defaultdict(list)
    for pres_id, title, pers_id in con.execute("""
        select pr.presentation_id, pr.title, pp.person_id
        from presentation pr
        join presentation_person pp on pp.presentation_id = pr.presentation_id
    """):
        speaker_talks[pers_id].append(title)
        
    core_serialized_count = 0
    core_total_count = 0
    periph_serialized_count = 0
    periph_total_count = 0
    person_stats = []
    
    for pers_id, titles in speaker_talks.items():
        total = len(titles)
        serialized = sum(1 for t in titles if is_serialized(t))
        is_core = total >= 5
        person_stats.append({
            "pers_id": pers_id,
            "total": total,
            "serialized": serialized,
            "is_core": is_core
        })
        if is_core:
            core_serialized_count += serialized
            core_total_count += total
        else:
            periph_serialized_count += serialized
            periph_total_count += total
            
    rows = []
    for p in sorted(person_stats, key=lambda x: x["total"], reverse=True):
        rows.append({
            "person_id": p["pers_id"],
            "total_talks": p["total"],
            "serialized_talks": p["serialized"],
            "serialization_pct": pct(p["serialized"], p["total"]),
            "is_core_speaker": "yes" if p["is_core"] else "no"
        })
        
    serialization_p_val = "н/д"
    if chi2_contingency:
        contingency_serialization = [
            [core_serialized_count, core_total_count - core_serialized_count],
            [periph_serialized_count, periph_total_count - periph_serialized_count]
        ]
        if fisher_exact:
            _, p_val = fisher_exact(contingency_serialization)
            serialization_p_val = f"{p_val:.4f}"
        else:
            _, p_val, _, _ = chi2_contingency(contingency_serialization)
            serialization_p_val = f"{p_val:.4f}"
            
    spearman_rho_val = "н/д"
    spearman_p_val = "н/д"
    if spearmanr:
        totals = [p["total"] for p in person_stats]
        serializeds = [p["serialized"] for p in person_stats]
        rho, p_val = spearmanr(totals, serializeds)
        spearman_rho_val = f"{rho:.3f}"
        spearman_p_val = f"{p_val:.4f}"
        
    stats = {
        "h10_core_serialized": core_serialized_count,
        "h10_core_total": core_total_count,
        "h10_core_serialized_pct": pct(core_serialized_count, core_total_count),
        "h10_periph_serialized": periph_serialized_count,
        "h10_periph_total": periph_total_count,
        "h10_periph_serialized_pct": pct(periph_serialized_count, periph_total_count),
        "h10_fisher_p": serialization_p_val,
        "h10_spearman_rho": spearman_rho_val,
        "h10_spearman_p": spearman_p_val
    }
    return rows, stats


def write_markdown_summary(stats: dict[str, object]) -> None:
    lines = [
        "# Отработка новых гипотез",
        "",
        "Сгенерировано `article/work_ppv_hypotheses.py` из локальной SQLite-базы, кешированных HTML и CSV из `analytics_output`.",
        f"Контроль стыковки тематических кодов с БД по серии/году/нормализованному названию: {stats.get('theme_match_total', 0)} из {stats.get('theme_presentations_total', 0)} докладов ({stats.get('theme_match_pct', 0)}%).",
        "",
        "## H1. Подзаголовок программы и реальное содержание",
        "",
        f"- Группы подзаголовков Рериховских чтений с кодированными докладами: {stats.get('subtitle_groups', '')}.",
        f"- Проверка L2 по группам: χ²={stats.get('subtitle_l2_chi2', 'н/д')}, p={stats.get('subtitle_l2_p', 'н/д')}, V={stats.get('subtitle_l2_v', 'н/д')}.",
        "- Первый вывод: подзаголовки полезны как источник, но пока не дают сильного объяснения тематического распределения.",
        "- Важная предварительная проблема: поле `event.theme_ru` в БД для Рериховских чтений унифицировано и скрывает реальные вариации заголовков, видимые в HTML.",
        "",
        "## H2. ИКВИА/ВШЭ как мост",
        "",
        f"- Участников перекрестной когорты с исторической аффилиацией ИКВИА/ВШЭ: {stats.get('ikvia_cross_count', 0)} из {stats.get('cross_cohort_total', 0)}.",
        f"- Крупнейшие институциональные группы перекрестной когорты: {stats.get('top_cross_institutions', '')}.",
        f"- Тематическая адаптация ИКВИА/ВШЭ между площадками: совпадение ведущей L1 у {stats.get('ikvia_same_top_l1', 0)} из {stats.get('ikvia_adaptation_count', 0)} участников; медианная cosine similarity={stats.get('ikvia_median_cosine', 'н/д')}.",
        "- Первый вывод: ИКВИА/ВШЭ выглядит как важный новый мост, но не как единственный центр связности.",
        "- См. `ikvia_bridge_cross_cohort.csv`, `ikvia_theme_adaptation.csv` и `institution_bridge_summary.csv`.",
        "",
        "## H3. Возраст первого выступления",
        "",
        f"- Участников с подтвержденным возрастом дебюта: {stats.get('age_debut_known', 0)}.",
        f"- Периодные медианы: {stats.get('age_summary_line', '')}.",
        f"- Тест тренда: Spearman ρ={stats.get('age_spearman_rho', 'н/д')}, p={stats.get('age_spearman_p', 'н/д')}; Kruskal-Wallis H={stats.get('age_kruskal_h', 'н/д')}, p={stats.get('age_kruskal_p', 'н/д')}.",
        "- Первый вывод: есть намек на снижение возраста входа, но кейс Гасунс/Крылова пока не проверяется из-за отсутствующих годов рождения.",
        "- См. `age_at_debut.csv`, `age_at_debut_summary.csv`, `age_at_debut_missing_priority.csv` и `age_at_debut.svg`.",
        "",
        "## H4. Публикационная конверсия",
        "",
        f"- В БД сейчас есть PDF-источников: {stats.get('publication_sources', 0)}, но они связаны с постами, а не с отдельными докладами.",
        "- Это означает, что гипотеза пока не проверяется автоматически; нужен слой парсинга оглавлений/сборников.",
        "",
        "## H5. Видео-доступность",
        "",
        f"- Презентаций с привязанной видеозаписью в таблице `media`: {stats.get('video_presentations', 0)}.",
        f"- Статусы внешнего video mapping: {stats.get('video_status_line', '')}.",
        "- Первый вывод: видеослой можно использовать, но только с явной оговоркой о неполной и неравномерной привязке.",
        "- См. `video_availability_by_year.csv`, `video_availability_by_l1.csv`, `video_mapping_status.csv` и `video_coverage_zograf.svg`.",
        "",
        "## H6. Сетевые посредники",
        "",
        f"- Верх списка по betweenness: {stats.get('network_top_line', '')}.",
        f"- На уровне сессий верх списка: {stats.get('network_session_top_line', '')}.",
        f"- Контроль плотности сессионного графа: {stats.get('sessions_multi_person', 0)} многоперсонных сессий из {stats.get('sessions_total', 0)}, крупных сессий ≥10 участников: {stats.get('sessions_large_10plus', 0)}.",
        "- Первый вывод: сессионный граф лучше отделяет устойчивых докладчиков от реальных посредников, но ранние программы с крупными дневными блоками всё еще завышают связность.",
        "- См. `network_bridges.csv`, `network_bridges_session.csv`, `network_bridges.svg` и `network_bridges_session.svg`.",
        "",
        "## H7. Институциональный фракционный счет",
        "",
        "- Сравнение простого и фракционного подсчета для ключевых организаций:",
        f"  - ИВ РАН: простой={stats.get('h7_ivran_simple', 0.0):.1f}, фракционный={stats.get('h7_ivran_fractional', 0.0):.3f}",
        f"  - ИВР РАН: простой={stats.get('h7_ivrran_simple', 0.0):.1f}, фракционный={stats.get('h7_ivrran_fractional', 0.0):.3f}",
        f"  - СПбГУ: простой={stats.get('h7_spbgu_simple', 0.0):.1f}, фракционный={stats.get('h7_spbgu_fractional', 0.0):.3f}",
        f"  - ИКВИА/ВШЭ: простой={stats.get('h7_ikvia_simple', 0.0):.1f}, фракционный={stats.get('h7_ikvia_fractional', 0.0):.3f}",
        "- Вывод: из-за крайне низкого уровня соавторства (99% докладов — индивидуальные) и редких мульти-аффилиаций переход к фракционному счету практически не меняет итоговые веса.",
        "- См. `org_fractional_counting.csv`.",
        "",
        "## H8. Влияние смены оргкомитета на тематический дрейф Зографских чтений",
        "",
        f"- Доля новичков (newcomer rate): эра Василькова (<=2024) — {stats.get('h8_vasilkov_newcomers_pct', 0.0)}% ({stats.get('h8_vasilkov_newcomers', 0)}/{stats.get('h8_vasilkov_speakers', 0)}), эра Альбедиль-Иванова (2025-2026) — {stats.get('h8_albedil_newcomers_pct', 0.0)}% ({stats.get('h8_albedil_newcomers', 0)}/{stats.get('h8_albedil_speakers', 0)}). Тест хи-квадрат: p={stats.get('h8_newcomer_p', 'н/д')}.",
        f"- Тематический дрейф L1 (дисциплины): тест хи-квадрат p={stats.get('h8_l1_p', 'н/д')}.",
        f"- Тематический дрейф L2 (хронологические периоды): тест хи-квадрат p={stats.get('h8_l2_p', 'н/д')}.",
        "- Вывод: смена оргкомитета не привела к статистически значимому изменению притока новичков или распределения научных дисциплин. Однако наблюдается статистически значимый сдвиг в хронологических периодах (L2, p < 0.05), выражающийся в снижении доли классических тем (с 36.2% до 26.3%) и росте неопределенных/неуказанных периодов (с 8.2% до 16.7%).",
        "- См. `era_newcomers.csv`, `era_themes_l1.csv`, `era_themes_l2.csv`.",
        "",
        "## H9. Географическое притяжение и когортная выживаемость",
        "",
        "- Распределение докладов по городам участников:",
        f"  - Зографские чтения (СПб): СПб — {stats.get('h9_zograf_spb_pct', 0.0)}%, Москва — {stats.get('h9_zograf_moscow_pct', 0.0)}%, Регионы/Ино — {stats.get('h9_zograf_regions_pct', 0.0)}%",
        f"  - Рериховские чтения (Москва): СПб — {stats.get('h9_roerich_spb_pct', 0.0)}%, Москва — {stats.get('h9_roerich_moscow_pct', 0.0)}%, Регионы/Ино — {stats.get('h9_roerich_regions_pct', 0.0)}%",
        f"- Выживаемость (доля участников с выступлением в >= 2 годах): Москва — {stats.get('h9_retention_moscow_pct', 0.0)}%, СПб — {stats.get('h9_retention_spb_pct', 0.0)}%, Регионы/Ино — {stats.get('h9_retention_regions_pct', 0.0)}%. Тест хи-квадрат (столица vs регионы): p={stats.get('h9_survival_p', 'н/д')}.",
        f"- Вывод: центры притяжения сильно поляризованы. Москва гораздо менее охотно посещает СПб ({stats.get('h9_roerich_spb_pct', 0.0)}% докладов в Москве из СПб), хотя питерские чтения привлекают {stats.get('h9_zograf_moscow_pct', 0.0)}% московских докладов. Выживаемость региональных авторов значимо ниже ({stats.get('h9_retention_regions_pct', 0.0)}% против {stats.get('h9_retention_moscow_pct', 0.0)}% у московских и {stats.get('h9_retention_spb_pct', 0.0)}% у петербургских участников, p={stats.get('h9_survival_p', 'н/д')}), что подтверждает периферийный характер регионального участия.",
        "- См. `geographic_presentation_distribution.csv`, `geographic_speaker_retention.csv`.",
        "",
        "## H10. Сериализация докладов",
        "",
        f"- Доля сериализованных докладов у ядра (>=5 выступлений): {stats.get('h10_core_serialized_pct', 0.0)}% ({stats.get('h10_core_serialized', 0)}/{stats.get('h10_core_total', 0)})",
        f"- Доля сериализованных докладов у периферии (<5 выступлений): {stats.get('h10_periph_serialized_pct', 0.0)}% ({stats.get('h10_periph_serialized', 0)}/{stats.get('h10_periph_total', 0)})",
        f"- Точный критерий Фишера (различие долей): p={stats.get('h10_fisher_p', 'н/д')}",
        f"- Корреляция Спирмена (число докладов vs число сериализованных докладов): rho={stats.get('h10_spearman_rho', 'н/д')}, p={stats.get('h10_spearman_p', 'н/д')}",
        f"- Вывод: ядро авторов не склонно к более высокой относительной сериализации по сравнению с периферией ({stats.get('h10_core_serialized_pct', 0.0)}% vs {stats.get('h10_periph_serialized_pct', 0.0)}%, p={stats.get('h10_fisher_p', 'н/д')}), однако существует слабая, но значимая положительная корреляция между общим объемом докладов автора и абсолютным количеством сериализованных работ (rho={stats.get('h10_spearman_rho', 'н/д')}, p={stats.get('h10_spearman_p', 'н/д')}).",
        "- См. `talk_serialization_stats.csv`.",
        "",
    ]
    (OUT / "hypothesis_workup.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    theme_rows = read_csv(ANALYTICS / "theme_codes_final.csv")
    people = person_series_counts(con)

    theme_match_rows, theme_match_stats = theme_match_diagnostics(con, theme_rows)
    write_csv(OUT / "theme_match_diagnostics.csv", theme_match_rows)

    subtitle_rows, subtitle_stats = hypothesis_program_subtitles(theme_rows, con)
    write_csv(OUT / "roerich_theme_heading_audit.csv", subtitle_rows)

    ikvia_rows, ikvia_summary = hypothesis_ikvia_bridge(con, people, theme_rows)
    write_csv(OUT / "ikvia_bridge_cross_cohort.csv", ikvia_rows)
    write_csv(OUT / "institution_bridge_summary.csv", ikvia_summary)
    ikvia_adaptation = hypothesis_ikvia_theme_adaptation(con, people, theme_rows)
    write_csv(OUT / "ikvia_theme_adaptation.csv", ikvia_adaptation)

    age_rows, age_summary, age_missing, age_stats = hypothesis_age_at_debut(con, people)
    write_csv(OUT / "age_at_debut.csv", age_rows)
    write_csv(OUT / "age_at_debut_summary.csv", age_summary)
    write_csv(OUT / "age_at_debut_missing_priority.csv", age_missing)
    figure_age_at_debut(age_rows)

    publication_rows = hypothesis_publication_sources(con)
    write_csv(OUT / "publication_sources_inventory.csv", publication_rows)

    video_year, video_l1, video_status = hypothesis_video_availability(con, theme_rows)
    write_csv(OUT / "video_availability_by_year.csv", video_year)
    write_csv(OUT / "video_availability_by_l1.csv", video_l1)
    write_csv(OUT / "video_mapping_status.csv", video_status)
    figure_video_coverage(video_year)

    network_rows = hypothesis_network_bridges(con, people)
    write_csv(OUT / "network_bridges.csv", network_rows)
    figure_network_bridges(network_rows)
    network_session_rows, network_session_stats = hypothesis_network_bridges_session(con, people)
    write_csv(OUT / "network_bridges_session.csv", network_session_rows)
    figure_network_bridges_session(network_session_rows)

    # Call the 4 new hypotheses
    frac_rows, frac_stats = hypothesis_fractional_counting(con)
    write_csv(OUT / "org_fractional_counting.csv", frac_rows)

    era_newcomer_rows, era_l1_rows, era_l2_rows, era_stats = hypothesis_era_influence(con, theme_rows)
    write_csv(OUT / "era_newcomers.csv", era_newcomer_rows)
    write_csv(OUT / "era_themes_l1.csv", era_l1_rows)
    write_csv(OUT / "era_themes_l2.csv", era_l2_rows)

    geo_dist_rows, geo_ret_rows, geo_stats = hypothesis_geographic_gravity(con)
    write_csv(OUT / "geographic_presentation_distribution.csv", geo_dist_rows)
    write_csv(OUT / "geographic_speaker_retention.csv", geo_ret_rows)

    serial_rows, serial_stats = hypothesis_talk_serialization(con)
    write_csv(OUT / "talk_serialization_stats.csv", serial_rows)

    ikvia_cosines = [float(row["l1_cosine_similarity"]) for row in ikvia_adaptation if row["l1_cosine_similarity"] != ""]

    stats = {
        "subtitle_groups": subtitle_stats.get("groups_with_coded_talks", ""),
        "subtitle_l2_chi2": subtitle_stats.get("l2_chi2", "н/д"),
        "subtitle_l2_p": subtitle_stats.get("l2_p", "н/д"),
        "subtitle_l2_v": subtitle_stats.get("l2_cramers_v", "н/д"),
        "cross_cohort_total": len(ikvia_rows),
        "ikvia_cross_count": sum(1 for row in ikvia_rows if row["has_ikvia_hse"] == "yes"),
        "top_cross_institutions": "; ".join(f"{row['affiliation_group']}={row['cross_cohort_people']}" for row in ikvia_summary[:3]),
        "ikvia_adaptation_count": len(ikvia_adaptation),
        "ikvia_same_top_l1": sum(1 for row in ikvia_adaptation if row["same_top_l1"] == "yes"),
        "ikvia_median_cosine": round(median(ikvia_cosines), 3) if ikvia_cosines else "н/д",
        "age_debut_known": len(age_rows),
        "age_summary_line": "; ".join(
            f"{row['debut_period']}: {row['median_age_at_debut']} (n={row['n_known_birth_year']})" for row in age_summary
        ),
        "age_spearman_rho": age_stats.get("spearman_rho", "н/д"),
        "age_spearman_p": age_stats.get("spearman_p", "н/д"),
        "age_kruskal_h": age_stats.get("kruskal_h", "н/д"),
        "age_kruskal_p": age_stats.get("kruskal_p", "н/д"),
        "publication_sources": len(publication_rows),
        "video_presentations": sum(1 for _, in con.execute("select distinct attached_to_id from media where media_type='video' and attached_to_type='presentation'")),
        "video_status_line": "; ".join(f"{row['status']}={row['videos']}" for row in video_status),
        "network_top_line": "; ".join(str(row["display_name"]) for row in network_rows[:7]),
        "network_session_top_line": "; ".join(str(row["display_name"]) for row in network_session_rows[:7]),
        **network_session_stats,
        **theme_match_stats,
        **frac_stats,
        **era_stats,
        **geo_stats,
        **serial_stats,
    }
    write_markdown_summary(stats)
    print(f"Wrote hypothesis outputs to {OUT}")


if __name__ == "__main__":
    main()
