"""Refuse a push that deletes lines another session added upstream moments ago —
the silent-revert class of Uprava#1516.

WHY THE OBVIOUS DESIGN DOES NOT WORK
------------------------------------
The guard proposed on #1516 was "refuse a push whose tree contains a path modified
upstream after the local HEAD's merge-base". Implemented and measured 04-08-2026, it
is **redundant with git itself**: ``merge-base != remote_tip`` is the definition of a
non-fast-forward push, which git already rejects; and a fast-forward push always has
``merge-base == remote_tip``, so the check is vacuous exactly when it is needed. Both
#1516 incidents were clean fast-forwards. A ref-level test cannot see them.

What both incidents *do* share is visible at the line level: the push **deletes lines
that an upstream commit added very recently**, because the author's file content was a
pre-image copy — a stale index (29-07) or a stale checkout (04-08). Nobody edits a line
that landed ninety seconds ago on purpose without knowing it; when it happens it is
almost always a copy written before that line existed.

THE CHECK
---------
For each path the push changes, take the lines it removes relative to the remote tip,
``git blame`` them at the remote tip, and flag any whose introducing commit is

* **recent** — within ``--recent-days`` (default 3), and
* **not part of this push** — so rewriting your own just-pushed line is fine.

That pair is the whole rule. Old lines are ordinary edits. Your own lines are yours.
Someone else's line from an hour ago, deleted by a commit that never mentions it, is
the defect.

WARN BY DEFAULT — AND WHY IT WAS DEMOTED
----------------------------------------
This started as a **blocking** hook, which is what #1516 asked for. It was demoted to a
warning on the day it shipped, on measured evidence: while landing its own handoff it
refused three pushes, all of them legitimate, all of them this repo's standard workflow —

1. resolving a ``CHANGELOG`` version collision by renumbering a concurrent session's
   section (their rows deleted at the old line numbers, re-added lower);
2. filling a ``mint_handoff.py`` stub that had been pushed to ``main`` seconds earlier;
3. ``handoff_close.py`` archiving a handoff, which repoints ``handoffs/X`` links to
   ``handoffs/archive/X`` **inside rows added minutes ago**.

(1) and (2) are exempted below. (3) is not cleanly exemptible without special-casing the
repo's own tooling. Three false-positive classes from routine work in one session, against
two true incidents in a week, is the wrong ratio for a blocker: the standing response to a
hook that refuses good pushes is to switch it off, and then it protects nothing. So the
default is a loud warning that lets the push through, matching how the org already treats
imperfect-judgment guards (``pre_shell_guards`` guard 9 warns on ``git pull``, because
pulls are sometimes right)::

    STALE_BASE_PUSH_STRICT=1 git push ...   # restore blocking
    ALLOW_STALE_BASE_PUSH=1  git push ...   # silence entirely

A deliberate revert of fresh upstream work is flagged too — correctly. The goal is to put
the fact in front of a human at the last moment it is still free to act on, not to forbid.

LIMITS (measured, not assumed)
------------------------------
* Blame is per-path and costs ~one blame per changed file; on a push touching hundreds
  of files this is slow, so ``--max-paths`` (default 40) bounds it and the script says
  so rather than silently sampling.
* Pure additions are never flagged; only deletions and rewrites of recent upstream lines.
* Whitespace-only differences are ignored (``-w``), so a CRLF renormalisation sweep does
  not trip it — the §299/§305 class is a different problem with a different fix.
* A push that reverts a line older than the window is not caught. That is the accepted
  cost of keeping false positives near zero.

Install once per clone::

    git config core.hooksPath .githooks

BASE-STATE GATE (H2579)
-----------------------
A separate, *non-vacuous* check runs first. FINDINGS §312 still holds: comparing
merge-base to the remote tip cannot detect the silent-revert class (those
pushes are clean fast-forwards). What it *can* do is refuse a push whose local
base is **behind** or **diverged** *before objects are sent* — including a
``--force`` that would otherwise overwrite the remote — and it can see a
**remote-advanced** tip that the local tracking ref has not yet absorbed
(pre-push stdin ``remote_sha`` vs ``origin/<branch>``).

Classification (exactly four operator-facing states):

* ``clean``           — remote is an ancestor of local (fast-forward).
* ``behind``          — local is an ancestor of remote (would rewind the branch).
* ``diverged``        — neither is an ancestor of the other.
* ``remote-advanced`` — the live remote tip (``--remote-sha`` or a successful
  fetch) is not the tracking ref we started with, and the live classification
  is behind or diverged.

``behind`` and ``diverged`` (and the remote-advanced form of either) **block**
the push. ``clean`` continues to the line-level scan above. Fetch is retried
at most ``FETCH_TRIES`` (5) times; if every try fails and no live tip is
known, the check fails closed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ESCAPE_ENV = "ALLOW_STALE_BASE_PUSH"
STRICT_ENV = "STALE_BASE_PUSH_STRICT"
MAX_LISTED = 12
FETCH_TRIES = 5
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+")
BASE_BLOCK = frozenset({"behind", "diverged", "remote-advanced", "unknown"})


def git(*args: str, check: bool = False) -> str:
    proc = subprocess.run(
        ("git",) + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout


def fetch_with_cap(remote: str, tries: int = FETCH_TRIES) -> tuple[bool, int]:
    """Fetch ``remote`` at most ``tries`` times. Returns (ok, attempts_used)."""
    if tries < 1:
        return False, 0
    for attempt in range(1, tries + 1):
        proc = subprocess.run(
            ("git", "fetch", remote, "--quiet"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return True, attempt
    return False, tries


def classify_base(local_ref: str, remote_ref: str) -> str:
    """Return equal | clean | behind | diverged | unknown.

    ``clean`` means remote is an ancestor of local (a fast-forward). This is
    not the §312-vacuous 'merge-base != remote tip' silent-revert test: a
    clean-FF revert is invisible here and is handled by the line-level scan.
    """
    local = git("rev-parse", "--verify", "--quiet", local_ref).strip()
    remote = git("rev-parse", "--verify", "--quiet", remote_ref).strip()
    if not local or not remote:
        return "unknown"
    if local == remote:
        return "equal"
    mb = git("merge-base", local, remote).strip()
    if not mb:
        return "diverged"
    if mb == remote:
        return "clean"
    if mb == local:
        return "behind"
    return "diverged"


def resolve_live_tip(tracking: str, remote_sha: str | None,
                     fetched: bool) -> tuple[str, bool]:
    """Pick the live remote tip and whether tracking was stale.

    Returns ``(tip_ref, remote_advanced)``. ``remote_advanced`` is true when
    we learned a tip that is not the tracking SHA we started with.
    """
    tracking_sha = git("rev-parse", "--verify", "--quiet", tracking).strip()
    if remote_sha:
        live = remote_sha.strip()
        if git("rev-parse", "--verify", "--quiet", live).strip():
            return live, bool(tracking_sha and tracking_sha != live)
    if fetched and tracking_sha:
        return tracking, False
    if tracking_sha:
        return tracking, False
    return tracking, False


def report_base_block(state: str, local_ref: str, remote_ref: str,
                      remote_advanced: bool, fetch_ok: bool,
                      fetch_tries: int) -> None:
    e = sys.stderr
    print("", file=e)
    print("PUSH BLOCKED — local base is %s vs %s." % (state, remote_ref), file=e)
    if remote_advanced:
        print("The live remote tip has advanced past the tracking ref this clone", file=e)
        print("last recorded (remote-advanced). A push now would not be a clean", file=e)
        print("fast-forward — including under --force, which git would otherwise accept.", file=e)
    elif state == "behind":
        print("HEAD is an ancestor of the remote tip. Pushing it would rewind the", file=e)
        print("branch (or, with --force, delete commits another session already landed).", file=e)
    elif state == "diverged":
        print("Local and remote each have commits the other does not. A force-push", file=e)
        print("would overwrite the remote side; a normal push would be rejected later.", file=e)
        print("Refusing here so nothing is sent.", file=e)
    else:
        print("The remote tip could not be classified after %d fetch attempt(s)."
              % fetch_tries, file=e)
        if not fetch_ok:
            print("Fetch failed every try (cap is %d). Fail closed."
                  % FETCH_TRIES, file=e)
    print("", file=e)
    print("Recover:", file=e)
    print("    git fetch origin && git rebase %s" % remote_ref, file=e)
    print("or rebuild on a fresh worktree off the live tip. Do not force-push.", file=e)
    print("", file=e)
    print("Deliberate override (rare):  %s=1 git push ..." % ESCAPE_ENV, file=e)
    print("", file=e)


def pushed_commits(remote_ref: str, local_ref: str) -> set[str]:
    out = git("rev-list", "%s..%s" % (remote_ref, local_ref))
    return {line.strip() for line in out.splitlines() if line.strip()}


def changed_paths(remote_ref: str, local_ref: str) -> list[str]:
    out = git("diff", "--name-only", "-w", remote_ref, local_ref)
    return [p for p in out.splitlines() if p.strip()]


def removed_line_numbers(remote_ref: str, local_ref: str, path: str) -> list[int]:
    """Line numbers AT THE REMOTE TIP that this push removes or rewrites."""
    out = git("diff", "-w", "-U0", remote_ref, local_ref, "--", path)
    numbers: list[int] = []
    old_line = 0
    for line in out.splitlines():
        m = HUNK_RE.match(line)
        if m:
            old_line = int(m.group(1))
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            numbers.append(old_line)
            old_line += 1
    return numbers


STUB_MARKER = "STUB claimed by mint_handoff.py"


def surviving_text(local_ref: str, path: str) -> set[str]:
    """Every non-blank stripped line of the path as this push would leave it.

    Used to separate a MOVE from a LOSS. Renumbering a changelog section, resolving a
    merge by relocating someone's rows, reordering a table — all delete lines at their
    old position and re-add them elsewhere. The remote keeps the content, so there is
    nothing to protect. Only a line whose text survives NOWHERE in the pushed file is a
    real deletion. (Found by dogfooding: the guard blocked its own landing commit for
    exactly this, which is the false-positive class that gets a blocking hook disabled.)
    """
    out = git("show", "%s:%s" % (local_ref, path))
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def is_mint_stub(remote_ref: str, path: str) -> bool:
    """A freshly minted handoff skeleton being filled in the same pass.

    `mint_handoff.py` lands a placeholder body on origin/main, then the session that
    minted it replaces those placeholders with real content — a legitimate rewrite of
    lines that are, by construction, minutes old and authored outside the push.
    """
    if "/handoffs/" not in "/" + path.replace("\\", "/"):
        return False
    return STUB_MARKER in git("show", "%s:%s" % (remote_ref, path))


def blame_recent(remote_ref: str, path: str, lines: list[int],
                 cutoff: datetime, ours: set[str],
                 survivors: set[str]) -> list[tuple[int, str, str]]:
    """(line, short_sha, author) for removed lines added recently by someone else."""
    hits: list[tuple[int, str, str]] = []
    old_text = git("show", "%s:%s" % (remote_ref, path)).splitlines()
    for ln in lines:
        # Moved, not lost: the same text is still somewhere in the pushed file.
        if 1 <= ln <= len(old_text) and old_text[ln - 1].strip() in survivors:
            continue
        out = git("blame", "-w", "--line-porcelain", "-L", "%d,%d" % (ln, ln),
                  remote_ref, "--", path)
        if not out.strip():
            continue
        head = out.splitlines()[0].split()
        if not head:
            continue
        sha = head[0]
        if sha in ours:
            continue
        author = ""
        when: datetime | None = None
        for row in out.splitlines():
            if row.startswith("author "):
                author = row[len("author "):].strip()
            elif row.startswith("author-time "):
                try:
                    when = datetime.fromtimestamp(int(row.split()[1]), tz=timezone.utc)
                except (ValueError, IndexError):
                    when = None
        if when is not None and when >= cutoff:
            hits.append((ln, sha[:9], author))
    return hits


def scan(local_ref: str, remote_ref: str, recent_days: float,
         max_paths: int) -> tuple[dict[str, list], bool]:
    ours = pushed_commits(remote_ref, local_ref)
    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    paths = changed_paths(remote_ref, local_ref)
    truncated = len(paths) > max_paths

    found: dict[str, list] = {}
    for path in paths[:max_paths]:
        removed = removed_line_numbers(remote_ref, local_ref, path)
        if not removed:
            continue
        if is_mint_stub(remote_ref, path):
            continue
        hits = blame_recent(remote_ref, path, removed, cutoff, ours,
                            surviving_text(local_ref, path))
        if hits:
            found[path] = hits
    return found, truncated


def report(found: dict[str, list], remote_ref: str, recent_days: float,
           truncated: bool, max_paths: int) -> None:
    total = sum(len(v) for v in found.values())
    e = sys.stderr
    # Banner must match what main() returns. Default is WARN (exit 0); BLOCK
    # only under STALE_BASE_PUSH_STRICT=1. Printing "PUSH BLOCKED" on the
    # default path announced a refusal that never happened (H2656).
    strict = bool(os.environ.get(STRICT_ENV))
    print("", file=e)
    if strict:
        print("PUSH BLOCKED (%s=1) — this push deletes %d line(s) that landed on %s"
              % (STRICT_ENV, total, remote_ref), file=e)
        print("within the last %g day(s), in %d file(s), and your commits never "
              "reference them." % (recent_days, len(found)), file=e)
    else:
        print("PUSH WARNING — the push is PROCEEDING; nothing has been refused."
              , file=e)
        print("It deletes %d line(s) that landed on %s within the last %g day(s), in "
              "%d file(s)," % (total, remote_ref, recent_days, len(found)), file=e)
        print("and your commits never reference them.", file=e)
    print("", file=e)
    shown = 0
    for path, hits in found.items():
        print("  %s" % path, file=e)
        for ln, sha, author in hits:
            if shown >= MAX_LISTED:
                break
            print("      line %-6d added by %s (%s)" % (ln, sha, author), file=e)
            shown += 1
        if shown >= MAX_LISTED:
            print("      …", file=e)
            break
    print("", file=e)
    print("That is Uprava#1516. Twice now a clean fast-forward with green hooks has", file=e)
    print("installed a pre-image copy over another session's work: 6 files on 29-07", file=e)
    print("(stale index after `git reset --soft`), 19 link fixes on 04-08 (stale", file=e)
    print("checkout — the branch ref moved, the working tree did not).", file=e)
    print("", file=e)
    print("If you did NOT mean to touch those lines, your file content is stale:", file=e)
    print("    git fetch origin && git rebase %s" % remote_ref, file=e)
    print("and if `git status` lists files you never edited, do NOT `git add -A` and", file=e)
    print("do NOT lift a patch out of that tree (a patch encodes its base, FINDINGS", file=e)
    print("§308) — rebuild on a fresh worktree off %s and re-apply your edits." % remote_ref, file=e)
    print("", file=e)
    print("If the revert IS deliberate:  %s=1 git push ..." % ESCAPE_ENV, file=e)
    if truncated:
        print("", file=e)
        print("NOTE: only the first %d changed paths were scanned (--max-paths)." % max_paths, file=e)
    print("", file=e)


def emit_json(payload: dict) -> None:
    print(json.dumps(payload))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("local_ref")
    ap.add_argument("remote_ref")
    ap.add_argument("--recent-days", type=float, default=3.0)
    ap.add_argument("--max-paths", type=int, default=40)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--remote-sha", default="",
                    help="live remote tip from pre-push stdin (preferred over tracking)")
    ap.add_argument("--fetch-tries", type=int, default=FETCH_TRIES)
    args = ap.parse_args(argv)

    if os.environ.get(ESCAPE_ENV):
        if args.json:
            emit_json({"result": "skip", "reason": ESCAPE_ENV})
        return 0

    remote_name = args.remote_ref.split("/", 1)[0] or "origin"
    tracking_before = git("rev-parse", "--verify", "--quiet", args.remote_ref).strip()
    fetch_ok = True
    fetch_tries = 0
    if not args.no_fetch:
        fetch_ok, fetch_tries = fetch_with_cap(remote_name, args.fetch_tries)

    live_tip, tracking_stale = resolve_live_tip(
        args.remote_ref, args.remote_sha or None, fetch_ok)
    # Fetch updates the tracking ref, so "was the clone stale?" is the
    # pre-fetch SHA compared to the live tip — not tracking-after-fetch.
    live_sha = git("rev-parse", "--verify", "--quiet", live_tip).strip()
    if tracking_before and live_sha and tracking_before != live_sha:
        tracking_stale = True

    live_exists = bool(git("rev-parse", "--verify", "--quiet", live_tip).strip())
    if not live_exists:
        state = "unknown"
        payload = {
            "result": "block",
            "base_state": state,
            "remote_advanced": tracking_stale,
            "fetch_ok": fetch_ok,
            "fetch_tries": fetch_tries,
            "reason": "remote tip not in object store",
        }
        if args.json:
            emit_json(payload)
        else:
            report_base_block(state, args.local_ref, live_tip,
                              tracking_stale, fetch_ok, fetch_tries)
        return 1

    raw_state = classify_base(args.local_ref, live_tip)
    remote_advanced = tracking_stale and raw_state in {"behind", "diverged"}
    state = "remote-advanced" if remote_advanced else raw_state

    if state in BASE_BLOCK:
        payload = {
            "result": "block",
            "base_state": state,
            "raw_state": raw_state,
            "remote_advanced": remote_advanced,
            "fetch_ok": fetch_ok,
            "fetch_tries": fetch_tries,
            "paths": [],
            "lines": 0,
            "truncated": False,
        }
        if args.json:
            emit_json(payload)
        else:
            report_base_block(state, args.local_ref, live_tip,
                              remote_advanced, fetch_ok, fetch_tries)
        return 1

    found, truncated = scan(args.local_ref, live_tip, args.recent_days, args.max_paths)
    strict = bool(os.environ.get(STRICT_ENV))
    if found:
        result = "block" if strict else "warn"
        rc = 1 if strict else 0
    else:
        result = "ok"
        rc = 0

    if args.json:
        emit_json({
            "result": result,
            "base_state": state,
            "raw_state": raw_state,
            "remote_advanced": remote_advanced,
            "fetch_ok": fetch_ok,
            "fetch_tries": fetch_tries,
            "paths": sorted(found),
            "lines": sum(len(v) for v in found.values()),
            "truncated": truncated,
        })
        return rc

    if found:
        report(found, live_tip, args.recent_days, truncated, args.max_paths)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
