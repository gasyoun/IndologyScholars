"""
One-shot script: populate preferred_latin_name in authority_ids.json for the
overlap cohort, regenerate site_data.json, record slug changes, and write
slug_redirects.json so generate_scholars_pages.py can emit redirect pages.

Run once: python apply_preferred_latin_names.py
"""

import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Preferred Latin names — curated mapping (person_id → "Firstname Lastname")
# Rules:
#   - Western order: FirstName LastName (no patronymic)
#   - Spelling matches how the scholar signs English-language publications
#   - Macron characters stripped for URL compatibility in the slugifier
# ---------------------------------------------------------------------------
PREFERRED = {
    "PERS_05d56645": "Alexander Babin",         # Бабин Александр Николаевич
    "PERS_0665f215": "Vladimir Shokhin",         # Шохин Владимир Кириллович
    "PERS_0e0a154e": "Lev Titlin",               # Титлин Лев Игоревич
    "PERS_11da326d": "Sergey Tavastsherna",      # Тавастшерна Сергей Сергеевич
    "PERS_12125da9": "Victoria Lysenko",         # Лысенко Виктория Георгиевна
    "PERS_1c6fcce5": "Elizaveta Kuzina",         # Кузина Елизавета Олеговна
    "PERS_1fa7cc0c": "Alexander Dubyansky",      # Дубянский Александр Михайлович
    "PERS_36dabb79": "Anastasia Guriya",         # Гурия Анастасия Георгиевна
    "PERS_3b196639": "Nikolai Gordiichuk",       # Гордийчук Николай Валентинович
    "PERS_3c202afd": "Rada Krapivina",           # Крапивина Рада Нельсоновна
    "PERS_40862f5e": "Natalia Korneeva",         # Корнеева Наталья Афанасьевна
    "PERS_41d6aa73": "Daria Vorobyeva",          # Воробьева Дарья Николаевна
    "PERS_50d73711": "Anna Smirnitskaya",        # Смирнитская Анна Александровна
    "PERS_5228da95": "Victoria Vertogradova",    # В. В. Вертоградова
    "PERS_58b39545": "Evgenia Renkovskaya",      # Ренковская Евгения Алексеевна
    "PERS_61202bf3": "Yulia Alikhanova",         # Ю. М. Алиханова (Юлия Михайловна, †)
    "PERS_6ae5c779": "Anastasia Fiveyskaya",     # Фивейская Анастасия Васильевна
    "PERS_72506535": "Anastasia Krylova",        # Крылова Анастасия Сергеевна
    "PERS_8516d1e4": "Marcis Gasuns",            # Гасунс Марцис Юрьевич (Mārcis Gasūns)
    "PERS_8e117242": "Ekaterina Yuditskaya",         # Е. А. Юдицкая (Екатерина Алексеевна)
    "PERS_92868e4f": "Dmitry Zhutaev",           # Жутаев Дмитрий Игоревич
    "PERS_93e2effb": "Dmitry Komissarov",        # Комиссаров Дмитрий Алексеевич
    "PERS_9f398436": "Leonid Kulikov",           # Куликов Леонид Игоревич
    "PERS_c52dfaa0": "Sofia Tsvetkova",          # С. О. Цветкова
    "PERS_cdbd7a15": "Sergey Kullanda",          # C. В. Кулланда
    "PERS_cfb92c5f": "Evgeny Ulansky",           # Уланский Евгений Александрович
    "PERS_d98da899": "Svetlana Ryzhakova",       # Рыжакова Светлана Игоревна
    "PERS_e1dd6b3e": "Natalia Lidova",           # Лидова Наталья Ростиславовна
    "PERS_e31ca12d": "Olga Vecherina",           # Вечерина Ольга Павловна
    "PERS_ebb6d156": "Anastasia Lozhkina",       # А. В. Ложкина
    "PERS_efc88709": "Natalia Kanaeva",          # Канаева Наталия Алексеевна
    "PERS_f074f69f": "Natalia Alexandrova",      # Александрова Наталия Владимировна
    "PERS_f2fef030": "Areg Mekhakyan",           # Мехакян Арег Гайкович
    "PERS_f5b8b340": "Alexey Vigasin",           # Вигасин Алексей Алексеевич
    # Skipped (initials-only, no confirmed first name):
    #   PERS_61202bf3 → now added as Yulia Alikhanova
    #   PERS_e72d4c09 Е. Д. Огнева  — first name unconfirmed
    #   PERS_9ad66151 Д. Н. Лелюхин — first name unconfirmed
    #   PERS_df6e2007 А. А. Мехакян — likely same person as Арег Гайкович; skip
}

AUTHORITY_PATH = Path("authority_ids.json")
SLUG_REDIRECTS_PATH = Path("slug_redirects.json")
SITE_DATA_PATH = Path("site_data.json")


def main():
    # 1. Capture current slugs before any change
    with SITE_DATA_PATH.open(encoding="utf-8") as f:
        old_data = json.load(f)
    old_slugs = {s["id"]: s["url_slug"] for s in old_data["scholars"]}

    # 2. Update authority_ids.json
    with AUTHORITY_PATH.open(encoding="utf-8") as f:
        auth = json.load(f)
    persons = auth.setdefault("persons", {})
    for pid, name in PREFERRED.items():
        entry = persons.setdefault(pid, {})
        entry["preferred_latin_name"] = name
    with AUTHORITY_PATH.open("w", encoding="utf-8") as f:
        json.dump(auth, f, ensure_ascii=False, indent=2)
    print(f"Updated authority_ids.json: {len(PREFERRED)} preferred_latin_name entries added.")

    # 3. Regenerate site_data.json
    result = subprocess.run(
        [sys.executable, "generate_site_data.py"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print("ERROR running generate_site_data.py:")
        print(result.stderr)
        sys.exit(1)
    print(result.stdout.strip())

    # 4. Load new slugs and find changes
    with SITE_DATA_PATH.open(encoding="utf-8") as f:
        new_data = json.load(f)
    new_slugs = {s["id"]: s["url_slug"] for s in new_data["scholars"]}

    changed = {
        pid: (old_slugs[pid], new_slugs[pid])
        for pid in old_slugs
        if pid in new_slugs and old_slugs[pid] != new_slugs[pid]
    }
    print(f"\nSlug changes ({len(changed)}):")
    for pid, (old, new) in sorted(changed.items(), key=lambda x: x[1][0]):
        print(f"  {old:40s} → {new}")

    # 5. Update slug_redirects.json (old_slug → person_id)
    if SLUG_REDIRECTS_PATH.exists():
        with SLUG_REDIRECTS_PATH.open(encoding="utf-8") as f:
            redirects = json.load(f)
    else:
        redirects = {}
    for pid, (old_slug, new_slug) in changed.items():
        if old_slug and old_slug != new_slug:
            redirects[old_slug] = pid
    with SLUG_REDIRECTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(redirects, f, ensure_ascii=False, indent=2)
    print(f"\nslug_redirects.json: {len(redirects)} total entries.")


if __name__ == "__main__":
    main()
