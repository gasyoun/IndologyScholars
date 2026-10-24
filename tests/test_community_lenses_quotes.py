"""H1898 quote-register tests — synthetic fixtures + invariants over the real
register (curation/community_quotes.csv)."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from community_lenses import quotes  # noqa: E402

FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "community_lenses"
    / "identity_quotes"
    / "synthetic_identity.json"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def make_quote(**overrides) -> dict:
    row = {
        "quote_id": "Q-SYN-1",
        "corpus_id": "vk_ors",
        "record_id": "vk_ors:-1_1",
        "person_id": "",
        "author_display": "Synthetic Author",
        "behaviour": "asked",
        "quote_verbatim": "как выучить грамматику Панини за год?",
        "source_url": "https://example.invalid/1",
        "source_date": "2020-01-01",
        "retrieved_at": "2026-08-05",
        "thread_subject": "synthetic",
        "context_note": "synthetic",
        "public_access_checked_at": "2026-08-05",
        "rights_review_status": "pending_review",
        "article_claim_id": "cl-synthetic",
        "agg_status": "available",
        "agg_numerator": "1",
        "agg_denominator": "10",
        "agg_denominator_unit": "synthetic records",
        "agg_coverage_status": "complete",
        "agg_snapshot_id": "synthetic:2026-08-05",
        "agg_method_version": "synthetic 1.0.0",
        "agg_note": "synthetic",
    }
    row.update(overrides)
    return row


class VerbatimTests(unittest.TestCase):
    def setUp(self):
        self.fx = load_fixture()
        self.source = self.fx["source_text"]

    def test_exact_quote_registers(self):
        row = quotes.register_quote(make_quote(), self.source)
        self.assertEqual(row["omissions_marked"], "0")
        self.assertTrue(row["context_before_sha256"])
        self.assertTrue(row["context_after_sha256"])

    def test_paraphrase_is_rejected(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(
                make_quote(quote_verbatim=self.fx["quote_paraphrase"]), self.source
            )

    def test_omission_marked_quote_matches_in_order(self):
        row = quotes.register_quote(
            make_quote(quote_verbatim=self.fx["quote_with_omission"]), self.source
        )
        self.assertEqual(row["omissions_marked"], "1")

    def test_out_of_order_segments_rejected(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(
                make_quote(quote_verbatim="за год? [...] Вопрос:"), self.source
            )

    def test_single_char_alteration_rejected(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(
                make_quote(quote_verbatim="как выучить граматику Панини за год?"),
                self.source,
            )

    def test_context_hash_changes_when_span_moves(self):
        row_a = quotes.register_quote(make_quote(), self.source)
        row_b = quotes.register_quote(
            make_quote(quote_verbatim="Первая строка контекста."), self.source
        )
        self.assertNotEqual(
            row_a["context_before_sha256"], row_b["context_before_sha256"]
        )


class GateTests(unittest.TestCase):
    def setUp(self):
        self.fx = load_fixture()
        self.source = self.fx["source_text"]

    def test_closed_corpus_forced_non_exportable(self):
        row = quotes.register_quote(
            make_quote(
                corpus_id="nagari",
                record_id="nagari:<syn-1@example>",
                rights_review_status="exportable_approved",
            ),
            self.source,
        )
        self.assertEqual(row["rights_review_status"], "non_exportable")

    def test_closed_corpus_with_complete_approval_may_export(self):
        row = quotes.register_quote(
            make_quote(
                corpus_id="nagari",
                record_id="nagari:<syn-1@example>",
                rights_review_status="exportable_approved",
                rights_approver="Named Owner",
                rights_approval_scope="this quote only",
                rights_approval_date="2026-08-05",
                rights_permitted_use="article illustration",
            ),
            self.source,
        )
        self.assertEqual(row["rights_review_status"], "exportable_approved")

    def test_open_corpus_cannot_claim_export_without_approval(self):
        row = quotes.register_quote(
            make_quote(rights_review_status="exportable_approved"), self.source
        )
        self.assertEqual(row["rights_review_status"], "non_exportable")

    def test_contact_data_flags_and_blocks_export(self):
        source = "пишите на test@example.com про грамматику"
        row = quotes.register_quote(
            make_quote(
                quote_verbatim="пишите на test@example.com про грамматику",
                rights_review_status="pending_review",
            ),
            source,
        )
        self.assertEqual(row["contact_data_removed"], "0")
        self.assertEqual(quotes.exportable_rows([row]), [])

    def test_non_observable_behaviour_rejected(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(make_quote(behaviour="was_nationalist"), None or self.source)

    def test_missing_claim_id_rejected(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(make_quote(article_claim_id=""), self.source)

    def test_aggregate_pointer_required(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(make_quote(agg_status=""), self.source)
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(
                make_quote(agg_status="available", agg_denominator=""), self.source
            )

    def test_aggregate_unavailable_requires_reason(self):
        with self.assertRaises(quotes.QuoteError):
            quotes.register_quote(
                make_quote(agg_status="aggregate_evidence_unavailable", agg_note=""),
                self.source,
            )
        row = quotes.register_quote(
            make_quote(
                agg_status="aggregate_evidence_unavailable",
                agg_note="no frozen scheme for this axis",
            ),
            self.source,
        )
        self.assertEqual(row["agg_status"], "aggregate_evidence_unavailable")


class RealRegisterTests(unittest.TestCase):
    """Deterministic invariants over the ACTUAL committed-shape register."""

    @classmethod
    def setUpClass(cls):
        path = quotes.QUOTES_PATH
        if not path.exists():
            raise unittest.SkipTest("curation/community_quotes.csv not present")
        with path.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_register_is_nonempty_and_complete(self):
        self.assertTrue(self.rows)
        for row in self.rows:
            for field in (
                "quote_id",
                "record_id",
                "author_display",
                "behaviour",
                "quote_verbatim",
                "retrieved_at",
                "article_claim_id",
                "rights_review_status",
                "context_before_sha256",
                "context_after_sha256",
            ):
                self.assertTrue(row[field], f"{row['quote_id']}: empty {field}")

    def test_every_row_has_aggregate_pointer_or_reason(self):
        for row in self.rows:
            quotes.validate_aggregate_pointer(row)

    def test_closed_list_rows_are_non_exportable_without_approval(self):
        """Closed-list quotes stay non_exportable unless approval_complete.

        H2573 parked the three approved rows fail-closed on the valid token
        ``non_exportable``. H2771 flips them to ``exportable_approved`` now
        that the rights lift is ruled. Without a complete approval record
        the old lock still holds.
        """
        for row in self.rows:
            if row["corpus_id"] not in quotes.CLOSED_CORPORA:
                continue
            status = quotes.effective_rights_status(row)
            if quotes.approval_complete(row):
                self.assertIn(status, quotes.RIGHTS_STATES, row["quote_id"])
            else:
                self.assertEqual(status, "non_exportable", row["quote_id"])

    def test_no_exportable_row_without_approval(self):
        exported = quotes.exportable_rows(self.rows)
        for row in exported:
            self.assertTrue(
                quotes.approval_complete(row),
                f"{row['quote_id']} is exportable without a complete approval record",
            )
        self.assertEqual(
            {row["quote_id"] for row in exported},
            {"Q-VK-22289", "Q-NG-PANINI-ASK", "Q-NG-PANINI-ANSWER"},
        )

    def test_no_contact_data_in_any_registered_quote(self):
        for row in self.rows:
            self.assertFalse(
                quotes.contact_data_present(row["quote_verbatim"]),
                f"{row['quote_id']} carries contact data",
            )

    def test_behaviours_are_observable_actions(self):
        for row in self.rows:
            self.assertIn(row["behaviour"], quotes.OBSERVABLE_ACTIONS)


if __name__ == "__main__":
    unittest.main()
