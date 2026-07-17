"""Publish the nagari «Книгохранилище»: the owner's own work + public-domain +
freely-distributed attachments. Holds everything that is a THIRD PARTY's copyright.

Owner decision 17-07-2026: publish all of the owner's own material and the
free/candidate documents for educational use. Third-party in-copyright works are
NOT the owner's to license and are held regardless of intended use:

  PUBLISH  A (owner's own)  B (public domain)  B-cand / C-cand (freely distributed)
  HOLD     D-author (participants' own in-copyright work — permission obtainable)
           D-third  (third-party in copyright: dictionaries, JSTOR, Gonda, …)
           E        (unidentified — unknown rights)
           + 3 Zalizniak-konspekt files (owner's typeset layer over Zalizniak's
             in-copyright text — the content is in copyright)

Blobs are read from the MAIN checkout's extracted set; output goes to the worktree.
Supersedes build_pd_books_portal.py (which published bucket B only).
"""

from __future__ import annotations

import csv
import glob
import html
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WORKTREE = Path(r"C:\Users\user\Documents\GitHub\IndologyScholars-nagari-books2")
BLOBS = Path(r"C:\Users\user\Documents\GitHub\IndologyScholars\nagari\data\attachments")
CSV = WORKTREE / "nagari" / "reports" / "nagari_attachment_rights.csv"
OUT_DIR = WORKTREE / "nagari" / "site" / "books"

# The 3 Zalizniak-konspekt files: A-tagged, but the content is Zalizniak's in-copyright
# text (census honesty note 3). Held with D. att 1208 ("Важнейшие корни по Зализняку")
# is the owner's OWN roots table, not a konspekt reproduction — it stays published.
ZALIZNIAK_HOLD = {"1426", "1492", "1502"}
PUBLISH_BUCKETS = {"A", "B", "B-cand", "C-cand"}

SECTION = {
    "own": ("own", "Работы владельца архива", "Собственные материалы М. Гасунса: статьи, таблицы, планы, специмены, наборные слои изданий."),
    "pd": ("pd", "Общественное достояние", "Издания до 1930 г., авторы умерли ≥70 лет назад (правило РФ/ЕС, 70 лет p.m.a.)."),
    "free": ("free", "Свободно распространяемые", "Открытые PDF, программы конференций, циркуляры, богослужебные тексты; лицензия отдельных файлов не верифицирована формально."),
}

rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
by_bucket = Counter(r["bucket"] for r in rows)


def section_of(r):
    if r["bucket"] == "A":
        return "own"
    if r["bucket"] == "B":
        return "pd"
    return "free"  # B-cand / C-cand


def publishable(r):
    return r["bucket"] in PUBLISH_BUCKETS and r["att_id"] not in ZALIZNIAK_HOLD


OUT_DIR.mkdir(parents=True, exist_ok=True)
# clear any prior copy so a re-run is clean (index.html is regenerated below)
for p in OUT_DIR.iterdir():
    if p.is_file():
        p.unlink()

published, missing = [], []
for r in rows:
    if not publishable(r):
        continue
    hits = glob.glob(str(BLOBS / (r["att_id"] + "__*")))
    if not hits:
        missing.append(r)
        continue
    src = Path(hits[0])
    dest_name = f"{r['att_id']}__{src.name.split('__', 1)[-1]}"
    shutil.copy2(src, OUT_DIR / dest_name)
    r["_dest"] = dest_name
    r["_size"] = (OUT_DIR / dest_name).stat().st_size
    published.append(r)


def esc(s):
    return html.escape(s or "")


secgroups = defaultdict(list)
for r in published:
    secgroups[section_of(r)].append(r)

pub_mb = sum(r["_size"] for r in published) / 1048576
sec_html = ""
for key in ("own", "pd", "free"):
    items = sorted(secgroups.get(key, []), key=lambda r: (r["year"] or "", r["filename"]))
    if not items:
        continue
    _, title, blurb = SECTION[key]
    cards = "".join(
        f'<tr><td><a href="{esc(r["_dest"])}" download>{esc(r["filename"])}</a></td>'
        f'<td class="n">{esc(r["year"])}</td><td class="n">{r["_size"]/1048576:.1f} МБ</td>'
        f'<td>{esc(r["evidence"])}</td></tr>'
        for r in items
    )
    sec_html += (
        f'<h2 class="sec">{esc(title)} <span class="c">{len(items)}</span></h2>'
        f'<p class="sub">{esc(blurb)}</p>'
        f'<table><thead><tr><th>Файл</th><th class="n">Год</th><th class="n">Размер</th><th>Атрибуция</th></tr></thead>'
        f'<tbody>{cards}</tbody></table>'
    )

held = {
    "Работы участников списка (в авторском праве; разрешение авторов получаемо)": by_bucket["D-author"],
    "Третьи лица в авторском праве (словари, статьи, монографии)": by_bucket["D-third"],
    "Наборный слой над текстом Зализняка (текст в авторском праве)": len(ZALIZNIAK_HOLD),
    "Не идентифицировано": by_bucket["E"],
}
held_rows = "".join(f"<tr><td>{esc(k)}</td><td class='n'>{v}</td></tr>" for k, v in held.items())
held_total = sum(held.values())

page = f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Книгохранилище — nagari (учебный архив)</title>
<style>
:root{{--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--muted:#6b6a66;--border:#e6e5e1;--accent:#2a78d6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--muted:#a3a29a;--border:#2c2b28}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:1.7rem;margin:0 0 4px}}h2.sec{{font-size:1.2rem;margin:30px 0 2px}}h2.sec .c{{color:var(--muted);font-weight:400;font-size:1rem}}
.sub{{color:var(--muted);margin:0 0 10px}}a{{color:var(--accent)}}
.note{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;color:var(--muted);font-size:.92rem;margin:18px 0}}
table{{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin:10px 0}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);font-size:.9rem;vertical-align:top}}
th{{color:var(--muted);font-weight:600}}td.n,th.n{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
tr:last-child td{{border-bottom:none}}footer{{margin-top:34px;color:var(--muted);font-size:.82rem}}
</style></head><body><div class="wrap">
<p><a href="../">← 20 лет Обществу ревнителей санскрита</a></p>
<h1>Книгохранилище</h1>
<p class="sub">Учебный архив для студентов · {len(published)} файлов · {pub_mb:.1f} МБ</p>

<div class="note"><b>Что здесь и на каких основаниях.</b> Опубликованы материалы, которые правомерно
выложить в открытый доступ: <b>собственные работы владельца архива</b>, тексты в <b>общественном
достоянии</b> и <b>свободно распространяемые</b> документы. Работы третьих лиц, остающиеся в
авторском праве, не публикуются — их правообладатели не давали разрешения, и учебная цель такого
разрешения не заменяет. Отбор — по правовой переписи
(<code>nagari/reports/nagari_attachment_rights.csv</code>, H1142).</div>

{sec_html}

<h2 class="sec">Не опубликовано <span class="c">{held_total}</span></h2>
<p class="sub">В авторском праве третьих лиц. Для работ участников списка разрешение получаемо —
по запросу можно написать авторам, и то, что они разрешат, будет добавлено.</p>
<table><thead><tr><th>Категория</th><th class="n">Файлов</th></tr></thead><tbody>{held_rows}</tbody></table>

<footer>Построено <code>build_books_portal.py</code> из правовой переписи H1142 (Fable 5 <code>claude-fable-5</code>).
Публикуются buckets A/B/B-cand/C-cand; D-author, D-third, E и наборный слой над текстом Зализняка — закрыты.</footer>
</div></body></html>"""

(OUT_DIR / "index.html").write_text(page, encoding="utf-8")

print("=" * 64)
print(f"bucket distribution: {dict(by_bucket)}")
print(f"PUBLISH buckets {sorted(PUBLISH_BUCKETS)} minus Zalizniak-hold {sorted(ZALIZNIAK_HOLD)}")
print(f"published: {len(published)}  |  {pub_mb:.1f} MB")
for k in ("own", "pd", "free"):
    print(f"   {k}: {len(secgroups.get(k, []))}")
if missing:
    print(f"MISSING BLOBS ({len(missing)}): " + ", ".join(r['att_id'] for r in missing))
print(f"held total: {held_total}  ({dict(held)})")
print(f"files in books/: {len(list(OUT_DIR.iterdir()))} (incl. index.html)")
