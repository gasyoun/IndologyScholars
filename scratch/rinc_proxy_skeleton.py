"""
Скелет для извлечения year of first publication (РИНЦ proxy для года рождения)
для 110 учёных без даты рождения.

ВНИМАНИЕ: elibrary.ru требует авторизации и часто блокирует роботов; не запускать
автоматически из-под скрипта в общем доступе. Этот скрипт делает:
  1) Выгрузку списка кандидатов (имена без birth_year) в analytics_output/rinc_lookup_queue.csv
  2) Заготовку для последующего ручного / Browser-driver поиска (или OpenAlex API
     как альтернативу — она открытая).

OpenAlex API (открытая, без ключа, https://api.openalex.org/) — рекомендуемая
замена elibrary.ru для пилота.
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


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT pers.person_id, pers.display_name, pers.full_name_ru,
               COUNT(DISTINCT pres.presentation_id) AS n_talks
          FROM person pers
          LEFT JOIN presentation_person pp ON pp.person_id = pers.person_id
          LEFT JOIN presentation pres ON pres.presentation_id = pp.presentation_id
         WHERE pers.birth_year IS NULL
         GROUP BY pers.person_id
         ORDER BY n_talks DESC
    """)
    rows = cur.fetchall()
    out = []
    for pid, disp, full, n in rows:
        out.append({
            "person_id": pid,
            "display_name": disp,
            "full_name_ru": full or "",
            "n_talks": n,
            "openalex_query": full or disp,
            "openalex_url": f"https://api.openalex.org/authors?search={(full or disp).replace(' ', '%20')}",
            "rinc_search_url": f"https://elibrary.ru/author_items.asp?authorid=&fams={(full or disp).split()[0]}",
            "first_publication_year": "",  # to be filled by lookup
            "first_publication_source": "",  # openalex|elibrary|manual
            "notes": "",
        })

    with open(f"{OUT_DIR}/rinc_lookup_queue.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"Wrote {OUT_DIR}/rinc_lookup_queue.csv ({len(out)} rows)")
    print(f"Топ-10 приоритетных по числу докладов:")
    for r in out[:10]:
        print(f"  {r['display_name']:40s}  ({r['n_talks']} talks)")
    print(f"\nДля автоматизации: используйте OpenAlex API. Например:")
    print(f"  curl '{out[0]['openalex_url']}' | jq '.results[0].counts_by_year[-1]'")
    print(f"\nПилот: попробовать на топ-30, оценить покрытие, потом решать.")
    conn.close()


if __name__ == "__main__":
    main()
