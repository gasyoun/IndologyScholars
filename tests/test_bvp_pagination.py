from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bvp"))

from pagination import Paginator, PaginationFault  # noqa: E402
from paginate_live import StopCrawl, run_pages  # noqa: E402


def make_listing_html(row_ids: list[str], first: int, last: int, total: int) -> str:
    rows = "\n".join(
        f'<div role="row" data-rowid="{row_id}">'
        f'<div class="o1DPKc">Subject {row_id}</div>'
        f'</div>'
        for row_id in row_ids
    )
    return f'<div class="aEb7Ed">{first}–{last} of {total}</div>\n{rows}'


def test_three_unique_pages_reconcile_cleanly(tmp_path):
    paginator = Paginator(tmp_path / "pages.json", requested_pages=3)
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    p2 = make_listing_html([f"id{i}" for i in range(31, 61)], 31, 60, 90)
    p3 = make_listing_html([f"id{i}" for i in range(61, 91)], 61, 90, 90)

    paginator.reconcile_page(1, p1, cursor_evidence="token-1")
    paginator.reconcile_page(2, p2, cursor_evidence="token-2")
    paginator.reconcile_page(3, p3, cursor_evidence=None)

    report = paginator.reconcile_report()
    assert report["pages_completed"] == 3
    assert report["unique_conversation_ids"] == 90
    assert report["duplicate_ids"] == 0
    assert report["unexplained_gap"] == 0
    assert report["faults"] == []
    assert report["coverage_status"] == "partial"


def test_repeated_page_signature_stops_with_fault(tmp_path):
    paginator = Paginator(tmp_path / "pages.json", requested_pages=3)
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    paginator.reconcile_page(1, p1, cursor_evidence="token-1")

    with pytest.raises(PaginationFault) as excinfo:
        paginator.reconcile_page(2, p1, cursor_evidence="token-1")
    assert excinfo.value.fault_type == "repeated_signature"
    assert paginator.state["coverage_status"] == "stopped"
    assert paginator.state["faults"][0]["type"] == "repeated_signature"


def test_overlap_or_backward_range_stops_with_fault(tmp_path):
    paginator = Paginator(tmp_path / "pages.json", requested_pages=3)
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    paginator.reconcile_page(1, p1, cursor_evidence="token-1")

    p2 = make_listing_html([f"id{i}" for i in range(20, 50)], 20, 49, 90)
    with pytest.raises(PaginationFault) as excinfo:
        paginator.reconcile_page(2, p2, cursor_evidence="token-2")
    assert excinfo.value.fault_type == "overlap_or_backward_range"


def test_forward_gap_is_recorded_not_faulted(tmp_path):
    paginator = Paginator(tmp_path / "pages.json", requested_pages=2)
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    p2 = make_listing_html([f"id{i}" for i in range(41, 71)], 41, 70, 90)

    paginator.reconcile_page(1, p1, cursor_evidence="token-1")
    paginator.reconcile_page(2, p2, cursor_evidence=None)

    report = paginator.reconcile_report()
    assert report["faults"] == []
    assert report["unexplained_gap"] == 20


def test_denominator_change_stops_with_fault(tmp_path):
    paginator = Paginator(tmp_path / "pages.json", requested_pages=2)
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    paginator.reconcile_page(1, p1, cursor_evidence="token-1")

    p2 = make_listing_html([f"id{i}" for i in range(31, 61)], 31, 60, 95)
    with pytest.raises(PaginationFault) as excinfo:
        paginator.reconcile_page(2, p2, cursor_evidence="token-2")
    assert excinfo.value.fault_type == "denominator_change"


def test_interruption_and_resume_skips_completed_pages(tmp_path):
    state_path = tmp_path / "pages.json"
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    p2 = make_listing_html([f"id{i}" for i in range(31, 61)], 31, 60, 90)
    p3 = make_listing_html([f"id{i}" for i in range(61, 91)], 61, 90, 90)

    first_session = Paginator(state_path, requested_pages=3)
    first_session.reconcile_page(1, p1, cursor_evidence="token-1")
    first_session.reconcile_page(2, p2, cursor_evidence="token-2")

    resumed = Paginator(state_path, requested_pages=3)
    assert resumed.completed_ordinals() == {1, 2}
    assert not resumed.has_page(3)
    resumed.reconcile_page(3, p3, cursor_evidence=None)

    report = resumed.reconcile_report()
    assert report["pages_completed"] == 3
    assert report["unique_conversation_ids"] == 90


def test_no_new_ids_stops_with_fault(tmp_path):
    paginator = Paginator(tmp_path / "pages.json", requested_pages=3)
    p1 = make_listing_html([f"id{i}" for i in range(1, 31)], 1, 30, 90)
    paginator.reconcile_page(1, p1, cursor_evidence="token-1")

    reordered_ids = list(reversed([f"id{i}" for i in range(1, 31)]))
    p2 = make_listing_html(reordered_ids, 31, 60, 90)
    with pytest.raises(PaginationFault) as excinfo:
        paginator.reconcile_page(2, p2, cursor_evidence="token-2")
    assert excinfo.value.fault_type == "no_new_ids"


def test_run_pages_stops_immediately_on_http_403(tmp_path):
    calls = []

    def fake_fetch_next(ordinal):
        calls.append(ordinal)
        if ordinal == 2:
            raise StopCrawl("origin returned 403; Retry-After=''")
        row_ids = [f"id{i}" for i in range(1, 31)]
        return make_listing_html(row_ids, 1, 30, 90), "token-1"

    paginator = Paginator(tmp_path / "pages.json", requested_pages=3)
    with pytest.raises(StopCrawl):
        run_pages(paginator, fetch_next=fake_fetch_next, max_pages=3, delay=0.0)

    assert calls == [1, 2]
    assert paginator.reconcile_report()["pages_completed"] == 1
