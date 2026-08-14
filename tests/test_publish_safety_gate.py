"""H2578 — four rights-gate cases + fail-closed publish + 5-try cap.

Named cases (the stop condition):

- approved
- missing
- malformed
- accidentally tracked / untracked

Plus: an unsafe ``publish()`` must exit non-zero *before* ``_site`` exists
and before any upload callback runs. Git probes retry at most 5 times and
then fail closed.

Tests build disposable trees. They never publish the live gated artifacts
and they never call GitHub Pages / Zenodo upload.

Run:  python -m pytest tests/test_publish_safety_gate.py -q
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))

import prepare_pages_artifact as ppa  # noqa: E402
import publish_safety_gate as gate  # noqa: E402

QUOTE_COLUMNS = [
    "quote_id",
    "corpus_id",
    "quote_verbatim",
    "rights_review_status",
    "rights_approver",
    "rights_approval_scope",
    "rights_approval_date",
    "rights_permitted_use",
]
LINK_COLUMNS = [
    "corpus_id",
    "name_as_source",
    "exportable",
]

APPROVAL = {
    "rights_approver": "Mārcis Gasūns (ORCID 0000-0003-4513-884X)",
    "rights_approval_scope": "all four H1899 artifacts; public repo publication",
    "rights_approval_date": "2026-08-07",
    "rights_permitted_use": "verbatim quotation and full row-level data",
}

GATED = list(gate.GATED_PATHS)


def git(cwd: Path, *args: str, check_rc: bool = True) -> str:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key)
    proc = subprocess.run(
        ("git",) + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if check_rc and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_quotes(path: Path, **fields) -> None:
    row = {
        "quote_id": "Q-TEST",
        "corpus_id": "nagari",
        "quote_verbatim": "test",
        "rights_review_status": "non_exportable",
        **APPROVAL,
        **fields,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUOTE_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def write_links(path: Path, exportable: str = "yes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LINK_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "corpus_id": "nagari",
                "name_as_source": "Anna Testova",
                "exportable": exportable,
            }
        )


def write_catalog(root: Path, rows: list[dict] | None = None) -> None:
    if rows is None:
        rows = [
            {"path": rel, "kind": kind, **APPROVAL}
            for rel, kind in (
                ("curation/community_quotes.csv", "quote_register"),
                ("curation/community_person_links.csv", "person_links"),
                ("article/comparison_snapshots", "snapshot_tree"),
                (
                    "analytics_output/community_lenses/reports/identity_quote_evidence.md",
                    "report",
                ),
            )
        ]
    payload = {"schema_version": gate.SCHEMA_VERSION, "artifacts": rows}
    write(root / gate.CATALOG_REL, json.dumps(payload, ensure_ascii=False, indent=2))


def seed_artifacts(root: Path) -> None:
    write_quotes(root / "curation" / "community_quotes.csv")
    write_links(root / "curation" / "community_person_links.csv")
    write(root / "article" / "comparison_snapshots" / "README.md", "snapshot\n")
    write(
        root
        / "analytics_output"
        / "community_lenses"
        / "reports"
        / "identity_quote_evidence.md",
        "# evidence\n",
    )


def init_repo(tmp: Path) -> Path:
    root = tmp / "repo"
    root.mkdir()
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key)
    subprocess.run(
        ("git", "init", "--initial-branch=main", str(root)),
        check=True,
        capture_output=True,
        env=env,
    )
    git(root, "config", "user.email", "gate@test")
    git(root, "config", "user.name", "Gate Test")
    write(root / "README.md", "seed\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "seed")
    return root


def run_cli(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        (sys.executable, str(SCRIPTS / "publish_safety_gate.py"), "--repo", str(root), *args),
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_gated_paths_are_the_h1899_four():
    assert set(gate.GATED_PATHS) == {
        "curation/community_person_links.csv",
        "curation/community_quotes.csv",
        "article/comparison_snapshots",
        "analytics_output/community_lenses/reports/identity_quote_evidence.md",
    }
    assert gate.GIT_TRIES == 5


def test_approved_is_go(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    write_catalog(root)
    git(root, "add", "-A")
    git(root, "commit", "-m", "approved")
    rc, out = run_cli(root)
    assert rc == 0, out
    assert out.startswith("GO:")
    verdict = gate.evaluate(root)
    assert verdict.ok
    assert set(verdict.inspected) >= set(GATED)


def test_missing_approval_is_nogo(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    git(root, "add", "-A")
    git(root, "commit", "-m", "no catalog")
    rc, out = run_cli(root)
    assert rc == 1, out
    assert "NO-GO:" in out
    assert "Remediation:" in out
    assert "not approval" in out
    codes = {item.code for item in gate.evaluate(root).findings}
    assert "missing" in codes


def test_malformed_approval_is_nogo(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    bad = {**APPROVAL, "rights_approval_date": "07-08-2026"}
    write_catalog(
        root,
        [{"path": rel, "kind": "report", **bad} for rel in GATED],
    )
    git(root, "add", "-A")
    git(root, "commit", "-m", "bad date")
    rc, out = run_cli(root)
    assert rc == 1, out
    assert "NO-GO:" in out
    assert any(item.code == "malformed" for item in gate.evaluate(root).findings)


def test_malformed_placeholder_approver_is_nogo(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    bad = {**APPROVAL, "rights_approver": "TBD"}
    write_catalog(
        root,
        [{"path": rel, "kind": "report", **bad} for rel in GATED],
    )
    git(root, "add", "-A")
    git(root, "commit", "-m", "placeholder")
    verdict = gate.evaluate(root)
    assert not verdict.ok
    assert any(item.code == "missing" for item in verdict.findings)


def test_accidentally_tracked_without_approval_is_nogo(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    git(root, "add", "-A")
    git(root, "commit", "-m", "accidentally tracked")
    verdict = gate.evaluate(root)
    assert not verdict.ok
    assert any(item.code == "tracked" for item in verdict.findings)


def test_accidentally_untracked_despite_approval_is_nogo(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    write_catalog(root)
    git(root, "add", "curation/rights_approvals.json")
    git(root, "commit", "-m", "catalog only")
    rc, out = run_cli(root)
    assert rc == 1, out
    verdict = gate.evaluate(root)
    assert not verdict.ok
    assert any(item.code == "untracked" for item in verdict.findings)


def test_gitignore_is_not_approval(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    write(root / ".gitignore", "curation/community_quotes.csv\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "ignored quotes")
    verdict = gate.evaluate(root)
    assert not verdict.ok
    assert any("not approval" in item.detail.lower() or item.code == "untracked"
               for item in verdict.findings)


def test_exportable_yes_without_approval_is_nogo(tmp_path: Path):
    root = init_repo(tmp_path)
    write_links(root / "curation" / "community_person_links.csv", exportable="yes")
    git(root, "add", "-A")
    git(root, "commit", "-m", "exportable yes, no catalog")
    verdict = gate.evaluate(root)
    assert not verdict.ok
    assert any("exportable=yes" in item.detail for item in verdict.findings)


def test_quote_row_disagrees_with_catalog(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    write_quotes(
        root / "curation" / "community_quotes.csv",
        rights_approver="Someone Else",
    )
    write_catalog(root)
    git(root, "add", "-A")
    git(root, "commit", "-m", "mismatch")
    verdict = gate.evaluate(root)
    assert not verdict.ok
    assert any("disagrees with catalog" in item.detail for item in verdict.findings)


class _FailingGit:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, repo: Path, args: tuple[str, ...]) -> gate.GitResult:
        self.calls += 1
        return gate.GitResult(128, "", "simulated git failure", 1)


def test_five_try_cap_fails_closed(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    write_catalog(root)
    failing = _FailingGit()
    verdict = gate.evaluate(root, git_fn=failing, tries=5)
    assert not verdict.ok
    assert failing.calls == 5
    assert any("after 5 tries" in item.detail for item in verdict.findings)


def test_zero_try_cap_fails_closed_without_running_git(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    write_catalog(root)
    failing = _FailingGit()
    verdict = gate.evaluate(root, git_fn=failing, tries=0)
    assert not verdict.ok
    assert failing.calls == 0


def test_unsafe_publish_exits_before_artifact_upload(tmp_path: Path, monkeypatch):
    uploaded: list[Path] = []
    dest = tmp_path / "_site"

    def _fake_evaluate(repo_root=None):
        class _V:
            ok = False
            findings = []
            inspected = []

        return _V(), lambda verdict: "NO-GO: fixture\n"

    monkeypatch.setattr(ppa, "evaluate_gate", _fake_evaluate)

    def _should_not_build(_dest):
        raise AssertionError("populate_site must not run after NO-GO")

    monkeypatch.setattr(ppa, "populate_site", _should_not_build)
    rc = ppa.publish(dest=dest, upload=uploaded.append)
    assert rc == 1
    assert uploaded == []
    assert not dest.exists()


def test_go_publish_invokes_upload_after_gate(tmp_path: Path, monkeypatch):
    uploaded: list[Path] = []
    dest = tmp_path / "_site"
    built: list[Path] = []

    def _fake_evaluate(repo_root=None):
        class _V:
            ok = True
            findings = []
            inspected = list(GATED)

        return _V(), lambda verdict: "GO: fixture\n"

    monkeypatch.setattr(ppa, "evaluate_gate", _fake_evaluate)
    monkeypatch.setattr(ppa, "populate_site", lambda d: built.append(d) or d.mkdir())
    rc = ppa.publish(dest=dest, upload=uploaded.append)
    assert rc == 0
    assert built == [dest]
    assert uploaded == [dest]


def test_live_repo_stays_go():
    """Preserve the #183 approved workflow: current main catalog must pass."""
    rc, out = run_cli(REPO_ROOT)
    assert rc == 0, out
    verdict = gate.evaluate(REPO_ROOT)
    assert verdict.ok, gate.format_report(verdict)
    assert set(gate.GATED_PATHS) <= set(verdict.inspected)


def test_cli_json_nogo_shape(tmp_path: Path):
    root = init_repo(tmp_path)
    seed_artifacts(root)
    rc, out = run_cli(root, "--json")
    assert rc == 1
    payload = json.loads(out)
    assert payload["verdict"] == "NO-GO"
    assert payload["ok"] is False
    assert payload["findings"]
