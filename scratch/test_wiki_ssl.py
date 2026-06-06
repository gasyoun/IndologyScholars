import ssl, urllib.request, urllib.parse, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

query = urllib.parse.urlencode({
    "action": "query",
    "list": "search",
    "srsearch": "индолог",
    "format": "json",
    "srlimit": "3",
})
url = "https://ru.wikipedia.org/w/api.php?" + query
print("URL:", url[:80])
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 IndologyScholars/1.0"})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        data = resp.read().decode("utf-8")
        print("OK:", len(data), "bytes")
        result = json.loads(data)
        hits = result.get("query", {}).get("search", [])
        print("Hits:", len(hits))
        for h in hits[:3]:
            print(" ", h["title"])
except Exception as e:
    print("FAIL:", type(e).__name__, str(e)[:200])
