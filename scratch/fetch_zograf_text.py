import urllib.request
from html.parser import HTMLParser
from pathlib import Path

class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_content = True # grab everything for now

    def handle_data(self, data):
        if self.in_content:
            self.text_parts.append(data)

url = "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=15177&option=com_content&task=view"
req = urllib.request.Request(
    url, 
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
)

try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        parser = MyHTMLParser()
        parser.feed(html)
        text = "".join(parser.text_parts)
        output = Path("archive/scratch/zograf_2025_text.txt")
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Success! Wrote text to {output}")
except Exception as e:
    print(f"Error: {e}")
