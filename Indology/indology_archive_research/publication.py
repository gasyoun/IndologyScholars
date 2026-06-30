"""Generate report, dashboard, and dataset manifest for the INDOLOGY appendix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


DATASET_DESCRIPTIONS = {
    "atlas_timeline.csv": "Year-by-year atlas summary for volume, threads, authors, dominant topics, and list functions.",
    "atlas_topic_profiles.csv": "Topic profiles with time span, thread counts, author counts, and dominant list functions.",
    "atlas_list_functions.csv": "Readable categories for what work the mailing list performed by decade.",
    "atlas_people_summary.csv": "Conservative person-level participation summary using normalized author labels.",
    "atlas_reply_summary.csv": "Directed reply reconstruction counts by confidence level.",
    "case_study_candidates.csv": "Data-driven thread candidates for close reading and human curation.",
    "thread_explorer_index.csv": "Index of generated static thread explorer pages for case-study candidates.",
    "curated_case_studies.csv": "Review-ready curation table seeded from generated case-study candidates.",
    "first_review_notes.csv": "Human-editable review intake for importing first-review notes.",
    "case_review_queue.csv": "English-only review queue for all generated case-study candidates.",
    "first_review_shortlist.csv": "Balanced first-pass shortlist for starting human case-study review.",
    "case_review_queue_philological.csv": "Review packet for case-study candidates suggested as philological substance.",
    "case_review_queue_infrastructure.csv": "Review packet for case-study candidates suggested as infrastructure history.",
    "case_review_queue_unassigned.csv": "Review packet for case-study candidates without an automatic track suggestion.",
    "curated_case_summary.csv": "Aggregate counts by curation status, track, and case type.",
    "review_import_audit.csv": "Audit trail for importing human review notes into curated case metadata.",
    "human_review_index.csv": "Unified reviewer-facing queue for author, case-study, count, noisy-subject, and reply-network checks.",
    "human_review_summary.json": "Machine-readable summary of the unified human review index.",
    "interpretive_guardrails.csv": "Responsible-claims guardrails for interpreting reply, co-participation, volume, archive, and author-normalization outputs.",
    "named_reply_network_summary.csv": "Named direct-reply network summary by decade, topic, and confidence.",
    "named_coparticipation_network_summary.csv": "Named co-participation network summary by topic.",
    "search_threads.json": "Static search index for generated thread pages and case-study candidate status.",
    "search_authors.json": "Static search index for conservative author summaries.",
    "search_topics.json": "Static search index for topic profiles.",
    "search_messages_sample.json": "Compact metadata-only message sample for static search.",
    "messages_raw.csv": "Harvested message metadata aligned from Pipermail HTML indexes and monthly mbox headers.",
    "messages.csv": "Analyzed message metadata with cleaned subjects, topic labels, thread length, and author display strings.",
    "messages_clean.csv": "Message metadata with conservative normalized author labels and author audit fields.",
    "author_aliases.csv": "Public author-normalization audit table, one row per raw author string.",
    "authors_needing_review.csv": "Ambiguous author strings retained without identity merging.",
    "excluded_author_artifacts.csv": "Mail-client/list artifacts excluded from person-level analysis.",
    "threads.csv": "Reconstructed thread-level metadata.",
    "network_edges.csv": "Undirected co-participation edges: two authors appear in the same thread.",
    "reply_edges.csv": "Directed reply edges resolved from In-Reply-To, References, or conservative thread inference.",
    "reply_network_edges.csv": "Aggregated directed reply edge weights by source, target, and confidence.",
    "count_mismatch_audit.csv": "Documentation of months where archive index and mbox counts differ.",
    "skipped_mbox_rows.csv": "Extra mbox rows skipped during subject-based archive alignment.",
    "topic_year_counts.csv": "Topic message counts by year.",
    "topic_decade_counts.csv": "Topic message counts by decade.",
    "monthly_counts.csv": "Message volume by archive month.",
    "yearly_counts.csv": "Message volume by year.",
}


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()


def markdown_table(frame: pd.DataFrame, limit: int = 12) -> str:
    if frame.empty:
        return "_No rows._"
    safe = frame.head(limit).copy().fillna("").astype(str)
    columns = list(safe.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in safe.iterrows():
        lines.append("| " + " | ".join(row[col].replace("|", "\\|").replace("\n", " ") for col in columns) + " |")
    return "\n".join(lines)


def to_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def build_manifest(output_dir: Path) -> pd.DataFrame:
    processed_dir = output_dir / "data" / "processed"
    curation_dir = output_dir / "data" / "curation"
    rows = []
    for path in sorted([*processed_dir.glob("*.csv"), *processed_dir.glob("*.json"), *curation_dir.glob("*.csv")]):
        if path.name in {"dataset_manifest.csv", "dataset_manifest.json"}:
            continue
        try:
            if path.suffix == ".json":
                row_count = len(json.loads(path.read_text(encoding="utf-8")))
            else:
                row_count = sum(1 for _ in path.open("r", encoding="utf-8", errors="replace")) - 1
        except OSError:
            row_count = ""
        except json.JSONDecodeError:
            row_count = ""
        rows.append(
            {
                "file": path.name,
                "relative_path": str(path.relative_to(output_dir)).replace("\\", "/"),
                "rows": row_count,
                "bytes": path.stat().st_size,
                "description": DATASET_DESCRIPTIONS.get(path.name, "Generated atlas output."),
            }
        )
    manifest = pd.DataFrame(rows)
    manifest.to_csv(processed_dir / "dataset_manifest.csv", index=False, encoding="utf-8")
    (processed_dir / "dataset_manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def write_research_report(output_dir: Path) -> Path:
    processed_dir = output_dir / "data" / "processed"
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    messages = read_csv_if_exists(processed_dir / "messages_clean.csv")
    months = read_csv_if_exists(processed_dir / "months.csv")
    threads = read_csv_if_exists(processed_dir / "threads.csv")
    aliases = read_csv_if_exists(processed_dir / "author_aliases.csv")
    needs_review = read_csv_if_exists(processed_dir / "authors_needing_review.csv")
    replies = read_csv_if_exists(processed_dir / "reply_edges.csv")
    reply_network = read_csv_if_exists(processed_dir / "reply_network_edges.csv")
    mismatches = read_csv_if_exists(processed_dir / "count_mismatch_audit.csv")
    topic_year = read_csv_if_exists(processed_dir / "topic_year_counts.csv")
    atlas_timeline = read_csv_if_exists(processed_dir / "atlas_timeline.csv")
    topic_profiles = read_csv_if_exists(processed_dir / "atlas_topic_profiles.csv")
    list_functions = read_csv_if_exists(processed_dir / "atlas_list_functions.csv")
    people = read_csv_if_exists(processed_dir / "atlas_people_summary.csv")
    reply_summary = read_csv_if_exists(processed_dir / "atlas_reply_summary.csv")
    cases = read_csv_if_exists(processed_dir / "case_study_candidates.csv")
    thread_index = read_csv_if_exists(processed_dir / "thread_explorer_index.csv")
    curated_cases = read_csv_if_exists(processed_dir / "curated_case_studies.csv")
    review_queue = read_csv_if_exists(processed_dir / "case_review_queue.csv")
    first_review_shortlist = read_csv_if_exists(processed_dir / "first_review_shortlist.csv")
    curated_summary = read_csv_if_exists(processed_dir / "curated_case_summary.csv")
    review_import_audit = read_csv_if_exists(processed_dir / "review_import_audit.csv")
    human_review_index = read_csv_if_exists(processed_dir / "human_review_index.csv")
    interpretive_guardrails = read_csv_if_exists(processed_dir / "interpretive_guardrails.csv")
    review_philological = read_csv_if_exists(processed_dir / "case_review_queue_philological.csv")
    review_infrastructure = read_csv_if_exists(processed_dir / "case_review_queue_infrastructure.csv")
    review_unassigned = read_csv_if_exists(processed_dir / "case_review_queue_unassigned.csv")
    named_replies = read_csv_if_exists(processed_dir / "named_reply_network_summary.csv")
    named_coparticipation = read_csv_if_exists(processed_dir / "named_coparticipation_network_summary.csv")
    interauthor_replies = named_replies[named_replies["is_self_reply"].astype(str).ne("True")] if "is_self_reply" in named_replies.columns else named_replies

    resolved_replies = replies[replies["target_author"] != ""] if not replies.empty else pd.DataFrame()
    top_topics = topic_profiles[["topic", "message_count", "thread_count", "author_count", "top_list_function"]].head(10) if not topic_profiles.empty else pd.DataFrame()
    top_functions = (
        list_functions.groupby("list_function")["message_count"].apply(lambda s: pd.to_numeric(s, errors="coerce").sum()).reset_index().sort_values("message_count", ascending=False).head(10)
        if not list_functions.empty
        else pd.DataFrame()
    )
    lines = [
        "# INDOLOGY-L as Scholarly Infrastructure, 1990-2026",
        "",
        "This report reads the INDOLOGY mailing-list archive as a long-running scholarly infrastructure: a reference desk, announcement board, technical support forum, bibliographic exchange, and conversation network. The summaries below are generated from public archive metadata and should be read as guides to further close reading, not as final social rankings.",
        "",
        "## Coverage",
        "",
        f"- Months: {len(months):,}",
        f"- Messages: {len(messages):,}",
        f"- Threads: {len(threads):,}",
        f"- Raw author strings: {len(aliases):,}",
        f"- Author strings needing review: {len(needs_review):,}",
        f"- Directed reply rows: {len(replies):,}",
        f"- Resolved directed replies: {len(resolved_replies):,}",
        f"- Aggregated directed reply edges: {len(reply_network):,}",
        "",
        "## Method Notes",
        "",
        "- Author normalization is conservative: exact display-name groups are confirmed, email-like and short labels are retained for review.",
        "- `network_edges.csv` is an undirected co-participation network, not a reply network.",
        "- `reply_edges.csv` is the stricter directed network and records confidence for each edge.",
        "- `atlas_list_functions.csv` assigns readable list-function categories from subject-line patterns; uncategorized messages fall back to `general discussion`.",
        "- `case_study_candidates.csv` ranks threads for human review by thread length, author count, reply density, topic variety, and request/resolution/debate language.",
        "- `thread_explorer_index.csv` links selected candidates to local static thread pages. These pages use metadata and subject lines only.",
        "- `curated_case_studies.csv` is seeded with `candidate` status for manual review; generated candidates are not a curated canon.",
        "- `case_review_queue.csv` supports English-only review across two tracks: philological substance and infrastructure history.",
        "- Named network summaries describe public reply and co-participation evidence, not influence, prestige, or importance.",
        "- `human_review_index.csv` combines review needs across author normalization, case studies, parse quirks, noisy subjects, and reply evidence.",
        "- `interpretive_guardrails.csv` and `reports/interpretive_guardrails.md` state which public claims are supported and which overclaims should be avoided.",
        "- Count mismatches are documented in `count_mismatch_audit.csv`; extra mbox rows are preserved in `skipped_mbox_rows.csv`.",
        "",
        "## What Changed Over Time?",
        "",
    ]
    if not atlas_timeline.empty:
        decade_summary = atlas_timeline.groupby("decade").agg({"message_count": lambda s: pd.to_numeric(s, errors="coerce").sum(), "thread_count": lambda s: pd.to_numeric(s, errors="coerce").sum(), "author_count": lambda s: pd.to_numeric(s, errors="coerce").max()}).reset_index()
        lines.append(markdown_table(decade_summary.rename(columns={"message_count": "messages", "thread_count": "threads", "author_count": "max_yearly_authors"}), 10))
    else:
        lines.append("_No timeline atlas table available._")

    lines.extend(
        [
            "",
            "## What Was Discussed?",
            "",
            markdown_table(top_topics.rename(columns={"topic": "topic", "message_count": "messages", "thread_count": "threads", "author_count": "authors"}), 10),
            "",
            "## What Work Did The List Do?",
            "",
            markdown_table(top_functions.rename(columns={"list_function": "list_function", "message_count": "messages"}), 10),
            "",
            "## Who Participated?",
            "",
            markdown_table(people[["normalized_author", "message_count", "thread_count", "first_year", "last_year", "top_list_function", "author_status"]].head(15) if not people.empty else pd.DataFrame(), 15),
            "",
            "## Who Replied To Whom?",
            "",
            markdown_table(reply_summary, 10),
            "",
            "## Threads Worth Reading",
            "",
            "The following are automatically selected candidates for close reading, not a curated canon.",
            "",
            markdown_table(thread_index[["case_score", "subject", "primary_topic", "list_function", "message_count", "author_count", "reply_count", "page_path"]].head(15) if not thread_index.empty else cases[["score", "subject", "primary_topic", "dominant_list_function", "message_count", "author_count", "reply_count", "first_url"]].head(15) if not cases.empty else pd.DataFrame(), 15),
            "",
            "## Curated Case-Study Workflow",
            "",
            "Case-study curation is English-only. Rows remain `candidate` until a human reviewer changes the status to `selected`, `rejected`, or `needs_more_review`.",
            "",
            markdown_table(curated_summary, 15),
            "",
            f"- Review queue rows: {len(review_queue):,}",
            f"- First review shortlist rows: {len(first_review_shortlist):,}",
            f"- Philological review packet rows: {len(review_philological):,}",
            f"- Infrastructure review packet rows: {len(review_infrastructure):,}",
            f"- Unassigned review packet rows: {len(review_unassigned):,}",
            f"- Review import audit rows: {len(review_import_audit):,}",
            f"- Unified human review index rows: {len(human_review_index):,}",
            f"- Interpretive guardrail rows: {len(interpretive_guardrails):,}",
            "",
            markdown_table(first_review_shortlist[["review_priority_reason", "short_title", "effective_track", "case_type", "message_count", "author_count", "reply_count", "page_path"]].head(25) if not first_review_shortlist.empty else pd.DataFrame(), 25),
            "",
            "## How To Read Thread Pages",
            "",
            "- Thread pages show chronology, participants, public archive links, and a compact directed-reply map.",
            "- Conversation-map rows keep reply confidence visible: exact header matches are stronger than thread-inferred links.",
            "- Unresolved reply-like messages are separated rather than forced into the graph.",
            "- `curated_case_studies.csv` is the place to add human notes before presenting a thread as an interpreted example.",
            "- `case_review_queue.csv` separates generated evidence from human public notes.",
            "",
            "## Named Network Summaries",
            "",
            "The named network tables are public-archive metadata summaries. `direct_reply` rows come from reply evidence; `co_participation` rows mean two authors appear in the same thread. Self-reply rows are flagged and omitted from the sample table below.",
            "",
            markdown_table(interauthor_replies[["network_type", "source_author", "target_author", "decade", "primary_topic", "confidence", "reply_count", "is_self_reply"]].head(15) if not interauthor_replies.empty else pd.DataFrame(), 15),
            "",
            markdown_table(named_coparticipation[["network_type", "source_author", "target_author", "topic", "thread_count"]].head(15) if not named_coparticipation.empty else pd.DataFrame(), 15),
            "",
            "## Archive Caveats",
            "",
            f"- Count-mismatch months documented: {len(mismatches):,}",
            "- Early archive metadata contains empty subjects and legacy email/address strings.",
            "- Direct reply reconstruction is incomplete where headers are missing or reference messages fall outside the harvested archive.",
            "",
            "## Ethical Notes",
            "",
            "- Names and email-like strings are taken from a public scholarly mailing-list archive.",
            "- The normalization table is an audit instrument, not a biographical authority file.",
            "- Ambiguous identities remain reviewable instead of silently merged.",
            "- Data reuse files (`data_dictionary.md`, `datapackage.json`, and `CITATION.cff`) describe generated metadata separately from the source archive.",
            "",
        ]
    )
    path = reports_dir / "research_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_dashboard(output_dir: Path) -> Path:
    processed_dir = output_dir / "data" / "processed"
    dashboard_dir = output_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    messages = read_csv_if_exists(processed_dir / "messages_clean.csv")
    threads = read_csv_if_exists(processed_dir / "threads.csv")
    replies = read_csv_if_exists(processed_dir / "reply_edges.csv")
    aliases = read_csv_if_exists(processed_dir / "author_aliases.csv")
    timeline = read_csv_if_exists(processed_dir / "atlas_timeline.csv")
    topic_profiles = read_csv_if_exists(processed_dir / "atlas_topic_profiles.csv")
    list_functions = read_csv_if_exists(processed_dir / "atlas_list_functions.csv")
    people = read_csv_if_exists(processed_dir / "atlas_people_summary.csv")
    reply_summary = read_csv_if_exists(processed_dir / "atlas_reply_summary.csv")
    cases = read_csv_if_exists(processed_dir / "case_study_candidates.csv")
    thread_index = read_csv_if_exists(processed_dir / "thread_explorer_index.csv")
    curated_cases = read_csv_if_exists(processed_dir / "curated_case_studies.csv")
    review_queue = read_csv_if_exists(processed_dir / "case_review_queue.csv")
    first_review_shortlist = read_csv_if_exists(processed_dir / "first_review_shortlist.csv")
    curated_summary = read_csv_if_exists(processed_dir / "curated_case_summary.csv")
    review_import_audit = read_csv_if_exists(processed_dir / "review_import_audit.csv")
    human_review_index = read_csv_if_exists(processed_dir / "human_review_index.csv")
    interpretive_guardrails = read_csv_if_exists(processed_dir / "interpretive_guardrails.csv")
    review_philological = read_csv_if_exists(processed_dir / "case_review_queue_philological.csv")
    review_infrastructure = read_csv_if_exists(processed_dir / "case_review_queue_infrastructure.csv")
    review_unassigned = read_csv_if_exists(processed_dir / "case_review_queue_unassigned.csv")
    named_replies = read_csv_if_exists(processed_dir / "named_reply_network_summary.csv")
    named_coparticipation = read_csv_if_exists(processed_dir / "named_coparticipation_network_summary.csv")
    interauthor_replies = named_replies[named_replies["is_self_reply"].astype(str).ne("True")] if "is_self_reply" in named_replies.columns else named_replies
    figures = [
        "monthly_message_volume.png",
        "yearly_message_volume.png",
        "topic_stream.png",
        "topic_decade_heatmap.png",
        "thread_length_distribution.png",
        "thread_coparticipation_network.png",
    ]
    top_topics_html = topic_profiles[["topic", "message_count", "thread_count", "author_count", "top_list_function"]].head(12).to_html(index=False, classes="data") if not topic_profiles.empty else ""
    top_functions = (
        list_functions.groupby("list_function")["message_count"].apply(lambda s: pd.to_numeric(s, errors="coerce").sum()).reset_index().sort_values("message_count", ascending=False)
        if not list_functions.empty
        else pd.DataFrame()
    )
    functions_html = top_functions.head(12).to_html(index=False, classes="data") if not top_functions.empty else ""
    people_html = people[["normalized_author", "message_count", "thread_count", "first_year", "last_year", "top_list_function", "author_status"]].head(20).to_html(index=False, classes="data") if not people.empty else ""
    replies_html = reply_summary.to_html(index=False, classes="data") if not reply_summary.empty else ""
    curated_summary_html = curated_summary.to_html(index=False, classes="data") if not curated_summary.empty else ""
    named_replies_html = interauthor_replies[["network_type", "source_author", "target_author", "decade", "primary_topic", "confidence", "reply_count", "is_self_reply"]].head(20).to_html(index=False, classes="data") if not interauthor_replies.empty else ""
    named_coparticipation_html = named_coparticipation[["network_type", "source_author", "target_author", "topic", "thread_count"]].head(20).to_html(index=False, classes="data") if not named_coparticipation.empty else ""
    case_display = thread_index.copy()
    if not case_display.empty:
        case_display["thread_page"] = case_display["page_path"].map(lambda value: f'<a href="{value}">open</a>')
        cases_html = case_display[["case_score", "subject", "primary_topic", "list_function", "message_count", "author_count", "reply_count", "thread_page"]].head(25).to_html(index=False, classes="data", escape=False)
    else:
        cases_html = cases[["score", "subject", "primary_topic", "dominant_list_function", "message_count", "author_count", "reply_count", "first_url"]].head(25).to_html(index=False, classes="data", render_links=True) if not cases.empty else ""
    explorer_sections = ""
    if not thread_index.empty:
        def section_table(title: str, frame: pd.DataFrame) -> str:
            if frame.empty:
                return ""
            local = frame.copy()
            local["thread_page"] = local["page_path"].map(lambda value: f'<a href="{value}">open</a>')
            return f"<h3>{title}</h3>" + local[["subject", "primary_topic", "list_function", "message_count", "author_count", "reply_count", "thread_page"]].head(12).to_html(index=False, classes="data", escape=False)

        explorer_sections = "".join(
            [
                section_table("Top long threads", thread_index.sort_values("message_count", key=lambda s: pd.to_numeric(s, errors="coerce"), ascending=False)),
                section_table("Request/help threads", thread_index[thread_index["list_function"].str.contains("request|help|bibliographic", case=False, regex=True)]),
                section_table("Debate/controversy threads", thread_index[thread_index["list_function"].str.contains("debate|controversy", case=False, regex=True)]),
                section_table("Digital-resource threads", thread_index[thread_index["list_function"].str.contains("digital|technical", case=False, regex=True)]),
                section_table("Memorial threads", thread_index[thread_index["list_function"].str.contains("memorial|obituary", case=False, regex=True)]),
                section_table("Philological-discussion threads", thread_index[thread_index["list_function"].str.contains("philological", case=False, regex=True)]),
            ]
        )
    decade_html = ""
    if not timeline.empty:
        decade_summary = timeline.groupby("decade").agg({"message_count": lambda s: pd.to_numeric(s, errors="coerce").sum(), "thread_count": lambda s: pd.to_numeric(s, errors="coerce").sum(), "author_count": lambda s: pd.to_numeric(s, errors="coerce").max()}).reset_index()
        decade_summary = decade_summary.rename(columns={"message_count": "messages", "thread_count": "threads", "author_count": "max_yearly_authors"})
        decade_html = decade_summary.to_html(index=False, classes="data")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>INDOLOGY Guided Archive Atlas</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #202124; background: #fafafa; line-height: 1.5; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ font-size: 34px; margin: 0 0 8px; }}
    h2 {{ margin-top: 38px; border-top: 1px solid #ddd; padding-top: 24px; }}
    h3 {{ margin-top: 24px; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 24px 0; }}
    .stat {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }}
    .stat strong {{ display: block; font-size: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }}
    img {{ width: 100%; background: white; border: 1px solid #ddd; border-radius: 8px; }}
    a {{ color: #245f73; }}
    ul {{ line-height: 1.6; }}
    table.data {{ width: 100%; border-collapse: collapse; margin: 12px 0 18px; background: white; font-size: 13px; }}
    table.data th, table.data td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
    table.data th {{ background: #eef3f1; text-align: left; }}
    .note {{ color: #555; max-width: 860px; }}
  </style>
</head>
<body>
<main>
  <h1>INDOLOGY-L as Scholarly Infrastructure, 1990-2026</h1>
  <p class="note">A guided, metadata-first atlas of the INDOLOGY mailing-list archive. These summaries are intended to help indologists find patterns and candidate threads for close reading, not to rank people or replace scholarly interpretation.</p>
  <section class="stats">
    <div class="stat"><strong>{len(messages):,}</strong>messages</div>
    <div class="stat"><strong>{len(threads):,}</strong>threads</div>
    <div class="stat"><strong>{len(aliases):,}</strong>raw author strings</div>
    <div class="stat"><strong>{len(replies):,}</strong>directed reply rows</div>
  </section>
  <p class="note"><strong><a href="search.html">Open static search and browse indexes</a></strong> for subjects, authors, topics, years, list functions, messages, and generated thread pages. <strong><a href="curated.html">Open curated case-study workflow</a></strong> for English-only review queues and track filters.</p>
  <h2>What changed over time?</h2>
  <p class="note">Volume, threads, and yearly author counts show when the list was quiet, when it became a regular scholarly exchange, and when online announcements and post-pandemic patterns intensified.</p>
  <div class="grid">
    <a href="../figures/yearly_message_volume.png"><img src="../figures/yearly_message_volume.png" alt="Yearly message volume"></a>
    <a href="../figures/monthly_message_volume.png"><img src="../figures/monthly_message_volume.png" alt="Monthly message volume"></a>
  </div>
  {decade_html}

  <h2>What was discussed?</h2>
  <p class="note">Topics are subject-line categories, useful as a map of discussion zones rather than as final intellectual taxonomy.</p>
  <div class="grid">
    <a href="../figures/topic_stream.png"><img src="../figures/topic_stream.png" alt="Topic mix over time"></a>
    <a href="../figures/topic_decade_heatmap.png"><img src="../figures/topic_decade_heatmap.png" alt="Topic decade heatmap"></a>
  </div>
  {top_topics_html}

  <h2>What work did the list do?</h2>
  <p class="note">List-function categories translate subjects into familiar scholarly practices: requests, announcements, technical help, debate, and philological exchange.</p>
  {functions_html}

  <h2>Who participated?</h2>
  <p class="note">People summaries use conservative normalized author labels. Ambiguous email-like strings remain reviewable in the public author-normalization table.</p>
  {people_html}

  <h2>Who replied to whom?</h2>
  <p class="note">The directed reply layer is stricter than co-participation. Exact header matches are strongest; thread-inferred edges are useful but should be treated as lower-confidence.</p>
  {replies_html}
  <p><a href="../data/processed/reply_edges.csv">Download directed reply edges</a> · <a href="../data/processed/network_edges.csv">Download co-participation edges</a></p>

  <h2>Threads worth reading</h2>
  <p class="note">These are automatically selected candidates for human review, based on thread size, number of participants, reply density, topic variety, and request/resolution/debate language.</p>
  {cases_html}

  <h2>Case Study Explorer</h2>
  <p class="note">Each linked page shows chronology, participants, reply evidence, unresolved reply-like messages, and public Pipermail links. All pages remain candidate pages until manually curated.</p>
  {explorer_sections}

  <h2>Curated Case-Study Workflow</h2>
  <p class="note">All 250 candidates remain available for review. Suggested tracks distinguish philological substance from infrastructure history, while human review fields stay empty until curated.</p>
  {curated_summary_html}
  <p><a href="curated.html">Open curated workflow page</a> · <a href="../data/processed/first_review_shortlist.csv">First review shortlist ({len(first_review_shortlist):,})</a> · <a href="../data/processed/case_review_queue.csv">All candidates</a> · <a href="../data/processed/case_review_queue_philological.csv">Philological packet ({len(review_philological):,})</a> · <a href="../data/processed/case_review_queue_infrastructure.csv">Infrastructure packet ({len(review_infrastructure):,})</a> · <a href="../data/processed/case_review_queue_unassigned.csv">Unassigned packet ({len(review_unassigned):,})</a></p>
  <p><a href="../reports/first_review_worksheet.md">Open first-review worksheet</a></p>
  <p><a href="../data/curation/first_review_notes.csv">Editable review notes intake</a> · <a href="../data/processed/review_import_audit.csv">Review import audit ({len(review_import_audit):,})</a></p>
  <p><a href="../data/processed/human_review_index.csv">Unified human review index ({len(human_review_index):,})</a> · <a href="../data/processed/human_review_summary.json">Human review summary</a></p>

  <h2>Named Network Summaries</h2>
  <p class="note">Named network tables describe visible public archive evidence. Direct-reply summaries and co-participation summaries are kept separate; self-reply rows are flagged and omitted from this sample table.</p>
  <h3>Direct Reply Evidence</h3>
  {named_replies_html}
  <h3>Co-Participation Evidence</h3>
  {named_coparticipation_html}

  <h2>Reports And Data</h2>
  <ul>
    <li><a href="../data_dictionary.md">Data dictionary</a></li>
    <li><a href="../datapackage.json">Datapackage metadata</a></li>
    <li><a href="../CITATION.cff">Citation metadata</a></li>
    <li><a href="../reports/research_report.md">Research report</a></li>
    <li><a href="../reports/validation.md">Validation report</a></li>
    <li><a href="../reports/interpretive_guardrails.md">Interpretive guardrails</a></li>
    <li><a href="../reports/first_review_worksheet.md">First-review worksheet</a></li>
    <li><a href="../data/processed/dataset_manifest.csv">Dataset manifest</a></li>
    <li><a href="../data/processed/messages_clean.csv">Cleaned messages</a></li>
    <li><a href="../data/processed/author_aliases.csv">Author normalization table</a></li>
    <li><a href="../data/processed/reply_edges.csv">Directed reply edges</a></li>
    <li><a href="../data/processed/case_study_candidates.csv">Case-study candidates</a></li>
    <li><a href="../data/processed/thread_explorer_index.csv">Thread explorer index</a></li>
    <li><a href="../data/processed/curated_case_studies.csv">Curated case-study review table</a></li>
    <li><a href="../data/processed/case_review_queue.csv">Case review queue</a></li>
    <li><a href="../data/processed/first_review_shortlist.csv">First review shortlist</a></li>
    <li><a href="../data/processed/case_review_queue_philological.csv">Philological review packet</a></li>
    <li><a href="../data/processed/case_review_queue_infrastructure.csv">Infrastructure review packet</a></li>
    <li><a href="../data/processed/case_review_queue_unassigned.csv">Unassigned review packet</a></li>
    <li><a href="../data/processed/curated_case_summary.csv">Curated case summary</a></li>
    <li><a href="../data/curation/first_review_notes.csv">Editable first-review notes</a></li>
    <li><a href="../data/processed/review_import_audit.csv">Review import audit</a></li>
    <li><a href="../data/processed/human_review_index.csv">Unified human review index</a></li>
    <li><a href="../data/processed/human_review_summary.json">Human review summary</a></li>
    <li><a href="../data/processed/interpretive_guardrails.csv">Interpretive guardrails table</a></li>
    <li><a href="../data/processed/named_reply_network_summary.csv">Named direct-reply summary</a></li>
    <li><a href="../data/processed/named_coparticipation_network_summary.csv">Named co-participation summary</a></li>
    <li><a href="../data/processed/search_threads.json">Thread search index</a></li>
    <li><a href="../data/processed/search_authors.json">Author search index</a></li>
    <li><a href="../data/processed/search_topics.json">Topic search index</a></li>
    <li><a href="../data/processed/search_messages_sample.json">Message sample search index</a></li>
  </ul>
  <h2>Figures</h2>
  <div class="grid">
    {''.join(f'<a href="../figures/{name}"><img src="../figures/{name}" alt="{name}"></a>' for name in figures)}
  </div>
</main>
</body>
</html>
"""
    path = dashboard_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def run_publication(output_dir: Path) -> dict[str, Path]:
    manifest = build_manifest(output_dir)
    report_path = write_research_report(output_dir)
    dashboard_path = write_dashboard(output_dir)
    return {"manifest_rows": len(manifest), "report": report_path, "dashboard": dashboard_path}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    outputs = run_publication(args.output_dir)
    print(outputs)


if __name__ == "__main__":
    main()
