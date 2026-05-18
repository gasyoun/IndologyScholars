import os
from html.parser import HTMLParser

class SmartHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.block_tags = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'ol', 'ul'}

    def handle_starttag(self, tag, attrs):
        if tag in self.block_tags:
            self._add_newline()

    def handle_endtag(self, tag):
        if tag in self.block_tags:
            self._add_newline()

    def handle_data(self, data):
        self.text_parts.append(data)

    def _add_newline(self):
        if self.text_parts and not self.text_parts[-1].endswith('\n'):
            self.text_parts.append('\n')

    def get_text(self):
        return "".join(self.text_parts)

with open("html_cache/roerich_2024.html", "r", encoding="utf-8") as f:
    html = f.read()

parser = SmartHTMLParser()
parser.feed(html)
text = parser.get_text()
lines = [line.strip() for line in text.split('\n') if line.strip()]

with open("debug_roerich_lines.txt", "w", encoding="utf-8") as f:
    f.write("First 300 lines of smart-parsed Roerich 2024 text:\n")
    for i, line in enumerate(lines[:300]):
        f.write(f"{i+1}: {line}\n")
print(f"Done writing to debug_roerich_lines.txt! Total lines: {len(lines)}")
