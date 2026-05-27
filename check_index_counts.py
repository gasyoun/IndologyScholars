import json
with open('site_data.json', 'r', encoding='utf-8') as f:
    summary = json.load(f).get('summary', {})
print(f"total_presentations: {summary.get('total_presentations')}")
print(f"unique_presentations: {summary.get('unique_presentations')}")

with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

talks_ru_desc = f"{summary.get('total_presentations')} участий в {summary.get('unique_presentations')} уникальных докладах"
talks_en_desc = f"{summary.get('total_presentations')} participations across {summary.get('unique_presentations')} unique talks"
print("ru desc count:", text.count(talks_ru_desc))
print("en desc count:", text.count(talks_en_desc))
print("В корпусе count:", text.count("В корпусе:"))
