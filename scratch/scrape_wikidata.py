"""Fetch Russian indologists from Wikidata.
Uses the Wikidata REST API since ru.wikipedia.org is blocked.
"""

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
OUTPUT = SCRATCH / "wikidata_indologists.json"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
USER_AGENT = "IndologyScholars/1.0"
DELAY = 0.3


def wd_api(params: dict) -> dict:
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_entity_data(qid: str) -> dict | None:
    """Fetch entity labels, claims from Wikidata."""
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "props": "labels|claims",
        "languages": "ru",
        "format": "json",
    }
    data = wd_api(params)
    entities = data.get("entities", {})
    return entities.get(qid)


def extract_person_info(entity: dict) -> dict | None:
    """Extract structured person info from Wikidata entity."""
    labels = entity.get("labels", {})
    label_ru = labels.get("ru", {}).get("value", "")
    label_en = labels.get("en", {}).get("value", "")
    label = label_ru or label_en
    if not label:
        return None

    claims = entity.get("claims", {})

    def claim_value(pid: str):
        vals = claims.get(pid, [])
        if vals:
            mainsnak = vals[0].get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            return datavalue.get("value", {})
        return {}

    def claim_q_labels(pid: str) -> list[str]:
        """Get Russian labels for Q-value claims like employer, alma mater."""
        vals = claims.get(pid, [])
        result = []
        for v in vals:
            q_val = v.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
            if q_val:
                label_data = get_entity_data(q_val)
                if label_data:
                    lab = label_data.get("labels", {}).get("ru", {}).get("value", "")
                    if lab:
                        result.append(lab)
        return result

    # Extract values
    birth_time = claim_value("P569").get("time", "")
    death_time = claim_value("P570").get("time", "")
    birth = int(birth_time[1:5]) if birth_time and birth_time[0] == "+" else None
    death = int(death_time[1:5]) if death_time and death_time[0] == "+" else None

    employers = claim_q_labels("P108")  # employer
    alma_maters = claim_q_labels("P69")  # educated at

    return {
        "wikidata_qid": entity.get("id", ""),
        "full_name": label,
        "birth_year": birth,
        "death_year": death,
        "employers": employers,
        "alma_maters": alma_maters,
    }


def main():
    print("=== Wikidata Indologist Search ===")

    # Step 1: Search for "индолог" in Russian Wikidata
    search_data = wd_api({
        "action": "wbsearchentities",
        "search": "индолог",
        "language": "ru",
        "format": "json",
        "type": "item",
        "limit": "50",
    })

    qids = []
    for r in search_data.get("search", []):
        desc = r.get("description", "").lower()
        # Filter: must be a person, not a concept
        if any(kw in desc for kw in ["человек", "учёный", "лингвист", "историк", "филолог",
                                       "переводчик", "ориенталист", "востоковед",
                                       "российск", "советск", "русск"]):
            qids.append(r["id"])

    print(f"Search hits filtered to people: {len(qids)}")
    for r in search_data.get("search", []):
        print(f"  {r['id']} | {r['label'][:40]} | {r.get('description', '')[:60]}")

    # Step 2: Fetch entity data for each QID
    people = []
    for i, qid in enumerate(qids):
        print(f"  [{i+1}/{len(qids)}] Fetching {qid} ...")
        entity = get_entity_data(qid)
        if entity:
            info = extract_person_info(entity)
            if info and info.get("full_name"):
                people.append(info)
        time.sleep(DELAY)

    # Deduplicate
    seen = set()
    unique = []
    for p in people:
        key = p["full_name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    output = {
        "description": "Russian indologists from Wikidata search",
        "total": len(unique),
        "people": sorted(unique, key=lambda p: p["full_name"].lower()),
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(unique)} people saved to {OUTPUT}")
    # Employer affiliations are written to the JSON output above; they are kept
    # out of this console summary so personal data is not echoed to logs.
    for p in unique:
        print(f"  {p['full_name']} | {p.get('birth_year','?')}-{p.get('death_year','?')}")


if __name__ == "__main__":
    main()
