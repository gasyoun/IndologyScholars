#!/usr/bin/env python3
"""H2573: rebuild both comparison packages into a temp dir and compare them,
byte for byte, against the committed ones — WITHOUT touching the committed
packages (``freeze`` refuses to overwrite: VERIFICATION R13, snapshots are
never overwritten or merged, and that guard is correct).

Why this is the right probe. The committed payload files are LF (git stores LF
per ``.gitattributes``), but the committed ``manifest.json`` records sha256 and
byte counts computed over CRLF bytes, because ``freeze`` wrote them through
``Path.write_text`` in default text mode on Windows. So the payload is right and
the MANIFEST is wrong — the package never matched its own manifest on the day it
was committed.

If that diagnosis holds, a rebuild with the writers fixed must produce payload
files whose bytes are IDENTICAL to the committed ones, and differ only in the
two manifest files. Then the minimal honest repair is to regenerate the
manifests for the existing payload — not to republish the data.

Usage:
    python tools/rebuild_compare_snapshots_h2573.py            # compare only
    python tools/rebuild_compare_snapshots_h2573.py --apply    # + copy manifests
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from community_lenses import metrics, snapshot  # noqa: E402

MANIFESTS = ("manifest.json", "manifest.txt")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def main() -> int:
    apply = "--apply" in sys.argv
    conn, provenance = metrics.build_inputs()
    exit_code = 0

    with tempfile.TemporaryDirectory(prefix="h2573-rebuild-") as tmp:
        root = Path(tmp)
        for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
            committed = snapshot.SNAPSHOT_ROOT / name
            print(f"\n=== {name} ===")
            if not committed.is_dir():
                print("  committed package absent — nothing to compare")
                continue
            rebuilt = snapshot.freeze(
                name, conn, provenance, cutoff="2025-12-31", root=root,
                created_at="1970-01-01T00:00:00Z",
            )
            old, new = relative_files(committed), relative_files(rebuilt)
            only_old = sorted(set(old) - set(new))
            only_new = sorted(set(new) - set(old))
            payload_diff, manifest_diff, same = [], [], 0
            for rel in sorted(set(old) & set(new)):
                if sha(old[rel]) == sha(new[rel]):
                    same += 1
                elif rel in MANIFESTS:
                    manifest_diff.append(rel)
                else:
                    payload_diff.append(rel)

            print(f"  identical            : {same}")
            print(f"  manifest differs     : {len(manifest_diff)} {manifest_diff}")
            print(f"  PAYLOAD differs      : {len(payload_diff)}")
            for rel in payload_diff:
                print(f"      - {rel} ({old[rel].stat().st_size} -> "
                      f"{new[rel].stat().st_size} bytes)")
            if only_old:
                print(f"  only in committed    : {only_old}")
            if only_new:
                print(f"  only in rebuild      : {only_new}")

            if payload_diff or only_old or only_new:
                print("  VERDICT: payload itself differs — a manifest-only "
                      "repair is NOT sufficient; do not --apply.")
                exit_code = 1
                continue
            print("  VERDICT: payload byte-identical; only the manifests were "
                  "wrong (CRLF hashes over LF bytes).")

            if apply:
                for rel in MANIFESTS:
                    if rel in new:
                        shutil.copyfile(new[rel], committed / rel)
                        print(f"  applied: {rel}")
                errors = snapshot.verify_snapshot(committed)
                print(f"  verify_snapshot after apply: {len(errors)} error(s)")
                for err in errors[:5]:
                    print(f"    - {err}")
                if errors:
                    exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
