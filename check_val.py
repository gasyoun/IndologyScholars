import re
with open('validate_publication.py', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.splitlines()):
    if 'index.html' in line:
        print(f"Line {i+1}: {line}")
