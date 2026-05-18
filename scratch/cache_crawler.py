import os
import time
import urllib.request
import urllib.error
import re
from html.parser import HTMLParser

# Configure cache directory
CACHE_DIR = "html_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

ZOGRAF_URLS = {
    2025: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=15177&option=com_content&task=view",
    2024: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=14999&option=com_content&task=view",
    2023: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=14847&option=com_content&task=view",
    2022: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=14629&option=com_content&task=view",
    2021: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=14119&option=com_content&task=view",
    2020: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=12981&option=com_content&task=view",
    2019: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=10154&option=com_content&task=view",
    2018: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=7591&option=com_content&task=view",
    2017: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=5510&option=com_content&task=view",
    2016: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=4789&option=com_content&task=view",
    2015: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=4023&option=com_content&task=view",
    2014: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=3663&option=com_content&task=view",
    2013: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=3296&option=com_content&task=view",
    2012: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=3036&option=com_content&task=view",
    2011: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=2846&option=com_content&task=view",
    2010: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=2609&option=com_content&task=view",
    2009: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=2306&option=com_content&task=view",
    2008: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=2074&option=com_content&task=view",
    2007: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=1791&option=com_content&task=view",
    2006: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=1251&option=com_content&task=view",
    2004: "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=80&option=com_content&task=view",
}

ROERICH_URLS = {
    2025: "https://ancient.ivran.ru/novosti?artid=222568",
    2024: "https://ancient.ivran.ru/novosti?artid=219061",
    2023: "https://ancient.ivran.ru/novosti?artid=221598",
    2022: "https://ancient.ivran.ru/novosti?artid=221597",
    2021: "https://ancient.ivran.ru/novosti?artid=221596",
    2020: "https://ancient.ivran.ru/novosti?artid=221595",
    2019: "https://ancient.ivran.ru/novosti?artid=221622",
    2018: "https://ancient.ivran.ru/novosti?artid=221623",
    2017: "https://ancient.ivran.ru/novosti?artid=221624",
    2016: "https://ancient.ivran.ru/novosti?artid=5940",
    2015: "https://ancient.ivran.ru/novosti?artid=4490",
    2014: "https://ancient.ivran.ru/novosti?artid=4868",
    2013: "https://ancient.ivran.ru/novosti?artid=4869",
    2012: "https://ancient.ivran.ru/novosti?artid=4870",
    2010: "https://ancient.ivran.ru/novosti?artid=4871",
    2009: "https://ancient.ivran.ru/novosti?artid=4872",
    2008: "https://ancient.ivran.ru/novosti?artid=4873",
    2007: "https://ancient.ivran.ru/novosti?artid=4874",
}

class PlainTextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return "".join(self.text_parts)

def fetch_page(url, filename):
    cache_path = os.path.join(CACHE_DIR, filename)
    if os.path.exists(cache_path):
        print(f"Loaded from cache: {filename}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()

    print(f"Fetching from web: {url}")
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    )
    
    # Try with up to 3 retries
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                time.sleep(1.0) # friendly crawl gap
                return html
        except Exception as e:
            print(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2.0)
    
    print(f"ERROR: Could not download {url}")
    return None

def main():
    print("Starting crawl of conference pages...")
    
    # Fetch Zograf
    for year, url in ZOGRAF_URLS.items():
        fetch_page(url, f"zograf_{year}.html")
        
    # Fetch Roerich
    for year, url in ROERICH_URLS.items():
        fetch_page(url, f"roerich_{year}.html")
        
    print("Done fetching pages! All downloaded successfully to cache folder.")

if __name__ == "__main__":
    main()
