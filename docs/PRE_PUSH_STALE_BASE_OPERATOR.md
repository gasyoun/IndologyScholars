# Pre-push stale-base and CRLF operator notes

_Created: 14-08-2026 · Last updated: 14-08-2026_

How the hook in [`.githooks/pre-push`](https://github.com/gasyoun/IndologyScholars/blob/main/.githooks/pre-push) decides whether a `git push` is allowed. Wired per clone with `git config core.hooksPath .githooks` (inherited by worktrees). Landed with [PR #179](https://github.com/gasyoun/IndologyScholars/pull/179); the four base-state cases and the fetch retry cap are H2579.

## What runs, in order

1. **Base-state** ([`scripts/pre_push_stale_base_check.py`](https://github.com/gasyoun/IndologyScholars/blob/main/scripts/pre_push_stale_base_check.py)) — **blocks** `behind`, `diverged`, and `remote-advanced`. Uses the live remote tip from pre-push stdin (`--remote-sha`) plus a fetch capped at **5** tries. If every fetch fails and the live tip is not in the object store, the check fails closed.
2. **Line-level silent-revert** (same script) — **warns** by default if the push deletes lines another session added in the last 3 days. Blocks only under `STALE_BASE_PUSH_STRICT=1`. This is the Uprava#1516 class (clean fast-forwards). It is *not* the merge-base test [FINDINGS §312](https://github.com/gasyoun/Uprava/blob/main/FINDINGS.md) measured as vacuous.
3. **CRLF-in-blob** ([`scripts/eol_census.py`](https://github.com/gasyoun/IndologyScholars/blob/main/scripts/eol_census.py) `--changed-since`) — **blocks** any path this push would newly store with CR bytes. Pre-existing CRLF blobs are ignored (ratchet).

A refused hook exits non-zero **before objects are sent**. The remote tip does not move. A normal `git push` of a behind/diverged history is also rejected by git itself (non-fast-forward); the hook is what still refuses the same state under `--force`, which git would otherwise accept.

## Four base states

| State | Meaning | Push |
| --- | --- | --- |
| `clean` | Remote is an ancestor of `HEAD` (fast-forward). | Allowed; line-level + CRLF still run. |
| `behind` | `HEAD` is an ancestor of the remote tip. | **Blocked.** Would rewind the branch. |
| `diverged` | Each side has commits the other does not. | **Blocked.** A `--force` would overwrite the remote. |
| `remote-advanced` | Tracking was stale; after learning the live tip the state is behind or diverged. | **Blocked.** |

`equal` (`HEAD` == remote tip) is treated as nothing to install and is not blocked.

## Recover

```text
git fetch origin
git rebase origin/main
```

If `git status` lists files this session never edited, do not `git add -A` and do not lift a patch out of that tree. Rebuild on a fresh worktree off `origin/main` and re-apply only this session's edits.

A CRLF refusal is fixed with:

```text
git add --renormalize -- <path>
git commit --amend --no-edit
```

## Overrides (leave unset after use)

| Variable | Effect |
| --- | --- |
| `ALLOW_STALE_BASE_PUSH=1` | Skip base-state + line-level. Does **not** skip CRLF. |
| `STALE_BASE_PUSH_STRICT=1` | Line-level hits become a hard block. |
| `ALLOW_CRLF_BLOB_PUSH=1` | Skip the CRLF blob gate. |

## Prove it

```text
python -m pytest tests/test_pre_push_stale_base.py -q
```

Four named cases (behind, diverged, clean, remote-advanced) plus CRLF-on-clean, default-warn silent-revert, and the escape hatch. Each blocking case asserts the bare remote tip is unchanged after `git push`.

_Dr. Mārcis Gasūns_
