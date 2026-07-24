_Created: 24-07-2026 · Last updated: 24-07-2026_

# PLAN — vk-ors advanced visualization (media gallery + faceted search + engagement analytics)

**Intended executor: Grok 4.5** (external model, not a Claude tier — this plan is
written so a fresh agent with no memory of this interview can execute it
unattended).

**Goal:** ship a new `vk-ors` retrospective page that is genuinely more advanced
than [nagari's](https://gasyoun.github.io/IndologyScholars/nagari/) — not by
copying its narrative-SVG-charts contract, but by exploiting the one
structural advantage VK has that nagari (a mailing list) cannot: real
photo/video/doc attachments. Three capabilities, one wave-1 build: a media
gallery, faceted client-side search, and deeper engagement analytics
(likes/reposts/comments/views — a dimension nagari has none of).

**Stop condition:** n/a — judgment-gated done. Acceptance bar in
[VERIFICATION](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_vk-ors_advanced_visualization.md).
Turn cap: this is scoped as one 5–8h unattended execution session; if wave-1c
(engagement analytics depth) is not done by then, ship 1a+1b complete and
park 1c as wave-2 (see the priority-order note in the roadmap) — do not leave
all three half-finished.

## Prior art (do not rebuild)

- `vk-ors/vk_ors_archive/{ingest,insights,page}.py` + `fetch.py` — the
  existing pipeline (Uprava
  [H1520](https://github.com/gasyoun/Uprava/blob/main/handoffs/H1520-Sonnet_IndologyScholars_vk-ors-wall-archive-extract_23.07.26.md),
  [H1532](https://github.com/gasyoun/Uprava/blob/main/handoffs/H1532-Sonnet_IndologyScholars_vk-post-inventory-source_23.07.26.md)).
  Read `vk-ors/README.md` and `vk-ors/.ai_state.md` first — they document the
  four existing analysis layers and the fetch→ingest→insights→page order.
  This plan **extends** that pipeline; it does not replace it.
- `nagari/nagari_group_archive/page.py` + `_template.py` — the sibling
  subsystem's self-contained-HTML-no-CDN pattern (narrative + hand-rolled SVG
  + client-side message search). Read it for the *contract* (offline-first,
  no build step, dated header/byline, palette conventions) — but per the
  decisions below, this plan explicitly allows Grok to vendor small JS libs
  rather than hand-roll everything, unlike nagari.
- `/viz-page` (org skill, `github-spine/SKILLS_INDEX.md`) — the org's
  Docusaurus/Observable-Framework house viz pipeline. **Not used here**: it
  targets published multi-page sites (csl-guides-style), not this repo's
  existing single-file-retrospective convention. Noted so Grok doesn't second
  guess the choice.

## Decisions taken (Phase 2 interview, 24-07-2026)

| # | Decision | Why |
|---|---|---|
| 1 | Wave-1 = all three: media gallery (1a) → faceted search (1b) → engagement analytics depth (1c), in that priority order | MG's call; media gallery is the highest-value, most structurally novel piece (real attachments nagari cannot have), so it goes first and is the one that must not slip |
| 2 | Vendor a lightweight JS lib (chart and/or search) instead of hand-rolling everything nagari-style | MG explicitly chose vendoring over pure hand-rolled SVG, on these constraints (see below) |
| 3 | Vendoring constraints: must work fully offline (file:// / GitHub Pages, no CDN at runtime) — **explicitly confirmed by MG**. Applied as defaults from repo convention (nagari's own no-CDN posture + `docs/reuse-rights.md`), not separately re-confirmed: permissive license only (MIT/BSD/Apache-2.0/ISC), single vendored file per lib under `vk-ors/vk_ors_archive/vendor/`, no npm/bundler introduced, ~150KB minified soft ceiling per lib | Public page, repo has standing reuse-rights commitments; "offline" is non-negotiable, the other three are the obvious extension of the same posture and were not contradicted |
| 4 | Media sourcing: fetch real attachment URLs via VK API live pull, hotlink thumbnails (not re-host) | Richest visual result without the storage/copyright exposure of re-hosting |
| 5 | Attachment pipeline: extend `fetch.py` (which already calls `wall.get` live) to also capture raw attachment metadata (post_id, type, url, width/height where available) in the same API pass, as a **new parallel artifact** (e.g. `data/attachments_raw.json` or a new SQLite table via `ingest.py`) | One API pass, no doubled calls; `ingest.py`'s existing "xlsx is read-only" contract is preserved because attachments are new data, not a xlsx rewrite |
| 6 | Link-rot handling: `onerror` JS fallback swaps a broken thumbnail for a "view on VK" card (post text/date/type) — never a broken-image icon | VK CDN URLs are signed/TTL'd and will rot between `fetch.py` refreshes; page must degrade gracefully per-item |
| 7 | Faceted search: client-side, vendored fuzzy/facet search lib indexing a compact per-post JSON array (text, hashtags, year, attachment type, engagement tier) embedded in the page | No server exists (static HTML); matches decision 2 |
| 8 | Engagement-tier definition (wave-1c): percentile buckets of likes/reposts/views **within each year**, with an explicit outlier/"viral" flag (top ~5%) — no time-decay velocity modeling | Simple, explainable, no defensible-decay-window argument needed; MG's pick |
| 9 | Acceptance bar: (a) `python validate_publication.py` + `python -m pytest` stay green: (b) the new page is a single self-contained HTML file with zero runtime requests except the intentionally-hotlinked `vk.com`/VK-CDN thumbnails (verify by loading with network restricted to those hosts — no console errors); (c) old `vk-ors/site/index.html` is not destructively lost — git history is the rollback path, PR diff makes the change auditable; (d) MG does a manual visual look at the live Pages URL | All four explicitly requested by MG |
| 10 | Commit authority: fresh git worktree off `origin/main` (IndologyScholars is a shared-main-tree-guarded repo), push a branch, open a PR, **auto-merge once the mechanical gates in decision 9(a)–(c) pass** | MG's explicit pick, matching this session's own H1532 handoff-scoped autonomy |
| 11 | **Reconciliation note (my judgment call, flagged as such):** decision 9(d) (MG's manual visual look) cannot be a pre-merge blocking gate if decision 10 says auto-merge-on-mechanical-gates — so 9(d) is **post-merge, non-blocking**. Grok's PR description must include a line asking MG to check the live Pages URL after merge, and a GTD follow-up (see Phase 5 below) is filed for it. If the look turns up a problem, a single `git revert` undoes it — cheap, so this doesn't need to block. | Two of MG's own answers were in tension (manual gate vs. auto-merge); resolved rather than left for Grok to improvise mid-build, per `/ask`'s no-blocking-fork rule |
| 12 | Ambiguity policy: pick the documented default below, log the choice in the PR description, keep going — do not stop and park | MG's explicit pick |
| 13 | Fence: nothing outside `vk-ors/`; `.env`/secrets read-only (never printed/committed/rotated); `ingest.py`'s read-only-xlsx contract untouched; no direct edits to any Uprava hub file — Grok documents status only in `vk-ors/.ai_state.md`, a Claude session does the Uprava-side registration afterward (see Phase 5) | `.env`/secrets explicitly confirmed by MG; the other three are the obvious scope boundary implied by "this is a vk-ors visualization build" and Grok not being wired into the Uprava handoff convention |

### Pinned defaults for anticipated ambiguities (decision 12, applied in advance)

- **Lib choice conflicts with the size/license ceiling:** pick any MIT/BSD/
  Apache-2.0/ISC lib that fits; if none fits for a given feature, fall back
  to hand-rolled JS/SVG for that piece only (matches nagari's baseline) —
  never silently exceed the ceiling.
- **VK API rate-limits harder than the existing 0.34s/req pace tolerates:**
  add exponential backoff on 429/error responses in `fetch.py`'s existing
  loop; if a full attachment-metadata pull can't finish inside the session's
  time budget, checkpoint progress by `post_id` and resume rather than
  restarting from offset 0.
- **Engagement-tier definition:** already pinned (decision 8) — do not
  re-derive a different metric mid-build.

## Layer docs

- [ROADMAP_vk-ors_advanced_visualization_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ROADMAP_vk-ors_advanced_visualization_2026.md)
- [ARCHITECTURE_vk-ors_advanced_visualization.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/ARCHITECTURE_vk-ors_advanced_visualization.md)
- [IMPLEMENTATION_vk-ors_advanced_visualization.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/IMPLEMENTATION_vk-ors_advanced_visualization.md)
- [VERIFICATION_vk-ors_advanced_visualization.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/VERIFICATION_vk-ors_advanced_visualization.md)

## Execution handoff

Uprava [H1557](https://github.com/gasyoun/Uprava/blob/main/handoffs/H1557-Sonnet_IndologyScholars_vk-ors-advanced-viz-grok-plan_24.07.26.md)
carries the starter line for Grok.

_Dr. Mārcis Gasūns_
