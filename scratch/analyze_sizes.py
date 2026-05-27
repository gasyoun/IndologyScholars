import json
import os

with open("site_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for key in data:
    val = data[key]
    size = len(json.dumps(val, ensure_ascii=False))
    print(f"Key: {key}, Size: {size / 1024:.2f} KB")

# Analyze scholars list sizes
scholars = data["scholars"]
print(f"Total scholars: {len(scholars)}")
# Let's see what is the size of scholars if we remove 'talks'
scholars_no_talks = []
for s in scholars:
    s_copy = dict(s)
    s_copy.pop("talks", None)
    scholars_no_talks.append(s_copy)
size_no_talks = len(json.dumps(scholars_no_talks, ensure_ascii=False))
print(f"Scholars without talks size: {size_no_talks / 1024:.2f} KB")

# And size of talks themselves
all_talks_count = sum(len(s.get("talks", [])) for s in scholars)
print(f"Total scholar talks: {all_talks_count}")
