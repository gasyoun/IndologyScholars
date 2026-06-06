"""Scrape institutional websites for Russian Indologists.

Strategy:
  1. Conference DB: extract all scholar→institution mappings from site_data_scholars.json
  2. Wikidata: SPARQL query for Russian/SSSR indologists with affiliations
  3. Combine with Wikipedia data
  4. Output: scratch/institutional_indologists.json

This avoids scraping JS-rendered institutional pages (ivran.ru etc.)
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
OUTPUT = SCRATCH / "institutional_indologists.json"
USER_AGENT = "IndologyScholars/1.0 (research; gasyoun@gmail.com)"
TIMEOUT = 30


# ── helpers ──────────────────────────────────────────────────────────

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Wikidata SPARQL ──────────────────────────────────────────────────

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

WD_QUERY = """
SELECT ?person ?personLabel ?birthYear ?deathYear ?employerLabel ?almaMaterLabel ?occupationLabel
WHERE {
  {
    # Occupation: Indologist (Q18539916)
    ?person wdt:P106 wd:Q18539916.
  } UNION {
    # Occupation: linguist-indologist via more specific query
    ?person wdt:P106/wdt:P279* wd:Q18539916.
  }

  # Country of citizenship: Russia (Q159), USSR (Q15180), Russian Empire (Q34266)
  { ?person wdt:P27 wd:Q159. }
  UNION { ?person wdt:P27 wd:Q15180. }
  UNION { ?person wdt:P27 wd:Q34266. }

  OPTIONAL { ?person wdt:P569 ?birthDate. BIND(YEAR(?birthDate) AS ?birthYear) }
  OPTIONAL { ?person wdt:P570 ?deathDate. BIND(YEAR(?deathDate) AS ?deathYear) }

  # Employer (workplace)
  OPTIONAL {
    ?person wdt:P108 ?employer.
    ?employer rdfs:label ?employerLabel.
    FILTER(LANG(?employerLabel) = "ru")
  }

  # Alma mater
  OPTIONAL {
    ?person wdt:P69 ?almaMater.
    ?almaMater rdfs:label ?almaMaterLabel.
    FILTER(LANG(?almaMaterLabel) = "ru")
  }

  # Occupation label
  OPTIONAL {
    ?person wdt:P106 ?occupation.
    ?occupation rdfs:label ?occupationLabel.
    FILTER(LANG(?occupationLabel) = "ru")
  }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". }
}
ORDER BY ?personLabel
"""


def scrape_wikidata() -> list[dict]:
    print("\n=== Wikidata SPARQL ===")
    url = WIKIDATA_SPARQL + "?" + urllib.parse.urlencode({"format": "json", "query": WD_QUERY})
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"  [!] SPARQL error: {e}")
        return []

    bindings = data.get("results", {}).get("bindings", [])
    print(f"  Results: {len(bindings)}")

    # Deduplicate by person URI
    seen = {}
    for b in bindings:
        person_uri = b.get("person", {}).get("value", "")
        if not person_uri:
            continue
        if person_uri not in seen:
            seen[person_uri] = {
                "wikidata_uri": person_uri,
                "wikidata_qid": person_uri.split("/")[-1],
                "label_ru": b.get("personLabel", {}).get("value", ""),
                "birth_year": b.get("birthYear", {}).get("value"),
                "death_year": b.get("deathYear", {}).get("value"),
                "employers": set(),
                "alma_maters": set(),
                "occupations": set(),
            }
        entry = seen[person_uri]
        if b.get("employerLabel", {}).get("value"):
            entry["employers"].add(b["employerLabel"]["value"])
        if b.get("almaMaterLabel", {}).get("value"):
            entry["alma_maters"].add(b["almaMaterLabel"]["value"])
        if b.get("occupationLabel", {}).get("value"):
            entry["occupations"].add(b["occupationLabel"]["value"])

    people = []
    for entry in seen.values():
        label = entry["label_ru"]
        if not label:
            continue

        birth = int(entry["birth_year"]) if entry["birth_year"] else None
        death = int(entry["death_year"]) if entry["death_year"] else None

        # Skip non-Russian-sounding names (filter out obviously non-RU labels)
        # Wikidata may return people with any country due to data issues
        if not re.search(r"[А-ЯЁа-яё]", label):
            continue

        employers = sorted(entry["employers"])[:3]
        occupations = sorted(entry["occupations"])[:3]

        people.append({
            "full_name": label,
            "wikidata_qid": entry["wikidata_qid"],
            "birth_year": birth,
            "death_year": death,
            "employers": employers,
            "alma_maters": sorted(entry["alma_maters"])[:3],
            "occupations": occupations,
            "source": "wikidata",
        })

    print(f"  Russian indologists: {len(people)}")
    return people


# ── Conference DB affiliations ────────────────────────────────────────

def extract_conf_affiliations() -> list[dict]:
    print("\n=== Conference DB affiliations ===")
    with open(ROOT / "site_data_scholars.json", "r", encoding="utf-8") as f:
        scholars = json.load(f)

    inst_people: dict[str, list[dict]] = {}

    for s in scholars:
        full_name = s.get("full_name_ru", "") or s.get("name", "")
        if not full_name:
            continue

        # Get affiliations from talks
        for t in s.get("talks", []):
            aff = t.get("affiliation_reported", "") or t.get("affiliation", "") or ""
            if not aff:
                continue
            # Normalize: ИВ РАН variants
            aff_norm = aff.strip()
            if "Институт востоковедения" in aff_norm or "ИВ РАН" in aff_norm:
                key = "ИВ РАН"
            elif "ИВР РАН" in aff_norm or "Институт восточных рукописей" in aff_norm:
                key = "ИВР РАН"
            elif "МАЭ" in aff_norm or "Кунсткамера" in aff_norm:
                key = "МАЭ РАН"
            elif "РГГУ" in aff_norm:
                key = "РГГУ"
            elif "ИСАА" in aff_norm:
                key = "ИСАА МГУ"
            elif "МГУ" in aff_norm and "ИСАА" not in aff_norm:
                key = "МГУ"
            elif "СПбГУ" in aff_norm or "ЛГУ" in aff_norm:
                key = "СПбГУ"
            elif "ВШЭ" in aff_norm:
                key = "ВШЭ"
            elif "МГИМО" in aff_norm:
                key = "МГИМО"
            elif "языкознания" in aff_norm.lower():
                key = "Институт языкознания РАН"
            else:
                continue  # skip unclear affiliations

            if key not in inst_people:
                inst_people[key] = {}
            inst_people[key][full_name] = {
                "total_talks": s.get("total_talks", 0),
                "zograf_talks": s.get("zograf_talks", 0),
                "roerich_talks": s.get("roerich_talks", 0),
            }

    result = []
    for inst, people in sorted(inst_people.items()):
        print(f"  {inst}: {len(people)} scholars")
        for name, info in people.items():
            result.append({
                "full_name": name,
                "institution": inst,
                "source": "conference_db",
                "total_talks": info["total_talks"],
                "zograf_talks": info["zograf_talks"],
                "roerich_talks": info["roerich_talks"],
            })

    return result


# ── main ───────────────────────────────────────────────────────────

def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)

    all_people = []

    # Wikidata
    wd_people = scrape_wikidata()
    for p in wd_people:
        for emp in p.get("employers", []):
            all_people.append({
                "full_name": p["full_name"],
                "institution": emp,
                "wikidata_qid": p.get("wikidata_qid", ""),
                "birth_year": p.get("birth_year"),
                "death_year": p.get("death_year"),
                "source": "wikidata",
            })

    # Conference DB
    conf_people = extract_conf_affiliations()
    all_people.extend(conf_people)

    # Deduplicate by name+institution
    seen = set()
    unique = []
    for p in all_people:
        key = (p["full_name"].lower().replace("ё", "е"), p["institution"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(p)

    output = {
        "description": "Indologists by institution (from Wikidata + Conference DB)",
        "total": len(unique),
        "people": sorted(unique, key=lambda p: (p["institution"], p["full_name"].lower())),
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary by institution
    print(f"\n=== Summary by institution ===")
    inst_counts: dict[str, int] = {}
    for p in unique:
        inst = p["institution"]
        inst_counts[inst] = inst_counts.get(inst, 0) + 1
    for inst, count in sorted(inst_counts.items(), key=lambda x: -x[1]):
        print(f"  {inst}: {count}")

    print(f"\nTotal unique: {len(unique)}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
