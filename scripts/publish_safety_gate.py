"""H2578 — fail-closed publish-safety gate for gated artifacts.

PR #181 treated untracked / gitignored status as the only protection for the
four H1899 closed-list artifacts. That is not a rights decision: a later
``git add`` or CI ``git add curation/*.csv`` publishes them into a public
repo, and ``git rm`` does not unpublish the blobs. PR #183 then published
those paths after filling approver / scope / date / permitted-use.

This gate makes that decision machine-checkable. It fails closed when
approval fields are absent, malformed, or inconsistent with the artifact,
and it never treats ``.gitignore``, file location, or untracked status as
approval. ``prepare_pages_artifact.py`` runs it *before* ``_site`` is
written, so an unsafe publish exits non-zero before artifact upload.

Git status probes retry at most ``GIT_TRIES`` (5) times and then fail
closed — the same cap as the H2579 fetch retry.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

GIT_TRIES = 5
CATALOG_REL = Path("curation") / "rights_approvals.json"
SCHEMA_VERSION = "h2578-1.0.0"

# Always gated. Omitting a row from the catalog cannot un-gate these paths.
GATED_PATHS = (
    "curation/community_person_links.csv",
    "curation/community_quotes.csv",
    "article/comparison_snapshots",
    "analytics_output/community_lenses/reports/identity_quote_evidence.md",
)

APPROVAL_FIELDS = (
    "rights_approver",
    "rights_approval_scope",
    "rights_approval_date",
    "rights_permitted_use",
)

PLACEHOLDERS = frozenset(
    {
        "",
        "tbd",
        "todo",
        "fixme",
        "unknown",
        "n/a",
        "na",
        "none",
        "pending",
        "-",
        "—",
    }
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPORTABLE_VALUES = frozenset({"yes", "no"})
RIGHTS_STATES = frozenset({"non_exportable", "exportable_approved", "pending_review"})

GitFn = Callable[[Path, tuple[str, ...]], "GitResult"]


@dataclass
class GitResult:
    returncode: int
    stdout: str
    stderr: str
    attempts: int


@dataclass
class Finding:
    code: str
    path: str
    detail: str
    remediation: str


@dataclass
class Verdict:
    ok: bool
    findings: list[Finding] = field(default_factory=list)
    inspected: list[str] = field(default_factory=list)
    git_attempts: int = 0

    def to_json(self) -> dict:
        payload = asdict(self)
        payload["verdict"] = "GO" if self.ok else "NO-GO"
        return payload


def posix(path: str | Path) -> str:
    return Path(path).as_posix()


def is_placeholder(value: object) -> bool:
    text = str(value or "").strip()
    return text.lower() in PLACEHOLDERS


def date_ok(value: object) -> bool:
    text = str(value or "").strip()
    if not DATE_RE.match(text):
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def default_git(repo: Path, args: tuple[str, ...]) -> GitResult:
    proc = subprocess.run(
        ("git",) + args,
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return GitResult(proc.returncode, proc.stdout, proc.stderr, 1)


def git_with_cap(
    repo: Path,
    args: tuple[str, ...],
    *,
    git_fn: GitFn = default_git,
    tries: int = GIT_TRIES,
    ok_codes: frozenset[int] = frozenset({0}),
) -> GitResult:
    """Run one git probe, retrying unexpected failures up to ``tries``.

    ``ok_codes`` are treated as a finished probe (no retry). After ``tries``
    unexpected failures the last result is returned; the caller fails closed.
    """
    if tries < 1:
        return GitResult(128, "", "publish-safety: git try cap is 0", 0)
    last = GitResult(128, "", "publish-safety: git did not run", 0)
    for attempt in range(1, tries + 1):
        last = git_fn(repo, args)
        last.attempts = attempt
        if last.returncode in ok_codes:
            return last
    return last


def load_catalog(repo: Path) -> tuple[dict[str, dict], list[Finding]]:
    path = repo / CATALOG_REL
    findings: list[Finding] = []
    if not path.is_file():
        findings.append(
            Finding(
                "missing",
                posix(CATALOG_REL),
                "rights catalog is absent",
                "Create curation/rights_approvals.json with one record per gated "
                "path (approver, scope, YYYY-MM-DD date, permitted use).",
            )
        )
        return {}, findings
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(
            Finding(
                "malformed",
                posix(CATALOG_REL),
                f"catalog is not valid JSON: {exc}",
                "Fix the JSON syntax, then re-run python scripts/publish_safety_gate.py.",
            )
        )
        return {}, findings
    if not isinstance(payload, dict) or not isinstance(payload.get("artifacts"), list):
        findings.append(
            Finding(
                "malformed",
                posix(CATALOG_REL),
                "catalog must be an object with an artifacts array",
                "Restore the h2578 schema (schema_version + artifacts[]).",
            )
        )
        return {}, findings
    by_path: dict[str, dict] = {}
    for index, row in enumerate(payload["artifacts"]):
        if not isinstance(row, dict):
            findings.append(
                Finding(
                    "malformed",
                    posix(CATALOG_REL),
                    f"artifacts[{index}] is not an object",
                    "Each artifacts[] row must be an object with a path.",
                )
            )
            continue
        rel = posix(str(row.get("path") or "").strip())
        if not rel or rel in PLACEHOLDERS:
            findings.append(
                Finding(
                    "malformed",
                    posix(CATALOG_REL),
                    f"artifacts[{index}] has no path",
                    "Set path to a repo-relative gated artifact.",
                )
            )
            continue
        if rel in by_path:
            findings.append(
                Finding(
                    "malformed",
                    rel,
                    "duplicate catalog path",
                    "Keep one approval record per path.",
                )
            )
            continue
        by_path[rel] = row
    return by_path, findings


def approval_problems(row: dict, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    missing = [name for name in APPROVAL_FIELDS if is_placeholder(row.get(name))]
    if missing:
        findings.append(
            Finding(
                "missing",
                rel,
                "approval fields absent or placeholder: " + ", ".join(missing),
                "Record rights_approver, rights_approval_scope, "
                "rights_approval_date (YYYY-MM-DD) and rights_permitted_use "
                f"for {rel} in curation/rights_approvals.json. "
                ".gitignore / untracked / file location is not approval.",
            )
        )
        return findings
    if not date_ok(row.get("rights_approval_date")):
        findings.append(
            Finding(
                "malformed",
                rel,
                f"rights_approval_date {row.get('rights_approval_date')!r} "
                "is not YYYY-MM-DD",
                "Use an ISO date such as 2026-08-07.",
            )
        )
    scope = str(row.get("rights_approval_scope") or "").strip()
    path_leaf = Path(rel).name
    covers = (
        "h1899" in scope.lower()
        or "all four" in scope.lower()
        or path_leaf.lower() in scope.lower()
        or rel.lower() in scope.lower()
    )
    if not covers:
        findings.append(
            Finding(
                "malformed",
                rel,
                "rights_approval_scope does not name this artifact "
                "(or the H1899 umbrella)",
                "Set scope to include this path, or the recorded "
                "'all four H1899 artifacts' umbrella.",
            )
        )
    return findings


def present_on_disk(repo: Path, rel: str) -> bool:
    path = repo / rel
    return path.exists()


def tracking_state(
    repo: Path,
    rel: str,
    git_fn: GitFn,
    tries: int,
) -> tuple[str, int, list[Finding]]:
    """Return tracked | untracked | ignored | unknown plus attempts."""
    listed = git_with_cap(
        repo,
        ("ls-files", "--", rel),
        git_fn=git_fn,
        tries=tries,
        ok_codes=frozenset({0}),
    )
    attempts = listed.attempts
    if listed.returncode != 0:
        return (
            "unknown",
            attempts,
            [
                Finding(
                    "missing",
                    rel,
                    f"git ls-files failed after {attempts} tries "
                    f"(exit {listed.returncode}); fail closed",
                    "Fix git in this worktree, then re-run "
                    "python scripts/publish_safety_gate.py. "
                    "The 5-try cap does not grant approval.",
                )
            ],
        )
    tracked = bool(listed.stdout.strip())
    ignored = git_with_cap(
        repo,
        ("check-ignore", "-q", "--", rel),
        git_fn=git_fn,
        tries=tries,
        ok_codes=frozenset({0, 1}),
    )
    attempts = max(attempts, ignored.attempts)
    if ignored.returncode not in (0, 1):
        return (
            "unknown",
            attempts,
            [
                Finding(
                    "missing",
                    rel,
                    f"git check-ignore failed after {ignored.attempts} tries "
                    f"(exit {ignored.returncode}); fail closed",
                    "Fix git in this worktree, then re-run the gate.",
                )
            ],
        )
    if ignored.returncode == 0:
        return "ignored", attempts, []
    if tracked:
        return "tracked", attempts, []
    return "untracked", attempts, []


def check_quote_register(repo: Path, rel: str, catalog_row: dict) -> list[Finding]:
    path = repo / rel
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows and not path.read_text(encoding="utf-8").strip():
        return [
            Finding(
                "malformed",
                rel,
                "quote register is empty",
                "Restore the register or revoke the catalog approval.",
            )
        ]
    header = set(rows[0].keys()) if rows else set()
    missing_cols = [name for name in APPROVAL_FIELDS if name not in header]
    if missing_cols:
        return [
            Finding(
                "malformed",
                rel,
                "quote register missing columns: " + ", ".join(missing_cols),
                "Keep the rights_* columns from community_lenses.quotes.QUOTE_COLUMNS.",
            )
        ]
    findings: list[Finding] = []
    for row in rows:
        qid = row.get("quote_id") or "?"
        status = (row.get("rights_review_status") or "").strip()
        if status and status not in RIGHTS_STATES:
            findings.append(
                Finding(
                    "malformed",
                    rel,
                    f"{qid}: unknown rights_review_status {status!r}",
                    "Use non_exportable / exportable_approved / pending_review.",
                )
            )
        if status == "exportable_approved":
            empty = [name for name in APPROVAL_FIELDS if is_placeholder(row.get(name))]
            if empty:
                findings.append(
                    Finding(
                        "missing",
                        rel,
                        f"{qid}: exportable_approved but empty {', '.join(empty)}",
                        "Fill the four approval fields on the row, or set "
                        "rights_review_status back to non_exportable.",
                    )
                )
        for name in APPROVAL_FIELDS:
            cell = str(row.get(name) or "").strip()
            expected = str(catalog_row.get(name) or "").strip()
            if cell and expected and cell != expected:
                findings.append(
                    Finding(
                        "malformed",
                        rel,
                        f"{qid}: {name} {cell!r} disagrees with catalog {expected!r}",
                        "Make the row fields match curation/rights_approvals.json, "
                        "or update the catalog to the recorded approval.",
                    )
                )
    return findings


def check_person_links(repo: Path, rel: str, has_approval: bool) -> list[Finding]:
    path = repo / rel
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    findings: list[Finding] = []
    if rows and "exportable" not in rows[0]:
        return [
            Finding(
                "malformed",
                rel,
                "person-links table has no exportable column",
                "Restore the exportable column (yes/no).",
            )
        ]
    for row in rows:
        flag = (row.get("exportable") or "").strip()
        name = row.get("name_as_source") or "?"
        if flag not in EXPORTABLE_VALUES:
            findings.append(
                Finding(
                    "malformed",
                    rel,
                    f"{name}: exportable must be yes or no, got {flag!r}",
                    "Set exportable to yes only when a complete catalog approval exists.",
                )
            )
        elif flag == "yes" and not has_approval:
            findings.append(
                Finding(
                    "missing",
                    rel,
                    f"{name}: exportable=yes without a complete catalog approval",
                    "Record the four approval fields in "
                    "curation/rights_approvals.json for this path, or set "
                    "exportable=no.",
                )
            )
    return findings


def evaluate(
    repo: Path,
    *,
    git_fn: GitFn = default_git,
    tries: int = GIT_TRIES,
) -> Verdict:
    repo = repo.resolve()
    catalog, findings = load_catalog(repo)
    inspected: list[str] = []
    attempts = 0
    subjects = sorted(set(GATED_PATHS) | set(catalog))
    for rel in subjects:
        on_disk = present_on_disk(repo, rel)
        state, used, probe_findings = tracking_state(repo, rel, git_fn, tries)
        attempts = max(attempts, used)
        findings.extend(probe_findings)
        if state == "unknown":
            # Git itself failed the 5-try cap. Further paths would only
            # burn the same cap; fail closed now.
            inspected.append(rel)
            break
        if not on_disk and state == "untracked" and rel not in catalog:
            continue
        inspected.append(rel)
        row = catalog.get(rel)
        approval_findings = approval_problems(row, rel) if row else [
            Finding(
                "missing",
                rel,
                "no catalog approval record for this gated path",
                "Add a complete record to curation/rights_approvals.json. "
                "Untracked or gitignored status is not approval "
                "(IndologyScholars#181).",
            )
        ]
        approval_ok = not approval_findings
        findings.extend(approval_findings)

        if state == "unknown":
            continue
        if state in {"untracked", "ignored"} and approval_ok:
            findings.append(
                Finding(
                    "untracked",
                    rel,
                    f"catalog records approval but the path is {state}",
                    "git add the path (the recorded approval is a publish "
                    "decision), or revoke the catalog row. Do not leave an "
                    "approved artifact untracked — that is the #181/#183 "
                    "inconsistency in reverse.",
                )
            )
        if state == "tracked" and not approval_ok:
            # The missing/malformed finding already covers the rights hole.
            # Label the tracking accident so the fourth named case is visible.
            findings.append(
                Finding(
                    "tracked",
                    rel,
                    "gated path is tracked without a usable approval record",
                    "This is the #181 accident: tracking is not a rights "
                    "decision. Either complete curation/rights_approvals.json "
                    "or git rm --cached the path before any publish.",
                )
            )
        if state == "ignored" and not approval_ok:
            findings.append(
                Finding(
                    "untracked",
                    rel,
                    "gated path is gitignored; that is not approval",
                    "Record an explicit approval or keep the file out of "
                    "prepare_pages_artifact / git add. .gitignore is not a "
                    "rights record.",
                )
            )

        if row and approval_ok:
            kind = str(row.get("kind") or "").strip()
            if kind == "quote_register" or rel.endswith("community_quotes.csv"):
                findings.extend(check_quote_register(repo, rel, row))
            if kind == "person_links" or rel.endswith("community_person_links.csv"):
                findings.extend(check_person_links(repo, rel, True))
        elif on_disk and (
            rel.endswith("community_person_links.csv")
        ):
            findings.extend(check_person_links(repo, rel, False))

    return Verdict(
        ok=not findings,
        findings=findings,
        inspected=inspected,
        git_attempts=attempts,
    )


def format_report(verdict: Verdict) -> str:
    if verdict.ok:
        n = len(verdict.inspected)
        return (
            f"GO: publish-safety gate passed ({n} gated artifact(s) approved).\n"
        )
    lines = [
        f"NO-GO: publish-safety gate failed ({len(verdict.findings)} finding(s))",
        "",
    ]
    for item in verdict.findings:
        lines.append(f"  [{item.code}] {item.path}")
        lines.append(f"    {item.detail}")
        lines.append(f"    Remediation: {item.remediation}")
        lines.append("")
    lines.append(
        "Unsafe publish stopped before any artifact was written or uploaded."
    )
    lines.append("Re-check: python scripts/publish_safety_gate.py")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed rights gate for gated publish artifacts (H2578)."
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="repository root (default: current directory)",
    )
    parser.add_argument("--json", action="store_true", help="print machine JSON")
    parser.add_argument(
        "--tries",
        type=int,
        default=GIT_TRIES,
        help=f"git retry cap (default {GIT_TRIES}); fail closed when exhausted",
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    verdict = evaluate(repo, tries=max(0, args.tries))
    if args.json:
        print(json.dumps(verdict.to_json(), ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(format_report(verdict))
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
