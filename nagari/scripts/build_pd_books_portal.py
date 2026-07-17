"""Publish the rights-cleared (bucket B = public domain) nagari attachments.

Reads the H1142 census CSV, selects ONLY bucket B (pre-1930 imprints, authors
dead >=70y), maps each att_id to its extracted blob, copies those blobs into a
publishable path (nagari/site/books/), and generates a «Книгохранилище» index.

Deliberately NOT published: bucket A (owner's own work — may include private
drafts/plans, an owner decision), B-cand/C-cand (licence unconfirmed), D-author,
D-third (in copyright), E (unidentified), and the 3 Zalizniak typeset-layer files.

Blobs are read from the MAIN checkout's extracted set; output goes to the worktree.
"""

from __future__ import annotations

import csv
import glob
import html
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WORKTREE = Path(r"C:\Users\user\Documents\GitHub\IndologyScholars-nagari-books")
BLOBS = Path(r"C:\Users\user\Documents\GitHub\IndologyScholars\nagari\data\attachments")
CSV = WORKTREE / "nagari" / "reports" / "nagari_attachment_rights.csv"
OUT_DIR = WORKTREE / "nagari" / "site" / "books"

rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
by_bucket = Counter(r["bucket"] for r in rows)

B = [r for r in rows if r["bucket"] == "B"]

OUT_DIR.mkdir(parents=True, exist_ok=True)
published, missing = [], []
for r in B:
    hits = glob.glob(str(BLOBS / (r["att_id"] + "__*")))
    if not hits:
        missing.append(r)
        continue
    src = Path(hits[0])
    # served filename: att_id keeps it unique + collision-free
    dest_name = f"{r['att_id']}__{src.name.split('__', 1)[-1]}"
    shutil.copy2(src, OUT_DIR / dest_name)
    published.append((r, dest_name, (OUT_DIR / dest_name).stat().st_size))

# ---- index page -------------------------------------------------------------
def esc(s: str) -> str:
    return html.escape(s or "")

pub_mb = sum(sz for _, _, sz in published) / 1048576
cards = []
for r, dest_name, sz in sorted(published, key=lambda t: (t[0]["year"] or "", t[0]["filename"])):
    cards.append(
        f'<tr><td><a href="{esc(dest_name)}" download>{esc(r["filename"])}</a></td>'
        f'<td class="n">{esc(r["year"])}</td>'
        f'<td class="n">{sz/1048576:.1f} МБ</td>'
        f'<td>{esc(r["evidence"])}</td></tr>'
    )

held = {
    "A — работы владельца (свои черновики/планы — решает владелец)": by_bucket["A"],
    "B-cand / C-cand — лицензия не подтверждена": by_bucket["B-cand"] + by_bucket["C-cand"],
    "D — в авторском праве (свои работы участников / третьих лиц)": by_bucket["D-author"] + by_bucket["D-third"],
    "E — не идентифицировано": by_bucket["E"],
}
held_rows = "".join(f"<tr><td>{esc(k)}</td><td class='n'>{v}</td></tr>" for k, v in held.items())

page = f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Книгохранилище (общественное достояние) — nagari</title>
<style>
:root{{--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--muted:#6b6a66;--border:#e6e5e1;--accent:#2a78d6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--muted:#a3a29a;--border:#2c2b28}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:1.7rem;margin:0 0 4px}}.sub{{color:var(--muted);margin:0 0 22px}}
a{{color:var(--accent)}}
.note{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;color:var(--muted);font-size:.92rem;margin:18px 0}}
table{{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin:14px 0}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);font-size:.9rem;vertical-align:top}}
th{{color:var(--muted);font-weight:600}}td.n,th.n{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
tr:last-child td{{border-bottom:none}}
footer{{margin-top:34px;color:var(--muted);font-size:.82rem}}
</style></head><body><div class="wrap">
<p><a href="../">← 20 лет Обществу ревнителей санскрита</a></p>
<h1>Книгохранилище: общественное достояние</h1>
<p class="sub">{len(published)} файлов · {pub_mb:.1f} МБ — сканы, перешедшие в общественное достояние (издания до 1930 г., авторы умерли ≥70 лет назад).</p>

<div class="note"><b>Что здесь опубликовано и почему.</b> Из {sum(by_bucket.values())} книжных вложений архива здесь выложены только те, что по итогам
правовой переписи (H1142) отнесены к <b>общественному достоянию</b>: издания XVIII–начала XX века,
чьи авторы умерли более 70 лет назад (правило РФ/ЕС, 70 лет post mortem auctoris). Всё остальное
не публикуется — см. таблицу ниже.</div>

<table><thead><tr><th>Файл</th><th class="n">Год</th><th class="n">Размер</th><th>Атрибуция</th></tr></thead>
<tbody>{''.join(cards)}</tbody></table>

<h2 style="font-size:1.15rem;margin-top:30px">Что НЕ опубликовано</h2>
<div class="note">Правовая перепись — это <i>совет</i>, а не разрешение. Ниже — вложения, оставленные закрытыми,
и причина. Работы третьих лиц в авторском праве не публикуются; работы самого владельца и участников
списка — отдельное решение их авторов.</div>
<table><thead><tr><th>Категория</th><th class="n">Файлов</th></tr></thead>
<tbody>{held_rows}</tbody></table>

<footer>Отбор по <code>nagari/reports/nagari_attachment_rights.csv</code> (перепись H1142, Fable 5 <code>claude-fable-5</code>).
Опубликован только bucket B (общественное достояние). Страница построена <code>build_pd_books_portal.py</code>.</footer>
</div></body></html>"""

(OUT_DIR / "index.html").write_text(page, encoding="utf-8")

print("=" * 64)
print(f"bucket distribution: {dict(by_bucket)}")
print(f"B (public domain) selected: {len(B)}")
print(f"published (blob found): {len(published)}  |  {pub_mb:.1f} MB")
if missing:
    print(f"MISSING BLOBS ({len(missing)}): " + ", ".join(r["att_id"] for r in missing))
print(f"output dir: {OUT_DIR}")
print(f"files written: {len(list(OUT_DIR.iterdir()))} (incl. index.html)")
