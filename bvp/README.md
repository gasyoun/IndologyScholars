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
GET URL. Pagination needs its own tested unit.

## Run

```powershell
python bvp/scrape.py --max-threads 3
```

The default delay is two seconds plus jitter, concurrency is one, network
requests retry once, repeated errors trigger adaptive pauses, and HTTP 403/429
stops the run. Existing parsed conversations are skipped.

All acquisition products under `bvp/data/` are ignored by Git:

- `raw/` — exact fetched HTML;
- `meta/state.json` — atomic checkpoint and coverage ledger;
- `meta/urls_failed.txt` — persistent failures;
- `parsed/` — local evidence records, including rendered message text.

Raw captures and parsed bodies are not publication artifacts. Article quotes
must be selected separately, remain exact, link to a stable public page, retain
enough context for review, and remove unrelated contact/signature material.

## Coverage contract

The state separates `discovered`, `fetched`, `parsed`, `failed`, and `retries`.
`coverage_status=complete` is forbidden until public pagination is enumerated,
the displayed listing denominator reconciles, and every gap is explained.

The hardening behavior is adapted from `D:\Tools\wisdomlib-scrape`, but this
repository has no runtime dependency on that external working directory.
