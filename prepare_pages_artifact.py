import shutil
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
    "robots.txt",
    "site.webmanifest",
    "CITATION.cff",
    "datapackage.json",
    "data_dictionary.md",
    "conferences.db",
    "LICENSE",
    "README.md",
    "README_RU.md",
    "methodology.html",
    "data-sources.html",
    "known-limitations.html",
    "how-to-cite.html",
    "metrics-guide.html",
    "networks.html",
    "indology_scholars_analytics.md",
]

PUBLIC_DIRS = [
    "assets",
    "analytics_output",
    "scholars",
    "conferences",
    "themes",
    "topics",
    "generations",
    "meso",
    "gumilyov",
    "videos",
    "findings",
    "cities",
    "institutions",
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


def main():
    dest = Path("_site")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()

    for path in PUBLIC_PATHS:
        copy_path(path, dest)
    for path in PUBLIC_DIRS:
        copy_dir(path, dest)

    print(f"Prepared GitHub Pages artifact at {dest.resolve()}")


if __name__ == "__main__":
    main()
