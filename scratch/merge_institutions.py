"""Merge institutional data into expanded Wikipedia list.

Reads:
  - scratch/wikipedia_indologists_expanded.json (72 from Wikipedia categories)
  - scratch/institutional_indologists.json (87 from conference DB + Wikidata)
  - site_data_scholars.json (270 conference participants)

Produces:
  - scratch/wikipedia_indologists_expanded.json (updated with institution info)
  - scratch/institutional_summary.md (summary per institution)
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
WIKI_JSON = SCRATCH / "wikipedia_indologists_expanded.json"
INST_JSON = SCRATCH / "institutional_indologists.json"
CONF_JSON = ROOT / "site_data_scholars.json"
SUMMARY_MD = SCRATCH / "institutional_summary.md"


def normalize_name(name: str) -> str:
    return name.lower().replace("ё", "е").strip()


def main():
    # Load sources
    with open(WIKI_JSON, "r", encoding="utf-8") as f:
        wiki_data = json.load(f)
    with open(INST_JSON, "r", encoding="utf-8") as f:
        inst_data = json.load(f)
    with open(CONF_JSON, "r", encoding="utf-8") as f:
        conf_people = json.load(f)

    wiki_people = wiki_data.get("people", [])
    inst_people = inst_data.get("people", [])

    # Build lookup: normalized name → institution list
    name_to_institutions: dict[str, list[str]] = {}
    for p in inst_people:
        name = normalize_name(p["full_name"])
        inst = p.get("institution", "")
        if name not in name_to_institutions:
            name_to_institutions[name] = []
        if inst and inst not in name_to_institutions[name]:
            name_to_institutions[name].append(inst)

    # Build lookup from conference DB for non-Wikipedia people
    conf_names = set()
    for c in conf_people:
        full = c.get("full_name_ru", "") or c.get("name", "")
        if full:
            conf_names.add(normalize_name(full))

    # Update Wikipedia people with institution info from institutions data
    for w in wiki_people:
        name = normalize_name(w.get("full_name", ""))
        if name in name_to_institutions:
            w["institutions_from_db"] = name_to_institutions[name]

    # Find institutional indologists NOT in Wikipedia
    wiki_names = set()
    for w in wiki_people:
        wiki_names.add(normalize_name(w.get("full_name", "")))

    new_from_inst = []
    added_names = set()
    for p in inst_people:
        name = normalize_name(p["full_name"])
        if name not in wiki_names and name not in added_names:
            added_names.add(name)
            new_from_inst.append({
                "full_name": p["full_name"],
                "institution": p.get("institution", ""),
                "source": p.get("source", "institutional"),
                "total_talks": p.get("total_talks", 0),
                "zograf_talks": p.get("zograf_talks", 0),
                "roerich_talks": p.get("roerich_talks", 0),
            })

    # Also: find conference participants NOT in Wikipedia (they are indologists by definition)
    for c in conf_people:
        full = c.get("full_name_ru", "") or c.get("name", "")
        if not full:
            continue
        name = normalize_name(full)
        if name not in wiki_names and name not in added_names:
            # These are indologists who participated in conferences but aren't in Wikipedia
            pass  # They are already visible on the website; don't add duplicates

    print(f"Wikipedia people: {len(wiki_people)}")
    print(f"Institutional mappings added: {sum(1 for w in wiki_people if 'institutions_from_db' in w)}")
    print(f"New people from institutions (not in Wikipedia): {len(new_from_inst)}")
    for np in new_from_inst:
        print(f"  + {np['full_name']} @ {np['institution']} ({np['source']})")

    # Save updated Wikipedia list
    wiki_data["people"] = wiki_people
    wiki_data["new_from_institutions"] = new_from_inst
    wiki_data["total_people"] = len(wiki_people)
    wiki_data["total_new"] = len(new_from_inst)

    with open(WIKI_JSON, "w", encoding="utf-8") as f:
        json.dump(wiki_data, f, ensure_ascii=False, indent=2)

    # Generate summary markdown
    lines = []
    lines.append("# Индологи по учреждениям")
    lines.append("")
    lines.append("## Из базы конференций (270 участников)")
    lines.append("")
    lines.append("| Учреждение | Кол-во учёных |")
    lines.append("|-----------|-------------|")

    inst_counts: dict[str, int] = {}
    for p in inst_people:
        inst = p.get("institution", "")
        if inst:
            inst_counts[inst] = inst_counts.get(inst, 0) + 1
    for inst, count in sorted(inst_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {inst} | {count} |")

    lines.append("")
    lines.append("## Новые имена (из базы конференций, отсутствуют в Википедии)")
    lines.append("")
    if new_from_inst:
        lines.append("| ФИО | Учреждение | Докладов (З/Р/Всего) |")
        lines.append("|-----|-----------|----------------------|")
        for np in new_from_inst:
            z = np.get("zograf_talks", 0)
            r = np.get("roerich_talks", 0)
            t = np.get("total_talks", 0)
            lines.append(f"| {np['full_name']} | {np['institution']} | {z}/{r}/{t} |")
    else:
        lines.append("Нет новых имён — все участники конференций уже присутствуют в википедийных категориях.")

    lines.append("")
    lines.append("## Примечание")
    lines.append("")
    lines.append(
        "Институциональные сайты (ivran.ru, orientalstudies.ru) используют "
        "JavaScript-рендеринг страниц сотрудников, что делает невозможным "
        "простое извлечение данных через HTTP-запросы. "
        "Данные в этом файле основаны на:"
    )
    lines.append("- Аффилиациях из базы конференций (`site_data_scholars.json`)")
    lines.append("- Расширенном списке из Википедии (`wikipedia_indologists_expanded.json`)")

    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nSummary saved to: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
