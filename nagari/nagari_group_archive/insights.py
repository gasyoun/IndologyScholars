"""Compute the analysis layers from ``nagari.db`` into CSV tables + ``site_data.json``.

Four layers, mirroring the Indology atlas playbook but exploiting the full bodies
that a *closed* Takeout export gives us:

1. Timeline & activity   — messages/threads/authors per year & month, member joins.
2. Threads & networks     — thread sizes, directed reply edges, co-participation.
3. Topics & body NLP      — the group's own tag taxonomy applied to subject+body,
                            topic trends, top terms.
4. Sanskrit / book layer  — Devanagari & IAST term frequency, attachment inventory,
                            the shared-book ("Книгохранилище") index, font/unicode threads.

Everything is written under ``<pkg>/../data/processed/`` and bundled into
``site_data.json`` for the standalone HTML page. Interpretive guardrails from the
Indology package apply: reply edges are not influence, co-participation is not
collaboration, message count is not importance.
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

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "nagari.db"
PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"

# --- Topic taxonomy: the group's own tags, expressed as keyword patterns over
#     subject+body. A message can match several tags; "разное" is the fallback. ---
TOPICS: dict[str, re.Pattern] = {
    "словарь": re.compile(r"словар|dictionary|lexicon|кош[аеу]?|koś|monier|monier-williams|бётлинг|böhtlingk|бётлингк|апте|\bapte\b|\bpwg?\b|\bmw\b|тезаурус", re.I),
    "учебник": re.compile(r"учебник|самоучител|граммати|grammar|пани[нь]и|p[āa]nini|урок|упражнени|склонени|спряжени|сандхи|sandhi", re.I),
    "книга": re.compile(r"книг|моногра|издани|djvu|скан|учебн?ое пособ|библиотек|книгохран|печатн", re.I),
    "pdf": re.compile(r"\bpdf\b|\.pdf|ocr|распозна|отскан", re.I),
    "сайт": re.compile(r"сайт|\bsite\b|github|программ|приложени|онлайн|\bapp\b|sanskrit-lexicon|api|базу данных|базы данных", re.I),
    "шрифт": re.compile(r"шрифт|\bfont\b|unicode|юникод|кодировк|deva?nagari|деванагари|transliterat|транслитер|раскладк|клавиатур", re.I),
    "астрология": re.compile(r"астролог|джьоти|jyoti|гороскоп|накшатр|планет|зодиак", re.I),
    "текст": re.compile(r"махабхарат|рамаян|\bгита\b|бхагавад|шлок|стих|перевод|упаниш|веды|ведийск|пуран|коммент", re.I),
}
TAG_ORDER = list(TOPICS)

DEVANAGARI = re.compile(r"[ऀ-ॿ]{2,}")
IAST = re.compile(r"\b\w*[āīūṛṝḷḹṃṁḥñṅṇṭḍśṣ][\wāīūṛṝḷḹṃṁḥñṅṇṭḍśṣ]*\b", re.I)
WORD_RU = re.compile(r"[а-яёА-ЯЁ]{4,}")
BOOK_EXT = {"pdf", "djvu", "epub", "fb2", "doc", "docx", "rtf", "txt"}

RU_STOP = set("""это как для что при чтобы если так там весь была было были быть будет
может можно надо нужно есть очень уже или его ему них они она оно этот эта эти тот все
всех всем чем том тем тому кто когда где куда пока ещё еще либо тоже также этого этому
этих такой такие таких себя свои своих спасибо просто здесь речь слово слова также""".split())


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


def author_key(name: str, email: str) -> str:
    """Prefer a stable email; fall back to a normalized display name."""
    email = (email or "").strip().lower()
    if email:
        return email
    return re.sub(r"\s+", " ", (name or "").strip().casefold()) or "(unknown)"


# --------------------------------------------------------------------------- #
# Layer 1 — timeline & activity
# --------------------------------------------------------------------------- #
def activity_tables(db: sqlite3.Connection) -> dict:
    by_year, by_month = [], []
    joins = dict(db.execute("SELECT joined_year,count(*) FROM members WHERE joined_year IS NOT NULL GROUP BY joined_year"))
    rows = db.execute(
        "SELECT year, ym, gm_thrid, from_name, from_email FROM messages WHERE year IS NOT NULL"
    ).fetchall()
    y_msg, y_thr, y_auth = Counter(), defaultdict(set), defaultdict(set)
    m_msg = Counter()
    for year, ym, thr, name, email in rows:
        y_msg[year] += 1
        m_msg[ym] += 1
        if thr:
            y_thr[year].add(thr)
        y_auth[year].add(author_key(name, email))
    for y in sorted(y_msg):
        by_year.append({
            "year": y, "messages": y_msg[y], "threads": len(y_thr[y]),
            "active_authors": len(y_auth[y]), "new_members": joins.get(y, 0),
        })
    for ym in sorted(m_msg):
        by_month.append({"ym": ym, "messages": m_msg[ym]})
    write_csv(PROCESSED / "activity_by_year.csv", by_year, ["year", "messages", "threads", "active_authors", "new_members"])
    write_csv(PROCESSED / "activity_by_month.csv", by_month, ["ym", "messages"])

    # month-of-year heatmap (seasonality): year x month message counts
    heat = defaultdict(lambda: [0] * 12)
    for (year, month, c) in db.execute(
        "SELECT year, month, count(*) FROM messages WHERE year IS NOT NULL AND month IS NOT NULL GROUP BY year, month"
    ):
        heat[year][month - 1] = c
    return {"by_year": by_year, "by_month": by_month, "heat": {y: heat[y] for y in sorted(heat)}}


# --------------------------------------------------------------------------- #
# Layer 2 — threads, reply network, co-participation
# --------------------------------------------------------------------------- #
def thread_and_network_tables(db: sqlite3.Connection) -> dict:
    msgs = db.execute(
        "SELECT id, gm_thrid, message_id, in_reply_to, from_name, from_email, date_utc, subject_clean, year FROM messages"
    ).fetchall()
    id_by_mid = {}
    author_by_id = {}
    for mid_row in msgs:
        _id, thr, message_id, irt, name, email, date, subj, year = mid_row
        author_by_id[_id] = author_key(name, email)
        if message_id:
            id_by_mid[message_id] = _id

    # thread sizes
    thr_msgs = defaultdict(list)
    for r in msgs:
        thr_msgs[r[1]].append(r)
    thread_rows = []
    for thr, items in thr_msgs.items():
        if not thr:
            continue
        items.sort(key=lambda x: x[6] or "")
        authors = {author_key(x[4], x[5]) for x in items}
        dates = [x[6] for x in items if x[6]]
        starter = items[0]
        thread_rows.append({
            "gm_thrid": thr, "subject": starter[7], "n_messages": len(items),
            "n_authors": len(authors), "starter": starter[4],
            "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
            "year": starter[8] or "",
        })
    thread_rows.sort(key=lambda r: r["n_messages"], reverse=True)
    write_csv(PROCESSED / "thread_sizes.csv", thread_rows,
              ["gm_thrid", "subject", "n_messages", "n_authors", "starter", "first", "last", "year"])

    # directed reply edges (In-Reply-To resolved to a known message)
    reply_edges = Counter()
    resolved = 0
    for r in msgs:
        _id, thr, message_id, irt, name, email, date, subj, year = r
        if irt and irt in id_by_mid:
            parent = id_by_mid[irt]
            src, dst = author_by_id[_id], author_by_id.get(parent, "")
            if dst and src != dst:
                reply_edges[(src, dst)] += 1
                resolved += 1
    reply_rows = [{"src": s, "dst": d, "weight": w} for (s, d), w in reply_edges.most_common()]
    write_csv(PROCESSED / "reply_network.csv", reply_rows, ["src", "dst", "weight"])

    # co-participation (undirected): authors sharing a thread
    copart = Counter()
    for thr, items in thr_msgs.items():
        if not thr:
            continue
        auths = sorted({author_key(x[4], x[5]) for x in items})
        for i in range(len(auths)):
            for j in range(i + 1, len(auths)):
                copart[(auths[i], auths[j])] += 1
    copart_rows = [{"a": a, "b": b, "shared_threads": w} for (a, b), w in copart.most_common(2000)]
    write_csv(PROCESSED / "coparticipation.csv", copart_rows, ["a", "b", "shared_threads"])

    # top authors
    a_msg, a_started, a_first, a_last, a_name = Counter(), Counter(), {}, {}, {}
    for r in msgs:
        k = author_key(r[4], r[5])
        a_msg[k] += 1
        d = r[6] or ""
        if d:
            a_first[k] = min(a_first.get(k, d), d)
            a_last[k] = max(a_last.get(k, d), d)
        if r[4] and (k not in a_name or len(r[4]) > len(a_name[k])):
            a_name[k] = r[4]
    for tr in thread_rows:
        pass
    starter_counts = Counter(author_key(x[4], x[5]) for items in thr_msgs.values() for x in [items[0]] if x[1])
    author_rows = []
    for k, c in a_msg.most_common():
        author_rows.append({
            "author": a_name.get(k, k), "key": k, "messages": c,
            "threads_started": starter_counts.get(k, 0),
            "first": a_first.get(k, ""), "last": a_last.get(k, ""),
            "years_active": (int(a_last[k][:4]) - int(a_first[k][:4]) + 1) if k in a_first else 0,
        })
    write_csv(PROCESSED / "top_authors.csv", author_rows,
              ["author", "key", "messages", "threads_started", "first", "last", "years_active"])

    return {
        "threads": thread_rows, "reply_rows": reply_rows, "authors": author_rows,
        "reply_resolved": resolved, "n_threads": len(thread_rows),
    }


# --------------------------------------------------------------------------- #
# Layer 3 — topic taxonomy + body NLP
# --------------------------------------------------------------------------- #
def topic_tables(db: sqlite3.Connection) -> dict:
    rows = db.execute("SELECT id, year, subject_clean, body_text FROM messages").fetchall()
    topic_year = defaultdict(Counter)   # tag -> year -> count
    topic_total = Counter()
    term_counter = Counter()
    msg_tags = []
    for _id, year, subj, body in rows:
        text = f"{subj or ''}\n{(body or '')[:4000]}"
        matched = [tag for tag, pat in TOPICS.items() if pat.search(text)]
        if not matched:
            matched = ["разное"]
        for tag in matched:
            topic_total[tag] += 1
            if year:
                topic_year[tag][year] += 1
        # Russian content terms (subjects only — cleaner signal than bodies)
        for w in WORD_RU.findall((subj or "").lower()):
            if w not in RU_STOP:
                term_counter[w] += 1
    ty_rows = []
    for tag in TAG_ORDER + ["разное"]:
        for y, c in sorted(topic_year[tag].items()):
            ty_rows.append({"tag": tag, "year": y, "count": c})
    write_csv(PROCESSED / "topics_by_year.csv", ty_rows, ["tag", "year", "count"])
    term_rows = [{"term": t, "count": c} for t, c in term_counter.most_common(300)]
    write_csv(PROCESSED / "subject_terms.csv", term_rows, ["term", "count"])
    return {"topic_total": dict(topic_total), "topic_year": {k: dict(v) for k, v in topic_year.items()},
            "top_terms": term_rows[:60]}


# --------------------------------------------------------------------------- #
# Layer 4 — Sanskrit terms, attachments, shared-book index
# --------------------------------------------------------------------------- #
def sanskrit_and_books(db: sqlite3.Connection) -> dict:
    deva, iast = Counter(), Counter()
    for (subj, body) in db.execute("SELECT subject_clean, substr(body_text,1,6000) FROM messages"):
        blob = f"{subj or ''} {body or ''}"
        for t in DEVANAGARI.findall(blob):
            deva[t] += 1
        for t in IAST.findall(blob):
            tl = t.lower()
            if len(tl) >= 3:
                iast[tl] += 1
    deva_rows = [{"term": t, "count": c, "script": "devanagari"} for t, c in deva.most_common(200)]
    iast_rows = [{"term": t, "count": c, "script": "iast"} for t, c in iast.most_common(200)]
    write_csv(PROCESSED / "sanskrit_terms.csv", deva_rows + iast_rows, ["term", "count", "script"])

    # attachment inventory
    by_ext = []
    for ext, n, total in db.execute(
        "SELECT ext, count(*), sum(size_bytes) FROM attachments GROUP BY ext ORDER BY 2 DESC"
    ):
        by_ext.append({"ext": ext or "(none)", "count": n, "total_bytes": total or 0})
    write_csv(PROCESSED / "attachments_by_type.csv", by_ext, ["ext", "count", "total_bytes"])

    # shared-book index: book-like attachments joined to the sharing message
    book_rows = []
    q = """SELECT a.filename, a.ext, a.size_bytes, m.from_name, m.date_utc, m.subject_clean, m.gm_thrid, m.year
           FROM attachments a JOIN messages m ON m.id=a.message_id
           WHERE a.ext IN ({}) AND a.size_bytes > 50000
           ORDER BY a.size_bytes DESC""".format(",".join("?" * len(BOOK_EXT)))
    for fn, ext, size, sharer, date, subj, thr, year in db.execute(q, tuple(BOOK_EXT)):
        book_rows.append({
            "filename": fn, "ext": ext, "size_bytes": size, "sharer": sharer,
            "date": date, "subject": subj, "gm_thrid": thr, "year": year or "",
        })
    write_csv(PROCESSED / "book_index.csv", book_rows,
              ["filename", "ext", "size_bytes", "sharer", "date", "subject", "gm_thrid", "year"])

    # font/unicode threads
    font_rows = []
    for _id, subj, year, name in db.execute(
        "SELECT id, subject_clean, year, from_name FROM messages "
        "WHERE subject_clean LIKE '%шрифт%' OR subject_clean LIKE '%font%' "
        "OR subject_clean LIKE '%unicode%' OR subject_clean LIKE '%юникод%' "
        "OR subject_clean LIKE '%деванагари%' OR subject_clean LIKE '%кодировк%'"
    ):
        font_rows.append({"id": _id, "subject": subj, "year": year or "", "from_name": name})
    write_csv(PROCESSED / "font_unicode_threads.csv", font_rows, ["id", "subject", "year", "from_name"])

    return {
        "deva_top": deva_rows[:40], "iast_top": iast_rows[:40],
        "attachments_by_type": by_ext, "n_books": len(book_rows),
        "books_top": book_rows[:60], "n_font_threads": len(font_rows),
        "book_bytes": sum(r["size_bytes"] for r in book_rows),
    }


def totals(db: sqlite3.Connection) -> dict:
    n_msg = db.execute("SELECT count(*) FROM messages").fetchone()[0]
    n_thr = db.execute("SELECT count(DISTINCT gm_thrid) FROM messages WHERE gm_thrid<>''").fetchone()[0]
    n_auth = db.execute("SELECT count(DISTINCT COALESCE(NULLIF(from_email,''), lower(from_name))) FROM messages").fetchone()[0]
    n_mem = db.execute("SELECT count(*) FROM members").fetchone()[0]
    n_att = db.execute("SELECT count(*) FROM attachments").fetchone()[0]
    dmin, dmax = db.execute("SELECT min(date_utc), max(date_utc) FROM messages WHERE date_utc<>''").fetchone()
    return {"messages": n_msg, "threads": n_thr, "authors": n_auth, "members": n_mem,
            "attachments": n_att, "date_min": dmin, "date_max": dmax}


def run(db_path: Path) -> dict:
    db = sqlite3.connect(db_path)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    site = {"totals": totals(db)}
    print("  layer 1: activity", flush=True); site["activity"] = activity_tables(db)
    print("  layer 2: threads + networks", flush=True); site["network"] = thread_and_network_tables(db)
    print("  layer 3: topics + terms", flush=True); site["topics"] = topic_tables(db)
    print("  layer 4: sanskrit + books", flush=True); site["sanskrit"] = sanskrit_and_books(db)
    db.close()
    # trim the network payload for the page (full tables live in CSV)
    site_page = {
        "totals": site["totals"],
        "activity": site["activity"],
        "topics": site["topics"],
        "sanskrit": {k: v for k, v in site["sanskrit"].items() if k != "books_top"},
        "top_authors": site["network"]["authors"][:40],
        "top_threads": site["network"]["threads"][:40],
        "reply_top": site["network"]["reply_rows"][:120],
        "books_top": site["sanskrit"]["books_top"][:40],
        "meta": {"reply_resolved": site["network"]["reply_resolved"], "n_threads": site["network"]["n_threads"]},
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
