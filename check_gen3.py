with open('generate_publication_pages.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines[6420:6435]):
    print(f"Line {6420+i}: {line}")
