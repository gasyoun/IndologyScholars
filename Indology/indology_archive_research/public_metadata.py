"""Generate public metadata, citation files, and review indexes."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd


DATASET_TITLE = "INDOLOGY-L Archive Atlas, 1990-2026"
SOURCE_ARCHIVE_URL = "https://list.indology.info/pipermail/indology/"
REPOSITORY_URL = "https://github.com/sanskrit-lexicon/IndologyScholars"
LICENSE = "CC-BY-4.0"


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("")


def file_row_count(path: Path) -> int | str:
    try:
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            return len(value) if isinstance(value, list) else 1
        if path.suffix == ".md":
            return len(path.read_text(encoding="utf-8").splitlines())
        if path.suffix == ".html":
            return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return max(sum(1 for _ in handle) - 1, 0)
    except (OSError, json.JSONDecodeError):
        return ""


def public_resource_rows(output_dir: Path) -> list[dict[str, object]]:
    processed_dir = output_dir / "data" / "processed"
    manifest_path = processed_dir / "dataset_manifest.csv"
    rows: list[dict[str, object]] = []
    if manifest_path.exists():
        manifest = read_csv_if_exists(manifest_path)
        for _, row in manifest.iterrows():
            rel = str(row.get("relative_path", ""))
            if rel and (output_dir / rel).exists():
                rows.append(
                    {
                        "name": Path(rel).name,
                        "path": rel.replace("\\", "/"),
                        "format": Path(rel).suffix.lstrip(".").upper() or "TEXT",
                        "mediatype": mediatype_for_path(Path(rel)),
                        "bytes": (output_dir / rel).stat().st_size,
                        "rows": row.get("rows", ""),
                        "description": row.get("description", "Generated atlas output."),
                    }
                )

    extras = [
        ("data_dictionary.md", "Plain-English data dictionary and reuse guide."),
        ("CITATION.cff", "Citation metadata for the standalone INDOLOGY-L archive atlas."),
        ("datapackage.json", "Frictionless-style machine-readable dataset metadata."),
        ("reports/research_report.md", "Narrative research report for the public atlas."),
        ("reports/validation.md", "Validation report and manual checklist."),
        ("reports/interpretive_guardrails.md", "Responsible-claims guide for interpreting generated outputs."),
        ("reports/first_review_worksheet.md", "Worksheet for the first pass of case-study review."),
        ("dashboard/index.html", "Static guided atlas dashboard."),
        ("dashboard/search.html", "Static search and browse interface."),
        ("dashboard/curated.html", "Static curation workflow page."),
    ]
    known_paths = {str(row["path"]) for row in rows}
    for rel, description in extras:
        path = output_dir / rel
        if path.exists() and rel not in known_paths:
            rows.append(
                {
                    "name": Path(rel).name,
                    "path": rel,
                    "format": Path(rel).suffix.lstrip(".").upper() or "TEXT",
                    "mediatype": mediatype_for_path(Path(rel)),
                    "bytes": path.stat().st_size,
                    "rows": file_row_count(path),
                    "description": description,
                }
            )
    return rows


def mediatype_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "text/csv"
    if suffix == ".json":
        return "application/json"
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".html":
        return "text/html"
    if suffix == ".png":
        return "image/png"
    return "application/octet-stream"


def write_datapackage(output_dir: Path) -> Path:
    resources = public_resource_rows(output_dir)
    package = {
        "profile": "data-package",
        "name": "indology-l-archive-atlas-1990-2026",
        "title": DATASET_TITLE,
        "description": (
            "A reproducible metadata-first atlas of the public INDOLOGY-L Pipermail archive. "
            "The package contains harvested metadata, conservative author-normalization audit tables, "
            "topic and list-function summaries, directed reply and co-participation evidence, curation "
            "queues, sparse Renou state/register subject-line crosswalks, validation reports, and static atlas/search pages."
        ),
        "version": date.today().isoformat(),
        "created": date.today().isoformat(),
        "contributors": [
            {"title": "Generated by the INDOLOGY archive research pipeline", "role": "author"},
            {"title": "INDOLOGY-L public mailing-list archive", "role": "source"},
        ],
        "licenses": [
            {
                "name": LICENSE,
                "title": "Creative Commons Attribution 4.0 International",
                "path": "https://creativecommons.org/licenses/by/4.0/",
            }
        ],
        "sources": [
            {
                "title": "INDOLOGY mailing-list Pipermail archive",
                "path": SOURCE_ARCHIVE_URL,
                "email_archive_public": True,
            }
        ],
        "homepage": "dashboard/index.html",
        "repository": REPOSITORY_URL,
        "rights": (
            "Generated metadata and code-oriented documentation are prepared for reuse with attribution. "
            "Message metadata derives from a public mailing-list archive; quoted or linked archive content "
            "remains subject to the source archive and original posters. The atlas does not redistribute full "
            "message bodies in v1."
        ),
        "resources": resources,
    }
    path = output_dir / "datapackage.json"
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_citation(output_dir: Path) -> Path:
    today = date.today().isoformat()
    text = f"""cff-version: 1.2.0
message: "If you use this standalone appendix, please cite it as below and also cite the public INDOLOGY-L archive where appropriate."
title: "{DATASET_TITLE}"
type: dataset
authors:
  - name: "Generated by the INDOLOGY archive research pipeline"
repository-code: "{REPOSITORY_URL}"
url: "{SOURCE_ARCHIVE_URL}"
date-released: "{today}"
license: "{LICENSE}"
abstract: "Metadata-first atlas of the public INDOLOGY-L Pipermail archive, with topic, thread, author-normalization, curation, validation, and network evidence tables."
keywords:
  - Indology
  - mailing-list archive
  - scholarly communication
  - metadata
  - digital humanities
"""
    path = output_dir / "CITATION.cff"
    path.write_text(text, encoding="utf-8")
    return path


def write_data_dictionary(output_dir: Path) -> Path:
    processed_dir = output_dir / "data" / "processed"
    manifest = read_csv_if_exists(processed_dir / "dataset_manifest.csv")
    table = "| File | Rows | Description |\n| --- | ---: | --- |\n"
    if not manifest.empty:
        for _, row in manifest.iterrows():
            table += (
                f"| `{row.get('relative_path', row.get('file', ''))}` | "
                f"{row.get('rows', '')} | {str(row.get('description', '')).replace('|', '\\|')} |\n"
            )

    text = f"""# INDOLOGY-L Archive Atlas Data Dictionary

This document describes the generated public-data layer for `{DATASET_TITLE}`. The atlas is a separate research appendix/tool under `Indology/`; it is not merged into the main Russian conference-archive site.

## Source And Scope

- Source archive: {SOURCE_ARCHIVE_URL}
- Coverage target: November 1990 through June 2026.
- Method: metadata-first parsing of monthly archive indexes and monthly mbox headers.
- Out of scope for v1: full message-body NLP and redistribution of message bodies.
- Stable archive anchors: `archive_id`, `archive_url`, `message_id`, `thread_root_id`, and generated local `page_path` values where available.

## Major Table Families

### Messages

`messages_raw.csv`, `messages.csv`, and `messages_clean.csv` move from harvested archive/index metadata to analyzed and author-normalized message metadata. Key provenance fields include `archive_id`, `archive_year`, `archive_month`, `archive_url`, `message_id`, `in_reply_to`, `references`, `date`, subject fields, and topic/list-function labels.

### Authors

`author_aliases.csv`, `authors_needing_review.csv`, and `excluded_author_artifacts.csv` are audit layers. `normalized_author` is a conservative display label, not an authority-file identity. `status`, `confidence`, and `evidence` explain whether a raw author string was confirmed, left for review, or treated as an artifact.

### Replies

`reply_edges.csv` records directed reply evidence from `message_id`, `in_reply_to`, `references`, and conservative thread fallback. Confidence values distinguish exact header matches from lower-confidence inference. `reply_network_edges.csv` aggregates those directed rows.

### Networks

`named_reply_network_summary.csv` is a named direct-reply evidence summary. `named_coparticipation_network_summary.csv` and `network_edges.csv` are co-participation evidence: two authors appear in the same thread. Co-participation is not collaboration.

### Atlas

`atlas_timeline.csv`, `atlas_topic_profiles.csv`, `atlas_list_functions.csv`, `atlas_people_summary.csv`, `atlas_reply_summary.csv`, and `case_study_candidates.csv` translate raw metadata into indologist-facing questions about time, topics, list functions, participation, replies, and candidate threads for close reading.

### Renou

`data/curation/renou_subject_rules.csv` adapts the Louis Renou I-V state axis and register lattice from `RENOU.md` into human-editable subject-line matching rules. `renou_messages.csv` keeps one row per message with optional `renou_states` and `renou_registers`; `renou_message_matches.csv` is the sparse evidence table; `renou_thread_matches.csv`, `renou_state_summary.csv`, `renou_register_summary.csv`, and `renou_coverage.csv` aggregate the layer. Empty Renou fields mean not classified by this layer, not negative evidence.

### Search

`search_threads.json`, `search_authors.json`, `search_topics.json`, and `search_messages_sample.json` feed the static search page. Message search remains compact metadata, not full text.

### Curation

`curated_case_studies.csv`, `case_review_queue.csv`, split review packets, `first_review_shortlist.csv`, `data/curation/first_review_notes.csv`, and `review_import_audit.csv` support the curation round-trip. Generated rows remain `candidate` until manually reviewed.

### Validation

`parse_issues.csv`, `count_mismatch_audit.csv`, `skipped_mbox_rows.csv`, `noisy_subjects.csv`, `human_review_index.csv`, `human_review_summary.json`, `interpretive_guardrails.csv`, `reports/validation.md`, and `reports/interpretive_guardrails.md` make parsing quirks, review needs, and responsible-claims limits visible.

## Review Fields

Human-facing review fields include `curation_status`, `review_track`, `review_decision`, `public_note`, `why_it_matters`, `curator_comments`, `manual_reviewer`, `manual_review_date`, `priority`, `reason`, and `note`. Empty review fields mean not yet reviewed, not negative evidence.

## Caveats

- Reply edges are not influence.
- Message counts are not scholarly importance.
- Archive visibility is not field representativeness.
- Author normalization is a reproducible audit layer, not a biographical authority file.
- Case-study candidates are generated reading suggestions, not a canon of important threads.
- The Renou layer is subject-line classification for mailing-list discussions, not dictionary headword tagging.

## Generated Resources

{table}
"""
    path = output_dir / "data_dictionary.md"
    path.write_text(text, encoding="utf-8")
    return path


def review_row(
    domain: str,
    priority: str,
    source_file: str,
    source_row: int | str,
    record_id: str,
    label: str,
    status: str,
    reason: str,
    evidence_url: str = "",
    reviewer: str = "",
    checked_at: str = "",
    note: str = "",
) -> dict[str, str]:
    return {
        "domain": domain,
        "priority": priority,
        "source_file": source_file,
        "source_row": str(source_row),
        "record_id": str(record_id),
        "label": str(label),
        "status": str(status),
        "reason": str(reason),
        "evidence_url": str(evidence_url),
        "reviewer": str(reviewer),
        "checked_at": str(checked_at),
        "note": str(note),
    }


def add_rows_from_frame(
    rows: list[dict[str, str]],
    frame: pd.DataFrame,
    source_file: str,
    domain: str,
    priority: str,
    id_col: str,
    label_col: str,
    status_col: str,
    reason_col: str,
    url_col: str = "",
    note_col: str = "",
    limit: int | None = None,
) -> None:
    if frame.empty:
        return
    local = frame.head(limit) if limit else frame
    for idx, row in local.iterrows():
        rows.append(
            review_row(
                domain=domain,
                priority=priority,
                source_file=source_file,
                source_row=int(idx) + 2,
                record_id=row.get(id_col, ""),
                label=row.get(label_col, ""),
                status=row.get(status_col, "review_needed") or "review_needed",
                reason=row.get(reason_col, ""),
                evidence_url=row.get(url_col, "") if url_col else "",
                note=row.get(note_col, "") if note_col else "",
            )
        )


def build_human_review_rows(output_dir: Path) -> list[dict[str, str]]:
    processed_dir = output_dir / "data" / "processed"
    rows: list[dict[str, str]] = []

    authors = read_csv_if_exists(processed_dir / "authors_needing_review.csv")
    add_rows_from_frame(
        rows,
        authors,
        "data/processed/authors_needing_review.csv",
        "author_normalization",
        "high",
        "author_id",
        "raw_author",
        "status",
        "evidence",
    )

    case_queue = read_csv_if_exists(processed_dir / "case_review_queue.csv")
    add_rows_from_frame(
        rows,
        case_queue,
        "data/processed/case_review_queue.csv",
        "case_study_review",
        "medium",
        "thread_root_id",
        "short_title",
        "curation_status",
        "evidence",
        "first_url",
        "suggested_track_basis",
    )

    shortlist = read_csv_if_exists(processed_dir / "first_review_shortlist.csv")
    add_rows_from_frame(
        rows,
        shortlist,
        "data/processed/first_review_shortlist.csv",
        "first_review_shortlist",
        "high",
        "thread_root_id",
        "short_title",
        "curation_status",
        "review_priority_reason",
        "first_url",
        "evidence",
    )

    audit = read_csv_if_exists(processed_dir / "review_import_audit.csv")
    if not audit.empty and "action" in audit.columns:
        needs_audit = audit[audit["action"].isin(["error", "skipped", "invalid", "blocked"])].copy()
        for idx, row in needs_audit.iterrows():
            rows.append(
                review_row(
                    "review_import",
                    "high" if row.get("action") == "error" else "medium",
                    "data/processed/review_import_audit.csv",
                    int(idx) + 2,
                    row.get("thread_root_id", ""),
                    row.get("column", ""),
                    row.get("action", ""),
                    row.get("reason", ""),
                    note=row.get("new_value", ""),
                )
            )

    mismatches = read_csv_if_exists(processed_dir / "count_mismatch_audit.csv")
    add_rows_from_frame(
        rows,
        mismatches,
        "data/processed/count_mismatch_audit.csv",
        "count_mismatch",
        "medium",
        "slug",
        "slug",
        "downstream_status",
        "notes",
    )

    noisy = read_csv_if_exists(processed_dir / "noisy_subjects.csv")
    add_rows_from_frame(
        rows,
        noisy,
        "data/processed/noisy_subjects.csv",
        "noisy_subject",
        "low",
        "archive_id",
        "clean_subject",
        "review_needed",
        "author_display",
        "archive_url",
        limit=250,
    )

    replies = read_csv_if_exists(processed_dir / "reply_edges.csv")
    if not replies.empty:
        target_cols = [col for col in ["target_author", "target_message_id", "target_url"] if col in replies.columns]
        unresolved = replies[replies[target_cols].apply(lambda row: any(str(value).strip() == "" for value in row), axis=1)] if target_cols else pd.DataFrame()
        for idx, row in unresolved.head(500).iterrows():
            rows.append(
                review_row(
                    "reply_network",
                    "medium",
                    "data/processed/reply_edges.csv",
                    int(idx) + 2,
                    row.get("source_message_id", "") or row.get("thread_root_id", ""),
                    row.get("subject", ""),
                    row.get("confidence", "unresolved"),
                    "Reply-like row has no resolved target author/message/url.",
                    row.get("source_url", ""),
                    note=row.get("evidence", ""),
                )
            )
    return rows


def write_human_review_index(output_dir: Path) -> tuple[Path, Path]:
    processed_dir = output_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    rows = build_human_review_rows(output_dir)
    path = processed_dir / "human_review_index.csv"
    columns = [
        "domain",
        "priority",
        "source_file",
        "source_row",
        "record_id",
        "label",
        "status",
        "reason",
        "evidence_url",
        "reviewer",
        "checked_at",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at": date.today().isoformat(),
        "row_count": len(rows),
        "by_domain": dict(sorted(Counter(row["domain"] for row in rows).items())),
        "by_priority": dict(sorted(Counter(row["priority"] for row in rows).items())),
        "notes": [
            "The index is a reviewer-facing queue, not a list of errors.",
            "Some large domains are capped for review ergonomics; source files remain complete.",
        ],
    }
    summary_path = processed_dir / "human_review_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, summary_path


GUARDRAILS = [
    {
        "claim_area": "direct_reply_network",
        "allowed_claim": "A source message can be linked to a target message by header evidence or documented inference.",
        "forbidden_overclaim": "A reply edge proves influence, agreement, mentorship, or scholarly dependence.",
        "required_evidence": "`reply_edges.csv` confidence, source URL, target URL, and spot-checks for interpreted examples.",
        "current_artifact": "data/processed/reply_edges.csv; data/processed/named_reply_network_summary.csv",
        "review_status": "active_guardrail",
    },
    {
        "claim_area": "co_participation_network",
        "allowed_claim": "Two normalized author labels appear in the same public thread.",
        "forbidden_overclaim": "Co-participation proves collaboration, friendship, institutional school, or shared views.",
        "required_evidence": "`network_edges.csv` or `named_coparticipation_network_summary.csv` plus thread context.",
        "current_artifact": "data/processed/network_edges.csv; data/processed/named_coparticipation_network_summary.csv",
        "review_status": "active_guardrail",
    },
    {
        "claim_area": "message_volume",
        "allowed_claim": "The archive contains a counted number of messages or threads matching the parser output.",
        "forbidden_overclaim": "High message count means importance, expertise, centrality, or field dominance.",
        "required_evidence": "`messages_clean.csv`, `threads.csv`, and validation notes about archive coverage.",
        "current_artifact": "data/processed/messages_clean.csv; reports/validation.md",
        "review_status": "active_guardrail",
    },
    {
        "claim_area": "archive_representativeness",
        "allowed_claim": "The atlas describes visible public INDOLOGY-L archive activity.",
        "forbidden_overclaim": "The archive represents all Indology, all Sanskrit studies, or all scholarly communication in the field.",
        "required_evidence": "Explicit source scope and caveats in report/dashboard/data dictionary.",
        "current_artifact": "data_dictionary.md; reports/research_report.md",
        "review_status": "active_guardrail",
    },
    {
        "claim_area": "author_normalization",
        "allowed_claim": "Raw author strings are grouped conservatively for metadata analysis and marked with confidence/evidence.",
        "forbidden_overclaim": "Normalized labels are authoritative identities or complete biographical records.",
        "required_evidence": "`author_aliases.csv`, `authors_needing_review.csv`, and manual review for public claims.",
        "current_artifact": "data/processed/author_aliases.csv; data/processed/authors_needing_review.csv",
        "review_status": "active_guardrail",
    },
    {
        "claim_area": "case_study_candidates",
        "allowed_claim": "A thread was selected automatically as a candidate because it matches recorded evidence fields.",
        "forbidden_overclaim": "Generated candidates are curated examples or definitive major debates before human review.",
        "required_evidence": "`case_study_candidates.csv`, `case_review_queue.csv`, and reviewed `curated_case_studies.csv` rows.",
        "current_artifact": "data/processed/case_study_candidates.csv; data/processed/curated_case_studies.csv",
        "review_status": "active_guardrail",
    },
    {
        "claim_area": "renou_subject_layer",
        "allowed_claim": "A message or thread subject clearly matches a Renou state/register rule adapted from RENOU.md.",
        "forbidden_overclaim": "A blank Renou field proves irrelevance, or a subject match is equivalent to dictionary headword/sense tagging.",
        "required_evidence": "`renou_subject_rules.csv`, matched term, confidence, archive URL, and thread context for interpreted examples.",
        "current_artifact": "data/processed/renou_messages.csv; data/processed/renou_message_matches.csv; data/curation/renou_subject_rules.csv",
        "review_status": "active_guardrail",
    },
]


def write_guardrails(output_dir: Path) -> tuple[Path, Path]:
    processed_dir = output_dir / "data" / "processed"
    reports_dir = output_dir / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = processed_dir / "interpretive_guardrails.csv"
    pd.DataFrame(GUARDRAILS).to_csv(csv_path, index=False, encoding="utf-8")
    lines = [
        "# Interpretive Guardrails",
        "",
        "These guardrails keep public claims close to the evidence produced by the metadata pipeline.",
        "",
    ]
    for row in GUARDRAILS:
        lines.extend(
            [
                f"## {row['claim_area']}",
                "",
                f"- Allowed claim: {row['allowed_claim']}",
                f"- Forbidden overclaim: {row['forbidden_overclaim']}",
                f"- Required evidence: {row['required_evidence']}",
                f"- Current artifact: `{row['current_artifact']}`",
                "",
            ]
        )
    md_path = reports_dir / "interpretive_guardrails.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def run_public_metadata(output_dir: Path) -> dict[str, Path]:
    outputs = {
        "data_dictionary": write_data_dictionary(output_dir),
        "datapackage": write_datapackage(output_dir),
        "citation": write_citation(output_dir),
    }
    review_index, review_summary = write_human_review_index(output_dir)
    guardrails_csv, guardrails_md = write_guardrails(output_dir)
    outputs.update(
        {
            "human_review_index": review_index,
            "human_review_summary": review_summary,
            "interpretive_guardrails_csv": guardrails_csv,
            "interpretive_guardrails_md": guardrails_md,
        }
    )
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    outputs = run_public_metadata(args.output_dir)
    print({key: str(value) for key, value in outputs.items()})


if __name__ == "__main__":
    main()
