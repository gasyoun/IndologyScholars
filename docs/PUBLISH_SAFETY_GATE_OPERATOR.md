# Publish-safety gate operator notes

_Created: 15-08-2026 · Last updated: 15-08-2026_

How [`scripts/publish_safety_gate.py`](https://github.com/gasyoun/IndologyScholars/blob/main/scripts/publish_safety_gate.py) decides whether gated artifacts may be published. Wired into [`prepare_pages_artifact.py`](https://github.com/gasyoun/IndologyScholars/blob/main/prepare_pages_artifact.py) and the [Rebuild & Deploy](https://github.com/gasyoun/IndologyScholars/blob/main/.github/workflows/rebuild_and_deploy.yml) workflow **before** `actions/upload-pages-artifact`. Landed with H2578 after [PR #181](https://github.com/gasyoun/IndologyScholars/pull/181) (gitignore-only protection) and [PR #183](https://github.com/gasyoun/IndologyScholars/pull/183) (explicit approval, then publish).

## What is gated

These four H1899 paths are **always** gated. Dropping a row from the catalog cannot un-gate them:

| Path | Kind |
| --- | --- |
| [`curation/community_person_links.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/community_person_links.csv) | person links (`exportable`) |
| [`curation/community_quotes.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/community_quotes.csv) | quote register |
| [`article/comparison_snapshots/`](https://github.com/gasyoun/IndologyScholars/tree/main/article/comparison_snapshots) | frozen comparison packages |
| [`analytics_output/community_lenses/reports/identity_quote_evidence.md`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/community_lenses/reports/identity_quote_evidence.md) | identity/quote evidence report |

Approval lives only in [`curation/rights_approvals.json`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/rights_approvals.json): `rights_approver`, `rights_approval_scope`, `rights_approval_date` (`YYYY-MM-DD`), `rights_permitted_use`.

`.gitignore`, file location, and untracked status are **never** approval.

## Four cases

| Case | Meaning | Publish |
| --- | --- | --- |
| `approved` | Catalog record complete and well-formed; path is tracked; artifact fields do not contradict the catalog. | Allowed. |
| `missing` | Gated path exists or is tracked, but approval fields are absent or placeholders (`TBD`, `TODO`, empty). | **Blocked.** |
| `malformed` | Date not `YYYY-MM-DD`, scope does not name the artifact or the H1899 umbrella, unknown `rights_review_status`, or row fields disagree with the catalog. | **Blocked.** |
| `tracked` / `untracked` | Tracked without a usable approval (the #181 accident), or catalog-approved but still untracked/gitignored. | **Blocked.** |

Git probes (`ls-files`, `check-ignore`) retry at most **5** times. If every try fails, the gate fails closed. The cap does not grant approval.

A refused gate exits non-zero **before** `_site` is created and **before** the Pages upload step. No gated bytes are copied into the artifact on NO-GO.

## Recover

```text
python scripts/publish_safety_gate.py
```

Example NO-GO for a missing approval:

```text
NO-GO: publish-safety gate failed (1 finding(s))

  [missing] curation/community_quotes.csv
    no catalog approval record for this gated path
    Remediation: Add a complete record to curation/rights_approvals.json. Untracked or gitignored status is not approval (IndologyScholars#181).

Unsafe publish stopped before any artifact was written or uploaded.
Re-check: python scripts/publish_safety_gate.py
```

Fill the four fields in the catalog (and the matching CSV columns when the artifact is a register), `git add` the path, re-run the command. Do not `git add -A` a gated file to "make the warning go away".

## Prove it

```text
python -m pytest tests/test_publish_safety_gate.py -q
```

Four named cases plus gitignore-is-not-approval, the 5-try cap, live-repo GO, and the upload-callback proof that `publish()` never reaches artifact upload on NO-GO.

_Dr. Mārcis Gasūns_
