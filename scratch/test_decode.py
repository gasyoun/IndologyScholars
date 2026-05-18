import os
import sys

def test_decoding():
    filepath = "html_cache/zograf_2004.html"
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'rb') as f:
        raw = f.read(10000)
        
    out = []
    
    # Try UTF-8
    try:
        utf8_decoded = raw.decode('utf-8')
        out.append("--- UTF-8 ---")
        out.append(utf8_decoded[:500])
    except Exception as e:
        out.append(f"UTF-8 failed: {e}")
        
    # Try Windows-1251
    try:
        win1251_decoded = raw.decode('windows-1251')
        out.append("--- WINDOWS-1251 ---")
        out.append(win1251_decoded[:500])
    except Exception as e:
        out.append(f"Windows-1251 failed: {e}")

    with open("scratch/decode_out.txt", 'w', encoding='utf-8') as f:
        f.write("\n\n".join(out))

if __name__ == "__main__":
    test_decoding()
