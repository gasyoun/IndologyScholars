#!/usr/bin/env python3
"""H2573 throwaway: characterise the committed comparison-snapshot integrity
failure behind ``test_the_live_packages_verify_if_they_exist``.

``verify_snapshot`` recomputes each file's sha256 and compares it to the
package's own ``manifest.json``. Both the manifest and the files it covers were
committed by the SAME commit (26dad1db4, #183), so a mismatch means the commit
published a package whose manifest never matched its payload — an internal
inconsistency in a committed artifact, not local drift. This prints the exact
per-file verdicts so the claim is measured, not inferred. Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from community_lenses import snapshot  # noqa: E402


def main() -> int:
    for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
        dest = snapshot.SNAPSHOT_ROOT / name
        print(f"\n=== {name} ===")
        print(f"path   : {dest}")
        if not dest.exists():
            print("       : ABSENT (test would skip)")
            continue
        errors = snapshot.verify_snapshot(dest)
        print(f"errors : {len(errors)}")
        for err in errors:
            print(f"  - {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
