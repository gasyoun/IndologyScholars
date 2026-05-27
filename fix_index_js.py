import re
with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'<script>(.*?)</script>', text, flags=re.DOTALL)
if m:
    with open('assets/dashboard.js', 'w', encoding='utf-8') as out:
        out.write(m.group(1))
    text = text[:m.start()] + '<script src="/IndologyScholars/assets/dashboard.js"></script>' + text[m.end():]
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(text)
