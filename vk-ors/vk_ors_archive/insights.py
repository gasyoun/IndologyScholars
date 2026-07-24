"""Compute the analysis layers from ``vk_ors.db`` into CSV tables + ``site_data.json``.

Four original layers, adapted from ``nagari_group_archive.insights`` to a VK
wall export (no thread/reply graph, no per-author breakdown — one publishing
account, but rich per-post engagement counters instead):

1. Timeline & activity   — posts per year & month, engagement sums/averages.
2. Engagement            — top posts by likes/reposts/comments/views, the
                            like-to-view and repost-to-view conversion trend.
3. Topics & hashtags      — the page's own hashtag taxonomy + a keyword topic
                            map applied to post text, topic trends over time.
4. Sanskrit / attachment layer — Devanagari & IAST term frequency, attachment
                            type inventory, book-flagged posts (doc attachment
                            + book-ish text).

Wave-1 advanced viz additions (additive, do not replace layers 1–4):

5. Gallery export         — ``attachments_gallery.csv`` + ``gallery`` key.
6. Engagement tiers       — within-year percentile buckets + top~5% outlier
                            flag (score = likes + 5*reposts + comments + views/50).
7. Search index           — compact per-post array for client-side facets.

Everything is written under ``<pkg>/../data/processed/`` and bundled into
``site_data.json``. Interpretive guardrails from the nagari/Indology packages
apply: likes are not agreement, views are not readership, hashtag presence is
not a curated taxonomy; "viral"/outlier is a statistical percentile label.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "vk_ors.db"
PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"

# --- Topic taxonomy: keyword patterns over post text, adapted from the
#     nagari package's tag set to what a public-facing wall actually posts:
#     book/dictionary announcements, teaching snippets, puzzles, events. ---
TOPICS: dict[str, re.Pattern] = {
    "словарь": re.compile(r"словар|dictionary|lexicon|кош[аеу]?|koś|monier|monier-williams|бётлинг|böhtlingk|бётлингк|апте|\bapte\b|\bpwg?\b|\bmw\b|тезаурус", re.I),
    "учебник": re.compile(r"учебник|самоучител|граммати|grammar|пани[нь]и|p[āa]nini|урок|упражнени|склонени|спряжени|сандхи|sandhi", re.I),
    "книга": re.compile(r"книг|моногра|издани|djvu|скан|учебн?ое пособ|библиотек|книгохран|печатн", re.I),
    "pdf": re.compile(r"\bpdf\b|\.pdf|ocr|распозна|отскан", re.I),
    "шрифт": re.compile(r"шрифт|\bfont\b|unicode|юникод|кодировк|deva?nagari|деванагари|transliterat|транслитер|раскладк|клавиатур", re.I),
    "текст": re.compile(r"махабхарат|рамаян|\bгита\b|бхагавад|шлок|стих|перевод|упаниш|веды|ведийск|пуран|коммент", re.I),
    "лингвистика": re.compile(r"лингвист|язык[аоуе]|этимолог|фонетик|морфолог|индоевропей|санскрит", re.I),
    "событие": re.compile(r"конференц|семинар|лекци|курс[ыа]?|вебинар|марафон|занят", re.I),
}
TAG_ORDER = list(TOPICS)

DEVANAGARI = re.compile(r"[ऀ-ॿ]{2,}")
IAST = re.compile(r"\b\w*[āīūṛṝḷḹṃṁḥñṅṇṭḍśṣ][\wāīūṛṝḷḹṃṁḥñṅṇṭḍśṣ]*\b", re.I)
WORD_RU = re.compile(r"[а-яёА-ЯЁ]{4,}")
BOOK_ATTACHMENT = re.compile(r"\bdoc\b", re.I)

RU_STOP = set("""это как для что при чтобы если так там весь была было были быть будет
может можно надо нужно есть очень уже или его ему них они она оно этот эта эти тот все
всех всем чем том тем тому кто когда где куда пока ещё еще либо тоже также этого этому
этих такой такие таких себя свои своих спасибо просто здесь речь слово слова также
который которая которые которых свою своей более среди перед после между такое настоящ""".split())

# Engagement score weights (documented choice — views scaled so they don't
# completely dominate likes/reposts on a wall with multi-thousand view counts).
W_LIKES = 1
W_REPOSTS = 5
W_COMMENTS = 2
W_VIEWS_DIV = 50

# Within-year percentile buckets → tier label. Top ~5% = outlier/"viral".
TIER_CUTS = (
    (0.25, "low"),
    (0.50, "mid_low"),
    (0.75, "mid_high"),
    (0.95, "high"),
    (1.01, "viral"),  # remainder; is_outlier also set for top ~5%
)


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def write_csv(path: Path, rows: list[dict], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def engagement_score(likes: int, reposts: int, comments: int, views: int) -> float:
    return (
        W_LIKES * (likes or 0)
        + W_REPOSTS * (reposts or 0)
        + W_COMMENTS * (comments or 0)
        + (views or 0) / W_VIEWS_DIV
    )


# --------------------------------------------------------------------------- #
# Layer 1 — timeline & activity
# --------------------------------------------------------------------------- #
def activity_tables(db: sqlite3.Connection) -> dict:
    rows = db.execute(
        "SELECT year, ym, likes, reposts, comments, views FROM posts WHERE year IS NOT NULL"
    ).fetchall()
    y_posts, y_likes, y_reposts, y_comments, y_views = (
        Counter(), Counter(), Counter(), Counter(), Counter()
    )
    m_posts = Counter()
    for year, ym, likes, reposts, comments, views in rows:
        y_posts[year] += 1
        m_posts[ym] += 1
        y_likes[year] += likes or 0
        y_reposts[year] += reposts or 0
        y_comments[year] += comments or 0
        y_views[year] += views or 0
    by_year = []
    for y in sorted(y_posts):
        n = y_posts[y]
        by_year.append({
            "year": y, "posts": n,
            "likes": y_likes[y], "reposts": y_reposts[y], "comments": y_comments[y], "views": y_views[y],
            "avg_likes": round(y_likes[y] / n, 1), "avg_views": round(y_views[y] / n, 1),
        })
    by_month = [{"ym": ym, "posts": c} for ym, c in sorted(m_posts.items())]
    write_csv(PROCESSED / "activity_by_year.csv", by_year,
              ["year", "posts", "likes", "reposts", "comments", "views", "avg_likes", "avg_views"])
    write_csv(PROCESSED / "activity_by_month.csv", by_month, ["ym", "posts"])

    heat = defaultdict(lambda: [0] * 12)
    for (year, month, c) in db.execute(
        "SELECT year, month, count(*) FROM posts WHERE year IS NOT NULL AND month IS NOT NULL GROUP BY year, month"
    ):
        heat[year][month - 1] = c
    return {"by_year": by_year, "by_month": by_month, "heat": {y: heat[y] for y in sorted(heat)}}


# --------------------------------------------------------------------------- #
# Layer 2 — engagement
# --------------------------------------------------------------------------- #
def engagement_tables(db: sqlite3.Connection) -> dict:
    rows = db.execute(
        "SELECT id, url, date_utc, year, substr(text,1,200), likes, reposts, comments, views "
        "FROM posts ORDER BY likes DESC LIMIT 60"
    ).fetchall()
    top_liked = [
        {"id": r[0], "url": r[1], "date": r[2], "year": r[3] or "", "excerpt": r[4], "likes": r[5],
         "reposts": r[6], "comments": r[7], "views": r[8]}
        for r in rows
    ]
    write_csv(PROCESSED / "top_posts_by_likes.csv", top_liked,
              ["id", "url", "date", "year", "excerpt", "likes", "reposts", "comments", "views"])

    rows = db.execute(
        "SELECT id, url, date_utc, year, substr(text,1,200), likes, reposts, comments, views "
        "FROM posts WHERE views > 0 ORDER BY reposts DESC LIMIT 60"
    ).fetchall()
    top_shared = [
        {"id": r[0], "url": r[1], "date": r[2], "year": r[3] or "", "excerpt": r[4], "likes": r[5],
         "reposts": r[6], "comments": r[7], "views": r[8]}
        for r in rows
    ]
    write_csv(PROCESSED / "top_posts_by_reposts.csv", top_shared,
              ["id", "url", "date", "year", "excerpt", "likes", "reposts", "comments", "views"])

    # like-to-view / repost-to-view conversion by year (engagement rate trend)
    conv_rows = []
    for year, likes, reposts, comments, views in db.execute(
        "SELECT year, sum(likes), sum(reposts), sum(comments), sum(views) FROM posts "
        "WHERE year IS NOT NULL AND views > 0 GROUP BY year ORDER BY year"
    ):
        conv_rows.append({
            "year": year,
            "like_rate_pct": round(100 * likes / views, 2) if views else 0,
            "repost_rate_pct": round(100 * reposts / views, 3) if views else 0,
            "comment_rate_pct": round(100 * comments / views, 3) if views else 0,
        })
    write_csv(PROCESSED / "engagement_rate_by_year.csv", conv_rows,
              ["year", "like_rate_pct", "repost_rate_pct", "comment_rate_pct"])

    totals = db.execute(
        "SELECT count(*), sum(likes), sum(reposts), sum(comments), sum(views) FROM posts"
    ).fetchone()
    return {
        "top_liked": top_liked[:20], "top_shared": top_shared[:20], "conversion": conv_rows,
        "totals": {"posts": totals[0], "likes": totals[1] or 0, "reposts": totals[2] or 0,
                   "comments": totals[3] or 0, "views": totals[4] or 0},
    }


# --------------------------------------------------------------------------- #
# Layer 3 — hashtags + topic taxonomy + term NLP
# --------------------------------------------------------------------------- #
def topic_tables(db: sqlite3.Connection) -> dict:
    rows = db.execute("SELECT id, year, text FROM posts").fetchall()
    topic_year: dict[str, Counter] = defaultdict(Counter)
    topic_total = Counter()
    term_counter: Counter = Counter()
    for _id, year, text in rows:
        blob = (text or "")[:4000]
        matched = [tag for tag, pat in TOPICS.items() if pat.search(blob)]
        if not matched:
            matched = ["разное"]
        for tag in matched:
            topic_total[tag] += 1
            if year:
                topic_year[tag][year] += 1
        for w in WORD_RU.findall(blob.lower()):
            if w not in RU_STOP:
                term_counter[w] += 1
    ty_rows = []
    for tag in TAG_ORDER + ["разное"]:
        for y, c in sorted(topic_year[tag].items()):
            ty_rows.append({"tag": tag, "year": y, "count": c})
    write_csv(PROCESSED / "topics_by_year.csv", ty_rows, ["tag", "year", "count"])
    term_rows = [{"term": t, "count": c} for t, c in term_counter.most_common(300)]
    write_csv(PROCESSED / "post_terms.csv", term_rows, ["term", "count"])

    tag_rows = db.execute(
        "SELECT tag, count(*) FROM hashtags GROUP BY tag ORDER BY 2 DESC"
    ).fetchall()
    hashtag_rows = [{"tag": t, "count": c} for t, c in tag_rows]
    write_csv(PROCESSED / "hashtags.csv", hashtag_rows, ["tag", "count"])

    return {
        "topic_total": dict(topic_total), "topic_year": {k: dict(v) for k, v in topic_year.items()},
        "top_terms": term_rows[:60], "top_hashtags": hashtag_rows[:60],
    }


# --------------------------------------------------------------------------- #
# Layer 4 — Sanskrit terms + attachment inventory + book-flagged posts
# --------------------------------------------------------------------------- #
def sanskrit_and_attachments(db: sqlite3.Connection) -> dict:
    deva, iast = Counter(), Counter()
    for (text,) in db.execute("SELECT substr(text,1,6000) FROM posts"):
        blob = text or ""
        for t in DEVANAGARI.findall(blob):
            deva[t] += 1
        for t in IAST.findall(blob):
            tl = t.lower()
            if len(tl) >= 3:
                iast[tl] += 1
    deva_rows = [{"term": t, "count": c, "script": "devanagari"} for t, c in deva.most_common(200)]
    iast_rows = [{"term": t, "count": c, "script": "iast"} for t, c in iast.most_common(200)]
    write_csv(PROCESSED / "sanskrit_terms.csv", deva_rows + iast_rows, ["term", "count", "script"])

    # attachment type inventory (VK export gives comma-joined type labels, not files)
    type_counter: Counter = Counter()
    for (att,) in db.execute("SELECT attachment_types FROM posts WHERE attachment_types <> ''"):
        for t in (att or "").split(","):
            t = t.strip()
            if t:
                type_counter[t] += 1
    att_rows = [{"type": t, "count": c} for t, c in type_counter.most_common()]
    write_csv(PROCESSED / "attachments_by_type.csv", att_rows, ["type", "count"])

    # book-flagged posts: doc attachment + book/dictionary-ish text
    book_pat = re.compile(r"книг|словар|dictionary|учебн|моногра|издани", re.I)
    book_rows = []
    for _id, url, date, year, text, likes, views, att in db.execute(
        "SELECT id, url, date_utc, year, text, likes, views, attachment_types FROM posts "
        "WHERE attachment_types LIKE '%doc%'"
    ):
        if book_pat.search(text or ""):
            book_rows.append({
                "id": _id, "url": url, "date": date, "year": year or "",
                "excerpt": (text or "")[:200], "likes": likes, "views": views,
            })
    book_rows.sort(key=lambda r: r["likes"], reverse=True)
    write_csv(PROCESSED / "book_posts.csv", book_rows,
              ["id", "url", "date", "year", "excerpt", "likes", "views"])

    return {
        "deva_top": deva_rows[:40], "iast_top": iast_rows[:40],
        "attachments_by_type": att_rows, "n_book_posts": len(book_rows),
        "book_posts_top": book_rows[:60],
    }


# --------------------------------------------------------------------------- #
# Wave-1c — engagement tiers (within-year percentiles)
# --------------------------------------------------------------------------- #
def engagement_tiers(db: sqlite3.Connection) -> dict[int, dict]:
    """Return {post_id: {tier, is_outlier, score, year}} and write CSV."""
    by_year: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for pid, year, likes, reposts, comments, views in db.execute(
        "SELECT id, year, likes, reposts, comments, views FROM posts WHERE year IS NOT NULL"
    ):
        score = engagement_score(likes, reposts, comments, views)
        by_year[year].append((pid, score))

    result: dict[int, dict] = {}
    csv_rows: list[dict] = []
    for year, items in sorted(by_year.items()):
        items_sorted = sorted(items, key=lambda x: x[1])
        n = len(items_sorted)
        for rank, (pid, score) in enumerate(items_sorted):
            # percentile of this post within its year (0..1)
            pct = (rank + 1) / n if n else 0.0
            tier = "low"
            for cut, label in TIER_CUTS:
                if pct <= cut:
                    tier = label
                    break
            is_outlier = pct > 0.95  # top ~5%
            if is_outlier:
                tier = "viral"
            result[pid] = {
                "tier": tier,
                "is_outlier": is_outlier,
                "score": round(score, 2),
                "year": year,
                "percentile": round(pct, 4),
            }
            csv_rows.append({
                "post_id": pid,
                "year": year,
                "tier": tier,
                "is_outlier": int(is_outlier),
                "score": round(score, 2),
                "percentile": round(pct, 4),
            })
    write_csv(
        PROCESSED / "engagement_tiers.csv",
        csv_rows,
        ["post_id", "year", "tier", "is_outlier", "score", "percentile"],
    )
    # Sanity: ~5% outliers overall
    n_out = sum(1 for v in result.values() if v["is_outlier"])
    n_all = len(result) or 1
    print(f"  engagement tiers: {n_all} posts, {n_out} outliers ({100*n_out/n_all:.1f}%)", flush=True)
    return result


# --------------------------------------------------------------------------- #
# Wave-1a/1b — gallery + search index
# --------------------------------------------------------------------------- #
def gallery_and_search(db: sqlite3.Connection, tiers: dict[int, dict]) -> dict:
    """Build gallery CSV/JSON + compact per-post search index."""
    # tags by post
    tags_by_post: dict[int, list[str]] = defaultdict(list)
    for pid, tag in db.execute("SELECT post_id, tag FROM hashtags"):
        tags_by_post[pid].append(tag)

    # attachments joined to posts
    gallery_rows: list[dict] = []
    att_types_by_post: dict[int, set[str]] = defaultdict(set)
    n_att = 0
    try:
        att_query = db.execute(
            """SELECT a.post_id, a.type, a.url, a.width, a.height, a.position,
                      p.url, p.date_utc, p.year, substr(p.text,1,160),
                      p.likes, p.reposts, p.comments, p.views
               FROM attachments a
               JOIN posts p ON p.id = a.post_id
               ORDER BY p.date_utc DESC, a.position"""
        )
    except sqlite3.OperationalError:
        att_query = []

    for row in att_query:
        (
            post_id, atype, aurl, width, height, pos,
            purl, date_utc, year, excerpt, likes, reposts, comments, views,
        ) = row
        n_att += 1
        att_types_by_post[post_id].add(atype)
        tier_info = tiers.get(post_id) or {}
        gallery_rows.append({
            "post_id": post_id,
            "type": atype,
            "url": aurl or "",
            "width": width or "",
            "height": height or "",
            "position": pos,
            "post_url": purl or "",
            "date": (date_utc or "")[:10],
            "year": year or "",
            "excerpt": excerpt or "",
            "likes": likes or 0,
            "reposts": reposts or 0,
            "comments": comments or 0,
            "views": views or 0,
            "tags": " ".join(tags_by_post.get(post_id) or []),
            "engagement_tier": tier_info.get("tier") or "",
            "is_outlier": int(bool(tier_info.get("is_outlier"))),
        })

    write_csv(
        PROCESSED / "attachments_gallery.csv",
        gallery_rows,
        [
            "post_id", "type", "url", "width", "height", "position",
            "post_url", "date", "year", "excerpt", "likes", "reposts",
            "comments", "views", "tags", "engagement_tier", "is_outlier",
        ],
    )

    # Gallery for the page: prefer items with a renderable URL; cap for payload size
    gallery_for_page = [
        {
            "post_id": r["post_id"],
            "type": r["type"],
            "url": r["url"],
            "post_url": r["post_url"],
            "date": r["date"],
            "year": r["year"],
            "excerpt": (r["excerpt"] or "")[:120],
            "likes": r["likes"],
            "engagement_tier": r["engagement_tier"],
            "is_outlier": r["is_outlier"],
            "tags": r["tags"],
        }
        for r in gallery_rows
        if r["url"] or r["type"] in ("photo", "video", "doc", "link")
    ]
    # Cap gallery payload (hotlinked thumbs); keep newest first
    GALLERY_CAP = 800
    gallery_for_page = gallery_for_page[:GALLERY_CAP]

    # Compact search index: one object per post
    search_index: list[dict] = []
    for pid, date_utc, year, text, likes, reposts, comments, views, att_types, purl in db.execute(
        "SELECT id, date_utc, year, substr(text,1,280), likes, reposts, comments, views, "
        "attachment_types, url FROM posts ORDER BY date_utc DESC"
    ):
        tier_info = tiers.get(pid) or {}
        types = sorted(att_types_by_post.get(pid) or set())
        if not types and att_types:
            types = sorted(t.strip() for t in att_types.split(",") if t.strip())
        search_index.append({
            "id": pid,
            "date": (date_utc or "")[:10],
            "year": year or "",
            "text": text or "",
            "tags": tags_by_post.get(pid) or [],
            "attachment_types": types,
            "engagement_tier": tier_info.get("tier") or "low",
            "is_outlier": bool(tier_info.get("is_outlier")),
            "url": purl or "",
            "likes": likes or 0,
            "reposts": reposts or 0,
            "views": views or 0,
            "score": tier_info.get("score") or 0,
        })

    print(f"  gallery: {n_att} attachment rows, {len(gallery_for_page)} in page payload", flush=True)
    print(f"  search index: {len(search_index)} posts", flush=True)

    # Tier distribution for engagement explorer
    tier_year: dict[str, Counter] = defaultdict(Counter)
    for info in tiers.values():
        tier_year[str(info["year"])][info["tier"]] += 1
    tier_by_year = {
        y: dict(counts) for y, counts in sorted(tier_year.items())
    }

    # Top posts per tier (for explorer)
    top_by_tier: dict[str, list] = defaultdict(list)
    for item in sorted(search_index, key=lambda x: -float(x.get("score") or 0)):
        t = item["engagement_tier"]
        if len(top_by_tier[t]) < 12:
            top_by_tier[t].append({
                "id": item["id"], "url": item["url"], "date": item["date"],
                "excerpt": (item["text"] or "")[:140], "likes": item["likes"],
                "score": item["score"], "year": item["year"],
            })

    return {
        "gallery": gallery_for_page,
        "search_index": search_index,
        "n_attachments": n_att,
        "tier_by_year": tier_by_year,
        "top_by_tier": dict(top_by_tier),
        "score_weights": {
            "likes": W_LIKES, "reposts": W_REPOSTS,
            "comments": W_COMMENTS, "views_div": W_VIEWS_DIV,
        },
    }


def totals(db: sqlite3.Connection) -> dict:
    n_posts = db.execute("SELECT count(*) FROM posts").fetchone()[0]
    n_tags = db.execute("SELECT count(DISTINCT tag) FROM hashtags").fetchone()[0]
    dmin, dmax = db.execute("SELECT min(date_utc), max(date_utc) FROM posts WHERE date_utc<>''").fetchone()
    sums = db.execute("SELECT sum(likes), sum(reposts), sum(comments), sum(views) FROM posts").fetchone()
    n_att = 0
    try:
        n_att = db.execute("SELECT count(*) FROM attachments").fetchone()[0]
    except sqlite3.OperationalError:
        pass
    return {
        "posts": n_posts, "distinct_hashtags": n_tags, "date_min": dmin, "date_max": dmax,
        "likes": sums[0] or 0, "reposts": sums[1] or 0, "comments": sums[2] or 0, "views": sums[3] or 0,
        "attachments": n_att,
    }


def run(db_path: Path) -> dict:
    db = sqlite3.connect(db_path)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    site: dict = {"totals": totals(db)}
    print("  layer 1: activity", flush=True); site["activity"] = activity_tables(db)
    print("  layer 2: engagement", flush=True); site["engagement"] = engagement_tables(db)
    print("  layer 3: topics + hashtags", flush=True); site["topics"] = topic_tables(db)
    print("  layer 4: sanskrit + attachments", flush=True); site["sanskrit"] = sanskrit_and_attachments(db)
    print("  wave-1c: engagement tiers", flush=True); tiers = engagement_tiers(db)
    print("  wave-1a/b: gallery + search index", flush=True); advanced = gallery_and_search(db, tiers)
    db.close()

    site_page = {
        "totals": site["totals"],
        "activity": site["activity"],
        "engagement": {k: v for k, v in site["engagement"].items() if k != "top_shared"} | {
            "top_shared": site["engagement"]["top_shared"][:20]
        },
        "topics": site["topics"],
        "sanskrit": {k: v for k, v in site["sanskrit"].items() if k != "book_posts_top"},
        "books_top": site["sanskrit"]["book_posts_top"][:40],
        # Wave-1 advanced viz payload
        "gallery": advanced["gallery"],
        "search_index": advanced["search_index"],
        "tier_by_year": advanced["tier_by_year"],
        "top_by_tier": advanced["top_by_tier"],
        "score_weights": advanced["score_weights"],
        "n_attachments": advanced["n_attachments"],
    }
    (PROCESSED.parent / "site_data.json").write_text(
        json.dumps(site_page, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return site["totals"]


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args(argv)
    t = run(args.db)
    print(f"insights done: {t}", flush=True)


if __name__ == "__main__":
    main()
