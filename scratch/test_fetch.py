import urllib.request
import urllib.error

url = "https://www.orientalstudies.ru/rus/index.php?Itemid=48&id=15177&option=com_content&task=view"
req = urllib.request.Request(
    url, 
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru,en-US;q=0.7,en;q=0.3'
    }
)

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8', errors='ignore')
        print(f"Success! Length of HTML: {len(html)}")
        print(html[:500])
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
except Exception as e:
    print(f"Error: {e}")
