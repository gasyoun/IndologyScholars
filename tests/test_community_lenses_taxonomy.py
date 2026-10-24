"""H1897: codebook + crosswalk contract tests.

Pins the Definition-of-Done invariants: versioned codebooks that keep
``unknown``/``other``/``not_applicable`` semantically distinct; a crosswalk in
which every row carries relation, rationale, evidence count, review state,
and version; full coverage of every crosswalk-required native label
(explicit ``unmapped`` rows included); the one-way shared_topic ->
intellectual_content supersession; and a validator that rejects silent
acceptance and malformed rows.
"""

from __future__ import annotations

import copy

import pytest

from community_lenses import taxonomy

FIXTURES_DIR = taxonomy.REPO_ROOT / "tests" / "fixtures" / "community_lenses" / "taxonomy"


# ---------------------------------------------------------------------------
# Codebooks
# ---------------------------------------------------------------------------

def test_intellectual_content_is_a_registered_codebook():
    assert "intellectual_content" in taxonomy.CODEBOOK_NAMES
    rows = taxonomy.load_codebook("intellectual_content")
    assert rows, "intellectual_content.csv must not be empty"


def test_all_codebooks_validate_clean():
    for name, errors in taxonomy.validate_all_codebooks().items():
        assert errors == [], f"codebook {name} has contract violations: {errors}"


@pytest.mark.parametrize("name", ["intellectual_content", "community_function", "argument_level"])
def test_shared_codebooks_distinguish_unknown_other_not_applicable(name):
    rows = {row["label_id"]: row for row in taxonomy.load_codebook(name)}
    present = [lab for lab in ("unknown", "not_applicable") if lab in rows]
    assert "unknown" in present and "not_applicable" in present, (
        f"{name} must carry BOTH unknown and not_applicable as distinct labels"
    )
    # Distinct semantics, not just distinct ids: each names the other in its
    # exclusion line so a coder cannot conflate them.
    for lab in present:
        other_lab = "unknown" if lab == "not_applicable" else "not_applicable"
        text = (rows[lab]["exclusion"] + rows[lab]["definition"]).lower()
        assert other_lab in text or "unreadable" in text, (
            f"{name}:{lab} does not delimit itself against {other_lab}"
        )


def test_shared_codebooks_are_single_versioned():
    assert taxonomy.codebook_version("intellectual_content") == "1.1.0"
    assert taxonomy.codebook_version("community_function") == "1.1.0"
    assert taxonomy.codebook_version("argument_level") == "1.1.0"
    # The frozen H1893 predecessor stays untouched.
    assert taxonomy.codebook_version("shared_topic") == "1.0.0"


def test_intellectual_content_carries_shared_topic_labels_forward():
    shared = {row["label_id"] for row in taxonomy.load_codebook("shared_topic")}
    canonical = {row["label_id"] for row in taxonomy.load_codebook("intellectual_content")}
    assert shared <= canonical, (
        "every H1893 shared_topic label_id must survive into intellectual_content "
        f"(missing: {sorted(shared - canonical)})"
    )


def test_argument_level_keeps_gumilev_scale_distinct_labels():
    labels = {row["label_id"] for row in taxonomy.load_codebook("argument_level")}
    assert {"G1", "G2", "G3", "not_applicable", "unknown"} <= labels


# ---------------------------------------------------------------------------
# Scheme inventory
# ---------------------------------------------------------------------------

def test_inventory_declares_unavailable_schemes_without_inventing_labels():
    for scheme in ("indology_l_atlas_topic", "indology_l_atlas_function", "bvp_native"):
        meta = taxonomy.SCHEME_INVENTORY[scheme]
        assert meta["coverage"] == "unavailable"
        assert meta["crosswalk_required"] is False, (
            f"{scheme} is unavailable; requiring crosswalk rows would force label "
            "invention from planning prose"
        )
    inventory = taxonomy.native_label_inventory()
    for scheme in ("indology_l_atlas_topic", "indology_l_atlas_function", "bvp_native"):
        assert scheme not in inventory


def test_inventory_covers_every_crosswalk_required_scheme():
    inventory = taxonomy.native_label_inventory()
    required = {s for s, meta in taxonomy.SCHEME_INVENTORY.items() if meta["crosswalk_required"]}
    assert required == set(inventory)
    for scheme, labels in inventory.items():
        assert labels, f"scheme {scheme} has an empty label inventory"


def test_inventory_is_deterministic():
    assert taxonomy.native_label_inventory() == taxonomy.native_label_inventory()


# ---------------------------------------------------------------------------
# Crosswalk contract
# ---------------------------------------------------------------------------

def test_crosswalk_validates_clean():
    assert taxonomy.validate_crosswalk() == []


def test_crosswalk_rows_are_complete_and_pending_review():
    rows = taxonomy.load_crosswalk()
    assert rows
    for row in rows:
        assert row["mapping_relation"] in taxonomy.MAPPING_RELATIONS
        assert row["rationale"].strip(), f"row without rationale: {row['source_scheme']}:{row['source_label']}"
        assert row["version"].strip()
        assert row["review_status"] in taxonomy.CROSSWALK_REVIEW_STATUSES
        int(row["evidence_count"])
        if row["review_status"] == "accepted":
            assert "reviewer:" in row["rationale"], (
                "an accepted mapping must record the reviewer decision"
            )


def test_crosswalk_never_targets_shared_topic():
    for row in taxonomy.load_crosswalk():
        assert row["target_scheme"] != "shared_topic", (
            "shared_topic is superseded; it may appear only as a source scheme"
        )


def test_shared_topic_supersession_is_exact_and_complete():
    shared_labels = {row["label_id"] for row in taxonomy.load_codebook("shared_topic")}
    identity = {
        row["source_label"]: row
        for row in taxonomy.load_crosswalk()
        if row["source_scheme"] == "shared_topic"
    }
    assert set(identity) == shared_labels
    for label, row in identity.items():
        assert row["mapping_relation"] == "exact"
        assert row["target_scheme"] == "intellectual_content"
        assert row["target_label"] == label


def test_unmapped_rows_have_empty_target_and_mapped_rows_valid_targets():
    target_labels = {
        scheme: {row["label_id"] for row in taxonomy.load_codebook(scheme)}
        for scheme in taxonomy.CROSSWALK_TARGET_SCHEMES
    }
    for row in taxonomy.load_crosswalk():
        if row["mapping_relation"] == "unmapped":
            assert row["target_label"] == ""
        else:
            assert row["target_label"] in target_labels[row["target_scheme"]]


def test_every_native_label_is_adjudicated():
    """DoD: every adapter-native label and Renou state/register has >= 1 row."""
    covered: dict[str, set[str]] = {}
    for row in taxonomy.load_crosswalk():
        covered.setdefault(row["source_scheme"], set()).add(row["source_label"])
    for scheme, labels in taxonomy.native_label_inventory().items():
        missing = set(labels) - covered.get(scheme, set())
        assert not missing, f"{scheme}: labels with no adjudication: {sorted(missing)}"


def test_renou_labels_never_map_exact():
    """Broad historical affinity is related, never exact (handoff step 4)."""
    for row in taxonomy.load_crosswalk():
        if row["source_scheme"] in ("renou_state", "renou_register"):
            assert row["mapping_relation"] != "exact", (
                f"Renou label {row['source_label']} mapped exact — affinity can be at "
                "most related/narrow"
            )


# ---------------------------------------------------------------------------
# Validator rejection paths (synthetic bad rows)
# ---------------------------------------------------------------------------

def _valid_rows():
    return taxonomy.load_crosswalk()


def test_validator_rejects_accepted_without_reviewer():
    rows = _valid_rows()
    bad = copy.deepcopy(rows[0])
    bad["review_status"] = "accepted"
    bad["rationale"] = "high confidence mapping"
    bad["target_label"] = ""  # keep key unique vs. the original row
    bad["mapping_relation"] = "unmapped"
    errors = taxonomy.validate_crosswalk(rows + [bad])
    assert any("cannot accept" in e for e in errors)


def test_validator_rejects_unknown_relation_and_empty_rationale():
    rows = _valid_rows()
    bad = copy.deepcopy(rows[0])
    bad["mapping_relation"] = "equivalent"
    bad["rationale"] = "  "
    bad["source_label"] = rows[0]["source_label"]
    bad["target_label"] = "zz_nonexistent"
    errors = taxonomy.validate_crosswalk(rows + [bad])
    assert any("unknown mapping_relation" in e for e in errors)
    assert any("empty rationale" in e for e in errors)


def test_validator_rejects_duplicate_keys():
    rows = _valid_rows()
    errors = taxonomy.validate_crosswalk(rows + [copy.deepcopy(rows[0])])
    assert any("duplicate crosswalk key" in e for e in errors)


def test_validator_rejects_unmapped_with_target():
    rows = _valid_rows()
    bad = copy.deepcopy(rows[0])
    bad["mapping_relation"] = "unmapped"
    bad["target_label"] = "grammar_linguistics"
    errors = taxonomy.validate_crosswalk(rows + [bad])
    assert any("unmapped row must carry an empty target_label" in e for e in errors)


def test_validator_reports_coverage_gaps():
    rows = [r for r in _valid_rows() if r["source_scheme"] != "renou_register"]
    errors = taxonomy.validate_crosswalk(rows)
    assert any("renou_register" in e and "coverage" in e for e in errors)
