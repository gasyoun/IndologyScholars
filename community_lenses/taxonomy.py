"""Versioned codebook contracts + the H1897 crosswalk/inventory layer.

Each codebook in ``community_lenses/codebooks/`` is a CSV with a fixed column
contract (label_id, label, definition, inclusion, exclusion, examples,
parent_label_id, status, version). H1893 populated the six shell axes;
H1897 adds:

- ``intellectual_content.csv`` — the canonical shared content axis named in
  ARCHITECTURE's planned layout. It carries H1893's ``shared_topic`` label set
  forward unchanged (same label_ids, so existing assignments stay valid) plus
  a ``not_applicable`` row; ``shared_topic.csv`` stays on disk untouched as the
  frozen H1893 predecessor, and the crosswalk records the exact identity
  mapping between the two.
- ``taxonomy_crosswalk.csv`` — the many-to-many adjudication of every
  source-native label and Renou state/register against the shared axes.
- the scheme/label inventory functions the crosswalk is validated against.

Crosswalk relation semantics (direction matters):

- ``exact``  — source and target label denote the same concept.
- ``broad``  — the source label's extension is BROADER than the target's
  (source ⊃ target).
- ``narrow`` — the source label's extension is NARROWER than the target's
  (source ⊂ target).
- ``related`` — genuine overlap/associative affinity, neither containment nor
  identity. Per the handoff rule, broad historical affinity (e.g. a Renou
  register vs. a topic) is ``related``, never ``exact``.
- ``unmapped`` — an explicit adjudicated decision that no defensible mapping
  into the considered target scheme exists. Unmapped rows keep the considered
  ``target_scheme`` and carry an EMPTY ``target_label``.

Crosswalking never rewrites, renames, or deletes a source-native label:
shared assignments derived from these rows are additional assertions layered
next to the native ones (ARCHITECTURE principle 6).
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

CODEBOOK_NAMES = (
    "native_topic",
    "shared_topic",
    "intellectual_content",
    "community_function",
    "renou_state",
    "renou_register",
    "argument_level",
)

REQUIRED_COLUMNS = (
    "label_id",
    "label",
    "definition",
    "inclusion",
    "exclusion",
    "examples",
    "parent_label_id",
    "status",
    "version",
)

STATUS_VALUES = ("active", "deprecated", "proposed")

CODEBOOKS_DIR = Path(__file__).resolve().parent / "codebooks"


class CodebookError(ValueError):
    pass


def codebook_path(name: str) -> Path:
    if name not in CODEBOOK_NAMES:
        raise CodebookError(f"unknown codebook {name!r}; expected one of {CODEBOOK_NAMES}")
    return CODEBOOKS_DIR / f"{name}.csv"


def load_codebook(name: str) -> list[dict]:
    path = codebook_path(name)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            raise CodebookError(
                f"{path.name} columns {reader.fieldnames} do not match the "
                f"required contract {list(REQUIRED_COLUMNS)}"
            )
        return list(reader)


def _all_label_ids() -> set[str]:
    """Union of label_ids across every codebook.

    ``parent_label_id`` may point either within the same codebook (a
    sub-label of a broader one) or into a coarser sibling codebook (e.g. a
    ``renou_register`` row's parent is a ``renou_state`` label) — both are
    legitimate, so parent existence is checked against this combined set.
    """
    ids: set[str] = set()
    for codebook_name in CODEBOOK_NAMES:
        try:
            rows = load_codebook(codebook_name)
        except (CodebookError, FileNotFoundError):
            # A sibling codebook file may legitimately be absent (e.g. a test
            # exercising a single codebook in isolation); a missing sibling
            # just means its labels are not available as parent targets.
            continue
        for row in rows:
            ids.add(row["label_id"])
    return ids


def validate_codebook(name: str) -> list[str]:
    """Return contract violations for one codebook; empty means it is valid."""
    errors: list[str] = []
    try:
        rows = load_codebook(name)
    except CodebookError as exc:
        return [str(exc)]

    all_ids = _all_label_ids()
    seen_ids: set[str] = set()
    seen_versions: set[str] = set()
    for row in rows:
        label_id = row["label_id"]
        if not label_id:
            errors.append(f"{name}: row with empty label_id")
            continue
        if label_id in seen_ids:
            errors.append(f"{name}: duplicate label_id {label_id!r}")
        seen_ids.add(label_id)

        if not row["label"]:
            errors.append(f"{name}: label_id {label_id!r} has empty label")
        if not row["version"]:
            errors.append(f"{name}: label_id {label_id!r} has empty version")
        else:
            seen_versions.add(row["version"])
        if row["status"] not in STATUS_VALUES:
            errors.append(
                f"{name}: label_id {label_id!r} has unknown status {row['status']!r}"
            )
        parent = row.get("parent_label_id")
        if parent and parent not in all_ids:
            errors.append(
                f"{name}: label_id {label_id!r} has dangling parent_label_id {parent!r}"
            )

    return errors


def validate_all_codebooks() -> dict[str, list[str]]:
    return {name: validate_codebook(name) for name in CODEBOOK_NAMES}


def codebook_version(name: str) -> str:
    """A codebook's declared version is the single version shared by all its rows."""
    rows = load_codebook(name)
    versions = {row["version"] for row in rows if row["version"]}
    if len(versions) > 1:
        raise CodebookError(
            f"{name} mixes versions within one file: {sorted(versions)}; "
            "bump via a new version for all rows or split the codebook"
        )
    return next(iter(versions), "0.0.0")


# ---------------------------------------------------------------------------
# H1897: scheme inventory, native-label inventory, and the taxonomy crosswalk
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

CROSSWALK_PATH = CODEBOOKS_DIR / "taxonomy_crosswalk.csv"
CROSSWALK_VERSION = "1.0.0"

CROSSWALK_COLUMNS = (
    "source_scheme",
    "source_label",
    "target_scheme",
    "target_label",
    "mapping_relation",
    "rationale",
    "evidence_count",
    "review_status",
    "version",
)

MAPPING_RELATIONS = ("exact", "broad", "narrow", "related", "unmapped")
CROSSWALK_REVIEW_STATUSES = ("pending", "accepted", "rejected", "not_applicable")

# The shared axes crosswalk rows may target. shared_topic is deliberately NOT a
# target: it is superseded by intellectual_content and appears only as a
# source scheme (the identity block that records the supersession).
CROSSWALK_TARGET_SCHEMES = ("intellectual_content", "community_function", "renou_state")

# Every independent taxonomy_scheme the comparison layer knows about, with
# provenance and version — the frozen inventory the handoff requires. Schemes
# whose ``codebook`` is None have no community_lenses codebook CSV of their
# own: their labels live in the named source asset and are enumerated by
# ``native_label_inventory()`` below. ``crosswalk_required`` marks the schemes
# whose every label must have at least one adjudicated crosswalk row.
SCHEME_INVENTORY = {
    "native_topic": {
        "kind": "per-source namespace codebook",
        "codebook": "native_topic",
        "provenance": "community_lenses/codebooks/native_topic.csv (H1893)",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "nagari_native_taxonomy": {
        "kind": "source-native controlled taxonomy",
        "codebook": None,
        "provenance": "nagari/nagari_group_archive/taxonomy.py PARENTS (reused verbatim)",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "conferences_theme_l1": {
        "kind": "source-native controlled taxonomy (disciplinary rubric)",
        "codebook": None,
        "provenance": "analytics_output/theme_codes_final_v2.csv column l1",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "conferences_theme_l2": {
        "kind": "source-native controlled taxonomy (period axis)",
        "codebook": None,
        "provenance": "analytics_output/theme_codes_final_v2.csv column l2",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "conferences_theme_l3": {
        "kind": "source-native controlled taxonomy (evidence-medium axis)",
        "codebook": None,
        "provenance": "analytics_output/theme_codes_final_v2.csv column l3",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "conferences_theme_l4": {
        "kind": "source-native controlled taxonomy (mode axis)",
        "codebook": None,
        "provenance": "analytics_output/theme_codes_final_v2.csv column l4",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "conferences_meso": {
        "kind": "source-native controlled taxonomy (meso codes)",
        "codebook": None,
        "provenance": "analytics_output/meso_codes_deepseek.csv columns meso_codes + proposed_meso",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "renou_state": {
        "kind": "independent historical-linguistic scheme (Renou état)",
        "codebook": "renou_state",
        "provenance": "curation/renou_conference_rules.csv via generate_renou_layer.py (H1893 codebook)",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "renou_register": {
        "kind": "independent historical-linguistic scheme (Renou register)",
        "codebook": "renou_register",
        "provenance": "curation/renou_conference_rules.csv via generate_renou_layer.py (H1893 codebook)",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "shared_topic": {
        "kind": "superseded shared content axis (H1893 predecessor of intellectual_content)",
        "codebook": "shared_topic",
        "provenance": "community_lenses/codebooks/shared_topic.csv (H1893; frozen)",
        "coverage": "available",
        "crosswalk_required": True,
    },
    "intellectual_content": {
        "kind": "shared axis (what the item is about)",
        "codebook": "intellectual_content",
        "provenance": "community_lenses/codebooks/intellectual_content.csv (H1897)",
        "coverage": "available",
        "crosswalk_required": False,
    },
    "community_function": {
        "kind": "shared axis (what the item does in its medium)",
        "codebook": "community_function",
        "provenance": "community_lenses/codebooks/community_function.csv (H1893, extended H1897)",
        "coverage": "available",
        "crosswalk_required": False,
    },
    "argument_level": {
        "kind": "shared Gumilev argument-level scale (canonical field argument_level; gumilyov_level is a legacy alias)",
        "codebook": "argument_level",
        "provenance": "community_lenses/codebooks/argument_level.csv (H1893) + analytics_output/gumilyov_scale.csv",
        "coverage": "available",
        "crosswalk_required": False,
    },
    "indology_l_atlas_topic": {
        "kind": "source-native taxonomy (INDOLOGY-L Atlas topic profiles)",
        "codebook": None,
        "provenance": "gasyoun/IndologyArchiveAtlas feed (blocked on H1894; adapter unavailable)",
        "coverage": "unavailable",
        "crosswalk_required": False,
    },
    "indology_l_atlas_function": {
        "kind": "source-native taxonomy (INDOLOGY-L Atlas list functions)",
        "codebook": None,
        "provenance": "gasyoun/IndologyArchiveAtlas feed (blocked on H1894; adapter unavailable)",
        "coverage": "unavailable",
        "crosswalk_required": False,
    },
    "bvp_native": {
        "kind": "source-native taxonomy (BVP native categories)",
        "codebook": None,
        "provenance": "no native category scheme observed in the H1896 partial acquisition; "
        "namespace reserved as native_topic row bvp:native_category (status=proposed)",
        "coverage": "unavailable",
        "crosswalk_required": False,
    },
}

_MESO_SPLIT = re.compile(r"[;,|\s]+")


def _nagari_native_labels() -> list[str]:
    """The nagari group's own two-level taxonomy labels, read from its code (never re-typed)."""
    nagari_pkg_dir = REPO_ROOT / "nagari"
    if str(nagari_pkg_dir) not in sys.path:
        sys.path.insert(0, str(nagari_pkg_dir))
    from nagari_group_archive import taxonomy as nagari_taxonomy  # noqa: PLC0415

    return sorted(
        f"{parent}/{child}"
        for parent, children in nagari_taxonomy.PARENTS.items()
        for child in children
    )


def _theme_code_labels() -> dict[str, Counter]:
    counters: dict[str, Counter] = {f"conferences_theme_l{n}": Counter() for n in (1, 2, 3, 4)}
    path = REPO_ROOT / "analytics_output" / "theme_codes_final_v2.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for n in (1, 2, 3, 4):
                value = (row.get(f"l{n}") or "").strip()
                if value:
                    counters[f"conferences_theme_l{n}"][value] += 1
    return counters


def _meso_labels() -> Counter:
    counter: Counter = Counter()
    path = REPO_ROOT / "analytics_output" / "meso_codes_deepseek.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for code in _MESO_SPLIT.split(row.get("meso_codes") or ""):
                code = code.strip()
                if code:
                    counter[code] += 1
            proposed = (row.get("proposed_meso") or "").strip()
            if proposed:
                counter[proposed] += 1
    return counter


def native_label_inventory() -> dict[str, dict[str, int]]:
    """Frozen inventory: every crosswalk-required scheme -> {label: evidence_count}.

    Evidence counts come from the actual source assets (assignment rows in the
    analytics CSVs, codebook rows for codebook-backed schemes). Codebook-backed
    schemes report a count of 0 for labels with no per-record source file here;
    the crosswalk CSV carries the frozen per-snapshot counts.
    """
    inventory: dict[str, dict[str, int]] = {}

    theme_counters = _theme_code_labels()
    for scheme, counter in theme_counters.items():
        inventory[scheme] = dict(sorted(counter.items()))

    inventory["conferences_meso"] = dict(sorted(_meso_labels().items()))
    inventory["nagari_native_taxonomy"] = {label: 0 for label in _nagari_native_labels()}

    for scheme, meta in SCHEME_INVENTORY.items():
        if not meta["crosswalk_required"] or scheme in inventory:
            continue
        codebook = meta["codebook"]
        if codebook is None:
            raise CodebookError(
                f"scheme {scheme!r} is crosswalk_required but has neither a codebook "
                "nor an inventory reader"
            )
        inventory[scheme] = {row["label_id"]: 0 for row in load_codebook(codebook)}

    return inventory


class CrosswalkError(ValueError):
    pass


def load_crosswalk() -> list[dict]:
    with CROSSWALK_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(CROSSWALK_COLUMNS):
            raise CrosswalkError(
                f"{CROSSWALK_PATH.name} columns {reader.fieldnames} do not match "
                f"the required contract {list(CROSSWALK_COLUMNS)}"
            )
        return list(reader)


def validate_crosswalk(rows: list[dict] | None = None) -> list[str]:
    """Contract violations for the crosswalk; empty list means it is valid.

    Checks every row for: known source/target schemes, allowed relation and
    review status, non-empty rationale and version, integer evidence_count,
    empty target_label exactly when relation is ``unmapped``, target labels
    that exist in the target codebook, and no silent acceptance (a row may be
    ``accepted`` only when a reviewer decision is recorded in the rationale).
    Then checks coverage: every label of every crosswalk-required scheme in
    ``native_label_inventory()`` has at least one row.
    """
    if rows is None:
        rows = load_crosswalk()
    errors: list[str] = []

    target_labels = {
        scheme: {row["label_id"] for row in load_codebook(scheme)}
        for scheme in CROSSWALK_TARGET_SCHEMES
    }
    inventory = native_label_inventory()
    known_sources = set(SCHEME_INVENTORY)

    seen_keys: set[tuple] = set()
    covered: dict[str, set[str]] = {scheme: set() for scheme in inventory}

    for i, row in enumerate(rows, start=2):  # 1-based + header line
        where = f"row {i} ({row.get('source_scheme')}:{row.get('source_label')})"
        source_scheme = row.get("source_scheme") or ""
        source_label = row.get("source_label") or ""
        relation = row.get("mapping_relation") or ""
        target_scheme = row.get("target_scheme") or ""
        target_label = row.get("target_label") or ""

        key = (source_scheme, source_label, target_scheme, target_label)
        if key in seen_keys:
            errors.append(f"{where}: duplicate crosswalk key {key}")
        seen_keys.add(key)

        if source_scheme not in known_sources:
            errors.append(f"{where}: unknown source_scheme {source_scheme!r}")
        if not source_label:
            errors.append(f"{where}: empty source_label")
        if relation not in MAPPING_RELATIONS:
            errors.append(f"{where}: unknown mapping_relation {relation!r}")
        if row.get("review_status") not in CROSSWALK_REVIEW_STATUSES:
            errors.append(f"{where}: unknown review_status {row.get('review_status')!r}")
        if not (row.get("rationale") or "").strip():
            errors.append(f"{where}: empty rationale")
        if not (row.get("version") or "").strip():
            errors.append(f"{where}: empty version")
        try:
            int(row.get("evidence_count") or "")
        except ValueError:
            errors.append(f"{where}: evidence_count {row.get('evidence_count')!r} is not an integer")

        if target_scheme not in CROSSWALK_TARGET_SCHEMES:
            errors.append(f"{where}: target_scheme {target_scheme!r} is not a shared crosswalk target")
        if relation == "unmapped":
            if target_label:
                errors.append(f"{where}: unmapped row must carry an empty target_label")
        else:
            if target_scheme in target_labels and target_label not in target_labels[target_scheme]:
                errors.append(
                    f"{where}: target_label {target_label!r} not present in codebook {target_scheme!r}"
                )
        if row.get("review_status") == "accepted" and "reviewer:" not in (row.get("rationale") or ""):
            errors.append(
                f"{where}: review_status=accepted without a recorded 'reviewer:' decision in the "
                "rationale — model/adjudicator confidence alone cannot accept a mapping"
            )

        if source_scheme in covered and source_label:
            covered[source_scheme].add(source_label)

    for scheme, labels in inventory.items():
        missing = sorted(set(labels) - covered.get(scheme, set()))
        if missing:
            errors.append(
                f"coverage: scheme {scheme!r} labels with no crosswalk row (add explicit "
                f"unmapped rows if no mapping is justified): {missing}"
            )

    return errors


def crosswalk_summary(rows: list[dict] | None = None) -> dict:
    """Relation/review/unmapped counts for the validity report."""
    if rows is None:
        rows = load_crosswalk()
    relation_counts = Counter(row["mapping_relation"] for row in rows)
    review_counts = Counter(row["review_status"] for row in rows)
    per_scheme = Counter(row["source_scheme"] for row in rows)
    unmapped_labels = sorted(
        {
            (row["source_scheme"], row["source_label"])
            for row in rows
            if row["mapping_relation"] == "unmapped"
        }
    )
    return {
        "total_rows": len(rows),
        "relation_counts": dict(sorted(relation_counts.items())),
        "review_counts": dict(sorted(review_counts.items())),
        "rows_per_source_scheme": dict(sorted(per_scheme.items())),
        "unmapped_labels": unmapped_labels,
    }
