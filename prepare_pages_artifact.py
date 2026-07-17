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
    "Indology": "IndologyArchive",
    # Only index.html is committed under nagari/site/; the DB, the Markdown mirror
    # and the raw dump are git-ignored, so nothing else can reach the artifact.
    "nagari/site": "nagari",
}


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
    destination = dest_root / "IndologyArchive" / "index.html"
    if not destination.parent.exists():
        return
    destination.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=dashboard/index.html">
  <title>INDOLOGY Archive Atlas</title>
</head>
<body>
  <p><a href="dashboard/index.html">Open the INDOLOGY Archive Atlas</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )


def minify_html(content):
    # Remove HTML comments (except IE conditional comments)
    content = re.sub(r'<!--(?!\[if).*?-->', '', content, flags=re.DOTALL)
    # Remove whitespace between tags where safe
    content = re.sub(r'>\s+<', '><', content)
    # Collapse multiple whitespaces
    content = re.sub(r'\s+', ' ', content)
    return content.strip()


def minify_css(content):
    # Remove comments
    content = re.sub(r'/\*(.*?)\*/', '', content, flags=re.DOTALL)
    # Remove space around delimiters
    content = re.sub(r'\s*([\{\}:;,])\s*', r'\1', content)
    # Collapse multiple whitespaces
    content = re.sub(r'\s+', ' ', content)
    return content.strip()


def minify_js(content):
    # Very simple safe JS minification
    # Remove comments
    content = re.sub(r'//.*?\n', '\n', content)
    content = re.sub(r'/\*(.*?)\*/', '', content, flags=re.DOTALL)
    # Collapse multiple spaces
    content = re.sub(r'\s+', ' ', content)
    return content.strip()


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
    write_indology_archive_landing(dest)

    minify_site(dest)

    print(f"Prepared GitHub Pages artifact at {dest.resolve()}")


if __name__ == "__main__":
    main()
