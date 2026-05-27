with open('generate_publication_pages.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines[6450:6500]):
    print(f"Line {6450+i}: {line}")
