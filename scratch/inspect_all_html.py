import os

def check_html():
    files = sorted([f for f in os.listdir("html_cache") if f.endswith(".html")])
    out = []
    for filename in files:
        filepath = os.path.join("html_cache", filename)
        with open(filepath, 'rb') as f:
            raw = f.read(1000)
            
        # Try decoding with utf-8 first
        try:
            raw.decode('utf-8')
            encoding = 'utf-8'
        except Exception:
            # Try windows-1251
            try:
                raw.decode('windows-1251')
                encoding = 'windows-1251'
            except Exception:
                encoding = 'unknown'
                
        out.append(f"File {filename}: guessed {encoding}")
        
    with open("scratch/html_encodings.txt", 'w', encoding='utf-8') as f:
        f.write("\n".join(out))

if __name__ == "__main__":
    check_html()
