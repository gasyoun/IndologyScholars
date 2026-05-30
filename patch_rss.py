import re
from pathlib import Path

# 1. Update base.html
base_path = Path("templates/base.html")
base_content = base_path.read_text(encoding="utf-8")
if "application/rss+xml" not in base_content:
    base_content = base_content.replace(
        '<link rel="manifest" href="/IndologyScholars/site.webmanifest">',
        '<link rel="manifest" href="/IndologyScholars/site.webmanifest">\\n    <link rel="alternate" type="application/rss+xml" title="RSS" href="/IndologyScholars/feed.xml">'
    )
    base_path.write_text(base_content, encoding="utf-8")

# 2. Update generate_publication_pages.py
with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

rss_func = '''def generate_rss_feed(records):
    unique_records = list(presentation_records_by_id(records).values())
    unique_records.sort(key=lambda talk: (-int(talk.get("year") or 0), talk.get("title") or ""))
    
    items_xml = []
    from publication_helpers import clean_text, slugify
    import datetime as dt
    
    # We take the top 100 most recent presentations
    for talk in unique_records[:100]:
        title = clean_text(talk.get("title") or "Доклад")
        author = clean_text(talk.get("author") or "Неизвестный автор")
        year = int(talk.get("year") or 0)
        series = clean_text(talk.get("series_key") or talk.get("series") or "")
        pid = clean_text(talk.get("presentation_id") or "")
        
        fallback = pid.lower().replace("_", "-")
        slug = slugify(title, fallback=fallback)
        if len(slug) > 96:
            slug = slug[:96].strip("-") or fallback
            
        link = site_url(f"p/{slug}.html")
        desc = f"Доклад: {title}. Автор: {author}. Конференция: {series} ({year})."
        
        pub_date = dt.datetime(year, 1, 1, 12, 0).strftime("%a, %d %b %Y %H:%M:%S +0000") if year else ""
        
        item = [
            "    <item>",
            f"      <title>{esc(title)}</title>",
            f"      <link>{esc(link)}</link>",
            f"      <description>{esc(desc)}</description>",
            f"      <guid>{esc(link)}</guid>",
        ]
        if pub_date:
            item.append(f"      <pubDate>{pub_date}</pubDate>")
        item.append("    </item>")
        
        items_xml.append("\\n".join(item))
        
    rss = [
        '<?xml version="1.0" encoding="UTF-8" ?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        f'    <title>{esc(SITE_NAME)}</title>',
        f'    <link>{site_url("")}</link>',
        '    <description>Архив российских индологических конференций и публикаций</description>',
        f'    <atom:link href="{site_url("feed.xml")}" rel="self" type="application/rss+xml" />',
        '    <language>ru</language>',
    ]
    rss.extend(items_xml)
    rss.append('  </channel>')
    rss.append('</rss>')
    
    write_text("feed.xml", "\\n".join(rss) + "\\n")
'''

if "def generate_rss_feed" not in content:
    # insert before def main()
    content = content.replace("def main():", rss_func + "\n\ndef main():")
    
if "generate_rss_feed(records)" not in content:
    content = content.replace("generate_publication_docs(data)", "generate_publication_docs(data)\n    generate_rss_feed(records)")
    
with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)

print("RSS patch applied.")
