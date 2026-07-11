"""Cross-check numeric claims in article/data_paper_draft.md against the data.

Companion to check_ppv_numbers.py (which gates the Russian PPV article):
every derivable figure quoted in the English data paper draft must match the
rebuilt site_data.json, or this script exits non-zero. Figures that cannot
be re-derived from current artifacts (e.g. the Zograf city-only share) are
listed as warnings so drift is at least visible at submission time.

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

NUM_WORDS = {4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}


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
    # Zograf city-only share: canonical derivation is appendix G (H4 pooled rate)
    with APPENDIX_G.open(encoding="utf-8", newline="") as f:
        appendix = {row["key"]: row["value"] for row in csv.DictReader(f)}
    z_city = appendix.get("H4_zograf_cityonly_pct", "")
    checks.append((f"{z_city}% of Zograf participant entries", "Zograf city-only share (appendix G H4)"))

    # OpenAlex candidates: persons with >=1 candidate row + total candidate rows
    with OPENALEX.open(encoding="utf-8", newline="") as f:
        oa_rows = [r for r in csv.DictReader(f) if r.get("openalex_id")]
    oa_persons = len({r["person_id"] for r in oa_rows})
    checks.append((f"({oa_persons} scholars returned at least", "OpenAlex candidate person count"))
    checks.append((f"{len(oa_rows)} candidate rows", "OpenAlex candidate row count"))

    # Schema table count (excluding sqlite's internal sqlite_sequence)
    con = sqlite3.connect(DB)
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'") if r[0] != "sqlite_sequence"]
    checks.append((f"with {len(tables)} tables", "schema table count"))
    historical = con.execute("select count(*) from person where person_kind='historical'").fetchone()[0]
    checks.append((f"{historical} pre-contemporary Russian Indologists", "historical prosopographical layer size"))
    con.close()

    # Network edge type count (spelled-out number at sentence start)
    with EDGES.open(encoding="utf-8", newline="") as f:
        edge_types = {r["edge_type"] for r in csv.DictReader(f)}
    word = NUM_WORDS.get(len(edge_types), str(len(edge_types)))
    checks.append((f"{word} network edge types", "network edge type count"))

    # Authority identifier coverage table rows (count, pct of scholars, candidate split)
    auth = json.loads(AUTHORITY.read_text(encoding="utf-8")).get("persons", {})
    for ident, label in [("wikidata", "Wikidata"), ("orcid", "ORCID"), ("openalex", "OpenAlex")]:
        have = [p for p in auth.values() if p.get(ident)]
        cand = sum(1 for p in have if p.get("confidence") == "candidate")
        pct = round(100 * len(have) / total_scholars, 1) if total_scholars else 0
        checks.append((f"| {label} | {len(have)} ({pct}%) | {cand} |", f"authority coverage row: {label}"))

    # Analytics CSV export count claim ("100+")
    n_csv = len(glob.glob(str(ROOT / "analytics_output" / "*.csv")))
    if "100+ statistical and review exports" in draft and n_csv < 100:
        errors.append(f"analytics CSV count: draft claims 100+ but only {n_csv} exist")

    for snippet, label in checks:
        if snippet not in draft:
            errors.append(f"{label}: draft does not contain `{snippet}`")

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
    print(f"Data paper number check passed ({len(checks)} derivable claims verified).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
