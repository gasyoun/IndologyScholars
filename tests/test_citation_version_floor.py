"""The published CITATION.cff version may be raised by a release tag, never lowered.

Regression guard for the 14-08-2026 incident: the auto-rebuild triggered BY the
release commit `chore(release): 1.12.1 (#233)` started 3 s after the merge, so its
checkout carried tags only up to `v1.7.0`, and `generate_publication_pages.py`
regenerated CITATION.cff with `version: "1.7.0"` — silently un-publishing the
version the release had just cut. This is H790's regression re-entering through
the tag lookup H790 itself introduced; `fetch-depth: 0` cannot fix it because the
tag does not exist yet at checkout time.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "generate_publication_pages.py"


def _load_version_helpers():
    """Exec just the two version helpers, without importing the whole generator.

    Importing `generate_publication_pages` at module scope opens the database and
    builds the site; the helpers under test are pure and sit above that work.
    """
    src = SOURCE.read_text(encoding="utf-8")
    start = src.index("def _recorded_citation_version")
    end = src.index("RELEASE_VERSION =")
    namespace = {"subprocess": subprocess, "re": re, "sys": sys}
    exec(compile(src[start:end], str(SOURCE), "exec"), namespace)
    return namespace


@pytest.fixture()
def helpers():
    return _load_version_helpers()


def test_recorded_version_is_read_from_citation_cff(helpers, tmp_path, monkeypatch):
    (tmp_path / "CITATION.cff").write_text(
        'cff-version: 1.2.0\nversion: "1.12.1"\nlicense: "CC-BY-4.0"\n',
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)
    assert helpers["_recorded_citation_version"]() == "1.12.1"


def test_stale_tag_list_never_lowers_the_published_version(helpers, tmp_path, monkeypatch):
    """The incident itself: tags stop at v1.7.0, CITATION.cff already says 1.12.1."""
    (tmp_path / "CITATION.cff").write_text(
        'version: "1.12.1"\n', encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        helpers["subprocess"],
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="v1.7.0 v1.6.8\n", stderr=""),
    )
    assert helpers["_latest_release_version"]() == "1.12.1"


def test_a_newer_tag_still_raises_the_version(helpers, tmp_path, monkeypatch):
    """The floor must not freeze the version: a real newer tag still wins."""
    (tmp_path / "CITATION.cff").write_text(
        'version: "1.12.1"\n', encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        helpers["subprocess"],
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="v1.13.0 v1.12.1\n", stderr=""),
    )
    assert helpers["_latest_release_version"]() == "1.13.0"


def test_reserve_tags_are_still_ignored(helpers, tmp_path, monkeypatch):
    """H1899: `reserve-vX.Y.Z` claims a number before a release exists."""
    (tmp_path / "CITATION.cff").write_text(
        'version: "1.12.1"\n', encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        helpers["subprocess"],
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 0, stdout="reserve-v1.99.0 v1.12.1\n", stderr=""
        ),
    )
    assert helpers["_latest_release_version"]() == "1.12.1"


def test_versions_compare_numerically_not_lexically(helpers, tmp_path, monkeypatch):
    """`"1.7.0" > "1.12.1"` as strings — the comparison must be tuple-of-ints."""
    (tmp_path / "CITATION.cff").write_text(
        'version: "1.7.0"\n', encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        helpers["subprocess"],
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="v1.12.1\n", stderr=""),
    )
    assert helpers["_latest_release_version"]() == "1.12.1"


def test_committed_citation_matches_the_latest_release_tag():
    """The live artifact, not a fixture: main's CITATION.cff must not sit below its tag."""
    recorded = re.search(
        r'^version:\s*"?(\d+\.\d+\.\d+)"?\s*$',
        (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert recorded, "CITATION.cff has no semver version line"
    tags = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*", "--sort=-v:refname"],
        capture_output=True, text=True, cwd=REPO_ROOT, encoding="utf-8",
    ).stdout.split()
    latest = next((t[1:] for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)), None)
    if latest is None:
        pytest.skip("no release tags in this checkout")
    to_tuple = lambda v: tuple(int(p) for p in v.split("."))
    assert to_tuple(recorded.group(1)) >= to_tuple(latest), (
        f"CITATION.cff publishes {recorded.group(1)} but v{latest} is released"
    )
