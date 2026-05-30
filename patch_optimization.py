import re

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add LEGACY_REDIRECT_PATHS at the top
if "LEGACY_REDIRECT_PATHS =" not in content:
    content = re.sub(
        r'(import os\n)',
        r'\1\nLEGACY_REDIRECT_PATHS = set()\n',
        content
    )

# 2. Update redirect_html to populate LEGACY_REDIRECT_PATHS
old_redirect = '''def redirect_html(title, canonical_path, target_path):
    target_url = site_url(target_path)'''

new_redirect = '''def redirect_html(title, canonical_path, target_path):
    LEGACY_REDIRECT_PATHS.add(str(canonical_path).replace("\\\\", "/"))
    target_url = site_url(target_path)'''

content = content.replace(old_redirect, new_redirect)

# 3. Update write_app_icon to cache
old_app_icon = '''def write_app_icon(path, size):
    background = (10, 14, 26)'''

new_app_icon = '''def write_app_icon(path, size):
    if Path(path).exists():
        return
    background = (10, 14, 26)'''

content = content.replace(old_app_icon, new_app_icon)

# 4. Update write_og_image to cache
old_og_image = '''def write_og_image(path):
    width, height = 1200, 630'''

new_og_image = '''def write_og_image(path):
    if Path(path).exists():
        return
    width, height = 1200, 630'''

content = content.replace(old_og_image, new_og_image)

# 5. Update generate_sitemap to take data and records, and use the new logic
old_sitemap = '''def is_legacy_redirect(path):
    try:
        return "data-legacy-redirect" in Path(path).read_text(encoding="utf-8")
    except OSError:
        return False


def generate_sitemap():'''

new_sitemap = '''def generate_sitemap(data, records):'''

# We also need to rewrite the body of generate_sitemap
# I will just replace the whole function

sitemap_end = '''    index_xml.append("</sitemapindex>")
    write_text("sitemap.xml", "\\n".join(index_xml) + "\\n")'''

# Find the start and end of the sitemap block
match = re.search(r'def is_legacy_redirect\(path\):.*?def generate_sitemap\(\):.*?    write_text\("sitemap\.xml", "\\n"\.join\(index_xml\) \+ "\\n"\)', content, re.DOTALL)
if match:
    new_sitemap_func = '''def generate_sitemap(data, records):
    static_paths = [
        "index.html", "en.html", "search.html", "download-data.html",
        "data-quality.html", "methodology.html", "hypotheses.html", "data-sources.html",
        "known-limitations.html", "how-to-cite.html", "metrics-guide.html",
        "classification-criteria.html", "networks.html"
    ]
    static_paths = sorted(set(static_paths))

    canonical_scholars = {f"s/{scholar['url_slug']}.html" for scholar in data.get("scholars", []) if "url_slug" in scholar}
    canonical_scholars.add("s/index.html")

    scholars_paths = sorted(
        str(p).replace("\\\\", "/")
        for p in Path("s").glob("*.html")
        if str(p).replace("\\\\", "/") in canonical_scholars
    )

    canonical_publications = {f"p/{r['slug']}.html" for r in records if "slug" in r}
    canonical_publications.add("p/index.html")

    publications_paths = sorted(
        str(p).replace("\\\\", "/")
        for p in Path("p").glob("*.html")
        if str(p).replace("\\\\", "/") in canonical_publications
    )

    taxonomy_paths = []
    for dirname in ("conferences", "themes", "topics", "generations", "meso", "gumilyov", "videos", "findings", "cities", "institutions", "keywords"):
        taxonomy_paths.extend(
            str(p).replace("\\\\", "/")
            for p in Path(dirname).glob("*.html")
            if str(p).replace("\\\\", "/") not in LEGACY_REDIRECT_PATHS
        )
    taxonomy_paths = sorted(set(taxonomy_paths), key=lambda p: (p.count("/"), p))

    def write_sub_sitemap(filename, paths):
        urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path in paths:
            if path == "index.html":
                loc = site_url("")
            elif path.endswith("/index.html"):
                loc = site_url(path[:-10])
            else:
                loc = site_url(path)
            urlset.append(f"  <url><loc>{esc(loc)}</loc></url>")
        urlset.append("</urlset>")
        write_text(filename, "\\n".join(urlset) + "\\n")

    write_sub_sitemap("sitemap_static.xml", static_paths)
    write_sub_sitemap("sitemap_scholars.xml", scholars_paths)
    write_sub_sitemap("sitemap_publications.xml", publications_paths)
    write_sub_sitemap("sitemap_taxonomy.xml", taxonomy_paths)

    sitemaps = [
        "sitemap_static.xml", "sitemap_scholars.xml",
        "sitemap_publications.xml", "sitemap_taxonomy.xml",
    ]
    index_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for sm in sitemaps:
        loc = site_url(sm)
        index_xml.append("  <sitemap>")
        index_xml.append(f"    <loc>{esc(loc)}</loc>")
        index_xml.append("  </sitemap>")
    index_xml.append("</sitemapindex>")
    write_text("sitemap.xml", "\\n".join(index_xml) + "\\n")'''
    content = content.replace(match.group(0), new_sitemap_func)

# 6. Update generate_sitemap call in main()
content = content.replace("generate_sitemap()", "generate_sitemap(data, records)")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully.")
