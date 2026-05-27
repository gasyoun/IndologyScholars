with open('generate_publication_pages.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_code = '''    path = Path("index.html")
    html = path.read_text(encoding="utf-8")'''

new_code = '''    path = Path("index.html")
    html = path.read_text(encoding="utf-8")
    js_path = Path("assets/dashboard.js")
    js_content = js_path.read_text(encoding="utf-8") if js_path.exists() else ""'''

text = text.replace(old_code, new_code)

with open('generate_publication_pages.py', 'w', encoding='utf-8') as f:
    f.write(text)
