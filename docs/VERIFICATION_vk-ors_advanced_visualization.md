_Created: 24-07-2026 · Last updated: 24-07-2026_

# VERIFICATION — vk-ors advanced visualization

Index: [PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md).

## Acceptance criteria per deliverable

| Deliverable | Proof |
|---|---|
| `fetch.py` attachment capture | `python -m vk_ors_archive.fetch` writes both `vk_posts_all.xlsx` (unchanged column layout, row count matches post count) and `data/attachments_raw.json`; spot-check 5 posts with known attachments (e.g. from `data/processed/attachments_by_type.csv`) have matching entries |
| `attachments` table | `python -m vk_ors_archive.ingest` — row count in `attachments` table is close to (not necessarily equal — some attachment types may be legitimately skipped, document which) the sum of `n_attachments` across `posts` |
| Gallery export + UI | `attachments_gallery.csv` non-empty, joins cleanly to post metadata (no orphan `post_id`s); `site/index.html` gallery grid renders thumbnails; `onerror` fallback manually verified once (break one URL, confirm graceful card, not a broken-image icon) |
| Engagement tiers | `engagement_tiers.csv` — every post has a tier, `is_outlier` is boolean, roughly ~5% of each year's posts are flagged outlier (sanity-check the percentile math, don't just trust it ran) |
| Search/facets | Searching a known hashtag returns a result count consistent with `hashtags.csv`; every facet (hashtag/year/attachment-type/engagement-tier) changes the visible result set when toggled |
| Engagement explorer (if shipped) | Time-series/tier view renders without console errors; "top posts this tier" list is non-empty and matches the CSV |
| Vendored lib | File exists under `vk-ors/vk_ors_archive/vendor/`, has a provenance comment (name/version/license/source), license is MIT/BSD/Apache-2.0/ISC, file size under ~150KB minified (soft ceiling — if exceeded, document why in the PR rather than silently shipping) |

## Gates before merge (mechanical — these must pass for auto-merge per PLAN decision 10)

1. `python validate_publication.py` — green, unchanged from before this
   work started (this plan does not touch the scholars/presentations corpus
   at all — a red result here means something leaked outside the fence).
2. `python -m pytest` — same pass count or higher than the pre-work baseline
   (176 as of 23-07-2026; confirm the current baseline with
   `git log -1 --format=%H` before starting, in case it moved).
3. `python -m vk_ors_archive.fetch && python -m vk_ors_archive.ingest &&
   python -m vk_ors_archive.insights && python -m vk_ors_archive.page` — full
   pipeline runs clean end to end, no manual intervention between stages.
4. Self-contained-file check: open `site/index.html` with network access
   restricted to `vk.com`/VK CDN hosts only (or inspect the page's outbound
   requests in devtools) — zero requests to any other host, zero console
   errors. This is the offline/no-CDN contract (PLAN decision 3) — verify it,
   don't just assert it.
5. `git diff --stat` against `origin/main` touches only paths under `vk-ors/`
   plus the four new/updated `docs/*.md` files from this plan — nothing else
   (fence, PLAN decision 13). A diff touching `nagari/`, root scholars
   pipeline files, or any `Uprava/` path fails this gate.

## Non-blocking, post-merge (PLAN decision 11)

- MG's manual visual look at the live GitHub Pages URL. Grok's PR description
  must include this ask explicitly; it does not block auto-merge. A file a
  GTD follow-up (see below) so it isn't silently forgotten.
- Uprava hub registration (GTD_NEXT_ACTIONS/PROJECT_INTERLINKS) for this new
  capability — fenced out of Grok's scope, left for a Claude session.

## Risks & things to watch (not spikes — known and pre-mitigated in the plan, listed so Grok doesn't rediscover them the hard way)

- **VK CDN URL rot** — mitigated by the `onerror` fallback (decision 6);
  don't skip building it "for later."
- **Video attachments have no direct playable URL from `wall.get`** without
  an extra `video.get` call — explicitly out of scope for wave-1
  (ARCHITECTURE delta 1); link-out only for video, do not attempt to fetch
  playable video URLs this wave.
- **VK API rate limiting** — pinned fallback in PLAN's "pinned defaults"
  section; don't invent a different backoff strategy.
- **Scope creep into 1c** at the expense of 1a/1b landing cleanly — the
  ROADMAP's priority order and "if time runs out" rule exist specifically to
  prevent this; re-read it if unsure which piece to prioritize.

_Dr. Mārcis Gasūns_
