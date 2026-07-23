"""Generate a self-contained HTML retrospective for the VK ORS wall archive.

Reads ``data/site_data.json`` (+ processed CSVs when present). No CDN.
Mirror of the nagari retrospective contract, adapted to a flat wall
(engagement layer instead of reply network).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
DEFAULT_SITE = PKG / "data" / "site_data.json"
DEFAULT_OUT = PKG / "site" / "index.html"
PROCESSED = PKG / "data" / "processed"


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def rd_csv(name: str) -> list[dict]:
    path = PROCESSED / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def esc(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def bar_row(label: str, value: float, max_v: float, color: str = "#62ae92") -> str:
    width = 0 if max_v <= 0 else min(100.0, 100.0 * value / max_v)
    return (
        f'<div class="bar-row"><span class="bar-label">{esc(label)}</span>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{width:.1f}%;background:{color};"></div></div>'
        f'<span class="bar-val">{value:g}</span></div>'
    )


def build(site_path: Path, out_path: Path) -> dict:
    site = json.loads(site_path.read_text(encoding="utf-8"))
    totals = site.get("totals") or {}
    activity = site.get("activity") or {}
    by_year = activity.get("by_year") or site.get("by_year") or []
    hashtags = rd_csv("hashtags.csv") or site.get("hashtags") or []
    topics = rd_csv("topics_by_year.csv") or site.get("topics_by_year") or []
    top_likes = rd_csv("top_posts_by_likes.csv") or site.get("top_posts_by_likes") or []
    top_reposts = rd_csv("top_posts_by_reposts.csv") or site.get("top_posts_by_reposts") or []
    engagement = rd_csv("engagement_rate_by_year.csv") or site.get("engagement_rate_by_year") or []
    sanskrit = rd_csv("sanskrit_terms.csv") or site.get("sanskrit_terms") or []

    posts = int(totals.get("posts") or 0)
    likes = int(totals.get("likes") or 0)
    reposts = int(totals.get("reposts") or 0)
    views = int(totals.get("views") or 0)
    dmin = esc(totals.get("date_min") or "")
    dmax = esc(totals.get("date_max") or "")
    today = date.today().isoformat()

    max_posts = max((int(r.get("posts") or 0) for r in by_year), default=1)
    year_bars = "".join(
        bar_row(str(r.get("year")), int(r.get("posts") or 0), max_posts)
        for r in by_year
    )

    # Top hashtags
    if hashtags and isinstance(hashtags[0], dict):
        tag_rows = sorted(
            hashtags,
            key=lambda r: -int(r.get("count") or r.get("n") or 0),
        )[:20]
    else:
        tag_rows = []
    max_tag = max((int(r.get("count") or r.get("n") or 0) for r in tag_rows), default=1)
    tag_bars = "".join(
        bar_row(
            str(r.get("hashtag") or r.get("tag") or r.get("name") or "?"),
            int(r.get("count") or r.get("n") or 0),
            max_tag,
            color="#6c5ce7",
        )
        for r in tag_rows
    )

    # Topics by year: pivot primary topics
    topic_keys = []
    if topics:
        keys = set()
        for r in topics:
            for k in ("topic", "tag", "label"):
                if r.get(k):
                    keys.add(r[k])
                    break
        topic_keys = sorted(keys)[:8]
    topic_table_head = "".join(f"<th>{esc(k)}</th>" for k in topic_keys)
    years_in_topics = sorted({str(r.get("year")) for r in topics if r.get("year")})
    topic_rows_html = ""
    for y in years_in_topics:
        cells = ""
        for k in topic_keys:
            val = 0
            for r in topics:
                label = r.get("topic") or r.get("tag") or r.get("label")
                if str(r.get("year")) == y and label == k:
                    val = int(r.get("count") or r.get("n") or 0)
                    break
            cells += f"<td>{val}</td>"
        topic_rows_html += f"<tr><td>{esc(y)}</td>{cells}</tr>"

    def post_list(rows, limit=8):
        items = []
        for r in rows[:limit]:
            text = (r.get("text") or r.get("snippet") or r.get("title") or "")[:160]
            likes_n = r.get("likes") or r.get("n_likes") or ""
            url = r.get("url") or r.get("post_url") or ""
            link = f' <a href="{esc(url)}" rel="noopener" target="_blank">VK</a>' if url else ""
            items.append(
                f"<li><strong>{esc(likes_n)}</strong> · {esc(text)}…{link}</li>"
            )
        return "<ol>" + "".join(items) + "</ol>" if items else "<p class='muted'>Нет данных.</p>"

    sanskrit_items = "".join(
        f"<li><code>{esc(r.get('term') or r.get('token'))}</code> — {esc(r.get('count') or r.get('n'))}</li>"
        for r in (sanskrit[:15] if sanskrit else [])
    ) or "<li class='muted'>Нет данных.</li>"

    eng_rows = ""
    for r in engagement:
        eng_rows += (
            f"<tr><td>{esc(r.get('year'))}</td>"
            f"<td>{esc(r.get('like_rate') or r.get('likes_per_view') or '')}</td>"
            f"<td>{esc(r.get('repost_rate') or r.get('reposts_per_view') or '')}</td>"
            f"<td>{esc(r.get('comment_rate') or r.get('comments_per_view') or '')}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ОРС ВКонтакте — ретроспектива стены (2015–2026)</title>
<meta name="description" content="Архив и анализ публичной стены «Общество ревнителей санскрита» (vk.com/wall-88831040)."/>
<style>
:root {{
  --bg:#101513; --panel:#171c19; --text:#e8eee9; --muted:#9aa89c;
  --border:rgba(255,255,255,0.1); --accent:#62ae92;
  font-family: "Segoe UI", system-ui, sans-serif;
}}
body {{ margin:0; background:var(--bg); color:var(--text); line-height:1.55; }}
main {{ max-width:960px; margin:0 auto; padding:1.5rem 1.2rem 3rem; }}
h1,h2 {{ font-weight:650; letter-spacing:-0.02em; }}
h1 {{ font-size:1.75rem; margin-bottom:0.4rem; }}
h2 {{ font-size:1.2rem; margin-top:2rem; border-bottom:1px solid var(--border); padding-bottom:0.35rem; }}
.muted {{ color:var(--muted); font-size:0.9rem; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:0.75rem; margin:1rem 0; }}
.card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:0.9rem 1rem; }}
.card .metric {{ font-size:1.5rem; font-weight:700; color:var(--accent); }}
.bar-row {{ display:grid; grid-template-columns:4rem 1fr 3.5rem; gap:0.5rem; align-items:center; margin:0.25rem 0; font-size:0.88rem; }}
.bar-track {{ background:rgba(255,255,255,0.06); border-radius:4px; height:12px; overflow:hidden; }}
.bar-fill {{ height:100%; border-radius:4px; }}
.bar-val {{ text-align:right; color:var(--muted); }}
table {{ width:100%; border-collapse:collapse; font-size:0.88rem; }}
th,td {{ border-bottom:1px solid var(--border); padding:0.4rem 0.5rem; text-align:left; }}
th {{ color:var(--muted); font-weight:600; }}
a {{ color:var(--accent); }}
ol {{ padding-left:1.2rem; }}
.caveat {{ background:rgba(98,174,146,0.08); border:1px solid rgba(98,174,146,0.25); border-radius:8px; padding:0.8rem 1rem; margin:1.2rem 0; font-size:0.9rem; }}
footer {{ margin-top:2.5rem; color:var(--muted); font-size:0.82rem; }}
</style>
</head>
<body>
<main>
<header>
  <h1>Общество ревнителей санскрита — стена ВК</h1>
  <p class="muted">Публичный архив <a href="https://vk.com/wall-88831040" rel="noopener" target="_blank">vk.com/wall-88831040</a>
  · {dmin[:10]} — {dmax[:10]} · сгенерировано {today}</p>
</header>

<section class="grid">
  <article class="card"><div class="muted">Постов</div><div class="metric">{posts:,}</div></article>
  <article class="card"><div class="muted">Лайков</div><div class="metric">{likes:,}</div></article>
  <article class="card"><div class="muted">Репостов</div><div class="metric">{reposts:,}</div></article>
  <article class="card"><div class="muted">Просмотров</div><div class="metric">{views:,}</div></article>
</section>

<div class="caveat">
  <strong>Оговорки.</strong> Лайк/репост/просмотр — метрика вовлечённости, не мера научной ценности.
  Хэштег — самоклассификация страницы, не куратская таксономия. Один аккаунт-издатель:
  сетевой слой ответов отсутствует (в отличие от закрытой гуглгруппы <a href="../nagari/">nagari</a>).
</div>

<h2>1. Активность по годам</h2>
{year_bars or '<p class="muted">Нет данных by_year.</p>'}

<h2>2. Вовлечённость</h2>
<p class="muted">Топ постов по лайкам (срез CSV; текст усечён).</p>
{post_list(top_likes)}
<p class="muted">Топ по репостам.</p>
{post_list(top_reposts)}
{f'''<h3>Конверсия по годам</h3>
<table><thead><tr><th>Год</th><th>like rate</th><th>repost rate</th><th>comment rate</th></tr></thead>
<tbody>{eng_rows}</tbody></table>''' if eng_rows else ''}

<h2>3. Хэштеги и темы</h2>
{tag_bars or '<p class="muted">Нет hashtags.csv</p>'}
{f'''<h3>Темы по годам</h3>
<table><thead><tr><th>Год</th>{topic_table_head}</tr></thead>
<tbody>{topic_rows_html}</tbody></table>''' if topic_keys else ''}

<h2>4. Санскритские термины (частота)</h2>
<ul>{sanskrit_items}</ul>

<footer>
  Источник данных: конвейер <code>vk_ors_archive</code> → <code>data/site_data.json</code>.
  Пересборка: <code>python -m vk_ors_archive.page</code>.
  Sibling: <a href="https://github.com/gasyoun/IndologyScholars/tree/main/nagari">nagari</a> (закрытая гуглгруппа).
</footer>
</main>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {"posts": posts, "out": str(out_path), "bytes": len(html.encode("utf-8"))}


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.site.exists():
        print(f"Missing {args.site}; run insights first.", file=sys.stderr)
        return 1
    meta = build(args.site, args.out)
    print(f"Wrote {meta['out']} ({meta['bytes']} bytes, posts={meta['posts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
