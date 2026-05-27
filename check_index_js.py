import re
with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

scripts = re.findall(r'<script>(.*?)</script>', text, flags=re.DOTALL)
for i, s in enumerate(scripts):
    print(f"Script {i} length: {len(s)}")
