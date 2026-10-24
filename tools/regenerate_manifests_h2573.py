#!/usr/bin/env python3
"""H2573: regenerate manifest.json and manifest.txt for BOTH committed comparison
packages in-place, hashing their actual committed payload (LF as stored by git),
NOT by rebuilding from source — which would silently bless a payload that was
frozen from a different conferences.db acquisition 4 days earlier.

The committed packages' payload files are correct; only the manifests hashed
CRLF over LF bytes (Path.write_text in default text mode on Windows). The
honest repair is to rehash what's there.

Usage:
    python tools/regenerate_manifests_h2573.py            # dry-run
    python tools/regenerate_manifests_h2573.py --apply    # write
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from community_lenses import snapshot  # noqa: E402

CREATION_METADATA_FIELDS = ("created_at",)


def regenerate_manifest(destination: Path, apply: bool) -> int:
    old_json = destination / "manifest.json"
    old_txt = destination / "manifest.txt"
    if not old_json.is_file():
        print(f"  no manifest.json — skip")
        return 1

    old = json.loads(old_json.read_text(encoding="utf-8"))
    files = [
        {
            "path": path.relative_to(destination).as_posix(),
            "sha256": snapshot.file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(
            (p for p in destination.rglob("*") if p.is_file()
             and p.name not in ("manifest.json", "manifest.txt")),
            key=lambda p: p.relative_to(destination).as_posix(),
        )
    ]

    manifest = {
        "snapshot_name": old["snapshot_name"],
        "snapshot_version": old["snapshot_version"],
        "schema_version": old["schema_version"],
        "crosswalk_version": old["crosswalk_version"],
        "cutoff_date": old["cutoff_date"],
        "temporal_rule": old["temporal_rule"],
        "record_accounting": old["record_accounting"],
        "pipeline": old["pipeline"],
        "creation_metadata_fields": list(CREATION_METADATA_FIELDS),
        "created_at": old["created_at"],
        "files": files,
    }

    changed_files = sum(
        1 for new, old_f in zip(files, old.get("files", []))
        if new["sha256"] != old_f.get("sha256")
    )
    print(f"  files: {len(files)} · changed sha256: {changed_files}")

    if apply:
        old_json.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )

        acc = old["record_accounting"]
        lines = [
            f"# Comparison snapshot `{old['snapshot_name']}` — manifest",
            "",
            "_Created: 06-08-2026 · Last updated: 11-08-2026_",
            "",
            f"Frozen by `community_lenses/snapshot.py` ({old['snapshot_version']}); "
            f"cutoff `{old['cutoff_date']}`.",
            f"Creation metadata (the only field allowed to vary across identical rebuilds): "
            f"`created_at = {old['created_at']}`.",
            "",
            "| Records included | Excluded (other period) | Excluded (undated) |",
            "|---:|---:|---:|",
            f"| {acc['included']} | {acc['excluded_other_period']} | "
            f"{acc['excluded_undated']} |",
            "",
            "| File | Bytes | SHA-256 |",
            "|---|---:|---|",
        ]
        for entry in files:
            lines.append(f"| `{entry['path']}` | {entry['bytes']} | `{entry['sha256']}` |")
        lines += ["", f"Total files: {len(files)}.", "", "_Dr. Mārcis Gasūns_"]
        old_txt.write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"  wrote manifest.json + manifest.txt")

    return 0


def main() -> int:
    apply = "--apply" in sys.argv
    print(f"mode: {'APPLY' if apply else 'DRY-RUN'}\n")

    for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
        destination = snapshot.SNAPSHOT_ROOT / name
        print(f"=== {name} ===")
        if not destination.is_dir():
            print(f"  package absent")
            continue
        regenerate_manifest(destination, apply)

    if apply:
        print("\nverifying both packages after manifest regeneration:")
        for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
            destination = snapshot.SNAPSHOT_ROOT / name
            if not destination.is_dir():
                continue
            errors = snapshot.verify_snapshot(destination)
            print(f"  {name}: {len(errors)} error(s)")
            for err in errors[:3]:
                print(f"    - {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
