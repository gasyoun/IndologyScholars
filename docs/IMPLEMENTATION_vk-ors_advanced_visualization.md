_Created: 24-07-2026 · Last updated: 24-07-2026_

# IMPLEMENTATION — vk-ors advanced visualization

Index: [PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md).
Ordered, file-level build sequence. Each step names what it touches and what
it depends on. Read [ARCHITECTURE](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_vk-ors_advanced_visualization.md)
first — this is "how to build it in order," not "what it is."

## Step 0 — Setup (before any code)

1. `git fetch origin && git log origin/main -5` on `IndologyScholars` — confirm
   no newer conflicting work landed since this plan was written (same
   discipline as `.ai_state.md`'s own protocol; a prior session in this exact
   repo got this wrong once — see H1532's "lesson for future sessions").
2. Work in a **fresh worktree**, not the shared main tree (IndologyScholars is
   one of the org's 16 guarded repos):
   `git worktree add -b vk-ors-advanced-viz ../IndologyScholars-vk-ors-advanced-viz origin/main`
3. Copy `.env` into the worktree root (gitignored, not carried by worktree
   creation) — needed for `fetch.py`'s `VK_ACCESS_TOKEN`/`VK_DOMAIN`/
   `VK_API_VERSION`.
4. Read (don't skim) `vk-ors/vk_ors_archive/fetch.py`, `ingest.py`,
   `insights.py`, `page.py`, `vk-ors/README.md`, `vk-ors/.ai_state.md`.

## Step 1 — Wave 1a: attachment metadata pipeline

1. `vk-ors/vk_ors_archive/fetch.py`: add attachment extraction inside the
   existing `fetch_all_posts`/`to_row` loop (do not add a second `wall.get`
   pass). Write `data/attachments_raw.json` per ARCHITECTURE delta 1.
   Verify: `python -m vk_ors_archive.fetch` still writes `vk_posts_all.xlsx`
   exactly as before (byte-for-byte column layout unchanged) *and* the new
   JSON.
2. `vk-ors/vk_ors_archive/ingest.py` (or a new sibling module wired into the
   same `__main__`): add the `attachments` table + load from
   `attachments_raw.json`. Verify: `python -m vk_ors_archive.ingest` still
   produces the same `posts`/`hashtags`/`posts_fts` row counts as before this
   change, plus a populated `attachments` table.
3. `vk-ors/vk_ors_archive/insights.py`: add the gallery export (joins
   `attachments`→`posts`) → `data/processed/attachments_gallery.csv` +
   `gallery` key in `site_data.json`.
4. Verify with `--limit` flags first (fast slice), then a full run.

## Step 2 — Wave 1a: gallery UI

1. `vk-ors/vk_ors_archive/page.py`: add the gallery section — grid render
   from the `gallery` JSON, `onerror` fallback per ARCHITECTURE's guardrail
   section. No search/facets yet (that's step 4) — a plain grid with
   attachment-type filter buttons is a valid 1a-only checkpoint.
2. Verify: open `site/index.html` locally, spot-check ~10 thumbnails render,
   spot-check the `onerror` fallback by editing one URL to garbage and
   confirming the "view on VK" card appears instead of a broken image.

**Checkpoint: if time is short, stop here with 1a fully working and open the
PR now (see VERIFICATION) rather than starting 1b half-committed.**

## Step 3 — Wave 1c schema (engagement tiers) — do this before 1b's UI

Do the data-layer half of 1c now, even though its UI comes after 1b, because
1b's search index embeds `engagement_tier`/`is_outlier` per post (Architecture
delta 3) — building the facet data twice would be wasted work.

1. `insights.py`: add the percentile-tier + outlier computation (ARCHITECTURE
   delta 2, decision 8's definition — do not substitute a different metric).
   Write `data/processed/engagement_tiers.csv`.
2. Fold `engagement_tier`/`is_outlier` into the per-post objects that will
   become the wave-1b search index (see step 4).

## Step 4 — Wave 1b: search index + vendored lib

1. Pick a vendored search/facet lib meeting the constraints in PLAN decision
   3. Vendor it to `vk-ors/vk_ors_archive/vendor/<lib>.js` with a provenance
   comment (name/version/license/source URL).
2. `insights.py` (or `page.py` directly, Grok's call — document which):
   assemble the compact per-post JSON array (id/date/year/text/tags/
   attachment_types/engagement_tier/is_outlier/url) and embed it inline in
   `site/index.html`.
3. `page.py`: wire the vendored lib against that inline array; build the
   search box + facet chips; make filtering re-render both the search
   results and the gallery grid from step 2 (shared filtered state).
4. Verify: search for a known hashtag (e.g. `bookzealots`), confirm result
   count is sane against `data/processed/hashtags.csv`'s existing count for
   that tag; toggle each facet type once and confirm the result set changes.

## Step 5 — Wave 1c UI: engagement explorer

1. `page.py`: add the engagement-explorer section — interactive
   year/tier view (vendored chart lib if one was already brought in for
   search and covers charts too; otherwise hand-rolled SVG per the fallback
   rule in PLAN's pinned defaults) + a "top posts this tier" list wired to
   the same facet state as step 4.
2. Only attempt this step if steps 1–4 are fully done and gated green — see
   ROADMAP's "if the time budget runs out" rule.

## Step 6 — Full pipeline re-verification

`python -m vk_ors_archive.fetch && python -m vk_ors_archive.ingest &&
python -m vk_ors_archive.insights && python -m vk_ors_archive.page` — clean
full run, no manual patching between stages. Then the repo-level gates —
see [VERIFICATION](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_vk-ors_advanced_visualization.md).

## Step 7 — Docs + handoff hygiene

1. Update `vk-ors/README.md` (new stage-of-pipeline table row(s) if a new
   module file was added) and `vk-ors/.ai_state.md` (Completed section,
   dated, with the PR link) — same convention as H1520/H1532's entries.
2. Do **not** edit any Uprava file (fence, PLAN decision 13) — instead, the
   PR description must include a one-line note: "Uprava hub registration
   (GTD/PROJECT_INTERLINKS) still needed — follow-up for a Claude session."
3. PR description includes: which vendored lib(s) were chosen and why, the
   engagement-tier weighting formula actually used, whether 1c shipped or was
   parked, and the post-merge visual-check ask (PLAN decision 11).

## Step 8 — Commit, PR, merge

Per PLAN decision 10: push the worktree branch, open a PR, auto-merge once
the mechanical gates in VERIFICATION pass. Remove the worktree after (both
`IndologyScholars` and, if one was needed for handoff bookkeeping, `Uprava`).

_Dr. Mārcis Gasūns_
