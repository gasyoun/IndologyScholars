"""Build scientometrics and sociology-of-science guardrail artifacts."""
from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "analytics_output"


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def read_csv(path: str) -> list[dict[str, str]]:
    csv_path = ROOT / path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str, fields: list[str], rows: list[dict[str, object]]) -> None:
    output_path = ROOT / path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean(row.get(field)) for field in fields})


def int_value(value: object, default: int = 0) -> int:
    try:
        return int(float(clean(value) or default))
    except ValueError:
        return default


def float_value(value: object, default: float = 0.0) -> float:
    try:
        return float(clean(value) or default)
    except ValueError:
        return default


def share(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000"
    return f"{numerator / denominator:.3f}"


def source_anchors() -> dict[str, str]:
    return {
        "leiden": "https://leidenmanifesto.org/",
        "dora": "https://sfdora.org/read/",
        "coara": "https://www.coara.org/agreement/the-agreement-full-text/",
        "credit": "https://credit.niso.org/",
        "fair": "https://doi.org/10.1038/sdata.2016.18",
        "science_of_science": "https://doi.org/10.1126/science.aao0185",
        "openalex_disambiguation": "https://help.openalex.org/hc/en-us/articles/24347048891543-Author-disambiguation",
    }


def build_guardrail_register() -> list[dict[str, str]]:
    anchors = source_anchors()
    return [
        {
            "guardrail_id": "G01",
            "title": "Registry of Claims",
            "output_path": "analytics_output/scientometrics_claim_registry.csv",
            "review_status": "review",
            "why_it_matters": "Prevents descriptive conference metadata from being promoted into unsupported career rankings.",
            "next_human_action": "Approve each allowed claim family before using it in article prose or public captions.",
            "source_anchor": anchors["leiden"],
        },
        {
            "guardrail_id": "G02",
            "title": "Coverage Bias Audit",
            "output_path": "analytics_output/coverage_bias_audit.csv",
            "review_status": "review",
            "why_it_matters": "Makes source-index visibility a measured limitation rather than an implicit quality signal.",
            "next_human_action": "Inspect high-activity scholars missing from authority indexes before any visibility claim.",
            "source_anchor": anchors["dora"],
        },
        {
            "guardrail_id": "G03",
            "title": "Negative Evidence Log",
            "output_path": "analytics_output/negative_evidence_log.csv",
            "review_status": "review",
            "why_it_matters": "Records failed or rejected matches so future disambiguation work does not repeat the same false leads.",
            "next_human_action": "Confirm generated no-hit and rejected-filter rows as true negatives or reopen them.",
            "source_anchor": anchors["openalex_disambiguation"],
        },
        {
            "guardrail_id": "G04",
            "title": "Conference Role Taxonomy",
            "output_path": "analytics_output/conference_role_taxonomy.csv",
            "review_status": "review",
            "why_it_matters": "Separates presentation, organization, chairing, editorial, and memorial roles before assigning credit.",
            "next_human_action": "Map raw programme wording to role codes only when source text supports the role.",
            "source_anchor": anchors["credit"],
        },
        {
            "guardrail_id": "G05",
            "title": "Event Ecology Layer",
            "output_path": "analytics_output/event_ecology_audit.csv",
            "review_status": "review",
            "why_it_matters": "Treats conferences as institutions and infrastructures, not just containers for individual talks.",
            "next_human_action": "Prioritize missing chair, venue, organizer, and session metadata in source programmes.",
            "source_anchor": anchors["science_of_science"],
        },
        {
            "guardrail_id": "G06",
            "title": "Network Robustness Checks",
            "output_path": "analytics_output/network_robustness_checks.csv",
            "review_status": "review",
            "why_it_matters": "Keeps co-presence, co-presentation, topical, and institutional networks from being interpreted as the same relation.",
            "next_human_action": "Report only network conclusions that survive the stated sensitivity checks.",
            "source_anchor": anchors["science_of_science"],
        },
        {
            "guardrail_id": "G07",
            "title": "Inter-Rater Reliability Dashboard",
            "output_path": "analytics_output/inter_rater_reliability_plan.csv",
            "review_status": "review",
            "why_it_matters": "Turns theme and level coding from a black-box label set into an auditable human-in-the-loop protocol.",
            "next_human_action": "Double-code the planned sample and record disagreements before treating labels as analysis.",
            "source_anchor": anchors["leiden"],
        },
        {
            "guardrail_id": "G08",
            "title": "FAIR / Reuse Maturity Audit",
            "output_path": "analytics_output/fair_reuse_maturity_audit.csv",
            "review_status": "review",
            "why_it_matters": "Checks whether the dataset is findable, accessible, interoperable, and reusable enough for scholarly reuse.",
            "next_human_action": "Review any non-pass row before publishing a new release.",
            "source_anchor": anchors["fair"],
        },
    ]


def build_claim_registry() -> list[dict[str, str]]:
    rows = [
        (
            "CLM01",
            "participation_counts",
            "Scholar or series counts describe observed presentations in the indexed Zograf/Roerich archive.",
            "Observed conference archive only.",
            "Stable presentation IDs, source programme links, and rebuild validation.",
            "Do not infer scholarly importance, productivity, seniority, or career quality from raw counts.",
            "analytics_output/presentation_id_manifest.csv",
        ),
        (
            "CLM02",
            "institutional_structure",
            "Institutional statements may describe programme affiliations or verified affiliation spans.",
            "Programme metadata and manually verified trajectories only.",
            "Source-backed affiliation span or explicit programme affiliation text.",
            "Do not claim institutional dominance or complete employment history from city labels.",
            "curation/verified_affiliation_spans.csv",
        ),
        (
            "CLM03",
            "authority_visibility",
            "Authority-ID coverage may be reported as index visibility and disambiguation status.",
            "Local authority coverage audit.",
            "Per-source coverage counts and candidate review queues.",
            "Do not interpret absence from OpenAlex, RINC, Wikipedia, ORCID, Wikidata, or VIAF as low scholarly productivity.",
            "analytics_output/coverage_bias_audit.csv",
        ),
        (
            "CLM04",
            "topic_classification",
            "Theme and meso codes are title-derived navigation and hypothesis-support labels.",
            "Presentation titles and reviewed classification samples.",
            "Classification reliability packet, uncertainty queues, and manual overrides.",
            "Do not present a theme code as a full content analysis of the paper.",
            "analytics_output/classification_reliability_sample.csv",
        ),
        (
            "CLM05",
            "network_position",
            "Network measures describe positions in explicitly typed observed conference networks.",
            "Chosen edge model and observed archive years.",
            "Network edge definitions, robustness checks, and sensitivity note.",
            "Do not conflate co-presence, co-presentation, coauthorship, citation, mentorship, or intellectual influence.",
            "analytics_output/network_robustness_checks.csv",
        ),
        (
            "CLM06",
            "cohort_dynamics",
            "Cohort statements may describe first observed presentation, return, and absence inside the archive.",
            "Observed participation histories.",
            "Debut timing, cohort survival, and missingness caveats.",
            "Do not claim employment continuity, career exit, or disciplinary entry/exit without external evidence.",
            "analytics_output/cohort_survival.csv",
        ),
        (
            "CLM07",
            "video_visibility",
            "Video coverage may describe which talks have known public recordings.",
            "Mapped media records and playlist sources.",
            "Video list, mapping table, and source notes.",
            "Do not treat recording availability as a status, importance, or quality metric.",
            "analytics_output/video_presentation_mapping.csv",
        ),
        (
            "CLM08",
            "external_publications",
            "Publication or citation data may be added only as source-specific, field-aware signals.",
            "Matched external indexes with confidence and field/language caveats.",
            "Author disambiguation dossier and field-normalized indicators.",
            "Do not compare scholars, generations, or fields using raw works or raw citations.",
            "analytics_output/openalex_author_candidates.csv",
        ),
        (
            "CLM09",
            "event_ecology",
            "Conference infrastructure claims may describe sessions, venues, themes, and programme organization when source-backed.",
            "Event/session/venue metadata in parsed programmes.",
            "Event ecology audit and source snippets.",
            "Do not present the two conferences as the whole infrastructure of Russian Indology.",
            "analytics_output/event_ecology_audit.csv",
        ),
        (
            "CLM10",
            "conference_roles",
            "Role claims may distinguish presenter, chair, organizer, editor, invited speaker, or memorial subject when the programme says so.",
            "Raw programme role wording and role taxonomy mapping.",
            "Conference role taxonomy and source evidence.",
            "Do not assign credit-like roles from name appearance alone.",
            "analytics_output/conference_role_taxonomy.csv",
        ),
    ]
    return [
        {
            "claim_id": claim_id,
            "claim_family": family,
            "allowed_claim": allowed_claim,
            "allowed_scope": allowed_scope,
            "required_evidence": required_evidence,
            "forbidden_overclaim": forbidden_overclaim,
            "minimum_review_artifact": artifact,
            "review_status": "review",
        }
        for claim_id, family, allowed_claim, allowed_scope, required_evidence, forbidden_overclaim, artifact in rows
    ]


def build_coverage_bias_audit() -> list[dict[str, object]]:
    rows = read_csv("analytics_output/authority_coverage.csv")
    total = len(rows)
    high_activity_threshold = 5
    sources = [
        ("orcid", "ORCID", "has_orcid"),
        ("wikidata", "Wikidata", "has_wikidata"),
        ("viaf", "VIAF", "has_viaf"),
        ("openalex", "OpenAlex", "has_openalex"),
        ("wikipedia", "Wikipedia", "has_wikipedia"),
        ("rinc", "RINC/eLIBRARY", "has_rinc"),
        ("google_scholar", "Google Scholar", "has_google_scholar"),
        ("official_url", "Official URL", "has_official_url"),
        ("any_external_id", "Any external ID", "has_any_external_id"),
    ]
    audit_rows = []
    for source, label, field in sources:
        covered = sum(1 for row in rows if int_value(row.get(field)) > 0)
        high_missing = [
            row
            for row in rows
            if int_value(row.get("total_talks")) >= high_activity_threshold
            and int_value(row.get(field)) == 0
        ]
        audit_rows.append(
            {
                "source": source,
                "source_label": label,
                "covered_persons": covered,
                "total_persons": total,
                "coverage_share": share(covered, total),
                "high_activity_missing_persons": len(high_missing),
                "high_activity_threshold": high_activity_threshold,
                "interpretation": "Coverage is a source-index visibility signal, not a scholar quality signal.",
                "review_status": "review" if high_missing else "pass",
                "review_action": "Inspect high-activity missing scholars and record true negatives or verified identifiers.",
            }
        )
    return audit_rows


def build_negative_evidence_log() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    counter = 1

    def add(source_file: str, source_row: int, system: str, person_id: str, label: str, candidate: str, signal: str, reason: str, note: str = "") -> None:
        nonlocal counter
        rows.append(
            {
                "evidence_id": f"NEG_{counter:05d}",
                "source_file": source_file,
                "source_row": source_row,
                "source_system": system,
                "person_id": person_id,
                "label": label,
                "candidate_or_query": candidate,
                "negative_signal": signal,
                "reason": reason,
                "review_status": "review",
                "reviewer": "",
                "checked_at": "",
                "note": note,
            }
        )
        counter += 1

    for idx, row in enumerate(read_csv("analytics_output/rinc_lookup_queue.csv"), start=2):
        notes = clean(row.get("notes"))
        if "no_match" in notes or "rejected_filter" in notes:
            add(
                "analytics_output/rinc_lookup_queue.csv",
                idx,
                "RINC/eLIBRARY",
                clean(row.get("person_id")),
                clean(row.get("full_name_ru") or row.get("display_name")),
                clean(row.get("rinc_search_url")),
                notes.split(":", 1)[0],
                notes,
                "Generated lookup needs human confirmation as true negative or false rejection.",
            )

    for idx, row in enumerate(read_csv("analytics_output/wikipedia_authority_candidates.csv"), start=2):
        if clean(row.get("status")) == "no_hit":
            add(
                "analytics_output/wikipedia_authority_candidates.csv",
                idx,
                "Wikipedia",
                clean(row.get("person_id")),
                clean(row.get("name")),
                clean(row.get("candidate_url") or row.get("query")),
                "no_hit",
                "No candidate page found by the current query.",
                clean(row.get("snippet")),
            )

    for idx, row in enumerate(read_csv("analytics_output/openalex_author_candidates.csv"), start=2):
        if float_value(row.get("relevance_score")) <= 0:
            add(
                "analytics_output/openalex_author_candidates.csv",
                idx,
                "OpenAlex",
                clean(row.get("person_id")),
                clean(row.get("local_display_name") or row.get("local_latin_name")),
                clean(row.get("openalex_id") or row.get("query_string")),
                "zero_relevance_score",
                "OpenAlex candidate has zero local relevance score.",
                f"query={clean(row.get('query_string'))}; candidate={clean(row.get('openalex_name'))}; works={clean(row.get('works_count'))}",
            )

    return rows


def db_counts() -> dict[str, int]:
    db_path = ROOT / "conferences.db"
    if not db_path.exists():
        return {}
    con = sqlite3.connect(db_path)
    try:
        scalar = lambda sql: int(con.execute(sql).fetchone()[0] or 0)
        return {
            "events": scalar("select count(*) from event"),
            "events_with_theme": scalar("select count(*) from event where coalesce(theme_ru, theme_en, '') <> ''"),
            "events_with_format": scalar("select count(*) from event where coalesce(format, '') <> '' and format <> 'unspecified'"),
            "sessions": scalar("select count(*) from session"),
            "sessions_with_title": scalar("select count(*) from session where coalesce(session_title, '') <> ''"),
            "sessions_with_chair": scalar("select count(*) from session where coalesce(chair_text_raw, '') <> ''"),
            "event_day_venues": scalar("select count(*) from event_day_venue"),
            "event_day_venues_with_room": scalar("select count(*) from event_day_venue where coalesce(room_text_raw, '') <> ''"),
            "presentations": scalar("select count(*) from presentation"),
            "presentations_with_affiliation_text": scalar("select count(distinct presentation_id) from presentation_person where coalesce(affiliation_text_raw, '') <> ''"),
            "presentations_with_organization_id": scalar("select count(distinct presentation_id) from presentation_person where coalesce(organization_id, '') <> ''"),
            "presentations_with_media": scalar("select count(distinct attached_to_id) from media where attached_to_type = 'presentation'"),
        }
    finally:
        con.close()


def build_event_ecology_audit() -> list[dict[str, object]]:
    counts = db_counts()

    def row(dimension: str, observed_key: str, total_key: str, interpretation: str, review_action: str) -> dict[str, object]:
        observed = counts.get(observed_key, 0)
        total = counts.get(total_key, 0)
        coverage = float(share(observed, total))
        return {
            "dimension": dimension,
            "observed_count": observed,
            "total_count": total,
            "coverage_share": f"{coverage:.3f}",
            "evidence_source": "conferences.db",
            "interpretation": interpretation,
            "review_status": "review" if coverage < 0.8 else "pass",
            "review_action": review_action,
        }

    return [
        row("event_theme", "events_with_theme", "events", "Conference themes are available only when programme metadata exposes them.", "Check programme headers for missing event themes."),
        row("event_format", "events_with_format", "events", "Format labels document online/offline/hybrid context when explicit.", "Review format fields before making digital-turn claims."),
        row("session_title", "sessions_with_title", "sessions", "Session titles are an event-ecology layer, not topical proof by themselves.", "Recover missing session titles from source programmes where possible."),
        row("session_chair", "sessions_with_chair", "sessions", "Chair metadata supports role sociology only after source-backed extraction.", "Manually extract chair strings where programme layout preserves them."),
        row("venue_room", "event_day_venues_with_room", "event_day_venues", "Room/venue detail helps describe conference infrastructure.", "Check weak venue rows against source snippets."),
        row("raw_affiliation_text", "presentations_with_affiliation_text", "presentations", "Raw affiliations are source strings and may be incomplete or inconsistent.", "Normalize only source-backed affiliation strings."),
        row("organization_normalization", "presentations_with_organization_id", "presentations", "Organization IDs are stricter than raw affiliation strings.", "Do not use organization networks as institutional productivity until coverage improves."),
        row("presentation_media", "presentations_with_media", "presentations", "Media coverage is preservation visibility, not status.", "Keep video availability separate from quality or importance claims."),
    ]


def build_conference_role_taxonomy() -> list[dict[str, str]]:
    rows = [
        ("presenter", "Presenter", "Person listed as delivering a presentation.", "presentation_person.role, programme speaker line", "Observed presentation participation.", "Investigation", "pass"),
        ("co_presenter", "Co-presenter", "Additional person listed on the same presentation.", "author_order, shared presentation_id", "Observed co-presentation only.", "Investigation", "pass"),
        ("session_chair", "Session chair", "Person named as chair, moderator, or presiding participant for a session.", "session.chair_text_raw", "Session stewardship when source-backed.", "Supervision", "needs_source_mapping"),
        ("organizer", "Organizer", "Person or organization named as an event organizer.", "programme header, source snippet", "Event organization when explicit.", "Project administration", "needs_source_mapping"),
        ("programme_committee", "Programme committee", "Person named as programme or organizing committee member.", "programme header/list", "Committee membership when explicit.", "Project administration", "needs_source_mapping"),
        ("invited_speaker", "Invited speaker", "Person labelled invited, plenary, keynote, or guest speaker.", "session title, programme label", "Invited role when explicit.", "Investigation", "needs_source_mapping"),
        ("editor_compiler", "Editor/compiler", "Person credited for published proceedings, programme, or source compilation.", "bibliographic note, programme footer", "Editorial contribution when explicit.", "Writing/review/editing", "needs_source_mapping"),
        ("memorial_subject", "Memorial/session subject", "Person who is the object of a memorial, jubilee, or dedicated session.", "session title, event theme", "Commemorative focus, not participation.", "Resources", "needs_source_mapping"),
        ("discussant", "Discussant/respondent", "Person named as discussant, respondent, or commentator.", "session notes, programme label", "Discussant role when explicit.", "Validation", "needs_source_mapping"),
    ]
    return [
        {
            "role_code": code,
            "role_label": label,
            "role_definition": definition,
            "possible_source_fields": source_fields,
            "public_claim_allowed": claim,
            "credit_mapping": credit,
            "review_status": status,
            "notes": "Inspired by CRediT-style role transparency, but scoped to conference programme evidence.",
        }
        for code, label, definition, source_fields, claim, credit, status in rows
    ]


def build_network_robustness_checks() -> list[dict[str, object]]:
    edges = read_csv("analytics_output/network_edges.csv")
    nodes = read_csv("analytics_output/network_nodes.csv")
    edge_counts = Counter(row.get("edge_type") for row in edges)
    node_counts = Counter(row.get("node_type") for row in nodes)
    person_series: dict[str, set[str]] = defaultdict(set)
    for row in edges:
        if row.get("edge_type") == "person_event" and clean(row.get("source")).startswith("person:"):
            person_series[clean(row.get("source"))].add(clean(row.get("series")))
    bridge_people = sum(1 for series in person_series.values() if len(series) > 1)

    specs = [
        ("NET01", "same_session_copresence", "person_person_same_session", "person-person", "Who appears in the same session?", "Compare with co-presentation and person-event models.", "Do not call same-session co-presence collaboration."),
        ("NET02", "same_presentation", "person_person_copresentation", "person-person", "Who appears on the same presentation record?", "Compare with same-session co-presence.", "Do not infer coauthorship beyond the programme line."),
        ("NET03", "person_event_bipartite", "person_event", "person-event", "Who participates in which conference years?", "Check series-specific and combined projections.", "Do not infer complete career history."),
        ("NET04", "person_theme_bipartite", "person_theme", "person-theme", "Which broad title-derived themes attach to observed participants?", "Repeat after uncertain theme review.", "Do not infer full research specialization."),
        ("NET05", "person_organization_bipartite", "person_organization", "person-organization", "Which source-backed organizations appear with participants?", "Compare raw affiliation and verified span coverage.", "Do not infer complete employment or institutional dominance."),
        ("NET06", "organization_theme_bipartite", "organization_theme", "organization-theme", "Which organizations appear with broad title-derived themes?", "Suppress or caveat when organization coverage is sparse.", "Do not claim institutional research profiles."),
        ("NET07", "series_bridge", "person_event", "person-series", "Who bridges Zograf and Roerich observed participation?", "Report bridge count alongside denominator and missingness.", "Do not infer disciplinary centrality from bridging alone."),
        ("NET08", "multi_layer_comparison", "all", "multi-layer", "Which findings survive edge-type choice?", "Recompute conclusions across all typed edge layers.", "Do not mix edge semantics in one undifferentiated network."),
    ]
    rows = []
    for check_id, model, edge_type, node_scope, question, sensitivity, forbidden in specs:
        current_edges = len(edges) if edge_type == "all" else edge_counts.get(edge_type, 0)
        rows.append(
            {
                "check_id": check_id,
                "network_model": model,
                "edge_types_included": edge_type,
                "node_scope": node_scope,
                "question_supported": question,
                "required_sensitivity_check": sensitivity,
                "current_edge_count": current_edges,
                "current_node_count": node_counts.get("person", 0) if "person" in node_scope else len(nodes),
                "review_status": "review",
                "forbidden_inference": forbidden,
                "note": f"series_bridge_people={bridge_people}" if check_id == "NET07" else "",
            }
        )
    return rows


def build_inter_rater_reliability_plan() -> list[dict[str, object]]:
    sample_rows = read_csv("analytics_output/classification_reliability_sample.csv")
    total = len(sample_rows)
    queued = sum(1 for row in sample_rows if row.get("review_status") == "queued_for_manual_review")
    overrides = sum(1 for row in sample_rows if row.get("review_status") == "manual_override")
    layers = [
        ("IRR01", "theme_l1", "Cohen kappa or Krippendorff alpha", "alpha >= 0.67 or publish disagreement table"),
        ("IRR02", "period_l2", "Cohen kappa or Krippendorff alpha", "alpha >= 0.67 or downgrade period claims"),
        ("IRR03", "gumilyov_level", "weighted kappa", "weighted kappa >= 0.67 or treat as exploratory"),
        ("IRR04", "meso_codes", "Jaccard overlap plus adjudication notes", "mean overlap >= 0.60 or publish as navigation only"),
        ("IRR05", "spacetime_inference", "binary agreement on place/time inference", "agreement >= 0.80 before aggregate claims"),
        ("IRR06", "identity_disambiguation", "two-reviewer adjudication log", "all high-impact merges require agreement or escalation"),
    ]
    return [
        {
            "sample_id": sample_id,
            "classification_layer": layer,
            "sample_file": "analytics_output/classification_reliability_sample.csv",
            "sample_rows": total,
            "queued_rows": queued,
            "manual_override_rows": overrides,
            "primary_metric": metric,
            "minimum_pass_rule": pass_rule,
            "current_status": "planned_double_code",
            "review_action": "Assign two human reviewers, record labels, adjudicate disagreements, then publish metric and caveat.",
            "review_status": "review",
        }
        for sample_id, layer, metric, pass_rule in layers
    ]


def build_fair_reuse_maturity_audit() -> list[dict[str, str]]:
    checks = [
        ("FAIR01", "F", "Stable local identifiers are exported.", "analytics_output/presentation_id_manifest.csv"),
        ("FAIR02", "F", "Machine-readable dataset metadata exists.", "datapackage.json"),
        ("FAIR03", "A", "Public download/documentation page exists.", "download-data.html"),
        ("FAIR04", "A", "Citation metadata exists.", "CITATION.cff"),
        ("FAIR05", "I", "Typed network exports use explicit schemas.", "analytics_output/network_edges.csv"),
        ("FAIR06", "I", "CSV field meanings are documented.", "data_dictionary.md"),
        ("FAIR07", "R", "Reuse rights are documented.", "docs/reuse-rights.md"),
        ("FAIR08", "R", "Field provenance sidecars exist.", "analytics_output/field_provenance_authority.csv"),
        ("FAIR09", "R", "Known limitations are public.", "known-limitations.html"),
        ("FAIR10", "R", "Scientometrics guardrails are documented.", "docs/scientometrics-sociology.md"),
    ]
    rows = []
    for fair_id, principle, criterion, evidence_path in checks:
        exists = (ROOT / evidence_path).exists()
        rows.append(
            {
                "fair_id": fair_id,
                "principle": principle,
                "criterion": criterion,
                "evidence_path": evidence_path,
                "evidence_status": "present" if exists else "missing",
                "review_status": "pass" if exists else "review",
                "action": "Keep current evidence current across releases." if exists else "Create or restore this evidence before publication.",
            }
        )
    return rows


def write_outputs() -> dict[str, object]:
    guardrails = build_guardrail_register()
    claim_registry = build_claim_registry()
    coverage = build_coverage_bias_audit()
    negatives = build_negative_evidence_log()
    roles = build_conference_role_taxonomy()
    ecology = build_event_ecology_audit()
    network = build_network_robustness_checks()
    inter_rater = build_inter_rater_reliability_plan()
    fair = build_fair_reuse_maturity_audit()

    write_csv(
        "analytics_output/scientometrics_guardrails.csv",
        ["guardrail_id", "title", "output_path", "review_status", "why_it_matters", "next_human_action", "source_anchor"],
        guardrails,
    )
    write_csv(
        "analytics_output/scientometrics_claim_registry.csv",
        ["claim_id", "claim_family", "allowed_claim", "allowed_scope", "required_evidence", "forbidden_overclaim", "minimum_review_artifact", "review_status"],
        claim_registry,
    )
    write_csv(
        "analytics_output/coverage_bias_audit.csv",
        ["source", "source_label", "covered_persons", "total_persons", "coverage_share", "high_activity_missing_persons", "high_activity_threshold", "interpretation", "review_status", "review_action"],
        coverage,
    )
    write_csv(
        "analytics_output/negative_evidence_log.csv",
        ["evidence_id", "source_file", "source_row", "source_system", "person_id", "label", "candidate_or_query", "negative_signal", "reason", "review_status", "reviewer", "checked_at", "note"],
        negatives,
    )
    write_csv(
        "analytics_output/conference_role_taxonomy.csv",
        ["role_code", "role_label", "role_definition", "possible_source_fields", "public_claim_allowed", "credit_mapping", "review_status", "notes"],
        roles,
    )
    write_csv(
        "analytics_output/event_ecology_audit.csv",
        ["dimension", "observed_count", "total_count", "coverage_share", "evidence_source", "interpretation", "review_status", "review_action"],
        ecology,
    )
    write_csv(
        "analytics_output/network_robustness_checks.csv",
        ["check_id", "network_model", "edge_types_included", "node_scope", "question_supported", "required_sensitivity_check", "current_edge_count", "current_node_count", "review_status", "forbidden_inference", "note"],
        network,
    )
    write_csv(
        "analytics_output/inter_rater_reliability_plan.csv",
        ["sample_id", "classification_layer", "sample_file", "sample_rows", "queued_rows", "manual_override_rows", "primary_metric", "minimum_pass_rule", "current_status", "review_action", "review_status"],
        inter_rater,
    )
    write_csv(
        "analytics_output/fair_reuse_maturity_audit.csv",
        ["fair_id", "principle", "criterion", "evidence_path", "evidence_status", "review_status", "action"],
        fair,
    )

    summary = {
        "schema_version": "1.0.0",
        "guardrail_count": len(guardrails),
        "claim_registry_rows": len(claim_registry),
        "coverage_sources": len(coverage),
        "negative_evidence_rows": len(negatives),
        "conference_role_rows": len(roles),
        "event_ecology_rows": len(ecology),
        "network_robustness_rows": len(network),
        "inter_rater_rows": len(inter_rater),
        "fair_audit_rows": len(fair),
        "fair_non_pass_rows": sum(1 for row in fair if row["review_status"] != "pass"),
        "coverage_review_sources": sum(1 for row in coverage if row["review_status"] != "pass"),
        "outputs": [row["output_path"] for row in guardrails],
    }
    summary_path = OUT_DIR / "scientometrics_guardrails_summary.json"
    with summary_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> int:
    summary = write_outputs()
    print(
        "Wrote scientometrics guardrails: "
        f"{summary['guardrail_count']} guardrails, "
        f"{summary['claim_registry_rows']} claims, "
        f"{summary['negative_evidence_rows']} negative-evidence rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
