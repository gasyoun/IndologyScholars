"""Cross-lens person identity linking — H1898 Step 8.

Builds the reviewed person-identity layer over the H1893 shared contract:

- inventories every source-local name/account identifier from the adapter
  fixtures WITHOUT normalization loss (``name_as_source`` is preserved
  byte-for-byte; normalization exists only as a documented matching method);
- reuses existing conference person IDs (``conferences:PERS_*``), the
  authority registry (``authority_ids.json``) and the manually accepted
  aliases (``curation/person_aliases.csv``);
- auto-accepts ONLY an exact authority-ID match; every exact-name,
  accepted-alias, transliteration or surname-initial match is a *candidate*
  routed to ``analytics_output/community_lenses/review/person_match_candidates.csv``
  and never linked without a manual decision;
- reads reviewed decisions from ``curation/community_person_links.csv``
  (accepted / rejected / ambiguous, each with evidence locator, match method,
  reviewer, reviewed date, confidence rationale and decision version) and
  applies ONLY accepted links to ``record_name.person_id`` +
  ``person_match_assertion``;
- preserves negative decisions so rejected pairs do not recur as candidates.

Nationality, ideology, reputation and demographic attributes are never
inferred from names, scripts, or membership — matching is string/authority
evidence only.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PERSON_LINKS_PATH = REPO_ROOT / "curation" / "community_person_links.csv"
CANDIDATES_PATH = (
    REPO_ROOT
    / "analytics_output"
    / "community_lenses"
    / "review"
    / "person_match_candidates.csv"
)
ALIASES_PATH = REPO_ROOT / "curation" / "person_aliases.csv"
AUTHORITY_IDS_PATH = REPO_ROOT / "authority_ids.json"

DECISION_VERSION = "h1898-identity-1.0.0"

# The ONLY method allowed to link without a manual review decision.
AUTO_ACCEPT_METHODS = ("authority_exact",)

# Candidate-generation methods. None of these may auto-accept.
CANDIDATE_METHODS = (
    "alias_exact",
    "name_exact",
    "translit_exact",
    "surname_initial",
    "manual",
)

DECISIONS = ("accepted", "rejected", "ambiguous")

# A decision row's grain is the ATTESTED IDENTITY — (corpus, exact source
# spelling, source account id) — not one message: a reviewed link covers
# every mention of that exact spelling+account, and record_name keeps the
# source-local display untouched either way.
LINK_COLUMNS = [
    "corpus_id",
    "name_as_source",
    "source_account_id",
    "person_id",
    "decision",
    "method",
    "evidence_locator",
    "mention_count",
    "reviewer",
    "reviewed_date",
    "confidence_rationale",
    "decision_version",
    "exportable",
]

CANDIDATE_COLUMNS = [
    "corpus_id",
    "name_as_source",
    "source_account_id",
    "candidate_person_id",
    "candidate_display_name",
    "method",
    "evidence",
    "mention_count",
    "first_seen",
    "last_seen",
    "sample_record_ids",
    "prior_decision",
]


class IdentityError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Composed database build (adapters + persons + native schemes), duplicate-safe
# ---------------------------------------------------------------------------

def dedupe_fixture(fixture: dict) -> tuple[dict, dict]:
    """Drop duplicate records (same corpus_id+source_record_id keeps its FIRST
    occurrence) and the dependent rows of the dropped duplicates.

    The live nagari mbox contains a handful of genuinely duplicated
    Message-IDs; ``build.populate_corpus`` (correctly) refuses them with a
    UNIQUE violation — the exact full-nagari.db crash recorded in
    FINDINGS §314 / IndologyScholars#169. Identity work only needs each
    record once, so the reviewed layer drops the later duplicates and REPORTS
    the drop instead of crashing or silently keeping both.
    Returns (deduped_fixture, drop_report).
    """
    records = fixture.get("records", [])
    seen: set[tuple[str, str]] = set()
    kept_ids: set[str] = set()
    dropped_ids: list[str] = []
    kept_records = []
    for record in records:
        key = (record["corpus_id"], record["source_record_id"])
        if key in seen:
            dropped_ids.append(record["record_id"])
            continue
        seen.add(key)
        kept_ids.add(record["record_id"])
        kept_records.append(record)

    dropped_set = set(dropped_ids)
    out = dict(fixture)
    out["records"] = kept_records

    def _keep_names(rows: list[dict]) -> list[dict]:
        kept, seen_keys = [], set()
        for row in rows:
            if row["record_id"] in dropped_set:
                continue
            key = (row["record_id"], row["ordinal"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            kept.append(row)
        return kept

    def _keep_unique(rows: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
        kept, seen_keys = [], set()
        for row in rows:
            ref = row.get("record_id") or row.get("subject_record_id")
            if ref in dropped_set:
                continue
            obj = row.get("object_record_id")
            if obj is not None and obj in dropped_set:
                continue
            key = tuple(row.get(f) for f in key_fields)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            kept.append(row)
        return kept

    out["record_names"] = _keep_names(fixture.get("record_names", []))
    out["record_relations"] = _keep_unique(
        fixture.get("record_relations", []),
        ("subject_record_id", "predicate", "object_record_id"),
    )
    out["classification_assignments"] = _keep_unique(
        fixture.get("classification_assignments", []),
        ("record_id", "scheme_id", "label_id"),
    )
    report = {
        "corpus_id": fixture["corpus"]["corpus_id"],
        "records_total": len(records),
        "records_dropped_duplicate": len(dropped_ids),
        "dropped_record_ids": dropped_ids,
    }
    return out, report


def build_reviewed_database(fixtures: dict[str, dict] | None = None) -> tuple[sqlite3.Connection, list[dict]]:
    """Build the full lens database the way classify.build_full_database does
    (persons + native schemes included), but duplicate-safe and reporting
    every dropped row. Returns (conn, drop_reports)."""
    from . import build
    from .adapters import bvp, conferences, indology_l, nagari, vk_ors

    adapters = {
        "conferences": conferences,
        "nagari": nagari,
        "vk_ors": vk_ors,
        "indology_l": indology_l,
        "bvp": bvp,
    }
    conn = build.create_connection(":memory:")
    build.build_schema(conn)
    build.seed_taxonomy_schemes(conn)
    reports: list[dict] = []
    for corpus_id, adapter in adapters.items():
        fixture = (fixtures or {}).get(corpus_id) or adapter.build_fixture()
        fixture, report = dedupe_fixture(fixture)
        reports.append(report)
        if corpus_id == "conferences":
            adapters["conferences"].insert_persons(conn, fixture)
        if corpus_id == "nagari" and hasattr(adapter, "insert_extra_schemes"):
            adapter.insert_extra_schemes(conn, fixture)
        build.populate_corpus(conn, fixture)
    conn.commit()
    return conn, reports


# ---------------------------------------------------------------------------
# Matching normalization (a documented METHOD; storage stays verbatim)
# ---------------------------------------------------------------------------

def normalize_for_match(name: str) -> str:
    """NFC + casefold + collapse whitespace + strip trailing punctuation.

    Used ONLY to compare two spellings; the stored ``name_as_source`` is
    never rewritten.
    """
    text = unicodedata.normalize("NFC", name).casefold()
    text = " ".join(text.replace(",", " ").replace(".", ". ").split())
    return text.strip(" .")


# Deliberately small, surname-oriented Latin<-Cyrillic comparison table.
# This exists to SURFACE candidates for manual review, never to accept them.
_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def translit_cyr_to_lat(text: str) -> str:
    return "".join(_CYR_TO_LAT.get(ch, ch) for ch in normalize_for_match(text))


def surname_of(name: str) -> str:
    """Best-effort surname token for candidate surfacing (longest token)."""
    tokens = [t for t in normalize_for_match(name).replace(". ", " ").split() if len(t) > 1]
    if not tokens:
        return ""
    return max(tokens, key=len)


# ---------------------------------------------------------------------------
# Existing registries (read-only inputs)
# ---------------------------------------------------------------------------

def load_authority_ids(path: Path = AUTHORITY_IDS_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("persons", {})


def load_accepted_aliases(path: Path = ALIASES_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("status") == "accepted"]


def conference_persons(conn: sqlite3.Connection) -> dict[str, dict]:
    """person_id -> person row for the conference-owned person registry."""
    return {
        row["person_id"]: dict(row)
        for row in conn.execute(
            "SELECT * FROM person WHERE person_id LIKE 'conferences:%'"
        )
    }


def source_identities(conn: sqlite3.Connection, corpus_ids: tuple[str, ...] = ("nagari", "vk_ors", "bvp", "indology_l")) -> list[dict]:
    """Inventory of source-local identities (non-conference corpora).

    Preserves the attested display, account id, record date and snapshot —
    nothing is merged or rewritten here.
    """
    placeholders = ", ".join("?" for _ in corpus_ids)
    rows = conn.execute(
        f"""SELECT r.corpus_id, rn.record_id, rn.ordinal, rn.role,
                   rn.name_as_source, rn.affiliation_as_source,
                   rn.source_account_id, rn.person_id,
                   r.created_at, r.source_snapshot_id
            FROM record_name rn JOIN record r ON r.record_id = rn.record_id
            WHERE r.corpus_id IN ({placeholders})
            ORDER BY r.corpus_id, rn.record_id, rn.ordinal""",
        corpus_ids,
    )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def _alias_index(aliases: list[dict]) -> dict[str, str]:
    """normalized alias/target spelling -> canonical target_name."""
    index: dict[str, str] = {}
    for row in aliases:
        target = row["target_name"]
        index.setdefault(normalize_for_match(target), target)
        index.setdefault(normalize_for_match(row["alias_name"]), target)
    return index


def _person_name_index(persons: dict[str, dict]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for person_id, person in persons.items():
        index.setdefault(normalize_for_match(person["display_name"]), []).append(person_id)
    return index


def name_tokens(name: str) -> frozenset[str]:
    """Order-insensitive, transliterated token set for comparison.

    Russian names appear both as "Surname First Patronymic" (conference
    programmes) and "First Surname" (mail/group displays); token-set
    comparison is the documented matching method that bridges the two.
    Initials (single letters) are dropped — they carry too little signal
    for candidate generation and never auto-accept anyway.
    """
    tokens = normalize_for_match(name).replace(". ", " ").replace(".", " ").split()
    return frozenset(translit_cyr_to_lat(t) for t in tokens if len(t) > 1)


def identity_key(row: dict) -> tuple[str, str, str]:
    return (
        row["corpus_id"],
        row["name_as_source"],
        row.get("source_account_id") or "",
    )


def prior_decisions(links: list[dict]) -> dict[tuple, str]:
    """(identity grain, person_id) -> decision, so negatives persist."""
    return {(identity_key(row), row["person_id"]): row["decision"] for row in links}


def aggregate_identities(identities: list[dict]) -> list[dict]:
    """Collapse per-mention rows to the attested-identity grain, keeping
    mention counts, date span and sample record ids as review evidence."""
    grouped: dict[tuple, dict] = {}
    for mention in identities:
        key = identity_key(mention)
        entry = grouped.get(key)
        created = mention.get("created_at") or ""
        if entry is None:
            grouped[key] = {
                "corpus_id": mention["corpus_id"],
                "name_as_source": mention["name_as_source"],
                "source_account_id": mention.get("source_account_id") or "",
                "person_id": mention.get("person_id"),
                "mention_count": 1,
                "first_seen": created,
                "last_seen": created,
                "sample_record_ids": [mention["record_id"]],
            }
            continue
        entry["mention_count"] += 1
        if created:
            if not entry["first_seen"] or created < entry["first_seen"]:
                entry["first_seen"] = created
            if created > entry["last_seen"]:
                entry["last_seen"] = created
        if len(entry["sample_record_ids"]) < 3:
            entry["sample_record_ids"].append(mention["record_id"])
    return list(grouped.values())


def generate_candidates(
    identities: list[dict],
    persons: dict[str, dict],
    aliases: list[dict],
    authority_ids: dict[str, dict] | None = None,
    reviewed_links: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (auto_accepts, candidates).

    ``auto_accepts`` holds ONLY authority-exact matches (shared ORCID or
    Wikidata identifier attested on both sides). Everything else — exact
    name, accepted-alias spelling, transliteration, surname+initial — is a
    candidate for manual review.
    """
    authority_ids = authority_ids or {}
    prior = prior_decisions(reviewed_links or [])

    name_index = _person_name_index(persons)
    alias_names = _alias_index(aliases)

    # authority id -> conference person_id (via authority_ids.json, keyed by bare PERS_*)
    authority_index: dict[str, str] = {}
    for bare_pid, meta in authority_ids.items():
        for key in ("orcid", "wikidata"):
            value = meta.get(key)
            if value:
                authority_index[f"{key}:{value}"] = f"conferences:{bare_pid}"

    # person_id -> set of comparison token-sets (Cyrillic display + any
    # authority-registered Latin form), all transliterated to one space.
    person_token_sets: dict[str, list[frozenset[str]]] = {}
    for person_id, person in persons.items():
        forms = [person["display_name"]]
        bare = person_id.removeprefix("conferences:")
        latin = (authority_ids.get(bare) or {}).get("preferred_latin_name")
        if latin:
            forms.append(latin)
        person_token_sets[person_id] = [name_tokens(f) for f in forms if name_tokens(f)]

    auto_accepts: list[dict] = []
    candidates: list[dict] = []
    seen: set[tuple] = set()

    def emit(identity: dict, person_id: str, method: str, evidence: str) -> None:
        key = (identity_key(identity), person_id)
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "corpus_id": identity["corpus_id"],
                "name_as_source": identity["name_as_source"],
                "source_account_id": identity.get("source_account_id") or "",
                "candidate_person_id": person_id,
                "candidate_display_name": persons[person_id]["display_name"],
                "method": method,
                "evidence": evidence,
                "mention_count": identity["mention_count"],
                "first_seen": (identity.get("first_seen") or "")[:10],
                "last_seen": (identity.get("last_seen") or "")[:10],
                "sample_record_ids": " ".join(identity["sample_record_ids"]),
                "prior_decision": prior.get(key, ""),
            }
        )

    for identity in aggregate_identities(identities):
        if identity.get("person_id"):
            continue  # already linked (e.g. by an earlier reviewed pass)
        name = identity["name_as_source"]
        norm = normalize_for_match(name)

        # 1. authority-exact — the only auto-accept path. A source-side
        # authority id would have to be attested in the source record itself;
        # none of the current corpora carry one, so this stays empty unless a
        # future adapter supplies `authority:<scheme>:<id>` in
        # source_account_id.
        account = identity.get("source_account_id") or ""
        if account.startswith("authority:"):
            auth_key = account.removeprefix("authority:")
            person_id = authority_index.get(auth_key)
            if person_id:
                auto_accepts.append(
                    {
                        "corpus_id": identity["corpus_id"],
                        "name_as_source": name,
                        "source_account_id": account,
                        "person_id": person_id,
                        "decision": "accepted",
                        "method": "authority_exact",
                        "evidence_locator": f"authority_ids.json:{auth_key}",
                        "mention_count": identity["mention_count"],
                        "reviewer": "",
                        "reviewed_date": "",
                        "confidence_rationale": "exact shared authority identifier",
                        "decision_version": DECISION_VERSION,
                        "exportable": "no",
                    }
                )
                continue

        # 2. exact spelling of an existing person display name
        for person_id in name_index.get(norm, []):
            emit(identity, person_id, "name_exact", f"exact normalized spelling match: {norm!r}")

        # 3. exact spelling of an accepted alias (conference curation)
        target = alias_names.get(norm)
        if target:
            for person_id in name_index.get(normalize_for_match(target), []):
                emit(
                    identity,
                    person_id,
                    "alias_exact",
                    f"matches accepted conference alias -> {target!r} (person_aliases.csv)",
                )

        # 4./5. order-insensitive transliterated token-set comparison against
        # every person form (Cyrillic display + authority Latin form):
        #   - set equality            -> translit_exact candidate
        #   - 2+-token subset either way -> surname_initial candidate
        # Both are REVIEW-ONLY; nothing here auto-accepts.
        id_tokens = name_tokens(name)
        if len(id_tokens) >= 2:
            for person_id, forms in person_token_sets.items():
                for form_tokens in forms:
                    if id_tokens == form_tokens:
                        emit(
                            identity,
                            person_id,
                            "translit_exact",
                            f"token-set equality: {sorted(id_tokens)!r}",
                        )
                        break
                    if len(form_tokens) >= 2 and (
                        id_tokens <= form_tokens or form_tokens <= id_tokens
                    ):
                        emit(
                            identity,
                            person_id,
                            "surname_initial",
                            f"token subset: {sorted(id_tokens & form_tokens)!r}",
                        )
                        break

    # Every surfaced pair stays in the queue file for audit, annotated with
    # its prior decision; a decided pair (accepted/rejected/ambiguous) is no
    # longer OPEN and must not recur as work — callers select open items via
    # open_candidates().
    return auto_accepts, candidates


def open_candidates(candidates: list[dict]) -> list[dict]:
    return [c for c in candidates if not c["prior_decision"]]


# ---------------------------------------------------------------------------
# Reviewed decisions (curation/community_person_links.csv)
# ---------------------------------------------------------------------------

def load_reviewed_links(path: Path = PERSON_LINKS_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    validate_reviewed_links(rows)
    return rows


def validate_reviewed_links(rows: list[dict]) -> None:
    """Fail-closed validation of the reviewed decision table."""
    for i, row in enumerate(rows, start=2):  # header is line 1
        where = f"community_person_links.csv line {i}"
        missing = [c for c in LINK_COLUMNS if c not in row or row[c] is None]
        if missing:
            raise IdentityError(f"{where}: missing columns {missing}")
        if row["decision"] not in DECISIONS:
            raise IdentityError(f"{where}: bad decision {row['decision']!r}")
        method = row["method"]
        if method not in AUTO_ACCEPT_METHODS + CANDIDATE_METHODS:
            raise IdentityError(f"{where}: unknown method {method!r}")
        if row["decision"] == "accepted":
            if not row["person_id"]:
                raise IdentityError(f"{where}: accepted link without person_id")
            if not row["evidence_locator"]:
                raise IdentityError(f"{where}: accepted link without evidence")
            if method not in AUTO_ACCEPT_METHODS:
                # every non-authority acceptance is a manual review decision
                if not (row["reviewer"] and row["reviewed_date"]):
                    raise IdentityError(
                        f"{where}: {method} acceptance requires reviewer + reviewed_date "
                        "(fuzzy/translit/name matches never auto-accept)"
                    )
            if not row["decision_version"]:
                raise IdentityError(f"{where}: accepted link without decision_version")
            if not row["confidence_rationale"]:
                raise IdentityError(f"{where}: accepted link without confidence_rationale")


def accepted_links(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["decision"] == "accepted"]


def apply_reviewed_links(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Apply ONLY accepted decisions to record_name.person_id (every mention
    of the attested spelling+account) and mirror every decision into
    person_match_assertion. Returns number of record_name rows linked."""
    validate_reviewed_links(rows)
    applied = 0
    status_map = {"accepted": "accepted", "rejected": "rejected", "ambiguous": "pending"}
    for row in rows:
        account = row.get("source_account_id") or ""
        mention_rows = conn.execute(
            """SELECT rn.record_id, rn.ordinal
               FROM record_name rn JOIN record r ON r.record_id = rn.record_id
               WHERE r.corpus_id = ? AND rn.name_as_source = ?
                 AND COALESCE(rn.source_account_id, '') = ?""",
            (row["corpus_id"], row["name_as_source"], account),
        ).fetchall()
        if row["person_id"] and mention_rows:
            first_record = mention_rows[0]["record_id"]
            assertion_id = (
                f"h1898:{row['corpus_id']}:{row['name_as_source']}"
                f"#{account or 'noaccount'}->{row['person_id']}"
            )
            conn.execute(
                """INSERT OR REPLACE INTO person_match_assertion
                   (assertion_id, source_record_id, candidate_person_id, method,
                    score, evidence, status)
                   VALUES (?, ?, ?, ?, NULL, ?, ?)""",
                (
                    assertion_id,
                    first_record,
                    row["person_id"],
                    row["method"],
                    f"{row['evidence_locator']} | reviewer={row['reviewer']} "
                    f"date={row['reviewed_date']} version={row['decision_version']}",
                    status_map[row["decision"]],
                ),
            )
        if row["decision"] == "accepted":
            for mention in mention_rows:
                cur = conn.execute(
                    "UPDATE record_name SET person_id = ? WHERE record_id = ? AND ordinal = ?",
                    (row["person_id"], mention["record_id"], int(mention["ordinal"])),
                )
                applied += cur.rowcount
    conn.commit()
    return applied


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def write_candidates(candidates: list[dict], path: Path = CANDIDATES_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_COLUMNS)
        writer.writeheader()
        writer.writerows(candidates)
    return path


def write_links(rows: list[dict], path: Path = PERSON_LINKS_PATH) -> Path:
    validate_reviewed_links(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LINK_COLUMNS)
        writer.writeheader()
        writer.writerows({c: row.get(c, "") for c in LINK_COLUMNS} for row in rows)
    return path
