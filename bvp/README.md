# BVP public archive acquisition

This directory contains the bounded, resumable acquisition layer for the
public Bharatiya Vidvat Parishat Google Group:
<https://groups.google.com/g/bvparishat>.

The first unit deliberately does two things only:

1. enumerate the 30 conversations exposed in the server-rendered first listing
   page;
2. fetch and parse a caller-bounded number of those conversation pages.

It does **not** claim full archive coverage. Google Groups exposes an opaque
continuation token and a JavaScript-driven Next button, not a stable next-page
GET URL — `paginate_live.py` (below) drives it, bounded to a caller-set number
of pages.

## Run

```powershell
python bvp/scrape.py --max-threads 3
python bvp/paginate_live.py --out bvp/data --max-pages 3
```

The default delay is two seconds plus jitter, concurrency is one, network
requests retry once, repeated errors trigger adaptive pauses, and HTTP 403/429
stops the run. Existing parsed conversations are skipped.

`paginate_live.py` drives the public "Next page" control in a headless
Chromium tab (Playwright) rather than replaying Google Groups' private
batchexecute RPC contract, and reconciles pages via `pagination.py`
(fetch-agnostic, unit-tested in `tests/test_bvp_pagination.py` without a
browser). Run it directly in the persistent main checkout, not a throwaway
worktree — its output must survive worktree GC (H2297, after H1892's
30-07-2026 pilot output was lost per FINDINGS §314 when its worktree was
deleted before escrow).

All acquisition products under `bvp/data/` are ignored by Git:

- `raw/` — exact fetched HTML;
- `meta/state.json` — atomic checkpoint and coverage ledger;
- `meta/pagination.json` — atomic per-page pagination checkpoint;
- `meta/urls_failed.txt` — persistent failures;
- `parsed/` — local evidence records, including rendered message text.

**One exception:** `meta/manifest_pin.json` is a small hash/pointer record
(per-page `row_set_sha256`/`cursor_evidence_sha256`/`raw_html_sha256`,
retrieval timestamps, reconciliation counts — no row IDs, no HTML) that is
force-added (`git add -f`) and committed despite the blanket `bvp/data/`
ignore, so a fresh `origin/main` worktree can verify the escrowed pilot
output is reachable without touching the raw data itself or re-scraping.

Raw captures and parsed bodies are not publication artifacts. Article quotes
must be selected separately, remain exact, link to a stable public page, retain
enough context for review, and remove unrelated contact/signature material.

## Coverage contract

The state separates `discovered`, `fetched`, `parsed`, `failed`, and `retries`.
`coverage_status=complete` is forbidden until public pagination is enumerated,
the displayed listing denominator reconciles, and every gap is explained.

The hardening behavior is adapted from `D:\Tools\wisdomlib-scrape`, but this
repository has no runtime dependency on that external working directory.
