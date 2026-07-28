import shutil
import re
from pathlib import Path


PUBLIC_PATHS = [
    "index.html",
    "404.html",
    "en.html",
    "site_data.json",
    "search-index.json",
    "search.html",
    "download-data.html",
    "data-quality.html",
    "sitemap.xml",
    "sitemap_static.xml",
    "sitemap_scholars.xml",
    "sitemap_publications.xml",
    "sitemap_taxonomy.xml",
    "robots.txt",
    "site.webmanifest",
    "offline.html",
    "service-worker.js",
    "CITATION.cff",
    "datapackage.json",
    "data_dictionary.md",
    "conferences.db",
    "LICENSE",
    "README.md",
    "README_EN.md",
    "README_RU.md",
    "methodology.html",
    "data-sources.html",
    "known-limitations.html",
    "how-to-cite.html",
    "metrics-guide.html",
    "classification-criteria.html",
    "networks.html",
    "sociology.html",
    "sociology-en.html",
    "gatekeeping.html",
    "gatekeeping-en.html",
    "known-relationships.html",
    "indologists.html",
    "indologiya-v-rossii.html",
    "sanskritologiya-v-rossii.html",
    "docs.html",
    "hypotheses.html",
    "voting.html",
    "indology_scholars_analytics.md",
    "missing_birth_years.md",
    "missing_birth_years.html",
]

PUBLIC_DIRS = [
    "assets",
    "analytics_output",
    "s",
    "conferences",
    "p",
    "themes",
    "topics",
    "generations",
    "meso",
    "gumilyov",
    "videos",
    "findings",
    "keywords",
    "cities",
    "institutions",
    "curation",
    "docs",
]

PUBLIC_ALIASED_DIRS = {
    # Only index.html is committed under nagari/site/; the DB, the Markdown mirror
    # and the raw dump are git-ignored, so nothing else can reach the artifact.
    "nagari/site": "nagari",
}

INDOLOGY_ARCHIVE_PAGES_URL = "https://gasyoun.github.io/IndologyArchiveAtlas/dashboard/index.html"


def copy_path(src, dest_root):
    source = Path(src)
    if not source.exists():
        return
    destination = dest_root / source
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_dir(src, dest_root):
    source = Path(src)
    if not source.exists():
        return
    destination = dest_root / source
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def copy_dir_as(src, dest_root, public_name):
    source = Path(src)
    if not source.exists():
        return
    destination = dest_root / public_name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def write_indology_archive_landing(dest_root):
    # Indology/ split out into its own repo + Pages site (H460). This redirect
    # keeps any existing inbound links/bookmarks to the old
    # /IndologyArchive/ path working instead of 404ing.
    destination = dest_root / "IndologyArchive" / "index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={INDOLOGY_ARCHIVE_PAGES_URL}">
  <title>INDOLOGY Archive Atlas (moved)</title>
</head>
<body>
  <p>The INDOLOGY Archive Atlas moved to its own repo.
  <a href="{INDOLOGY_ARCHIVE_PAGES_URL}">Open the INDOLOGY Archive Atlas</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )


def minify_html(content):
    # Protect the bodies of inline <script> and <style> from whitespace
    # collapsing. Collapsing newlines inside an inline script turns any single
    # "// ..." line comment into one that swallows the rest of the now one-line
    # script, silently killing every page with inline JS (the nagari
    # retrospective's charts were blanked this way). CSS is whitespace-tolerant,
    # but its bodies are preserved for the same structural reason.
    protected: list[str] = []

    def _stash(match: "re.Match[str]") -> str:
        protected.append(match.group(0))
        return f"\x00PROTECTED{len(protected) - 1}\x00"

    content = re.sub(
        r'<(script|style)\b[^>]*>.*?</\1\s*>',
        _stash,
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove HTML comments (except IE conditional comments)
    content = re.sub(r'<!--(?!\[if).*?-->', '', content, flags=re.DOTALL)
    # Remove whitespace between tags where safe
    content = re.sub(r'>\s+<', '><', content)
    # Collapse multiple whitespaces
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    # Restore the protected <script>/<style> bodies verbatim.
    content = re.sub(
        r'\x00PROTECTED(\d+)\x00',
        lambda m: protected[int(m.group(1))],
        content,
    )
    return content


def minify_css(content):
    # Remove comments
    content = re.sub(r'/\*(.*?)\*/', '', content, flags=re.DOTALL)
    # Remove space around delimiters
    content = re.sub(r'\s*([\{\}:;,])\s*', r'\1', content)
    # Collapse multiple whitespaces
    content = re.sub(r'\s+', ' ', content)
    return content.strip()


def minify_js(content):
    # Correctness over cleverness. The previous "very simple" version was neither
    # simple nor safe: `//.*?\n` -> '\n' ate every `//` that lived *inside* a
    # string literal — the https:// URLs in assets/js/main.js (ORCID, Wikidata
    # links) and the map basemap tile template in charts.js were all corrupted —
    # and then `\s+` -> ' ' flattened newlines so any surviving `//` comment
    # would swallow the rest of the file (the same failure that blanked the
    # nagari charts through minify_html). A regex cannot tell code from strings,
    # regex literals or template literals, so we do NOT touch any line's inline
    # content. We only drop lines that are unambiguously whole-line `//` comments
    # or blank — that keeps newlines (no comment can swallow code) and cannot
    # corrupt a URL, string, or regex. Modest savings, zero risk.
    kept = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        kept.append(line)
    return "\n".join(kept)


def minify_site(dest_root):
    print("Running production minification pass...")
    html_count = 0
    css_count = 0
    js_count = 0
    for p in Path(dest_root).rglob("*"):
        if p.is_file():
            if p.suffix == ".html":
                try:
                    text = p.read_text(encoding="utf-8")
                    p.write_text(minify_html(text), encoding="utf-8")
                    html_count += 1
                except Exception as e:
                    print(f"Error minifying HTML {p}: {e}")
            elif p.suffix == ".css":
                try:
                    text = p.read_text(encoding="utf-8")
                    p.write_text(minify_css(text), encoding="utf-8")
                    css_count += 1
                except Exception as e:
                    print(f"Error minifying CSS {p}: {e}")
            elif p.suffix == ".js":
                try:
                    text = p.read_text(encoding="utf-8")
                    p.write_text(minify_js(text), encoding="utf-8")
                    js_count += 1
                except Exception as e:
                    print(f"Error minifying JS {p}: {e}")
    print(f"Minified {html_count} HTML, {css_count} CSS, and {js_count} JS files.")


def prune_og_images(dest_root):
    # assets/og/ holds ~1700 per-scholar/per-presentation OG PNGs. Shipping
    # them in the Pages artifact pushed the deployment past its timeout
    # (H1741) — GitHub Pages degrades badly with that many small files. The
    # images stay committed to git and are served as OG meta-tag images via
    # raw.githubusercontent.com instead (see publication_helpers.RAW_CONTENT_URL).
    og_dir = Path(dest_root) / "assets" / "og"
    if og_dir.exists():
        shutil.rmtree(og_dir)


def main():
    dest = Path("_site")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()

    for path in PUBLIC_PATHS:
        copy_path(path, dest)
    for path in PUBLIC_DIRS:
        copy_dir(path, dest)
    for source, public_name in PUBLIC_ALIASED_DIRS.items():
        copy_dir_as(source, dest, public_name)
    prune_og_images(dest)
    write_indology_archive_landing(dest)

    minify_site(dest)

    print(f"Prepared GitHub Pages artifact at {dest.resolve()}")


if __name__ == "__main__":
    main()
