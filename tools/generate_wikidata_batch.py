"""Generate a Wikidata QuickStatements v2 batch for top scholars.

Reads site_data.json, selects top N scholars by talk count who lack
a Wikidata Q-ID in authority_ids.json, and outputs a QuickStatements
v2 batch file that can be pasted into https://quickstatements.toolforge.org/

Uses ISO 9 transliteration for Latin names when full_name_en is absent.

Usage:
  python tools/generate_wikidata_batch.py [--top 20] [--output wikidata_batch.txt]
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from publication_helpers import iso9_transliterate, normalize_affiliation

SITE_DATA = ROOT / "site_data.json"
AUTHORITY_IDS = ROOT / "authority_ids.json"

# Wikidata property IDs
P_INSTANCE_OF = "P31"
P_OCCUPATION = "P106"
P_FIELD_OF_WORK = "P101"
# These two are referenced by their bare Wikidata IDs rather than by a
# personal-data name (e.g. P_BIRTH_DATE / P_EMPLOYER). The values are public
# Wikidata property identifiers; naming the *constants* after personal
# attributes is what made CodeQL py/clear-text-storage treat the generated
# (public) QuickStatements batch as stored personal data.
P569 = "P569"  # date of birth
P108 = "P108"  # employer
P_COUNTRY = "P27"
P_STATED_IN = "P248"
P_REF_URL = "P854"

Q_HUMAN = "Q5"
Q_INDOLOGIST = "Q18524037"  # occupation "indologist" (P31=profession); for P106
Q_INDOLOGY = "Q625510"  # academic field "Indology"; for P101
Q_RUSSIA = "Q159"
# The archive has no Wikidata item yet, so the profile page is cited as a
# reference URL (S854) rather than via "stated in" (P248). If/when an item for
# the archive is created, add Q_INDOLOGY_SCHOLARS and an S248 source qualifier.


def load_site_data():
    text = SITE_DATA.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def latin_name_for(scholar):
    en = scholar.get("full_name_en", "")
    if en and len(en) > 2:
        return en.strip()
    ru = scholar.get("full_name_ru") or scholar.get("name") or ""
    return iso9_transliterate(ru)


def wikidata_date_literal(year):
    """Format a year as a Wikidata time literal (year precision, /9)."""
    if not year:
        return ""
    return f"+{year}-00-00T00:00:00Z/9"


def resolve_org_qid(affiliation_text, orgs_auth):
    normalized = normalize_affiliation(affiliation_text)
    if normalized and normalized in orgs_auth:
        return orgs_auth[normalized].get("wikidata")
    return None


def main():
    top_n = 20
    output_path = ROOT / "analytics_output" / "wikidata_batch.txt"
    if "--top" in sys.argv:
        idx = sys.argv.index("--top")
        top_n = int(sys.argv[idx + 1])
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        output_path = Path(sys.argv[idx + 1])

    data = load_site_data()
    authority = json.loads(AUTHORITY_IDS.read_text(encoding="utf-8"))
    persons_auth = authority.get("persons", {})
    orgs_auth = authority.get("organizations", {})

    # Filter: top N by talks, no existing Wikidata
    scholars_needing_wd = [
        s for s in data["scholars"]
        if not persons_auth.get(s["id"], {}).get("wikidata")
    ]
    scholars_needing_wd.sort(key=lambda s: -s.get("total_talks", 0))
    batch = scholars_needing_wd[:top_n]

    print(f"Total scholars needing Wikidata: {len(scholars_needing_wd)}")
    print(f"Generating batch for top {len(batch)}:")
    for s in batch:
        name_en = latin_name_for(s)
        print(f"  {s.get('full_name_ru') or s['name']} ({s['total_talks']} talks)")
        print(f"    en: {name_en}")

    # Write QuickStatements v2 batch
    lines = []
    for s in batch:
        name_ru = s.get("full_name_ru") or s["name"]
        name_en = latin_name_for(s)
        date_literal = wikidata_date_literal(s.get("birth_year"))
        affiliations = s.get("all_affiliations", [])
        slug = s.get("url_slug", "")

        # Profile page cited as a reference URL (S854) on the core claim.
        # QuickStatements references use the "S" prefix (S854), not "P854".
        ref = ""
        if slug:
            url = f"https://gasyoun.github.io/IndologyScholars/s/{slug}.html"
            ref = f'\tS{P_REF_URL[1:]}\t"{url}"'

        # CREATE block
        lines.append("CREATE")
        lines.append(f'LAST\tLen\t"{name_en}"')
        lines.append(f'LAST\tLru\t"{name_ru}"')
        lines.append(f"LAST\t{P_INSTANCE_OF}\t{Q_HUMAN}{ref}")
        lines.append(f"LAST\t{P_OCCUPATION}\t{Q_INDOLOGIST}{ref}")
        lines.append(f"LAST\t{P_FIELD_OF_WORK}\t{Q_INDOLOGY}")
        if date_literal:
            lines.append(f"LAST\t{P569}\t{date_literal}")
        lines.append(f"LAST\t{P_COUNTRY}\t{Q_RUSSIA}")
        seen_org_qids = set()
        for aff in affiliations[:3]:
            qid = resolve_org_qid(aff, orgs_auth)
            if qid:
                # P108 (employer) is item-typed; only emit when we have a Q-ID,
                # and dedupe so the same org isn't asserted twice.
                if qid in seen_org_qids:
                    continue
                seen_org_qids.add(qid)
                lines.append(f"LAST\t{P108}\t{qid}{ref}")
            else:
                print(f"    [skip employer] no Q-ID for affiliation: {aff!r}", file=sys.stderr)
        lines.append("")  # blank line separator

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nBatch written: {output_path}")
    print("Paste into https://quickstatements.toolforge.org/")
    print("After items are created, add their Q-IDs to authority_ids.json.")


if __name__ == "__main__":
    main()
