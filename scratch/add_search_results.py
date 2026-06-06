"""Add 12 new names found via Wikipedia full-text search to expanded JSON."""
import json

with open("scratch/wikipedia_indologists_expanded.json", "r", encoding="utf-8") as f:
    data = json.load(f)

existing_names = set()
for p in data["people"]:
    existing_names.add(p.get("full_name", "").lower())

new_people = [
    ("Лебедев", "Герасим Степанович", "1749–1817", "первый русский индолог"),
    ("Ленц", "Роберт Христианович", "1808–1836", "востоковед, индолог и санскритолог"),
    ("Петров", "Павел Яковлевич", "1814–1875", "санскритолог, индолог"),
    ("Бётлингк", "Оттон Николаевич", "1815–1904", "санскритолог, индолог"),
    ("Миронов", "Николай Дмитриевич", "1880–1936", "индолог, санскритолог"),
    ("Болензен", "Фёдор Фёдорович", "1810–1878", "индолог, санскритолог"),
    ("Голубев", "Виктор Викторович", "1878–1945", "востоковед, индолог"),
    ("Минаев", "Иван Павлович", "1840–1890", "востоковед-индолог"),
    ("Булич", "Сергей Константинович", "1859–1921", "индолог, лингвист"),
    ("Овсянико-Куликовский", "Дмитрий Николаевич", "1853–1920", "индолог, санскритолог"),
    ("Перзашкевич", "Олег Валерьевич", "", "индолог"),
    ("Кудрявский", "Дмитрий Николаевич", "1867–1920", "историк-индолог, языковед"),
]

added = 0
for surname, given, years, desc in new_people:
    full = f"{given} {surname}"
    if full.lower() in existing_names:
        continue
    data["people"].append({
        "wikipedia_title": f"{surname}, {given}",
        "surname": surname,
        "given_name": given,
        "full_name": full,
        "birth_year": None,
        "death_year": None,
        "scientific_field": "индология",
        "role": "индолог",
        "workplace": "",
        "alma_mater": "",
        "degree": "",
        "wikidata_qid": "",
        "is_indologist": True,
        "notes": f"{desc}. Найден через полнотекстовый поиск Wikipedia (srsearch→HTML).",
    })
    added += 1

data["total_people"] = len(data["people"])

with open("scratch/wikipedia_indologists_expanded.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Added: {added}")
print(f"Total Wiki people: {len(data['people'])}")
print(f"Institutional additions: {len(data.get('new_from_institutions', []))}")
print(f"Grand total: {len(data['people']) + len(data.get('new_from_institutions', []))}")
