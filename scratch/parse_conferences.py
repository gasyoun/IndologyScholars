import os
import re
from html.parser import HTMLParser

CACHE_DIR = "html_cache"

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

# Regex to detect presentations
# Format: Name (City/Affil) Title
TALK_REGEX = re.compile(
    r'^([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,2}|\s*[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z][а-яёa-z\-]+|\s*[А-ЯЁA-Z][а-яёa-z\-]+\s+[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z]\.)\s*\(([^)]+)\)\.?\s*(.+)$'
)

def clean_title(title):
    title = title.strip()
    # Strip optional online markers
    title = re.sub(r'\s*\(\s*онлайн\s*\)\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(\s*zoom\s*\)\s*', '', title, flags=re.IGNORECASE)
    # Strip trailing dot
    if title.endswith('.'):
        title = title[:-1]
    return title.strip()

def preprocess_line(line):
    line = line.strip()
    # Remove leading time/number prefix e.g., "11.30.", "13. 00.", "14.30. ", "1."
    line = re.sub(r'^\s*\d{1,2}\s*[\.:]\s*\d{2}\s*\.?\s*', '', line)
    line = re.sub(r'^\s*\d{1,2}\s*\.\s*', '', line)
    return line.strip()

def parse_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = SmartHTMLParser()
    parser.feed(html)
    text = parser.get_text()
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    talks = []
    current_day = None
    
    for line in lines:
        # Check if line is a day or date indicator
        if "мая" in line or "декабря" in line or re.search(r'\b\d{1,2}\.\d{1,2}\.\d{4}\b', line):
            if len(line) < 100:
                current_day = line
        
        cleaned_line = preprocess_line(line)
        # Check if it matches a talk
        match = TALK_REGEX.match(cleaned_line)
        if match:
            speaker = match.group(1).strip()
            affil = match.group(2).strip()
            title = clean_title(match.group(3))
            
            talks.append({
                'day': current_day,
                'speaker': speaker,
                'affiliation': affil,
                'title': title,
                'raw': line
            })
            
    return talks

def main():
    print("Testing Zograf 2025 parsing:")
    z2025_path = os.path.join(CACHE_DIR, "zograf_2025.html")
    if os.path.exists(z2025_path):
        talks = parse_file(z2025_path)
        print(f"Total talks parsed: {len(talks)}")
        for i, t in enumerate(talks[:10]):
            safe_speaker = t['speaker'].encode('ascii', errors='replace').decode('ascii')
            safe_title = t['title'].encode('ascii', errors='replace').decode('ascii')
            print(f"{i+1}. Speaker: {safe_speaker} | Affiliation: {t['affiliation']} | Title: {safe_title}")
    
    print("\nTesting Roerich 2024 parsing:")
    r2024_path = os.path.join(CACHE_DIR, "roerich_2024.html")
    if os.path.exists(r2024_path):
        talks = parse_file(r2024_path)
        print(f"Total talks parsed: {len(talks)}")
        for i, t in enumerate(talks[:10]):
            safe_speaker = t['speaker'].encode('ascii', errors='replace').decode('ascii')
            safe_title = t['title'].encode('ascii', errors='replace').decode('ascii')
            print(f"{i+1}. Speaker: {safe_speaker} | Affiliation: {t['affiliation']} | Title: {safe_title}")

if __name__ == "__main__":
    main()
