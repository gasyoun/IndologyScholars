#!/usr/bin/env python3
"""H2573 throwaway: test whether the committed comparison-snapshot hash
mismatches are a Windows CRLF-checkout artifact rather than a corrupt commit.

ALL 26 files in BOTH packages mismatch while ``git status`` is clean, and the
codebook hashes are identical across the two packages on both sides of each
comparison. That uniformity points at a systematic byte-level transform applied
between commit and checkout — i.e. git converting LF to CRLF on this clone —
not at 52 independently wrong hashes.

Discriminating probe: for each mismatching file, hash (a) the bytes on disk,
(b) the committed blob bytes from ``git cat-file``, and (c) the on-disk bytes
with CRLF folded to LF. If (b) or (c) equals the manifest's expected hash, the
package is internally consistent and only the checkout is transformed.
Read-only.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
PACKAGES = ("through-2025", "partial-2026")
REL_ROOT = "article/comparison_snapshots"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_bytes(rel: str) -> bytes | None:
    # No encoding= here on purpose: this must compare RAW BYTES, so the blob
    # is read in binary and never decoded.
    proc = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{rel}"],
        cwd=REPO, capture_output=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def main() -> int:
    verdicts: dict[str, int] = {}
    for name in PACKAGES:
        pkg = REPO / REL_ROOT / name
        manifest_path = pkg / "manifest.json"
        if not manifest_path.is_file():
            print(f"{name}: no manifest.json")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.get("files") or []
        print(f"\n=== {name} ({len(files)} files in manifest) ===")
        for entry in sorted(files, key=lambda e: e["path"]):
            rel_in_pkg = entry["path"]
            expected = entry.get("sha256")
            expected_bytes = entry.get("bytes")
            on_disk_path = pkg / rel_in_pkg
            if not on_disk_path.is_file():
                verdicts["missing"] = verdicts.get("missing", 0) + 1
                continue
            raw = on_disk_path.read_bytes()
            if sha(raw) == expected:
                verdicts["disk-matches"] = verdicts.get("disk-matches", 0) + 1
                continue
            blob = blob_bytes(f"{REL_ROOT}/{name}/{rel_in_pkg}")
            folded = raw.replace(b"\r\n", b"\n")
            # Reverse direction: the manifest may have been computed on CRLF
            # bytes that git then normalised to LF in the committed blob, in
            # which case re-inflating LF->CRLF reproduces the recorded hash.
            inflated = folded.replace(b"\n", b"\r\n")
            if blob is not None and sha(blob) == expected:
                verdict = "blob-matches (CRLF checkout artifact)"
            elif sha(folded) == expected:
                verdict = "lf-folded-matches (CRLF checkout artifact)"
            elif sha(inflated) == expected:
                verdict = "crlf-inflated-matches (manifest hashed CRLF, git stored LF)"
            else:
                verdict = "GENUINELY DIFFERENT"
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
            if verdict == "GENUINELY DIFFERENT":
                # The recorded byte count is an independent discriminator: a
                # CRLF-inflated file is LARGER on disk than the manifest says
                # by exactly the number of newlines.
                print(f"  [{verdict}] {rel_in_pkg}: "
                      f"disk={len(raw)} folded={len(folded)} "
                      f"manifest_bytes={expected_bytes}")

    print("\n--- verdict tally ---")
    for k, v in sorted(verdicts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:44} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
