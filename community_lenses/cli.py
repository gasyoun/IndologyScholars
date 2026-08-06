"""`python -m community_lenses.cli <command>` — the VERIFICATION entry points.

Every subcommand is a thin dispatcher over the modules that own the work
(`build`, `classify`, `identity`, `quotes`, `metrics`, `figures`, `report`,
`snapshot`); no logic lives here, so a CLI change can never make a gate say
something the library does not.

Exit code 0 = gate passed, 1 = gate failed. A failing gate always prints the
concrete rows that failed, never a bare "FAILED".
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import build as build_mod
from . import classify, figures, identity, metrics, quotes, report, snapshot, taxonomy

REPO_ROOT = Path(__file__).resolve().parents[1]


def _print_errors(label: str, errors: list[str], limit: int = 40) -> int:
    if errors:
        print(f"{label}: FAILED ({len(errors)})")
        for error in errors[:limit]:
            print(f"  - {error}")
        if len(errors) > limit:
            print(f"  … {len(errors) - limit} more")
        return 1
    print(f"{label}: PASSED")
    return 0


def _tables(rebuild: bool = False):
    if rebuild:
        conn, provenance = metrics.build_inputs()
        return metrics.build_tables(conn, provenance), conn, provenance
    return {name: metrics.read_table(name) for name in metrics.TABLE_NAMES}, None, {}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_validate_manifests(args) -> int:
    conn, _provenance = metrics.build_inputs()
    errors: list[str] = []
    rows = snapshot.source_manifest_rows(conn)
    required = ("snapshot_id", "corpus_id", "coverage_status", "source_version",
                "acquired_at", "source_sha256", "pipeline_commit", "schema_version",
                "codebook_version", "rights_basis")
    for row in rows:
        for field in required:
            if not str(row.get(field) or "").strip():
                errors.append(f"{row['corpus_id']}: missing manifest field {field}")
        if row["coverage_status"] == "mixed_snapshot":
            errors.append(f"{row['corpus_id']}: mixed_snapshot source may not enter a build")
    print(f"{len(rows)} source manifests inspected")
    for row in rows:
        print(f"  {row['corpus_id']:<12} {row['coverage_status']:<12} {row['snapshot_id']}")
    return _print_errors("V1 manifests", errors)


def cmd_validate_schema(args) -> int:
    conn, _ = metrics.build_inputs()
    return _print_errors("V2 schema", build_mod.validate_schema(conn))


def cmd_roundtrip_check(args) -> int:
    conn, provenance = metrics.build_inputs()
    errors = list(provenance.get("roundtrip_errors") or [])
    first = build_mod.canonical_json(conn)
    second = build_mod.canonical_json(conn)
    if first != second:
        errors.append("canonical serialization is not stable across two dumps")
    return _print_errors("V2 round-trip", errors)


def cmd_reconcile(args) -> int:
    conn, provenance = metrics.build_inputs()
    print("| lens | offered | duplicates dropped | loaded |")
    print("|---|---:|---:|---:|")
    errors: list[str] = []
    for entry in sorted(provenance.get("drop_reports", []), key=lambda r: r["corpus_id"]):
        loaded = conn.execute(
            "SELECT COUNT(*) FROM record WHERE corpus_id = ?", (entry["corpus_id"],)
        ).fetchone()[0]
        print(f"| {entry['corpus_id']} | {entry['records_total']} | "
              f"{entry['records_dropped_duplicate']} | {loaded} |")
        expected = entry["records_total"] - entry["records_dropped_duplicate"]
        if loaded != expected:
            errors.append(
                f"{entry['corpus_id']}: loaded {loaded} != offered-minus-duplicates {expected}"
            )
    return _print_errors("V3 reconciliation", errors)


def cmd_validate_cutoff(args) -> int:
    conn, _ = metrics.build_inputs()
    errors: list[str] = []
    for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
        rows, accounting = snapshot.select_records(conn, name, args.cutoff)
        errors.extend(snapshot.validate_cutoff(rows, name, args.cutoff))
        print(f"{name}: {accounting['included']} records "
              f"(excluded other-period {accounting['excluded_other_period']}, "
              f"undated {accounting['excluded_undated']})")
    return _print_errors(f"V4 temporal separation (cutoff {args.cutoff})", errors)


def cmd_crosswalk_report(args) -> int:
    summary = taxonomy.crosswalk_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return _print_errors("V5 crosswalk", taxonomy.validate_crosswalk())


def cmd_build_review_samples(args) -> int:
    conn, _ = metrics.build_inputs()
    sample = classify.build_review_sample(conn)
    classify.write_review_sample(sample)
    print(f"{len(sample)} sample rows -> {classify.SAMPLE_PATH.relative_to(REPO_ROOT)}")
    return 0


def cmd_identity_report(args) -> int:
    links = identity.load_reviewed_links()
    errors: list[str] = []
    try:
        identity.validate_reviewed_links(links)
    except identity.IdentityError as exc:  # pragma: no cover - defensive
        errors.append(str(exc))
    accepted = identity.accepted_links(links)
    ambiguous = [row for row in links if row.get("decision") == "ambiguous"]
    print(f"reviewed decisions: {len(links)} (accepted {len(accepted)}, ambiguous {len(ambiguous)})")
    for row in accepted:
        if not str(row.get("evidence_locator") or "").strip():
            errors.append(f"{row.get('name_as_source')}: accepted link with no evidence locator")
    return _print_errors("V7 identity", errors)


def cmd_validate_quotes(args) -> int:
    errors: list[str] = []
    rows = []
    if quotes.QUOTES_PATH.exists():
        import csv as _csv

        with quotes.QUOTES_PATH.open(encoding="utf-8", newline="") as handle:
            rows = list(_csv.DictReader(handle))
    for row in rows:
        if quotes.contact_data_present(row.get("quote_verbatim", "")):
            errors.append(f"{row['quote_id']}: contact data present in the quoted span")
        effective = quotes.effective_rights_status(row)
        if effective != row.get("rights_review_status"):
            errors.append(
                f"{row['quote_id']}: stored rights {row.get('rights_review_status')!r} != "
                f"mechanically effective {effective!r}"
            )
    exportable = quotes.exportable_rows(rows)
    print(f"registered quotes: {len(rows)}; exportable after the mechanical gate: {len(exportable)}")
    return _print_errors("V8 quotes", errors)


def cmd_validate_metrics(args) -> int:
    tables, _conn, _prov = _tables(rebuild=args.rebuild)
    errors = metrics.validate_metrics(tables) + metrics.validate_temporal_separation(tables)
    for name in metrics.TABLE_NAMES:
        print(f"  {name:<32} {len(tables[name]):>4} rows")
    return _print_errors("V9 metrics", errors)


def cmd_build(args) -> int:
    conn, provenance = metrics.build_inputs()
    tables = metrics.build_tables(conn, provenance)
    written = metrics.write_tables(tables)
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    errors = metrics.validate_metrics(tables)
    return _print_errors("V9 metrics", errors)


def cmd_figures(args) -> int:
    tables, _conn, _prov = _tables(rebuild=args.rebuild)
    written = figures.write_all(tables)
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    captions = json.loads(figures.CAPTIONS_JSON.read_text(encoding="utf-8"))
    return _print_errors("V10 figures", figures.validate_captions(captions, tables))


def cmd_report(args) -> int:
    return report.main()


def cmd_validate_claims(args) -> int:
    claims = report.load_claims() if report.LEDGER_PATH.exists() else report.build_claims()
    tables, _conn, _prov = _tables(rebuild=args.rebuild)
    print(f"{len(claims)} claims in the ledger")
    return _print_errors("V10 claims", report.validate_claims(claims, tables))


def cmd_freeze(args) -> int:
    conn, provenance = metrics.build_inputs()
    try:
        destination = snapshot.freeze(args.name, conn, provenance, cutoff=args.cutoff)
    except snapshot.SnapshotError as exc:
        print(f"freeze refused: {exc}")
        return 1
    print(f"froze {destination.relative_to(REPO_ROOT)}")
    return _print_errors("V11 snapshot", snapshot.verify_snapshot(destination))


def cmd_verify_snapshot(args) -> int:
    destination = Path(args.path)
    if not destination.is_absolute():
        destination = REPO_ROOT / destination
    return _print_errors(f"V11 {destination.name}", snapshot.verify_snapshot(destination))


def cmd_rebuild_check(args) -> int:
    """V11: rebuild into a temporary destination and compare content hashes."""
    conn, provenance = metrics.build_inputs()
    with tempfile.TemporaryDirectory(prefix="community-lenses-rebuild-") as tmp:
        root = Path(tmp)
        rebuilt = snapshot.freeze(args.name, conn, provenance, cutoff=args.cutoff, root=root)
        original = snapshot.SNAPSHOT_ROOT / args.name
        if not original.exists():
            print(f"no existing snapshot at {original} to compare against")
            return 1
        differences = snapshot.compare_snapshots(original, rebuilt)
    print(f"compared {args.name}: creation metadata exempt "
          f"({', '.join(snapshot.CREATION_METADATA_FIELDS)})")
    return _print_errors("V11 unchanged rebuild", differences)


COMMANDS = {
    "validate-manifests": (cmd_validate_manifests, "V1 — every source manifest is complete"),
    "validate-schema": (cmd_validate_schema, "V2 — schema/foreign-key integrity"),
    "roundtrip-check": (cmd_roundtrip_check, "V2 — deterministic serialization round-trip"),
    "reconcile": (cmd_reconcile, "V3 — adapter reconciliation table"),
    "validate-cutoff": (cmd_validate_cutoff, "V4 — temporal separation, zero leakage"),
    "crosswalk-report": (cmd_crosswalk_report, "V5 — crosswalk inventory and validation"),
    "build-review-samples": (cmd_build_review_samples, "V6 — deterministic review sample"),
    "identity-report": (cmd_identity_report, "V7 — reviewed identity evidence"),
    "validate-quotes": (cmd_validate_quotes, "V8 — quote context and rights gate"),
    "build": (cmd_build, "build and write the frozen metric tables"),
    "validate-metrics": (cmd_validate_metrics, "V9 — denominator discipline"),
    "figures": (cmd_figures, "V10 — regenerate the six figures from frozen tables"),
    "report": (cmd_report, "V10 — validity report + claims ledger"),
    "validate-claims": (cmd_validate_claims, "V10 — zero unlinked article claims"),
    "freeze": (cmd_freeze, "V11 — freeze one comparison package"),
    "verify-snapshot": (cmd_verify_snapshot, "V11 — verify a package's manifest hashes"),
    "rebuild-check": (cmd_rebuild_check, "V11 — unchanged rebuild is content-identical"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m community_lenses.cli",
        description="Verification gates for the five-lens community comparison (H1899).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, (_handler, help_text) in COMMANDS.items():
        sub = subparsers.add_parser(name, help=help_text)
        if name in ("validate-cutoff", "freeze", "rebuild-check"):
            sub.add_argument("--cutoff", default="2025-12-31")
        if name in ("freeze", "rebuild-check"):
            sub.add_argument("--name", default=snapshot.THROUGH_2025,
                             choices=[snapshot.THROUGH_2025, snapshot.PARTIAL_2026])
            sub.add_argument("--from", dest="from_date", default=None,
                             help="documented alias: --from 2026-01-01 is --name partial-2026")
        if name == "verify-snapshot":
            sub.add_argument("path")
        if name in ("validate-metrics", "figures", "validate-claims"):
            sub.add_argument("--rebuild", action="store_true",
                             help="rebuild the tables from source instead of reading the frozen CSVs")
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if getattr(args, "from_date", None) and args.from_date >= "2026-01-01":
        args.name = snapshot.PARTIAL_2026
    handler, _help = COMMANDS[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
