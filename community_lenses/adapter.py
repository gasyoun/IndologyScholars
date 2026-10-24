"""Shared ``LensAdapter`` contract (H1893 gap, closed by H2242).

Per ARCHITECTURE "Adapter contract": every per-corpus adapter (nagari, VK/ORS,
INDOLOGY-L, conferences, BVP) is a pure reader over one pinned
:class:`~community_lenses.manifests.SourceManifest`. It emits rows shaped
exactly like the ``container``/``record``/``record_name``/``record_relation``/
``annotation`` tables in :mod:`community_lenses.schema`, and it must reconcile
every emitted row to explicit listed/discovered/fetched/parsed/excluded/failed
denominators — never collapsing ``missing``, ``excluded``, and genuine ``0``
into each other (H1896 Guardrails).

Row shape is a plain ``dict`` matching the corresponding table's columns
(the same convention :mod:`community_lenses.build` uses for fixtures), not a
dataclass — an adapter's ``iter_*`` output can be fed straight into
``build._insert_rows`` without translation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from . import ids as ids_mod
from .manifests import SourceManifest
from .schema import ACCESS_CLASSES, CORPUS_IDS, RECORD_STATUSES, RELATION_PREDICATES

__all__ = [
    "AdapterContractError",
    "ReconciliationError",
    "PopulationMetricsUnavailable",
    "ReconciliationReport",
    "LensAdapter",
    "complete_coverage_predicate",
    "build_reconciliation_report",
    "assert_no_duplicate_native_ids",
    "validate_container_row",
    "validate_record_row",
    "validate_record_name_row",
    "validate_record_relation_row",
    "validate_annotation_row",
]


class AdapterContractError(ValueError):
    """A row emitted by a :class:`LensAdapter` violates the shared contract."""


class ReconciliationError(ValueError):
    """A :func:`build_reconciliation_report` call collapsed or mismatched a
    denominator instead of reporting it explicitly."""


class PopulationMetricsUnavailable(RuntimeError):
    """Raised when population-level metrics (annual trend, person-share,
    topic-share) are requested from a report whose coverage does not satisfy
    :func:`complete_coverage_predicate`."""


# --- row shapes (mirrors schema.py's DDL column sets) ------------------------

CONTAINER_FIELDS = (
    "container_id", "corpus_id", "source_snapshot_id", "parent_container_id",
    "container_type", "source_native_id", "title", "date_from", "date_to",
    "source_url",
)
_CONTAINER_REQUIRED = (
    "container_id", "corpus_id", "source_snapshot_id", "container_type",
    "source_native_id",
)

RECORD_FIELDS = (
    "record_id", "corpus_id", "source_record_id", "source_record_id_method",
    "container_id", "record_type", "title_or_subject", "body_locator",
    "created_at", "language", "canonical_url", "content_sha256", "status",
    "is_partial_2026", "access_class", "source_snapshot_id",
)
_RECORD_REQUIRED = (
    "record_id", "corpus_id", "source_record_id", "record_type", "status",
    "access_class", "source_snapshot_id",
)

RECORD_NAME_FIELDS = (
    "record_id", "ordinal", "role", "name_as_source", "affiliation_as_source",
    "source_account_id", "person_id",
)
_RECORD_NAME_REQUIRED = ("record_id", "ordinal", "role", "name_as_source")

RECORD_RELATION_FIELDS = (
    "subject_record_id", "predicate", "object_record_id", "evidence_locator",
)
_RECORD_RELATION_REQUIRED = ("subject_record_id", "predicate", "object_record_id")

ANNOTATION_FIELDS = (
    "annotation_id", "record_id", "annotation_type", "body", "author",
    "created_at", "access_class",
)
_ANNOTATION_REQUIRED = ("annotation_id", "record_id", "annotation_type")


def _validate_row(
    row: Mapping,
    *,
    table_name: str,
    fields: tuple[str, ...],
    required: tuple[str, ...],
) -> None:
    if not isinstance(row, Mapping):
        raise AdapterContractError(f"{table_name} row must be a mapping, got {type(row)!r}")
    unknown = set(row) - set(fields)
    if unknown:
        raise AdapterContractError(
            f"{table_name} row has fields outside the contract: {sorted(unknown)}"
        )
    missing = [f for f in required if row.get(f) in (None, "")]
    if missing:
        raise AdapterContractError(
            f"{table_name} row missing required field(s): {missing}"
        )


def validate_container_row(row: Mapping) -> None:
    _validate_row(row, table_name="container", fields=CONTAINER_FIELDS, required=_CONTAINER_REQUIRED)
    if row["corpus_id"] not in CORPUS_IDS:
        raise AdapterContractError(f"container.corpus_id unknown: {row['corpus_id']!r}")


def validate_record_row(row: Mapping) -> None:
    _validate_row(row, table_name="record", fields=RECORD_FIELDS, required=_RECORD_REQUIRED)
    if row["corpus_id"] not in CORPUS_IDS:
        raise AdapterContractError(f"record.corpus_id unknown: {row['corpus_id']!r}")
    if row["status"] not in RECORD_STATUSES:
        raise AdapterContractError(f"record.status unknown: {row['status']!r}")
    if row["access_class"] not in ACCESS_CLASSES:
        raise AdapterContractError(f"record.access_class unknown: {row['access_class']!r}")
    expected_id = ids_mod.make_record_id(row["corpus_id"], row["source_record_id"])
    if row["record_id"] != expected_id:
        raise AdapterContractError(
            f"record.record_id {row['record_id']!r} != make_record_id() result "
            f"{expected_id!r}"
        )


def validate_record_name_row(row: Mapping) -> None:
    _validate_row(row, table_name="record_name", fields=RECORD_NAME_FIELDS, required=_RECORD_NAME_REQUIRED)


def validate_record_relation_row(row: Mapping) -> None:
    _validate_row(
        row, table_name="record_relation", fields=RECORD_RELATION_FIELDS,
        required=_RECORD_RELATION_REQUIRED,
    )
    if row["predicate"] not in RELATION_PREDICATES:
        raise AdapterContractError(f"record_relation.predicate unknown: {row['predicate']!r}")


def validate_annotation_row(row: Mapping) -> None:
    _validate_row(row, table_name="annotation", fields=ANNOTATION_FIELDS, required=_ANNOTATION_REQUIRED)
    if "access_class" in row and row["access_class"] not in ACCESS_CLASSES:
        raise AdapterContractError(f"annotation.access_class unknown: {row['access_class']!r}")


# --- reconciliation ----------------------------------------------------------


def complete_coverage_predicate(
    *, coverage_status: str, listed: int, discovered: int, fetched: int,
    parsed: int, excluded: int, failed: int,
) -> bool:
    """The one place ``supports_population_metrics`` may become True.

    Complete coverage requires the listing, discovery, and fetch stages to
    agree on the same denominator AND every listed item to be accounted for
    by parsed + excluded + failed — no unexplained gap. Adapters never set
    this flag themselves; :func:`build_reconciliation_report` always derives
    it from the counts actually supplied.
    """
    if coverage_status != "complete":
        return False
    if not (listed == discovered == fetched):
        return False
    return (parsed + excluded + failed) == listed


def assert_no_duplicate_native_ids(source_record_ids: Iterable[str]) -> None:
    """Reject silently-merged duplicate native IDs (H1896 Procedure step 8)."""
    seen: dict[str, int] = {}
    for sid in source_record_ids:
        seen[sid] = seen.get(sid, 0) + 1
    duplicates = {sid: n for sid, n in seen.items() if n > 1}
    if duplicates:
        raise ReconciliationError(
            f"duplicate native source_record_id(s), never silently merged: {duplicates}"
        )


def _require_count(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReconciliationError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise ReconciliationError(f"{name} must be >= 0, got {value!r}")
    return value


@dataclass(frozen=True)
class ReconciliationReport:
    corpus_id: str
    coverage_status: str
    denominator_unit: str
    listed: int
    discovered: int
    fetched: int
    parsed: int
    excluded: int
    failed: int
    excluded_reasons: Mapping[str, int] = field(default_factory=dict)
    missing_fields: Mapping[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    supports_population_metrics: bool = False

    def unexplained_gap(self) -> int:
        """listed items not accounted for by parsed + excluded + failed.

        Never silently zeroed — a nonzero gap is a real finding, not a bug in
        the report, and callers must surface it (H2242 acceptance).
        """
        return self.listed - (self.parsed + self.excluded + self.failed)

    def require_population_metrics(self) -> None:
        """Mechanically reject a population-level query on partial coverage."""
        if not self.supports_population_metrics:
            raise PopulationMetricsUnavailable(
                f"corpus={self.corpus_id!r} coverage_status={self.coverage_status!r} "
                f"does not satisfy the complete-coverage predicate; annual "
                f"trend / person-share / topic-share claims are unavailable"
            )


def build_reconciliation_report(
    *,
    corpus_id: str,
    coverage_status: str,
    denominator_unit: str,
    listed: int,
    discovered: int,
    fetched: int,
    parsed: int,
    excluded: int,
    failed: int,
    excluded_reasons: Mapping[str, int] | None = None,
    missing_fields: Mapping[str, int] | None = None,
    notes: Iterable[str] = (),
) -> ReconciliationReport:
    """The one sanctioned way to build a :class:`ReconciliationReport`.

    All six denominator counts are required keyword args with no default —
    an adapter cannot accidentally let ``excluded`` or ``failed`` default to
    0 and thereby hide a count it never measured. ``supports_population_metrics``
    is always computed here via :func:`complete_coverage_predicate`; nothing
    a caller passes can override it.
    """
    if corpus_id not in CORPUS_IDS:
        raise ReconciliationError(f"unknown corpus_id: {corpus_id!r}")

    counts = {
        "listed": _require_count("listed", listed),
        "discovered": _require_count("discovered", discovered),
        "fetched": _require_count("fetched", fetched),
        "parsed": _require_count("parsed", parsed),
        "excluded": _require_count("excluded", excluded),
        "failed": _require_count("failed", failed),
    }

    excluded_reasons = dict(excluded_reasons or {})
    if excluded_reasons and sum(excluded_reasons.values()) != counts["excluded"]:
        raise ReconciliationError(
            f"excluded_reasons sums to {sum(excluded_reasons.values())} but "
            f"excluded={counts['excluded']} — a reason breakdown must "
            f"reconcile to its own total, not just to the denominator"
        )

    missing_fields = dict(missing_fields or {})

    gap = counts["listed"] - (counts["parsed"] + counts["excluded"] + counts["failed"])
    notes = tuple(notes)
    if gap != 0:
        notes = notes + (
            f"unexplained_gap={gap} (listed - (parsed + excluded + failed)); "
            f"not zeroed, surfaced for review",
        )

    supports_population_metrics = complete_coverage_predicate(
        coverage_status=coverage_status,
        listed=counts["listed"],
        discovered=counts["discovered"],
        fetched=counts["fetched"],
        parsed=counts["parsed"],
        excluded=counts["excluded"],
        failed=counts["failed"],
    )

    return ReconciliationReport(
        corpus_id=corpus_id,
        coverage_status=coverage_status,
        denominator_unit=denominator_unit,
        excluded_reasons=excluded_reasons,
        missing_fields=missing_fields,
        notes=notes,
        supports_population_metrics=supports_population_metrics,
        **counts,
    )


# --- the contract --------------------------------------------------------


class LensAdapter(ABC):
    """Pure-reader contract every per-corpus community-lens adapter implements.

    An adapter converts one pinned :class:`SourceManifest` into H1893 schema
    rows. It must never fetch a rolling source, mutate a native database, or
    trigger a model call (ARCHITECTURE "Adapter contract"; H1896 Guardrails).
    """

    corpus_id: str

    @abstractmethod
    def source_manifest(self) -> SourceManifest:
        """The pinned, hashed snapshot this adapter reads — never a live source."""

    @abstractmethod
    def iter_containers(self) -> Iterable[dict]:
        """Yield ``container`` rows (see :data:`CONTAINER_FIELDS`)."""

    @abstractmethod
    def iter_records(self) -> Iterable[dict]:
        """Yield ``record`` rows (see :data:`RECORD_FIELDS`)."""

    @abstractmethod
    def iter_names(self) -> Iterable[dict]:
        """Yield ``record_name`` rows (see :data:`RECORD_NAME_FIELDS`)."""

    @abstractmethod
    def iter_relations(self) -> Iterable[dict]:
        """Yield ``record_relation`` rows (see :data:`RECORD_RELATION_FIELDS`)."""

    @abstractmethod
    def iter_native_annotations(self) -> Iterable[dict]:
        """Yield ``annotation`` rows preserving source-native labels, unmapped
        to any shared taxonomy (see :data:`ANNOTATION_FIELDS`)."""

    @abstractmethod
    def reconcile(self) -> ReconciliationReport:
        """Return this adapter's denominator reconciliation.

        Implementations should build the report via
        :func:`build_reconciliation_report` so the capability gate and
        collapse guards apply uniformly across every lens.
        """

    def validate_emitted_rows(self) -> list[str]:
        """Run every emitted row through the shape/reference validators plus
        the cross-cutting invariants (record_id derivation, corpus_id
        consistency, no duplicate native IDs, deterministic ordering).

        Not part of the abstract contract — a convenience adapters and their
        tests may call; returns a list of violations (empty means clean).
        """
        errors: list[str] = []

        for row in self.iter_containers():
            try:
                validate_container_row(row)
                if row["corpus_id"] != self.corpus_id:
                    errors.append(
                        f"container {row.get('container_id')!r} corpus_id "
                        f"{row['corpus_id']!r} != adapter corpus_id {self.corpus_id!r}"
                    )
            except AdapterContractError as exc:
                errors.append(str(exc))

        records = list(self.iter_records())
        source_ids = []
        for row in records:
            try:
                validate_record_row(row)
                if row["corpus_id"] != self.corpus_id:
                    errors.append(
                        f"record {row.get('record_id')!r} corpus_id "
                        f"{row['corpus_id']!r} != adapter corpus_id {self.corpus_id!r}"
                    )
                else:
                    source_ids.append(row["source_record_id"])
            except AdapterContractError as exc:
                errors.append(str(exc))

        try:
            assert_no_duplicate_native_ids(source_ids)
        except ReconciliationError as exc:
            errors.append(str(exc))

        for row in self.iter_names():
            try:
                validate_record_name_row(row)
            except AdapterContractError as exc:
                errors.append(str(exc))

        for row in self.iter_relations():
            try:
                validate_record_relation_row(row)
            except AdapterContractError as exc:
                errors.append(str(exc))

        for row in self.iter_native_annotations():
            try:
                validate_annotation_row(row)
            except AdapterContractError as exc:
                errors.append(str(exc))

        first_order = [r["record_id"] for r in records]
        second_order = [r["record_id"] for r in self.iter_records()]
        if sorted(first_order) != sorted(second_order):
            errors.append(
                "iter_records() is not stable across calls — the same "
                "record_id set must be emitted every time"
            )

        return errors
