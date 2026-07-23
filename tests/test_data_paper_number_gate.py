"""Regression tests for the anchored data-paper number gate (H1467).

``article/check_data_paper_numbers.py`` was hardened from bare
``snippet in draft`` substring containment to *anchored value assertions*
(phrase-anchored regexes that capture the number and compare it with word
boundaries). These tests pin the three drift classes that motivated the
change — each mutates a copy of the real draft, leaves every other artifact
untouched, and asserts:

  * the hardened gate FAILS on the mutation (``main() == 1``), and
  * the OLD containment check would have PASSED it (the exact substring the
    old gate looked for is still present) — documenting the regression the
    hardening closes, so a future refactor that reintroduces ``in`` semantics
    trips these tests.

The gate reads the draft from the module-level ``DRAFT`` constant, so each
case redirects ``DRAFT`` at a mutated temp copy and restores it afterwards.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# The gate and its sibling check_ppv_numbers both live in article/; put that
# on the path so `import check_data_paper_numbers` and its internal
# `from check_ppv_numbers import ...` both resolve.
sys.path.insert(0, str(ROOT / "article"))

DRAFT = ROOT / "article" / "data_paper_draft.md"
SITE_DATA = ROOT / "site_data.json"
DB = ROOT / "conferences.db"

pytestmark = pytest.mark.skipif(
    not (DRAFT.exists() and SITE_DATA.exists() and DB.exists()),
    reason="publication artifacts not built",
)


@pytest.fixture(scope="module")
def gate():
    import check_data_paper_numbers as mod
    return mod


@pytest.fixture(scope="module")
def summary(gate):
    return gate.load_site_data().get("summary", {})


@pytest.fixture
def run_on(gate, tmp_path, monkeypatch):
    """Return a helper that runs the gate against a mutated draft copy."""
    real = DRAFT.read_text(encoding="utf-8")

    def _run(mutate):
        mutated = mutate(real)
        assert mutated != real, "mutation was a no-op — the anchor text moved"
        tmp = tmp_path / "mutated_draft.md"
        tmp.write_text(mutated, encoding="utf-8")
        monkeypatch.setattr(gate, "DRAFT", tmp)
        return gate.main(), mutated

    return _run


def test_gate_passes_on_current_artifacts(gate):
    """Green baseline: the hardened gate must not false-fail on real data."""
    assert gate.main() == 0


def test_substring_bleed_false_pass_is_now_caught(run_on, summary):
    """A wrong number that *contains* the right one as a substring.

    Old: ``"1,362 conference presentations" in draft`` is satisfied by
    ``"21,362 conference presentations"`` (tail substring) -> false PASS.
    New: ``([\\d,]+)`` captures ``21,362`` -> mismatch -> FAIL.
    """
    unique = summary["unique_presentations"]
    old_phrase = f"{unique:,} conference presentations"
    rc, mutated = run_on(lambda d: d.replace(old_phrase, f"2{old_phrase}", 1))
    assert old_phrase in mutated, "precondition: old containment check would still pass"
    assert rc == 1, "hardened gate must reject the substring-bleed value"


def test_contradictory_duplicate_is_now_caught(run_on, summary):
    """A stale duplicate of a quantity that is correct elsewhere.

    Old: the correct ``"268 scholar profiles"`` satisfies the ``in`` check, so
    a second, contradictory ``"270 scholar profiles"`` sails through -> false
    PASS. New: every occurrence of the anchored phrase is checked -> FAIL.
    """
    total = summary["total_scholars"]
    correct = f"{total} scholar profiles"
    stale = f"{total + 2} scholar profiles"
    rc, mutated = run_on(
        lambda d: d + f"\n\n(An earlier revision counted {stale}.)\n"
    )
    assert correct in mutated, "precondition: the correct value is still present"
    assert stale in mutated
    assert rc == 1, "hardened gate must reject the contradictory duplicate"


def test_missing_anchor_phrase_still_fails(run_on, summary):
    """Coverage must not regress: a vanished phrase is still an error.

    The old containment check errored when its snippet was absent; the anchored
    gate keeps that by asserting the phrase is present at least once.
    """
    total = summary["total_scholars"]
    correct = f"{total} scholar profiles"
    # "268 scholar profiles" occurs more than once (abstract + coverage §);
    # strip the count from *every* occurrence so the anchor truly vanishes.
    rc, mutated = run_on(lambda d: d.replace(correct, "scholar profiles"))
    assert correct not in mutated
    assert rc == 1, "gate must fail when an anchored claim's phrase disappears"
