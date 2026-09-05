_Created: 15-08-2026 · Last updated: 05-09-2026_

_Measured: 29-07-2026 (single-page smoke), 06-08-2026 (three-page pagination pilot v2) · Status: local bounded acquisition_

# BVP public source assessment

## Verdict

**GO for bounded, checkpointed acquisition; PARTIAL for quantitative use.**

`https://groups.google.com/g/bvparishat` returned HTTP 200. The initial archive
page and individual conversations are server-rendered without login. Google
Groups exposes stable conversation IDs, native message IDs, subjects, public
display names, timestamps, message HTML, and a displayed archive denominator.

The first listing page has no stable next-page GET link. It exposes an opaque
continuation token and a JavaScript-driven Next button. Therefore this unit
does not claim full archive enumeration.

## Smoke result

| Measure | Observed |
|---|---:|
| Displayed conversations | 23,467 |
| First-page range | 1–30 |
| Unique conversation IDs discovered | 30 |
| Conversation pages fetched | 30 |
| Conversation pages parsed | 30 |
| Native messages identified | 156 |
| Incomplete public message records | 1 |
| Permanent failures | 0 |
| Retries | 2 |
| Coverage status | `partial` |

Both the DOM and embedded archive denominator were 23,467 in the frozen
listing capture. All 30 enumerated conversation pages were saved and produced
156 unique native message IDs. Twenty-nine threads parsed through embedded
`ds:7` data; one promotional thread fell back to the semantic DOM and exposes
one native message ID but no usable public author/body. It is recorded as
incomplete and must be excluded from content/person denominators. Resume runs
reused good thread captures and recovered from two transient listing failures
with the bounded retry path. Parsed message fields include exact subject, native
message ID, public author display, public Google actor ID where exposed,
epoch timestamp, exact HTML body, derived text, and SHA-256 hashes.

## Storage and evidence limits

Raw HTML, checkpoints, failure ledgers, and parsed bodies are local under
ignored `bvp/data/`. No attachment was fetched. No email address is inferred:
the signed-out public interface anonymizes addresses. Parsed bodies may contain
quoted replies, signatures, or contact data and are not publication-ready.

Quantitative article claims remain disabled until listing pagination,
discovered IDs, fetched pages, parsed records, exclusions, and failures
reconcile. Exact article quotations require a stable public URL, context audit,
and removal of unrelated contact/signature material without paraphrasing.

## Three-page pagination pilot v2 (H2297, 06-08-2026 — H1892 redo)

H1892's own pagination pilot (30-07-2026) ran successfully but its output
lived only inside a one-off worktree that was deleted before durable escrow
(FINDINGS §314) — the original numbers below are gone, not approximated.
`bvp/pagination.py` and `bvp/paginate_live.py` (built during H1892, tested,
but stranded on an unmerged branch until H2297 recovered them onto `main`
via [PR #174](https://github.com/gasyoun/IndologyScholars/pull/174)) drive
the public "Next page" control in a headless Chromium tab (Playwright).
Bounded to exactly three consecutive listing pages, run directly in the
persistent main checkout so the raw pages and pin record are already in a
location that survives worktree GC:

| Measure | Observed (06-08-2026) | Observed (30-07-2026, destroyed) |
|---|---:|---:|
| Pages requested / completed | 3 / 3 | 3 / 3 |
| Displayed total (stable across all 3 pages) | 23,476 | 23,468 |
| Listed rows | 90 | 90 |
| Unique conversation IDs | 90 | 90 |
| Duplicate IDs | 0 | 0 |
| Faults | 0 | 0 |
| Unexplained gap (beyond the 3 enumerated pages) | 23,386 | 23,378 |
| Coverage status | `partial` | `partial` |

Page ranges reconciled exactly sequentially (1–30, 31–60, 61–90) with no
overlap and no repeated row-set signature — a completely independent set of
90 conversation IDs from the 30-07-2026 run (Google Groups' listing order is
not stable across runs; row-ID overlap between the two pilots was not
checked and is not required by either handoff's definition of done). The
denominator grew by 8 conversations over the eight days between pilots,
consistent with ordinary list growth. `coverage_status` remains `partial` by
contract. Escrow: manifest + raw pages sit in `bvp/data/` inside this
persistent main checkout (gitignored, per H2242's "simplest" convention); a
small hash/pointer record, `bvp/data/meta/manifest_pin.json` (per-page
`row_set_sha256`/`cursor_evidence_sha256`/`raw_html_sha256`, retrieval
timestamps, reconciliation counts), is force-added and committed so a fresh
`origin/main` worktree can verify reachability without touching the raw
data or re-scraping. Fixture tests for repeated-page, overlap/backward-range,
denominator-change, no-new-IDs, interruption/resume, and HTTP 403/429-stop
live in `tests/test_bvp_pagination.py` (recovered alongside the pagination
driver, still green: 12/12 with `tests/test_bvp_scrape.py`).

## Next bounded unit

Extend the pagination pilot beyond three pages under the same fault
contract, or begin the person/author identity-resolution pass over the
already-checkpointed conversation IDs. Full-archive (~23,476-conversation)
enumeration remains out of scope until a much larger bounded run is
explicitly authorized.

_Dr. Mārcis Gasūns_
