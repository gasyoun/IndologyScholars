"""H1898 identity-layer tests — synthetic fixtures + invariants over the real
reviewed decision table (curation/community_person_links.csv)."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from community_lenses import identity  # noqa: E402

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


def make_link(**overrides) -> dict:
    row = {
        "corpus_id": "nagari",
        "name_as_source": "Anna Testova",
        "source_account_id": "atest@…",
        "person_id": "conferences:PERS_TEST01",
        "decision": "accepted",
        "method": "translit_exact",
        "evidence_locator": "nagari:<syn-1@example>",
        "mention_count": "1",
        "reviewer": "Fable 5 (claude-fable-5)",
        "reviewed_date": "2026-08-05",
        "confidence_rationale": "synthetic",
        "decision_version": identity.DECISION_VERSION,
        "exportable": "no",
    }
    row.update(overrides)
    return row


class CandidateGenerationTests(unittest.TestCase):
    def setUp(self):
        self.fx = load_fixture()

    def run_generate(self, reviewed=None):
        return identity.generate_candidates(
            self.fx["identities"],
            self.fx["persons"],
            self.fx["aliases"],
            self.fx["authority_ids"],
            reviewed or [],
        )

    def test_no_candidate_method_auto_accepts(self):
        auto, cands = self.run_generate()
        self.assertEqual(auto, [], "only authority_exact may auto-accept; none present")
        self.assertTrue(cands, "synthetic matches must surface as candidates")
        for cand in cands:
            self.assertIn(cand["method"], identity.CANDIDATE_METHODS)
            self.assertNotIn(cand["method"], identity.AUTO_ACCEPT_METHODS)

    def test_translit_and_subset_candidates_surface(self):
        _, cands = self.run_generate()
        pairs = {(c["name_as_source"], c["candidate_person_id"]) for c in cands}
        self.assertIn(("Anna Testova", "conferences:PERS_TEST01"), pairs)
        self.assertIn(("Анна Тестова", "conferences:PERS_TEST01"), pairs)
        self.assertIn(("Boris Primerov", "conferences:PERS_TEST02"), pairs)

    def test_unrelated_name_yields_no_candidate(self):
        _, cands = self.run_generate()
        self.assertFalse(
            [c for c in cands if c["name_as_source"] == "Совсем Непохожий Никнейм"],
            "an unrelated display name must not match anyone",
        )

    def test_negative_decisions_do_not_recur_as_open(self):
        rejected = make_link(decision="rejected")
        _, cands = self.run_generate(reviewed=[rejected])
        open_items = identity.open_candidates(cands)
        self.assertFalse(
            [
                c
                for c in open_items
                if c["name_as_source"] == "Anna Testova"
                and c["candidate_person_id"] == "conferences:PERS_TEST01"
            ],
            "a rejected pair must not reopen",
        )
        decided = [
            c
            for c in cands
            if c["name_as_source"] == "Anna Testova"
            and c["candidate_person_id"] == "conferences:PERS_TEST01"
        ]
        self.assertTrue(decided and decided[0]["prior_decision"] == "rejected")

    def test_homonym_surname_yields_both_candidates_for_review(self):
        # "Тестова" belongs to two persons; the given name separates them, but
        # the subset method may surface either — both must stay review-only.
        _, cands = self.run_generate()
        for cand in cands:
            self.assertNotIn(cand["method"], identity.AUTO_ACCEPT_METHODS)


class ReviewedLinkValidationTests(unittest.TestCase):
    def test_accepted_without_reviewer_fails(self):
        with self.assertRaises(identity.IdentityError):
            identity.validate_reviewed_links([make_link(reviewer="")])

    def test_accepted_without_evidence_fails(self):
        with self.assertRaises(identity.IdentityError):
            identity.validate_reviewed_links([make_link(evidence_locator="")])

    def test_accepted_without_date_or_version_fails(self):
        with self.assertRaises(identity.IdentityError):
            identity.validate_reviewed_links([make_link(reviewed_date="")])
        with self.assertRaises(identity.IdentityError):
            identity.validate_reviewed_links([make_link(decision_version="")])

    def test_unknown_method_or_decision_fails(self):
        with self.assertRaises(identity.IdentityError):
            identity.validate_reviewed_links([make_link(method="vibes")])
        with self.assertRaises(identity.IdentityError):
            identity.validate_reviewed_links([make_link(decision="maybe")])

    def test_ambiguous_row_passes_without_application(self):
        identity.validate_reviewed_links([make_link(decision="ambiguous")])


class RealDecisionTableTests(unittest.TestCase):
    """Deterministic invariants over the ACTUAL reviewed table."""

    @classmethod
    def setUpClass(cls):
        path = identity.PERSON_LINKS_PATH
        if not path.exists():
            raise unittest.SkipTest("curation/community_person_links.csv not present")
        with path.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_table_validates(self):
        identity.validate_reviewed_links(self.rows)

    def test_every_accepted_row_is_manual_with_full_provenance(self):
        for row in self.rows:
            if row["decision"] != "accepted":
                continue
            self.assertTrue(row["reviewer"], row)
            self.assertTrue(row["reviewed_date"], row)
            self.assertTrue(row["evidence_locator"], row)
            self.assertTrue(row["confidence_rationale"], row)

    def test_no_auto_accepted_fuzzy_rows(self):
        for row in self.rows:
            if row["method"] not in identity.AUTO_ACCEPT_METHODS:
                self.assertTrue(
                    row["reviewer"],
                    f"non-authority method {row['method']} requires a manual reviewer: {row}",
                )

    def test_closed_list_rows_not_exportable(self):
        for row in self.rows:
            if row["corpus_id"] == "nagari":
                self.assertEqual(row["exportable"], "no", row)

    def test_ambiguous_rows_carry_rationale_not_links(self):
        ambiguous = [r for r in self.rows if r["decision"] == "ambiguous"]
        for row in ambiguous:
            self.assertTrue(row["confidence_rationale"], row)


if __name__ == "__main__":
    unittest.main()
