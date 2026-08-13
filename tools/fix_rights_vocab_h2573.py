#!/usr/bin/env python3
"""H2573 one-shot: normalise off-vocabulary rights_review_status in the quote register.

The H1899 curation layer (commit 26dad1db4, 07-08-2026) wrote the token
``approved`` into ``rights_review_status``, but the rights gate landed a day
earlier (56a4820ce, 06-08-2026) with the closed vocabulary

    RIGHTS_STATES = ("non_exportable", "exportable_approved", "pending_review")

so ``community_lenses.quotes.effective_rights_status`` raises
``QuoteError: unknown rights_review_status 'approved'`` and 14 snapshot /
identity / quote tests fail. All three affected rows carry a COMPLETE approval
record (approver + scope + date + permitted use).

**What this script does and deliberately does not do.** It rewrites ONLY the
``rights_review_status`` column, and only where the value is the
off-vocabulary token ``approved``, mapping every such row onto
``non_exportable`` — the fail-closed member of the accepted vocabulary.

It does NOT promote any row to ``exportable_approved``, even though all three
carry a complete approval record. Commit 26dad1db4 reads as lifting nagari's
closed-corpus designation, but
``tests/test_community_lenses_quotes.py`` and
``tests/test_community_lenses_identity.py`` still assert that closed-list rows
are UNCONDITIONALLY non-exportable, and #183 did not update them. That
contradiction is a rights decision, not a typo. A human should decide it; this
script fixes only the crash-level defect (a token the gate cannot parse at
all) and takes the fail-closed side meanwhile. Reversible: flip the parked rows
to ``exportable_approved`` once ruled.

Idempotent: re-running finds nothing to change. Delete after the fix lands.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
PATH = REPO / "curation" / "community_quotes.csv"
APPROVAL_FIELDS = (
    "rights_approver",
    "rights_approval_scope",
    "rights_approval_date",
    "rights_permitted_use",
)
# Mirrors community_lenses.quotes.CLOSED_CORPORA — kept literal so this
# one-shot never imports (and so never silently follows) a changed gate.
CLOSED_CORPORA = ("nagari",)


def approval_complete(row: dict) -> bool:
    return all((row.get(f) or "").strip() for f in APPROVAL_FIELDS)


def main() -> int:
    with open(PATH, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        print(f"ERROR: no header in {PATH}")
        return 1

    changed = []
    skipped = []
    closed = []
    for row in rows:
        if row.get("rights_review_status") != "approved":
            continue
        # Fail-closed on a CLOSED corpus. Commit 26dad1db4 records a
        # rights-holder approval that reads as lifting nagari's closed
        # designation, but tests/test_community_lenses_quotes.py and
        # tests/test_community_lenses_identity.py still assert that closed-list
        # rows are UNCONDITIONALLY non-exportable, and #183 did not update
        # them. That contradiction is a rights decision, not a typo, so this
        # script does NOT resolve it: it parks closed-corpus rows on the
        # fail-closed side of the on-vocabulary set and leaves the ruling to
        # a human. Reversible: flip to exportable_approved once ruled.
        row["rights_review_status"] = "non_exportable"
        if row.get("corpus_id") in CLOSED_CORPORA:
            closed.append(row.get("quote_id"))
        elif approval_complete(row):
            changed.append(row.get("quote_id"))
        else:
            skipped.append(row.get("quote_id"))

    if not changed:
        print("nothing to change — register already on-vocabulary")
        return 0

    with open(PATH, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"rewrote {PATH.relative_to(REPO).as_posix()}")
    total = len(changed) + len(closed) + len(skipped)
    print(f"  'approved' -> 'non_exportable' : {total} row(s)")
    if closed:
        print(f"    closed corpus {CLOSED_CORPORA} (rights ruling pending, "
              f"parked fail-closed): {', '.join(closed)}")
    if changed:
        print(f"    open corpus with a complete approval record (would be "
              f"exportable_approved once ruled): {', '.join(changed)}")
    if skipped:
        print(f"    approval record incomplete: {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
