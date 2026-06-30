"""Validation report for harvested INDOLOGY archive metadata."""

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


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a small Markdown table without optional pandas dependencies."""

    if frame.empty:
        return "_No rows._"
    safe = frame.copy().fillna("").astype(str)
    columns = list(safe.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in safe.iterrows():
        values = [row[col].replace("\n", " ").replace("|", "\\|") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def validation_report(output_dir: Path) -> str:
    processed_dir = output_dir / "data" / "processed"
    months_path = processed_dir / "months.csv"
    messages_path = processed_dir / "messages.csv"
    threads_path = processed_dir / "threads.csv"
    parse_issues_path = processed_dir / "parse_issues.csv"
    noisy_path = processed_dir / "noisy_subjects.csv"
    messages_clean_path = processed_dir / "messages_clean.csv"
    author_aliases_path = processed_dir / "author_aliases.csv"
    needs_review_path = processed_dir / "authors_needing_review.csv"
    reply_edges_path = processed_dir / "reply_edges.csv"
    count_mismatch_audit_path = processed_dir / "count_mismatch_audit.csv"
    skipped_mbox_path = processed_dir / "skipped_mbox_rows.csv"
    atlas_paths = {
        "atlas_timeline.csv": processed_dir / "atlas_timeline.csv",
        "atlas_topic_profiles.csv": processed_dir / "atlas_topic_profiles.csv",
        "atlas_list_functions.csv": processed_dir / "atlas_list_functions.csv",
        "atlas_people_summary.csv": processed_dir / "atlas_people_summary.csv",
        "atlas_reply_summary.csv": processed_dir / "atlas_reply_summary.csv",
        "case_study_candidates.csv": processed_dir / "case_study_candidates.csv",
    }
    thread_index_path = processed_dir / "thread_explorer_index.csv"
    curated_cases_path = processed_dir / "curated_case_studies.csv"
    review_notes_path = output_dir / "data" / "curation" / "first_review_notes.csv"
    review_import_audit_path = processed_dir / "review_import_audit.csv"
    case_review_queue_path = processed_dir / "case_review_queue.csv"
    first_review_shortlist_path = processed_dir / "first_review_shortlist.csv"
    case_review_packet_paths = {
        "case_review_queue_philological.csv": processed_dir / "case_review_queue_philological.csv",
        "case_review_queue_infrastructure.csv": processed_dir / "case_review_queue_infrastructure.csv",
        "case_review_queue_unassigned.csv": processed_dir / "case_review_queue_unassigned.csv",
    }
    curated_case_summary_path = processed_dir / "curated_case_summary.csv"
    named_reply_summary_path = processed_dir / "named_reply_network_summary.csv"
    named_coparticipation_summary_path = processed_dir / "named_coparticipation_network_summary.csv"
    search_paths = {
        "search_threads.json": processed_dir / "search_threads.json",
        "search_authors.json": processed_dir / "search_authors.json",
        "search_topics.json": processed_dir / "search_topics.json",
        "search_messages_sample.json": processed_dir / "search_messages_sample.json",
    }
    search_page_path = output_dir / "dashboard" / "search.html"
    curated_page_path = output_dir / "dashboard" / "curated.html"
    first_review_worksheet_path = output_dir / "reports" / "first_review_worksheet.md"
    data_dictionary_path = output_dir / "data_dictionary.md"
    datapackage_path = output_dir / "datapackage.json"
    citation_path = output_dir / "CITATION.cff"
    human_review_index_path = processed_dir / "human_review_index.csv"
    human_review_summary_path = processed_dir / "human_review_summary.json"
    interpretive_guardrails_path = processed_dir / "interpretive_guardrails.csv"
    interpretive_guardrails_report_path = output_dir / "reports" / "interpretive_guardrails.md"

    months = pd.read_csv(months_path) if months_path.exists() else pd.DataFrame()
    messages = pd.read_csv(messages_path, dtype=str, low_memory=False) if messages_path.exists() else pd.DataFrame()
    threads = pd.read_csv(threads_path) if threads_path.exists() else pd.DataFrame()
    parse_issues = pd.read_csv(parse_issues_path) if parse_issues_path.exists() else pd.DataFrame()
    noisy = pd.read_csv(noisy_path) if noisy_path.exists() else pd.DataFrame()
    messages_clean = pd.read_csv(messages_clean_path, dtype=str, low_memory=False) if messages_clean_path.exists() else pd.DataFrame()
    author_aliases = pd.read_csv(author_aliases_path, dtype=str, low_memory=False) if author_aliases_path.exists() else pd.DataFrame()
    needs_review = pd.read_csv(needs_review_path, dtype=str, low_memory=False) if needs_review_path.exists() else pd.DataFrame()
    reply_edges = pd.read_csv(reply_edges_path, dtype=str, low_memory=False) if reply_edges_path.exists() else pd.DataFrame()
    count_mismatch_audit = pd.read_csv(count_mismatch_audit_path, dtype=str, low_memory=False) if count_mismatch_audit_path.exists() else pd.DataFrame()
    skipped_mbox = pd.read_csv(skipped_mbox_path, dtype=str, low_memory=False) if skipped_mbox_path.exists() else pd.DataFrame()
    atlas_tables = {name: pd.read_csv(path, dtype=str, low_memory=False) if path.exists() else pd.DataFrame() for name, path in atlas_paths.items()}
    thread_index = pd.read_csv(thread_index_path, dtype=str, low_memory=False) if thread_index_path.exists() else pd.DataFrame()
    curated_cases = pd.read_csv(curated_cases_path, dtype=str, low_memory=False) if curated_cases_path.exists() else pd.DataFrame()
    review_notes = pd.read_csv(review_notes_path, dtype=str, low_memory=False).fillna("") if review_notes_path.exists() else pd.DataFrame()
    review_import_audit = pd.read_csv(review_import_audit_path, dtype=str, low_memory=False).fillna("") if review_import_audit_path.exists() else pd.DataFrame()
    case_review_queue = pd.read_csv(case_review_queue_path, dtype=str, low_memory=False).fillna("") if case_review_queue_path.exists() else pd.DataFrame()
    first_review_shortlist = pd.read_csv(first_review_shortlist_path, dtype=str, low_memory=False).fillna("") if first_review_shortlist_path.exists() else pd.DataFrame()
    case_review_packets = {
        name: pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()
        for name, path in case_review_packet_paths.items()
    }
    curated_case_summary = pd.read_csv(curated_case_summary_path, dtype=str, low_memory=False).fillna("") if curated_case_summary_path.exists() else pd.DataFrame()
    named_reply_summary = pd.read_csv(named_reply_summary_path, dtype=str, low_memory=False).fillna("") if named_reply_summary_path.exists() else pd.DataFrame()
    named_coparticipation_summary = pd.read_csv(named_coparticipation_summary_path, dtype=str, low_memory=False).fillna("") if named_coparticipation_summary_path.exists() else pd.DataFrame()
    human_review_index = pd.read_csv(human_review_index_path, dtype=str, low_memory=False).fillna("") if human_review_index_path.exists() else pd.DataFrame()
    interpretive_guardrails = pd.read_csv(interpretive_guardrails_path, dtype=str, low_memory=False).fillna("") if interpretive_guardrails_path.exists() else pd.DataFrame()
    search_tables: dict[str, list[dict[str, object]]] = {}
    search_errors: list[str] = []
    for name, path in search_paths.items():
        try:
            search_tables[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except json.JSONDecodeError as exc:
            search_tables[name] = []
            search_errors.append(f"{name}: {exc}")

    lines = ["# INDOLOGY Archive Validation", ""]
    if months.empty:
        lines.append("No month metadata found. Run the scraper first.")
        return "\n".join(lines)

    first = months.sort_values(["year", "month"]).iloc[0]
    last = months.sort_values(["year", "month"]).iloc[-1]
    lines.extend(
        [
            "## Coverage",
            "",
            f"- Months harvested: {len(months):,}",
            f"- First harvested month: {int(first['year'])}-{int(first['month']):02d}",
            f"- Last harvested month: {int(last['year'])}-{int(last['month']):02d}",
            f"- Messages parsed: {len(messages):,}",
            f"- Cleaned message rows: {len(messages_clean):,}" if not messages_clean.empty else "- Cleaned message rows: not generated",
            f"- Threads reconstructed: {len(threads):,}",
            "",
        ]
    )

    missing_counts = months[months["message_count_index"] != months["message_count_mbox"]]
    lines.extend(
        [
            "## Count Checks",
            "",
            f"- Months where archive index count differs from mbox count: {len(missing_counts):,}",
            f"- Parse issue rows: {len(parse_issues):,}",
            "",
        ]
    )
    if not missing_counts.empty:
        lines.append(markdown_table(missing_counts[["slug", "message_count_index", "message_count_mbox"]].head(20)))
        lines.append("")
    if not count_mismatch_audit.empty:
        lines.extend(
            [
                "- Count mismatch audit generated: yes",
                f"- Extra skipped mbox rows recorded: {len(skipped_mbox):,}",
                "",
                markdown_table(count_mismatch_audit.head(20)),
                "",
            ]
        )

    if not messages_clean.empty and len(messages_clean) != len(messages):
        lines.extend(["## Blocking Validation Issues", "", f"- `messages_clean.csv` row count {len(messages_clean):,} does not match `messages.csv` row count {len(messages):,}.", ""])

    if not messages.empty:
        topic_counts = messages["primary_topic"].value_counts().head(12)
        topic_table = topic_counts.rename_axis("topic").reset_index(name="messages")
        lines.extend(["## Topic Spot Check", "", markdown_table(topic_table), ""])
        sample_cols = ["archive_id", "date", "author_display", "primary_topic", "clean_subject", "archive_url"]
        sampled = messages.sort_values(["archive_year", "archive_month", "archive_id"]).groupby("decade", dropna=False).head(3)
        lines.extend(["## Sample By Era", "", markdown_table(sampled[sample_cols].head(40)), ""])

    if not author_aliases.empty:
        status_counts = author_aliases["status"].value_counts().rename_axis("status").reset_index(name="raw_author_strings")
        lines.extend(
            [
                "## Author Normalization",
                "",
                f"- Raw author strings audited: {len(author_aliases):,}",
                f"- Author strings needing review: {len(needs_review):,}",
                "",
                markdown_table(status_counts),
                "",
            ]
        )

    if not reply_edges.empty:
        confidence_counts = reply_edges["confidence"].value_counts().rename_axis("confidence").reset_index(name="reply_rows")
        resolved_count = len(reply_edges[reply_edges["target_author"].fillna("") != ""])
        lines.extend(
            [
                "## Directed Reply Network",
                "",
                f"- Directed reply rows: {len(reply_edges):,}",
                f"- Resolved directed replies: {resolved_count:,}",
                "",
                markdown_table(confidence_counts),
                "",
            ]
        )

    if all(not table.empty for table in atlas_tables.values()):
        atlas_counts = pd.DataFrame(
            [{"table": name, "rows": len(table)} for name, table in atlas_tables.items()]
        )
        lines.extend(["## Guided Atlas Layers", "", markdown_table(atlas_counts), ""])
    else:
        missing_atlas = [name for name, table in atlas_tables.items() if table.empty]
        lines.extend(["## Guided Atlas Layers", "", f"- Missing or empty atlas tables: {', '.join(missing_atlas)}", ""])

    if not thread_index.empty:
        existing_pages = thread_index["page_path"].map(lambda value: (output_dir / "dashboard" / str(value)).exists())
        valid_urls = thread_index["first_url"].fillna("").str.startswith("https://list.indology.info/")
        lines.extend(
            [
                "## Thread Explorer",
                "",
                f"- Generated thread pages indexed: {len(thread_index):,}",
                f"- Indexed page files present: {int(existing_pages.sum()):,}",
                f"- Rows with public archive URLs: {int(valid_urls.sum()):,}",
                f"- Curated case-study seed rows: {len(curated_cases):,}",
                "",
            ]
        )
        if not curated_cases.empty:
            curation_counts = curated_cases["curation_status"].value_counts().rename_axis("curation_status").reset_index(name="rows")
            lines.extend([markdown_table(curation_counts), ""])
            selected_cases = curated_cases[curated_cases["curation_status"].fillna("").eq("selected")].copy()
            selected_missing_public_note = selected_cases[selected_cases["public_note"].fillna("").eq("")] if "public_note" in selected_cases.columns else selected_cases
            selected_missing_why = selected_cases[selected_cases["why_it_matters"].fillna("").eq("")] if "why_it_matters" in selected_cases.columns else selected_cases
            selected_links = selected_cases.merge(thread_index[["thread_root_id", "page_path", "first_url"]], on="thread_root_id", how="left") if not selected_cases.empty else pd.DataFrame()
            selected_link_ok = selected_links.apply(
                lambda row: (output_dir / "dashboard" / str(row.get("page_path", ""))).exists()
                or str(row.get("first_url", "")).startswith("https://list.indology.info/"),
                axis=1,
            ) if not selected_links.empty else pd.Series(dtype=bool)
            lines.extend(
                [
                    f"- Selected cases: {len(selected_cases):,}",
                    f"- Selected cases with public notes: {len(selected_cases) - len(selected_missing_public_note):,}/{len(selected_cases):,}",
                    f"- Selected cases with why-it-matters notes: {len(selected_cases) - len(selected_missing_why):,}/{len(selected_cases):,}",
                    f"- Selected cases with local page or archive fallback: {int(selected_link_ok.sum()) if not selected_link_ok.empty else 0:,}/{len(selected_cases):,}",
                    "",
                ]
            )
            if not selected_missing_public_note.empty:
                lines.extend(["## Blocking Validation Issues", "", "- Some selected cases lack `public_note`.", ""])
            if not selected_missing_why.empty:
                lines.extend(["## Blocking Validation Issues", "", "- Some selected cases lack `why_it_matters`.", ""])
            if not selected_link_ok.empty and int(selected_link_ok.sum()) != len(selected_cases):
                lines.extend(["## Blocking Validation Issues", "", "- Some selected cases lack both an existing local thread page and a public archive fallback.", ""])
        if int(existing_pages.sum()) != len(thread_index):
            lines.extend(["## Blocking Validation Issues", "", "- Some `thread_explorer_index.csv` page paths do not exist.", ""])

    if not case_review_queue.empty or curated_page_path.exists():
        allowed_statuses = {"candidate", "selected", "rejected", "needs_more_review"}
        allowed_tracks = {"", "philological_substance", "infrastructure_history"}
        status_bad = case_review_queue[~case_review_queue["curation_status"].isin(allowed_statuses)] if not case_review_queue.empty else pd.DataFrame()
        track_bad = case_review_queue[
            ~(case_review_queue["review_track"].isin(allowed_tracks) & case_review_queue["suggested_track"].isin(allowed_tracks))
        ] if not case_review_queue.empty else pd.DataFrame()
        local_links = case_review_queue["page_path"].map(lambda value: (output_dir / "dashboard" / str(value)).exists()) if not case_review_queue.empty else pd.Series(dtype=bool)
        fallback_links = case_review_queue["first_url"].fillna("").str.startswith("https://list.indology.info/") if not case_review_queue.empty else pd.Series(dtype=bool)
        queue_link_ok = (local_links | fallback_links) if not case_review_queue.empty else pd.Series(dtype=bool)
        lines.extend(
            [
                "## Curated Case-Study Workflow",
                "",
                f"- Curated workflow page generated: {'yes' if curated_page_path.exists() else 'no'}",
                f"- Editable review notes rows: {len(review_notes):,}",
                f"- Review import audit rows: {len(review_import_audit):,}",
                f"- Review queue rows: {len(case_review_queue):,}",
                f"- Case summary rows: {len(curated_case_summary):,}",
                f"- Queue rows with existing local page or public archive fallback: {int(queue_link_ok.sum()) if not queue_link_ok.empty else 0:,}/{len(case_review_queue):,}",
                "",
            ]
        )
        packet_counts = pd.DataFrame(
            [{"packet": name, "rows": len(frame), "exists": "yes" if case_review_packet_paths[name].exists() else "no"} for name, frame in case_review_packets.items()]
        )
        packet_total = int(packet_counts["rows"].sum()) if not packet_counts.empty else 0
        lines.extend([markdown_table(packet_counts), f"- Review packet rows total: {packet_total:,}/{len(case_review_queue):,}", ""])
        shortlist_ids = set(first_review_shortlist["thread_root_id"].astype(str)) if not first_review_shortlist.empty else set()
        queue_ids = set(case_review_queue["thread_root_id"].astype(str)) if not case_review_queue.empty else set()
        shortlist_link_ok = first_review_shortlist["page_path"].map(lambda value: (output_dir / "dashboard" / str(value)).exists()) if not first_review_shortlist.empty else pd.Series(dtype=bool)
        shortlist_fallback_ok = first_review_shortlist["first_url"].fillna("").str.startswith("https://list.indology.info/") if not first_review_shortlist.empty else pd.Series(dtype=bool)
        shortlist_reason_ok = first_review_shortlist["review_priority_reason"].fillna("").ne("").all() if not first_review_shortlist.empty else False
        worksheet_text = first_review_worksheet_path.read_text(encoding="utf-8") if first_review_worksheet_path.exists() else ""
        worksheet_sections = worksheet_text.count("\n## ")
        worksheet_prompt_ok = all(
            prompt in worksheet_text
            for prompt in [
                "What is this thread about?",
                "Why is it useful for the atlas?",
                "What caveats should be visible?",
                "Recommended public note:",
            ]
        )
        lines.extend(
            [
                f"- First review shortlist rows: {len(first_review_shortlist):,}",
                f"- First review shortlist rows present in full queue: {len(shortlist_ids & queue_ids):,}/{len(first_review_shortlist):,}",
                f"- First review shortlist rows with local page or public archive fallback: {int((shortlist_link_ok | shortlist_fallback_ok).sum()) if not first_review_shortlist.empty else 0:,}/{len(first_review_shortlist):,}",
                f"- First review shortlist rows with priority reasons: {'yes' if shortlist_reason_ok else 'no'}",
                f"- First review worksheet generated: {'yes' if first_review_worksheet_path.exists() else 'no'}",
                f"- First review worksheet sections: {worksheet_sections}",
                f"- First review worksheet includes standard prompts: {'yes' if worksheet_prompt_ok else 'no'}",
                "",
            ]
        )
        if not case_review_queue.empty:
            track_counts = case_review_queue["suggested_track"].replace("", "(unassigned)").value_counts().rename_axis("suggested_track").reset_index(name="rows")
            lines.extend([markdown_table(track_counts), ""])
        if not curated_case_summary.empty:
            lines.extend([markdown_table(curated_case_summary.head(20)), ""])
        if len(case_review_queue) != 250:
            lines.extend(["## Blocking Validation Issues", "", f"- `case_review_queue.csv` has {len(case_review_queue):,} rows, expected 250.", ""])
        if not status_bad.empty:
            lines.extend(["## Blocking Validation Issues", "", "- Some review queue rows have invalid curation statuses.", ""])
        if not track_bad.empty:
            lines.extend(["## Blocking Validation Issues", "", "- Some review queue rows have invalid review or suggested tracks.", ""])
        if not queue_link_ok.empty and int(queue_link_ok.sum()) != len(case_review_queue):
            lines.extend(["## Blocking Validation Issues", "", "- Some review queue rows lack both an existing local thread page and a public archive fallback.", ""])
        if packet_total != len(case_review_queue):
            lines.extend(["## Blocking Validation Issues", "", "- Split review packet row counts do not add up to `case_review_queue.csv`.", ""])
        if len(first_review_shortlist) != 25:
            lines.extend(["## Blocking Validation Issues", "", f"- `first_review_shortlist.csv` has {len(first_review_shortlist):,} rows, expected 25.", ""])
        if len(shortlist_ids & queue_ids) != len(first_review_shortlist):
            lines.extend(["## Blocking Validation Issues", "", "- Some `first_review_shortlist.csv` rows are not present in `case_review_queue.csv`.", ""])
        if not first_review_shortlist.empty and int((shortlist_link_ok | shortlist_fallback_ok).sum()) != len(first_review_shortlist):
            lines.extend(["## Blocking Validation Issues", "", "- Some shortlist rows lack both an existing local thread page and a public archive fallback.", ""])
        if not shortlist_reason_ok:
            lines.extend(["## Blocking Validation Issues", "", "- Some shortlist rows lack `review_priority_reason`.", ""])
        if worksheet_sections != len(first_review_shortlist):
            lines.extend(["## Blocking Validation Issues", "", "- `first_review_worksheet.md` section count does not match `first_review_shortlist.csv`.", ""])
        if not worksheet_prompt_ok:
            lines.extend(["## Blocking Validation Issues", "", "- `first_review_worksheet.md` is missing one or more standard review prompts.", ""])

    if not named_reply_summary.empty or not named_coparticipation_summary.empty:
        reply_type_ok = named_reply_summary["network_type"].eq("direct_reply").all() if not named_reply_summary.empty else True
        cop_type_ok = named_coparticipation_summary["network_type"].eq("co_participation").all() if not named_coparticipation_summary.empty else True
        reply_self_flag_ok = "is_self_reply" in named_reply_summary.columns if not named_reply_summary.empty else True
        network_counts = pd.DataFrame(
            [
                {"table": "named_reply_network_summary.csv", "rows": len(named_reply_summary), "expected_network_type": "direct_reply", "type_ok": reply_type_ok, "has_self_reply_flag": reply_self_flag_ok},
                {"table": "named_coparticipation_network_summary.csv", "rows": len(named_coparticipation_summary), "expected_network_type": "co_participation", "type_ok": cop_type_ok, "has_self_reply_flag": ""},
            ]
        )
        lines.extend(["## Named Network Summaries", "", markdown_table(network_counts), ""])
        if not reply_type_ok:
            lines.extend(["## Blocking Validation Issues", "", "- `named_reply_network_summary.csv` contains rows not labeled `direct_reply`.", ""])
        if not reply_self_flag_ok:
            lines.extend(["## Blocking Validation Issues", "", "- `named_reply_network_summary.csv` is missing `is_self_reply`.", ""])
        if not cop_type_ok:
            lines.extend(["## Blocking Validation Issues", "", "- `named_coparticipation_network_summary.csv` contains rows not labeled `co_participation`.", ""])

    if search_tables or search_errors or search_page_path.exists():
        search_counts = pd.DataFrame(
            [
                {
                    "file": name,
                    "exists": "yes" if path.exists() else "no",
                    "valid_json_rows": len(search_tables.get(name, [])),
                }
                for name, path in search_paths.items()
            ]
        )
        lines.extend(
            [
                "## Static Search And Browse",
                "",
                f"- Search page generated: {'yes' if search_page_path.exists() else 'no'}",
                "",
                markdown_table(search_counts),
                "",
            ]
        )
        if search_errors:
            lines.extend(["## Blocking Validation Issues", "", "- Search JSON parse errors: " + "; ".join(search_errors), ""])
        thread_search = search_tables.get("search_threads.json", [])
        if thread_search:
            local_ok = 0
            fallback_ok = 0
            status_ok = 0
            curated_status = {}
            if not curated_cases.empty:
                curated_status = dict(zip(curated_cases["thread_root_id"].astype(str), curated_cases["curation_status"].astype(str)))
            for row in thread_search:
                local_page = str(row.get("local_page", "") or "")
                first_url = str(row.get("first_url", "") or "")
                thread_id = str(row.get("thread_root_id", "") or "")
                if local_page and (output_dir / "dashboard" / local_page).exists():
                    local_ok += 1
                elif first_url.startswith("https://list.indology.info/"):
                    fallback_ok += 1
                if not curated_status or str(row.get("curation_status", "") or "candidate") == curated_status.get(thread_id, "candidate"):
                    status_ok += 1
            lines.extend(
                [
                    f"- Thread search rows with local page or public archive fallback: {local_ok + fallback_ok:,}/{len(thread_search):,}",
                    f"- Thread search rows whose curation status matches `curated_case_studies.csv`: {status_ok:,}/{len(thread_search):,}",
                    "",
                ]
            )
            if local_ok + fallback_ok != len(thread_search):
                lines.extend(["## Blocking Validation Issues", "", "- Some `search_threads.json` rows have neither an existing local page nor a public archive fallback URL.", ""])
            if status_ok != len(thread_search):
                lines.extend(["## Blocking Validation Issues", "", "- Some `search_threads.json` curation statuses do not match `curated_case_studies.csv`.", ""])

    datapackage = {}
    datapackage_errors: list[str] = []
    if datapackage_path.exists():
        try:
            datapackage = json.loads(datapackage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            datapackage_errors.append(str(exc))
    data_dictionary_text = data_dictionary_path.read_text(encoding="utf-8") if data_dictionary_path.exists() else ""
    citation_text = citation_path.read_text(encoding="utf-8") if citation_path.exists() else ""
    guardrails_text = interpretive_guardrails_report_path.read_text(encoding="utf-8") if interpretive_guardrails_report_path.exists() else ""
    dictionary_families = ["messages", "authors", "replies", "networks", "atlas", "search", "curation", "validation"]
    dictionary_hits = {
        family: family in data_dictionary_text.lower()
        for family in dictionary_families
    }
    required_citation_terms = ["title:", "authors:", "repository-code:", "license:", "date-released:"]
    citation_hits = {term: term in citation_text for term in required_citation_terms}
    datapackage_resources = datapackage.get("resources", []) if isinstance(datapackage, dict) else []
    missing_datapackage_paths = [
        str(resource.get("path", ""))
        for resource in datapackage_resources
        if resource.get("path") and not (output_dir / str(resource.get("path"))).exists()
    ]
    review_domains = set(human_review_index["domain"].astype(str)) if not human_review_index.empty and "domain" in human_review_index.columns else set()
    expected_review_domain_groups = {
        "author review": {"author_normalization"},
        "case review": {"case_study_review", "first_review_shortlist"},
        "count/noisy subject review": {"count_mismatch", "noisy_subject"},
        "reply-network review": {"reply_network"},
    }
    review_domain_hits = {
        label: bool(review_domains & domains)
        for label, domains in expected_review_domain_groups.items()
    }
    guardrail_claim_areas = set(interpretive_guardrails["claim_area"].astype(str)) if not interpretive_guardrails.empty and "claim_area" in interpretive_guardrails.columns else set()
    required_guardrails = {"direct_reply_network", "co_participation_network", "message_volume", "archive_representativeness", "author_normalization"}
    guardrails_have_overclaims = (
        not interpretive_guardrails.empty
        and "forbidden_overclaim" in interpretive_guardrails.columns
        and interpretive_guardrails["forbidden_overclaim"].astype(str).str.len().gt(0).all()
    )
    lines.extend(
        [
            "## Publication Metadata Layer",
            "",
            f"- Data dictionary generated: {'yes' if data_dictionary_path.exists() else 'no'}",
            f"- Datapackage generated: {'yes' if datapackage_path.exists() else 'no'}",
            f"- Datapackage resources listed: {len(datapackage_resources):,}",
            f"- Datapackage resources with missing local paths: {len(missing_datapackage_paths):,}",
            f"- Citation metadata generated: {'yes' if citation_path.exists() else 'no'}",
            f"- Unified human review index rows: {len(human_review_index):,}",
            f"- Human review summary generated: {'yes' if human_review_summary_path.exists() else 'no'}",
            f"- Interpretive guardrails rows: {len(interpretive_guardrails):,}",
            f"- Interpretive guardrails report generated: {'yes' if interpretive_guardrails_report_path.exists() else 'no'}",
            "",
            markdown_table(pd.DataFrame([{"check": key, "ok": "yes" if value else "no"} for key, value in dictionary_hits.items()])),
            "",
            markdown_table(pd.DataFrame([{"check": key, "ok": "yes" if value else "no"} for key, value in review_domain_hits.items()])),
            "",
        ]
    )
    if datapackage_errors:
        lines.extend(["## Blocking Validation Issues", "", "- `datapackage.json` is not valid JSON: " + "; ".join(datapackage_errors), ""])
    if not datapackage_path.exists():
        lines.extend(["## Blocking Validation Issues", "", "- `datapackage.json` is missing.", ""])
    if missing_datapackage_paths:
        lines.extend(["## Blocking Validation Issues", "", "- `datapackage.json` lists missing local resources: " + ", ".join(missing_datapackage_paths[:10]), ""])
    if not all(dictionary_hits.values()):
        lines.extend(["## Blocking Validation Issues", "", "- `data_dictionary.md` does not mention all required major table families.", ""])
    if not all(citation_hits.values()) or "INDOLOGY-L Archive Atlas, 1990-2026" not in citation_text:
        lines.extend(["## Blocking Validation Issues", "", "- `CITATION.cff` is missing one or more required citation fields.", ""])
    if not human_review_index_path.exists() or human_review_index.empty:
        lines.extend(["## Blocking Validation Issues", "", "- `human_review_index.csv` is missing or empty.", ""])
    if not all(review_domain_hits.values()):
        lines.extend(["## Blocking Validation Issues", "", "- `human_review_index.csv` does not include all required review domains.", ""])
    if not required_guardrails.issubset(guardrail_claim_areas) or not guardrails_have_overclaims:
        lines.extend(["## Blocking Validation Issues", "", "- `interpretive_guardrails.csv` is missing required network/author/volume overclaim warnings.", ""])
    if "reply edges are not influence" not in guardrails_text.lower() and "reply edge proves influence" not in guardrails_text.lower():
        lines.extend(["## Blocking Validation Issues", "", "- `reports/interpretive_guardrails.md` does not visibly warn against influence claims from reply edges.", ""])

    if not noisy.empty:
        lines.extend(
            [
                "## Flagged Noisy Subjects",
                "",
                f"- Noisy or list-mechanics-like subjects: {len(noisy):,}",
                "",
                markdown_table(noisy.head(30)),
                "",
            ]
        )
    else:
        lines.extend(["## Flagged Noisy Subjects", "", "- None flagged.", ""])

    lines.extend(
        [
            "## Manual Validation Checklist",
            "",
            "- Spot-check several archive URLs from `messages.csv` against the live HTML pages.",
            "- For a full run, confirm harvested month count against the archive landing page.",
            "- Inspect `parse_issues.csv`; count mismatches usually mean malformed monthly mbox text or interrupted download.",
            "- Inspect `count_mismatch_audit.csv` and `skipped_mbox_rows.csv` for known minor mbox/archive count quirks.",
            "- Review `authors_needing_review.csv` before making person-level claims.",
            "- Spot-check sampled `reply_edges.csv` rows against `source_url` and `target_url` before interpreting directed networks.",
            "- Review `case_study_candidates.csv`; these are candidates for close reading, not final curated examples.",
            "- Review `topic_year_counts.csv` before drawing interpretive conclusions from topic labels.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(output_dir: Path) -> Path:
    report = validation_report(output_dir)
    path = output_dir / "reports" / "validation.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    path = write_report(args.output_dir)
    print(path)


if __name__ == "__main__":
    main()
