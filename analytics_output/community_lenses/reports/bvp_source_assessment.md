_Measured: 29-07-2026 (single-page smoke), 30-07-2026 (three-page pagination pilot) · Status: local bounded acquisition_

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

## Three-page pagination pilot (H1892, 30-07-2026)

`bvp/paginate_live.py` drives the public "Next page" control in a headless
Chromium tab (Playwright) rather than replaying Google Groups' private
batchexecute RPC contract. Bounded to exactly three consecutive listing
pages this run:

| Measure | Observed |
|---|---:|
| Pages requested / completed | 3 / 3 |
| Displayed total (stable across all 3 pages) | 23,468 |
| Listed rows | 90 |
| Unique conversation IDs | 90 |
| Duplicate IDs | 0 |
| Faults | 0 |
| Unexplained gap (beyond the 3 enumerated pages) | 23,378 |
| Coverage status | `partial` |

Page ranges reconciled exactly sequentially (1–30, 31–60, 61–90) with no
overlap and no repeated row-set signature. `coverage_status` remains
`partial` by contract — a clean 3-page pilot is not archive-wide coverage.
Fixture tests for repeated-page, overlap/backward-range, denominator-change,
no-new-IDs, interruption/resume, and HTTP 403/429-stop live in
`tests/test_bvp_pagination.py`.

## Next bounded unit

Extend the pagination pilot beyond three pages under the same fault
contract, or begin the person/author identity-resolution pass over the 90
already-checkpointed conversation IDs. Full-archive (23,468-conversation)
enumeration remains out of scope until a much larger bounded run is
explicitly authorized.
