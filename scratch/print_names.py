import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
with open('site_data.json', encoding='utf-8') as f:
    d = json.load(f)

for s in d['scholars'][:40]:
    print(f"ID: {s.get('id')}, FullNameRu: {repr(s.get('full_name_ru'))}, DisplayName: {repr(s.get('display_name'))}, Name: {repr(s.get('name'))}")
