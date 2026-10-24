from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bvp"))

from fetch_hardening import Backoff, FailLedger
from scrape import parse_listing, parse_thread


def test_parse_listing_deduplicates_native_ids():
    html = """
    <div class="aEb7Ed">1–30 of 23,467</div>
    <div role="row" data-rowid="abc_123">
      <a href="./bvparishat/c/abc_123">thread</a>
      <div class="o1DPKc">A subject</div>
      <div class="WzoK">A snippet</div>
      <div class="z0zUgf">A scholar</div>
      <div class="F5JnCe" aria-label="it has 3 messages"></div>
      <div class="tRlaM">Jul 29</div>
    </div>
    <div role="row" data-rowid="abc_123">
      <a href="/g/bvparishat/c/abc_123">duplicate</a>
    </div>
    """
    parsed = parse_listing(html)
    assert parsed["listing"]["displayed_total"] == 23467
    assert len(parsed["conversations"]) == 1
    row = parsed["conversations"][0]
    assert row["conversation_id"] == "abc_123"
    assert row["message_count"] == 3


def test_parse_thread_deduplicates_message_nodes():
    html = """
    <h1 jsname="GNEpNe">A grammatical question</h1>
    <article data-conv-id="conv1" data-message-id="msg1">
      <h3 class="s1f8Zd">Madhav Deshpande</h3>
      <div>Pāṇini lists the root śru.</div>
    </article>
    <button data-conv-id="conv1" data-message-id="msg1">menu</button>
    <article data-conv-id="conv1" data-message-id="msg2">
      <h3 class="s1f8Zd">Second Scholar</h3>
      <div>A reply.</div>
    </article>
    """
    parsed = parse_thread(html, expected_id="conv1")
    assert parsed["conversation_id"] == "conv1"
    assert parsed["subject"] == "A grammatical question"
    assert parsed["message_count"] == 2
    assert parsed["messages"][0]["author_display"] == "Madhav Deshpande"
    assert "Pāṇini" in parsed["messages"][0]["rendered_text"]


def test_parse_thread_prefers_embedded_source_fields():
    data = [
        ["group-1", "bvparishat@googlegroups.com"],
        [None, "conv1", "A grammatical question", None, None, None, 1],
        [
            [
                [
                    [
                        "group-1",
                        "msg1",
                        [["Madhav Deshpande", None, None, "person-1"]],
                        None,
                        None,
                        "A grammatical question",
                        "snippet",
                        [1608661951, 0],
                    ],
                    [2, [[1, [None, "<div>Pāṇini lists śru.</div>"]]]],
                ]
            ]
        ],
    ]
    html = (
        "<script>AF_initDataCallback({key: 'ds:7', data:"
        + __import__("json").dumps(data, ensure_ascii=False)
        + ", sideChannel: {}});</script>"
    )
    parsed = parse_thread(html, expected_id="conv1")
    assert parsed["parse_source"] == "AF_initDataCallback ds:7"
    assert parsed["messages"][0]["author_display"] == "Madhav Deshpande"
    assert parsed["messages"][0]["author_native_id"] == "person-1"
    assert parsed["messages"][0]["timestamp_epoch"] == 1608661951
    assert parsed["messages"][0]["body_text"] == "Pāṇini lists śru."


def test_backoff_and_failure_ledger(tmp_path):
    backoff = Backoff(threshold=2, steps=(1.0, 5.0))
    assert backoff.record_error() == 0.0
    assert backoff.record_error() == 1.0
    backoff.record_success()
    assert backoff.record_error() == 0.0

    ledger = FailLedger(tmp_path / "failed.txt")
    ledger.load()
    ledger.add("https://example.test/a")
    ledger.add("https://example.test/a")
    assert "https://example.test/a" in ledger
    assert (tmp_path / "failed.txt").read_text(encoding="utf-8").count("\n") == 1
