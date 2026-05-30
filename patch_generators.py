import re

# 1. Patch generate_publication_pages.py
with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = '''        structured = [
            page_data(title, seo_description, path, page_type="ScholarlyArticle"),
            make_breadcrumbs([("Главная", ""), ("Доклады", "p/"), (title, path)]),
        ]
        write_text(path, page_shell(presentation_seo_title(title, public_id), seo_description, path, body, structured))'''

new_block = '''        structured = [
            page_data(title, seo_description, path, page_type="ScholarlyArticle"),
            make_breadcrumbs([("Главная", ""), ("Доклады", "p/"), (title, path)]),
        ]
        
        og_path = f"assets/og/presentation_{public_id}.png"
        from publication_helpers import create_dynamic_og_image
        author_text = clean_text(talk.get("author") or "")
        series_text = series_label(talk.get('series_key'), 'ru')
        create_dynamic_og_image([title, f"Автор: {author_text}" if author_text else "", f"Конференция: {series_text} ({year})"], og_path)
        
        write_text(path, page_shell(presentation_seo_title(title, public_id), seo_description, path, body, structured, custom_og_image=og_path))'''

if "custom_og_image=og_path" not in content:
    content = content.replace(old_block, new_block)
    with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("generate_publication_pages.py updated.")

# 2. Patch generate_scholars_pages.py
with open("generate_scholars_pages.py", "r", encoding="utf-8") as f:
    scholars_content = f.read()
    
# Let's find where page_shell is called
# Usually it's: write_text(path, page_shell(title, desc, path, body, structured))
import sys
import os
