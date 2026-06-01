"""Build one curator-facing index from all machine-generated review queues."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "analytics_output" / "human_review_index.csv"
OUT_JSON = ROOT / "analytics_output" / "human_review_summary.json"

DONE_STATUSES = {
    "accepted",
    "already_confirmed",
    "confirmed",
    "done",
    "manual_override",
    "pass",
}

FIELDS = [
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


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def first(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def status_value(row: dict[str, str], *names: str, default: str = "todo") -> str:
    status = first(row, *names)
    return status or default


def int_value(row: dict[str, str], name: str, default: int = 0) -> int:
    try:
        return int(float(clean(row.get(name)) or default))
    except ValueError:
        return default


def float_value(row: dict[str, str], name: str, default: float = 0.0) -> float:
    try:
        return float(clean(row.get(name)) or default)
    except ValueError:
        return default


def priority_from_talks(row: dict[str, str], field: str = "total_talks", base: int = 1000) -> int:
    return max(1, base - int_value(row, field, 0))


def maybe_add(rows: list[dict[str, str]], item: dict[str, object]) -> None:
    status = clean(item.get("status")).lower()
    if status in DONE_STATUSES:
        return
    normalized = {field: clean(item.get(field)) for field in FIELDS}
    normalized["priority"] = clean(item.get("priority") or "9999")
    rows.append(normalized)


def add_csv_rows(
    output: list[dict[str, str]],
    *,
    source_file: str,
    domain: str,
    id_fields: tuple[str, ...],
    label_fields: tuple[str, ...],
    status_fields: tuple[str, ...],
    reason_fields: tuple[str, ...] = (),
    evidence_fields: tuple[str, ...] = (),
    note_fields: tuple[str, ...] = (),
    priority_fn=None,
) -> None:
    path = ROOT / source_file
    for idx, row in enumerate(read_csv(path), start=2):
        reason = "; ".join(clean(row.get(name)) for name in reason_fields if clean(row.get(name)))
        note = "; ".join(clean(row.get(name)) for name in note_fields if clean(row.get(name)))
        maybe_add(
            output,
            {
                "domain": domain,
                "priority": priority_fn(row) if priority_fn else 9999,
                "source_file": source_file,
                "source_row": idx,
                "record_id": first(row, *id_fields),
                "label": first(row, *label_fields),
                "status": status_value(row, *status_fields),
                "reason": reason,
                "evidence_url": first(row, *evidence_fields),
                "reviewer": first(row, "reviewer"),
                "checked_at": first(row, "checked_at"),
                "note": note,
            },
        )


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    add_csv_rows(
        rows,
        source_file="analytics_output/authority_review_queue.csv",
        domain="authority_identity",
        id_fields=("person_id",),
        label_fields=("full_name_ru", "display_name"),
        status_fields=("review_status",),
        reason_fields=("reason",),
        evidence_fields=("rinc_search_url", "openalex_search_url", "wikipedia_search_url"),
        note_fields=("suggested_query",),
        priority_fn=lambda row: int_value(row, "priority_rank", 999),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/rinc_lookup_queue.csv",
        domain="rinc_identity",
        id_fields=("person_id",),
        label_fields=("full_name_ru", "display_name"),
        status_fields=("review_status",),
        reason_fields=("notes",),
        evidence_fields=("profile_url", "rinc_search_url"),
        note_fields=("birth_year_estimate", "first_publication_year", "first_publication_source"),
        priority_fn=lambda row: priority_from_talks(row, "n_talks"),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/openalex_author_candidates.csv",
        domain="openalex_identity",
        id_fields=("person_id", "openalex_id"),
        label_fields=("local_display_name", "local_latin_name", "openalex_name"),
        status_fields=("manual_status",),
        reason_fields=("notes",),
        evidence_fields=("openalex_id",),
        note_fields=("query_type", "query_string", "works_count", "top_affiliation_name", "relevance_score"),
        priority_fn=lambda row: max(1, 1200 - int_value(row, "total_talks", 0) * 10 - int(float_value(row, "relevance_score") * 100)),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/wikipedia_authority_candidates.csv",
        domain="wikipedia_identity",
        id_fields=("person_id", "candidate_url"),
        label_fields=("name", "candidate_title"),
        status_fields=("review_status", "status"),
        reason_fields=("match_type", "status"),
        evidence_fields=("candidate_url",),
        note_fields=("query", "snippet", "score"),
        priority_fn=lambda row: max(1, 1200 - int_value(row, "total_talks", 0) * 10 - int_value(row, "score", 0)),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/identity_alias_candidates.csv",
        domain="person_disambiguation",
        id_fields=("alias_person_id", "target_person_id"),
        label_fields=("alias_name", "target_name"),
        status_fields=("curation_status",),
        reason_fields=("rule", "confidence"),
        note_fields=("shared_years", "alias_total_talks", "target_total_talks"),
        priority_fn=lambda row: 10 if clean(row.get("confidence")) == "high" else 30,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/birth_year_gap_audit.csv",
        domain="biographical_gap",
        id_fields=("person_id",),
        label_fields=("name", "best_alias_target"),
        status_fields=("curation_status",),
        reason_fields=("best_alias_rule", "best_alias_confidence"),
        note_fields=("total_talks", "first_year", "last_year", "initials_only"),
        priority_fn=lambda row: priority_from_talks(row, "total_talks"),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/theme_review_queue.csv",
        domain="theme_classification",
        id_fields=("presentation_id",),
        label_fields=("title",),
        status_fields=("review_status",),
        reason_fields=("notes",),
        note_fields=("existing_theme_code", "l1_baseline", "l1_conf", "l3_baseline", "l3_conf"),
        priority_fn=lambda row: 50 if clean(row.get("existing_theme_code")) == "unspecified" else 120,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/theme_codes_uncertain_v2.csv",
        domain="theme_uncertainty",
        id_fields=("presentation_id",),
        label_fields=("title",),
        status_fields=("review_status", "status"),
        reason_fields=("reason", "notes"),
        note_fields=("theme_code", "theme_confidence", "l1_conf", "l3_conf"),
        priority_fn=lambda row: 140,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/classification_reliability_sample.csv",
        domain="classification_reliability",
        id_fields=("presentation_id",),
        label_fields=("title",),
        status_fields=("review_status",),
        reason_fields=("selection_reason", "override_reason"),
        note_fields=("theme_l1", "period_l2", "gumilyov_level", "meso_codes", "confidence"),
        priority_fn=lambda row: 40 if int_value(row, "gumilyov_level", 0) >= 3 else 90,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/spacetime_unmatched.csv",
        domain="spacetime_index",
        id_fields=("presentation_id",),
        label_fields=("title",),
        status_fields=("review_status",),
        reason_fields=("needs_place", "needs_time"),
        note_fields=("speaker", "conference_year", "series", "meso_codes"),
        priority_fn=lambda row: 160 - 40 * (int_value(row, "needs_place") + int_value(row, "needs_time")),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/zograf_2026_affiliation_audit.csv",
        domain="affiliation_scope",
        id_fields=("full_name", "person_display"),
        label_fields=("full_name", "person_display"),
        status_fields=("review_status",),
        reason_fields=("category",),
        note_fields=("affil_2026", "history_count", "history_sample", "title"),
        priority_fn=lambda row: {"A": 40, "B": 70, "C": 100}.get(clean(row.get("category")), 120),
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/lineage_candidates.csv",
        domain="scholarly_lineage",
        id_fields=("person_id", "target_person_id"),
        label_fields=("display_name", "target_name"),
        status_fields=("status",),
        reason_fields=("reason", "relation_type"),
        note_fields=("source", "notes"),
        priority_fn=lambda row: 80,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/coauthorship_review.csv",
        domain="coauthorship_review",
        id_fields=("presentation_id",),
        label_fields=("title",),
        status_fields=("review_status",),
        reason_fields=("human_action",),
        evidence_fields=("source_url",),
        note_fields=("year", "series", "people", "source_snippet"),
        priority_fn=lambda row: 65,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/senior_absence_audit.csv",
        domain="senior_absence",
        id_fields=("person_id",),
        label_fields=("display_name",),
        status_fields=("review_status",),
        reason_fields=("interpretation_note",),
        note_fields=("cohort", "birth_year", "first_year", "last_year", "talks_before_threshold", "living_status_basis"),
        priority_fn=lambda row: 60 if clean(row.get("cohort")) == "absent_after_2022" else 68,
    )
    add_csv_rows(
        rows,
        source_file="curation/senior_biographical_verification.csv",
        domain="senior_biographical_verification",
        id_fields=("person_id",),
        label_fields=("display_name",),
        status_fields=("external_status",),
        reason_fields=("interpretation_note",),
        evidence_fields=("source_url",),
        note_fields=("cohort_scope", "source_title", "source_date", "checked_at"),
        priority_fn=lambda row: 45 if clean(row.get("external_status")) == "needs_stronger_biographical_source" else 72,
    )

    add_scientometrics_guardrail_rows(rows)
    add_data_quality_rows(rows)
    rows.sort(key=lambda row: (int(row["priority"] or 9999), row["domain"], row["label"], row["record_id"]))
    return rows


def add_scientometrics_guardrail_rows(rows: list[dict[str, str]]) -> None:
    add_csv_rows(
        rows,
        source_file="analytics_output/scientometrics_guardrails.csv",
        domain="scientometrics_guardrail",
        id_fields=("guardrail_id",),
        label_fields=("title",),
        status_fields=("review_status",),
        reason_fields=("why_it_matters",),
        evidence_fields=("source_anchor",),
        note_fields=("next_human_action", "output_path"),
        priority_fn=lambda row: 25,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/scientometrics_claim_registry.csv",
        domain="scientometrics_claim",
        id_fields=("claim_id",),
        label_fields=("allowed_claim", "claim_family"),
        status_fields=("review_status",),
        reason_fields=("forbidden_overclaim",),
        note_fields=("allowed_scope", "required_evidence", "minimum_review_artifact"),
        priority_fn=lambda row: 35,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/coverage_bias_audit.csv",
        domain="coverage_bias",
        id_fields=("source",),
        label_fields=("source_label",),
        status_fields=("review_status",),
        reason_fields=("interpretation",),
        note_fields=("coverage_share", "high_activity_missing_persons", "review_action"),
        priority_fn=lambda row: 45,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/conference_role_taxonomy.csv",
        domain="conference_role_taxonomy",
        id_fields=("role_code",),
        label_fields=("role_label",),
        status_fields=("review_status",),
        reason_fields=("role_definition",),
        note_fields=("possible_source_fields", "public_claim_allowed", "credit_mapping"),
        priority_fn=lambda row: 70,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/event_ecology_audit.csv",
        domain="event_ecology",
        id_fields=("dimension",),
        label_fields=("dimension",),
        status_fields=("review_status",),
        reason_fields=("interpretation",),
        note_fields=("observed_count", "total_count", "coverage_share", "review_action"),
        priority_fn=lambda row: 75,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/network_robustness_checks.csv",
        domain="network_robustness",
        id_fields=("check_id",),
        label_fields=("network_model",),
        status_fields=("review_status",),
        reason_fields=("forbidden_inference",),
        note_fields=("edge_types_included", "question_supported", "required_sensitivity_check", "current_edge_count"),
        priority_fn=lambda row: 80,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/inter_rater_reliability_plan.csv",
        domain="inter_rater_reliability",
        id_fields=("sample_id",),
        label_fields=("classification_layer",),
        status_fields=("review_status",),
        reason_fields=("minimum_pass_rule",),
        note_fields=("sample_rows", "primary_metric", "review_action"),
        priority_fn=lambda row: 85,
    )
    add_csv_rows(
        rows,
        source_file="analytics_output/fair_reuse_maturity_audit.csv",
        domain="fair_reuse_maturity",
        id_fields=("fair_id",),
        label_fields=("criterion",),
        status_fields=("review_status",),
        reason_fields=("action",),
        note_fields=("principle", "evidence_path", "evidence_status"),
        priority_fn=lambda row: 90,
    )


def add_data_quality_rows(rows: list[dict[str, str]]) -> None:
    path = ROOT / "analytics_output" / "data_quality_report.json"
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    samples = report.get("samples") or {}
    for sample_name, sample_rows in samples.items():
        for idx, row in enumerate(sample_rows, start=1):
            maybe_add(
                rows,
                {
                    "domain": "data_quality",
                    "priority": 20,
                    "source_file": "analytics_output/data_quality_report.json",
                    "source_row": idx,
                    "record_id": first(row, "presentation_id", "person_id", "id"),
                    "label": first(row, "title", "scholar", "name"),
                    "status": "review",
                    "reason": sample_name,
                    "evidence_url": "",
                    "reviewer": "",
                    "checked_at": "",
                    "note": json.dumps(row, ensure_ascii=False, sort_keys=True),
                },
            )


def write_outputs(rows: list[dict[str, str]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)

    by_domain: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for row in rows:
        by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + 1
        by_source[row["source_file"]] = by_source.get(row["source_file"], 0) + 1
    summary = {
        "schema_version": "1.0.0",
        "total_open_review_items": len(rows),
        "by_domain": dict(sorted(by_domain.items())),
        "by_source_file": dict(sorted(by_source.items())),
    }
    with OUT_JSON.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    rows = build_rows()
    write_outputs(rows)
    print(f"Wrote {len(rows)} human review items to {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
