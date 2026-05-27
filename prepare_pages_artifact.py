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
    "indology_scholars_analytics.md",
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
    "cities",
    "institutions",
    "curation",
    "docs",
]


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

    minify_site(dest)

    print(f"Prepared GitHub Pages artifact at {dest.resolve()}")


if __name__ == "__main__":
    main()
