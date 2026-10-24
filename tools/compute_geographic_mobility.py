#!/usr/bin/env python3
"""Geographic mobility formalisation (H2416 / Phase-2).

Recomputes:
  - multi-city programme speakers (city labels via geography.json aliases)
  - affiliation-string changers
  - SPb / Moscow / Regions talk distribution by series
  - speaker retention by home-city bucket

Does NOT invent moves: cities come only from programme affiliation text.
City ≠ institution (city-only labels are a known Zograf format artifact).

Usage:
  python tools/compute_geographic_mobility.py
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
GEO_PATH = ROOT / "assets" / "data" / "geography.json"
SITE_DATA = ROOT / "site_data.json"
OUT = ROOT / "analytics_output"

SPB_PATTERNS = re.compile(
    r"СПб|Санкт-Петербург|Ленинград|ИВР|МАЭ|Кунсткам|РХГА|ЕУСПб|ГМИР|РНБ|Герцен|С\.-Петербург|С\.-Петерб|Эрмитаж",
    re.I,
)
MOSCOW_PATTERNS = re.compile(
    r"Москва|МГУ|ИВ РАН|ВШЭ|ИКВИА|Высш|РГГУ|ИФ РАН|Институт философии|ИМЛИ|РУДН|ИСАА|ИЭА|этнологии и антропологии|ИЯз|ИЯ РАН|Институт языкознания|МГИМО|ПСТГУ|МГХПА|РГСУ|МПГУ|РАНХиГС|РХТУ|РГХПУ",
    re.I,
)


def load_city_aliases() -> list[tuple[str, str, str]]:
    if not GEO_PATH.exists():
        return []
    data = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    return [(item["keyword"], item["ru"], item["en"]) for item in data.get("city_aliases", [])]


def extract_city_ru(affiliation_text: str | None, aliases: list[tuple[str, str, str]]) -> str | None:
    if not affiliation_text:
        return None
    aff = affiliation_text.strip()
    if not aff or aff in ("Не указана", "Не указан"):
        return None
    aff_low = aff.lower()
    for keyword, ru, _en in aliases:
        if keyword in aff_low:
            return ru
    return None


def infer_bucket(affil: str | None) -> str:
    if not affil or not str(affil).strip():
        return "Unknown"
    if SPB_PATTERNS.search(affil):
        return "SPb"
    if MOSCOW_PATTERNS.search(affil):
        return "Moscow"
    return "Regions/Foreign"


def pct(n: float, d: float) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def load_site_scholars() -> list[dict]:
    if not SITE_DATA.exists():
        return []
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    if text.endswith(";"):
        text = text[:-1]
    data = json.loads(text)
    return data.get("scholars") or []


def multi_city_from_site(scholars: list[dict]) -> list[dict]:
    rows = []
    for s in scholars:
        cities = set()
        for t in s.get("talks") or []:
            g = t.get("geography") or {}
            c = g.get("ru") if isinstance(g, dict) else ""
            if c and c not in ("Не указана", "Не указан", ""):
                cities.add(c)
        if len(cities) < 2:
            continue
        rows.append(
            {
                "person_id": s.get("id") or "",
                "display_name": s.get("full_name_ru") or s.get("name") or "",
                "url_slug": s.get("url_slug") or "",
                "n_cities": len(cities),
                "cities": "; ".join(sorted(cities)),
                "has_changed_affiliations": "yes" if s.get("has_changed_affiliations") else "no",
                "total_talks": len(s.get("talks") or []),
            }
        )
    rows.sort(key=lambda r: (-int(r["n_cities"]), str(r["display_name"])))
    return rows


def aff_changers_from_site(scholars: list[dict]) -> list[dict]:
    rows = []
    for s in scholars:
        if not s.get("has_changed_affiliations"):
            continue
        affs = s.get("all_affiliations") or s.get("affiliations") or []
        if isinstance(affs, str):
            affs = [affs]
        rows.append(
            {
                "person_id": s.get("id") or "",
                "display_name": s.get("full_name_ru") or s.get("name") or "",
                "url_slug": s.get("url_slug") or "",
                "n_affiliations": len(affs),
                "affiliations": " | ".join(str(a) for a in affs[:12]),
            }
        )
    rows.sort(key=lambda r: (-int(r["n_affiliations"]), str(r["display_name"])))
    return rows


def gravity_from_db(con: sqlite3.Connection) -> tuple[list[dict], list[dict], dict]:
    zograf_cities: Counter = Counter()
    roerich_cities: Counter = Counter()
    speaker_city_years: dict[str, dict] = defaultdict(lambda: {"city": "Unknown", "years": set(), "name": ""})

    for year, series, pers_id, affil, dname, ru in con.execute(
        """
        SELECT e.year, es.series_name_en, pp.person_id, pp.affiliation_text_raw,
               p.display_name, p.full_name_ru
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        """
    ):
        city = infer_bucket(affil)
        if "Zograf" in (series or ""):
            zograf_cities[city] += 1
        else:
            roerich_cities[city] += 1
        speaker_city_years[pers_id]["name"] = ru or dname or pers_id
        speaker_city_years[pers_id]["years"].add(year)
        if speaker_city_years[pers_id]["city"] == "Unknown" or city != "Regions/Foreign":
            speaker_city_years[pers_id]["city"] = city

    total_z = sum(zograf_cities.values())
    total_r = sum(roerich_cities.values())
    dist = []
    for city in ["SPb", "Moscow", "Regions/Foreign"]:
        dist.append(
            {
                "city": city,
                "zograf_talks": zograf_cities[city],
                "zograf_pct": pct(zograf_cities[city], total_z),
                "roerich_talks": roerich_cities[city],
                "roerich_pct": pct(roerich_cities[city], total_r),
            }
        )

    survival = defaultdict(lambda: {"total": 0, "returning": 0})
    for info in speaker_city_years.values():
        city = info["city"]
        if city == "Unknown":
            continue
        survival[city]["total"] += 1
        if len(info["years"]) >= 2:
            survival[city]["returning"] += 1

    ret = []
    for city in ["Moscow", "SPb", "Regions/Foreign"]:
        tot = survival[city]["total"]
        retn = survival[city]["returning"]
        ret.append(
            {
                "city": city,
                "total_speakers": tot,
                "returning_speakers": retn,
                "retention_pct": pct(retn, tot),
            }
        )

    stats = {
        "zograf_talks_total": total_z,
        "roerich_talks_total": total_r,
        "unknown_bucket_talks": zograf_cities["Unknown"] + roerich_cities["Unknown"],
    }
    return dist, ret, stats


def multi_city_from_db(con: sqlite3.Connection, aliases: list[tuple[str, str, str]]) -> list[dict]:
    person_cities: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    talk_counts: Counter = Counter()
    for pid, dname, ru, aff in con.execute(
        """
        SELECT p.person_id, p.display_name, p.full_name_ru, pp.affiliation_text_raw
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        """
    ):
        names[pid] = ru or dname or pid
        talk_counts[pid] += 1
        city = extract_city_ru(aff, aliases)
        if city:
            person_cities[pid].add(city)
    rows = []
    for pid, cities in person_cities.items():
        if len(cities) < 2:
            continue
        rows.append(
            {
                "person_id": pid,
                "display_name": names.get(pid, pid),
                "url_slug": "",
                "n_cities": len(cities),
                "cities": "; ".join(sorted(cities)),
                "has_changed_affiliations": "",
                "total_talks": talk_counts[pid],
            }
        )
    rows.sort(key=lambda r: (-int(r["n_cities"]), str(r["display_name"])))
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    aliases = load_city_aliases()
    scholars = load_site_scholars()
    source = "site_data+db" if scholars else "db"

    if scholars:
        movers = multi_city_from_site(scholars)
        changers = aff_changers_from_site(scholars)
        n_scholars = len(scholars)
    else:
        movers, changers, n_scholars = [], [], 0

    dist, ret, gstats = [], [], {}
    if DB_PATH.exists():
        con = sqlite3.connect(str(DB_PATH))
        dist, ret, gstats = gravity_from_db(con)
        if not movers:
            movers = multi_city_from_db(con, aliases)
            n_scholars = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
            source = "db"
        con.close()
    else:
        print("WARN: conferences.db missing — gravity tables empty", file=sys.stderr)

    avg_cities = round(sum(int(r["n_cities"]) for r in movers) / len(movers), 1) if movers else 0.0
    summary = {
        "generated": date.today().isoformat(),
        "handoff": "H2416",
        "source": source,
        "n_scholars": n_scholars,
        "multi_city_movers": len(movers),
        "multi_city_pct": pct(len(movers), n_scholars),
        "affiliation_changers": len(changers),
        "affiliation_changer_pct": pct(len(changers), n_scholars),
        "avg_cities_among_movers": avg_cities,
        "gravity": gstats,
        "distribution": dist,
        "retention": ret,
        "notes": [
            "City labels are extracted from programme affiliation text only.",
            "City is not the same as employing institution.",
            "City-only affiliation is often a Zograf programme format artifact (paper H4).",
            "Retention = speakers with talks in ≥2 distinct years within their home-city bucket.",
        ],
    }

    write_csv(
        OUT / "geographic_mobility_movers.csv",
        movers,
        ["person_id", "display_name", "url_slug", "n_cities", "cities", "has_changed_affiliations", "total_talks"],
    )
    write_csv(
        OUT / "geographic_mobility_affiliation_changers.csv",
        changers,
        ["person_id", "display_name", "url_slug", "n_affiliations", "affiliations"],
    )
    write_csv(
        OUT / "geographic_mobility_distribution.csv",
        dist,
        ["city", "zograf_talks", "zograf_pct", "roerich_talks", "roerich_pct"],
    )
    write_csv(
        OUT / "geographic_mobility_retention.csv",
        ret,
        ["city", "total_speakers", "returning_speakers", "retention_pct"],
    )
    # Keep paper hypothesis paths in sync when we recompute
    hyp = ROOT / "article" / "hypothesis_output"
    if hyp.exists() and dist:
        write_csv(hyp / "geographic_presentation_distribution.csv", dist, ["city", "zograf_talks", "zograf_pct", "roerich_talks", "roerich_pct"])
        write_csv(hyp / "geographic_speaker_retention.csv", ret, ["city", "total_speakers", "returning_speakers", "retention_pct"])

    (OUT / "geographic_mobility_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"source={source} scholars={n_scholars}")
    print(f"multi_city_movers={len(movers)} ({summary['multi_city_pct']}%)")
    print(f"affiliation_changers={len(changers)} ({summary['affiliation_changer_pct']}%)")
    print(f"avg_cities_among_movers={avg_cities}")
    for d in dist:
        print(f"  dist {d['city']}: Z={d['zograf_talks']} ({d['zograf_pct']}%) R={d['roerich_talks']} ({d['roerich_pct']}%)")
    for r in ret:
        print(f"  ret  {r['city']}: {r['returning_speakers']}/{r['total_speakers']} ({r['retention_pct']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
