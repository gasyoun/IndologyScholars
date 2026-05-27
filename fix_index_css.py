import re
with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'<style>(.*?)</style>', text, flags=re.DOTALL)
if m:
    with open('assets/index.css', 'w', encoding='utf-8') as out:
        out.write(m.group(1))
    text = text[:m.start()] + '<link rel="stylesheet" href="/IndologyScholars/assets/index.css">' + text[m.end():]
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(text)
