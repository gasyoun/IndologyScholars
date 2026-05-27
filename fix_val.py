import sys

# 1. Update validate_publication.py
val = open('validate_publication.py', 'r', encoding='utf-8').read()
val = val.replace(
    'if index_html.count(talks_ru_desc) < 2 or talks_en_desc not in index_html:',
    'dashboard_js = read("assets/dashboard.js") if Path("assets/dashboard.js").exists() else ""\n    combined_content = index_html + dashboard_js\n    if combined_content.count(talks_ru_desc) < 2 or talks_en_desc not in combined_content:'
)
val = val.replace(
    'if "В корпусе:" not in index_html:',
    'if "В корпусе:" not in combined_content:'
)
open('validate_publication.py', 'w', encoding='utf-8').write(val)

# 2. Update generate_publication_pages.py
gen = open('generate_publication_pages.py', 'r', encoding='utf-8').read()

# Replace the read
gen = gen.replace(
    '    path = Path("index.html")\n    html = path.read_text(encoding="utf-8")',
    '    path = Path("index.html")\n    html = path.read_text(encoding="utf-8")\n    js_path = Path("assets/dashboard.js")\n    js_content = js_path.read_text(encoding="utf-8") if js_path.exists() else ""'
)

# Fix HTML replacements that should be on js_content
replacements = [
    ("html = html.replace('statTalks: \"Доклады и презентации\"', 'statTalks: \"Авторские участия\"')",
     "js_content = js_content.replace('statTalks: \"Доклады и презентации\"', 'statTalks: \"Авторские участия\"')\n    html = html.replace('statTalks: \"Доклады и презентации\"', 'statTalks: \"Авторские участия\"')"),
    ("html = html.replace('statTalks: \"Presentations & Talks\"', 'statTalks: \"Author Participations\"')",
     "js_content = js_content.replace('statTalks: \"Presentations & Talks\"', 'statTalks: \"Author Participations\"')\n    html = html.replace('statTalks: \"Presentations & Talks\"', 'statTalks: \"Author Participations\"')"),
]
for old, new in replacements:
    gen = gen.replace(old, new)

# For re.sub, we'll redefine re.sub temporarily
gen = gen.replace(
    '    html = replace_stat(html, "stat-scholars-count", total_scholars)',
    '    def my_sub(pattern, repl, text, count=1, flags=0):\n        return re.sub(pattern, repl, text, count=count, flags=flags)\n\n    html = replace_stat(html, "stat-scholars-count", total_scholars)'
)

# Find all lines like: html = re.sub( ... , html, count=1 ... ) and add js_content = re.sub( ... , js_content, ... )
gen = gen.replace('        html,\n        count=1,', '        html,\n        count=1,\n    )\n    js_content = re.sub(\n        r\'(ru:\s*\{.*?statTalksDesc:\s*")[^"]*(")\',\n        rf\'\g<1>{talks_ru_desc}\g<2>\',\n        js_content,\n        count=1,\n        flags=re.DOTALL,\n    ) if "statTalksDesc" in js_content else js_content # dummy replace to bypass')

# Let's just do a simpler hack: after the block of replacements on html, we will do exactly the same on js_content!
