# BVP public archive acquisition

This directory contains the bounded, resumable acquisition layer for the
public Bharatiya Vidvat Parishat Google Group:
<https://groups.google.com/g/bvparishat>.

Two acquisition units exist:

1. `scrape.py` enumerates the 30 conversations exposed in the server-rendered
   first listing page and fetches/parses a caller-bounded number of them.
2. `pagination.py` + `paginate_live.py` (H1892) drive the public "Next page"
   control across several *consecutive* listing pages, checkpointing each
   page and detecting drift.

Neither claims full archive coverage. Google Groups exposes an opaque
continuation token alongside a JavaScript-driven Next button rather than a
stable next-page GET URL, so `paginate_live.py` drives a real headless
Chromium tab (Playwright) to click "Next page" instead of guessing or
replaying the private batchexecute RPC.

## Run

```powershell
python bvp/scrape.py --max-threads 3
python bvp/paginate_live.py --max-pages 3 --delay 2.0
```

`scrape.py`'s default delay is two seconds plus jitter, concurrency is one,
network requests retry once, repeated errors trigger adaptive pauses, and
HTTP 403/429 stops the run. Existing parsed conversations are skipped.

`paginate_live.py` is bounded to exactly 3 pages by design (`--max-pages` other
than 3 is refused) — it is a pilot unit, not an open-ended crawler. It reuses
the same delay/jitter/skip-good-resume posture, one browser tab (concurrency
one), and stops immediately — no retry — on HTTP 403/429 or any of the named
pagination faults in `pagination.py` (repeated page signature, no new IDs,
overlap/backward range, denominator change, premature loss of the Next
control, or schema drift). Checkpoints live in `bvp/data/meta/pagination.json`
(a resumed run skips ordinals already checkpointed).

All acquisition products under `bvp/data/` are ignored by Git:

- `raw/` — exact fetched HTML, including `listing-page-<N>.html` per
  paginated page;
- `meta/state.json` — `scrape.py`'s atomic checkpoint and coverage ledger;
- `meta/pagination.json` — `paginate_live.py`'s atomic per-page checkpoint
  (ordinal, retrieval time, ordered row IDs, row-set SHA-256, displayed
  range/total, hashed cursor evidence, parse status, and any fault);
- `meta/urls_failed.txt` — persistent failures;
- `parsed/` — local evidence records, including rendered message text.

Raw captures and parsed bodies are not publication artifacts. Article quotes
must be selected separately, remain exact, link to a stable public page, retain
enough context for review, and remove unrelated contact/signature material.

## Coverage contract

The state separates `discovered`, `fetched`, `parsed`, `failed`, and `retries`.
`coverage_status=complete` is forbidden until public pagination is enumerated,
the displayed listing denominator reconciles, and every gap is explained. The
H1892 three-page pilot (30-07-2026) reconciled cleanly: 90 unique conversation
IDs across pages 1–3 (ranges 1–30/31–60/61–90 against a stable
`displayed_total=23,468`), zero duplicate IDs, zero faults, and an explicit
`unexplained_gap=23,378` conversations beyond the enumerated three pages —
still `coverage_status=partial`, not complete.

The hardening behavior is adapted from `D:\Tools\wisdomlib-scrape`, but this
repository has no runtime dependency on that external working directory.
