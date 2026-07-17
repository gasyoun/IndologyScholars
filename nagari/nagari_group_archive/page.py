"""Generate the standalone HTML retrospective «20 лет Обществу ревнителей санскрита».

Self-contained (no CDN): all CSS + JS + data inline. Hybrid narrative + interactive
SVG charts (hover tooltips, table views, light/dark). Palette is the validated
data-viz reference instance (8-hue categorical + neutral "разное"; sequential blue
for the heatmap). Reads the outputs of :mod:`insights` and renders them; nothing is
recomputed here except a few narrative figures.

Guardrails (carried from the Indology atlas): reply edges are not influence,
co-participation is not collaboration, message count is not scholarly importance,
and display names / handles are shown unmerged.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

from nagari_group_archive.export_md import slug as md_slug
from nagari_group_archive.redact import NAME_STOP, mask_name, redact_emails

PKG_DATA = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DUMP = Path(
    r"C:/Users/user/Documents/GitHub/IndologyScholars/nagari-2005-2026/nagari@googlegroups.com"
)
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "site" / "index.html"

# Every thread's per-message mirror is published as a Markdown file at this path
# pattern (see export_md.py); mirror the same subject/year/thrid -> filename
# logic here so the site can link straight to the online blob.
REPO_BLOB = "https://github.com/gasyoun/IndologyScholars/blob/main"


def thread_md_url(subject_raw: str, year: str, gm_thrid: str) -> str:
    subj = redact_emails(subject_raw) or "(без темы)"
    y = year if year else "undated"
    fname = f"{md_slug(subj)}__{str(gm_thrid)[-8:]}.md"
    return f"{REPO_BLOB}/{quote(f'nagari/md/{y}/{fname}')}"


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def rd(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def group_description(dump: Path) -> tuple[str, str]:
    info = dump / "info.csv"
    if not info.exists():
        return ("Общество ревнителей санскрита (Sanscrit)", "")
    with info.open(encoding="utf-8") as fh:
        row = next(csv.DictReader(fh), {})
    return (row.get("name", "").strip(), (row.get("description", "") or "").strip())


def human_bytes(n: int) -> str:
    n = float(n or 0)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.1f} {unit}" if unit != "Б" else f"{int(n)} Б"
        n /= 1024
    return f"{n:.1f} ГБ"


def build(dump: Path, out: Path) -> dict:
    site = json.loads((PKG_DATA / "site_data.json").read_text(encoding="utf-8"))
    threads = rd(PKG_DATA / "processed" / "thread_sizes.csv")
    books = rd(PKG_DATA / "processed" / "book_index.csv")
    authors = rd(PKG_DATA / "processed" / "top_authors.csv")
    name, desc = group_description(dump)

    # export_md.py names each file after its thread's *starter* message subject/year,
    # which can differ from the subject/year of whichever message shared a given
    # attachment (thread drift) -- look the URL up by gm_thrid, never recompute it
    # from a book/message row directly, or the link 404s.
    thread_by_id = {t["gm_thrid"]: t for t in threads}

    def md_url_for_thread(gm_thrid: str, fallback_subject: str, fallback_year: str) -> str:
        t = thread_by_id.get(gm_thrid)
        if t is not None:
            return thread_md_url(t["subject"], t["year"], gm_thrid)
        return thread_md_url(fallback_subject, fallback_year, gm_thrid)

    tot = site["totals"]
    ay = site["activity"]["by_year"]
    for r in ay:
        for k in ("year", "messages", "threads", "active_authors", "new_members"):
            r[k] = int(r[k])
    peak = max(ay, key=lambda r: r["messages"])
    first_year, last_year = ay[0]["year"], ay[-1]["year"]
    span = last_year - first_year

    # Partial final year: the mbox ends mid-year (date_max), so the last point in
    # every by-year series covers only part of its year. Left unmarked, the short
    # final bar reads as a collapse rather than an incomplete year. Compute the
    # coverage and an annualized projection so the page can say so; self-disables
    # on a future full-year rebuild (coverage ~1.0 -> partial is None).
    MONTHS_RU = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    partial = None
    dmax = str(tot.get("date_max") or "")[:10]
    if dmax:
        yy, mm, dd = (int(x) for x in dmax.split("-"))
        doy = date(yy, mm, dd).timetuple().tm_yday
        ydays = 366 if (yy % 4 == 0 and (yy % 100 != 0 or yy % 400 == 0)) else 365
        cov = doy / ydays
        if last_year == yy and cov < 0.99:
            partial = {
                "year": yy,
                "cutoff": dmax,
                "cutoff_ru": f"{dd} {MONTHS_RU[mm]} {yy}",
                "coverage_pct": round(cov * 100),
                "annualized_msgs": round(ay[-1]["messages"] / cov),
            }
    total_att_bytes = sum(int(r["total_bytes"] or 0) for r in site["sanskrit"]["attachments_by_type"])

    # cumulative membership curve
    cum = 0
    membership = []
    for r in ay:
        cum += r["new_members"]
        membership.append({"year": r["year"], "cum": cum, "new": r["new_members"]})

    # topic order by total, split colored vs neutral "разное"
    topic_total = site["topics"]["topic_total"]
    colored = [t for t in sorted(topic_total, key=lambda t: -topic_total[t]) if t != "разное"][:8]
    topic_year = site["topics"]["topic_year"]
    years = [r["year"] for r in ay]
    topic_series = []
    for tag in colored + (["разное"] if "разное" in topic_total else []):
        topic_series.append({"tag": tag, "values": [topic_year.get(tag, {}).get(str(y), topic_year.get(tag, {}).get(y, 0)) for y in years]})

    # reply network: index nodes (0..N) so no email addresses reach the page
    name_by_key = {a["key"]: a["author"] for a in authors}
    msgs_by_key = {a["key"]: int(a["messages"]) for a in authors}
    top_keys = [a["key"] for a in authors[:26]]
    id_by_key = {k: i for i, k in enumerate(top_keys)}
    edges = []
    for e in site["reply_top"]:
        if e["src"] in id_by_key and e["dst"] in id_by_key and e["src"] != e["dst"]:
            edges.append({"s": id_by_key[e["src"]], "d": id_by_key[e["dst"]], "w": int(e["weight"])})
    nodes = [{"id": i, "name": mask_name(name_by_key.get(k, k)), "msgs": msgs_by_key.get(k, 0)}
             for i, k in enumerate(top_keys)]

    # books per year
    book_year = {}
    for b in books:
        y = b["year"] or "?"
        book_year[y] = book_year.get(y, 0) + 1
    books_by_year = [{"year": int(y), "count": c} for y, c in sorted(book_year.items()) if str(y).isdigit()]

    # sanskrit terms (filter names out of IAST)
    deva = [{"t": r["term"], "c": int(r["count"])} for r in site["sanskrit"]["deva_top"]][:24]
    iast = [{"t": r["term"], "c": int(r["count"])} for r in site["sanskrit"]["iast_top"] if r["term"] not in NAME_STOP][:24]

    # embeddable compact thread list for search/browse
    thr_compact = [
        [redact_emails(t["subject"])[:120], mask_name(t["starter"]), int(t["year"]) if str(t["year"]).isdigit() else 0,
         int(t["n_messages"]), int(t["n_authors"]), thread_md_url(t["subject"], t["year"], t["gm_thrid"])]
        for t in threads if t["subject"]
    ]

    # notable threads (biggest) + tag the Gita court case
    notable = [
        {"subject": redact_emails(t["subject"]), "year": t["year"], "n": int(t["n_messages"]), "a": int(t["n_authors"]),
         "starter": mask_name(t["starter"]), "url": thread_md_url(t["subject"], t["year"], t["gm_thrid"])}
        for t in threads[:24]
    ]

    top_authors_disp = [
        {"name": mask_name(a["author"]), "msgs": int(a["messages"]), "started": int(a["threads_started"]),
         "first": a["first"][:4], "last": a["last"][:4]}
        for a in authors[:20]
    ]

    heat = site["activity"]["heat"]

    payload = {
        "totals": tot, "activity": ay, "membership": membership, "peak": peak,
        "topic_series": topic_series, "topic_total": topic_total,
        "nodes": nodes, "edges": edges,
        "books_by_year": books_by_year, "notable": notable,
        "deva": deva, "iast": iast, "heat": heat,
        "attachments_by_type": site["sanskrit"]["attachments_by_type"],
        "top_authors": top_authors_disp, "threads": thr_compact,
        "book_top": [{"f": redact_emails(b["filename"]), "ext": b["ext"], "y": b["year"], "mb": round(int(b["size_bytes"]) / 1e6, 1), "by": mask_name(b["sharer"]),
                      "url": md_url_for_thread(b["gm_thrid"], b["subject"], b["year"])} for b in books[:60]],
        "meta": {
            "n_books": len(books), "att_bytes": total_att_bytes, "span": span,
            "first_year": first_year, "last_year": last_year,
            "reply_resolved": site["meta"]["reply_resolved"], "n_font": site["sanskrit"]["n_font_threads"],
            "n_pdf": next((int(r["count"]) for r in site["sanskrit"]["attachments_by_type"] if r["ext"] == "pdf"), 0),
            "partial": partial,
        },
    }

    facts = {
        "name": name, "desc": desc,
        "att_human": human_bytes(total_att_bytes),
        "peak_year": peak["year"], "peak_msgs": peak["messages"],
        "join2007": next((r["new_members"] for r in ay if r["year"] == 2007), 0),
        "recent_threads": next((r["threads"] for r in ay if r["year"] == 2025), 0),
        "top_author": authors[0]["author"], "top_author_msgs": int(authors[0]["messages"]),
        "top_author_started": int(authors[0]["threads_started"]),
    }

    html = render(payload, facts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return {"out": str(out), "bytes": len(html.encode("utf-8")), "threads_embedded": len(thr_compact)}


def render(payload: dict, f: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    tot = payload["totals"]
    meta = payload["meta"]
    tmpl = TEMPLATE
    repl = {
        "__DATA__": data_json,
        "__DESC__": f["desc"],
        "__SPAN__": str(meta["span"] + 1),
        "__FY__": str(meta["first_year"]),
        "__LY__": str(meta["last_year"]),
        "__MSGS__": f"{tot['messages']:,}".replace(",", " "),
        "__THREADS__": f"{tot['threads']:,}".replace(",", " "),
        "__MEMBERS__": f"{tot['members']:,}".replace(",", " "),
        "__AUTHORS__": f"{tot['authors']:,}".replace(",", " "),
        "__ATT__": f"{tot['attachments']:,}".replace(",", " "),
        "__BOOKS__": str(meta["n_books"]),
        "__ATTHUMAN__": f["att_human"],
        "__NPDF__": str(meta["n_pdf"]),
        "__NFONT__": str(meta["n_font"]),
        "__REPLIES__": f"{meta['reply_resolved']:,}".replace(",", " "),
        "__PEAKY__": str(f["peak_year"]),
        "__PEAKM__": f"{f['peak_msgs']:,}".replace(",", " "),
        "__JOIN2007__": str(f["join2007"]),
        "__RECTHREADS__": str(f["recent_threads"]),
        "__TOPA__": f["top_author"],
        "__TOPAM__": f"{f['top_author_msgs']:,}".replace(",", " "),
        "__TOPAS__": f"{f['top_author_started']:,}".replace(",", " "),
    }
    for k, v in repl.items():
        tmpl = tmpl.replace(k, v)
    return tmpl


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", type=Path, default=DEFAULT_DUMP)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    stats = build(args.dump, args.out)
    print(f"page done: {stats}", flush=True)


# The HTML/CSS/JS template lives in a sibling module to keep this file readable.
from nagari_group_archive._template import TEMPLATE  # noqa: E402


if __name__ == "__main__":
    main()
