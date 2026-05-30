import re

with open("generate_scholars_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

old_shell = '''    return page_shell(
        f"{name_ru} | {SITE_NAME}",
        description,
        path,
        body,
        profile_structured_data(scholar, authority),
        extra_head=extra_css,
    )'''

new_shell = '''    og_path = f"assets/og/scholar_{public_id}.png"
    from publication_helpers import create_dynamic_og_image
    create_dynamic_og_image([name_ru, profile_label, f"Докладов: {scholar.get('total_talks') or 0}"], og_path)

    return page_shell(
        f"{name_ru} | {SITE_NAME}",
        description,
        path,
        body,
        profile_structured_data(scholar, authority),
        extra_head=extra_css,
        custom_og_image=og_path,
    )'''

if "custom_og_image=og_path" not in content:
    content = content.replace(old_shell, new_shell)
    with open("generate_scholars_pages.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("generate_scholars_pages.py updated.")
