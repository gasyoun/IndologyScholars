"""Cross-check numeric claims in article/data_paper_draft.md against the data.

Companion to check_ppv_numbers.py (which gates the Russian PPV article):
every derivable figure quoted in the English data paper draft must match the
rebuilt site_data.json, or this script exits non-zero. Figures that cannot
be re-derived from current artifacts (e.g. the Zograf city-only share) are
listed as warnings so drift is at least visible at submission time.

Usage:
  python article/check_data_paper_numbers.py
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "article" / "data_paper_draft.md"
SITE_DATA = ROOT / "site_data.json"


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def main():
    if not DRAFT.exists():
        print(f"Draft not found: {DRAFT}")
        return 1
    draft = DRAFT.read_text(encoding="utf-8")
    data = load_site_data()
    summary = data.get("summary", {})
    scholars = data.get("scholars", [])

    unique = summary.get("unique_presentations", 0)
    total_scholars = summary.get("total_scholars", 0)
    participations = summary.get("total_presentations", 0)
    start_year = summary.get("start_year", 0)
    end_year = summary.get("end_year", 0)
    total_events = summary.get("total_events", 0)
    years_covered = summary.get("years_covered", 0)

    with_birth = sum(1 for s in scholars if s.get("birth_year"))
    birth_pct = round(100 * with_birth / total_scholars, 1) if total_scholars else 0

    def fmt(n):
        return f"{n:,}"

    errors = []
    warnings = []

    checks = [
        (f"{fmt(unique)} conference presentations", "abstract unique presentations"),
        (f"{total_scholars} scholar profiles", "abstract scholar profiles"),
        (f"{fmt(participations)} author", "abstract author participations"),
        (f"between {start_year} and {end_year}", "abstract year range"),
        (f"{total_events} event", "event record count"),
        (f"({years_covered} program years)", "program year count"),
        (f"{total_scholars} profiles with talks", "data model scholars row"),
        (f"All {total_scholars} scholars", "reuse section scholar count"),
        (f"({birth_pct}% coverage)", "birth-year coverage"),
        (f"{fmt(unique)} Russian-language presentation titles", "text analysis corpus size"),
    ]
    for snippet, label in checks:
        if snippet not in draft:
            errors.append(f"{label}: draft does not contain `{snippet}`")

    # Figures quoted in the draft that are not re-derivable from current
    # artifacts; flag their presence so a stale value is reviewed by hand.
    for pattern, label in [
        (r"70\.3% of Zograf participant entries", "Zograf city-only share (manual figure)"),
        (r"122 scholars returned at least", "OpenAlex candidate count (manual figure)"),
    ]:
        if re.search(pattern, draft):
            warnings.append(f"{label}: present in draft but not machine-verified; re-derive before submission")

    if warnings:
        print("Warnings (manual verification needed):")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("Data paper number check FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"Data paper number check passed ({len(checks)} derivable claims verified).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
