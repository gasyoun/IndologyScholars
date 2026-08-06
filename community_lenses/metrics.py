"""Denominator-aware metric tables for the five-lens comparison (H1899, Wave 1E).

Every row this module emits carries its own numerator, denominator,
denominator unit, period, missingness, coverage status, source snapshot and
calculation method+version — the VERIFICATION V9 contract. Nothing here ever
adds a talk, a message, a thread and a post into one "activity" total: each
lens keeps its native unit and its own denominator, and the only cross-lens
object is a *set of parallel rows*, never a sum.

The tables are the frozen input for `community_lenses.figures` and
`community_lenses.report`: figures are drawn from the CSVs, not from the live
database, so a figure can never quietly disagree with the numbers a reader can
check.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from . import classify, identity

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "tables"

METHOD_VERSION = "h1899-metrics-1.0.0"

# Period bins are NEVER re-derived here; they are the ARCHITECTURE contract
# centralised in classify.PERIOD_BINS.
PERIOD_BINS = classify.PERIOD_BINS
TREND_PERIODS = tuple(name for name, _lo, _hi in PERIOD_BINS if name != "2026-partial")
PARTIAL_PERIOD = "2026-partial"

LENSES = ("conferences", "nagari", "vk_ors", "indology_l", "bvp")

# Forum ORIENTATION — a corpus-selection premise about the forum, grounded in
# author expertise. It is NOT a nationality claim about any participant and
# never receives a p-value (VERIFICATION R7 / V10). Kept next to the metric
# rows so a figure cannot silently promote it to a measurement.
LENS_ORIENTATION = {
    "conferences": "russia_centred",
    "nagari": "russia_centred",
    "vk_ors": "russia_centred",
    "indology_l": "western_centred",
    "bvp": "india_centred",
}
ORIENTATION_EVIDENCE_CLASS = "expert_judgment"

# A lens whose coverage is one of these may not carry a population share.
NON_POPULATION_COVERAGE = ("pilot", "partial", "unavailable", "mixed_snapshot")

METRIC_COLUMNS = (
    "metric_id",
    "lens",
    "native_unit",
    "period",
    "numerator_name",
    "numerator",
    "denominator_name",
    "denominator",
    "denominator_unit",
    "value",
    "missingness",
    "coverage_status",
    "source_snapshot",
    "method",
    "method_version",
    "caveat",
)

TABLE_NAMES = (
    "lens_source_coverage",
    "activity_by_period",
    "intellectual_content_by_lens",
    "community_function_by_lens",
    "argument_level_by_lens",
    "person_overlap",
    "orientation_contrast",
)


class MetricError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Input build (reuses the upstream H1893–H1898 pipeline; nothing re-derived)
# ---------------------------------------------------------------------------

def build_inputs() -> tuple[sqlite3.Connection, dict]:
    """The frozen analytical input: adapters + crosswalk + pilot + reviewed links.

    Mirrors `classify.build_full_database()` but through
    `identity.build_reviewed_database()`, which is duplicate-safe (the full
    nagari.db's 2 repeated Message-IDs, IndologyScholars#169) and reports every
    dropped row instead of crashing.
    """
    conn, drop_reports = identity.build_reviewed_database()
    native_before = classify.native_assignment_snapshot(conn)
    crosswalk_inserted = classify.apply_crosswalk_assignments(conn)
    pilot_inserted = classify.run_argument_level_pilot(conn)
    roundtrip_errors = classify.verify_native_roundtrip(conn, native_before)
    links = identity.load_reviewed_links()
    identity.validate_reviewed_links(links)
    mentions_linked = identity.apply_reviewed_links(conn, links)
    provenance = {
        "drop_reports": drop_reports,
        "crosswalk_inserted": crosswalk_inserted,
        "pilot_inserted": pilot_inserted,
        "roundtrip_errors": roundtrip_errors,
        "reviewed_links": links,
        "mentions_linked": mentions_linked,
    }
    return conn, provenance


def lens_meta(conn: sqlite3.Connection) -> dict[str, dict]:
    """Per-lens native unit, coverage status, snapshot id and coverage dates."""
    meta: dict[str, dict] = {}
    for row in conn.execute(
        """SELECT c.corpus_id, c.native_unit, c.medium, c.rights_status,
                  s.snapshot_id, s.coverage_status, s.coverage_start,
                  s.coverage_end, s.cutoff_date, s.source_version
           FROM corpus c JOIN source_snapshot s ON s.corpus_id = c.corpus_id
           ORDER BY c.corpus_id"""
    ):
        meta[row["corpus_id"]] = dict(row)
    return meta


def _is_placeholder(meta_row: dict) -> bool:
    return meta_row["coverage_status"] == "unavailable"


def observable_lenses(meta: dict[str, dict]) -> tuple[str, ...]:
    """Lenses with real records; an `unavailable` lens is a GAP, never a zero."""
    return tuple(lens for lens in LENSES if lens in meta and not _is_placeholder(meta[lens]))


def _row(**kwargs) -> dict:
    row = {column: "" for column in METRIC_COLUMNS}
    row.update(kwargs)
    unknown = set(row) - set(METRIC_COLUMNS)
    if unknown:
        raise MetricError(f"unknown metric column(s): {sorted(unknown)}")
    return row


def _method_slug(method: str) -> str:
    """Stable, filename-safe short form of a method string for metric ids."""
    slug = "".join(ch if ch.isalnum() else "_" for ch in method.lower())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")[:48]


PILOT_CAVEAT = (
    "PILOT/PARTIAL coverage: within-lens composition only, no population share"
)


def _enforce_coverage_caveats(rows: list[dict]) -> list[dict]:
    """Any valued row on a pilot/partial lens must SAY it is not a population share.

    Applied centrally so a new table cannot forget it; `validate_metrics`
    checks the same invariant from the outside.
    """
    for row in rows:
        if (
            row["coverage_status"] in NON_POPULATION_COVERAGE
            and str(row["value"]).strip()
            and "no population" not in row["caveat"]
            and "non-comparable" not in row["caveat"]
            and "pilot" not in row["caveat"]
        ):
            row["caveat"] = f"{PILOT_CAVEAT} — {row['caveat']}" if row["caveat"] else PILOT_CAVEAT
    return rows


def _share(numerator: int, denominator: int) -> str:
    if not denominator:
        return ""
    return f"{numerator / denominator:.6f}"


def _record_counts(conn: sqlite3.Connection, lens: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM record WHERE corpus_id = ?", (lens,)
    ).fetchone()[0]


def _period_of(created_at: str | None) -> str:
    return classify.period_bin(created_at)


# ---------------------------------------------------------------------------
# Table 1 — source and coverage (the table every other table is read against)
# ---------------------------------------------------------------------------

def lens_source_coverage(conn: sqlite3.Connection, meta: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for lens in LENSES:
        if lens not in meta:
            continue
        info = meta[lens]
        placeholder = _is_placeholder(info)
        total = 0 if placeholder else _record_counts(conn, lens)
        undated = 0
        if not placeholder:
            undated = conn.execute(
                "SELECT COUNT(*) FROM record WHERE corpus_id = ? AND "
                "(created_at IS NULL OR created_at = '')",
                (lens,),
            ).fetchone()[0]
        rows.append(
            _row(
                metric_id=f"coverage.{lens}",
                lens=lens,
                native_unit=info["native_unit"],
                period=(
                    f"{info['coverage_start']}..{info['coverage_end']}"
                    if info["coverage_start"]
                    else "no_coverage"
                ),
                numerator_name="records_in_snapshot",
                numerator="" if placeholder else total,
                denominator_name="records_in_snapshot",
                denominator="" if placeholder else total,
                denominator_unit=info["native_unit"],
                value="" if placeholder else "1.000000",
                missingness=(
                    "source_unavailable_on_this_machine"
                    if placeholder
                    else f"undated_records={undated}"
                ),
                coverage_status=info["coverage_status"],
                source_snapshot=info["snapshot_id"],
                method="source_snapshot_manifest",
                method_version=METHOD_VERSION,
                caveat=(
                    "explicit evidence GAP — not a zero; no share, rate or trend "
                    "may be computed for this lens"
                    if placeholder
                    else (
                        "pilot/partial coverage: no population share may be claimed"
                        if info["coverage_status"] in NON_POPULATION_COVERAGE
                        else "complete for the source's own extent"
                    )
                ),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Table 2 — activity by native unit and period (never summed across lenses)
# ---------------------------------------------------------------------------

def activity_by_period(conn: sqlite3.Connection, meta: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for lens in observable_lenses(meta):
        info = meta[lens]
        counts: dict[str, int] = {name: 0 for name, _lo, _hi in PERIOD_BINS}
        undated = 0
        for record in conn.execute(
            "SELECT created_at FROM record WHERE corpus_id = ?", (lens,)
        ):
            created_at = record["created_at"]
            if not created_at:
                undated += 1
                continue
            counts[_period_of(created_at)] = counts.get(_period_of(created_at), 0) + 1
        # Denominator = this lens's own dated records, never a cross-lens total.
        dated_total = sum(counts.values())
        for period, _lo, _hi in PERIOD_BINS:
            rows.append(
                _row(
                    metric_id=f"activity.{lens}.{period}",
                    lens=lens,
                    native_unit=info["native_unit"],
                    period=period,
                    numerator_name=f"{info['native_unit']}s_in_period",
                    numerator=counts.get(period, 0),
                    denominator_name="dated_records_in_this_lens",
                    denominator=dated_total,
                    denominator_unit=info["native_unit"],
                    value=_share(counts.get(period, 0), dated_total),
                    missingness=f"undated_records={undated}",
                    coverage_status=info["coverage_status"],
                    source_snapshot=info["snapshot_id"],
                    method="record.created_at binned by classify.PERIOD_BINS",
                    method_version=METHOD_VERSION,
                    caveat=(
                        "2026 is PARTIAL: never comparable with a full-year rate"
                        if period == PARTIAL_PERIOD
                        else (
                            "pilot coverage: within-lens composition only, no population claim"
                            if info["coverage_status"] in NON_POPULATION_COVERAGE
                            else "within-lens composition; native unit is not comparable across lenses"
                        )
                    ),
                )
            )
    return rows


# ---------------------------------------------------------------------------
# Tables 3–5 — shared axes, each against ITS OWN classified denominator
# ---------------------------------------------------------------------------

def _axis_table(
    conn: sqlite3.Connection,
    meta: dict[str, dict],
    scheme_id: str,
    metric_prefix: str,
    method_filter: str | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for lens in observable_lenses(meta):
        info = meta[lens]
        query = (
            """SELECT ca.label_id, ca.method, COUNT(DISTINCT ca.record_id) AS n
               FROM classification_assignment ca
               JOIN record r ON r.record_id = ca.record_id
               WHERE r.corpus_id = ? AND ca.scheme_id = ?"""
        )
        params: list = [lens, scheme_id]
        if method_filter:
            query += " AND ca.method = ?"
            params.append(method_filter)
        query += " GROUP BY ca.label_id, ca.method ORDER BY ca.label_id, ca.method"
        counts = [dict(row) for row in conn.execute(query, params)]

        classified = conn.execute(
            "SELECT COUNT(DISTINCT ca.record_id) FROM classification_assignment ca "
            "JOIN record r ON r.record_id = ca.record_id "
            "WHERE r.corpus_id = ? AND ca.scheme_id = ?"
            + (" AND ca.method = ?" if method_filter else ""),
            params if method_filter else [lens, scheme_id],
        ).fetchone()[0]
        lens_records = _record_counts(conn, lens)

        if not counts:
            rows.append(
                _row(
                    metric_id=f"{metric_prefix}.{lens}.none",
                    lens=lens,
                    native_unit=info["native_unit"],
                    period="all",
                    numerator_name=f"{scheme_id}_labelled_records",
                    numerator=0,
                    denominator_name="records_with_this_axis_assigned",
                    denominator=0,
                    denominator_unit=info["native_unit"],
                    value="",
                    missingness=(
                        f"no {scheme_id} assignment exists for this lens "
                        f"({lens_records} records unclassified on this axis)"
                    ),
                    coverage_status=info["coverage_status"],
                    source_snapshot=info["snapshot_id"],
                    method="classification_assignment",
                    method_version=METHOD_VERSION,
                    caveat="axis GAP for this lens — suppress it from any comparison figure",
                )
            )
            continue

        for entry in counts:
            # The method belongs in the id: one label can legitimately arrive
            # from two different methods (e.g. conference Gumilev from the
            # deepseek pass and from the strict scale audit), and collapsing
            # them into one id would silently hide one of the two.
            rows.append(
                _row(
                    metric_id=f"{metric_prefix}.{lens}.{entry['label_id']}.{_method_slug(entry['method'])}",
                    lens=lens,
                    native_unit=info["native_unit"],
                    period="all",
                    numerator_name=f"records_labelled_{entry['label_id']}",
                    numerator=entry["n"],
                    denominator_name="records_with_this_axis_assigned",
                    denominator=classified,
                    denominator_unit=info["native_unit"],
                    value=_share(entry["n"], classified),
                    missingness=(
                        f"unclassified_on_this_axis={lens_records - classified}"
                    ),
                    coverage_status=info["coverage_status"],
                    source_snapshot=info["snapshot_id"],
                    method=entry["method"],
                    method_version=METHOD_VERSION,
                    caveat=(
                        "crosswalk-derived PROPOSAL (review_status=pending); "
                        "labels are additional assertions layered next to native ones"
                        if entry["method"] == classify.CROSSWALK_METHOD
                        else (
                            "deterministic ruleset PILOT, unreviewed: non-comparable "
                            "across lenses, no cross-lens distribution may be published"
                            if entry["method"] == classify.PILOT_METHOD
                            else "source-native accepted evidence"
                        )
                    ),
                )
            )
    return rows


def intellectual_content_by_lens(conn, meta) -> list[dict]:
    return _axis_table(conn, meta, "intellectual_content", "content")


def community_function_by_lens(conn, meta) -> list[dict]:
    return _axis_table(conn, meta, "community_function", "function")


def argument_level_by_lens(conn, meta) -> list[dict]:
    return _axis_table(conn, meta, "argument_level", "gumilev")


# ---------------------------------------------------------------------------
# Table 6 — verified cross-lens people (accepted links only)
# ---------------------------------------------------------------------------

def person_overlap(conn: sqlite3.Connection, meta: dict[str, dict], links: list[dict]) -> list[dict]:
    accepted = identity.accepted_links(links)
    accepted_persons = {row["person_id"] for row in accepted if row.get("person_id")}
    pending = [row for row in links if row.get("decision") == "ambiguous"]

    rows: list[dict] = []
    for lens in observable_lenses(meta):
        info = meta[lens]
        linked_persons = conn.execute(
            """SELECT COUNT(DISTINCT rn.person_id) FROM record_name rn
               JOIN record r ON r.record_id = rn.record_id
               WHERE r.corpus_id = ? AND rn.person_id IS NOT NULL""",
            (lens,),
        ).fetchone()[0]
        mentions = conn.execute(
            """SELECT COUNT(*) FROM record_name rn
               JOIN record r ON r.record_id = rn.record_id
               WHERE r.corpus_id = ? AND rn.person_id IS NOT NULL""",
            (lens,),
        ).fetchone()[0]
        # A reviewed link binds a NON-conference attestation to a canonical
        # conferences person_id, so the conference side of every accepted link
        # is the full accepted-person set, and each other lens contributes only
        # the persons attested in that lens.
        if lens == "conferences":
            cross_lens = len(accepted_persons)
        else:
            cross_lens = len(
                {
                    row["person_id"]
                    for row in accepted
                    if row.get("person_id") and row.get("corpus_id") == lens
                }
                & accepted_persons
            )
        rows.append(
            _row(
                metric_id=f"overlap.{lens}",
                lens=lens,
                native_unit=info["native_unit"],
                period="all",
                numerator_name="verified_cross_lens_persons_attested_in_this_lens",
                numerator=cross_lens,
                denominator_name="persons_linked_in_this_lens",
                denominator=linked_persons,
                denominator_unit="person",
                value=_share(cross_lens, linked_persons),
                missingness=(
                    f"ambiguous_candidates_excluded={len(pending)}; "
                    f"linked_mentions={mentions}"
                ),
                coverage_status=info["coverage_status"],
                source_snapshot=info["snapshot_id"],
                method="reviewed identity links (curation/community_person_links.csv)",
                method_version=identity.DECISION_VERSION,
                caveat=(
                    "accepted links only; ambiguous candidates are NEVER counted. "
                    "Cross-lens links derive from a closed group's membership and are "
                    "not exportable until the nagari rights gate is approved"
                ),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Table 7 — Russia / West / India orientation contrast (forum, not nationality)
# ---------------------------------------------------------------------------

def orientation_contrast(conn: sqlite3.Connection, meta: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for lens in LENSES:
        if lens not in meta:
            continue
        info = meta[lens]
        placeholder = _is_placeholder(info)
        total = 0 if placeholder else _record_counts(conn, lens)
        rows.append(
            _row(
                metric_id=f"orientation.{LENS_ORIENTATION[lens]}.{lens}",
                lens=lens,
                native_unit=info["native_unit"],
                period=(
                    f"{info['coverage_start']}..{info['coverage_end']}"
                    if info["coverage_start"]
                    else "no_coverage"
                ),
                numerator_name=f"observable_records_in_{LENS_ORIENTATION[lens]}_forum",
                numerator="" if placeholder else total,
                denominator_name="records_in_this_lens_snapshot",
                denominator="" if placeholder else total,
                denominator_unit=info["native_unit"],
                value="",
                missingness=(
                    "NO OBSERVATION — source unavailable; this orientation is an "
                    "evidence gap, not a measured zero"
                    if placeholder
                    else "none"
                ),
                coverage_status=info["coverage_status"],
                source_snapshot=info["snapshot_id"],
                method=f"corpus-selection premise ({ORIENTATION_EVIDENCE_CLASS})",
                method_version=METHOD_VERSION,
                caveat=(
                    "orientation describes the FORUM, not the nationality of any "
                    "participant, and is author expert judgment: it carries no "
                    "p-value and no representativeness claim about Russia, "
                    "'the West' or India"
                ),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Build / write / validate
# ---------------------------------------------------------------------------

def build_tables(conn: sqlite3.Connection, provenance: dict) -> dict[str, list[dict]]:
    meta = lens_meta(conn)
    links = provenance.get("reviewed_links") or identity.load_reviewed_links()
    tables = {
        "lens_source_coverage": lens_source_coverage(conn, meta),
        "activity_by_period": activity_by_period(conn, meta),
        "intellectual_content_by_lens": intellectual_content_by_lens(conn, meta),
        "community_function_by_lens": community_function_by_lens(conn, meta),
        "argument_level_by_lens": argument_level_by_lens(conn, meta),
        "person_overlap": person_overlap(conn, meta, links),
        "orientation_contrast": orientation_contrast(conn, meta),
    }
    return {name: _enforce_coverage_caveats(rows) for name, rows in tables.items()}


def write_tables(tables: dict[str, list[dict]], directory: Path = TABLES_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in TABLE_NAMES:
        rows = tables[name]
        path = directory / f"{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(METRIC_COLUMNS), lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        written.append(path)
    return written


def read_table(name: str, directory: Path = TABLES_DIR) -> list[dict]:
    path = directory / f"{name}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_metrics(tables: dict[str, list[dict]]) -> list[str]:
    """VERIFICATION V9. Empty return means every row is publishable as-is."""
    errors: list[str] = []
    seen_ids: set[str] = set()

    for name in TABLE_NAMES:
        if name not in tables:
            errors.append(f"missing metric table: {name}")
            continue
        for row in tables[name]:
            metric_id = row["metric_id"]
            if metric_id in seen_ids:
                errors.append(f"{name}: duplicate metric_id {metric_id!r}")
            seen_ids.add(metric_id)

            if not row["lens"]:
                errors.append(f"{name}:{metric_id}: no lens — a metric row may never be lens-less")
            if row["lens"] not in LENSES:
                errors.append(f"{name}:{metric_id}: unknown lens {row['lens']!r}")
            if not row["native_unit"]:
                errors.append(f"{name}:{metric_id}: no native unit")
            if not row["period"]:
                errors.append(f"{name}:{metric_id}: no period")
            if not row["denominator_name"] or not row["denominator_unit"]:
                errors.append(f"{name}:{metric_id}: denominator not named/united")
            if not row["source_snapshot"]:
                errors.append(f"{name}:{metric_id}: no source snapshot")
            if not row["method"] or not row["method_version"]:
                errors.append(f"{name}:{metric_id}: no method/version")
            if row["missingness"] == "":
                errors.append(f"{name}:{metric_id}: missingness not stated")

            # A value without a positive denominator is the V9 headline defect.
            if str(row["value"]).strip():
                denominator = str(row["denominator"]).strip()
                if not denominator or denominator == "0":
                    errors.append(
                        f"{name}:{metric_id}: value {row['value']!r} with no positive denominator"
                    )
                if row["coverage_status"] == "unavailable":
                    errors.append(
                        f"{name}:{metric_id}: an unavailable lens may not carry a value "
                        "(a gap is not a zero)"
                    )

            # Pilot/partial lenses may describe their own composition but never
            # a population share: the caveat must say so out loud.
            if (
                row["coverage_status"] in NON_POPULATION_COVERAGE
                and str(row["value"]).strip()
                and "no population" not in row["caveat"]
                and "non-comparable" not in row["caveat"]
                and "pilot" not in row["caveat"]
            ):
                errors.append(
                    f"{name}:{metric_id}: {row['coverage_status']} coverage with a value "
                    "and no pilot/no-population caveat"
                )

    # Prohibited combination: a single activity total across native units.
    activity_units = {row["denominator_unit"] for row in tables.get("activity_by_period", [])}
    for row in tables.get("activity_by_period", []):
        if row["denominator_name"] != "dated_records_in_this_lens":
            errors.append(
                f"activity_by_period:{row['metric_id']}: denominator is not lens-local "
                "(cross-unit activity totals are prohibited)"
            )
    if len(activity_units) < 2 and tables.get("activity_by_period"):
        # Not an error, but a silent single-unit table would hide the point of
        # the contract; recorded as a note-level check only when >1 lens exists.
        lenses = {row["lens"] for row in tables["activity_by_period"]}
        if len(lenses) > 1 and len(activity_units) == 1:
            pass  # legitimately identical native units (e.g. two message lenses)

    # Orientation rows must stay expert judgment and carry no computed value.
    for row in tables.get("orientation_contrast", []):
        if str(row["value"]).strip():
            errors.append(
                f"orientation_contrast:{row['metric_id']}: orientation rows carry no "
                "computed value (they are a corpus-selection premise, not a measurement)"
            )
        if ORIENTATION_EVIDENCE_CLASS not in row["method"]:
            errors.append(
                f"orientation_contrast:{row['metric_id']}: orientation must be marked "
                f"{ORIENTATION_EVIDENCE_CLASS}"
            )

    # Overlap must exclude pending/ambiguous candidates.
    for row in tables.get("person_overlap", []):
        if "ambiguous_candidates_excluded" not in row["missingness"]:
            errors.append(
                f"person_overlap:{row['metric_id']}: does not state how many ambiguous "
                "candidates were excluded"
            )
    return errors


def validate_temporal_separation(tables: dict[str, list[dict]], cutoff_year: int = 2025) -> list[str]:
    """VERIFICATION V4/R10: no 2026 material inside a through-2025 trend row."""
    errors: list[str] = []
    for row in tables.get("activity_by_period", []):
        if row["period"] == PARTIAL_PERIOD and "PARTIAL" not in row["caveat"]:
            errors.append(
                f"activity_by_period:{row['metric_id']}: 2026 row without a partial caveat"
            )
    return errors


def trend_rows(rows: list[dict]) -> list[dict]:
    """The through-2025 subset of an activity table (2026 dropped, never merged)."""
    return [row for row in rows if row["period"] in TREND_PERIODS]


def partial_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["period"] == PARTIAL_PERIOD]


def main() -> int:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    conn, provenance = build_inputs()
    tables = build_tables(conn, provenance)
    written = write_tables(tables)
    errors = validate_metrics(tables) + validate_temporal_separation(tables)
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT)} ({sum(1 for _ in read_table(path.stem))} rows)")
    if errors:
        print(f"\nV9 validation FAILED with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("\nV9 validation: PASSED (every row carries numerator, denominator, unit, "
          "period, missingness, snapshot, method+version)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
