"""One-command runner for external Phase-5 roster enrichment.

Run this on a host where Wikidata REST and ru.wikipedia article HTML are
reachable. The runner automates only the safe, non-curatorial part of Phase 5:

1. preflight network checks;
2. Wikidata life-year enrichment;
3. ru.wikipedia infobox enrichment;
4. roster artifact rebuild;
5. registry health checks;
6. publication validation and pytest;
7. optional source-only commit and push.

It deliberately does not run the institutional scraper or OpenAlex injection:
both produce candidate evidence that needs human review before it should affect
the curated registry.

Usage:
  python tools/run_external_phase5_enrichment.py
  python tools/run_external_phase5_enrichment.py --commit
  python tools/run_external_phase5_enrichment.py --commit --push
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REACHABILITY_URLS = {
    "wikidata": "https://www.wikidata.org/wiki/Special:EntityData/Q4103377.json",
    "ruwiki": (
        "https://ru.wikipedia.org/wiki/"
        "%D0%92%D0%B0%D0%BD%D0%B8%D0%BD%D0%B0,_"
        "%D0%95%D0%B2%D0%B3%D0%B5%D0%BD%D0%B8%D1%8F_"
        "%D0%AE%D1%80%D1%8C%D0%B5%D0%B2%D0%BD%D0%B0"
    ),
}

SOURCE_OUTPUTS = [
    "scratch/wikipedia_indologists_expanded.json",
    "scratch/non_participants.md",
    "curation/non_participant_indologists.csv",
    "analytics_output/roster_participant_links.csv",
    "authority_ids.json",
]

def run(args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run a subprocess from the repository root and fail loudly."""
    printable = " ".join(args)
    print(f"\n$ {printable}", flush=True)
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=True,
    )


def capture(args: list[str]) -> str:
    return subprocess.check_output(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def py(script: str, *args: str, timeout: int | None = None) -> None:
    run([sys.executable, script, *args], timeout=timeout)


def git(*args: str, timeout: int | None = None) -> None:
    run(["git", *args], timeout=timeout)


def git_output(*args: str) -> str:
    return capture(["git", *args])


def setup_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def ensure_repo_root() -> None:
    if not (ROOT / ".git").exists():
        raise SystemExit(f"Not a git repository root: {ROOT}")
    if not (ROOT / "scratch" / "wikipedia_indologists_expanded.json").exists():
        raise SystemExit("Missing scratch/wikipedia_indologists_expanded.json")


def tracked_dirty_lines() -> list[str]:
    lines = git_output("status", "--porcelain").splitlines()
    return [line for line in lines if not line.startswith("?? ")]


def ensure_clean_tracked_worktree() -> None:
    dirty = tracked_dirty_lines()
    if dirty:
        print("Refusing to start with pre-existing tracked changes:")
        for line in dirty:
            print(f"  {line}")
        raise SystemExit(2)


def check_reachability(timeout: int) -> None:
    print("\n== Reachability checks ==")
    opener = urllib.request.build_opener()
    opener.addheaders = [
        (
            "User-Agent",
            "IndologyScholars/1.0 "
            "(https://github.com/gasyoun/IndologyScholars; external-runner)",
        )
    ]
    failed = []
    for label, url in REACHABILITY_URLS.items():
        try:
            with opener.open(url, timeout=timeout) as resp:
                body = resp.read(2048)
                status = getattr(resp, "status", None) or resp.getcode()
            print(f"  {label}: HTTP {status}, sample_bytes={len(body)}")
            if status != 200 or not body:
                failed.append(label)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  {label}: ERROR {exc}")
            failed.append(label)
    if failed:
        raise SystemExit(
            "Network preflight failed for "
            + ", ".join(failed)
            + ". Run this on another host."
        )


def roster_count() -> int:
    path = ROOT / "scratch" / "wikipedia_indologists_expanded.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    people = data.get("people", [])
    if not isinstance(people, list):
        raise SystemExit("Roster JSON has no list-valued 'people' field.")
    return len(people)


def registry_health() -> dict[str, int]:
    path = ROOT / "curation" / "non_participant_indologists.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    verified = [r for r in rows if r.get("status") == "verified"]
    bad_verified = [r for r in verified if not (r.get("source_url") or "").strip()]
    names = [(r.get("full_name_ru") or "").strip() for r in rows]
    duplicate_names = len(names) - len(set(names))

    health = {
        "total": len(rows),
        "verified": len(verified),
        "verified_without_source_url": len(bad_verified),
        "duplicate_names": duplicate_names,
    }
    print("\n== Registry health ==")
    for key, value in health.items():
        print(f"  {key}: {value}")

    if bad_verified:
        raise SystemExit("Registry has verified rows without source_url.")
    if duplicate_names:
        raise SystemExit("Registry has duplicate full_name_ru values.")
    return health


def changed_source_outputs() -> list[str]:
    out = git_output("status", "--porcelain", "--", *SOURCE_OUTPUTS)
    changed = []
    for line in out.splitlines():
        if not line.strip():
            continue
        changed.append(line[3:])
    return changed


def print_status_summary() -> None:
    print("\n== Git status ==")
    status = git_output("status", "-sb")
    print(status.rstrip())


def maybe_commit_and_push(*, commit: bool, push: bool, message: str) -> None:
    changed = changed_source_outputs()
    if not changed:
        print("\nNo source/curation outputs changed; nothing to commit.")
        if push:
            print("Skipping push because no commit was created.")
        return

    print("\nChanged source/curation outputs:")
    for path in changed:
        print(f"  {path}")

    if not commit:
        print("\nRun again with --commit to stage and commit these explicit paths.")
        return

    git("add", "--", *SOURCE_OUTPUTS)
    git("commit", "-m", message)

    if push:
        git("pull", "--rebase", "origin", "main", timeout=120)
        git("push", "origin", "main", timeout=120)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit changed source/curation outputs after successful checks.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push to origin/main after creating the commit. Implies --commit.",
    )
    parser.add_argument(
        "--message",
        default="data: phase-5 external roster enrichment",
        help="Commit message used with --commit.",
    )
    parser.add_argument(
        "--network-timeout",
        type=int,
        default=20,
        help="Seconds for each reachability probe.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip validate_publication.py and pytest. Use only for debugging.",
    )
    return parser.parse_args()


def main() -> None:
    setup_utf8()
    args = parse_args()
    if args.push:
        args.commit = True

    ensure_repo_root()
    ensure_clean_tracked_worktree()
    check_reachability(args.network_timeout)

    before_count = roster_count()
    print(f"\nRoster people before enrichment: {before_count}")

    py("scratch/wikidata_enrich.py", "--dry-run", timeout=120)
    py("scratch/wikidata_enrich.py", timeout=300)
    py("scratch/expand_wikipedia_indologists.py", timeout=900)

    after_count = roster_count()
    print(f"\nRoster people after enrichment: {after_count}")
    if after_count < before_count:
        raise SystemExit("Roster shrank; refusing to continue.")

    py("scratch/crossref_nonparticipants.py", timeout=180)
    py("tools/build_non_participant_registry.py", "--dry-run", timeout=180)
    py("tools/build_non_participant_registry.py", timeout=180)
    py("tools/link_roster_participants.py", "--dry-run", timeout=180)
    py("tools/link_roster_participants.py", timeout=180)

    registry_health()

    if not args.skip_tests:
        py("validate_publication.py", timeout=180)
        py("-m", "pytest", "-q", timeout=300)

    maybe_commit_and_push(commit=args.commit, push=args.push, message=args.message)
    print_status_summary()
    print("\nExternal Phase-5 enrichment runner finished.")


if __name__ == "__main__":
    main()
