"""Run the whole nagari-archive pipeline end to end.

    python scripts/run_pipeline.py                 # ingest -> insights -> md -> page
    python scripts/run_pipeline.py --skip-ingest   # rebuild analyses/page from an existing DB
    python scripts/run_pipeline.py --skip-md       # skip the (large) Markdown mirror

All stages are stdlib-only. The raw Takeout dump is read from ``--dump`` (default:
the copy in the main IndologyScholars checkout) and never modified. Outputs land
under ``nagari/data/``, ``nagari/md/`` and ``nagari/site/`` — all git-ignored,
because they carry the closed list's names/bodies until a ``/publish-safety-check`` GO.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nagari_group_archive import ingest, insights, export_md, page  # noqa: E402

DEFAULT_DUMP = ingest.DEFAULT_DUMP
DB = ingest.DEFAULT_DB


def main(argv: list[str] | None = None) -> None:
    ingest.configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", type=Path, default=DEFAULT_DUMP)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--limit", type=int, default=None, help="ingest only first N messages")
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--skip-md", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    if not args.skip_ingest:
        print("[1/4] ingest mbox -> SQLite", flush=True)
        print("      ", ingest.build(args.dump, args.db, args.limit), flush=True)
    else:
        print("[1/4] ingest skipped", flush=True)

    print("[2/4] insights (4 analysis layers)", flush=True)
    print("      ", insights.run(args.db), flush=True)

    if not args.skip_md:
        print("[3/4] export Markdown mirror", flush=True)
        print("      ", export_md.export(args.db, export_md.DEFAULT_OUT, min_messages=1), flush=True)
    else:
        print("[3/4] md export skipped", flush=True)

    print("[4/4] render retrospective HTML", flush=True)
    print("      ", page.build(args.dump, page.DEFAULT_OUT), flush=True)

    print(f"pipeline done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
