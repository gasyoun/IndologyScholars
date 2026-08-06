"""H1899: denominator discipline (V9), figure captions and the claims ledger (V10).

The point of these tests is the FAILURE modes: a metric row that carries a
value without a denominator, an `unavailable` lens rendered as a zero, a
pilot share presented as a population share, an orientation premise promoted
to a measurement, an overlap count that quietly includes pending matches, and
an article claim with no evidence behind it. Each is constructed here as a
synthetic table and must be rejected; the real frozen tables must pass.
"""
from __future__ import annotations

import copy

import pytest

from community_lenses import figures, metrics, report


# ---------------------------------------------------------------------------
# Synthetic fixtures (fast: no adapter build)
# ---------------------------------------------------------------------------

def _row(**overrides) -> dict:
    row = {
        "metric_id": "activity.conferences.2018-2025",
        "lens": "conferences",
        "native_unit": "presentation",
        "period": "2018-2025",
        "numerator_name": "presentations_in_period",
        "numerator": "10",
        "denominator_name": "dated_records_in_this_lens",
        "denominator": "100",
        "denominator_unit": "presentation",
        "value": "0.100000",
        "missingness": "undated_records=0",
        "coverage_status": "complete",
        "source_snapshot": "conferences:2026-08-06",
        "method": "record.created_at binned by classify.PERIOD_BINS",
        "method_version": metrics.METHOD_VERSION,
        "caveat": "within-lens composition",
    }
    row.update(overrides)
    return row


def _tables(**overrides) -> dict[str, list[dict]]:
    base = {
        "lens_source_coverage": [
            _row(metric_id="coverage.conferences", period="2004-01-01..2026-05-29",
                 denominator_name="records_in_snapshot", value="1.000000")
        ],
        "activity_by_period": [_row()],
        "intellectual_content_by_lens": [
            _row(metric_id="content.conferences.texts_philology.crosswalk", period="all",
                 denominator_name="records_with_this_axis_assigned")
        ],
        "community_function_by_lens": [
            _row(metric_id="function.conferences.teaching_learning.crosswalk", period="all",
                 denominator_name="records_with_this_axis_assigned")
        ],
        "argument_level_by_lens": [
            _row(metric_id="gumilev.conferences.G1.native", period="all",
                 denominator_name="records_with_this_axis_assigned")
        ],
        "person_overlap": [
            _row(metric_id="overlap.conferences", period="all",
                 denominator_name="persons_linked_in_this_lens", denominator_unit="person",
                 missingness="ambiguous_candidates_excluded=5; linked_mentions=1388")
        ],
        "orientation_contrast": [
            _row(metric_id="orientation.russia_centred.conferences", period="all",
                 denominator_name="records_in_this_lens_snapshot", value="",
                 method=f"corpus-selection premise ({metrics.ORIENTATION_EVIDENCE_CLASS})",
                 missingness="none")
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# V9 — the contract itself
# ---------------------------------------------------------------------------

def test_clean_synthetic_tables_validate():
    assert metrics.validate_metrics(_tables()) == []


def test_value_without_a_denominator_is_rejected():
    tables = _tables(activity_by_period=[_row(denominator="", value="0.5")])
    errors = metrics.validate_metrics(tables)
    assert any("no positive denominator" in error for error in errors)


def test_zero_denominator_with_a_value_is_rejected():
    tables = _tables(activity_by_period=[_row(denominator="0", value="0.5")])
    assert any("no positive denominator" in e for e in metrics.validate_metrics(tables))


def test_unavailable_lens_may_not_carry_a_value():
    """A gap is never a zero: an absent source may not produce a number."""
    tables = _tables(activity_by_period=[
        _row(lens="bvp", metric_id="activity.bvp.2018-2025", coverage_status="unavailable",
             caveat="explicit evidence GAP — no population claim", value="0.000000")
    ])
    errors = metrics.validate_metrics(tables)
    assert any("a gap is not a zero" in error for error in errors)


def test_pilot_coverage_with_a_value_must_carry_a_pilot_caveat():
    tables = _tables(activity_by_period=[
        _row(lens="nagari", metric_id="activity.nagari.2018-2025", coverage_status="pilot",
             native_unit="message", denominator_unit="message", caveat="within-lens composition")
    ])
    errors = metrics.validate_metrics(tables)
    assert any("no pilot/no-population caveat" in error for error in errors)


def test_cross_unit_activity_denominator_is_rejected():
    """The prohibited combination: one activity total across native units."""
    tables = _tables(activity_by_period=[
        _row(denominator_name="all_records_across_every_lens", denominator="27699")
    ])
    errors = metrics.validate_metrics(tables)
    assert any("cross-unit activity totals are prohibited" in error for error in errors)


def test_orientation_rows_may_not_carry_a_computed_value():
    tables = _tables(orientation_contrast=[
        _row(metric_id="orientation.russia_centred.conferences", value="0.62",
             method=f"corpus-selection premise ({metrics.ORIENTATION_EVIDENCE_CLASS})")
    ])
    errors = metrics.validate_metrics(tables)
    assert any("orientation rows carry no" in error for error in errors)


def test_orientation_must_be_marked_expert_judgment():
    tables = _tables(orientation_contrast=[
        _row(metric_id="orientation.russia_centred.conferences", value="",
             method="measured_forum_share")
    ])
    errors = metrics.validate_metrics(tables)
    assert any("must be marked expert_judgment" in error for error in errors)


def test_overlap_must_state_excluded_ambiguous_candidates():
    tables = _tables(person_overlap=[
        _row(metric_id="overlap.conferences", denominator_name="persons_linked_in_this_lens",
             denominator_unit="person", missingness="none")
    ])
    errors = metrics.validate_metrics(tables)
    assert any("ambiguous" in error for error in errors)


def test_duplicate_metric_ids_are_rejected():
    tables = _tables(activity_by_period=[_row(), _row()])
    assert any("duplicate metric_id" in e for e in metrics.validate_metrics(tables))


def test_missing_table_is_reported():
    tables = _tables()
    del tables["person_overlap"]
    assert any("missing metric table" in e for e in metrics.validate_metrics(tables))


def test_period_helpers_split_the_partial_year_off_the_trend():
    rows = [_row(period="2018-2025"), _row(metric_id="x", period=metrics.PARTIAL_PERIOD)]
    assert [r["period"] for r in metrics.trend_rows(rows)] == ["2018-2025"]
    assert [r["period"] for r in metrics.partial_rows(rows)] == [metrics.PARTIAL_PERIOD]
    assert metrics.PARTIAL_PERIOD not in metrics.TREND_PERIODS


def test_coverage_caveat_enforcement_is_applied_centrally():
    rows = [_row(coverage_status="pilot", caveat="within-lens composition")]
    metrics._enforce_coverage_caveats(rows)
    assert metrics.PILOT_CAVEAT in rows[0]["caveat"]


# ---------------------------------------------------------------------------
# The real frozen tables
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def frozen_tables() -> dict[str, list[dict]]:
    if not (metrics.TABLES_DIR / "activity_by_period.csv").exists():
        pytest.skip("frozen metric tables not built in this checkout")
    return {name: metrics.read_table(name) for name in metrics.TABLE_NAMES}


def test_frozen_tables_pass_the_v9_contract(frozen_tables):
    assert metrics.validate_metrics(frozen_tables) == []
    assert metrics.validate_temporal_separation(frozen_tables) == []


def test_frozen_tables_never_sum_native_units(frozen_tables):
    units = {row["lens"]: row["denominator_unit"] for row in frozen_tables["activity_by_period"]}
    for row in frozen_tables["activity_by_period"]:
        assert row["denominator_unit"] == units[row["lens"]]
        assert row["denominator_name"] == "dated_records_in_this_lens"


def test_unavailable_lenses_are_gaps_not_zeros(frozen_tables):
    for row in frozen_tables["lens_source_coverage"]:
        if row["coverage_status"] == "unavailable":
            assert row["value"] == ""
            assert row["numerator"] == ""
            assert "GAP" in row["caveat"]


# ---------------------------------------------------------------------------
# V10 — captions and the claims ledger
# ---------------------------------------------------------------------------

def test_caption_without_a_coverage_caveat_is_rejected(frozen_tables):
    errors = figures.validate_captions(
        {"fig9_bogus": "Рис. 9. Доклады по годам, знаменатель — presentation."}, frozen_tables
    )
    assert any("coverage caveat" in error for error in errors)


def test_real_captions_pass(frozen_tables):
    import json

    if not figures.CAPTIONS_JSON.exists():
        pytest.skip("figures not generated in this checkout")
    captions = json.loads(figures.CAPTIONS_JSON.read_text(encoding="utf-8"))
    assert figures.validate_captions(captions, frozen_tables) == []
    assert set(captions) == set(figures.FIGURE_IDS)


def test_real_claims_ledger_has_no_unlinked_claim(frozen_tables):
    claims = report.build_claims()
    assert report.validate_claims(claims, frozen_tables) == []


def test_unlinked_claim_is_rejected(frozen_tables):
    claims = copy.deepcopy(report.build_claims())
    claims[0]["evidence_ids"] = ""
    errors = report.validate_claims(claims, frozen_tables)
    assert any("UNLINKED" in error for error in errors)


def test_dangling_metric_evidence_is_rejected(frozen_tables):
    claims = copy.deepcopy(report.build_claims())
    claims[0]["evidence_ids"] = "activity.atlantis.2018-2025"
    errors = report.validate_claims(claims, frozen_tables)
    assert any("not a frozen metric row" in error for error in errors)


def test_causal_language_in_a_descriptive_claim_is_rejected(frozen_tables):
    claims = copy.deepcopy(report.build_claims())
    claims[0]["claim_ru"] = "Рост числа докладов вызвал приток новых исследователей."
    errors = report.validate_claims(claims, frozen_tables)
    assert any("causal language" in error for error in errors)


def test_representativeness_overclaim_is_rejected(frozen_tables):
    claims = copy.deepcopy(report.build_claims())
    claims[0]["claim_ru"] = "Корпус репрезентативен для российской индологии."
    errors = report.validate_claims(claims, frozen_tables)
    assert any("representativeness overclaim" in error for error in errors)


def test_expert_judgment_may_not_carry_a_p_value(frozen_tables):
    claims = copy.deepcopy(report.build_claims())
    expert = next(c for c in claims if c["evidence_kind"] == "expert_judgment")
    expert["claim_ru"] += " (p < 0.05)"
    errors = report.validate_claims(claims, frozen_tables)
    assert any("p-value" in error for error in errors)


def test_every_claim_names_a_figure_or_table_and_a_limitation():
    for claim in report.build_claims():
        assert claim["figure_or_table"].strip(), claim["claim_id"]
        assert claim["limitation"].strip(), claim["claim_id"]
        assert claim["verdict"] in report.VERDICTS
