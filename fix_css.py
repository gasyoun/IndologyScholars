import re
with open('publication_helpers.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the PUBLIC_ID_CSS block
text = re.sub(r'PUBLIC_ID_CSS = \"\"\"\s*<style>.*?</style>\s*\"\"\"', 'PUBLIC_ID_CSS = ""', text, flags=re.DOTALL)

# Replace the main <style> block in page_shell
text = re.sub(r'<style>.*?</style>', '<link rel="stylesheet" href="/IndologyScholars/assets/styles.css">', text, flags=re.DOTALL)

with open('publication_helpers.py', 'w', encoding='utf-8') as f:
    f.write(text)
