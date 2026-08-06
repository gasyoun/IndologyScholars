"""INDOLOGY-L adapter — H1895 Wave 1B.

Per the handoff's own requirement 5, this adapter must "consume only the
complete atomic H1894 snapshot" and "reject mixed/partial input" -- but
H1894 (atomic staging-then-promote fetch + pinning manifest for the
INDOLOGY-L feed) was never actually built, despite being registry-marked
Done (see .ai_state.md Dev Notes and the H1895 handoff's own Depends-on
line). ``tools/fetch_indology_feed.py`` on disk is still the old,
unhardened per-file ``urlopen`` fetcher with no manifest/hash verification
and no atomic promotion -- exactly the kind of unverified, possibly-partial
input this adapter must refuse.

So rather than silently succeed against an input it cannot trust, this
adapter always returns a ``coverage_status="unavailable"`` fixture and
names the real blocker (H1894 not landed) as an explicit gap -- never a
fabricated snapshot.
"""

from __future__ import annotations

from . import _shared

CORPUS_ID = "indology_l"


def build_fixture() -> dict:
    return _shared.unavailable_fixture(
        corpus_id=CORPUS_ID,
        title="INDOLOGY-L Pipermail archive (fed from gasyoun/IndologyArchiveAtlas)",
        native_unit="message",
        rights_basis=(
            "public Pipermail archive; this repo only fetches a small feed, full "
            "atlas lives in gasyoun/IndologyArchiveAtlas"
        ),
        gap_note=(
            "BLOCKED on H1894: no atomic staging-then-promote feed fetcher or pinned "
            "manifest exists. tools/fetch_indology_feed.py is still the old per-file "
            "urlopen fetcher with no manifest/hash verification, so its output cannot "
            "be trusted as a complete atomic snapshot -- H1895 requirement 5 requires "
            "rejecting mixed/partial input, so this adapter refuses to consume it "
            "rather than fabricate a 'complete' or 'partial' coverage_status."
        ),
    )


def coverage_report(fixture: dict) -> str:
    manifest = fixture["manifest"]
    return _shared.render_coverage_report(
        corpus_id=CORPUS_ID,
        title="INDOLOGY-L (blocked on H1894)",
        native_unit="message",
        coverage_status=manifest["coverage_status"],
        manifest_snapshot_id=manifest["snapshot_id"],
        date_range="? .. ?",
        denominator_definition="deferred: no atomic snapshot exists to define a denominator against",
        included=0,
        excluded=0,
        failures=0,
        completeness_status="blocked -- H1894 (atomic feed hardening) was never actually built",
        notes=[
            "This is a NAMED gap, not a silent success: see .ai_state.md Dev Notes for the "
            "H1894 registry-vs-reality discrepancy this adapter was built against.",
            "When H1894 lands (atomic staging-then-promote fetcher + pinned SourceManifest), "
            "this adapter's build_fixture() should be replaced with one that loads that "
            "snapshot and calls community_lenses.manifests.validate_no_mixed_snapshot on it "
            "before accepting any record.",
        ],
    )
