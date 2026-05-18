import os

def test_md():
    filepath = "zograf-roerich-db.md"
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out = []
    for idx, line in enumerate(lines):
        if "D2004" in line or "D2006" in line:
            out.append(f"Line {idx+1}: {line.strip()}")
            
    with open("scratch/md_out.txt", 'w', encoding='utf-8') as f:
        f.write("\n".join(out))

if __name__ == "__main__":
    test_md()
