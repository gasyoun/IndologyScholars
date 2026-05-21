"""
Анализ онлайн/офлайн участия (H6: открыл ли онлайн новых лиц,
а потом вернул монополию старым?).

Выводы:
  analytics_output/online_share_by_year.csv — доля онлайн-докладов по годам/сериям
  analytics_output/online_repeaters_2020_plus.csv — кто регулярно "онлайн" с 2020+

Текущее состояние БД: pres.is_online устанавливается по наличию слова 'онлайн'
в строке программы. Это значит, что для COVID-2020 года, где ВСЯ конференция
проходила онлайн без поясняющих пометок, is_online=0 у каждого доклада. Это лакуна.
Корректируем: для event E2020 (Zograf 2020 — internet-trans) считаем все онлайн.
"""

import sys
import csv
import sqlite3
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

DB = "conferences.db"
OUT_DIR = "analytics_output"
FULLY_ONLINE_EVENTS = {"E2020"}  # explicit online-only years


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT es.series_name_en, e.event_id, e.year,
               pres.is_online, COUNT(*) AS n
          FROM event e
          JOIN event_series es ON es.event_series_id = e.event_series_id
          JOIN event_day ed ON ed.event_id = e.event_id
          JOIN event_day_venue edv ON edv.event_day_id = ed.event_day_id
          JOIN session s ON s.event_day_venue_id = edv.event_day_venue_id
          JOIN presentation pres ON pres.session_id = s.session_id
         GROUP BY es.series_name_en, e.event_id, e.year, pres.is_online
    """)
    rows = cur.fetchall()

    by_event = defaultdict(lambda: {"online": 0, "offline": 0, "year": 0, "series": ""})
    for series, ev_id, year, is_on, n in rows:
        by_event[ev_id]["year"] = year
        by_event[ev_id]["series"] = series
        if is_on:
            by_event[ev_id]["online"] += n
        else:
            by_event[ev_id]["offline"] += n

    # Apply COVID override for events listed as fully online
    for ev_id in FULLY_ONLINE_EVENTS:
        if ev_id in by_event:
            d = by_event[ev_id]
            d["online"] = d["online"] + d["offline"]
            d["offline"] = 0
            d["override_applied"] = True

    out = []
    for ev_id, d in sorted(by_event.items(), key=lambda x: (x[1]["series"], x[1]["year"])):
        total = d["online"] + d["offline"]
        share = round(100 * d["online"] / total, 1) if total else 0
        out.append({
            "event_id": ev_id,
            "series": d["series"],
            "year": d["year"],
            "n_online": d["online"],
            "n_offline": d["offline"],
            "online_share_pct": share,
            "override": d.get("override_applied", False),
        })

    with open(f"{OUT_DIR}/online_share_by_year.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print(f"Wrote {OUT_DIR}/online_share_by_year.csv ({len(out)} rows)")
    print("\nOnline share by year (среди годов с >=1 онлайн-докладом):")
    for r in out:
        if r["n_online"] > 0:
            print(f"  {r['series']:10s} {r['year']}: онлайн {r['n_online']:3d}/{r['n_online']+r['n_offline']:3d} = {r['online_share_pct']:5.1f}%  {'(override)' if r['override'] else ''}")

    # H6: who participates online >=3 times after 2020?
    cur.execute("""
        SELECT pp.person_id, pers.display_name, e.year, pres.is_online
          FROM presentation_person pp
          JOIN person pers ON pers.person_id = pp.person_id
          JOIN presentation pres ON pres.presentation_id = pp.presentation_id
          JOIN session s ON s.session_id = pres.session_id
          JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
          JOIN event_day ed ON ed.event_day_id = edv.event_day_id
          JOIN event e ON e.event_id = ed.event_id
         WHERE e.year >= 2020 AND pres.is_online = 1
    """)
    online_2020 = defaultdict(list)
    for pid, name, year, _ in cur.fetchall():
        online_2020[pid].append((name, year))

    repeaters = [(pid, v[0][0], len(v), sorted({y for _, y in v}))
                 for pid, v in online_2020.items() if len(v) >= 2]
    repeaters.sort(key=lambda x: -x[2])

    with open(f"{OUT_DIR}/online_repeaters_2020_plus.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "display_name", "n_online_talks", "years"])
        for r in repeaters:
            w.writerow([r[0], r[1], r[2], ";".join(str(y) for y in r[3])])

    print(f"\nWrote {OUT_DIR}/online_repeaters_2020_plus.csv ({len(repeaters)} rows)")
    print(f"\nТоп-10 онлайн-репитеров 2020+:")
    for r in repeaters[:10]:
        print(f"  {r[1]}: {r[2]} онлайн-докладов в годах {r[3]}")

    conn.close()


if __name__ == "__main__":
    main()
