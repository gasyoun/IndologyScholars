"""Check that the PPV article's numbers match the current data.

Builds a comprehensive snapshot from ``conferences.db`` and
``analytics_output/expanded_classification_deepseek.csv`` (G-scale and
theme counts), then verifies every number in
``article/ppv_submission_article.md`` against it via phrase-based regexes.

The script is non-mutating: it does not rewrite the article. It prints a
drift report (and writes one to ``article/hypothesis_output/``) and exits
non-zero on any mismatch so the pre-submission gate fails until the
article is synchronised. Issue #12 replaces the old hardcoded
``replacements`` list (which was pinned to very old values like 220/895
and missed any newer drift).
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "conferences.db"
CLASS_CSV = ROOT / "analytics_output" / "expanded_classification_deepseek.csv"
ARTICLES = [ROOT / "article" / "ppv_submission_article.md"]
OUT = ROOT / "article" / "hypothesis_output"


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def pct(n: int | float, d: int | float, digits: int = 1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def gini(values: list[int]) -> float:
    xs = sorted(float(v) for v in values)
    n = len(xs)
    total = sum(xs)
    if not n or not total:
        return 0.0
    cumulative = 0.0
    weighted = 0.0
    for value in xs:
        cumulative += value
        weighted += cumulative
    return round((n + 1 - 2 * weighted / total) / n, 3)


def series_block(con: sqlite3.Connection, where_sql: str = "") -> dict[str, dict[str, float]]:
    rows = con.execute(
        f"""
        select es.series_name_en, pp.person_id, pr.presentation_id
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        {where_sql}
        """
    ).fetchall()
    by_series: dict[str, Counter[str]] = {"Zograf": Counter(), "Roerich": Counter()}
    presentations: dict[str, set[str]] = {"Zograf": set(), "Roerich": set()}
    for series_name, person_id, presentation_id in rows:
        key = "Zograf" if "Zograf" in series_name else "Roerich"
        by_series[key][person_id] += 1
        presentations[key].add(presentation_id)

    out: dict[str, dict[str, float]] = {}
    for key, counter in by_series.items():
        values = list(counter.values())
        one_timers = sum(1 for v in values if v == 1)
        core = sum(1 for v in values if v >= 5)
        out[key] = {
            "unique_scholars": len(counter),
            "presentations": len(presentations[key]),
            "author_participations": sum(values),
            "one_talk_share_pct": pct(one_timers, len(values)),
            "core_share_pct": pct(core, len(values)),
            "retention_pct": pct(len(values) - one_timers, len(values)),
            "gini": gini(values),
        }
    return out


def combined_block(con: sqlite3.Connection) -> dict[str, float]:
    values = [
        row[0]
        for row in con.execute(
            "select count(*) from presentation_person group by person_id"
        ).fetchall()
    ]
    one_timers = sum(1 for v in values if v == 1)
    core = sum(1 for v in values if v >= 5)
    return {
        "one_talk_share_pct": pct(one_timers, len(values)),
        "core_share_pct": pct(core, len(values)),
        "retention_pct": pct(len(values) - one_timers, len(values)),
        "gini": gini(values),
    }


def classification_blocks() -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Return (g_levels, theme_counts_by_series)."""
    g: Counter[str] = Counter()
    themes: dict[str, Counter[str]] = {"Zograf": Counter(), "Roerich": Counter()}
    if not CLASS_CSV.exists():
        return dict(g), {k: dict(v) for k, v in themes.items()}
    with open(CLASS_CSV, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            level = row.get("gumilyov_level", "").strip()
            if level:
                g[level] += 1
            series_label = row.get("series", "")
            bucket = "Zograf" if "Zograf" in series_label else "Roerich" if "Roerich" in series_label else None
            theme = row.get("theme_l1", "").strip()
            if bucket and theme:
                themes[bucket][theme] += 1
    return dict(g), {k: dict(v) for k, v in themes.items()}


def build_snapshot() -> dict[str, object]:
    con = sqlite3.connect(str(DB))
    series = series_block(con)
    zog_until_2025 = series_block(
        con, "where es.series_name_en='Zograf Readings' and e.year <= 2025"
    )["Zograf"]
    zog_2026_row = con.execute(
        """
        select count(distinct pr.presentation_id),
               count(distinct pp.person_id),
               count(*)
        from presentation_person pp
        join presentation pr using(presentation_id)
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        where es.series_name_en='Zograf Readings' and e.year=2026
        """
    ).fetchone()
    overlap = con.execute(
        """
        select count(*) from (
            select pp.person_id
            from presentation_person pp
            join presentation pr using(presentation_id)
            join session s using(session_id)
            join event_day_venue edv using(event_day_venue_id)
            join event_day ed using(event_day_id)
            join event e using(event_id)
            join event_series es using(event_series_id)
            group by pp.person_id
            having sum(case when es.series_name_en='Zograf Readings' then 1 else 0 end) > 0
               and sum(case when es.series_name_en='Roerich Readings' then 1 else 0 end) > 0
        )
        """
    ).fetchone()[0]
    only_zograf = con.execute(
        """
        select count(*) from (
            select pp.person_id
            from presentation_person pp
            join presentation pr using(presentation_id)
            join session s using(session_id)
            join event_day_venue edv using(event_day_venue_id)
            join event_day ed using(event_day_id)
            join event e using(event_id)
            join event_series es using(event_series_id)
            group by pp.person_id
            having sum(case when es.series_name_en='Zograf Readings' then 1 else 0 end) > 0
               and sum(case when es.series_name_en='Roerich Readings' then 1 else 0 end) = 0
        )
        """
    ).fetchone()[0]
    only_roerich = con.execute(
        """
        select count(*) from (
            select pp.person_id
            from presentation_person pp
            join presentation pr using(presentation_id)
            join session s using(session_id)
            join event_day_venue edv using(event_day_venue_id)
            join event_day ed using(event_day_id)
            join event e using(event_id)
            join event_series es using(event_series_id)
            group by pp.person_id
            having sum(case when es.series_name_en='Zograf Readings' then 1 else 0 end) = 0
               and sum(case when es.series_name_en='Roerich Readings' then 1 else 0 end) > 0
        )
        """
    ).fetchone()[0]

    total = {
        "unique_scholars": con.execute(
            "select count(distinct person_id) from presentation_person"
        ).fetchone()[0],
        "presentations": con.execute(
            "select count(*) from presentation"
        ).fetchone()[0],
        "author_participations": con.execute(
            "select count(*) from presentation_person"
        ).fetchone()[0],
        "known_birth_years": con.execute(
            "select count(distinct pp.person_id) from presentation_person pp "
            "join person p using(person_id) "
            "where p.birth_year is not null and trim(cast(p.birth_year as text))!=''"
        ).fetchone()[0],
        "cross_cohort": overlap,
        "zograf_only": only_zograf,
        "roerich_only": only_roerich,
        "events": con.execute("select count(*) from event").fetchone()[0],
        "program_years": con.execute(
            "select count(distinct e.year) from event e "
            "join event_day ed using(event_id) "
            "join event_day_venue edv using(event_day_id) "
            "join session s using(event_day_venue_id) "
            "join presentation pr using(session_id)"
        ).fetchone()[0],
    }

    cross_cohort_pct = pct(total["cross_cohort"], total["unique_scholars"])

    g_levels, theme_counts = classification_blocks()

    snapshot = {
        "total": total,
        "cross_cohort_pct": cross_cohort_pct,
        "combined_activity": combined_block(con),
        "series": series,
        "zograf_until_2025": zog_until_2025,
        "zograf_2026": {
            "presentations": zog_2026_row[0],
            "unique_scholars": zog_2026_row[1],
            "author_participations": zog_2026_row[2],
        },
        "g_levels": g_levels,
        "theme_counts": theme_counts,
    }
    return snapshot


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def _parse_number(s: str) -> int | float | None:
    s = s.replace(",", "").replace(" ", "")
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return None


def check(label: str, regex: str, expected, text: str, *, flags: int = 0) -> list[dict]:
    drifts = []
    for m in re.finditer(regex, text, flags=flags):
        s = m.group(1)
        n = _parse_number(s)
        if n is None:
            continue
        if isinstance(expected, float) or isinstance(n, float):
            ok = abs(float(n) - float(expected)) < 0.05
        else:
            ok = n == expected
        if not ok:
            line_no = text[: m.start()].count("\n") + 1
            ctx = text[max(0, m.start() - 30): min(len(text), m.end() + 35)].replace("\n", " ").strip()
            drifts.append(
                {
                    "label": label,
                    "expected": expected,
                    "found": n,
                    "line": line_no,
                    "context": ctx,
                }
            )
    return drifts


def find_drifts(text: str, snap: dict[str, object]) -> list[dict]:
    T = snap["total"]                        # type: ignore[index]
    S = snap["series"]                       # type: ignore[index]
    Z25 = snap["zograf_until_2025"]          # type: ignore[index]
    Z26 = snap["zograf_2026"]                # type: ignore[index]
    C = snap["combined_activity"]            # type: ignore[index]
    G = snap["g_levels"]                     # type: ignore[index]
    cross_pct = snap["cross_cohort_pct"]     # type: ignore[index]

    out: list[dict] = []

    # --- Totals (multiple phrasings) ---
    out += check("Total unique scholars (prose)",
        r"(\d[\d,]*)\s+(?:уникальных\s+)?ученых\s+за", T["unique_scholars"], text)
    out += check("Total unique scholars (RU 'и N ученых')",
        r"участий\s+и\s+(\d[\d,]*)\s+ученых", T["unique_scholars"], text)
    out += check("Total unique scholars (EN)",
        r"and\s+(\d[\d,]*)\s+scholars\s+for", T["unique_scholars"], text)
    out += check("Total unique scholars (methods 'В корпус')",
        r"В\s+устный\s+корпус\s+вошли\s+(\d[\d,]*)\s+уникальных\s+ученых", T["unique_scholars"], text)
    out += check("Total presentations (RU 'корпус включает')",
        r"корпус\s+включает\s+(\d[\d,]*)\s+докладов", T["presentations"], text)
    out += check("Total presentations (EN 'contains X presentations')",
        r"contains\s+(\d[\d,]*)\s+presentations", T["presentations"], text)
    out += check("Total presentations (RU 'X уникальных докладов')",
        r"(\d[\d,]*)\s+уникальных\s+докладов", T["presentations"], text)
    out += check("Total presentations (EN 'X of Y presentations')",
        r"of\s+(\d[\d,]*)\s+presentations\s+are", T["presentations"], text)
    # Anchored to specific Total-context phrasings to avoid matching the censored block.
    out += check("Total author participations (RU, abstract)",
        r"(\d[\d,]*)\s+авторских\s+участий\s+и\s+\d+\s+ученых",
        T["author_participations"], text)
    out += check("Total author participations (RU, methods)",
        r"уникальных\s+докладов\s+и\s+(\d[\d,]*)\s+авторских\s+участий",
        T["author_participations"], text)
    out += check("Total author participations (EN)",
        r"(\d[\d,]*)\s+author\s+participations", T["author_participations"], text)
    out += check("Cross-cohort (RU 'выступал только X')",
        r"выступал\s+только\s+(\d+)\s+ученый", T["cross_cohort"], text)
    out += check("Cross-cohort (EN 'only X scholars appeared')",
        r"only\s+(\d+)\s+scholars\s+appeared", T["cross_cohort"], text)
    out += check("Cross-cohort (RU 'X человек выступал')",
        r"(\d+)\s+человек\s+выступал\s+на\s+обеих", T["cross_cohort"], text)
    out += check("Cross-cohort % (RU 'или X%')",
        r"только\s+\d+,\s*или\s+(\d+\.?\d*)%", cross_pct, text)

    # --- Events / program years (stable but verify) ---
    out += check("Event records",
        r"включены\s+(\d+)\s+событийных\s+записей", T["events"], text)
    out += check("Program-years coverage",
        r"составляет\s+(\d+)\s+программных\s+года", T["program_years"], text)

    # --- Zograf 2026 preliminary ---
    out += check("Zograf 2026 declared presentations",
        r"(\d+)\s+заявленных\s+докладов", Z26["presentations"], text)
    out += check("Zograf 2026 author participations",
        r"и\s+(\d+)\s+авторское\s+участие", Z26["author_participations"], text)

    # --- Per-series (prose, § 3) ---
    out += check("Zograf presentations (prose)",
        r"Зографские\s+чтения\s+дают\s+(\d+)\s+докладов", S["Zograf"]["presentations"], text)
    out += check("Roerich presentations (prose)",
        r"Рериховские\s+-\s+(\d+)\.", S["Roerich"]["presentations"], text)
    out += check("Zograf unique scholars (prose '… ученый видим на Зографских')",
        r"(\d+)\s+ученый\s+видим\s+на\s+Зографских", S["Zograf"]["unique_scholars"], text)
    out += check("Roerich unique scholars (prose 'и X - на Рериховских')",
        r"чтениях\s+и\s+(\d+)\s+-\s+на\s+Рериховских", S["Roerich"]["unique_scholars"], text)

    # Derived: 221 + 106 = 327 — totally derived from per-series; auto-recompute
    sum_series_scholars = S["Zograf"]["unique_scholars"] + S["Roerich"]["unique_scholars"]
    out += check("Sum of per-series scholars (derived)",
        r"число\s+уникальных\s+ученых\s+не\s+равно\s+(\d+)", sum_series_scholars, text)

    # --- Series table (markdown row cells, in order Zograf | Roerich | Total) ---
    # Be conservative: only check rows where a known label is on the left.
    series_total_scholars = T["unique_scholars"]
    series_total_pres = T["presentations"]
    series_total_part = T["author_participations"]
    out += check("Table: Уникальные ученые (Zograf)",
        r"\|\s*Уникальные\s+ученые\s*\|\s*(\d+)\s*\|", S["Zograf"]["unique_scholars"], text)
    out += check("Table: Уникальные ученые (Roerich)",
        r"\|\s*Уникальные\s+ученые\s*\|\s*\d+\s*\|\s*(\d+)\s*\|", S["Roerich"]["unique_scholars"], text)
    out += check("Table: Уникальные ученые (Total)",
        r"\|\s*Уникальные\s+ученые\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|", series_total_scholars, text)
    out += check("Table: Уникальные доклады (Zograf)",
        r"\|\s*Уникальные\s+доклады\s*\|\s*(\d+)\s*\|", S["Zograf"]["presentations"], text)
    out += check("Table: Уникальные доклады (Roerich)",
        r"\|\s*Уникальные\s+доклады\s*\|\s*\d+\s*\|\s*(\d+)\s*\|", S["Roerich"]["presentations"], text)
    out += check("Table: Уникальные доклады (Total)",
        r"\|\s*Уникальные\s+доклады\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|", series_total_pres, text)
    out += check("Table: Авторские участия (Zograf)",
        r"\|\s*Авторские\s+участия\s*\|\s*(\d+)\s*\|", S["Zograf"]["author_participations"], text)
    out += check("Table: Авторские участия (Roerich)",
        r"\|\s*Авторские\s+участия\s*\|\s*\d+\s*\|\s*(\d+)\s*\|", S["Roerich"]["author_participations"], text)
    out += check("Table: Авторские участия (Total)",
        r"\|\s*Авторские\s+участия\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|", series_total_part, text)
    out += check("Table: Доля разовых участников, % (Zograf)",
        r"\|\s*Доля\s+разовых\s+участников,\s*%\s*\|\s*(\d+\.\d+)\s*\|",
        S["Zograf"]["one_talk_share_pct"], text)
    out += check("Table: Доля разовых участников, % (Roerich)",
        r"\|\s*Доля\s+разовых\s+участников,\s*%\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        S["Roerich"]["one_talk_share_pct"], text)
    out += check("Table: Доля разовых участников, % (Total)",
        r"\|\s*Доля\s+разовых\s+участников,\s*%\s*\|\s*\d+\.\d+\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        C["one_talk_share_pct"], text)
    out += check("Table: Доля ядра, % (Zograf)",
        r"\|\s*Доля\s+ядра[^|]*\|\s*(\d+\.\d+)\s*\|",
        S["Zograf"]["core_share_pct"], text)
    out += check("Table: Доля ядра, % (Roerich)",
        r"\|\s*Доля\s+ядра[^|]*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        S["Roerich"]["core_share_pct"], text)
    out += check("Table: Доля ядра, % (Total)",
        r"\|\s*Доля\s+ядра[^|]*\|\s*\d+\.\d+\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        C["core_share_pct"], text)
    out += check("Table: Удержание, % (Zograf)",
        r"\|\s*Удержание,\s*%\s*\|\s*(\d+\.\d+)\s*\|",
        S["Zograf"]["retention_pct"], text)
    out += check("Table: Удержание, % (Roerich)",
        r"\|\s*Удержание,\s*%\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        S["Roerich"]["retention_pct"], text)
    out += check("Table: Удержание, % (Total)",
        r"\|\s*Удержание,\s*%\s*\|\s*\d+\.\d+\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        C["retention_pct"], text)
    out += check("Table: Индекс Джини (Zograf)",
        r"\|\s*Индекс\s+Джини\s*\|\s*(\d+\.\d+)\s*\|",
        S["Zograf"]["gini"], text)
    out += check("Table: Индекс Джини (Roerich)",
        r"\|\s*Индекс\s+Джини\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        S["Roerich"]["gini"], text)
    out += check("Table: Индекс Джини (Total)",
        r"\|\s*Индекс\s+Джини\s*\|\s*\d+\.\d+\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)\s*\|",
        C["gini"], text)

    # --- Right-censoring Zograf 2025 block ---
    out += check("Zograf-2025 unique scholars (censored)",
        r"Зографские\s+чтения\s+дают\s+(\d+)\s+ученых", Z25["unique_scholars"], text)
    out += check("Zograf-2025 presentations (censored)",
        r"ученых,\s+(\d+)\s+докладов", Z25["presentations"], text)
    # Anchored to censored phrasing ("X ученых, Y докладов и Z авторских") which lacks "уникальных"
    # before "докладов", so it does not match the Methods total phrasing.
    out += check("Zograf-2025 author participations (censored)",
        r"ученых,\s+\d+\s+докладов\s+и\s+(\d+)\s+авторских\s+участий",
        Z25["author_participations"], text)
    out += check("Zograf-2025 core share %",
        r"Доля\s+ядра\s+тогда\s+составляет\s+(\d+\.\d+)%", Z25["core_share_pct"], text)
    out += check("Zograf-2025 one-talk share %",
        r"доля\s+разовых\s+участников\s+-\s+(\d+\.\d+)%", Z25["one_talk_share_pct"], text)
    out += check("Zograf-2025 retention %",
        r"удержание\s+-\s+(\d+\.\d+)%", Z25["retention_pct"], text)
    out += check("Zograf-2025 Gini",
        r"индекс\s+Джини\s+-\s+(\d+\.\d+)", Z25["gini"], text)

    # --- G-scale (1155 / 185 / 10) ---
    if "1" in G:
        out += check("G1 micro-cases (prose 'X из ...')",
            r"(\d[\d,]*)\s+из\s+\d[\d,]*\s+(?:уникальных\s+)?докладов\s+(?:являются\s+микрокейсами|относятся\s+к\s+G1)",
            G["1"], text)
        out += check("G1 micro-cases (EN '1,155 of 1,350')",
            r"that\s+(\d[\d,]*)\s+of\s+\d[\d,]*\s+presentations\s+are\s+micro",
            G["1"], text)
    if "2" in G:
        out += check("G2 traditions/schools (prose)",
            r"G2\s+включает\s+(\d+)\s+докладов", G["2"], text)
    if "3" in G:
        out += check("G3 broad generalisations (prose)",
            r"G3\s+-\s+только\s+(\d+)\.", G["3"], text)

    # --- G1 denominator ('из 1350') ---
    out += check("G1 denominator (RU 'из X')",
        r"из\s+(\d[\d,]*)\s+(?:уникальных\s+)?докладов\s+(?:являются\s+микрокейсами|относятся\s+к\s+G1)",
        T["presentations"], text)
    out += check("G1 denominator (EN 'of X presentations')",
        r"of\s+(\d[\d,]*)\s+presentations\s+are\s+micro", T["presentations"], text)

    # Strip duplicates: same label + same line + same expected/found
    seen = set()
    uniq: list[dict] = []
    for d in out:
        key = (d["label"], d["line"], d["expected"], d["found"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    uniq.sort(key=lambda d: (d["line"], d["label"]))
    return uniq


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_snapshot_and_report(snap: dict, drifts: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ppv_numbers_snapshot.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = snap["total"]
    series = snap["series"]
    z25 = snap["zograf_until_2025"]
    z26 = snap["zograf_2026"]
    g = snap["g_levels"]
    lines = [
        "# PPV Numbers Snapshot",
        "",
        "Generated by `article/check_ppv_numbers.py` from `conferences.db` and "
        "`analytics_output/expanded_classification_deepseek.csv`.",
        "",
        "## Totals",
        "",
        f"- Unique scholars (with presentations): **{total['unique_scholars']}**",
        f"- Presentations: **{total['presentations']}**",
        f"- Author participations: **{total['author_participations']}**",
        f"- Known birth years: **{total['known_birth_years']}**",
        f"- Cross-cohort scholars: **{total['cross_cohort']}** ({snap['cross_cohort_pct']}%)",
        f"- Zograf-only: **{total['zograf_only']}**; Roerich-only: **{total['roerich_only']}**",
        f"- Events: {total['events']}; Program-years (with presentations): {total['program_years']}",
        "",
        "## Series",
        "",
        "| Metric | Zograf | Roerich |",
        "|---|---:|---:|",
        f"| Unique scholars | {series['Zograf']['unique_scholars']} | {series['Roerich']['unique_scholars']} |",
        f"| Presentations | {series['Zograf']['presentations']} | {series['Roerich']['presentations']} |",
        f"| Author participations | {series['Zograf']['author_participations']} | {series['Roerich']['author_participations']} |",
        f"| One-talk share, % | {series['Zograf']['one_talk_share_pct']} | {series['Roerich']['one_talk_share_pct']} |",
        f"| Core share >=5, % | {series['Zograf']['core_share_pct']} | {series['Roerich']['core_share_pct']} |",
        f"| Retention, % | {series['Zograf']['retention_pct']} | {series['Roerich']['retention_pct']} |",
        f"| Gini | {series['Zograf']['gini']} | {series['Roerich']['gini']} |",
        "",
        "## Censoring (Zograf through 2025)",
        "",
        f"- {z25['unique_scholars']} scholars, {z25['presentations']} presentations, "
        f"{z25['author_participations']} author participations",
        f"- Core share: {z25['core_share_pct']}%; One-talk: {z25['one_talk_share_pct']}%; "
        f"Retention: {z25['retention_pct']}%; Gini: {z25['gini']}",
        f"- Zograf 2026 preliminary: {z26['presentations']} presentations, "
        f"{z26['unique_scholars']} scholars, {z26['author_participations']} author participations",
        "",
        "## G-scale (from expanded_classification_deepseek.csv)",
        "",
        f"- G1 micro-cases: **{g.get('1', 0)}**",
        f"- G2 traditions/schools: **{g.get('2', 0)}**",
        f"- G3 broad generalisations: **{g.get('3', 0)}**",
        "",
        "## Article drifts (article numbers that do not match the snapshot above)",
        "",
    ]
    if drifts:
        for d in drifts:
            lines.append(
                f"- **line {d['line']}** · {d['label']} → expected `{d['expected']}`, "
                f"found `{d['found']}` · *…{d['context']}…*"
            )
    else:
        lines.append("_No drifts. Article numbers are in sync with the rebuilt data._")
    lines.append("")
    (OUT / "ppv_numbers_snapshot.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    snap = build_snapshot()
    drifts: list[dict] = []
    for article_path in ARTICLES:
        if article_path.exists():
            drifts.extend(find_drifts(article_path.read_text(encoding="utf-8"), snap))
    write_snapshot_and_report(snap, drifts)
    print(f"Wrote {OUT / 'ppv_numbers_snapshot.md'}")
    print(f"Wrote {OUT / 'ppv_numbers_snapshot.json'}")
    print(f"Article drifts: {len(drifts)}")
    for d in drifts:
        print(
            f"  line {d['line']:>3}  {d['label']:<48}  "
            f"expected {d['expected']!s:>8}  found {d['found']!s:>8}"
        )
    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
