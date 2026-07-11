"""Guard: every root page we advertise must actually ship in the Pages artifact.

`prepare_pages_artifact.py` copies a hardcoded allowlist (`PUBLIC_PATHS`) into the
`_site` directory that GitHub Pages serves. `copy_path` silently skips a file that
isn't listed, so a page can exist on `main`, sit in the sitemap, be linked from the
nav — and still 404 in production with no build error. That is exactly how
`indologiya-v-rossii.html`, `sanskritologiya-v-rossii.html`, `docs.html` and
`hypotheses.html` were unreachable despite being generated and committed.

This test closes the loop: anything the static sitemap promises at the site root
must be in the artifact allowlist (or be a directory the artifact copies wholesale).
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import prepare_pages_artifact as ppa  # noqa: E402

SITEMAP_STATIC = ROOT / "sitemap_static.xml"
SITE_BASE = "gasyoun.github.io/IndologyScholars/"


def _static_sitemap_root_pages():
    """Root-level .html locs in the static sitemap (no extra path segment)."""
    if not SITEMAP_STATIC.exists():
        pytest.skip("sitemap_static.xml not built")
    text = SITEMAP_STATIC.read_text(encoding="utf-8")
    pages = set()
    for loc in re.findall(r"<loc>([^<]+)</loc>", text):
        idx = loc.find(SITE_BASE)
        if idx == -1:
            continue
        rel = loc[idx + len(SITE_BASE):]
        # Root-level pages only: no '/' in the remainder. Directory entries
        # (e.g. IndologyArchive/…) are shipped via PUBLIC_DIRS/aliased dirs.
        if rel.endswith(".html") and "/" not in rel:
            pages.add(rel)
    return pages


def test_every_advertised_root_page_ships_in_the_artifact():
    advertised = _static_sitemap_root_pages()
    allowlisted = set(ppa.PUBLIC_PATHS)
    missing = sorted(advertised - allowlisted)
    assert not missing, (
        "these root pages are in sitemap_static.xml but absent from "
        f"prepare_pages_artifact.PUBLIC_PATHS, so they would 404 on Pages: {missing}"
    )


def test_allowlisted_root_html_pages_are_generated():
    """No dangling allowlist entry: every .html in PUBLIC_PATHS exists on disk."""
    missing = [
        name
        for name in ppa.PUBLIC_PATHS
        if name.endswith(".html") and not (ROOT / name).exists()
    ]
    assert not missing, f"PUBLIC_PATHS lists non-existent pages: {missing}"


def test_the_two_section_pages_are_covered():
    """Explicit regression for the H473 sections that triggered this guard."""
    for name in ("indologiya-v-rossii.html", "sanskritologiya-v-rossii.html"):
        assert name in ppa.PUBLIC_PATHS
