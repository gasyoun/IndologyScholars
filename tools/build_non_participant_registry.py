"""Seed curation/non_participant_indologists.csv from the scratch/ roster.

Implements Phase 1 of docs/roster-merge-design.md. Classifies every roster
indologist as participant / non-participant using the existing matcher
(scratch/crossref_nonparticipants.py), and writes the non-participants to a
curated CSV that becomes the source of truth for the registry page.

The write is NON-DESTRUCTIVE: existing rows (keyed by registry_id) are never
modified, only new registry_ids are appended. Human curation of existing rows
is preserved across re-runs (mirrors the roster's non-destructive merge).

registry_id is a deterministic hash of the normalized name + birth year, so it
is stable across rebuilds and never collides with the conference person_id
namespace (PERS_*).

Usage:
  python tools/build_non_participant_registry.py [--dry-run]
"""

import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
sys.path.insert(0, str(SCRATCH))
sys.path.insert(0, str(ROOT))

import crossref_nonparticipants as cx  # noqa: E402

try:
    from publication_helpers import iso9_transliterate
except Exception:  # pragma: no cover - transliteration is best-effort
    def iso9_transliterate(s):
        return ""

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_CSV = ROOT / "curation" / "non_participant_indologists.csv"

FIELDNAMES = [
    "registry_id", "full_name_ru", "full_name_en", "birth_year", "death_year",
    "field", "role", "affiliation", "alma_mater", "degree",
    "wikidata_qid", "orcid", "source_url", "status", "note",
]


def registry_id_for(person):
    surname = cx.normalize(person.get("surname", ""))
    given = cx.normalize(person.get("given_name", ""))
    birth = str(person.get("birth_year") or "")
    key = f"{surname}|{given}|{birth}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"RIND_{digest}"


def latin_name_for(person):
    full = (person.get("full_name") or "").strip()
    if not full:
        return ""
    try:
        return iso9_transliterate(full)
    except Exception:
        return ""


def build_row(person):
    qid = (person.get("wikidata_qid") or "").strip()
    # A Wikidata item is a citable source -> the row may be marked verified.
    if qid:
        source_url = f"https://www.wikidata.org/wiki/{qid}"
        status = "verified"
    else:
        source_url = ""
        status = "candidate"  # needs a human-supplied source before publishing
    return {
        "registry_id": registry_id_for(person),
        "full_name_ru": (person.get("full_name") or "").strip(),
        "full_name_en": latin_name_for(person),
        "birth_year": person.get("birth_year") or "",
        "death_year": person.get("death_year") or "",
        "field": (person.get("scientific_field") or "").strip(),
        "role": (person.get("role") or "").strip(),
        "affiliation": (person.get("workplace") or "").strip(),
        "alma_mater": (person.get("alma_mater") or "").strip(),
        "degree": (person.get("degree") or "").strip(),
        "wikidata_qid": qid,
        "orcid": "",
        "source_url": source_url,
        "status": status,
        "note": "",
    }


def main():
    dry_run = "--dry-run" in sys.argv

    wiki = cx.load_wiki_data()
    conf = cx.load_conf_data()

    non_participants = []
    seen_ids = set()
    participants = 0
    for person in wiki:
        is_participant, _ = cx.classify_participation(person, conf)
        if is_participant:
            participants += 1
            continue
        if not (person.get("full_name") or "").strip():
            continue
        row = build_row(person)
        if row["registry_id"] in seen_ids:
            continue  # collapse exact duplicates within the roster
        seen_ids.add(row["registry_id"])
        non_participants.append(row)

    print(f"Roster people: {len(wiki)} | participants: {participants} | "
          f"non-participants: {len(non_participants)}")

    # Non-destructive merge with any existing curated file.
    existing_rows = []
    existing_ids = set()
    if OUTPUT_CSV.exists():
        with OUTPUT_CSV.open(encoding="utf-8", newline="") as f:
            existing_rows = list(csv.DictReader(f))
        existing_ids = {r["registry_id"] for r in existing_rows}

    new_rows = [r for r in non_participants if r["registry_id"] not in existing_ids]
    print(f"Existing curated rows: {len(existing_rows)} | new to append: {len(new_rows)}")

    if dry_run:
        for r in new_rows[:10]:
            print(f"  [DRY] {r['registry_id']} {r['full_name_ru']} "
                  f"({r['birth_year']}-{r['death_year']}) status={r['status']}")
        return

    merged = existing_rows + new_rows
    merged.sort(key=lambda r: cx.normalize(r.get("full_name_ru", "")))

    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in merged:
            writer.writerow({k: r.get(k, "") for k in FIELDNAMES})

    print(f"Wrote {len(merged)} rows -> {OUTPUT_CSV}")
    verified = sum(1 for r in merged if r.get("status") == "verified")
    print(f"  verified (have source): {verified} | "
          f"candidate (need source): {len(merged) - verified}")


if __name__ == "__main__":
    main()
