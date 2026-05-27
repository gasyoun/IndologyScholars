import re
with open('generate_scholars_pages.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace extra_css block
text = re.sub(r'extra_css = \"\"\"\s*<style>.*?</style>\s*\"\"\"', 'extra_css = ""', text, flags=re.DOTALL)

with open('generate_scholars_pages.py', 'w', encoding='utf-8') as f:
    f.write(text)
