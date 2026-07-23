"""Compute the analysis layers from ``vk_ors.db`` into CSV tables + ``site_data.json``.

Four layers, adapted from ``nagari_group_archive.insights`` to a VK wall export
(no thread/reply graph, no per-author breakdown — one publishing account, but
rich per-post engagement counters instead):

1. Timeline & activity   — posts per year & month, engagement sums/averages.
2. Engagement            — top posts by likes/reposts/comments/views, the
                            like-to-view and repost-to-view conversion trend.
3. Topics & hashtags      — the page's own hashtag taxonomy + a keyword topic
                            map applied to post text, topic trends over time.
4. Sanskrit / attachment layer — Devanagari & IAST term frequency, attachment
                            type inventory, book-flagged posts (doc attachment
                            + book-ish text).

Everything is written under ``<pkg>/../data/processed/`` and bundled into
``site_data.json``. Interpretive guardrails from the nagari/Indology packages
apply: likes are not agreement, views are not readership, hashtag presence is
not a curated taxonomy.
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


def totals(db: sqlite3.Connection) -> dict:
    n_posts = db.execute("SELECT count(*) FROM posts").fetchone()[0]
    n_tags = db.execute("SELECT count(DISTINCT tag) FROM hashtags").fetchone()[0]
    dmin, dmax = db.execute("SELECT min(date_utc), max(date_utc) FROM posts WHERE date_utc<>''").fetchone()
    sums = db.execute("SELECT sum(likes), sum(reposts), sum(comments), sum(views) FROM posts").fetchone()
    return {
        "posts": n_posts, "distinct_hashtags": n_tags, "date_min": dmin, "date_max": dmax,
        "likes": sums[0] or 0, "reposts": sums[1] or 0, "comments": sums[2] or 0, "views": sums[3] or 0,
    }


def run(db_path: Path) -> dict:
    db = sqlite3.connect(db_path)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    site: dict = {"totals": totals(db)}
    print("  layer 1: activity", flush=True); site["activity"] = activity_tables(db)
    print("  layer 2: engagement", flush=True); site["engagement"] = engagement_tables(db)
    print("  layer 3: topics + hashtags", flush=True); site["topics"] = topic_tables(db)
    print("  layer 4: sanskrit + attachments", flush=True); site["sanskrit"] = sanskrit_and_attachments(db)
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
