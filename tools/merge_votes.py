"""Merge student vote exports from voting.html into a "who voted how" table.

Reads the JSON/CSV exports produced by voting.html (or a Yandex Forms responses
CSV whose cells contain pasted JSON) and writes two attributed tables:

  - votes_by_talk.csv      one row per talk: counts + the names/emails who marked
                           it heard / liked, plus their comments;
  - votes_by_respondent.csv one row per student: how many talks heard/liked.

Identity is the respondent email (voting.html requires it before export); the
optional name is shown alongside. Duplicate submissions from the same email for
the same talk are collapsed, keeping the latest by `exported_at`.

Usage:
  # a folder of per-student .json/.csv exports:
  python tools/merge_votes.py path/to/exports/

  # a Yandex Forms responses CSV with a column holding the pasted JSON:
  python tools/merge_votes.py responses.csv --json-column "JSON выгрузки"

  # explicit output dir (default: analytics_output/votes/):
  python tools/merge_votes.py exports/ --out-dir analytics_output/votes
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Fields a voting.html row carries (see generate_voting_page / rowsForExport).
ROW_FIELDS = [
    "respondent_email", "respondent_name", "visibility_mode", "exported_at",
    "source_page", "id", "year", "series", "date", "time", "session",
    "speaker", "title", "heard", "liked", "comment", "url",
]


def _truthy(v):
    return str(v).strip().lower() in {"1", "true", "yes", "да", "heard", "liked"}


def _coerce_rows(obj):
    """A single export is a list of row dicts; tolerate {'rows': [...]} too."""
    if isinstance(obj, dict):
        obj = obj.get("rows") or obj.get("votes") or []
    return [r for r in obj if isinstance(r, dict)] if isinstance(obj, list) else []


def rows_from_json_text(text, source):
    try:
        return _coerce_rows(json.loads(text))
    except json.JSONDecodeError as exc:
        print(f"  [skip] {source}: invalid JSON ({exc})", file=sys.stderr)
        return []


def load_inputs(paths, json_column):
    rows = []
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(p.glob("*.json")))
            files.extend(sorted(p.glob("*.csv")))
        else:
            files.append(p)

    for f in files:
        if not f.exists():
            print(f"  [skip] {f}: not found", file=sys.stderr)
            continue
        if f.suffix.lower() == ".json":
            rows.extend(rows_from_json_text(f.read_text(encoding="utf-8"), f.name))
        elif f.suffix.lower() == ".csv":
            with f.open(encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for rec in reader:
                    if json_column:
                        cell = rec.get(json_column, "")
                        if cell and cell.strip():
                            rows.extend(rows_from_json_text(cell, f.name))
                    elif "respondent_email" in rec or "id" in rec:
                        rows.append(rec)  # already a flat voting CSV export
    return rows


def dedupe(rows):
    """Keep the latest submission per (email, talk_id)."""
    best = {}
    for r in rows:
        email = (r.get("respondent_email") or "").strip().lower()
        tid = str(r.get("id") or "").strip()
        if not email or not tid:
            continue
        key = (email, tid)
        prev = best.get(key)
        if prev is None or str(r.get("exported_at") or "") >= str(prev.get("exported_at") or ""):
            best[key] = r
    return list(best.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="export files or a folder of them")
    ap.add_argument("--json-column", help="CSV column holding pasted JSON (Yandex Forms)")
    ap.add_argument("--out-dir", default="analytics_output/votes")
    args = ap.parse_args()

    rows = dedupe(load_inputs(args.inputs, args.json_column))
    if not rows:
        print("No vote rows found. Check the input paths / --json-column.", file=sys.stderr)
        sys.exit(1)

    who = lambda r: (r.get("respondent_name") or "").strip() or (r.get("respondent_email") or "").strip()

    talks = {}
    heard_by = defaultdict(list)
    liked_by = defaultdict(list)
    comments = defaultdict(list)
    by_resp = defaultdict(lambda: {"name": "", "email": "", "heard": 0, "liked": 0})

    for r in rows:
        tid = str(r.get("id") or "").strip()
        if not tid:
            continue
        talks.setdefault(tid, r)
        label = who(r)
        email = (r.get("respondent_email") or "").strip().lower()
        rec = by_resp[email]
        rec["email"] = email
        rec["name"] = (r.get("respondent_name") or "").strip()
        if _truthy(r.get("heard")):
            heard_by[tid].append(label)
            rec["heard"] += 1
        if _truthy(r.get("liked")):
            liked_by[tid].append(label)
            rec["liked"] += 1
        c = (r.get("comment") or "").strip()
        if c:
            comments[tid].append(f"{label}: {c}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    talk_csv = out / "votes_by_talk.csv"
    with talk_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "year", "series", "session", "speaker", "title",
                    "n_heard", "n_liked", "heard_by", "liked_by", "comments"])
        for tid, t in sorted(talks.items(), key=lambda kv: (-len(liked_by[kv[0]]), -len(heard_by[kv[0]]))):
            w.writerow([
                tid, t.get("year", ""), t.get("series", ""), t.get("session", ""),
                t.get("speaker", ""), t.get("title", ""),
                len(heard_by[tid]), len(liked_by[tid]),
                "; ".join(heard_by[tid]), "; ".join(liked_by[tid]),
                " | ".join(comments[tid]),
            ])

    resp_csv = out / "votes_by_respondent.csv"
    with resp_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["respondent_email", "respondent_name", "talks_heard", "talks_liked"])
        for email, rec in sorted(by_resp.items()):
            w.writerow([rec["email"], rec["name"], rec["heard"], rec["liked"]])

    print(f"Respondents: {len(by_resp)} | talks with votes: {len(talks)} | rows: {len(rows)}")
    print(f"  {talk_csv}")
    print(f"  {resp_csv}")
    top = sorted(talks, key=lambda t: -len(liked_by[t]))[:5]
    if any(liked_by[t] for t in top):
        print("Top liked:")
        for t in top:
            if liked_by[t]:
                print(f"  [{len(liked_by[t])}] {talks[t].get('title', t)[:60]}")


if __name__ == "__main__":
    main()
