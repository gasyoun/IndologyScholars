with open('generate_publication_pages.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Make the script also patch js_content
text = text.replace(
    'path.write_text(html, encoding="utf-8")',
    'path.write_text(html, encoding="utf-8")\n    if js_path.exists():\n        js_path.write_text(js_content, encoding="utf-8")'
)

# Also apply the re.sub to js_content
old_code = '''    html = re.sub(
        r\'(ru:\s*\{.*?statTalksDesc:\s*")[^"]*(")\',
        rf\'\g<1>{talks_ru_desc}\g<2>\',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
new_code = '''    if js_path.exists():
        js_content = re.sub(
            r'(ru:\\s*\\{.*?statTalksDesc:\\s*")[^"]*(")',
            rf'\\g<1>{talks_ru_desc}\\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(ru:\\s*\\{.*?statTalksDesc:\\s*")[^"]*(")',
        rf'\\g<1>{talks_ru_desc}\\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
text = text.replace(old_code, new_code)

old_code2 = '''    html = re.sub(
        r\'(en:\s*\{.*?statTalksDesc:\s*")[^"]*(")\',
        rf\'\g<1>{talks_en_desc}\g<2>\',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
new_code2 = '''    if js_path.exists():
        js_content = re.sub(
            r'(en:\\s*\\{.*?statTalksDesc:\\s*")[^"]*(")',
            rf'\\g<1>{talks_en_desc}\\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(en:\\s*\\{.*?statTalksDesc:\\s*")[^"]*(")',
        rf'\\g<1>{talks_en_desc}\\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
text = text.replace(old_code2, new_code2)

old_code3 = '''    html = re.sub(
        r\'(ru:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")\',
        rf\'\g<1>{corpus_pause_ru}\g<2>\',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
new_code3 = '''    if js_path.exists():
        js_content = re.sub(
            r'(ru:\\s*\\{.*?findingsCorpusNote:\\s*")[^"]*(")',
            rf'\\g<1>{corpus_pause_ru}\\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(ru:\\s*\\{.*?findingsCorpusNote:\\s*")[^"]*(")',
        rf'\\g<1>{corpus_pause_ru}\\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
text = text.replace(old_code3, new_code3)

old_code4 = '''    html = re.sub(
        r\'(en:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")\',
        rf\'\g<1>{corpus_pause_en}\g<2>\',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
new_code4 = '''    if js_path.exists():
        js_content = re.sub(
            r'(en:\\s*\\{.*?findingsCorpusNote:\\s*")[^"]*(")',
            rf'\\g<1>{corpus_pause_en}\\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(en:\\s*\\{.*?findingsCorpusNote:\\s*")[^"]*(")',
        rf'\\g<1>{corpus_pause_en}\\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )'''
text = text.replace(old_code4, new_code4)

with open('generate_publication_pages.py', 'w', encoding='utf-8') as f:
    f.write(text)
