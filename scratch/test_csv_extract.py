import re
import csv
import io

def extract_csv_from_md(md_path, csv_name):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find ### CSVName.csv and the following csv block
    pattern = r'###\s+' + re.escape(csv_name) + r'\s*\n\n```csv\n(.*?)\n```'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        # Try without the .csv suffix
        pattern_alt = r'###\s+' + re.escape(csv_name.replace('.csv', '')) + r'\s*\n\n```csv\n(.*?)\n```'
        match = re.search(pattern_alt, content, re.DOTALL)
        
    if not match:
        print(f"Could not find CSV block for {csv_name}")
        return []
    
    csv_data = match.group(1)
    reader = csv.DictReader(io.StringIO(csv_data))
    return list(reader)

# Let's test it
md_path = r"c:\Users\user\Documents\GitHub\IndologyScholars\zograf-roerich-db.md"
posts = extract_csv_from_md(md_path, "Posts.csv")
print(f"Parsed {len(posts)} posts!")
if posts:
    print(posts[0])
