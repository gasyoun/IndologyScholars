import re

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

old_sitemap_func_start = '''    def write_sub_sitemap(filename, paths):
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
        write_text(filename, "\\n".join(urlset) + "\\n")'''

new_sitemap_func_start = '''    today_iso = dt.date.today().isoformat()

    def write_sub_sitemap(filename, paths):
        urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path in paths:
            if path == "index.html":
                loc = site_url("")
            elif path.endswith("/index.html"):
                loc = site_url(path[:-10])
            else:
                loc = site_url(path)
            urlset.append(f"  <url>\\n    <loc>{esc(loc)}</loc>\\n    <lastmod>{today_iso}</lastmod>\\n  </url>")
        urlset.append("</urlset>")
        write_text(filename, "\\n".join(urlset) + "\\n")'''

content = content.replace(old_sitemap_func_start, new_sitemap_func_start)


old_sitemap_index = '''    index_xml = [
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

new_sitemap_index = '''    index_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for sm in sitemaps:
        loc = site_url(sm)
        index_xml.append("  <sitemap>")
        index_xml.append(f"    <loc>{esc(loc)}</loc>")
        index_xml.append(f"    <lastmod>{today_iso}</lastmod>")
        index_xml.append("  </sitemap>")
    index_xml.append("</sitemapindex>")
    write_text("sitemap.xml", "\\n".join(index_xml) + "\\n")'''

content = content.replace(old_sitemap_index, new_sitemap_index)

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)

print("SEO lastmod patch applied.")
