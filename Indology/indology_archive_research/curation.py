"""Curated case-study workflow and named network summaries."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

import pandas as pd


ALLOWED_STATUSES = {"candidate", "selected", "rejected", "needs_more_review"}
ALLOWED_TRACKS = {"", "philological_substance", "infrastructure_history"}

PHILOLOGICAL_TOPICS = {
    "Bibliographic requests",
    "Buddhism and Jainism",
    "Grammar and linguistics",
    "Manuscripts and epigraphy",
    "Texts and philology",
    "Veda and ritual",
}
INFRASTRUCTURE_TOPICS = {"Digital resources and tools"}
PHILOLOGICAL_FUNCTIONS = {"bibliographic request", "identification/help request", "philological discussion"}
INFRASTRUCTURE_FUNCTIONS = {"digital resource/tool", "technical support", "list administration"}

INFRASTRUCTURE_PATTERN = re.compile(
    r"\b(unicode|font|fonts|pdf|scan|scans|database|databases|corpus|corpora|online|website|"
    r"digital|ocr|xml|software|tool|tools|etext|e-text|list|email|archive|searchable|access)\b",
    re.I,
)
PHILOLOGICAL_PATTERN = re.compile(
    r"\b(text|texts|philolog|grammar|veda|vedic|buddh|jain|manuscript|manuscripts|epigraph|"
    r"inscription|translation|edition|reading|variant|sutra|sūtra|panini|pāṇini|bibliograph|"
    r"reference|identify|identification|meaning|interpretation)\b",
    re.I,
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


def to_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def classify_suggested_track(subject: str, topic: str, list_function: str, case_type: str) -> tuple[str, str]:
    blob = f"{subject} {topic} {list_function} {case_type}"
    if topic in INFRASTRUCTURE_TOPICS:
        return "infrastructure_history", f"topic={topic}"
    if list_function in INFRASTRUCTURE_FUNCTIONS or case_type in INFRASTRUCTURE_FUNCTIONS:
        return "infrastructure_history", f"function={list_function or case_type}"
    if INFRASTRUCTURE_PATTERN.search(blob):
        return "infrastructure_history", "keyword match"
    if topic in PHILOLOGICAL_TOPICS:
        return "philological_substance", f"topic={topic}"
    if list_function in PHILOLOGICAL_FUNCTIONS or case_type in PHILOLOGICAL_FUNCTIONS:
        return "philological_substance", f"function={list_function or case_type}"
    if PHILOLOGICAL_PATTERN.search(blob):
        return "philological_substance", "keyword match"
    return "", ""


def normalize_status(value: str) -> str:
    value = str(value or "").strip()
    return value if value in ALLOWED_STATUSES else "candidate"


def normalize_track(value: str) -> str:
    value = str(value or "").strip()
    return value if value in ALLOWED_TRACKS else ""


def build_curated_cases(processed_dir: Path) -> pd.DataFrame:
    thread_index = read_csv(processed_dir / "thread_explorer_index.csv")
    candidates = read_csv(processed_dir / "case_study_candidates.csv")
    existing = read_csv(processed_dir / "curated_case_studies.csv")
    if thread_index.empty:
        return pd.DataFrame()

    base = thread_index.merge(
        candidates[["thread_root_id", "authors"]].drop_duplicates("thread_root_id"),
        on="thread_root_id",
        how="left",
    )
    old_by_id = {
        str(row["thread_root_id"]): row
        for _, row in existing.iterrows()
        if str(row.get("thread_root_id", ""))
    }
    rows = []
    for _, row in base.iterrows():
        thread_id = str(row["thread_root_id"])
        old = old_by_id.get(thread_id, {})
        case_type = str(old.get("case_type", "") or row.get("case_type", "") or row.get("list_function", ""))
        suggested_track, suggested_track_basis = classify_suggested_track(
            str(row.get("subject", "")),
            str(row.get("primary_topic", "")),
            str(row.get("list_function", "")),
            case_type,
        )
        rows.append(
            {
                "thread_root_id": thread_id,
                "curation_status": normalize_status(str(old.get("curation_status", "candidate"))),
                "review_track": normalize_track(str(old.get("review_track", ""))),
                "suggested_track": suggested_track,
                "suggested_track_basis": suggested_track_basis,
                "case_type": case_type,
                "short_title": str(old.get("short_title", "") or row.get("subject", "")),
                "public_note": str(old.get("public_note", "")),
                "why_it_matters": str(old.get("why_it_matters", "")),
                "curator_comments": str(old.get("curator_comments", "")),
                "manual_reviewer": str(old.get("manual_reviewer", "")),
                "manual_review_date": str(old.get("manual_review_date", "")),
                "review_notes": str(old.get("review_notes", "") or row.get("evidence", "")),
            }
        )
    curated = pd.DataFrame(rows)
    curated.to_csv(processed_dir / "curated_case_studies.csv", index=False, encoding="utf-8")
    return curated


def build_case_review_queue(processed_dir: Path, curated: pd.DataFrame) -> pd.DataFrame:
    thread_index = read_csv(processed_dir / "thread_explorer_index.csv")
    if thread_index.empty or curated.empty:
        return pd.DataFrame()
    queue = thread_index.merge(curated, on="thread_root_id", how="left")
    queue["queue_rank"] = range(1, len(queue) + 1)
    queue["review_decision"] = ""
    queue["english_public_note_draft"] = ""
    queue["english_why_it_matters_draft"] = ""
    queue["manual_reviewer"] = ""
    queue["manual_review_date"] = ""
    columns = [
        "queue_rank",
        "thread_root_id",
        "curation_status",
        "review_track",
        "suggested_track",
        "suggested_track_basis",
        "case_type",
        "review_decision",
        "short_title",
        "english_public_note_draft",
        "english_why_it_matters_draft",
        "curator_comments",
        "manual_reviewer",
        "manual_review_date",
        "subject",
        "year",
        "primary_topic",
        "list_function",
        "message_count",
        "author_count",
        "reply_count",
        "case_score",
        "page_path",
        "first_url",
        "evidence",
    ]
    queue = queue[columns]
    queue.to_csv(processed_dir / "case_review_queue.csv", index=False, encoding="utf-8")
    return queue


def build_case_summary(processed_dir: Path, queue: pd.DataFrame) -> pd.DataFrame:
    if queue.empty:
        return pd.DataFrame()
    frame = queue.copy()
    frame["effective_track"] = frame["review_track"].where(frame["review_track"].ne(""), frame["suggested_track"])
    summary = (
        frame.groupby(["curation_status", "effective_track", "case_type"], dropna=False)
        .size()
        .reset_index(name="thread_count")
        .sort_values(["curation_status", "effective_track", "thread_count"], ascending=[True, True, False])
    )
    summary.to_csv(processed_dir / "curated_case_summary.csv", index=False, encoding="utf-8")
    return summary


def write_review_queue_slices(processed_dir: Path, queue: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if queue.empty:
        return {}
    frame = queue.copy()
    frame["effective_track"] = frame["review_track"].where(frame["review_track"].ne(""), frame["suggested_track"])
    slices = {
        "case_review_queue_philological.csv": frame[frame["effective_track"].eq("philological_substance")],
        "case_review_queue_infrastructure.csv": frame[frame["effective_track"].eq("infrastructure_history")],
        "case_review_queue_unassigned.csv": frame[frame["effective_track"].eq("")],
    }
    for name, sliced in slices.items():
        sliced.drop(columns=["effective_track"]).to_csv(processed_dir / name, index=False, encoding="utf-8")
    return slices


def build_first_review_shortlist(processed_dir: Path, queue: pd.DataFrame, limit: int = 25) -> pd.DataFrame:
    if queue.empty:
        return pd.DataFrame()
    frame = queue.copy()
    frame["effective_track"] = frame["review_track"].where(frame["review_track"].ne(""), frame["suggested_track"])
    for column in ["case_score", "message_count", "author_count", "reply_count", "queue_rank"]:
        frame[f"{column}_int"] = to_int_series(frame[column])
    selected: list[pd.Series] = []
    seen: set[str] = set()

    def take(label: str, subset: pd.DataFrame, count: int) -> None:
        if count <= 0 or subset.empty:
            return
        ordered = subset.sort_values(
            ["case_score_int", "author_count_int", "reply_count_int", "message_count_int"],
            ascending=False,
        )
        for _, row in ordered.iterrows():
            thread_id = str(row["thread_root_id"])
            if thread_id in seen:
                continue
            item = row.copy()
            item["review_priority_reason"] = label
            selected.append(item)
            seen.add(thread_id)
            if sum(1 for existing in selected if existing["review_priority_reason"] == label) >= count:
                break

    take("highest overall candidate score", frame, 7)
    take("philological substance track", frame[frame["effective_track"].eq("philological_substance")], 5)
    take("infrastructure history track", frame[frame["effective_track"].eq("infrastructure_history")], 5)
    take("debate or controversy case type", frame[frame["case_type"].str.contains("debate|controversy", case=False, regex=True)], 3)
    take("community memory or announcement case type", frame[frame["case_type"].str.contains("memorial|announcement", case=False, regex=True)], 3)
    take("high-participation unassigned candidate", frame[frame["effective_track"].eq("")], limit - len(selected))

    shortlist = pd.DataFrame(selected).head(limit)
    if shortlist.empty:
        return pd.DataFrame()
    keep_columns = [
        "review_priority_reason",
        "queue_rank",
        "thread_root_id",
        "curation_status",
        "effective_track",
        "suggested_track_basis",
        "case_type",
        "short_title",
        "subject",
        "year",
        "primary_topic",
        "list_function",
        "message_count",
        "author_count",
        "reply_count",
        "case_score",
        "page_path",
        "first_url",
        "evidence",
    ]
    shortlist = shortlist[keep_columns]
    shortlist.to_csv(processed_dir / "first_review_shortlist.csv", index=False, encoding="utf-8")
    return shortlist


def write_first_review_worksheet(output_dir: Path, shortlist: pd.DataFrame) -> Path:
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# INDOLOGY First Review Worksheet",
        "",
        "English-only worksheet for the balanced first-pass case-study shortlist. The prompts below are for human review; generated metadata is evidence for selection, not a final interpretation.",
        "",
        "Reviewer status options: `selected`, `rejected`, `needs_more_review`, `candidate`.",
        "Primary track options: `philological_substance`, `infrastructure_history`, or blank if neither is appropriate.",
        "",
    ]
    if shortlist.empty:
        lines.append("_No shortlist rows generated._")
    for idx, row in shortlist.reset_index(drop=True).iterrows():
        number = idx + 1
        title = str(row.get("short_title", "") or row.get("subject", ""))
        thread_page = str(row.get("page_path", ""))
        archive = str(row.get("first_url", ""))
        lines.extend(
            [
                f"## {number}. {title}",
                "",
                f"- Thread root: `{row.get('thread_root_id', '')}`",
                f"- Review priority reason: {row.get('review_priority_reason', '')}",
                f"- Suggested track: {row.get('effective_track', '') or '(unassigned)'}",
                f"- Suggested track basis: {row.get('suggested_track_basis', '') or '(none)'}",
                f"- Case type: {row.get('case_type', '')}",
                f"- Year: {row.get('year', '')}",
                f"- Topic: {row.get('primary_topic', '')}",
                f"- List function: {row.get('list_function', '')}",
                f"- Messages/authors/replies: {row.get('message_count', '')}/{row.get('author_count', '')}/{row.get('reply_count', '')}",
                f"- Local thread page: `{thread_page}`",
                f"- Public archive URL: {archive}",
                f"- Generated evidence: {row.get('evidence', '')}",
                "",
                "Reviewer fields:",
                "",
                "- Review status:",
                "- Primary track:",
                "- Short public title:",
                "- What is this thread about?",
                "- Why is it useful for the atlas?",
                "- What caveats should be visible?",
                "- Recommended public note:",
                "- Follow-up checks:",
                "",
            ]
        )
    path = reports_dir / "first_review_worksheet.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_named_reply_summary(processed_dir: Path) -> pd.DataFrame:
    replies = read_csv(processed_dir / "reply_edges.csv")
    messages = read_csv(processed_dir / "messages_clean.csv")
    if replies.empty:
        return pd.DataFrame()
    topic_map = messages[["thread_root_id", "primary_topic", "decade"]].drop_duplicates("thread_root_id") if not messages.empty else pd.DataFrame()
    frame = replies[replies["target_author"].ne("")].copy()
    frame = frame.merge(topic_map, on="thread_root_id", how="left")
    frame["decade"] = frame["decade"].where(frame["decade"].ne(""), pd.to_datetime(frame["date"], errors="coerce", utc=True).dt.year.floordiv(10).mul(10).astype("Int64").astype(str) + "s")
    grouped = (
        frame.groupby(["source_author", "target_author", "decade", "primary_topic", "confidence"], dropna=False)
        .agg(reply_count=("source_message_id", "count"), first_date=("date", "min"), last_date=("date", "max"))
        .reset_index()
    )
    grouped.insert(0, "network_type", "direct_reply")
    grouped["is_self_reply"] = grouped["source_author"].eq(grouped["target_author"])
    grouped = grouped.sort_values("reply_count", ascending=False)
    grouped.to_csv(processed_dir / "named_reply_network_summary.csv", index=False, encoding="utf-8")
    return grouped


def build_named_coparticipation_summary(processed_dir: Path) -> pd.DataFrame:
    edges = read_csv(processed_dir / "network_edges.csv")
    if edges.empty:
        return pd.DataFrame()
    rows = []
    for _, row in edges.iterrows():
        for topic in str(row.get("topics", "")).split("|"):
            rows.append(
                {
                    "network_type": "co_participation",
                    "source_author": row.get("source", ""),
                    "target_author": row.get("target", ""),
                    "topic": topic,
                    "thread_count": row.get("weight", ""),
                    "evidence": "authors appear in the same public archive threads",
                }
            )
    summary = pd.DataFrame(rows).sort_values("thread_count", key=to_int_series, ascending=False)
    summary.to_csv(processed_dir / "named_coparticipation_network_summary.csv", index=False, encoding="utf-8")
    return summary


def html_table(frame: pd.DataFrame, columns: list[str], link_columns: set[str] | None = None, limit: int = 50) -> str:
    link_columns = link_columns or set()
    if frame.empty:
        return "<p class=\"muted\">No rows.</p>"
    rows = [
        "<table class=\"data\"><thead><tr>"
        + "".join(f"<th>{esc(col)}</th>" for col in columns)
        + "</tr></thead><tbody>"
    ]
    for _, row in frame.head(limit)[columns].iterrows():
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


def write_curated_dashboard(output_dir: Path, queue: pd.DataFrame, summary: pd.DataFrame, shortlist: pd.DataFrame) -> Path:
    dashboard_dir = output_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    display = queue.copy()
    if not display.empty:
        display["thread_page"] = display["page_path"].map(lambda value: value if value else "")
        display["archive"] = display["first_url"]
        display["effective_track"] = display["review_track"].where(display["review_track"].ne(""), display["suggested_track"])
    selected = display[display["curation_status"].eq("selected")] if not display.empty else pd.DataFrame()
    needs_review = display[display["curation_status"].isin(["candidate", "needs_more_review"])] if not display.empty else pd.DataFrame()
    rejected = display[display["curation_status"].eq("rejected")] if not display.empty else pd.DataFrame()
    philological = display[display["effective_track"].eq("philological_substance")] if not display.empty else pd.DataFrame()
    infrastructure = display[display["effective_track"].eq("infrastructure_history")] if not display.empty else pd.DataFrame()
    shortlist_display = shortlist.copy()
    if not shortlist_display.empty:
        shortlist_display["thread_page"] = shortlist_display["page_path"].map(lambda value: value if value else "")
        shortlist_display["archive"] = shortlist_display["first_url"]
    columns = [
        "curation_status",
        "effective_track",
        "suggested_track_basis",
        "case_type",
        "short_title",
        "message_count",
        "author_count",
        "reply_count",
        "thread_page",
        "archive",
    ]
    shortlist_columns = [
        "review_priority_reason",
        "effective_track",
        "case_type",
        "short_title",
        "message_count",
        "author_count",
        "reply_count",
        "thread_page",
        "archive",
    ]
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Curated Cases · INDOLOGY Guided Archive Atlas</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #202124; background: #fafafa; line-height: 1.5; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 56px; }}
    h1 {{ font-size: 32px; margin-bottom: 8px; }}
    h2 {{ margin-top: 34px; border-top: 1px solid #ddd; padding-top: 22px; }}
    a {{ color: #245f73; }}
    table.data {{ width: 100%; border-collapse: collapse; background: white; font-size: 13px; margin: 12px 0 20px; }}
    table.data th, table.data td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
    table.data th {{ background: #eef3f1; text-align: left; }}
    .muted {{ color: #555; max-width: 880px; }}
  </style>
</head>
<body>
<main>
  <p><a href="index.html">Back to guided atlas</a> · <a href="search.html">Search atlas</a></p>
  <h1>Curated Case Studies</h1>
  <p class="muted">English-only review workflow for 250 automatically selected candidate threads. Rows remain candidates until a human reviewer marks them selected; public language describes metadata evidence, not scholarly rank.</p>
  <h2>Review Packets</h2>
  <p class="muted">Use the split CSV packets for staged human review. Edit `curated_case_studies.csv` as the durable source of review decisions; these packets are regenerated views.</p>
  <ul>
    <li><a href="../data/processed/case_review_queue.csv">All candidates</a></li>
    <li><a href="../data/processed/first_review_shortlist.csv">First review shortlist</a></li>
    <li><a href="../reports/first_review_worksheet.md">First review worksheet</a></li>
    <li><a href="../data/curation/first_review_notes.csv">Editable first-review notes</a></li>
    <li><a href="../data/processed/review_import_audit.csv">Review import audit</a></li>
    <li><a href="../data/processed/case_review_queue_philological.csv">Philological substance packet</a></li>
    <li><a href="../data/processed/case_review_queue_infrastructure.csv">Infrastructure history packet</a></li>
    <li><a href="../data/processed/case_review_queue_unassigned.csv">Unassigned packet</a></li>
  </ul>
  <p class="muted">Round trip: edit <code>data/curation/first_review_notes.csv</code>, run <code>python -m indology_archive_research.review_import --output-dir .</code>, then regenerate curation/search/publication/validation.</p>
  <h2>First Review Shortlist</h2>
  <p class="muted">Automatically balanced starting set for human review. It mixes high-score, philological, infrastructure, debate, community, and unassigned candidates.</p>
  {html_table(shortlist_display, shortlist_columns, {'thread_page', 'archive'}, limit=50)}
  <h2>Review Summary</h2>
  {html_table(summary, ['curation_status', 'effective_track', 'case_type', 'thread_count'], limit=100)}
  <h2>Selected Cases</h2>
  {html_table(selected, columns, {'thread_page', 'archive'}, limit=100)}
  <h2>Candidates Needing Review</h2>
  {html_table(needs_review, columns, {'thread_page', 'archive'}, limit=100)}
  <h2>Philological Substance Track</h2>
  {html_table(philological, columns, {'thread_page', 'archive'}, limit=100)}
  <h2>Infrastructure History Track</h2>
  {html_table(infrastructure, columns, {'thread_page', 'archive'}, limit=100)}
  <h2>Rejected Or Noisy Cases</h2>
  {html_table(rejected, columns, {'thread_page', 'archive'}, limit=100)}
</main>
</body>
</html>
"""
    path = dashboard_dir / "curated.html"
    path.write_text(html_doc, encoding="utf-8")
    return path


def run_curation(output_dir: Path) -> dict[str, object]:
    processed_dir = output_dir / "data" / "processed"
    curated = build_curated_cases(processed_dir)
    queue = build_case_review_queue(processed_dir, curated)
    summary = build_case_summary(processed_dir, queue)
    queue_slices = write_review_queue_slices(processed_dir, queue)
    shortlist = build_first_review_shortlist(processed_dir, queue)
    worksheet = write_first_review_worksheet(output_dir, shortlist)
    reply_summary = build_named_reply_summary(processed_dir)
    coparticipation_summary = build_named_coparticipation_summary(processed_dir)
    curated_page = write_curated_dashboard(output_dir, queue, summary, shortlist)
    return {
        "curated_cases": len(curated),
        "case_review_queue": len(queue),
        "case_summary": len(summary),
        "first_review_shortlist": len(shortlist),
        "first_review_worksheet": worksheet,
        "case_review_queue_philological": len(queue_slices.get("case_review_queue_philological.csv", [])),
        "case_review_queue_infrastructure": len(queue_slices.get("case_review_queue_infrastructure.csv", [])),
        "case_review_queue_unassigned": len(queue_slices.get("case_review_queue_unassigned.csv", [])),
        "named_reply_network_summary": len(reply_summary),
        "named_coparticipation_network_summary": len(coparticipation_summary),
        "curated_page": curated_page,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    print(run_curation(args.output_dir))


if __name__ == "__main__":
    main()
