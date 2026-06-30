"""Static thread explorer pages for INDOLOGY case-study candidates."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

import pandas as pd


CASE_TYPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bibliographic rescue", re.compile(r"\b(pdf|scan|article|copy|offprint|bibliograph|reference)\b", re.I)),
    ("identification/help request", re.compile(r"\b(help|identify|looking for|seeking|query|question|does anyone|can anyone)\b", re.I)),
    ("digital resource/tool", re.compile(r"\b(digital|unicode|font|software|database|corpus|etext|searchable|website|online|ocr|xml)\b", re.I)),
    ("philological debate", re.compile(r"\b(translation|edition|meaning|reading|variant|grammar|sandhi|sutra|sūtra|manuscript|text)\b", re.I)),
    ("debate/controversy", re.compile(r"\b(debate|controversy|bias|sexism|politics|critique|problem)\b", re.I)),
    ("memorial/community memory", re.compile(r"\b(obituary|memorial|passed away|gone|tribute|remembering)\b", re.I)),
    ("announcement", re.compile(r"\b(conference|workshop|seminar|lecture|cfp|call for papers|job|position|fellowship)\b", re.I)),
)


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return text[:80] or "thread"


def classify_case_type(subject: str, list_function: str, topic: str) -> str:
    blob = f"{subject} {list_function} {topic}"
    for label, pattern in CASE_TYPE_RULES:
        if pattern.search(blob):
            return label
    return list_function or "general discussion"


def html_table(frame: pd.DataFrame, columns: list[str], link_columns: set[str] | None = None) -> str:
    link_columns = link_columns or set()
    if frame.empty:
        return "<p class=\"muted\">No rows.</p>"
    rows = [
        "<table class=\"data\"><thead><tr>"
        + "".join(f"<th>{esc(col)}</th>" for col in columns)
        + "</tr></thead><tbody>"
    ]
    for _, row in frame[columns].iterrows():
        cells = []
        for col in columns:
            value = str(row[col])
            if col in link_columns and value:
                cells.append(f'<td><a href="{esc(value)}">open</a></td>')
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def write_thread_page(
    dashboard_dir: Path,
    page_path: str,
    candidate: pd.Series,
    messages: pd.DataFrame,
    replies: pd.DataFrame,
) -> None:
    path = dashboard_dir / page_path
    path.parent.mkdir(parents=True, exist_ok=True)
    participants = sorted(a for a in messages["normalized_author"].unique() if a)
    resolved = replies[replies["target_author"] != ""].copy()
    unresolved = replies[replies["target_author"] == ""].copy()
    confidence_order = {"exact_in_reply_to": 0, "references_chain": 1, "thread_inferred": 2, "unresolved": 3}
    resolved["confidence_order"] = resolved["confidence"].map(confidence_order).fillna(9)
    resolved = resolved.sort_values(["confidence_order", "date"])
    timeline = messages.sort_values(["date", "archive_id"])[
        ["date", "normalized_author", "clean_subject", "list_function", "primary_topic", "archive_url"]
    ].rename(
        columns={
            "normalized_author": "author",
            "clean_subject": "subject",
            "archive_url": "archive",
        }
    )
    conversation = resolved[
        ["source_author", "target_author", "confidence", "source_url", "target_url"]
    ].rename(
        columns={
            "source_author": "source",
            "target_author": "target",
            "source_url": "source",
            "target_url": "target",
        }
    )
    # Avoid duplicate column names in the displayed conversation table.
    if not resolved.empty:
        conversation = resolved[["source_author", "target_author", "confidence", "source_url", "target_url"]].rename(
            columns={
                "source_author": "source_author",
                "target_author": "target_author",
                "source_url": "source_message",
                "target_url": "target_message",
            }
        )
    unresolved_display = unresolved[["source_author", "confidence", "evidence", "source_url"]].rename(
        columns={"source_url": "source_message"}
    )
    title = str(candidate["subject"])
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} · INDOLOGY thread</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #202124; background: #fafafa; line-height: 1.5; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px 20px 56px; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; border-top: 1px solid #ddd; padding-top: 20px; }}
    a {{ color: #245f73; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 20px 0; }}
    .stat {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 12px; }}
    .stat strong {{ display: block; font-size: 20px; }}
    table.data {{ width: 100%; border-collapse: collapse; background: white; font-size: 13px; margin: 12px 0; }}
    table.data th, table.data td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
    table.data th {{ background: #eef3f1; text-align: left; }}
    .muted {{ color: #666; }}
  </style>
</head>
<body>
<main>
  <p><a href="../index.html">Back to guided atlas</a></p>
  <h1>{esc(title)}</h1>
  <p class="muted">Automatically generated candidate page. This page uses archive metadata and subject lines only; it is not a curated scholarly interpretation.</p>
  <section class="summary">
    <div class="stat"><strong>{esc(candidate['message_count'])}</strong>messages</div>
    <div class="stat"><strong>{esc(candidate['author_count'])}</strong>authors</div>
    <div class="stat"><strong>{esc(candidate['reply_count'])}</strong>resolved replies</div>
    <div class="stat"><strong>{esc(candidate['case_type'])}</strong>candidate type</div>
  </section>
  <h2>Why selected</h2>
  <p>{esc(candidate.get('evidence', ''))}</p>
  <p><strong>Topic:</strong> {esc(candidate.get('primary_topic', ''))}<br>
  <strong>List function:</strong> {esc(candidate.get('list_function', ''))}<br>
  <strong>First public archive message:</strong> <a href="{esc(candidate.get('first_url', ''))}">open</a></p>
  <h2>Participants</h2>
  <p>{esc(' | '.join(participants))}</p>
  <h2>Message timeline</h2>
  {html_table(timeline, ['date', 'author', 'subject', 'list_function', 'primary_topic', 'archive'], {'archive'})}
  <h2>Conversation map</h2>
  <p class="muted">Exact header matches and references-chain rows are strongest. Thread-inferred rows are lower-confidence metadata inference.</p>
  {html_table(conversation, ['source_author', 'target_author', 'confidence', 'source_message', 'target_message'], {'source_message', 'target_message'})}
  <h2>Unresolved reply-like messages</h2>
  {html_table(unresolved_display, ['source_author', 'confidence', 'evidence', 'source_message'], {'source_message'})}
</main>
</body>
</html>
"""
    path.write_text(page, encoding="utf-8")


def seed_curated_cases(candidates: pd.DataFrame, existing: pd.DataFrame | None = None) -> pd.DataFrame:
    existing = existing if existing is not None else pd.DataFrame()
    old_by_id = {
        str(row["thread_root_id"]): row
        for _, row in existing.iterrows()
        if str(row.get("thread_root_id", ""))
    }
    rows = []
    for _, row in candidates.iterrows():
        old = old_by_id.get(str(row["thread_root_id"]), {})
        case_type = classify_case_type(row["subject"], row["dominant_list_function"], row["primary_topic"])
        rows.append(
            {
                "thread_root_id": row["thread_root_id"],
                "curation_status": old.get("curation_status", "candidate"),
                "review_track": old.get("review_track", ""),
                "suggested_track": old.get("suggested_track", ""),
                "case_type": old.get("case_type", case_type),
                "short_title": old.get("short_title", row["subject"]),
                "public_note": old.get("public_note", ""),
                "why_it_matters": old.get("why_it_matters", ""),
                "curator_comments": old.get("curator_comments", ""),
                "review_notes": old.get("review_notes", row.get("evidence", "")),
            }
        )
    return pd.DataFrame(rows)


def run_thread_explorer(output_dir: Path, limit: int = 250) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    dashboard_dir = output_dir / "dashboard"
    threads_dir = dashboard_dir / "threads"
    messages = read_csv(processed_dir / "messages_clean.csv")
    replies = read_csv(processed_dir / "reply_edges.csv")
    candidates = read_csv(processed_dir / "case_study_candidates.csv").head(limit).copy()
    if messages.empty or candidates.empty:
        raise FileNotFoundError("messages_clean.csv and case_study_candidates.csv are required")

    if threads_dir.exists():
        shutil.rmtree(threads_dir)
    threads_dir.mkdir(parents=True, exist_ok=True)

    existing_curated = read_csv(processed_dir / "curated_case_studies.csv")
    curated = seed_curated_cases(candidates, existing_curated)
    index_rows = []
    for rank, (_, row) in enumerate(candidates.iterrows(), start=1):
        thread_id = row["thread_root_id"]
        thread_messages = messages[messages["thread_root_id"] == thread_id].copy()
        if thread_messages.empty:
            continue
        thread_replies = replies[replies["thread_root_id"] == thread_id].copy()
        case_type = curated[curated["thread_root_id"] == thread_id]["case_type"].iloc[0]
        page_path = f"threads/{rank:03d}-{slugify(thread_id + '-' + row['subject'])}.html"
        page_row = {
            **row.to_dict(),
            "case_type": case_type,
            "list_function": row.get("dominant_list_function", ""),
            "page_path": page_path,
        }
        write_thread_page(dashboard_dir, page_path, pd.Series(page_row), thread_messages, thread_replies)
        first_year = pd.to_datetime(thread_messages["date"], errors="coerce", utc=True).dt.year.dropna()
        index_rows.append(
            {
                "thread_root_id": thread_id,
                "subject": row["subject"],
                "year": int(first_year.iloc[0]) if not first_year.empty else "",
                "primary_topic": row["primary_topic"],
                "list_function": row["dominant_list_function"],
                "message_count": row["message_count"],
                "author_count": row["author_count"],
                "reply_count": row["reply_count"],
                "case_score": row["score"],
                "page_path": page_path,
                "first_url": row["first_url"],
                "evidence": row["evidence"],
            }
        )

    index = pd.DataFrame(index_rows)
    index.to_csv(processed_dir / "thread_explorer_index.csv", index=False, encoding="utf-8")
    curated.to_csv(processed_dir / "curated_case_studies.csv", index=False, encoding="utf-8")
    return {"thread_explorer_index": index, "curated_case_studies": curated}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--limit", type=int, default=250)
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    run_thread_explorer(args.output_dir, args.limit)


if __name__ == "__main__":
    main()
