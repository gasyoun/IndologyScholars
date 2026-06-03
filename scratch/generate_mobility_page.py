"""Mobility analysis: inter-institutional and inter-city transitions."""
# Quick helper: generate mobility page for findings/
import json, re, csv
from collections import defaultdict

def generate_mobility_page():
    with open("site_data.json", encoding="utf-8") as f:
        text = f.read().strip()
        text = re.sub(r'^const CONFERENCE_DATA = ', '', text)
        text = re.sub(r';$', '', text)
        scholars = json.loads(text).get("scholars", [])

    # City transitions
    from collections import Counter
    city_pairs = Counter()
    city_list = []
    for s in scholars:
        cities = set()
        for t in s.get("talks", []):
            g = t.get("geography", {})
            c = g.get("ru", "") if isinstance(g, dict) else ""
            if c and c not in ("Не указана", ""):
                cities.add(c)
        if len(cities) > 1:
            city_list.append((s.get("full_name_ru") or s.get("name", ""), list(cities)))

    # Affiliation changes
    aff_changes = sum(1 for s in scholars if s.get("has_changed_affiliations"))
    total = len(scholars)

    body = f'''<header>
<h1>Межинституциональная мобильность</h1>
<p>Анализ переходов учёных между городами и институциями за период 2004-2026.</p>
</header>
<section class="grid">
<article class="card"><strong>Учёных с переездами</strong><div class="metric">{len(city_list)}</div><div class="meta">из {total} ({round(100*len(city_list)/total,1)}%)</div></article>
<article class="card"><strong>Меняли аффилиацию</strong><div class="metric">{aff_changes}</div><div class="meta">из {total} ({round(100*aff_changes/total,1)}%)</div></article>
<article class="card"><strong>Среднее городов</strong><div class="metric">{round(sum(len(c[1]) for c in city_list)/len(city_list),1) if city_list else 0}</div></article>
</section>
<h2>Учёные, выступавшие из нескольких городов</h2>
<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;">
<thead><tr><th>Учёный</th><th>Города</th></tr></thead>
<tbody>{"".join(f'<tr><td>{name}</td><td>{", ".join(cities)}</td></tr>' for name, cities in sorted(city_list, key=lambda x: -len(x[1]))[:30])}</tbody>
</table></div>
<p style="color:var(--muted);">Данные основаны на указанных в программах городах. Город не всегда равен институции.</p>'''

    with open("findings/mobility.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Мобильность | Архив российской индологии</title>
<link rel="stylesheet" href="../assets/styles.css">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
</head><body>
<nav class="top-nav"><div class="nav-brand"><a href="../" style="color:inherit;text-decoration:none;">Архив российской индологии</a></div></nav>
<main style="max-width:960px;margin:2rem auto;padding:0 1.5rem;">{body}</main>
</body></html>''')
    print("findings/mobility.html generated")

if __name__ == "__main__":
    generate_mobility_page()
