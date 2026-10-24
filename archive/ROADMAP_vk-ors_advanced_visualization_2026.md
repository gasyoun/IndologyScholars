_Created: 24-07-2026 · Last updated: 24-07-2026_

# ROADMAP — vk-ors advanced visualization

Index: [PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md).

## Wave 1a — Media gallery (do first, must not slip)

- Extend `fetch.py` to capture raw attachment metadata (photo/video/doc URLs,
  types, sizes) alongside the existing xlsx write, keyed by `post_id`.
- New ingest step (in `ingest.py` or a sibling module) loads this into a
  new `attachments` table (post_id, type, url, width, height, position) —
  additive, does not touch the existing `posts`/`hashtags`/`posts_fts` schema
  or `ingest.py`'s read-only xlsx contract.
- `insights.py` gains a 5th layer (or extends layer 4): a gallery-ready export
  — one row per attachment, joined to its post's date/text/tags/engagement —
  written to `data/processed/attachments_gallery.csv` + folded into
  `data/site_data.json`.
- `page.py` renders a gallery view: grid of hotlinked thumbnails, `onerror`
  fallback to a "view on VK" card (decision 6), filterable by
  attachment type at minimum (full faceting is wave-1b).

## Wave 1b — Faceted search

- Vendor a small client-side search/facet lib (decision 2–3 constraints) under
  `vk-ors/vk_ors_archive/vendor/`.
- Embed a compact per-post JSON index (text, hashtags, year, attachment
  type(s), engagement tier — see 1c) directly in the page.
- UI: search box + facet filters (hashtag, year, attachment type, engagement
  tier), results re-render the gallery/post list live, no page reload.

## Wave 1c — Engagement analytics depth

- `insights.py` computes the percentile-tier + outlier/"viral" flag per post
  within its year (decision 8) into a new
  `data/processed/engagement_tiers.csv`.
- Page surfaces this as: (a) a facet in 1b's search, (b) a small explorable
  "top posts this tier" view, (c) an interactive time-series of engagement by
  year/tier (vendored chart lib or hand-rolled SVG per the fallback rule).

## If the time budget runs out mid-build

Priority order is 1a → 1b → 1c. Ship 1a and 1b fully working, end to end
(`fetch` → `ingest` → `insights` → `page`, gates green) before spending
remaining budget on 1c. A complete 1a+1b with 1c explicitly parked as wave-2
in the PR description is a correct wave-1 outcome; three simultaneously
half-finished features is not.

## Non-goals (this wave)

- Re-hosting/downloading media into the repo (decision 4 — hotlink only).
- Replacing nagari's own page or unifying the two subsystems' visual design.
- A cross-venue (nagari + vk-ors) combined view — flagged as an optional
  future follow-up in both subsystems' `.ai_state.md`, not part of this plan.
- Registering this work in Uprava hub files (GTD/PROJECT_INTERLINKS) — fence
  item, left for a Claude follow-up session (see PLAN Phase 5 / decision 13).

_Dr. Mārcis Gasūns_
