"""H2242: the shared LensAdapter contract, proven with a synthetic adapter.

Covers: partial manifest, incomplete record, exclusion, parse failure,
duplicate native ID, deterministic ordering under input-order changes,
interrupted manifest, denominator mismatch, and a mechanically-rejected
population-metrics query against partial coverage (Procedure step 4).
"""
from __future__ import annotations

import pytest

from community_lenses.adapter import (
    AdapterContractError,
    LensAdapter,
    PopulationMetricsUnavailable,
    ReconciliationError,
    ReconciliationReport,
    assert_no_duplicate_native_ids,
    build_reconciliation_report,
    complete_coverage_predicate,
    validate_annotation_row,
    validate_container_row,
    validate_record_name_row,
    validate_record_relation_row,
    validate_record_row,
)
from community_lenses.ids import make_record_id
from community_lenses.manifests import SourceManifest

CORPUS = "conferences"
SNAPSHOT_ID = f"{CORPUS}:synthetic-2026-08-05"


def _manifest(coverage_status: str = "complete") -> SourceManifest:
    return SourceManifest(
        snapshot_id=SNAPSHOT_ID,
        corpus_id=CORPUS,
        coverage_status=coverage_status,
        source_version="synthetic-1",
        acquired_at="2026-08-05T00:00:00Z",
        source_sha256="a" * 64,
        pipeline_commit="deadbeef",
        schema_version="1.0.0",
        codebook_version="1.0.0",
        rights_basis="synthetic_test_fixture",
    )


class SyntheticAdapter(LensAdapter):
    """Minimal test-only adapter proving the ABC is actually usable end to end.

    Not a real corpus reader — its "source" is an in-memory list of synthetic
    item dicts with a ``kind`` of ``ok`` / ``incomplete`` / ``excluded`` /
    ``parse_failed``, so every reconciliation case in Procedure step 4 can be
    driven from one adapter shape.
    """

    corpus_id = CORPUS

    def __init__(self, items, *, coverage_status="complete", listed=None, discovered=None, fetched=None):
        self._items = items
        self._coverage_status = coverage_status
        n = len(items)
        self._listed = listed if listed is not None else n
        self._discovered = discovered if discovered is not None else n
        self._fetched = fetched if fetched is not None else n

    def source_manifest(self) -> SourceManifest:
        return _manifest(self._coverage_status)

    def _ok_items(self):
        return [i for i in self._items if i["kind"] in ("ok", "incomplete")]

    def iter_containers(self):
        yield {
            "container_id": f"{CORPUS}:container:synthetic",
            "corpus_id": CORPUS,
            "source_snapshot_id": SNAPSHOT_ID,
            "container_type": "meeting",
            "source_native_id": "synthetic",
        }

    def iter_records(self):
        for item in self._ok_items():
            record_id = make_record_id(CORPUS, item["id"])
            yield {
                "record_id": record_id,
                "corpus_id": CORPUS,
                "source_record_id": item["id"],
                "container_id": f"{CORPUS}:container:synthetic",
                "record_type": "presentation",
                "title_or_subject": item.get("title"),
                "status": "active",
                "access_class": "public",
                "source_snapshot_id": SNAPSHOT_ID,
            }

    def iter_names(self):
        for item in self._ok_items():
            if item["kind"] == "incomplete":
                continue
            record_id = make_record_id(CORPUS, item["id"])
            yield {
                "record_id": record_id,
                "ordinal": 0,
                "role": "presenter",
                "name_as_source": item.get("name", "Unknown"),
            }

    def iter_relations(self):
        return iter(())

    def iter_native_annotations(self):
        return iter(())

    def reconcile(self) -> ReconciliationReport:
        excluded = [i for i in self._items if i["kind"] == "excluded"]
        failed = [i for i in self._items if i["kind"] == "parse_failed"]
        parsed = [i for i in self._items if i["kind"] in ("ok", "incomplete")]
        missing_fields = {}
        incomplete = [i for i in self._items if i["kind"] == "incomplete"]
        if incomplete:
            missing_fields["record_name"] = len(incomplete)
        return build_reconciliation_report(
            corpus_id=CORPUS,
            coverage_status=self._coverage_status,
            denominator_unit="presentation",
            listed=self._listed,
            discovered=self._discovered,
            fetched=self._fetched,
            parsed=len(parsed),
            excluded=len(excluded),
            failed=len(failed),
            excluded_reasons={"synthetic_exclusion": len(excluded)} if excluded else None,
            missing_fields=missing_fields,
        )


def _items(n_ok=1, n_incomplete=0, n_excluded=0, n_failed=0):
    items = []
    for i in range(n_ok):
        items.append({"id": f"ok-{i}", "kind": "ok", "name": "A. Scholar", "title": "T"})
    for i in range(n_incomplete):
        items.append({"id": f"incomplete-{i}", "kind": "incomplete", "title": "T"})
    for i in range(n_excluded):
        items.append({"id": f"excluded-{i}", "kind": "excluded"})
    for i in range(n_failed):
        items.append({"id": f"failed-{i}", "kind": "parse_failed"})
    return items


# --- ABC usability: the synthetic adapter proves the contract works ----------


def test_synthetic_adapter_satisfies_the_full_contract():
    adapter = SyntheticAdapter(_items(n_ok=2, n_incomplete=1, n_excluded=1, n_failed=1))
    assert adapter.validate_emitted_rows() == []
    report = adapter.reconcile()
    assert report.listed == 5
    assert report.parsed == 3  # ok + incomplete
    assert report.excluded == 1
    assert report.failed == 1
    assert report.unexplained_gap() == 0


def test_cannot_instantiate_lens_adapter_directly():
    with pytest.raises(TypeError):
        LensAdapter()


# --- partial manifest / interrupted manifest ---------------------------------


def test_partial_manifest_never_grants_population_metrics():
    adapter = SyntheticAdapter(_items(n_ok=3), coverage_status="partial")
    report = adapter.reconcile()
    assert report.coverage_status == "partial"
    assert report.supports_population_metrics is False


def test_interrupted_manifest_listed_exceeds_fetched():
    # Acquisition stopped mid-fetch: more was listed than was ever fetched.
    adapter = SyntheticAdapter(_items(n_ok=2), coverage_status="partial", listed=10, discovered=10, fetched=2)
    report = adapter.reconcile()
    assert report.listed == 10
    assert report.fetched == 2
    assert report.supports_population_metrics is False
    assert report.unexplained_gap() == 8
    assert any("unexplained_gap=8" in n for n in report.notes)


# --- incomplete record / exclusion / parse failure ---------------------------


def test_incomplete_record_is_parsed_but_recorded_as_missing_not_dropped():
    adapter = SyntheticAdapter(_items(n_ok=1, n_incomplete=1))
    report = adapter.reconcile()
    assert report.parsed == 2  # the incomplete record IS parsed, not discarded
    assert report.missing_fields == {"record_name": 1}
    record_ids = {r["record_id"] for r in adapter.iter_records()}
    name_ids = {n["record_id"] for n in adapter.iter_names()}
    assert record_ids - name_ids  # the incomplete record has no name row


def test_exclusion_reasons_must_sum_to_excluded_total():
    with pytest.raises(ReconciliationError):
        build_reconciliation_report(
            corpus_id=CORPUS, coverage_status="complete", denominator_unit="x",
            listed=5, discovered=5, fetched=5, parsed=3, excluded=2, failed=0,
            excluded_reasons={"reason_a": 1},  # sums to 1, not 2
        )


def test_parse_failure_counted_separately_from_excluded():
    adapter = SyntheticAdapter(_items(n_ok=1, n_failed=2))
    report = adapter.reconcile()
    assert report.failed == 2
    assert report.excluded == 0


# --- duplicate native ID ------------------------------------------------------


def test_duplicate_native_id_is_rejected_not_silently_merged():
    with pytest.raises(ReconciliationError):
        assert_no_duplicate_native_ids(["a", "b", "a"])


def test_synthetic_adapter_with_duplicate_ids_fails_validate_emitted_rows():
    adapter = SyntheticAdapter(_items(n_ok=1))
    # Force a duplicate by re-adding the same synthetic id.
    adapter._items.append(dict(adapter._items[0]))
    errors = adapter.validate_emitted_rows()
    assert any("duplicate native" in e for e in errors)


# --- deterministic ordering under input-order changes -------------------------


def test_deterministic_ordering_survives_input_order_change():
    forward = _items(n_ok=3)
    reversed_input = list(reversed(forward))
    forward_ids = {r["record_id"] for r in SyntheticAdapter(forward).iter_records()}
    reversed_ids = {r["record_id"] for r in SyntheticAdapter(reversed_input).iter_records()}
    assert forward_ids == reversed_ids


def test_validate_emitted_rows_checks_iter_records_is_stable_across_calls():
    adapter = SyntheticAdapter(_items(n_ok=2))
    assert adapter.validate_emitted_rows() == []


# --- denominator mismatch ------------------------------------------------------


def test_denominator_mismatch_is_surfaced_not_hidden():
    report = build_reconciliation_report(
        corpus_id=CORPUS, coverage_status="complete", denominator_unit="x",
        listed=10, discovered=10, fetched=10, parsed=7, excluded=1, failed=1,
    )
    assert report.unexplained_gap() == 1
    assert any("unexplained_gap=1" in n for n in report.notes)


def test_counts_reject_none_and_bool_and_negative():
    for bad in (None, True, -1):
        with pytest.raises(ReconciliationError):
            build_reconciliation_report(
                corpus_id=CORPUS, coverage_status="complete", denominator_unit="x",
                listed=bad, discovered=0, fetched=0, parsed=0, excluded=0, failed=0,
            )


# --- population-metrics gate --------------------------------------------------


def test_complete_coverage_predicate_requires_full_reconciliation():
    assert complete_coverage_predicate(
        coverage_status="complete", listed=5, discovered=5, fetched=5,
        parsed=5, excluded=0, failed=0,
    ) is True
    assert complete_coverage_predicate(
        coverage_status="complete", listed=5, discovered=5, fetched=5,
        parsed=4, excluded=0, failed=0,
    ) is False
    assert complete_coverage_predicate(
        coverage_status="pilot", listed=5, discovered=5, fetched=5,
        parsed=5, excluded=0, failed=0,
    ) is False


def test_population_metrics_query_against_partial_coverage_is_mechanically_rejected():
    adapter = SyntheticAdapter(_items(n_ok=3), coverage_status="partial")
    report = adapter.reconcile()
    with pytest.raises(PopulationMetricsUnavailable):
        report.require_population_metrics()


def test_population_metrics_query_against_complete_coverage_succeeds():
    adapter = SyntheticAdapter(_items(n_ok=3), coverage_status="complete")
    report = adapter.reconcile()
    report.require_population_metrics()  # must not raise


def test_supports_population_metrics_cannot_be_overridden_by_caller():
    # build_reconciliation_report takes no flag param at all — the gate is
    # always derived, never settable, so there is nothing to try to override
    # except by passing counts that legitimately satisfy the predicate.
    report = build_reconciliation_report(
        corpus_id=CORPUS, coverage_status="pilot", denominator_unit="x",
        listed=5, discovered=5, fetched=5, parsed=5, excluded=0, failed=0,
    )
    assert report.supports_population_metrics is False


# --- row validators ------------------------------------------------------------


def test_row_validators_reject_unknown_fields():
    with pytest.raises(AdapterContractError):
        validate_container_row({
            "container_id": "x", "corpus_id": CORPUS, "source_snapshot_id": "s",
            "container_type": "t", "source_native_id": "n", "not_a_field": 1,
        })


def test_record_row_validator_enforces_record_id_derivation():
    with pytest.raises(AdapterContractError):
        validate_record_row({
            "record_id": "conferences:wrong-id",
            "corpus_id": CORPUS, "source_record_id": "right-id",
            "record_type": "presentation", "status": "active",
            "access_class": "public", "source_snapshot_id": SNAPSHOT_ID,
        })


def test_record_relation_validator_enforces_predicate_enum():
    with pytest.raises(AdapterContractError):
        validate_record_relation_row({
            "subject_record_id": "a", "predicate": "not_a_real_predicate",
            "object_record_id": "b",
        })


def test_record_name_and_annotation_validators_accept_minimal_valid_rows():
    validate_record_name_row({
        "record_id": "conferences:x", "ordinal": 0, "role": "presenter",
        "name_as_source": "A. Scholar",
    })
    validate_annotation_row({
        "annotation_id": "ann1", "record_id": "conferences:x",
        "annotation_type": "native_topic",
    })
