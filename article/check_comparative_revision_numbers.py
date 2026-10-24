"""Number gate for the H1900 comparative revision.

Every comparative-lens number in ``article/ppv_comparative_revision_ru.md`` must
come from a frozen H1899 metric table, cited by ``metric_id`` — never from prose,
chat or an intermediate run. This script re-derives each asserted value from the
tables and fails if the article disagrees.

Baseline-provenance numbers (the conference-only figures inherited from
``ppv_submission_article.md``) are checked by ``check_ppv_numbers.py`` against
``conferences.db``; they are deliberately NOT re-checked here. What this gate adds
is the half no other checker covers: the five-lens comparative layer.

Exit 0 = every checked assertion matches. Exit 1 = at least one drift.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "analytics_output" / "community_lenses" / "tables"
LEDGER = ROOT / "analytics_output" / "community_lenses" / "reports" / "claims_ledger.csv"
QUOTES = ROOT / "curation" / "community_quotes.csv"
LINKS = ROOT / "curation" / "community_person_links.csv"
ARTICLE = ROOT / "article" / "ppv_comparative_revision_ru.md"


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def metrics() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for csv_path in sorted(TABLES.glob("*.csv")):
        for row in rows(csv_path):
            out[row["metric_id"]] = row
    return out


M = metrics()
TEXT = ARTICLE.read_text(encoding="utf-8")
failures: list[str] = []
checked = 0


def nbsp_variants(value: str) -> list[str]:
    """Accept the several ways the article may render one number.

    Large integers may carry a thousands separator (space, no-break space or
    narrow no-break space). Decimal shares use a comma and are matched
    literally, so only integers get grouped variants.
    """
    variants = [value]
    if value.isdigit() and len(value) > 3:
        for sep in (' ', '\xa0', '\u202f'):
            variants.append(f"{int(value):,}".replace(",", sep))
    return variants


def present(value: str, label: str) -> None:
    global checked
    checked += 1
    if not any(v in TEXT for v in nbsp_variants(value)):
        failures.append(f"{label}: {value!r} absent from the article")


def numerator(metric_id: str) -> str:
    if metric_id not in M:
        failures.append(f"missing metric_id {metric_id!r} in the frozen tables")
        return "<MISSING>"
    return M[metric_id]["numerator"]


def pct(metric_id: str, decimals: int = 1) -> str:
    if metric_id not in M:
        failures.append(f"missing metric_id {metric_id!r} in the frozen tables")
        return "<MISSING>"
    value = float(M[metric_id]["value"]) * 100
    return f"{value:.{decimals}f}".replace(".", ",")


# --- coverage: record counts per lens -------------------------------------
for metric_id, label in (
    ("coverage.conferences", "conferences records"),
    ("coverage.nagari", "nagari records"),
    ("coverage.vk_ors", "vk_ors records"),
):
    present(numerator(metric_id), label)

# absent lenses must NOT carry a fabricated count
for metric_id in ("coverage.indology_l", "coverage.bvp"):
    row = M.get(metric_id, {})
    checked += 1
    if (row.get("numerator") or "").strip():
        failures.append(f"{metric_id}: frozen table unexpectedly carries a numerator")
    if row.get("coverage_status") != "unavailable":
        failures.append(f"{metric_id}: coverage_status is not 'unavailable'")

# --- activity by period: the § 3 comparative insert -----------------------
for metric_id, decimals in (
    ("activity.conferences.2018-2025", 1),
    ("activity.conferences.2005-2010", 1),
    ("activity.nagari.2011-2017", 1),
    ("activity.nagari.2018-2025", 1),
    ("activity.vk_ors.2018-2025", 1),
):
    present(numerator(metric_id), f"{metric_id} numerator")
    present(pct(metric_id, decimals), f"{metric_id} share")

# --- partial-2026 counts (rule stated in § 2) ----------------------------
for metric_id in (
    "activity.conferences.2026-partial",
    "activity.nagari.2026-partial",
    "activity.vk_ors.2026-partial",
):
    present(numerator(metric_id), f"{metric_id} numerator")

# --- intellectual content: § 4 projection -------------------------------
for metric_id in (
    "content.conferences.literature_poetics.taxonomy_crosswalk",
    "content.conferences.religion_philosophy.taxonomy_crosswalk",
    "content.nagari.texts_philology.taxonomy_crosswalk",
    "content.nagari.grammar_linguistics.taxonomy_crosswalk",
    "content.nagari.digital_computational.taxonomy_crosswalk",
    "content.nagari.religion_philosophy.taxonomy_crosswalk",
):
    present(numerator(metric_id), f"{metric_id} numerator")
    present(pct(metric_id), f"{metric_id} share")

# denominators the article names explicitly
present(M["content.conferences.literature_poetics.taxonomy_crosswalk"]["denominator"],
        "conferences content denominator")
present(M["content.nagari.texts_philology.taxonomy_crosswalk"]["denominator"],
        "nagari content denominator")

# --- community function: § 4 teaching claim -----------------------------
for metric_id in (
    "function.nagari.teaching_learning.taxonomy_crosswalk",
    "function.nagari.resource_sharing.taxonomy_crosswalk",
):
    present(numerator(metric_id), f"{metric_id} numerator")
    present(pct(metric_id), f"{metric_id} share")
present(M["function.nagari.teaching_learning.taxonomy_crosswalk"]["denominator"],
        "nagari function denominator")

# --- argument level: the frozen partition quoted in § 5 -----------------
frozen_levels: dict[str, int] = {}
for metric_id, row in M.items():
    if metric_id.startswith("gumilev.conferences."):
        frozen_levels[metric_id.split(".")[2]] = frozen_levels.get(
            metric_id.split(".")[2], 0
        ) + int(row["numerator"])
for level in ("G1", "G2", "G3"):
    present(str(frozen_levels[level]), f"frozen {level} total")
present(M["gumilev.conferences.G1.gumilyov_scale_csv_deepseek"]["denominator"],
        "frozen Gumilev denominator")
present(numerator("gumilev.nagari.unknown.deterministic_ruleset_pilot"),
        "nagari pilot unknown")
present(pct("gumilev.nagari.unknown.deterministic_ruleset_pilot"),
        "nagari pilot unknown share")
present(numerator("gumilev.vk_ors.unknown.deterministic_ruleset_pilot"),
        "vk_ors pilot unknown")

# --- person overlap: § 5 ------------------------------------------------
present(numerator("overlap.conferences"), "cross-lens persons")
present(M["overlap.conferences"]["denominator"], "conferences persons denominator")
present(pct("overlap.conferences"), "cross-lens person share")
miss = M["overlap.nagari"]["missingness"]
linked = re.search(r"linked_mentions=(\d+)", miss)
present(linked.group(1), "nagari linked mentions")
excluded = re.search(r"ambiguous_candidates_excluded=(\d+)", miss)
present(excluded.group(1), "ambiguous candidates excluded")

# --- quotes: rights + aggregate discipline ------------------------------
quote_rows = {r["quote_id"]: r for r in rows(QUOTES)}
ledger_ids = {r["claim_id"].strip() for r in rows(LEDGER)}

for qid in ("Q-VK-22289", "Q-NG-PANINI-ASK", "Q-NG-PANINI-ANSWER"):
    checked += 1
    row = quote_rows.get(qid)
    if row is None:
        failures.append(f"quote {qid} missing from the register")
        continue
    verbatim = row["quote_verbatim"].strip()
    if verbatim not in TEXT:
        failures.append(f"quote {qid}: verbatim text not reproduced exactly")
    for field in ("rights_approver", "rights_approval_scope",
                  "rights_approval_date", "rights_permitted_use"):
        if not (row.get(field) or "").strip():
            failures.append(f"quote {qid}: incomplete approval record ({field} empty)")

# Q-VK aggregate numbers are asserted in § 4
vk = quote_rows["Q-VK-22289"]
present(vk["agg_numerator"], "vk bookzealots numerator")
present(vk["agg_denominator"], "vk bookzealots denominator")

# Q-NG-PANINI-ASK numerator asserted in § 5
present(quote_rows["Q-NG-PANINI-ASK"]["agg_numerator"], "nagari asker numerator")

# The ANSWER quote has NO denominator: the article must not invent one.
checked += 1
if quote_rows["Q-NG-PANINI-ANSWER"]["agg_status"] != "aggregate_evidence_unavailable":
    failures.append("Q-NG-PANINI-ANSWER: expected aggregate_evidence_unavailable")

# Unresolved claim ids must be disclosed, not cited as ledger-backed
unresolved = [
    qid for qid, r in quote_rows.items()
    if (r.get("article_claim_id") or "").strip() not in ledger_ids
]
checked += 1
if unresolved and "отсутству" not in TEXT:
    failures.append(
        f"quotes with unresolved claim ids {unresolved} are not disclosed in the article"
    )

# --- identity links: ambiguous rows must be flagged ---------------------
link_rows = rows(LINKS)
n_ambiguous = sum(1 for r in link_rows if r["decision"] == "ambiguous")
present(str(len(link_rows)), "adjudicated links total")
present(str(n_ambiguous), "ambiguous links")

# --- prohibited constructions ------------------------------------------
for lens_pair, forbidden in (
    ("cross-lens total", str(1362 + 18727 + 7608)),
    ("conferences+nagari", str(1362 + 18727)),
    ("nagari+vk_ors", str(18727 + 7608)),
):
    checked += 1
    if forbidden in TEXT.replace(" ", "").replace(" ", ""):
        failures.append(f"prohibited {lens_pair} sum {forbidden} appears in the article")

print(f"Comparative revision: {checked} assertions checked")
if failures:
    print(f"DRIFTS: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("All comparative numbers trace to a frozen metric_id. PASSED")
