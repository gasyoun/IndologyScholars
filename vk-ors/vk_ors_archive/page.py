"""Generate a self-contained HTML retrospective for the VK ORS wall archive.

Reads ``data/site_data.json`` (+ processed CSVs when present). No CDN.
Mirror of the nagari retrospective contract, adapted to a flat wall
(engagement layer instead of reply network).

Wave-1 advanced viz (additive sections):
  * Media gallery — hotlinked attachment thumbs with onerror → "view on VK" card
  * Faceted client-side search — year / hashtag / attachment type / engagement tier
  * Engagement explorer — within-year tiers + top posts per tier

Search/facets are hand-rolled JS (exact-match facets + substring text); no
vendored lib needed under the PLAN size/license ceiling fallback rule.
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

    gallery = site.get("gallery") or []
    search_index = site.get("search_index") or []
    tier_by_year = site.get("tier_by_year") or {}
    top_by_tier = site.get("top_by_tier") or {}
    score_weights = site.get("score_weights") or {}
    n_attachments = int(site.get("n_attachments") or totals.get("attachments") or 0)

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
            text = (r.get("text") or r.get("snippet") or r.get("excerpt") or r.get("title") or "")[:160]
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
            f"<td>{esc(r.get('like_rate_pct') or r.get('like_rate') or r.get('likes_per_view') or '')}</td>"
            f"<td>{esc(r.get('repost_rate_pct') or r.get('repost_rate') or r.get('reposts_per_view') or '')}</td>"
            f"<td>{esc(r.get('comment_rate_pct') or r.get('comment_rate') or r.get('comments_per_view') or '')}</td></tr>"
        )

    # Embed JSON for client-side advanced sections (inline — no separate fetch)
    # Keep payload bounded: search_index can be large; strip long text already capped in insights
    embed = {
        "gallery": gallery,
        "search_index": search_index,
        "tier_by_year": tier_by_year,
        "top_by_tier": top_by_tier,
        "score_weights": score_weights,
    }
    embed_json = json.dumps(embed, ensure_ascii=False, separators=(",", ":"))
    # Escape for </script> safety
    embed_json = embed_json.replace("<", "\\u003c").replace(">", "\\u003e")

    sw = score_weights
    weight_note = (
        f"score = {sw.get('likes', 1)}×likes + {sw.get('reposts', 5)}×reposts + "
        f"{sw.get('comments', 2)}×comments + views/{sw.get('views_div', 50)}"
    )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ОРС ВКонтакте — ретроспектива стены (2015–2026)</title>
<meta name="description" content="Архив и анализ публичной стены «Общество ревнителей санскрита» (vk.com/wall-88831040). Медиа-галерея, фасетный поиск, вовлечённость."/>
<style>
:root {{
  --bg:#101513; --panel:#171c19; --text:#e8eee9; --muted:#9aa89c;
  --border:rgba(255,255,255,0.1); --accent:#62ae92; --accent2:#6c5ce7;
  font-family: "Segoe UI", system-ui, sans-serif;
}}
body {{ margin:0; background:var(--bg); color:var(--text); line-height:1.55; }}
main {{ max-width:1080px; margin:0 auto; padding:1.5rem 1.2rem 3rem; }}
h1,h2,h3 {{ font-weight:650; letter-spacing:-0.02em; }}
h1 {{ font-size:1.75rem; margin-bottom:0.4rem; }}
h2 {{ font-size:1.2rem; margin-top:2rem; border-bottom:1px solid var(--border); padding-bottom:0.35rem; }}
h3 {{ font-size:1.0rem; margin-top:1.2rem; color:var(--muted); }}
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
/* advanced viz */
.controls {{ display:flex; flex-wrap:wrap; gap:0.5rem; align-items:center; margin:0.8rem 0; }}
.controls input[type=search] {{
  flex:1 1 220px; min-width:160px; background:var(--panel); color:var(--text);
  border:1px solid var(--border); border-radius:8px; padding:0.55rem 0.75rem; font-size:0.95rem;
}}
.chip {{
  display:inline-block; padding:0.25rem 0.65rem; border-radius:999px; font-size:0.8rem;
  border:1px solid var(--border); background:var(--panel); color:var(--muted); cursor:pointer;
  user-select:none;
}}
.chip.active {{ background:rgba(98,174,146,0.2); border-color:var(--accent); color:var(--accent); }}
.chip-row {{ display:flex; flex-wrap:wrap; gap:0.35rem; margin:0.35rem 0; }}
.chip-label {{ font-size:0.78rem; color:var(--muted); margin-right:0.25rem; align-self:center; }}
#result-meta {{ font-size:0.85rem; color:var(--muted); margin:0.4rem 0 0.8rem; }}
.gallery {{
  display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:0.6rem;
}}
.g-card {{
  background:var(--panel); border:1px solid var(--border); border-radius:10px; overflow:hidden;
  display:flex; flex-direction:column; min-height:160px; position:relative;
}}
.g-card a.thumb-link {{ display:block; aspect-ratio:1; background:#0c100e; position:relative; }}
.g-card img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.g-fallback {{
  display:none; position:absolute; inset:0; padding:0.6rem; font-size:0.78rem; color:var(--muted);
  background:var(--panel); flex-direction:column; justify-content:center; gap:0.3rem;
}}
.g-fallback.show {{ display:flex; }}
.g-meta {{ padding:0.45rem 0.55rem 0.6rem; font-size:0.75rem; color:var(--muted); }}
.g-meta .type {{ color:var(--accent2); text-transform:uppercase; font-size:0.68rem; letter-spacing:0.04em; }}
.badge-viral {{
  position:absolute; top:0.35rem; right:0.35rem; background:rgba(108,92,231,0.9);
  color:#fff; font-size:0.65rem; padding:0.15rem 0.4rem; border-radius:4px; z-index:1;
}}
#post-results {{ list-style:none; padding:0; margin:0.5rem 0 0; }}
#post-results li {{
  border-bottom:1px solid var(--border); padding:0.55rem 0; font-size:0.88rem;
}}
#post-results .meta {{ color:var(--muted); font-size:0.78rem; }}
.tier-bars {{ margin:0.6rem 0 1rem; }}
.tier-row {{ display:grid; grid-template-columns:3.5rem 1fr; gap:0.4rem; align-items:center; margin:0.2rem 0; font-size:0.82rem; }}
.tier-stack {{ display:flex; height:14px; border-radius:4px; overflow:hidden; background:rgba(255,255,255,0.05); }}
.tier-seg {{ height:100%; }}
.legend {{ display:flex; flex-wrap:wrap; gap:0.6rem; font-size:0.75rem; color:var(--muted); margin:0.4rem 0 0.8rem; }}
.legend span::before {{
  content:""; display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:0.3rem; vertical-align:middle;
}}
.t-low::before {{ background:#3d4f46; }} .t-mid_low::before {{ background:#4a7c6a; }}
.t-mid_high::before {{ background:#62ae92; }} .t-high::before {{ background:#8fd4bc; }}
.t-viral::before {{ background:#6c5ce7; }}
#top-tier-list {{ list-style:none; padding:0; }}
#top-tier-list li {{ padding:0.4rem 0; border-bottom:1px solid var(--border); font-size:0.88rem; }}
.nav-adv {{ display:flex; flex-wrap:wrap; gap:0.75rem; margin:1rem 0; font-size:0.9rem; }}
.nav-adv a {{ text-decoration:none; border-bottom:1px dotted var(--accent); }}
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
  <article class="card"><div class="muted">Вложений (raw)</div><div class="metric">{n_attachments:,}</div></article>
</section>

<nav class="nav-adv" aria-label="Расширенные разделы">
  <a href="#gallery-section">Галерея</a>
  <a href="#search-section">Поиск и фильтры</a>
  <a href="#engagement-explorer">Вовлечённость (tiers)</a>
  <a href="#stats-section">Статистика</a>
</nav>

<div class="caveat">
  <strong>Оговорки.</strong> Лайк/репост/просмотр — метрика вовлечённости, не мера научной ценности.
  Хэштег — самоклассификация страницы, не куратская таксономия. Один аккаунт-издатель:
  сетевой слой ответов отсутствует (в отличие от закрытой гуглгруппы <a href="../nagari/">nagari</a>).
  «Viral»/outlier — статистический перцентиль внутри года (топ ~5%), не оценка качества контента.
  Миниатюры галереи подгружаются с CDN ВК (hotlink); при протухшем URL показывается карточка «на ВК».
</div>

<!-- ===== Wave-1b: faceted search ===== -->
<section id="search-section">
  <h2>Поиск и фильтры</h2>
  <p class="muted">Клиентский поиск по тексту/хэштегам + фасеты (год, тип вложения, tier вовлечённости). Без сети, кроме миниатюр ВК.</p>
  <div class="controls">
    <input type="search" id="q" placeholder="Текст или #хэштег…" autocomplete="off"/>
  </div>
  <div class="chip-row" id="facet-year"><span class="chip-label">Год:</span></div>
  <div class="chip-row" id="facet-type"><span class="chip-label">Тип:</span></div>
  <div class="chip-row" id="facet-tier"><span class="chip-label">Tier:</span></div>
  <div class="chip-row" id="facet-tag"><span class="chip-label">Топ-хэштеги:</span></div>
  <div id="result-meta"></div>
  <ul id="post-results"></ul>
</section>

<!-- ===== Wave-1a: media gallery ===== -->
<section id="gallery-section">
  <h2>Медиа-галерея</h2>
  <p class="muted">Вложения (photo / video preview / doc preview / link). Клик — пост на ВК. Фильтры выше сужают и галерею, и список постов.</p>
  <div class="gallery" id="gallery"></div>
</section>

<!-- ===== Wave-1c: engagement explorer ===== -->
<section id="engagement-explorer">
  <h2>Вовлечённость: tiers по годам</h2>
  <p class="muted">Перцентили внутри каждого года. Score: {esc(weight_note)}. Outlier = top ~5% (viral).</p>
  <div class="legend">
    <span class="t-low">low</span>
    <span class="t-mid_low">mid_low</span>
    <span class="t-mid_high">mid_high</span>
    <span class="t-high">high</span>
    <span class="t-viral">viral</span>
  </div>
  <div class="tier-bars" id="tier-bars"></div>
  <h3>Топ постов выбранного tier</h3>
  <div class="chip-row" id="tier-pick"></div>
  <ul id="top-tier-list"></ul>
</section>

<section id="stats-section">
<h2>1. Активность по годам</h2>
{year_bars or '<p class="muted">Нет данных by_year.</p>'}

<h2>2. Вовлечённость (топ)</h2>
<p class="muted">Топ постов по лайкам (срез CSV; текст усечён).</p>
{post_list(top_likes)}
<p class="muted">Топ по репостам.</p>
{post_list(top_reposts)}
{f'''<h3>Конверсия по годам</h3>
<table><thead><tr><th>Год</th><th>like rate %</th><th>repost rate %</th><th>comment rate %</th></tr></thead>
<tbody>{eng_rows}</tbody></table>''' if eng_rows else ''}

<h2>3. Хэштеги и темы</h2>
{tag_bars or '<p class="muted">Нет hashtags.csv</p>'}
{f'''<h3>Темы по годам</h3>
<table><thead><tr><th>Год</th>{topic_table_head}</tr></thead>
<tbody>{topic_rows_html}</tbody></table>''' if topic_keys else ''}

<h2>4. Санскритские термины (частота)</h2>
<ul>{sanskrit_items}</ul>
</section>

<footer>
  Источник данных: конвейер <code>vk_ors_archive</code> → <code>data/site_data.json</code>.
  Пересборка: <code>python -m vk_ors_archive.fetch && …ingest && …insights && …page</code>.
  Sibling: <a href="https://github.com/gasyoun/IndologyScholars/tree/main/nagari">nagari</a> (закрытая гуглгруппа).
  Plan: <a href="https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md">advanced viz Q3 2026</a>.
</footer>
</main>

<script id="site-embed" type="application/json">{embed_json}</script>
<script>
(function () {{
  "use strict";
  var raw = document.getElementById("site-embed").textContent;
  var DATA = JSON.parse(raw);
  var posts = DATA.search_index || [];
  var gallery = DATA.gallery || [];
  var tierByYear = DATA.tier_by_year || {{}};
  var topByTier = DATA.top_by_tier || {{}};

  var state = {{
    q: "",
    year: null,
    type: null,
    tier: null,
    tag: null
  }};

  var TIER_COLORS = {{
    low: "#3d4f46", mid_low: "#4a7c6a", mid_high: "#62ae92",
    high: "#8fd4bc", viral: "#6c5ce7"
  }};
  var TIER_ORDER = ["low", "mid_low", "mid_high", "high", "viral"];

  function matches(p) {{
    if (state.year && String(p.year) !== String(state.year)) return false;
    if (state.tier && p.engagement_tier !== state.tier) return false;
    if (state.tag) {{
      var tags = p.tags || [];
      var ok = false;
      for (var i = 0; i < tags.length; i++) {{
        if (String(tags[i]).toLowerCase() === state.tag) {{ ok = true; break; }}
      }}
      if (!ok) return false;
    }}
    if (state.type) {{
      var types = p.attachment_types || [];
      var okT = false;
      for (var j = 0; j < types.length; j++) {{
        if (types[j] === state.type) {{ okT = true; break; }}
      }}
      if (!okT) return false;
    }}
    if (state.q) {{
      var q = state.q.toLowerCase();
      var blob = ((p.text || "") + " " + (p.tags || []).join(" ")).toLowerCase();
      if (blob.indexOf(q) === -1) return false;
    }}
    return true;
  }}

  function filteredPosts() {{
    var out = [];
    for (var i = 0; i < posts.length; i++) {{
      if (matches(posts[i])) out.push(posts[i]);
    }}
    return out;
  }}

  function filteredIds() {{
    var set = {{}};
    var fp = filteredPosts();
    for (var i = 0; i < fp.length; i++) set[fp[i].id] = true;
    return set;
  }}

  function collectFacets() {{
    var years = {{}}, types = {{}}, tiers = {{}}, tags = {{}};
    for (var i = 0; i < posts.length; i++) {{
      var p = posts[i];
      if (p.year) years[p.year] = (years[p.year] || 0) + 1;
      if (p.engagement_tier) tiers[p.engagement_tier] = (tiers[p.engagement_tier] || 0) + 1;
      var ts = p.attachment_types || [];
      for (var j = 0; j < ts.length; j++) types[ts[j]] = (types[ts[j]] || 0) + 1;
      var tg = p.tags || [];
      for (var k = 0; k < tg.length; k++) tags[tg[k]] = (tags[tg[k]] || 0) + 1;
    }}
    return {{ years: years, types: types, tiers: tiers, tags: tags }};
  }}

  function renderChips(containerId, map, key, sortFn, limit) {{
    var el = document.getElementById(containerId);
    if (!el) return;
    // keep label
    var label = el.querySelector(".chip-label");
    el.innerHTML = "";
    if (label) el.appendChild(label);
    var all = document.createElement("button");
    all.type = "button";
    all.className = "chip" + (state[key] == null ? " active" : "");
    all.textContent = "все";
    all.addEventListener("click", function () {{
      state[key] = null;
      render();
    }});
    el.appendChild(all);
    var keys = Object.keys(map);
    keys.sort(sortFn || function (a, b) {{ return map[b] - map[a]; }});
    if (limit) keys = keys.slice(0, limit);
    for (var i = 0; i < keys.length; i++) {{
      (function (val) {{
        var b = document.createElement("button");
        b.type = "button";
        b.className = "chip" + (String(state[key]) === String(val) ? " active" : "");
        b.textContent = val + " (" + map[val] + ")";
        b.addEventListener("click", function () {{
          state[key] = (String(state[key]) === String(val)) ? null : val;
          render();
        }});
        el.appendChild(b);
      }})(keys[i]);
    }}
  }}

  function onImgError(img) {{
    img.style.display = "none";
    var card = img.closest(".g-card");
    if (!card) return;
    var fb = card.querySelector(".g-fallback");
    if (fb) fb.classList.add("show");
  }}
  // expose for inline onerror
  window.__vkorsImgError = onImgError;

  function renderGallery(idSet) {{
    var root = document.getElementById("gallery");
    if (!root) return;
    root.innerHTML = "";
    var shown = 0;
    var MAX = 240;
    for (var i = 0; i < gallery.length && shown < MAX; i++) {{
      var g = gallery[i];
      if (idSet && !idSet[g.post_id]) continue;
      var card = document.createElement("article");
      card.className = "g-card";
      if (g.is_outlier) {{
        var badge = document.createElement("span");
        badge.className = "badge-viral";
        badge.textContent = "viral";
        card.appendChild(badge);
      }}
      var link = document.createElement("a");
      link.className = "thumb-link";
      link.href = g.post_url || "#";
      link.target = "_blank";
      link.rel = "noopener";
      if (g.url) {{
        var img = document.createElement("img");
        img.loading = "lazy";
        img.alt = (g.type || "media") + " " + (g.date || "");
        img.src = g.url;
        img.onerror = function () {{ onImgError(this); }};
        link.appendChild(img);
      }}
      var fb = document.createElement("div");
      fb.className = "g-fallback" + (g.url ? "" : " show");
      fb.innerHTML = "<strong>Смотреть на ВК</strong>"
        + "<span>" + (g.type || "?") + " · " + (g.date || "") + "</span>"
        + "<span>" + (g.excerpt || "").slice(0, 80) + "</span>";
      link.appendChild(fb);
      card.appendChild(link);
      var meta = document.createElement("div");
      meta.className = "g-meta";
      meta.innerHTML = '<span class="type">' + (g.type || "") + "</span> · "
        + (g.date || "") + " · ♥ " + (g.likes || 0);
      card.appendChild(meta);
      root.appendChild(card);
      shown++;
    }}
    if (shown === 0) {{
      root.innerHTML = '<p class="muted">Нет вложений под текущие фильтры'
        + (gallery.length === 0 ? " (attachments_raw.json пуст — запустите fetch.py)." : ".")
        + "</p>";
    }}
  }}

  function renderResults() {{
    var fp = filteredPosts();
    var meta = document.getElementById("result-meta");
    if (meta) meta.textContent = "Найдено постов: " + fp.length + " из " + posts.length;
    var ul = document.getElementById("post-results");
    if (!ul) return;
    ul.innerHTML = "";
    var LIMIT = 40;
    for (var i = 0; i < fp.length && i < LIMIT; i++) {{
      var p = fp[i];
      var li = document.createElement("li");
      var tags = (p.tags || []).slice(0, 5).map(function (t) {{ return "#" + t; }}).join(" ");
      li.innerHTML = '<div class="meta">' + (p.date || "") + " · tier:" + (p.engagement_tier || "")
        + " · ♥" + (p.likes || 0)
        + (p.attachment_types && p.attachment_types.length
            ? " · " + p.attachment_types.join(",") : "")
        + (p.url ? ' · <a href="' + p.url + '" target="_blank" rel="noopener">VK</a>' : "")
        + "</div>"
        + "<div>" + (p.text || "").slice(0, 200) + "</div>"
        + (tags ? '<div class="meta">' + tags + "</div>" : "");
      ul.appendChild(li);
    }}
  }}

  function renderTierBars() {{
    var root = document.getElementById("tier-bars");
    if (!root) return;
    root.innerHTML = "";
    var years = Object.keys(tierByYear).sort();
    for (var i = 0; i < years.length; i++) {{
      var y = years[i];
      var counts = tierByYear[y] || {{}};
      var total = 0;
      for (var t = 0; t < TIER_ORDER.length; t++) total += (counts[TIER_ORDER[t]] || 0);
      if (!total) continue;
      var row = document.createElement("div");
      row.className = "tier-row";
      var lab = document.createElement("span");
      lab.textContent = y;
      var stack = document.createElement("div");
      stack.className = "tier-stack";
      stack.title = y + ": " + total + " posts";
      for (var j = 0; j < TIER_ORDER.length; j++) {{
        var tier = TIER_ORDER[j];
        var n = counts[tier] || 0;
        if (!n) continue;
        var seg = document.createElement("div");
        seg.className = "tier-seg";
        seg.style.width = (100 * n / total) + "%";
        seg.style.background = TIER_COLORS[tier] || "#666";
        seg.title = tier + ": " + n;
        stack.appendChild(seg);
      }}
      row.appendChild(lab);
      row.appendChild(stack);
      root.appendChild(row);
    }}
  }}

  var activeTierPick = "viral";

  function renderTierPick() {{
    var el = document.getElementById("tier-pick");
    if (!el) return;
    el.innerHTML = "";
    for (var i = 0; i < TIER_ORDER.length; i++) {{
      (function (tier) {{
        var b = document.createElement("button");
        b.type = "button";
        b.className = "chip" + (activeTierPick === tier ? " active" : "");
        var n = (topByTier[tier] || []).length;
        b.textContent = tier + (n ? " (" + n + ")" : "");
        b.addEventListener("click", function () {{
          activeTierPick = tier;
          renderTierPick();
          renderTopTier();
        }});
        el.appendChild(b);
      }})(TIER_ORDER[i]);
    }}
  }}

  function renderTopTier() {{
    var ul = document.getElementById("top-tier-list");
    if (!ul) return;
    ul.innerHTML = "";
    var list = topByTier[activeTierPick] || [];
    if (!list.length) {{
      ul.innerHTML = '<li class="muted">Нет данных для tier «' + activeTierPick + '».</li>';
      return;
    }}
    for (var i = 0; i < list.length; i++) {{
      var p = list[i];
      var li = document.createElement("li");
      li.innerHTML = "<strong>" + (p.score || "") + "</strong> · "
        + (p.date || "") + " · ♥" + (p.likes || 0)
        + (p.url ? ' · <a href="' + p.url + '" target="_blank" rel="noopener">VK</a>' : "")
        + "<div class='muted'>" + (p.excerpt || "") + "</div>";
      ul.appendChild(li);
    }}
  }}

  function render() {{
    var facets = collectFacets();
    renderChips("facet-year", facets.years, "year", function (a, b) {{
      return Number(a) - Number(b);
    }});
    renderChips("facet-type", facets.types, "type");
    renderChips("facet-tier", facets.tiers, "tier", function (a, b) {{
      return TIER_ORDER.indexOf(a) - TIER_ORDER.indexOf(b);
    }});
    renderChips("facet-tag", facets.tags, "tag", null, 12);
    var ids = filteredIds();
    renderResults();
    renderGallery(ids);
  }}

  var qEl = document.getElementById("q");
  if (qEl) {{
    var t = null;
    qEl.addEventListener("input", function () {{
      clearTimeout(t);
      t = setTimeout(function () {{
        state.q = (qEl.value || "").trim();
        render();
      }}, 120);
    }});
  }}

  renderTierBars();
  renderTierPick();
  renderTopTier();
  render();
}})();
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {
        "posts": posts,
        "out": str(out_path),
        "bytes": len(html.encode("utf-8")),
        "gallery": len(gallery),
        "search_index": len(search_index),
    }


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
    print(
        f"Wrote {meta['out']} ({meta['bytes']} bytes, posts={meta['posts']}, "
        f"gallery={meta['gallery']}, search_index={meta['search_index']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
