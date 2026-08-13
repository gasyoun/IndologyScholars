"""Shared-axis classification logic — H1897 (Step 7 of the Wave-1 implementation).

Three jobs, all layered ON TOP of native evidence, never over it:

1. **Crosswalk application.** For every native ``classification_assignment``
   whose (scheme, label) has a non-``unmapped`` row in
   ``codebooks/taxonomy_crosswalk.csv``, insert an ADDITIONAL assignment in
   the target shared scheme. Native rows are never updated, deleted, or
   rewritten; ``native_assignment_snapshot`` + ``verify_native_roundtrip``
   prove that byte-for-byte.

2. **Gumilev argument-level pilot.** Conference ``argument_level`` values are
   canonical existing evidence (imported verbatim by the adapter from
   ``analytics_output/gumilyov_scale.csv``; ``gumilyov_level`` is a legacy
   alias, not a second scale) and are NEVER re-proposed here. For the other
   lenses a bounded, deterministic, review-gated ruleset proposes
   G1/G2/G3/``not_applicable``/``unknown`` per the codebook: announcements,
   bare links, greetings, and bibliography-only requests are
   ``not_applicable``; records whose applicability cannot be decided are
   ``unknown``. Every proposal carries the ruleset version and the matched
   rule id, and stays ``review_status=pending`` — no proposal is ever
   silently accepted, and no confidence value can accept one.

3. **Deterministic stratified review sample + validity report.** The sample
   is reproducible from the data alone (selection by SHA-256 of record_id,
   no RNG), includes every proposed G3, oversamples G2 and the ambiguous
   ``unknown``/``not_applicable`` boundary, and covers each available lens.

Run as a script (``python -m community_lenses.classify``) to rebuild
``analytics_output/community_lenses/review/classification_sample.csv`` and
``analytics_output/community_lenses/reports/classification_validity.md``
from the real adapters.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from collections import Counter
from pathlib import Path

from . import taxonomy

REPO_ROOT = taxonomy.REPO_ROOT

CROSSWALK_METHOD = "taxonomy_crosswalk"
PILOT_METHOD = "deterministic_ruleset_pilot"
PILOT_RULESET_VERSION = "h1897-argument-rules-1.0.0"

# Conference argument_level is canonical existing evidence; the pilot runs
# only on the other lenses.
PILOT_CORPORA = ("nagari", "vk_ors", "bvp")

# ARCHITECTURE period contract, centralized (period boundaries are never
# reimplemented per adapter).
PERIOD_BINS = (
    ("pre-1990", None, 1989),
    ("1990-2004", 1990, 2004),
    ("2005-2010", 2005, 2010),
    ("2011-2017", 2011, 2017),
    ("2018-2025", 2018, 2025),
    ("2026-partial", 2026, None),
)

REVIEW_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "review"
REPORTS_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "reports"
SAMPLE_PATH = REVIEW_DIR / "classification_sample.csv"
REPORT_PATH = REPORTS_DIR / "classification_validity.md"

SAMPLE_COLUMNS = (
    "record_id",
    "corpus_id",
    "period",
    "title_or_subject",
    "native_labels",
    "proposed_intellectual_content",
    "proposed_community_function",
    "proposed_argument_level",
    "proposal_method",
    "stratum",
    "review_intellectual_content",
    "review_community_function",
    "review_argument_applicability",
    "review_argument_level",
    "reviewer",
    "review_decision",
)

# VERIFICATION V6 publication thresholds, restated so the report and tests
# share one source.
SHARED_AXIS_THRESHOLDS = {
    "raw_agreement_min": 0.80,
    "gwet_ac1_min": 0.70,
    "per_label_precision_min": 0.70,
}
GUMILEV_THRESHOLDS = {
    "applicability_precision_min": 0.90,
    "raw_level_agreement_min": 0.80,
    "gwet_ac1_min": 0.67,
}

# Per-lens deterministic sample floors: at least 40 records from each
# complete lens (VERIFICATION V6); smaller floors for pilot/partial lenses.
SAMPLE_FLOORS = {"conferences": 40, "vk_ors": 40, "nagari": 20, "bvp": 10}
G2_OVERSAMPLE_CAP = 60
BOUNDARY_SAMPLE_PER_LENS = 15  # ambiguous unknown/not_applicable oversample


# ---------------------------------------------------------------------------
# 1. Native snapshot + lossless round-trip
# ---------------------------------------------------------------------------

def native_assignment_snapshot(conn: sqlite3.Connection) -> tuple:
    """The frozen, ordered set of NATIVE assignments (everything not added by H1897).

    Includes label AND value so a rewritten value (not just a relabel) fails
    the round-trip.
    """
    rows = conn.execute(
        """SELECT record_id, scheme_id, label_id, COALESCE(value, ''), method,
                  method_version, COALESCE(review_status, ''), COALESCE(reviewer, '')
           FROM classification_assignment
           WHERE method NOT IN (?, ?)
           ORDER BY record_id, scheme_id, label_id""",
        (CROSSWALK_METHOD, PILOT_METHOD),
    ).fetchall()
    return tuple(tuple(row) for row in rows)


def verify_native_roundtrip(conn: sqlite3.Connection, before: tuple) -> list[str]:
    """Empty list = every native assignment survived byte-for-byte."""
    after = native_assignment_snapshot(conn)
    errors: list[str] = []
    if before == after:
        return errors
    before_set, after_set = set(before), set(after)
    for row in sorted(before_set - after_set):
        errors.append(f"native assignment lost or altered: {row}")
    for row in sorted(after_set - before_set):
        errors.append(f"unexpected new 'native' assignment: {row}")
    if not errors:
        errors.append("native assignment ORDER changed (same set, different sequence)")
    return errors


# ---------------------------------------------------------------------------
# 2. Crosswalk application (additional assertions, never replacements)
# ---------------------------------------------------------------------------

def apply_crosswalk_assignments(
    conn: sqlite3.Connection,
    crosswalk_rows: list[dict] | None = None,
    assigned_at: str = "1970-01-01T00:00:00Z",
) -> int:
    """Layer shared-axis assignments derived from the crosswalk next to native ones.

    Every inserted row is a PROPOSAL: ``review_status='pending'``,
    ``method='taxonomy_crosswalk'``. Returns the number of rows inserted.
    """
    if crosswalk_rows is None:
        crosswalk_rows = taxonomy.load_crosswalk()
    mapping: dict[tuple[str, str], list[dict]] = {}
    for row in crosswalk_rows:
        if row["mapping_relation"] == "unmapped":
            continue
        mapping.setdefault((row["source_scheme"], row["source_label"]), []).append(row)

    inserted = 0
    native = conn.execute(
        "SELECT record_id, scheme_id, label_id FROM classification_assignment "
        "WHERE method NOT IN (?, ?) ORDER BY record_id, scheme_id, label_id",
        (CROSSWALK_METHOD, PILOT_METHOD),
    ).fetchall()
    for record_id, scheme_id, label_id in native:
        for xrow in mapping.get((scheme_id, label_id), ()):
            cursor = conn.execute(
                """INSERT OR IGNORE INTO classification_assignment
                   (record_id, scheme_id, label_id, value, evidence_span, method,
                    method_version, confidence, review_status, reviewer, assigned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'pending', NULL, ?)""",
                (
                    record_id,
                    xrow["target_scheme"],
                    xrow["target_label"],
                    f"{xrow['mapping_relation']} from {scheme_id}:{label_id}",
                    f"crosswalk:{scheme_id}:{label_id}",
                    CROSSWALK_METHOD,
                    xrow["version"],
                    assigned_at,
                ),
            )
            inserted += cursor.rowcount
    return inserted


# ---------------------------------------------------------------------------
# 3. Deterministic Gumilev argument-level pilot
# ---------------------------------------------------------------------------

# Rule order matters: the first matching bucket wins, and not_applicable is
# checked FIRST so announcements/greetings/etc. can never be forced into G1.
_NA_RULES = (
    ("na_announcement", re.compile(
        r"анонс|объявлен|приглаша|расписани|регистраци|запись\s+(на|в)\b|скидк|конкурс"
        r"|call\s+for\s+papers|\bcfp\b|vacan|job\s+posting|программа\s+конференции",
        re.IGNORECASE)),
    ("na_greeting", re.compile(
        r"поздравля|с\s+новым\s+годом|с\s+праздником|с\s+днём|с\s+днем|happy\s+new\s+year"
        r"|congratulat|добро\s+пожаловать",
        re.IGNORECASE)),
    ("na_bibliography_only", re.compile(
        r"ищу\s+(книгу|pdf|скан|учебник)|прошу\s+прислать|поделитесь|есть\s+ли\s+у\s+кого"
        r"|looking\s+for\s+a\s+(copy|pdf)|pdf\s+request",
        re.IGNORECASE)),
    ("na_bare_link", re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)),
)

_G3_RULE = ("g3_synthesis", re.compile(
    r"сравнительн|компаративн|comparative|цивилизац|civilizat|методологи|methodolog"
    r"|типологи|typolog",
    re.IGNORECASE))

_G2_RULE = ("g2_tradition_class", re.compile(
    r"\bшкол[аыуе]\b|традици|\bжанр|направлени[ея]\b|история\s+(изучени|индологи|санскрит)"
    r"|history\s+of|обзор|survey|overview|\btradition\b|\bgenre\b",
    re.IGNORECASE))

# G1: an identifiable individual object — an explicitly quoted title, or a
# named text/text-class from the Renou layer's own conference-title patterns
# (reused as evidence of a specific source being named, never re-derived).
_G1_QUOTED = ("g1_quoted_title", re.compile(r"[«»„“”\"'].+[«»„“”\"']"))


def _g1_renou_patterns() -> tuple[tuple[str, re.Pattern], ...]:
    rules = []
    path = REPO_ROOT / "curation" / "renou_conference_rules.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rules.append((f"g1_renou_{row['rule_id']}", re.compile(row["pattern"], re.IGNORECASE)))
    return tuple(rules)


_G1_RENOU_CACHE: tuple | None = None


def propose_argument_level(text: str | None) -> tuple[str, str]:
    """Deterministic (label, rule_id) proposal for one record's title/subject.

    ``not_applicable`` beats everything; then G3 > G2 > G1; anything left is
    ``unknown`` (may be applicable, evidence insufficient) — never a forced G1.
    """
    global _G1_RENOU_CACHE
    if not text or not text.strip():
        return "unknown", "no_subject_evidence"
    for rule_id, pattern in _NA_RULES:
        if pattern.search(text):
            return "not_applicable", rule_id
    rule_id, pattern = _G3_RULE
    if pattern.search(text):
        return "G3", rule_id
    rule_id, pattern = _G2_RULE
    if pattern.search(text):
        return "G2", rule_id
    rule_id, pattern = _G1_QUOTED
    if pattern.search(text):
        return "G1", rule_id
    if _G1_RENOU_CACHE is None:
        _G1_RENOU_CACHE = _g1_renou_patterns()
    for rule_id, pattern in _G1_RENOU_CACHE:
        if pattern.search(text):
            return "G1", rule_id
    return "unknown", "no_rule_matched"


def run_argument_level_pilot(
    conn: sqlite3.Connection,
    assigned_at: str = "1970-01-01T00:00:00Z",
) -> int:
    """Propose argument_level for pilot-lens records that have none. Returns rows inserted."""
    placeholders = ", ".join("?" for _ in PILOT_CORPORA)
    records = conn.execute(
        f"""SELECT r.record_id, r.title_or_subject
            FROM record r
            JOIN container c ON c.container_id = r.container_id
            WHERE c.corpus_id IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM classification_assignment ca
                  WHERE ca.record_id = r.record_id AND ca.scheme_id = 'argument_level')
            ORDER BY r.record_id""",
        PILOT_CORPORA,
    ).fetchall()
    inserted = 0
    for record_id, title in records:
        label, rule_id = propose_argument_level(title)
        cursor = conn.execute(
            """INSERT OR IGNORE INTO classification_assignment
               (record_id, scheme_id, label_id, value, evidence_span, method,
                method_version, confidence, review_status, reviewer, assigned_at)
               VALUES (?, 'argument_level', ?, ?, 'title_or_subject', ?, ?, NULL,
                       'pending', NULL, ?)""",
            (record_id, label, rule_id, PILOT_METHOD, PILOT_RULESET_VERSION, assigned_at),
        )
        inserted += cursor.rowcount
    return inserted


# ---------------------------------------------------------------------------
# 4. Deterministic stratified review sample
# ---------------------------------------------------------------------------

def period_bin(created_at: str | None) -> str:
    if not created_at or len(created_at) < 4 or not created_at[:4].isdigit():
        return "undated"
    year = int(created_at[:4])
    for name, lo, hi in PERIOD_BINS:
        if (lo is None or year >= lo) and (hi is None or year <= hi):
            return name
    return "undated"


def _stable_key(record_id: str) -> str:
    return hashlib.sha256(record_id.encode("utf-8")).hexdigest()


def _conference_theme_proposals() -> dict[str, set[str]]:
    """presentation_id -> IC labels derivable from theme/meso codes via the crosswalk.

    The conference adapter deliberately does not emit theme/meso assignments;
    this derives review-sheet PROPOSALS directly from the frozen analytics
    CSVs + the crosswalk so the sample can validate exactly that adjudication.
    """
    mapping: dict[tuple[str, str], set[str]] = {}
    for row in taxonomy.load_crosswalk():
        if row["mapping_relation"] == "unmapped":
            continue
        if row["target_scheme"] != "intellectual_content":
            continue
        mapping.setdefault((row["source_scheme"], row["source_label"]), set()).add(
            row["target_label"]
        )
    proposals: dict[str, set[str]] = {}
    theme_path = REPO_ROOT / "analytics_output" / "theme_codes_final_v2.csv"
    with theme_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            labels: set[str] = set()
            for n in (1, 2, 3, 4):
                value = (row.get(f"l{n}") or "").strip()
                if value:
                    labels |= mapping.get((f"conferences_theme_l{n}", value), set())
            if labels:
                proposals[row["presentation_id"]] = labels
    meso_path = REPO_ROOT / "analytics_output" / "meso_codes_deepseek.csv"
    with meso_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            labels = set()
            for code in taxonomy._MESO_SPLIT.split(row.get("meso_codes") or ""):
                code = code.strip()
                if code:
                    labels |= mapping.get(("conferences_meso", code), set())
            if labels:
                proposals.setdefault(row["presentation_id"], set()).update(labels)
    return proposals


def build_review_sample(conn: sqlite3.Connection) -> list[dict]:
    """Deterministic stratified sample rows (no RNG: selection by SHA-256 of record_id)."""
    theme_proposals = _conference_theme_proposals()

    rows = conn.execute(
        """SELECT r.record_id, c.corpus_id, r.created_at, r.title_or_subject,
                  r.source_record_id
           FROM record r JOIN container c ON c.container_id = r.container_id
           ORDER BY r.record_id"""
    ).fetchall()

    assignments: dict[str, list[tuple]] = {}
    for row in conn.execute(
        """SELECT record_id, scheme_id, label_id, method, review_status
           FROM classification_assignment
           ORDER BY record_id, scheme_id, label_id"""
    ):
        assignments.setdefault(row[0], []).append(row[1:])

    candidates = []
    for record_id, corpus_id, created_at, title, source_record_id in rows:
        assigned = assignments.get(record_id, [])
        native = sorted(
            f"{s}:{l}" for s, l, method, _ in assigned
            if method not in (CROSSWALK_METHOD, PILOT_METHOD)
        )
        ic = sorted({l for s, l, m, _ in assigned
                     if s == "intellectual_content" and m == CROSSWALK_METHOD})
        if not ic and corpus_id == "conferences":
            ic = sorted(theme_proposals.get(source_record_id, ()))
        cf = sorted({l for s, l, m, _ in assigned
                     if s == "community_function" and m == CROSSWALK_METHOD})
        pilot_level = next(
            (l for s, l, m, _ in assigned
             if s == "argument_level" and m == PILOT_METHOD), "")
        native_level = next(
            (l for s, l, m, _ in assigned
             if s == "argument_level" and m != PILOT_METHOD), "")
        candidates.append({
            "record_id": record_id,
            "corpus_id": corpus_id,
            "period": period_bin(created_at),
            "title_or_subject": (title or "")[:300],
            "native_labels": "; ".join(native),
            "proposed_intellectual_content": "; ".join(ic),
            "proposed_community_function": "; ".join(cf),
            "proposed_argument_level": pilot_level or native_level,
            "proposal_method": (PILOT_METHOD if pilot_level
                                else ("existing_conference_assignment" if native_level else "")),
            "_sort": _stable_key(record_id),
        })

    selected: dict[str, dict] = {}

    def take(row: dict, stratum: str) -> None:
        if row["record_id"] not in selected:
            row = dict(row)
            row["stratum"] = stratum
            selected[row["record_id"]] = row

    # 1. Every proposed G3 from the pilot lenses.
    for row in sorted(candidates, key=lambda r: r["_sort"]):
        if row["proposal_method"] == PILOT_METHOD and row["proposed_argument_level"] == "G3":
            take(row, "pilot_G3_all")

    # 2. G2 oversample (deterministic-first, capped).
    g2 = [r for r in sorted(candidates, key=lambda r: r["_sort"])
          if r["proposal_method"] == PILOT_METHOD and r["proposed_argument_level"] == "G2"]
    for row in g2[:G2_OVERSAMPLE_CAP]:
        take(row, "pilot_G2_oversample")

    # 3. Ambiguous unknown / not_applicable boundary, per pilot lens.
    for corpus in PILOT_CORPORA:
        pool = [r for r in sorted(candidates, key=lambda r: r["_sort"])
                if r["corpus_id"] == corpus and r["proposal_method"] == PILOT_METHOD
                and r["proposed_argument_level"] in ("unknown", "not_applicable")]
        for row in pool[:BOUNDARY_SAMPLE_PER_LENS]:
            take(row, f"pilot_boundary_{corpus}")

    # 4. Per-lens floors, stratified over period × has-native-class × level.
    for corpus, floor in SAMPLE_FLOORS.items():
        pool = [r for r in candidates if r["corpus_id"] == corpus]
        if not pool:
            continue
        strata: dict[tuple, list[dict]] = {}
        for row in pool:
            key = (row["period"], bool(row["native_labels"]),
                   row["proposed_argument_level"] or "none")
            strata.setdefault(key, []).append(row)
        for key in strata:
            strata[key].sort(key=lambda r: r["_sort"])
        need = max(0, floor - sum(1 for r in selected.values() if r["corpus_id"] == corpus))
        stratum_keys = sorted(strata)
        idx = 0
        while need > 0 and any(strata[k] for k in stratum_keys):
            key = stratum_keys[idx % len(stratum_keys)]
            bucket = strata[key]
            while bucket:
                row = bucket.pop(0)
                if row["record_id"] not in selected:
                    take(row, f"floor_{corpus}_{key[0]}")
                    need -= 1
                    break
            idx += 1

    sample = sorted(selected.values(), key=lambda r: (r["corpus_id"], r["_sort"]))
    for row in sample:
        row.pop("_sort", None)
        for col in SAMPLE_COLUMNS:
            row.setdefault(col, "")
    return sample


def write_review_sample(sample: list[dict], path: Path = SAMPLE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SAMPLE_COLUMNS))
        writer.writeheader()
        for row in sample:
            writer.writerow({col: row.get(col, "") for col in SAMPLE_COLUMNS})


# ---------------------------------------------------------------------------
# 5. Validity report
# ---------------------------------------------------------------------------

def _lens_coverage(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    rows = conn.execute(
        """SELECT s.corpus_id, s.coverage_status, COUNT(r.record_id)
           FROM source_snapshot s
           LEFT JOIN record r ON r.source_snapshot_id = s.snapshot_id
           GROUP BY s.corpus_id, s.coverage_status
           ORDER BY s.corpus_id"""
    ).fetchall()
    return [tuple(row) for row in rows]


def write_validity_report(
    conn: sqlite3.Connection,
    sample: list[dict],
    roundtrip_errors: list[str],
    crosswalk_inserted: int,
    pilot_inserted: int,
    path: Path = REPORT_PATH,
) -> None:
    inventory = taxonomy.native_label_inventory()
    summary = taxonomy.crosswalk_summary()
    validation_errors = taxonomy.validate_crosswalk()

    pilot_counts = Counter(
        row[0] for row in conn.execute(
            "SELECT label_id FROM classification_assignment "
            "WHERE scheme_id = 'argument_level' AND method = ?", (PILOT_METHOD,))
    )
    native_gumilev = Counter(
        row[0] for row in conn.execute(
            "SELECT label_id FROM classification_assignment "
            "WHERE scheme_id = 'argument_level' AND method != ?", (PILOT_METHOD,))
    )
    sample_strata = Counter(row["stratum"].split("_", 1)[0] for row in sample)
    sample_by_corpus = Counter(row["corpus_id"] for row in sample)

    lines: list[str] = []
    a = lines.append
    a("# Classification validity — shared axes, crosswalk, and Gumilev pilot (H1897)")
    a("")
    a("_Created: 31-07-2026 · Last updated: 31-07-2026_")
    a("")
    a("Produced by `community_lenses/classify.py` (H1897, Fable 5 `claude-fable-5`); "
      "deterministic, no RNG. Native classification is immutable evidence: every shared "
      "assignment below is an ADDITIONAL assertion with `review_status=pending`.")
    a("")
    a("## Scheme and label inventory")
    a("")
    a("| Scheme | Kind | Coverage | Distinct labels |")
    a("|---|---|---|---|")
    for scheme, meta in sorted(taxonomy.SCHEME_INVENTORY.items()):
        n = len(inventory.get(scheme, ())) if scheme in inventory else (
            len(taxonomy.load_codebook(meta["codebook"])) if meta["codebook"] else 0)
        a(f"| `{scheme}` | {meta['kind']} | {meta['coverage']} | {n} |")
    a("")
    a("Frozen before crosswalking; provenance per scheme is recorded in "
      "`community_lenses/taxonomy.py` `SCHEME_INVENTORY`.")
    a("")
    a("## Crosswalk")
    a("")
    a(f"- Total rows: **{summary['total_rows']}** "
      f"(version {taxonomy.CROSSWALK_VERSION}, all rows carry relation, rationale, "
      "evidence count, review state, and version).")
    a(f"- Relation counts: {summary['relation_counts']}")
    a(f"- Review-state counts: {summary['review_counts']} — every mapping is an "
      "adjudicated PROPOSAL awaiting human review; nothing is auto-accepted.")
    a(f"- Rows per source scheme: {summary['rows_per_source_scheme']}")
    a(f"- Explicit `unmapped` adjudications: {len(summary['unmapped_labels'])} labels "
      "(each with a written rationale; see the CSV).")
    a(f"- Contract validation: "
      f"{'**clean**' if not validation_errors else f'**{len(validation_errors)} ERRORS**'}.")
    a("")
    a("## Source-native round-trip")
    a("")
    if roundtrip_errors:
        a(f"**FAILED** — {len(roundtrip_errors)} discrepancies:")
        for err in roundtrip_errors[:20]:
            a(f"- {err}")
    else:
        a("**PASSED** — every source-native assignment (record, scheme, label, value, "
          "method, review state) survived crosswalk application and the pilot "
          "byte-for-byte; shared assignments were layered next to them "
          f"({crosswalk_inserted} crosswalk-derived rows inserted).")
    a("")
    a("## Lens coverage at classification time")
    a("")
    a("| Lens | Coverage status | Records |")
    a("|---|---|---|")
    for corpus_id, status, n in _lens_coverage(conn):
        a(f"| {corpus_id} | {status} | {n} |")
    a("")
    a("- INDOLOGY-L: adapter unavailable (blocked on H1894); its Atlas topic/function "
      "schemes are declared in the inventory with crosswalk coverage `unavailable` — no "
      "labels were invented from planning prose.")
    a("- BVP: partial acquisition; no native category scheme observed, so `bvp_native` "
      "remains a reserved namespace. All BVP percentages downstream must carry explicit "
      "denominators (partial coverage limits classification claims).")
    a("- nagari: pilot slice; shared-axis label shares from this lens are "
      "pilot-denominator only.")
    a("")
    a("## Gumilev argument-level pilot")
    a("")
    a("Existing conference `argument_level` is canonical accepted evidence "
      f"(distribution: {dict(sorted(native_gumilev.items()))}); `gumilyov_level` is a "
      "legacy alias, not a second scale, and was not re-proposed.")
    a("")
    a(f"Pilot lenses ({', '.join(PILOT_CORPORA)}): deterministic ruleset "
      f"`{PILOT_RULESET_VERSION}` proposed {pilot_inserted} labels, all "
      "`review_status=pending`:")
    a("")
    a("| Proposed level | Count |")
    a("|---|---|")
    for label in ("G1", "G2", "G3", "not_applicable", "unknown"):
        a(f"| {label} | {pilot_counts.get(label, 0)} |")
    a("")
    a("Announcements, bare links, greetings, and bibliography-only requests are "
      "`not_applicable` by rule (checked before any G rule, so none can be forced into "
      "G1); undecidable applicability is `unknown`.")
    a("")
    a("## Review sample design")
    a("")
    a(f"- File: `analytics_output/community_lenses/review/classification_sample.csv` "
      f"({len(sample)} rows).")
    a("- Deterministic: candidate ordering and selection use SHA-256 of `record_id`; "
      "re-running on the same snapshot reproduces the identical sample.")
    a("- Strata: every proposed G3 (all of them), a G2 oversample "
      f"(cap {G2_OVERSAMPLE_CAP}), an ambiguous `unknown`/`not_applicable` boundary "
      f"sample per pilot lens ({BOUNDARY_SAMPLE_PER_LENS} each), then per-lens floors "
      f"{SAMPLE_FLOORS} stratified by period × native-class presence × proposed level.")
    a(f"- Selected per lens: {dict(sorted(sample_by_corpus.items()))}")
    a(f"- Selected per stratum family: {dict(sorted(sample_strata.items()))}")
    a("")
    a("## Decision thresholds and gate status")
    a("")
    a("Shared axes (VERIFICATION V6): raw agreement >= "
      f"{SHARED_AXIS_THRESHOLDS['raw_agreement_min']:.0%}, Gwet AC1 >= "
      f"{SHARED_AXIS_THRESHOLDS['gwet_ac1_min']}, no article-critical label below "
      f"{SHARED_AXIS_THRESHOLDS['per_label_precision_min']} precision. Cross-lens "
      "Gumilev: applicability precision >= "
      f"{GUMILEV_THRESHOLDS['applicability_precision_min']}, raw level agreement >= "
      f"{GUMILEV_THRESHOLDS['raw_level_agreement_min']:.0%}, Gwet AC1 >= "
      f"{GUMILEV_THRESHOLDS['gwet_ac1_min']}, every accepted G3 reviewed.")
    a("")
    a("**Threshold evidence is ABSENT: no human review of this sample has happened yet, "
      "so the cross-lens Gumilev extension is a NON-COMPARABLE PILOT and no cross-lens "
      "Gumilev distribution may be published.** Conference Gumilev results (with their "
      "existing reliability packet) remain the only publishable argument-level evidence.")
    a("")
    a("**Renou gate: BINDING and unchanged.** The Renou layer's measured precision "
      "limitations (`docs/renou-precision-audit.md`: title-regex method, unanchored "
      "Cyrillic substrings, 57.3% conference / 10.0% archive coverage) travel with every "
      "crosswalk row that touches `renou_state`/`renou_register`; a classification "
      "suggestion is not an accepted assignment, and the existing gold-review gate is "
      "unmodified by H1897.")
    a("")
    a("No model-only score counts as human validation; a crosswalk or pilot proposal can "
      "only become `accepted` through a recorded reviewer decision "
      "(`validate_crosswalk` enforces a `reviewer:` note for any accepted row).")
    a("")
    a("_Dr. Mārcis Gasūns_")
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": hashed into the comparison-package manifests (H2573).
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Entry point: run against the real adapters
# ---------------------------------------------------------------------------

def build_full_database() -> sqlite3.Connection:
    from . import build
    from .adapters import bvp, conferences, indology_l, nagari, vk_ors

    conn = build.create_connection(":memory:")
    build.build_schema(conn)
    build.seed_taxonomy_schemes(conn)
    for corpus_id, adapter in (
        ("conferences", conferences),
        ("nagari", nagari),
        ("vk_ors", vk_ors),
        ("indology_l", indology_l),
        ("bvp", bvp),
    ):
        fixture = adapter.build_fixture()
        if corpus_id == "conferences":
            conferences.insert_persons(conn, fixture)
        if corpus_id == "nagari":
            nagari.insert_extra_schemes(conn, fixture)
        build.populate_corpus(conn, fixture)
    return conn


def main() -> int:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    conn = build_full_database()
    before = native_assignment_snapshot(conn)
    crosswalk_inserted = apply_crosswalk_assignments(conn)
    pilot_inserted = run_argument_level_pilot(conn)
    roundtrip_errors = verify_native_roundtrip(conn, before)
    sample = build_review_sample(conn)
    write_review_sample(sample)
    write_validity_report(conn, sample, roundtrip_errors, crosswalk_inserted, pilot_inserted)
    print(f"native assignments: {len(before)}")
    print(f"crosswalk-derived assignments inserted: {crosswalk_inserted}")
    print(f"pilot argument_level proposals inserted: {pilot_inserted}")
    print(f"round-trip: {'PASSED' if not roundtrip_errors else 'FAILED'}")
    print(f"review sample rows: {len(sample)} -> {SAMPLE_PATH}")
    print(f"validity report -> {REPORT_PATH}")
    return 1 if roundtrip_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
