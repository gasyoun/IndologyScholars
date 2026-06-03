"""Freeze a reproducible snapshot of the data underlying the PPV article.

Creates a timestamped directory article/snapshots/<date>/ containing:
  - conferences.db (SQLite, the full relational database)
  - site_data.json (master public dataset)
  - analytics_output/ (all CSV and JSON exports)
  - article/hypothesis_output/ (appendix G, null model, PPV numbers)
  - curation/ (verified trajectories, relationships)
  - authority_ids.json (external identifiers)
  - assets/data/geography.json (city aliases)
  - A manifest.txt listing every frozen file with SHA-256 checksum.

This directory is intended for DOI deposition via Zenodo/Figshare.
The snapshot is READ-ONLY — it copies data, never modifies it.

Usage:
  python tools/freeze_article_data.py
"""

import hashlib
import shutil
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = date.today().isoformat()
SNAPSHOT_DIR = ROOT / "article" / "snapshots" / TODAY

# Directories to copy in full (top-level contents only)
DIRS_TO_COPY = [
    "analytics_output",
    "article/hypothesis_output",
    "curation",
]

# Individual files to copy
FILES_TO_COPY = [
    "conferences.db",
    "site_data.json",
    "site_data_summary.json",
    "site_data_scholars.json",
    "site_data_timeline.json",
    "site_data_network.json",
    "site_data_timeline_1.json",
    "site_data_timeline_2.json",
    "authority_ids.json",
    "authority_ids.schema.json",
    "public_ids.json",
    "assets/data/geography.json",
    "data_dictionary.md",
    "datapackage.json",
    "CITATION.cff",
    "zograf-roerich-db.md",
    "search-index.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if SNAPSHOT_DIR.exists():
        print(f"Snapshot already exists: {SNAPSHOT_DIR}")
        resp = input("Overwrite? [y/N] ").strip().lower()
        if resp != "y":
            print("Aborted.")
            return
        shutil.rmtree(str(SNAPSHOT_DIR))

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_lines = [
        f"PPV Article Data Snapshot",
        f"Frozen: {datetime.now().isoformat(timespec='seconds')}",
        f"Repository: https://github.com/gasyoun/IndologyScholars",
        f"",
        f"{'='*60}",
        f"FILE MANIFEST (SHA-256 checksums)",
        f"{'='*60}",
        f"",
    ]

    # Copy directories
    for d in DIRS_TO_COPY:
        src = ROOT / d
        if not src.exists():
            print(f"  SKIP (missing): {d}/")
            continue
        dst = SNAPSHOT_DIR / d
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(str(f), str(dst / f.name))
                cs = sha256(f)
                size = f.stat().st_size
                rel = f"{d}/{f.name}"
                manifest_lines.append(f"  {cs}  {size:>10d}  {rel}")
                print(f"  copy: {rel}")

    # Copy individual files
    for f in FILES_TO_COPY:
        src = ROOT / f
        if not src.exists():
            print(f"  SKIP (missing): {f}")
            continue
        dst = SNAPSHOT_DIR / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        cs = sha256(src)
        size = src.stat().st_size
        manifest_lines.append(f"  {cs}  {size:>10d}  {f}")
        print(f"  copy: {f}")

    # Write manifest
    manifest_path = SNAPSHOT_DIR / "manifest.txt"
    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")
    print(f"\nManifest: {manifest_path}")
    print(f"\nSnapshot frozen at: {SNAPSHOT_DIR}")
    print(f"To create a DOI, upload this directory to Zenodo or Figshare.")
    print(f"Then update CITATION.cff with the DOI.")


if __name__ == "__main__":
    main()
