import os
import chardet

def check_encodings():
    files = [f for f in os.listdir("html_cache") if f.endswith(".html")]
    for filename in sorted(files):
        filepath = os.path.join("html_cache", filename)
        with open(filepath, 'rb') as f:
            raw_data = f.read(5000) # read first 5kb
        res = chardet.detect(raw_data)
        print(f"File {filename}: detected {res['encoding']} with confidence {res['confidence']}")

if __name__ == "__main__":
    check_encodings()
