import json
import csv
from pathlib import Path
import sys
import re

# Add workspace directory to path to import helpers
sys.path.append(str(Path(__file__).resolve().parents[1]))
from publication_helpers import clean_person_urls, load_authority_overrides, load_site_data

def test_authority_coverage():
    authority = load_authority_overrides()
    data = load_site_data("site_data.json")
    
    scholars = data.get("scholars", [])
    persons_auth = authority.get("persons", {})
    
    coverage_rows = []
    review_queue = []
    
    total_scholars = len(scholars)
    scholars_with_any = 0
    total_orcid = 0
    total_wikidata = 0
    total_viaf = 0
    total_openalex = 0
    total_rinc = 0
    total_google_scholar = 0
    total_official_url = 0
    
    for s in scholars:
        pid = s["id"]
        dname = s.get("display_name") or s.get("name") or ""
        fullname_ru = s.get("full_name_ru") or s.get("original_fullname") or ""
        
        person_auth = persons_auth.get(pid, {})
        pref_latin = person_auth.get("preferred_latin_name", "")
        
        urls_dict = clean_person_urls(person_auth)
        
        has_orcid = 1 if "orcid" in urls_dict else 0
        has_wikidata = 1 if "wikidata" in urls_dict else 0
        has_viaf = 1 if "viaf" in urls_dict else 0
        has_openalex = 1 if "openalex" in urls_dict else 0
        has_rinc = 1 if "rinc_author_id" in urls_dict else 0
        has_google = 1 if "google_scholar" in urls_dict else 0
        has_official = 1 if "official_url" in urls_dict else 0
        
        has_any = 1 if (has_orcid or has_wikidata or has_viaf or has_openalex or has_rinc or has_google or has_official) else 0
        
        confidence = person_auth.get("confidence", "")
        checked_at = person_auth.get("checked_at", "")
        
        if has_any:
            scholars_with_any += 1
        total_orcid += has_orcid
        total_wikidata += has_wikidata
        total_viaf += has_viaf
        total_openalex += has_openalex
        total_rinc += has_rinc
        total_google_scholar += has_google
        total_official_url += has_official
        
        talks = s.get("total_talks", 0)
        
        coverage_rows.append({
            "person_id": pid,
            "display_name": dname,
            "full_name_ru": fullname_ru,
            "preferred_latin_name": pref_latin,
            "total_talks": talks,
            "has_orcid": has_orcid,
            "has_wikidata": has_wikidata,
            "has_viaf": has_viaf,
            "has_openalex": has_openalex,
            "has_rinc": has_rinc,
            "has_google_scholar": has_google,
            "has_official_url": has_official,
            "has_any_external_id": has_any,
            "authority_confidence": confidence,
            "checked_at": checked_at
        })
        
        # Determine review priority and reasons
        reasons = []
        priority = 99
        
        # Rule 1: many talks (e.g. >= 5 talks) and no external ID
        if talks >= 5 and not has_any:
            reasons.append("Many talks and no external ID")
            priority = min(priority, 1)
        elif talks > 0 and not has_any:
            reasons.append("Active scholar and no external ID")
            priority = min(priority, 2)
            
        # Rule 2: initials-only display name
        if re.search(r"\b[A-ZА-ЯЁ]\.", dname):
            reasons.append("Initials-only display name")
            priority = min(priority, 2)
            
        # Rule 3: missing preferred Latin name
        if not pref_latin:
            reasons.append("Missing preferred Latin name")
            priority = min(priority, 3)
            
        # Rule 4: existing ID but missing confidence/checked_at
        if has_any and (not confidence or not checked_at):
            reasons.append("Existing ID but missing confidence or checked_at")
            priority = min(priority, 4)
            
        if reasons:
            suggested_query = f"{fullname_ru or dname} индолог"
            review_queue.append({
                "priority_rank": priority,
                "person_id": pid,
                "display_name": dname,
                "full_name_ru": fullname_ru,
                "total_talks": talks,
                "reason": "; ".join(reasons),
                "suggested_query": suggested_query,
                "review_status": "todo"
            })
            
    review_queue.sort(key=lambda r: (r["priority_rank"], -r["total_talks"], r["display_name"]))
    
    print(f"Total scholars: {total_scholars}")
    print(f"Scholars with any ID: {scholars_with_any}")
    print(f"ORCID: {total_orcid}")
    print(f"Wikidata: {total_wikidata}")
    print(f"VIAF: {total_viaf}")
    print(f"OpenAlex: {total_openalex}")
    print(f"RINC: {total_rinc}")
    print(f"Google Scholar: {total_google_scholar}")
    print(f"Official URL: {total_official_url}")
    print(f"Queue size: {len(review_queue)}")
    
    if review_queue:
        print("\nTop 5 review queue items:")
        for item in review_queue[:5]:
            print(item)

if __name__ == "__main__":
    test_authority_coverage()
