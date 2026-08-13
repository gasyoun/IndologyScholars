#!/usr/bin/env python3
"""H2573 throwaway: locate the duplicate (corpus_id, source_record_id) in the
nagari adapter fixture that makes
``test_adapter_fixture_loads_and_validates_with_no_errors[nagari]`` fail with
``sqlite3.IntegrityError: UNIQUE constraint failed: record.corpus_id,
record.source_record_id``. Read-only. Delete once diagnosed.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from community_lenses.adapters import nagari  # noqa: E402


def main() -> int:
    fixture = nagari.build_fixture()
    records = fixture.get("records", [])
    print(f"records: {len(records)}")
    counts = Counter(r.get("source_record_id") for r in records)
    dups = [(k, v) for k, v in counts.items() if v > 1]
    print(f"duplicate source_record_ids: {len(dups)}")
    # Real record-dict field names (the earlier guess used schema names that
    # do not exist on these rows and printed None for everything).
    show = ("record_id", "source_record_id", "source_record_id_method",
            "container_id", "title_or_subject", "created_at", "body_locator",
            "is_partial_2026")
    for key, n in dups[:10]:
        print(f"\n--- {key!r} x{n} ---")
        for r in records:
            if r.get("source_record_id") == key:
                for f in show:
                    print(f"  {f:20} = {r.get(f)!r}")
                print("  ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
