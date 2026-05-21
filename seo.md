Next SEO moves:

SEO-D step 3 — Person JSON-LD upgrade on scholar pages: add givenName/familyName split, gender, knowsAbout from dominant_theme, affiliation linked by @id to the new institution pages. Highest-leverage block once Phase 2a identity reconciliation populates sameAs
SEO-C — Yandex-specific robots.txt (Clean-param, Host), hreflang annotations on landing pages, per-page RU-tuned <meta name="description"> + keywords
~~SEO-E step 1~~ DONE 2026-05-20 — site_data.js → async JSON fetch + preload; CDN gzip 1557 KB → 180 KB; blocking script removed
~~SEO-F~~ DONE 2026-05-21 — `patch_index_stats()` in `generate_publication_pages.py` updates the four `#stat-*-count` divs, `stat-years-desc`, and per-series year strings (RU + EN) on every CI rebuild. Crawlers and tools without JS execution now see live numbers (226 / 899 / 23 / 39 / 2026) instead of stale hardcoded fallbacks. `index.html` added to the workflow's `git add` list.
Build matching preferred_latin_name handoff — same paste-flow infrastructure but for the 32 cross-conference scholars, fixing vertogradova-viktoriya → victoria-vertogradova style published-name slugs