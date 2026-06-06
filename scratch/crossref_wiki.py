import json
import re

# 1. Load conference scholars
with open("site_data_scholars.json", encoding="utf-8") as f:
    scholars = json.load(f)

print(f"=== Total scholars in site_data_scholars.json: {len(scholars)} ===")
print()

# Extract full names
scholar_full_names = [
    (s["id"], s["full_name_ru"], s["total_talks"], s.get("death_year"))
    for s in scholars
]
scholar_short_names = [
    (s["id"], s["name"], s["full_name_ru"], s["total_talks"])
    for s in scholars
]

# 2. Normalize names for matching
def normalize_wiki_name(wiki_name):
    parts = wiki_name.split(",")
    if len(parts) >= 2:
        last = parts[0].strip()
        rest = " ".join(p.strip() for p in parts[1:])
        full = f"{last} {rest}"
    else:
        full = wiki_name.strip()
    full = re.sub(r"\s*\(.*?\)\s*", "", full)
    return full.lower().strip()

def normalize_scholar_name(full_name):
    return full_name.lower().strip()

# Wikipedia names list (69 names)
wiki_names_raw = [
    "\u0410\u043b\u0430\u0435\u0432, \u041b\u0435\u043e\u043d\u0438\u0434 \u0411\u043e\u0440\u0438\u0441\u043e\u0432\u0438\u0447",
    "\u0410\u043b\u0438\u0445\u0430\u043d\u043e\u0432\u0430, \u042e\u043b\u0438\u044f \u041c\u0430\u0440\u043a\u043e\u0432\u043d\u0430",
    "\u0410\u043b\u044c\u0431\u0435\u0434\u0438\u043b\u044c, \u041c\u0430\u0440\u0433\u0430\u0440\u0438\u0442\u0430 \u0424\u0451\u0434\u043e\u0440\u043e\u0432\u043d\u0430",
    "\u0410\u043d\u0434\u0440\u043e\u043d\u043e\u0432, \u041c\u0438\u0445\u0430\u0438\u043b \u0421\u0435\u0440\u0433\u0435\u0435\u0432\u0438\u0447",
    "\u0410\u043d\u0438\u043a\u0435\u0435\u0432, \u041d\u0438\u043a\u043e\u043b\u0430\u0439 \u041f\u0435\u0442\u0440\u043e\u0432\u0438\u0447",
    "\u0410\u043d\u0442\u043e\u043d\u043e\u0432\u0430, \u041a\u043e\u043a\u0430 \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440\u043e\u0432\u043d\u0430",
    "\u0410\u0448\u0440\u0430\u0444\u044f\u043d, \u041a\u043b\u0430\u0440\u0430 \u0417\u0430\u0440\u043c\u0430\u0439\u0440\u043e\u0432\u043d\u0430",
    "\u0411\u043e\u043d\u0433\u0430\u0440\u0434-\u041b\u0435\u0432\u0438\u043d, \u0413\u0440\u0438\u0433\u043e\u0440\u0438\u0439 \u041c\u0430\u043a\u0441\u0438\u043c\u043e\u0432\u0438\u0447",
    "\u0411\u0440\u043e\u0434\u043e\u0432, \u0412\u0430\u0441\u0438\u043b\u0438\u0439 \u0412\u0430\u0441\u0438\u043b\u044c\u0435\u0432\u0438\u0447",
    "\u0411\u0443\u0445\u0430\u0440\u0438\u043d, \u041c\u0438\u0445\u0430\u0438\u043b \u0414\u043c\u0438\u0442\u0440\u0438\u0435\u0432\u0438\u0447",
    "\u0412\u0430\u043d\u0438\u043d\u0430, \u0415\u0432\u0433\u0435\u043d\u0438\u044f \u042e\u0440\u044c\u0435\u0432\u043d\u0430",
    "\u0412\u0430\u0441\u0438\u043b\u044c\u043a\u043e\u0432, \u042f\u0440\u043e\u0441\u043b\u0430\u0432 \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440\u043e\u0432\u0438\u0447",
    "\u0412\u0435\u0440\u0442\u043e\u0433\u0440\u0430\u0434\u043e\u0432\u0430, \u0412\u0438\u043a\u0442\u043e\u0440\u0438\u044f \u0412\u0438\u043a\u0442\u043e\u0440\u043e\u0432\u043d\u0430",
    "\u0412\u0438\u0433\u0430\u0441\u0438\u043d, \u0410\u043b\u0435\u043a\u0441\u0435\u0439 \u0410\u043b\u0435\u043a\u0441\u0435\u0435\u0432\u0438\u0447",
    "\u0412\u043e\u0440\u043e\u0431\u044c\u0451\u0432\u0430-\u0414\u0435\u0441\u044f\u0442\u043e\u0432\u0441\u043a\u0430\u044f, \u041c\u0430\u0440\u0433\u0430\u0440\u0438\u0442\u0430 \u0418\u043e\u0441\u0438\u0444\u043e\u0432\u043d\u0430",
    "\u0413\u043b\u0443\u0448\u043a\u043e\u0432\u0430, \u0418\u0440\u0438\u043d\u0430 \u041f\u0435\u0442\u0440\u043e\u0432\u043d\u0430",
    "\u0413\u0440\u0438\u043d\u0446\u0435\u0440, \u041f\u0430\u0432\u0435\u043b \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440\u043e\u0432\u0438\u0447",
    "\u0413\u0443\u0440\u043e\u0432, \u041d\u0438\u043a\u0438\u0442\u0430 \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440\u043e\u0432\u0438\u0447",
    "\u0413\u0443\u0441\u0435\u0432\u0430, \u041d\u0430\u0442\u0430\u043b\u044c\u044f \u0420\u043e\u043c\u0430\u043d\u043e\u0432\u043d\u0430",
    "\u0414\u0443\u0431\u044f\u043d\u0441\u043a\u0438\u0439, \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440 \u041c\u0438\u0445\u0430\u0439\u043b\u043e\u0432\u0438\u0447",
    "\u0415\u043b\u0438\u0437\u0430\u0440\u0435\u043d\u043a\u043e\u0432\u0430, \u0422\u0430\u0442\u044c\u044f\u043d\u0430 \u042f\u043a\u043e\u0432\u043b\u0435\u0432\u043d\u0430",
    "\u0417\u0430\u043b\u0438\u0437\u043d\u044f\u043a, \u0410\u043d\u0434\u0440\u0435\u0439 \u0410\u043d\u0430\u0442\u043e\u043b\u044c\u0435\u0432\u0438\u0447",
    "\u0417\u0430\u0445\u0430\u0440\u044c\u0438\u043d, \u0411\u043e\u0440\u0438\u0441 \u0410\u043b\u0435\u043a\u0441\u0435\u0435\u0432\u0438\u0447",
    "\u0417\u043e\u0433\u0440\u0430\u0444, \u0413\u0435\u043e\u0440\u0433\u0438\u0439 \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440\u043e\u0432\u0438\u0447",
    "\u0418\u0441\u0430\u0435\u0432\u0430, \u041d\u0430\u0442\u0430\u043b\u0438\u044f \u0412\u0430\u0441\u0438\u043b\u044c\u0435\u0432\u043d\u0430",
    "\u041a\u0430\u043b\u044c\u044f\u043d\u043e\u0432, \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440 \u0418\u0432\u0430\u043d\u043e\u0432\u0438\u0447",
    "\u041a\u043e\u0441\u0442\u044e\u0447\u0435\u043d\u043a\u043e, \u0412\u043b\u0430\u0434\u0438\u0441\u043b\u0430\u0432 \u0421\u0435\u0440\u0433\u0435\u0435\u0432\u0438\u0447",
    "\u041a\u043e\u0442\u043e\u0432\u0441\u043a\u0438\u0439, \u0413\u0440\u0438\u0433\u043e\u0440\u0438\u0439 \u0413\u0440\u0438\u0433\u043e\u0440\u044c\u0435\u0432\u0438\u0447",
    "\u041a\u0443\u043b\u0438\u043a\u043e\u0432, \u041b\u0435\u043e\u043d\u0438\u0434 \u0418\u0433\u043e\u0440\u0435\u0432\u0438\u0447",
    "\u041a\u0443\u0446\u0435\u043d\u043a\u043e\u0432, \u0410\u043d\u0430\u0442\u043e\u043b\u0438\u0439 \u0410\u043a\u0438\u043c\u043e\u0432\u0438\u0447",
    "\u041b\u044b\u0441\u0435\u043d\u043a\u043e, \u0412\u0438\u043a\u0442\u043e\u0440\u0438\u044f \u0413\u0435\u043e\u0440\u0433\u0438\u0435\u0432\u043d\u0430",
    "\u041c\u0430\u043a\u0430\u0435\u0432, \u042d\u043d\u0432\u0435\u0440 \u0410\u0445\u043c\u0435\u0434\u043e\u0432\u0438\u0447",
    "\u041d\u0435\u0432\u0435\u043b\u0435\u0432\u0430, \u0421\u0432\u0435\u0442\u043b\u0430\u043d\u0430 \u041b\u0435\u043e\u043d\u0438\u0434\u043e\u0432\u043d\u0430",
    "\u041e\u0433\u0438\u0431\u0435\u043d\u0438\u043d, \u0411\u043e\u0440\u0438\u0441 \u041b\u0435\u043e\u043d\u0438\u0434\u043e\u0432\u0438\u0447",
    "\u041e\u0440\u0435\u043b\u044c\u0441\u043a\u0430\u044f, \u041c\u0430\u0440\u0438\u043d\u0430 \u0412\u0430\u043b\u0435\u0440\u044c\u0435\u0432\u043d\u0430",
    "\u041f\u0430\u0432\u043b\u043e\u0432, \u042e\u0440\u0438\u0439 \u041c\u0438\u0445\u0430\u0439\u043b\u043e\u0432\u0438\u0447 (\u0443\u0447\u0451\u043d\u044b\u0439)",
    "\u041f\u0430\u0440\u0438\u0431\u043e\u043a, \u0410\u043d\u0434\u0440\u0435\u0439 \u0412\u0441\u0435\u0432\u043e\u043b\u043e\u0434\u043e\u0432\u0438\u0447",
    "\u041f\u0443\u043b\u044f\u0440\u043a\u0438\u043d, \u0412\u0430\u043b\u0435\u0440\u0438\u0439 \u0410\u043b\u0435\u043a\u0441\u0435\u0435\u0432\u0438\u0447",
    "\u041f\u044f\u0442\u0438\u0433\u043e\u0440\u0441\u043a\u0438\u0439, \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440 \u041c\u043e\u0438\u0441\u0435\u0435\u0432\u0438\u0447",
    "\u0420\u043e\u043c\u0430\u043d\u043e\u0432, \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440 \u041d\u0438\u043a\u043e\u043b\u0430\u0435\u0432\u0438\u0447 (\u0438\u0441\u0442\u043e\u0440\u0438\u043a)",
    "\u0420\u0443\u0434\u043e\u0439, \u0412\u0430\u043b\u0435\u0440\u0438\u0439 \u0418\u0441\u0430\u0435\u0432\u0438\u0447",
    "\u0420\u044b\u0431\u0430\u043a\u043e\u0432, \u0420\u043e\u0441\u0442\u0438\u0441\u043b\u0430\u0432 \u0411\u043e\u0440\u0438\u0441\u043e\u0432\u0438\u0447",
    "\u0421\u0430\u0432\u0435\u043b\u044c\u0435\u0432\u0430, \u041b\u044e\u0434\u043c\u0438\u043b\u0430 \u0412\u0430\u0441\u0438\u043b\u044c\u0435\u0432\u043d\u0430",
    "\u0421\u0430\u0437\u0430\u043d\u043e\u0432\u0430, \u041d\u0430\u0442\u0430\u043b\u044c\u044f \u041c\u0438\u0445\u0430\u0439\u043b\u043e\u0432\u043d\u0430",
    "\u0421\u0430\u043c\u043e\u0437\u0432\u0430\u043d\u0446\u0435\u0432, \u0410\u043d\u0434\u0440\u0435\u0439 \u041c\u0438\u0445\u0430\u0439\u043b\u043e\u0432\u0438\u0447",
    "\u0421\u0434\u0430\u0441\u044e\u043a, \u0413\u0430\u043b\u0438\u043d\u0430 \u0412\u0430\u0441\u0438\u043b\u044c\u0435\u0432\u043d\u0430",
    "\u0421\u0435\u043d\u043a\u0435\u0432\u0438\u0447, \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440 \u041d\u0438\u043a\u043e\u043b\u0430\u0435\u0432\u0438\u0447",
    "\u0421\u0435\u0440\u0435\u0431\u0440\u044f\u043a\u043e\u0432, \u0418\u0433\u043e\u0440\u044c \u0414\u043c\u0438\u0442\u0440\u0438\u0435\u0432\u0438\u0447",
    "\u0421\u0435\u0440\u0435\u0431\u0440\u044f\u043d\u044b\u0439, \u0421\u0435\u0440\u0433\u0435\u0439 \u0414\u043c\u0438\u0442\u0440\u0438\u0435\u0432\u0438\u0447",
    "\u0421\u0442\u043e\u043b\u044f\u0440\u043e\u0432, \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440 \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440\u043e\u0432\u0438\u0447 (\u0438\u043d\u0434\u043e\u043b\u043e\u0433)",
    "\u0421\u0443\u0432\u043e\u0440\u043e\u0432\u0430, \u0410\u043d\u043d\u0430 \u0410\u0440\u043e\u043d\u043e\u0432\u043d\u0430",
    "\u0422\u0430\u0432\u0430\u0441\u0442\u0448\u0435\u0440\u043d\u0430, \u0421\u0435\u0440\u0433\u0435\u0439 \u0421\u0435\u0440\u0433\u0435\u0435\u0432\u0438\u0447",
    "\u0422\u0435\u0440\u0435\u043d\u0442\u044c\u0435\u0432, \u0410\u043d\u0434\u0440\u0435\u0439 \u0410\u043d\u0430\u0442\u043e\u043b\u044c\u0435\u0432\u0438\u0447",
    "\u0422\u043a\u0430\u0447\u0451\u0432\u0430, \u0410\u043d\u043d\u0430 \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440\u043e\u0432\u043d\u0430",
    "\u0422\u043e\u043b\u0441\u0442\u0430\u044f, \u041d\u0430\u0442\u0430\u043b\u044c\u044f \u0418\u0432\u0430\u043d\u043e\u0432\u043d\u0430",
    "\u0422\u043e\u043f\u043e\u0440\u043e\u0432, \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440 \u041d\u0438\u043a\u043e\u043b\u0430\u0435\u0432\u0438\u0447",
    "\u0422\u044e\u043b\u044f\u0435\u0432, \u0421\u0435\u043c\u0451\u043d \u0418\u0432\u0430\u043d\u043e\u0432\u0438\u0447",
    "\u0423\u043b\u044c\u0446\u0438\u0444\u0435\u0440\u043e\u0432, \u041e\u043b\u0435\u0433 \u0413\u0435\u043e\u0440\u0433\u0438\u0435\u0432\u0438\u0447",
    "\u0423\u043b\u044c\u044f\u043d\u043e\u0432\u0441\u043a\u0438\u0439, \u0420\u043e\u0441\u0442\u0438\u0441\u043b\u0430\u0432 \u0410\u043b\u0435\u043a\u0441\u0430\u043d\u0434\u0440\u043e\u0432\u0438\u0447",
    "\u0427\u0435\u043b\u044b\u0448\u0435\u0432, \u0415\u0432\u0433\u0435\u043d\u0438\u0439 \u041f\u0435\u0442\u0440\u043e\u0432\u0438\u0447",
    "\u0427\u0435\u0440\u043d\u043e\u0432\u0441\u043a\u0430\u044f, \u0412\u0430\u043b\u0435\u043d\u0442\u0438\u043d\u0430 \u0412\u0435\u043d\u0438\u0430\u043c\u0438\u043d\u043e\u0432\u043d\u0430",
    "\u0428\u0430\u043f\u043e\u0448\u043d\u0438\u043a\u043e\u0432\u0430, \u041b\u044e\u0434\u043c\u0438\u043b\u0430 \u0412\u0430\u0441\u0438\u043b\u044c\u0435\u0432\u043d\u0430",
    "\u0428\u0430\u0441\u0442\u0438\u0442\u043a\u043e, \u041f\u0451\u0442\u0440 \u041c\u0438\u0445\u0430\u0439\u043b\u043e\u0432\u0438\u0447",
    "\u0428\u0430\u0443\u043c\u044f\u043d, \u0422\u0430\u0442\u044c\u044f\u043d\u0430 \u041b\u044c\u0432\u043e\u0432\u043d\u0430",
    "\u0428\u0435\u043f\u0442\u0443\u043d\u043e\u0432\u0430, \u0418\u0440\u0438\u043d\u0430 \u0418\u0433\u043e\u0440\u0435\u0432\u043d\u0430",
    "\u0428\u043e\u0445\u0438\u043d, \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440 \u041a\u0438\u0440\u0438\u043b\u043b\u043e\u0432\u0438\u0447",
    "\u042d\u0434\u0435\u043b\u044c\u043c\u0430\u043d, \u0414\u0436\u043e\u0439 \u0418\u043e\u0441\u0438\u0444\u043e\u0432\u043d\u0430",
    "\u042d\u0440\u043c\u0430\u043d, \u0412\u043b\u0430\u0434\u0438\u043c\u0438\u0440 \u0413\u0430\u043d\u0441\u043e\u0432\u0438\u0447",
]

# Normalize all wiki names
wiki_normalized = [(name, normalize_wiki_name(name)) for name in wiki_names_raw]

# Normalize all scholar full names
scholar_normalized = {}
for sid, full_name, talks, death_year in scholar_full_names:
    key = normalize_scholar_name(full_name)
    scholar_normalized[key] = (sid, full_name, talks, death_year)

# Index by last name + initials for fuzzy matching
def extract_last_first_patr(name):
    parts = name.split()
    if len(parts) >= 3:
        return (parts[0], parts[1][0] if parts[1] else "", parts[2][0] if len(parts) > 2 and parts[2] else "")
    return (name, "", "")

initials_index = {}
for full_name in scholar_normalized:
    last, fi, pi = extract_last_first_patr(full_name)
    key = (last, fi, pi)
    if key in initials_index:
        initials_index[key].append(full_name)
    else:
        initials_index[key] = [full_name]

# Cross-reference
print("=" * 80)
print("(B) WIKIPEDIA SCHOLARS WHO PARTICIPATED IN CONFERENCES")
print("=" * 80)
print()

matched = []
not_matched = []

for wiki_raw, wiki_norm in wiki_normalized:
    found = False
    found_talks = 0
    found_name = ""

    if wiki_norm in scholar_normalized:
        sid, full_name, talks, death = scholar_normalized[wiki_norm]
        found = True
        found_talks = talks
        found_name = full_name

    if not found:
        last, fi, pi = extract_last_first_patr(wiki_norm)
        key = (last, fi, pi)
        if key in initials_index:
            for candidate in initials_index[key]:
                if found:
                    break
                sid, full_name, talks, death = scholar_normalized[candidate]
                found = True
                found_talks = talks
                found_name = full_name

    if found:
        matched.append((wiki_raw, found_name, found_talks))
    else:
        not_matched.append(wiki_raw)

print(f"PARTICIPATED: {len(matched)} / {len(wiki_names_raw)}")
print("-" * 80)
for wiki, conf_name, talks in sorted(matched, key=lambda x: -x[2]):
    print(f"  {wiki}")
    print(f"    Conference name: {conf_name}")
    print(f"    Total talks: {talks}")
    print()

print()
print("=" * 80)
print("(C) WIKIPEDIA SCHOLARS WHO NEVER PARTICIPATED")
print("=" * 80)
print(f"NEVER PARTICIPATED: {len(not_matched)} / {len(wiki_names_raw)}")
print("-" * 80)
for name in not_matched:
    print(f"  {name}")

print()
print("=" * 80)
print("(D) ANALYSIS OF NEVER-PARTICIPATED GROUP")
print("=" * 80)

# Known living/deceased info (from general knowledge + data)
known_dead = {
    "Алаев, Леонид Борисович": "died 2024",
    "Андронов, Михаил Сергеевич": "died 2009",
    "Аникеев, Николай Петрович": "died 1992",
    "Антонова, Кока Александровна": "died 2007",
    "Ашрафян, Клара Зармайровна": "died 1999",
    "Бонгард-Левин, Григорий Максимович": "died 2008",
    "Бродов, Василий Васильевич": "died 2000s",
    "Гринцер, Павел Александрович": "died 2006",
    "Гусева, Наталья Романовна": "died 2010",
    "Елизаренкова, Татьяна Яковлевна": "died 2007",
    "Зализняк, Андрей Анатольевич": "died 2017",
    "Захарьин, Борис Алексеевич": "died 2016",
    "Зограф, Георгий Александрович": "died 2022",
    "Исаева, Наталия Васильевна": "living?",
    "Кальянов, Владимир Иванович": "died 2002",
    "Костюченко, Владислав Сергеевич": "died 2012",
    "Котовский, Григорий Григорьевич": "died 2001",
    "Куценков, Анатолий Акимович": "died 2021",
    "Макаев, Энвер Ахмедович": "died 2004?",
    "Огибенин, Борис Леонидович": "died (emigrated)",
    "Орельская, Марина Валерьевна": "living (active)",
    "Павлов, Юрий Михайлович (учёный)": "died 2023",
    "Пуляркин, Валерий Алексеевич": "died 2015",
    "Пятигорский, Александр Моисеевич": "died 2009",
    "Романов, Владимир Николаевич (историк)": "died 2013",
    "Рудой, Валерий Исаевич": "died 2009",
    "Рыбаков, Ростислав Борисович": "died 2019",
    "Савельева, Людмила Васильевна": "died?",
    "Сазанова, Наталья Михайловна": "living (active)",
    "Самозванцев, Андрей Михайлович": "died 2021",
    "Сдасюк, Галина Васильевна": "died 2021",
    "Сенкевич, Александр Николаевич": "died 2025",
    "Серебряков, Игорь Дмитриевич": "died 1998",
    "Столяров, Александр Александрович (индолог)": "living (active at RSUH)",
    "Суворова, Анна Ароновна": "died 2023",
    "Ткачёва, Анна Александровна": "died 2007",
    "Толстая, Наталья Ивановна": "died 2003",
    "Топоров, Владимир Николаевич": "died 2005",
    "Тюляев, Семён Иванович": "died 1993",
    "Ульциферов, Олег Георгиевич": "died 2022",
    "Ульяновский, Ростислав Александрович": "died 1995",
    "Челышев, Евгений Петрович": "died 2020",
    "Черновская, Валентина Вениаминовна": "died?",
    "Шапошникова, Людмила Васильевна": "died 2015",
    "Шаститко, Пётр Михайлович": "died 2018",
    "Шаумян, Татьяна Львовна": "living (active)",
    "Шептунова, Ирина Игоревна": "living (active)",
    "Эдельман, Джой Иосифовна": "died 2023",
    "Эрман, Владимир Гансович": "died 2017",
}

print()
print("Life status of never-participated scholars:")
print("-" * 60)
deceased = []
living = []
unknown = []
for name in not_matched:
    if name in known_dead:
        status = known_dead[name]
        if "living" in status.lower():
            living.append((name, status))
        elif "died" in status.lower():
            deceased.append((name, status))
        else:
            unknown.append((name, status))
    else:
        unknown.append((name, "unknown"))

print(f"  Deceased (or most likely deceased): {len(deceased)}")
for n, s in deceased:
    print(f"    {n}  ({s})")
print()
print(f"  Living (active but not in conference data): {len(living)}")
for n, s in living:
    print(f"    {n}  ({s})")
print()
print(f"  Unknown status: {len(unknown)}")
for n, s in unknown:
    print(f"    {n}  ({s})")

print()
print("=" * 80)
print("(A) ALL 270 SCHOLAR NAMES FROM CONFERENCE DATA")
print("=" * 80)
print(f"Total: {len(scholars)}")
print()
# Output as Python-like list
print("PYTHON LIST OF full_name_ru values:")
print("[")
for i, (sid, full_name, talks, death) in enumerate(scholar_full_names):
    comma = "," if i < len(scholar_full_names) - 1 else ""
    print(f'    "{full_name}"{comma}')
print("]")

print()
print("SUMMARY COUNTS:")
already_matched_set = set(norm for _, norm, _ in matched)
print(f"  Wikipedia names in conference data: {len(matched)}")
print(f"  Wikipedia names NOT in conference data: {len(not_matched)}")
print(f"  Total scholars in conference data: {len(scholars)}")
