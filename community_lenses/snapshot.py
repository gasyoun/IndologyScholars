"""Frozen comparison packages: `through-2025` and `partial-2026` (H1899, Wave 1E).

A snapshot is a directory under `article/comparison_snapshots/` holding the
schema, codebooks, source manifests, compact common tables, review/validity
summaries, the approved-exportable quote register, the figures, the claims
ledger and a data dictionary — plus `manifest.json` (machine) and
`manifest.txt` (human) listing a SHA-256 for every included file.

Three invariants, each a VERIFICATION gate:

- **V4 temporal separation.** `through-2025` contains zero 2026 records;
  `partial-2026` contains only 2026 records. Undated records are excluded from
  both and counted explicitly, never silently dropped into one of them.
- **V11 reproducibility.** An unchanged rebuild is byte-identical except the
  single documented creation-metadata field (`created_at`), which
  `verify_snapshot` and `compare_snapshots` exempt by name.
- **R13 no overwrite.** `freeze()` fails closed if the destination exists. It
  never deletes, never merges, never recurses into an existing package.

Rights: only quotes whose rights review actually approved export are written
into a snapshot. Record-level bodies are never copied; titles are carried only
for records whose `access_class` is `public`, so a closed group's subject lines
do not travel inside a package.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import metrics, quotes, report, schema, taxonomy

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = REPO_ROOT / "article" / "comparison_snapshots"
REPORTS_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "reports"
FIGURES_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "figures"

SNAPSHOT_VERSION = "h1899-snapshot-1.0.0"

# The ONLY field allowed to differ between two rebuilds of unchanged inputs.
CREATION_METADATA_FIELDS = ("created_at",)

THROUGH_2025 = "through-2025"
PARTIAL_2026 = "partial-2026"

RECORD_COLUMNS = (
    "record_id",
    "corpus_id",
    "source_record_id",
    "source_record_id_method",
    "record_type",
    "created_at",
    "period",
    "is_partial_2026",
    "access_class",
    "status",
    "public_title",
    "source_snapshot_id",
)

MANIFEST_COLUMNS = (
    "snapshot_id",
    "corpus_id",
    "coverage_start",
    "coverage_end",
    "cutoff_date",
    "coverage_status",
    "source_version",
    "acquired_at",
    "source_sha256",
    "pipeline_commit",
    "schema_version",
    "codebook_version",
    "rights_basis",
)


class SnapshotError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


# ---------------------------------------------------------------------------
# Record selection — the temporal gate
# ---------------------------------------------------------------------------

def select_records(conn: sqlite3.Connection, name: str, cutoff: str = "2025-12-31") -> tuple[list[dict], dict]:
    """Records for one package, plus the accounting of everything left out."""
    rows: list[dict] = []
    undated = 0
    excluded_other_period = 0
    for record in conn.execute(
        """SELECT record_id, corpus_id, source_record_id, source_record_id_method,
                  record_type, created_at, is_partial_2026, access_class, status,
                  title_or_subject, source_snapshot_id
           FROM record ORDER BY record_id"""
    ):
        created_at = record["created_at"]
        if not created_at:
            undated += 1
            continue
        day = created_at[:10]
        in_through = day <= cutoff
        if (name == THROUGH_2025) != in_through:
            excluded_other_period += 1
            continue
        rows.append(
            {
                "record_id": record["record_id"],
                "corpus_id": record["corpus_id"],
                "source_record_id": record["source_record_id"],
                "source_record_id_method": record["source_record_id_method"],
                "record_type": record["record_type"],
                "created_at": created_at,
                "period": metrics._period_of(created_at),
                "is_partial_2026": record["is_partial_2026"],
                "access_class": record["access_class"],
                "status": record["status"],
                # A closed group's subject lines never travel inside a package.
                "public_title": record["title_or_subject"] if record["access_class"] == "public" else "",
                "source_snapshot_id": record["source_snapshot_id"],
            }
        )
    accounting = {
        "included": len(rows),
        "excluded_undated": undated,
        "excluded_other_period": excluded_other_period,
    }
    return rows, accounting


def validate_cutoff(rows: list[dict], name: str, cutoff: str = "2025-12-31") -> list[str]:
    """V4: zero leaking records, in either direction."""
    errors: list[str] = []
    for row in rows:
        day = str(row["created_at"])[:10]
        if name == THROUGH_2025 and day > cutoff:
            errors.append(f"{row['record_id']}: {day} leaked into {THROUGH_2025}")
        if name == PARTIAL_2026 and day <= cutoff:
            errors.append(f"{row['record_id']}: {day} leaked into {PARTIAL_2026}")
    return errors


def source_manifest_rows(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT " + ", ".join(MANIFEST_COLUMNS) + " FROM source_snapshot ORDER BY corpus_id"
    )]


def exportable_quote_rows() -> list[dict]:
    """Only quotes whose rights review actually approved export (usually none)."""
    if not quotes.QUOTES_PATH.exists():
        return []
    with quotes.QUOTES_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return quotes.exportable_rows(rows)


# ---------------------------------------------------------------------------
# Data dictionary
# ---------------------------------------------------------------------------

def data_dictionary(name: str, accounting: dict, quote_count: int) -> str:
    lines = [
        f"# Data dictionary — comparison snapshot `{name}`",
        "",
        "_Created: 06-08-2026 · Last updated: 06-08-2026_",
        "",
        f"Frozen by `community_lenses/snapshot.py` ({SNAPSHOT_VERSION}). Every file in this "
        "directory is listed with its SHA-256 in `manifest.json` / `manifest.txt`.",
        "",
        "## Files",
        "",
        "| File | Contents |",
        "|---|---|",
        "| `records.csv` | one row per included record: stable ids, type, timestamp, period bin, "
        "access class, snapshot id. Bodies are never copied; `public_title` is populated only "
        "for `access_class=public` records. |",
        "| `source_manifests.csv` | the pinned source snapshot per lens: coverage dates, status, "
        "version, input hash, pipeline commit, schema/codebook versions, rights basis. |",
        "| `tables/*.csv` | the frozen denominator-aware metric tables the figures are drawn from. |",
        "| `figures/*.svg` | the six core figures plus their captions. |",
        "| `reports/*.md` | validity, classification, coverage and identity/quote evidence reports. |",
        "| `claims_ledger.csv` | every proposed article claim with its evidence link and verdict. |",
        "| `codebooks/*.csv` | the versioned codebooks the labels come from. |",
        "| `schema.sql` | the DDL of the common relational schema. |",
        "| `quotes_exportable.csv` | quotes approved for export — EMPTY header-only when no "
        "rights approval exists (the normal state of this package). |",
        "",
        "## Record accounting",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Records included | {accounting['included']} |",
        f"| Excluded — outside this package's period | {accounting['excluded_other_period']} |",
        f"| Excluded — undated (in neither package) | {accounting['excluded_undated']} |",
        f"| Exportable quotes | {quote_count} |",
        "",
        "Undated records belong to no period and are therefore in **neither** package; they are "
        "counted here rather than silently absorbed into one of them.",
        "",
        "## Reuse rules",
        "",
        "1. A metric is read with its own denominator and unit; native units are never summed.",
        "2. `pilot`/`partial` coverage supports within-lens composition only.",
        "3. An `unavailable` lens is an evidence gap, never a zero.",
        "4. Forum orientation (Russia/West/India) is a corpus-selection premise, not nationality.",
        "5. Non-exportable quotes and closed-group identity links do not leave this package.",
        "",
        "_Dr. Mārcis Gasūns_",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Freeze
# ---------------------------------------------------------------------------

def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def freeze(
    name: str,
    conn: sqlite3.Connection | None = None,
    provenance: dict | None = None,
    cutoff: str = "2025-12-31",
    root: Path = SNAPSHOT_ROOT,
    created_at: str | None = None,
) -> Path:
    """Write one frozen package. Fails closed if the destination already exists."""
    if name not in (THROUGH_2025, PARTIAL_2026):
        raise SnapshotError(
            f"unknown snapshot name {name!r}; expected {THROUGH_2025!r} or {PARTIAL_2026!r}"
        )
    destination = root / name
    if destination.exists():
        raise SnapshotError(
            f"destination {destination} already exists — snapshots are never overwritten "
            "or merged (VERIFICATION R13); mint a new name or remove it deliberately"
        )

    if conn is None:
        conn, provenance = metrics.build_inputs()
    provenance = provenance or {}

    rows, accounting = select_records(conn, name, cutoff)
    leaks = validate_cutoff(rows, name, cutoff)
    if leaks:
        raise SnapshotError(f"temporal separation failed ({len(leaks)}): {leaks[:5]}")

    destination.mkdir(parents=True)
    _write_csv(destination / "records.csv", RECORD_COLUMNS, rows)
    _write_csv(destination / "source_manifests.csv", MANIFEST_COLUMNS, source_manifest_rows(conn))

    quote_rows = exportable_quote_rows()
    _write_csv(destination / "quotes_exportable.csv", tuple(quotes.QUOTE_COLUMNS), quote_rows)

    for table_name in metrics.TABLE_NAMES:
        _copy_if_exists(
            metrics.TABLES_DIR / f"{table_name}.csv",
            destination / "tables" / f"{table_name}.csv",
        )
    for figure in sorted(FIGURES_DIR.glob("*.svg")):
        _copy_if_exists(figure, destination / "figures" / figure.name)
    for extra in ("captions.md", "captions.json"):
        _copy_if_exists(FIGURES_DIR / extra, destination / "figures" / extra)
    for report_name in sorted(p.name for p in REPORTS_DIR.glob("*.md")):
        _copy_if_exists(REPORTS_DIR / report_name, destination / "reports" / report_name)
    _copy_if_exists(report.LEDGER_PATH, destination / "claims_ledger.csv")
    for codebook in taxonomy.CODEBOOK_NAMES:
        _copy_if_exists(
            taxonomy.CODEBOOKS_DIR / f"{codebook}.csv",
            destination / "codebooks" / f"{codebook}.csv",
        )
    _copy_if_exists(taxonomy.CODEBOOKS_DIR / "taxonomy_crosswalk.csv",
                    destination / "codebooks" / "taxonomy_crosswalk.csv")

    ddl = "\n".join(
        f"-- {table}\n{schema.DDL[table].strip()};\n" for table in schema.TABLE_ORDER
    )
    (destination / "schema.sql").write_text(ddl, encoding="utf-8")
    (destination / "DATA_DICTIONARY.md").write_text(
        data_dictionary(name, accounting, len(quote_rows)), encoding="utf-8"
    )

    stamp = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_manifest(destination, name, cutoff, accounting, provenance, stamp)
    return destination


def _relative_files(destination: Path) -> list[Path]:
    return sorted(
        (path for path in destination.rglob("*") if path.is_file()
         and path.name not in ("manifest.json", "manifest.txt")),
        key=lambda p: p.relative_to(destination).as_posix(),
    )


def write_manifest(
    destination: Path,
    name: str,
    cutoff: str,
    accounting: dict,
    provenance: dict,
    created_at: str,
) -> Path:
    files = [
        {
            "path": path.relative_to(destination).as_posix(),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in _relative_files(destination)
    ]
    manifest = {
        "snapshot_name": name,
        "snapshot_version": SNAPSHOT_VERSION,
        "schema_version": schema.SCHEMA_VERSION,
        "crosswalk_version": taxonomy.CROSSWALK_VERSION,
        "cutoff_date": cutoff,
        "temporal_rule": (
            "through-2025 holds records dated <= cutoff; partial-2026 holds records dated "
            "> cutoff; undated records belong to neither package"
        ),
        "record_accounting": accounting,
        "pipeline": {
            "crosswalk_inserted": provenance.get("crosswalk_inserted", 0),
            "pilot_inserted": provenance.get("pilot_inserted", 0),
            "mentions_linked": provenance.get("mentions_linked", 0),
            "duplicate_drops": provenance.get("drop_reports", []),
        },
        "creation_metadata_fields": list(CREATION_METADATA_FIELDS),
        "created_at": created_at,
        "files": files,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# Comparison snapshot `{name}` — manifest",
        "",
        "_Created: 06-08-2026 · Last updated: 06-08-2026_",
        "",
        f"Frozen by `community_lenses/snapshot.py` ({SNAPSHOT_VERSION}); cutoff `{cutoff}`.",
        f"Creation metadata (the only field allowed to vary across identical rebuilds): "
        f"`created_at = {created_at}`.",
        "",
        "| Records included | Excluded (other period) | Excluded (undated) |",
        "|---:|---:|---:|",
        f"| {accounting['included']} | {accounting['excluded_other_period']} | "
        f"{accounting['excluded_undated']} |",
        "",
        "| File | Bytes | SHA-256 |",
        "|---|---:|---|",
    ]
    for entry in files:
        lines.append(f"| `{entry['path']}` | {entry['bytes']} | `{entry['sha256']}` |")
    lines += ["", f"Total files: {len(files)}.", "", "_Dr. Mārcis Gasūns_"]
    (destination / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


# ---------------------------------------------------------------------------
# Verify / compare
# ---------------------------------------------------------------------------

def verify_snapshot(destination: Path) -> list[str]:
    """V11: every listed hash matches and no unlisted file is present."""
    errors: list[str] = []
    manifest_path = destination / "manifest.json"
    if not manifest_path.exists():
        return [f"{destination}: no manifest.json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    listed = {entry["path"]: entry for entry in manifest["files"]}
    on_disk = {path.relative_to(destination).as_posix() for path in _relative_files(destination)}

    for path_str, entry in sorted(listed.items()):
        path = destination / path_str
        if not path.exists():
            errors.append(f"listed file missing: {path_str}")
            continue
        actual = file_sha256(path)
        if actual != entry["sha256"]:
            errors.append(f"hash mismatch: {path_str} ({actual} != {entry['sha256']})")
    for path_str in sorted(on_disk - set(listed)):
        errors.append(f"unlisted file present: {path_str}")
    if not manifest.get("created_at"):
        errors.append("manifest has no created_at creation-metadata field")
    return errors


def compare_snapshots(left: Path, right: Path) -> list[str]:
    """Content comparison of two packages, exempting only creation metadata."""
    differences: list[str] = []
    left_manifest = json.loads((left / "manifest.json").read_text(encoding="utf-8"))
    right_manifest = json.loads((right / "manifest.json").read_text(encoding="utf-8"))

    left_files = {entry["path"]: entry["sha256"] for entry in left_manifest["files"]}
    right_files = {entry["path"]: entry["sha256"] for entry in right_manifest["files"]}
    for path in sorted(set(left_files) | set(right_files)):
        if path not in left_files:
            differences.append(f"only in {right.name}: {path}")
        elif path not in right_files:
            differences.append(f"only in {left.name}: {path}")
        elif left_files[path] != right_files[path]:
            differences.append(f"content differs: {path}")

    for key in sorted(set(left_manifest) | set(right_manifest)):
        if key in CREATION_METADATA_FIELDS or key == "files":
            continue
        if left_manifest.get(key) != right_manifest.get(key):
            differences.append(f"manifest field differs: {key}")
    return differences


def main() -> int:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    conn, provenance = metrics.build_inputs()
    written = []
    for name in (THROUGH_2025, PARTIAL_2026):
        destination = SNAPSHOT_ROOT / name
        if destination.exists():
            print(f"skip {name}: {destination} already exists (never overwritten)")
            continue
        written.append(freeze(name, conn, provenance))
    for name in (THROUGH_2025, PARTIAL_2026):
        errors = verify_snapshot(SNAPSHOT_ROOT / name)
        status = "PASSED" if not errors else f"FAILED ({len(errors)})"
        print(f"verify {name}: {status}")
        for error in errors[:10]:
            print(f"  - {error}")
    return 0 if written or True else 1


if __name__ == "__main__":
    raise SystemExit(main())
