"""Build a current numeric snapshot for the PPV article.

The article is prose, so this script deliberately does not rewrite it.  It
extracts the current canonical counts from `conferences.db`, writes a small
Markdown/JSON snapshot, and reports likely stale numeric strings in
`article/ppv_draft.md` for manual synchronization.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "conferences.db"
ARTICLE = ROOT / "article" / "ppv_draft.md"
OUT = ROOT / "article" / "hypothesis_output"


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
    return (n + 1 - 2 * weighted / total) / n


def series_counts(con: sqlite3.Connection, where_sql: str = "") -> dict[str, dict[str, float]]:
    rows = con.execute(
        f"""
        select
            es.series_name_en,
            pp.person_id,
            pr.presentation_id
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
        series = "Zograf" if "Zograf" in series_name else "Roerich"
        by_series[series][person_id] += 1
        presentations[series].add(presentation_id)

    out: dict[str, dict[str, float]] = {}
    for series, counter in by_series.items():
        values = list(counter.values())
        one_timers = sum(1 for value in values if value == 1)
        core = sum(1 for value in values if value >= 5)
        out[series] = {
            "unique_scholars": len(counter),
            "presentations": len(presentations[series]),
            "author_participations": sum(values),
            "one_talk_share_pct": pct(one_timers, len(values)),
            "core_share_pct": pct(core, len(values)),
            "retention_pct": pct(len(values) - one_timers, len(values)),
            "gini": round(gini(values), 3),
            "median_talks": sorted(values)[len(values) // 2] if values else 0,
            "max_talks": max(values) if values else 0,
        }
    return out


def person_count_stats(values: list[int]) -> dict[str, float]:
    one_timers = sum(1 for value in values if value == 1)
    core = sum(1 for value in values if value >= 5)
    return {
        "unique_scholars": len(values),
        "author_participations": sum(values),
        "one_talk_share_pct": pct(one_timers, len(values)),
        "core_share_pct": pct(core, len(values)),
        "retention_pct": pct(len(values) - one_timers, len(values)),
        "gini": round(gini(values), 3),
        "median_talks": sorted(values)[len(values) // 2] if values else 0,
        "max_talks": max(values) if values else 0,
    }


def build_snapshot() -> dict[str, object]:
    con = sqlite3.connect(DB)
    all_series = series_counts(con)
    z_until_2025 = series_counts(
        con,
        "where es.series_name_en='Zograf Readings' and e.year <= 2025",
    )["Zograf"]
    combined_values = [
        row[0]
        for row in con.execute(
            "select count(*) from presentation_person group by person_id"
        ).fetchall()
    ]

    people_by_series = {
        "Zograf": {
            row[0]
            for row in con.execute(
                """
                select distinct pp.person_id
                from presentation_person pp
                join presentation pr using(presentation_id)
                join session s using(session_id)
                join event_day_venue edv using(event_day_venue_id)
                join event_day ed using(event_day_id)
                join event e using(event_id)
                join event_series es using(event_series_id)
                where es.series_name_en='Zograf Readings'
                """
            )
        },
        "Roerich": {
            row[0]
            for row in con.execute(
                """
                select distinct pp.person_id
                from presentation_person pp
                join presentation pr using(presentation_id)
                join session s using(session_id)
                join event_day_venue edv using(event_day_venue_id)
                join event_day ed using(event_day_id)
                join event e using(event_id)
                join event_series es using(event_series_id)
                where es.series_name_en='Roerich Readings'
                """
            )
        },
    }
    overlap = people_by_series["Zograf"] & people_by_series["Roerich"]

    zograf_2026 = con.execute(
        """
        select count(distinct pr.presentation_id), count(distinct pp.person_id), count(*)
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

    snapshot = {
        "total": {
            "unique_scholars": con.execute("select count(distinct person_id) from presentation_person").fetchone()[0],
            "person_table_rows": con.execute("select count(*) from person").fetchone()[0],
            "presentations": con.execute("select count(*) from presentation").fetchone()[0],
            "author_participations": con.execute("select count(*) from presentation_person").fetchone()[0],
            "known_birth_years": con.execute(
                "select count(distinct pp.person_id) from presentation_person pp join person p using(person_id) where p.birth_year is not null and trim(p.birth_year)!=''"
            ).fetchone()[0],
            "cross_cohort": len(overlap),
            "zograf_only": len(people_by_series["Zograf"] - people_by_series["Roerich"]),
            "roerich_only": len(people_by_series["Roerich"] - people_by_series["Zograf"]),
        },
        "combined_activity": person_count_stats(combined_values),
        "series": all_series,
        "zograf_until_2025": z_until_2025,
        "zograf_2026": {
            "presentations": zograf_2026[0],
            "unique_scholars": zograf_2026[1],
            "author_participations": zograf_2026[2],
        },
    }
    return snapshot


def stale_candidates(article_text: str) -> list[dict[str, object]]:
    replacements = {
        "226": "220",
        "171": "167",
        "94": "91",
        "39": "38",
        "30.9": "31.9",
        "23.4": "24.0",
        "46.2": "43.7",
        "39.4": "38.5",
        "53.8": "56.3",
        "60.6": "61.5",
        "152": "148",
        "25.0": "25.7",
        "42.8": "39.9",
        "57.2": "60.1",
        "0.450": "0.444",
        "0.459": "0.470",
        "0.465": "0.461",
        "0.487": "0.510",
    }
    allowed_contexts = (
        "061.3:94(540)",
        "| 2016 |",
    )
    findings = []
    lines = article_text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        if any(context in line for context in allowed_contexts):
            continue
        for old, new in replacements.items():
            if re.search(rf"(?<![\d.,]){re.escape(old)}(?![\d.,])", line):
                findings.append({"line": line_no, "old": old, "suggested": new, "text": line.strip()})
    return findings


def write_outputs(snapshot: dict[str, object], findings: list[dict[str, object]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ppv_numbers_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = snapshot["total"]
    combined = snapshot["combined_activity"]
    series = snapshot["series"]
    z2025 = snapshot["zograf_until_2025"]
    z2026 = snapshot["zograf_2026"]
    lines = [
        "# PPV Numbers Snapshot",
        "",
        "Generated by `article/check_ppv_numbers.py` from `conferences.db`.",
        "",
        "## Canonical Counts",
        "",
        f"1. Unique scholars with presentations: {total['unique_scholars']}.",
        f"2. Presentations: {total['presentations']}.",
        f"3. Author participations: {total['author_participations']}.",
        f"4. Known birth years: {total['known_birth_years']}.",
        f"5. Cross-cohort scholars: {total['cross_cohort']}.",
        f"6. Zograf-only scholars: {total['zograf_only']}.",
        f"7. Roerich-only scholars: {total['roerich_only']}.",
        f"8. Combined one-talk share: {combined['one_talk_share_pct']}%.",
        f"9. Combined core share >=5: {combined['core_share_pct']}%.",
        f"10. Combined retention: {combined['retention_pct']}%.",
        f"11. Combined Gini: {combined['gini']}.",
        f"12. Combined max talks per scholar: {combined['max_talks']}.",
        "",
        "## Series Counts",
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
        "## Censoring Checks",
        "",
        f"1. Zograf through 2025: {z2025['unique_scholars']} scholars, {z2025['presentations']} presentations, {z2025['author_participations']} author participations.",
        f"2. Zograf through 2025 core share: {z2025['core_share_pct']}%.",
        f"3. Zograf through 2025 one-talk share: {z2025['one_talk_share_pct']}%.",
        f"4. Zograf through 2025 retention: {z2025['retention_pct']}%.",
        f"5. Zograf 2026 preliminary programme: {z2026['presentations']} presentations, {z2026['unique_scholars']} scholars, {z2026['author_participations']} author participations.",
        "",
        "## Candidate Stale Mentions",
        "",
    ]
    if findings:
        for item in findings:
            lines.append(
                f"- Line {item['line']}: `{item['old']}` -> `{item['suggested']}`? {item['text']}"
            )
    else:
        lines.append("- No candidate stale mentions found.")
    lines.append("")
    (OUT / "ppv_numbers_snapshot.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    snapshot = build_snapshot()
    article_text = ARTICLE.read_text(encoding="utf-8")
    findings = stale_candidates(article_text)
    write_outputs(snapshot, findings)
    print(f"Wrote {OUT / 'ppv_numbers_snapshot.md'}")
    print(f"Wrote {OUT / 'ppv_numbers_snapshot.json'}")
    print(f"Candidate stale mentions: {len(findings)}")


if __name__ == "__main__":
    main()
