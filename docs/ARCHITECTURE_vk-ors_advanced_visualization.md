_Created: 24-07-2026 · Last updated: 24-07-2026_

# ARCHITECTURE — vk-ors advanced visualization

Index: [PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/PLAN_vk-ors_advanced_visualization_grok_2026-Q3.md).
Read `vk-ors/README.md`, `vk-ors/.ai_state.md`, and the four existing pipeline
modules before touching anything — this document describes deltas, not the
whole system.

## Current data flow (unchanged, read before extending)

```
fetch.py --live wall.get--> vk_posts_all.xlsx (gitignored, regenerable)
ingest.py --read-only--> data/vk_ors.db (posts, hashtags, posts_fts)
insights.py --> data/processed/*.csv + data/site_data.json
              (keys: totals, activity, engagement, topics, sanskrit, books_top)
page.py --> site/index.html (self-contained, no CDN)
```

`ingest.py`'s xlsx read is a hard contract (fence item, decision 13) — do not
change what it reads or how. All new capability in this plan is **additive**:
new artifacts, a new table, new `site_data.json` keys, new page sections.

## Delta 1 — attachment metadata capture (wave-1a)

`fetch.py` already performs a live, paginated `wall.get` call and currently
throws away everything except `attachment_count`/`attachment_types` when
flattening to xlsx rows (see its `to_row()` — that's the discard point).
Add a **parallel write** in the same fetch loop:

- For each post, extract from the raw `attachments` list: `type`
  (photo/video/doc/link/audio/poll), a stable id, a usable URL (for `photo`:
  the largest `sizes[]` entry's `url`; for `doc`: `url`; for `video`: the
  best available `photo_*` preview field — VK's video objects don't expose a
  direct playable URL without an extra `video.get` call, which is **out of
  scope** for wave-1 — link out to the VK post for video, thumbnail only for
  photo/doc), and `width`/`height` where present.
- Write to a new artifact, e.g. `data/attachments_raw.json`
  (`{post_id: [{type, url, width, height, position}, ...]}`), alongside the
  xlsx write. One API pass — do not add a second round of `wall.get` calls.
- `ingest.py` (or a new sibling `ingest_attachments.py` invoked from the same
  `__main__` entry point — Grok's call, document the choice) loads this into
  a new SQLite table:

```sql
CREATE TABLE attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id      INTEGER REFERENCES posts(id),
    type         TEXT,
    url          TEXT,
    width        INTEGER,
    height       INTEGER,
    position     INTEGER
);
CREATE INDEX idx_attachments_post ON attachments(post_id);
CREATE INDEX idx_attachments_type ON attachments(type);
```

- `insights.py` gains a gallery export joining `attachments` to
  `posts`/`hashtags` (date, text snippet, tags, engagement counts) →
  `data/processed/attachments_gallery.csv`, and a compact array folded into
  `site_data.json` under a new `gallery` key.

## Delta 2 — engagement tiers (wave-1c, but the schema addition happens once)

`insights.py`'s existing engagement layer already computes sums/averages by
year. Add, per post: `engagement_tier` = percentile bucket of
`likes+reposts+views` (weighting is Grok's call, document it) **within its
own year**, plus a boolean `is_outlier` for the top ~5% (decision 8, PLAN
table). Write `data/processed/engagement_tiers.csv` (post_id, tier,
is_outlier) and fold `engagement_tier`/`is_outlier` into each post's entry in
the `gallery`/search-index JSON so wave-1b's facets can filter on it without
a second data structure.

## Delta 3 — client-side search index (wave-1b)

A single compact JSON array, one object per post:
`{id, date, year, text, tags[], attachment_types[], engagement_tier,
is_outlier, url}` — embedded inline in `site/index.html` (same pattern as
nagari embedding `site_data.json`-derived data; do not fetch it via a
separate request, that would break the offline/no-CDN contract for local
`file://` viewing). Vendored search lib (decision 2/3) indexes this array
client-side; facet filters (hashtag, year, attachment type, engagement tier)
narrow both the search results and the gallery grid — one shared filtered
state, not two separate UIs.

## UI composition (`page.py`)

Three new/extended sections, additive to the existing narrative+stats page:

1. **Gallery** — grid of attachment thumbnails (hotlinked `<img src=...
   onerror="...">` per decision 6's fallback), each linking to its post on
   vk.com.
2. **Search/facets** — a search box + facet chips (hashtag/year/type/tier)
   above the gallery and/or a post-list view; filtering re-renders both.
3. **Engagement explorer** — a small interactive view (vendored chart lib or
   hand-rolled SVG, per the size-ceiling fallback rule) of engagement by
   year/tier, and a "top posts this tier" list.

Keep the existing four analysis-layer sections (activity, engagement basics,
topics/hashtags, sanskrit/attachments) — this plan extends the page, it does
not replace it.

## Vendored dependency placement

`vk-ors/vk_ors_archive/vendor/<lib>.min.js` (or `.js` if unminified and under
the size ceiling), loaded via a local `<script>` tag in the generated HTML —
never a CDN `<script src="https://...">`. Record each vendored lib's name,
version, license, and source URL in a short comment block at the top of its
vendored file (matches how the repo already documents provenance elsewhere,
e.g. `docs/data_dictionary.md`'s field-source notes).

## Guardrails carried forward (same as nagari/vk-ors's existing ones)

Likes/reposts/views are engagement, not scholarly or curatorial value;
hashtags are the page author's self-classification, not a curated taxonomy;
"viral"/outlier framing (delta 2) is a statistical percentile label, not a
claim about content quality — say so in the page's own copy near the
engagement explorer, mirroring the existing "Оговорки" section in
`vk-ors/README.md`.

_Dr. Mārcis Gasūns_
