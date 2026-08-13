#!/usr/bin/env python3
"""H2573: characterise the THREE payload files that differ between the committed
comparison packages and a fresh rebuild, plus the one report present only in the
rebuild.

This matters because it decides the repair. If the payload differences are
CRLF-only, the packages are internally consistent modulo line endings and a
manifest regeneration is honest. If any difference is real content, then the
committed packages were frozen from a DIFFERENT host/source state, and
regenerating their manifests would silently bless data that was never
re-verified — in that case the fix belongs to the writers only, and the stale
packages need a human decision about re-publication.

``records.csv`` and ``source_manifests.csv`` are suspicious precisely because
their byte counts are IDENTICAL while their hashes differ — that rules out
CRLF (which always changes length) and points at same-length content churn.
Read-only.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from community_lenses import metrics, snapshot  # noqa: E402

TARGETS = ("records.csv", "source_manifests.csv",
           "reports/bvp_source_assessment.md")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def report_line_diff(old: bytes, new: bytes, label: str, limit: int = 6) -> None:
    old_lines = old.decode("utf-8", "replace").splitlines()
    new_lines = new.decode("utf-8", "replace").splitlines()
    print(f"    lines: committed={len(old_lines)} rebuilt={len(new_lines)}")
    shown = 0
    for i, (a, b) in enumerate(zip(old_lines, new_lines), start=1):
        if a != b:
            print(f"    L{i} committed: {a[:150]}")
            print(f"    L{i} rebuilt  : {b[:150]}")
            shown += 1
            if shown >= limit:
                print("    ... (truncated)")
                break
    if shown == 0 and len(old_lines) != len(new_lines):
        extra = new_lines[len(old_lines):] or old_lines[len(new_lines):]
        print(f"    identical prefix; {len(extra)} extra line(s), first: "
              f"{extra[0][:150] if extra else ''}")
    elif shown == 0:
        print(f"    no line-level difference -> line-ending only "
              f"({label}: CRLF vs LF)")


def main() -> int:
    conn, provenance = metrics.build_inputs()
    with tempfile.TemporaryDirectory(prefix="h2573-diff-") as tmp:
        root = Path(tmp)
        for name in (snapshot.THROUGH_2025, snapshot.PARTIAL_2026):
            committed = snapshot.SNAPSHOT_ROOT / name
            print(f"\n=== {name} ===")
            rebuilt = snapshot.freeze(
                name, conn, provenance, cutoff="2025-12-31", root=root,
                created_at="1970-01-01T00:00:00Z",
            )
            for rel in TARGETS:
                old_p, new_p = committed / rel, rebuilt / rel
                if not (old_p.is_file() and new_p.is_file()):
                    print(f"  {rel}: missing on one side")
                    continue
                old, new = old_p.read_bytes(), new_p.read_bytes()
                print(f"\n  --- {rel} ---")
                print(f"    bytes: committed={len(old)} rebuilt={len(new)}")
                crlf_equal = (old.replace(b"\r\n", b"\n")
                              == new.replace(b"\r\n", b"\n"))
                print(f"    equal after folding CRLF->LF on both: {crlf_equal}")
                if crlf_equal:
                    print("    => LINE-ENDING ONLY")
                    continue
                report_line_diff(old, new, rel)
            extra = rebuilt / "reports" / "H1899_completion_note.md"
            if extra.is_file():
                text = extra.read_text(encoding="utf-8", errors="replace")
                print(f"\n  --- reports/H1899_completion_note.md "
                      f"(rebuild only, {len(text)} chars) ---")
                for line in text.splitlines()[:8]:
                    print(f"    {line[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
