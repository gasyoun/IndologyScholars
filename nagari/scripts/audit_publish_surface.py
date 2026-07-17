"""Audit what the generated nagari artifacts would expose if published.

The nagari archive is built from a *closed* Google Group: 2 333 third-party
members joined a members-only venue, so every publication step needs evidence,
not assurances. This script produces that evidence. It is read-only.

It answers three questions:

1. Does ``site/index.html`` leak any real email address? The page is meant to
   redact all of them; it is the one artifact cleared for publication.
2. Does the Markdown mirror leak addresses? The mirror carries full message
   bodies and is a different exposure class than the page. As of 17-07-2026 it
   holds 1 290 distinct third-party addresses across 42 421 occurrences, which
   is why it stays git-ignored until ``export_md.py`` redacts the way
   ``page.py`` already does.
3. Are any attachment *blobs* on disk? ``ingest.py`` records attachment metadata
   only and never extracts the 2 030 attachments (367 book-like files, whose
   rights status was never triaged). This verifies that guarantee still holds.

Usage::

    python nagari/scripts/audit_publish_surface.py

Exits non-zero if the page leaks an address, so it can gate a publish step.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "index.html"
MD = ROOT / "md"
DATA = ROOT / "data"

# Deliberately permissive: over-reporting a candidate beats missing one.
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Not third-party PII: the list's own address and the archive owner's.
ALLOW = {
    "nagari@googlegroups.com",
    "gasyoun@ya.ru",
    "rusamskrtam@gmail.com",
}

BLOB_SUFFIXES = {".pdf", ".djvu", ".doc", ".docx", ".zip", ".rar", ".epub", ".jpg", ".png"}


def scan_emails(text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for m in RE_EMAIL.finditer(text):
        addr = m.group(0).lower()
        if addr in ALLOW:
            continue
        found[addr] = found.get(addr, 0) + 1
    return found


def main() -> int:
    rc = 0
    print("=" * 68)
    print("nagari publish-surface audit")
    print("=" * 68)

    if not PAGE.exists():
        print("[page] MISSING:", PAGE)
        print("       run: python nagari/scripts/run_pipeline.py")
        return 1
    text = PAGE.read_text(encoding="utf-8", errors="replace")
    print("[page] index.html: {:,} chars".format(len(text)))
    leaks = scan_emails(text)
    if leaks:
        rc = 1
        print("[page] *** {} distinct third-party address(es) LEAKED ***".format(len(leaks)))
        for addr, n in sorted(leaks.items(), key=lambda kv: -kv[1])[:20]:
            print("        {}  x{}".format(addr, n))
    else:
        print("[page] OK - no third-party addresses found (redaction holds)")

    if MD.exists():
        files = list(MD.rglob("*.md"))
        total = sum(p.stat().st_size for p in files)
        print("[md ] {:,} files, {:.1f} MB (full message bodies)".format(len(files), total / 1048576))
        md_leaks: dict[str, int] = {}
        for p in files:
            for addr, n in scan_emails(p.read_text(encoding="utf-8", errors="replace")).items():
                md_leaks[addr] = md_leaks.get(addr, 0) + n
        if md_leaks:
            hits = sum(md_leaks.values())
            print("[md ] {:,} distinct third-party address(es), {:,} occurrences".format(len(md_leaks), hits))
            print("       -> NOT redacted; publishing the mirror would expose these")
        else:
            print("[md ] no third-party addresses found")
    else:
        print("[md ] absent (not built, or already pruned)")

    blobs = []
    for base in (DATA, MD, ROOT / "site"):
        if base.exists():
            blobs += [p for p in base.rglob("*") if p.suffix.lower() in BLOB_SUFFIXES]
    if blobs:
        size = sum(p.stat().st_size for p in blobs)
        print("[blob] {:,} attachment blob(s) on disk, {:.1f} MB".format(len(blobs), size / 1048576))
        print("       -> ingest is metadata-only; investigate before publishing")
    else:
        print("[blob] OK - no attachment blobs extracted (metadata-only, as designed)")

    print("=" * 68)
    print("VERDICT:", "LEAK - do not publish the page as-is" if rc else "page redaction holds")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
