"""H2579 — four base-state cases + CRLF gate + pre-network block.

The ref-level check (behind / diverged / clean / remote-advanced) is NOT the
vacuous merge-base test FINDINGS §312 discarded. A clean-FF silent revert is
invisible here and stays on the line-level scan. These cases pin the states
the operator runbook names, and they drive a real ``git push`` so a refusal
is proven before the remote tip moves.

Run:  python -m pytest tests/test_pre_push_stale_base.py -q
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "pre_push_stale_base_check.py"
HOOK = REPO_ROOT / ".githooks" / "pre-push"
EOL_CENSUS = REPO_ROOT / "scripts" / "eol_census.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import pre_push_stale_base_check as check  # noqa: E402


def git(cwd: Path, *args: str, env: dict | None = None, check_rc: bool = True) -> str:
    full = dict(os.environ)
    if env:
        full.update(env)
    proc = subprocess.run(
        ("git",) + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full,
    )
    if check_rc and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def run_checker(cwd: Path, *args: str, env: dict | None = None) -> tuple[int, dict, str]:
    full = dict(os.environ)
    if env:
        full.update(env)
    proc = subprocess.run(
        (sys.executable, str(CHECKER), *args, "--json"),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full,
    )
    payload: dict = {}
    if proc.stdout.strip():
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return proc.returncode, payload, proc.stdout + proc.stderr


def push(cwd: Path, env: dict | None = None, force: bool = False) -> tuple[int, str]:
    full = dict(os.environ)
    if env:
        full.update(env)
    cmd = ["git", "push"]
    if force:
        cmd.append("--force")
    cmd.extend(["origin", "HEAD:main"])
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full,
    )
    return proc.returncode, proc.stdout + proc.stderr


def world(tmp: Path) -> tuple[Path, Path, Path]:
    """Bare remote + 'them' (lands upstream) + 'us' (real hook wired)."""
    bare = tmp / "remote.git"
    git(tmp, "init", "--bare", "--initial-branch=main", str(bare))

    them = tmp / "them"
    git(tmp, "clone", str(bare), str(them))
    git(them, "config", "user.email", "them@test")
    git(them, "config", "user.name", "Them")
    write(them / ".gitattributes", "* text=auto eol=lf\n*.md text eol=lf\n")
    write(them / "audit.md", "# Audit\n\nseed line\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "seed")
    git(them, "push", "origin", "main")

    us = tmp / "us"
    git(tmp, "clone", str(bare), str(us))
    git(us, "config", "user.email", "us@test")
    git(us, "config", "user.name", "Us")
    (us / ".githooks").mkdir(exist_ok=True)
    (us / "scripts").mkdir(exist_ok=True)
    (us / ".githooks" / "pre-push").write_text(
        HOOK.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    (us / "scripts" / "pre_push_stale_base_check.py").write_text(
        CHECKER.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    (us / "scripts" / "eol_census.py").write_text(
        EOL_CENSUS.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    hook_path = us / ".githooks" / "pre-push"
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
    git(us, "config", "core.hooksPath", ".githooks")
    return bare, them, us


def remote_tip(bare: Path) -> str:
    return git(bare, "rev-parse", "refs/heads/main")


def test_fetch_with_cap_stops_at_five(monkeypatch):
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="network down")

    monkeypatch.setattr(check.subprocess, "run", fake_run)
    ok, tries = check.fetch_with_cap("origin", tries=check.FETCH_TRIES)
    assert ok is False
    assert tries == 5
    assert calls["n"] == 5


def test_fetch_with_cap_returns_on_first_success(monkeypatch):
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(check.subprocess, "run", fake_run)
    ok, tries = check.fetch_with_cap("origin", tries=5)
    assert ok is True
    assert tries == 1
    assert calls["n"] == 1


def test_classify_clean_behind_diverged(tmp_path, monkeypatch):
    bare, them, us = world(tmp_path)
    monkeypatch.chdir(us)

    # them lands a new commit; us fetches but does not merge → behind
    write(them / "audit.md", "# Audit\n\nseed line\nthem extra\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "them ahead")
    git(them, "push", "origin", "main")
    git(us, "fetch", "origin")
    assert check.classify_base("HEAD", "origin/main") == "behind"

    # us adds its own commit without rebasing → diverged
    write(us / "audit.md", "# Audit\n\nseed line\nus extra\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "us unique")
    assert check.classify_base("HEAD", "origin/main") == "diverged"

    # rebuild as a fast-forward of origin/main → clean
    git(us, "reset", "--hard", "origin/main")
    write(us / "audit.md", "# Audit\n\nseed line\nthem extra\nus on tip\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "us on current tip")
    assert check.classify_base("HEAD", "origin/main") == "clean"


def test_case_behind_blocks_before_remote_moves(tmp_path):
    bare, them, us = world(tmp_path)
    before = remote_tip(bare)
    write(them / "audit.md", "# Audit\n\nseed line\nthem extra\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "them ahead")
    git(them, "push", "origin", "main")
    git(us, "fetch", "origin")
    # Stay on the old commit so HEAD is behind origin/main.
    git(us, "reset", "--hard", before)

    rc, payload, _ = run_checker(us, "HEAD", "origin/main", "--no-fetch")
    assert rc == 1
    assert payload["base_state"] == "behind"
    assert payload["result"] == "block"

    # --force is the non-vacuous case: git would rewind the remote; the hook must not.
    rc_push, out = push(us, force=True)
    assert rc_push != 0
    assert "PUSH BLOCKED" in out
    assert "behind" in out
    assert remote_tip(bare) != before
    # The *blocked* push must not have moved the remote off them's commit.
    assert remote_tip(bare) == git(them, "rev-parse", "HEAD")


def test_case_diverged_blocks_before_remote_moves(tmp_path):
    bare, them, us = world(tmp_path)
    write(them / "audit.md", "# Audit\n\nseed line\nthem extra\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "them unique")
    git(them, "push", "origin", "main")
    them_tip = git(them, "rev-parse", "HEAD")

    write(us / "audit.md", "# Audit\n\nseed line\nus extra\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "us unique")
    git(us, "fetch", "origin")

    rc, payload, _ = run_checker(us, "HEAD", "origin/main", "--no-fetch")
    assert rc == 1
    assert payload["base_state"] == "diverged"
    assert payload["result"] == "block"

    rc_push, out = push(us, force=True)
    assert rc_push != 0
    assert "PUSH BLOCKED" in out
    assert "diverged" in out
    assert remote_tip(bare) == them_tip


def test_case_clean_is_allowed(tmp_path):
    bare, them, us = world(tmp_path)
    write(us / "audit.md", "# Audit\n\nseed line\nus extra\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "us ahead")

    rc, payload, _ = run_checker(us, "HEAD", "origin/main", "--no-fetch")
    assert rc == 0
    assert payload["base_state"] == "clean"
    assert payload["result"] == "ok"

    rc_push, out = push(us)
    assert rc_push == 0, out
    assert remote_tip(bare) == git(us, "rev-parse", "HEAD")


def test_case_remote_advanced_blocks(tmp_path):
    bare, them, us = world(tmp_path)
    write(us / "audit.md", "# Audit\n\nseed line\nus extra\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "us unique")

    write(them / "audit.md", "# Audit\n\nseed line\nthem extra\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "them unique")
    git(them, "push", "origin", "main")
    them_tip = git(them, "rev-parse", "HEAD")
    seed_tracking = git(us, "rev-parse", "origin/main")
    # us has NOT fetched. Tracking is the seed; live tip is them.
    rc, payload, err = run_checker(us, "HEAD", "origin/main")
    assert rc == 1
    assert payload["base_state"] == "remote-advanced"
    assert payload["remote_advanced"] is True
    assert payload["raw_state"] == "diverged"
    assert payload["result"] == "block"

    # Restore stale tracking so the hook sees the same remote-advanced shape.
    # (the checker fetch above updated origin/main.)
    git(us, "update-ref", "refs/remotes/origin/main", seed_tracking)
    rc_push, out = push(us, force=True)
    assert rc_push != 0
    assert "PUSH BLOCKED" in out
    assert "remote-advanced" in out
    assert remote_tip(bare) == them_tip


def test_crlf_blob_still_blocks_on_clean_push(tmp_path):
    bare, them, us = world(tmp_path)
    body = b"# dirty\r\ncrlf landed via hash-object\r\n"
    proc = subprocess.run(
        ("git", "hash-object", "-w", "--stdin"),
        cwd=str(us),
        input=body,
        capture_output=True,
    )
    blob = proc.stdout.decode().strip()
    git(us, "update-index", "--add", "--cacheinfo", f"100644,{blob},dirty.md")
    git(us, "commit", "-m", "plant CRLF blob")

    rc_push, out = push(us)
    assert rc_push != 0
    assert "VIOLATION" in out or "CR" in out or "CRLF" in out or "BLOCKED" in out
    # Remote must still be the seed, not the CRLF commit.
    assert remote_tip(bare) != git(us, "rev-parse", "HEAD")


def test_silent_revert_warns_by_default_blocks_when_strict(tmp_path):
    bare, them, us = world(tmp_path)
    write(them / "audit.md", "# Audit\n\nseed line\nlink: handoffs/archive/H1.md\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "repoint")
    git(them, "push", "origin", "main")
    git(us, "fetch", "origin")
    git(us, "reset", "--hard", "origin/main")
    # Pre-image copy: drop the fresh upstream line, add our own section.
    write(us / "audit.md", "# Audit\n\nseed line\n\nmy section\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "stale copy")

    rc, payload, _ = run_checker(us, "HEAD", "origin/main", "--no-fetch")
    assert rc == 0
    assert payload["base_state"] == "clean"
    assert payload["result"] == "warn"
    assert "audit.md" in payload["paths"]

    rc_strict, payload_s, _ = run_checker(
        us, "HEAD", "origin/main", "--no-fetch",
        env={"STALE_BASE_PUSH_STRICT": "1"},
    )
    assert rc_strict == 1
    assert payload_s["result"] == "block"


def test_escape_hatch_skips_base_block(tmp_path):
    bare, them, us = world(tmp_path)
    write(them / "audit.md", "# Audit\n\nseed line\nthem extra\n")
    git(them, "add", "-A")
    git(them, "commit", "-m", "them unique")
    git(them, "push", "origin", "main")
    write(us / "audit.md", "# Audit\n\nseed line\nus extra\n")
    git(us, "add", "-A")
    git(us, "commit", "-m", "us unique")
    git(us, "fetch", "origin")

    rc, payload, _ = run_checker(
        us, "HEAD", "origin/main", "--no-fetch",
        env={"ALLOW_STALE_BASE_PUSH": "1"},
    )
    assert rc == 0
    assert payload["result"] == "skip"
