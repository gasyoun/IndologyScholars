_Created: 24-07-2026 · Last updated: 24-07-2026_

# Metadoc — PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md

**Purpose:** execution-ready plan for an unattended agent (Grok 4.5) to build
a media-gallery + faceted-search + engagement-analytics upgrade to the
`vk-ors` retrospective page, front-loading every architectural/tooling
decision so the build never has to stop and ask.

**Audience:** the executing agent (Grok 4.5, external — not a Claude tier);
secondarily any Claude session picking up an interrupted/incomplete run, and
MG reviewing the eventual PR.

**Provenance:** minted via `/ask` (heavyweight interview skill), Sonnet 5
(`claude-sonnet-5`), 24-07-2026, in the same session that shipped the
`fetch.py` live-refresh stage (Uprava H1532, PR #140). Interview ran 4 rounds
/ ~14 questions (fewer, denser rounds than the skill's nominal 3–5×4–6,
justified because the Phase-1 audit — reading `vk-ors/README.md`,
`.ai_state.md`, `nagari/page.py`, and `SKILLS_INDEX.md`'s `/viz-page` entry —
had already answered most of the "what exists" questions before the
interview started). Tracked as Uprava H1557.

**Ranked improvement backlog:**
1. If Grok's execution surfaces that the vendored search lib also covers
   charting well, fold the engagement-explorer chart into the same lib
   rather than hand-rolling SVG — cheaper than the plan's fallback path.
2. Video-attachment playable-URL support (needs `video.get`, explicitly
   deferred) is the natural wave-2 candidate once wave-1's `video.get`
   call-budget impact is measured.
3. Cross-referencing vk-ors and nagari engagement/topic trends (flagged as a
   non-goal here) is worth revisiting once both subsystems have comparable
   analytics depth — currently nagari has no engagement layer at all.

**Limitations:**
- This plan was written without Grok in the loop — all "Grok's call, document
  it" markers are genuine open implementation choices, not oversights; they
  were deliberately left open because they are non-blocking (any reasonable
  choice satisfies the constraints), unlike the pinned decisions.
- The interview's Phase-2 answers came from MG in a single sitting; no second
  round-trip was possible to resolve MG's decision 9/10 tension live, so it
  was resolved by documented judgment (PLAN decision 11) rather than a
  further question — flagged there for review.

**Revision history:**
- 24-07-2026 — created (Sonnet 5, `claude-sonnet-5`).

_Dr. Mārcis Gasūns_
