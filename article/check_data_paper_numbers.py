"""Cross-check numeric claims in article/data_paper_draft.md against the data.

Companion to check_ppv_numbers.py (which gates the Russian PPV article):
every derivable figure quoted in the English data paper draft must match the
rebuilt site_data.json, or this script exits non-zero. Figures that cannot
be re-derived from current artifacts (e.g. the cross-model agreement κ) are
listed as warnings so drift is at least visible at submission time.

Assertions are *anchored value checks*, not bare substring containment.
Each claim is verified with a phrase-anchored regex that captures the number
and compares it (with word boundaries) to the value derived from the data —
so this gate now catches three drift classes the old `snippet in draft`
containment could not:

  1. substring-bleed false PASSES — an old check for ``"22 event"`` was
     silently satisfied by ``"122 events"``; ``\b``-anchored capture rejects it;
  2. contradictory duplicates — a correct value in the abstract no longer
     masks a *stale* value of the same quantity elsewhere in the draft, because
     every occurrence of the anchored phrase is checked, not just the first;
  3. blind spots — a mismatch is reported as ``expected X, draft line N has Y``
     with surrounding context, instead of the uninformative "does not contain".

The drift-check primitives (:func:`check`, :func:`check_word`) are shared with
the PPV gate rather than reimplemented, so both gates use one drift semantics.

Usage:
  python article/check_data_paper_numbers.py
"""

import csv
import glob
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "article" / "data_paper_draft.md"
SITE_DATA = ROOT / "site_data.json"
DB = ROOT / "conferences.db"
AUTHORITY = ROOT / "authority_ids.json"
APPENDIX_G = ROOT / "article" / "hypothesis_output" / "appendix_g_summary.csv"
OPENALEX = ROOT / "analytics_output" / "openalex_author_candidates.csv"
EDGES = ROOT / "analytics_output" / "network_edges.csv"

# Reuse the anchored drift-check helpers from the PPV gate so both submission
# gates share one drift semantics (single source of truth for how a captured
# number is parsed and compared). Both scripts live in article/, so add that
# directory to the path explicitly — this keeps the import working regardless
# of the caller's cwd (direct run, CI, or pytest import).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from check_ppv_numbers import check, check_word  # noqa: E402

# Lowercase values on purpose: check_word() lowercases the token it captures
# from the draft before comparing, so the expected numeral must be lowercase
# too (the draft writes it sentence-initially as "Six").
NUM_WORDS = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def assert_value(errors, draft, label, regex, expected, *, flags=0):
    """Anchored numeric assertion.

    Fails if the anchored phrase is absent (draft structure changed, so the
    claim can no longer be verified — this preserves the old containment
    check's "phrase missing" coverage) OR if any occurrence of the phrase
    carries a number other than ``expected``.
    """
    if not re.search(regex, draft, flags):
        errors.append(
            f"{label}: anchor phrase absent (/{regex}/) — draft structure "
            f"changed, cannot verify expected {expected}"
        )
        return
    for d in check(label, regex, expected, draft, flags=flags):
        errors.append(
            f"{label}: expected {d['expected']}, draft line {d['line']} has "
            f"{d['found']} (…{d['context']}…)"
        )


def assert_word(errors, draft, label, regex, expected_int, numerals):
    """Anchored assertion for a spelled-out numeral (e.g. 'Six network...')."""
    if not re.search(regex, draft):
        errors.append(f"{label}: anchor phrase absent (/{regex}/)")
        return
    for d in check_word(label, regex, expected_int, numerals, draft):
        errors.append(
            f"{label}: expected '{d['expected']}', draft line {d['line']} has "
            f"'{d['found']}' (…{d['context']}…)"
        )


def assert_auth_row(errors, draft, label, count, pct, cand):
    """Anchored assertion for one '| Ident | N (pct%) | C |' coverage row."""
    row = re.compile(
        rf"\|\s*{re.escape(label)}\s*\|\s*(\d+)\s*\(([\d.]+)%\)\s*\|\s*(\d+)\s*\|"
    )
    m = row.search(draft)
    if not m:
        errors.append(
            f"authority coverage row {label}: table row absent or malformed "
            f"(expected {count} ({pct}%) | {cand})"
        )
        return
    got_count, got_pct, got_cand = int(m.group(1)), float(m.group(2)), int(m.group(3))
    if got_count != count:
        errors.append(f"authority {label} count: expected {count}, draft has {got_count}")
    if abs(got_pct - pct) >= 0.05:
        errors.append(f"authority {label} pct: expected {pct}%, draft has {got_pct}%")
    if got_cand != cand:
        errors.append(f"authority {label} candidate count: expected {cand}, draft has {got_cand}")


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

    errors = []
    warnings = []
    checks_run = 0

    # --- Abstract + narrative figures (anchored to their surrounding phrase) ---
    # ([\d,]+) captures comma-grouped integers; check() strips the commas.
    assert_value(errors, draft, "abstract unique presentations",
                 r"([\d,]+)\s+conference presentations", unique)
    assert_value(errors, draft, "abstract scholar profiles",
                 r"(\d[\d,]*)\s+scholar profiles", total_scholars)
    assert_value(errors, draft, "abstract author participations",
                 r"([\d,]+)\s+author\s+participations", participations)
    assert_value(errors, draft, "abstract year range (start)",
                 r"between\s+(\d{4})\s+and\s+\d{4}", start_year)
    assert_value(errors, draft, "abstract year range (end)",
                 r"between\s+\d{4}\s+and\s+(\d{4})", end_year)
    assert_value(errors, draft, "event record count",
                 r"(\d+)\s+event\s+records", total_events)
    assert_value(errors, draft, "program year count",
                 r"\((\d+)\s+program years\)", years_covered)
    assert_value(errors, draft, "data model scholars row",
                 r"(\d+)\s+profiles with talks", total_scholars)
    assert_value(errors, draft, "reuse section scholar count",
                 r"All\s+(\d+)\s+scholars", total_scholars)
    assert_value(errors, draft, "birth-year coverage",
                 r"\(([\d.]+)%\s+coverage\)", float(birth_pct))
    assert_value(errors, draft, "text analysis corpus size",
                 r"([\d,]+)\s+Russian-language presentation titles", unique)
    checks_run += 11

    # Zograf city-only share: canonical derivation is appendix G (H4 pooled rate)
    with APPENDIX_G.open(encoding="utf-8", newline="") as f:
        appendix = {row["key"]: row["value"] for row in csv.DictReader(f)}
    z_city = appendix.get("H4_zograf_cityonly_pct", "")
    try:
        z_city_val = float(z_city)
    except (TypeError, ValueError):
        errors.append(f"Zograf city-only share (appendix G H4): non-numeric value {z_city!r}")
    else:
        assert_value(errors, draft, "Zograf city-only share (appendix G H4)",
                     r"([\d.]+)%\s+of Zograf participant entries", z_city_val)
        checks_run += 1

    # OpenAlex candidates: persons with >=1 candidate row + total candidate rows
    with OPENALEX.open(encoding="utf-8", newline="") as f:
        oa_rows = [r for r in csv.DictReader(f) if r.get("openalex_id")]
    oa_persons = len({r["person_id"] for r in oa_rows})
    assert_value(errors, draft, "OpenAlex candidate person count",
                 r"\((\d+)\s+scholars returned at least", oa_persons)
    assert_value(errors, draft, "OpenAlex candidate row count",
                 r"(\d+)\s+candidate rows", len(oa_rows))
    checks_run += 2

    # Schema table count (excluding sqlite's internal sqlite_sequence)
    con = sqlite3.connect(DB)
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'") if r[0] != "sqlite_sequence"]
    assert_value(errors, draft, "schema table count",
                 r"with\s+(\d+)\s+tables", len(tables))
    historical = con.execute("select count(*) from person where person_kind='historical'").fetchone()[0]
    assert_value(errors, draft, "historical prosopographical layer size",
                 r"(\d+)\s+pre-contemporary Russian Indologists", historical)
    con.close()
    checks_run += 2

    # Network edge type count (spelled-out number at sentence start)
    with EDGES.open(encoding="utf-8", newline="") as f:
        edge_types = {r["edge_type"] for r in csv.DictReader(f)}
    assert_word(errors, draft, "network edge type count",
                r"(\w+)\s+network edge types", len(edge_types), NUM_WORDS)
    checks_run += 1

    # Authority identifier coverage table rows (count, pct of scholars, candidate split)
    auth = json.loads(AUTHORITY.read_text(encoding="utf-8")).get("persons", {})
    for ident, label in [("wikidata", "Wikidata"), ("orcid", "ORCID"), ("openalex", "OpenAlex")]:
        have = [p for p in auth.values() if p.get(ident)]
        cand = sum(1 for p in have if p.get("confidence") == "candidate")
        pct = round(100 * len(have) / total_scholars, 1) if total_scholars else 0
        assert_auth_row(errors, draft, label, len(have), pct, cand)
        checks_run += 1

    # Analytics CSV export count claim ("100+")
    n_csv = len(glob.glob(str(ROOT / "analytics_output" / "*.csv")))
    if "100+ statistical and review exports" in draft and n_csv < 100:
        errors.append(f"analytics CSV count: draft claims 100+ but only {n_csv} exist")
    checks_run += 1

    # Figures quoted in the draft that are not re-derivable from current
    # artifacts; flag their presence so a stale value is reviewed by hand.
    for pattern, label in [
        (r"κ = 0\.670|κ = 0\.553", "cross-model agreement κ (from docs/classification-reliability-packet.md)"),
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
    print(f"Data paper number check passed ({checks_run} anchored claims verified).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
