"""Link roster participants to conference person_ids and enrich authority IDs.

Implements Phase 2 of docs/roster-merge-design.md. For each roster indologist
that the matcher maps to a Zograf/Roerich speaker, this:

  1. writes an audit table analytics_output/roster_participant_links.csv
     (roster name, matched person_id, score, Q-ID, birth-year comparison);
  2. injects the roster's Wikidata Q-ID into authority_ids.json under the
     matched person_id with confidence='candidate' (never 'confirmed', never
     clobbering an existing value) — the same rule as the OpenAlex injector.

Birth/death years are reported for human review only; they are NOT auto-applied
(the birth-year assertion path in tools/apply_birth_years.py owns that).

Usage:
  python tools/link_roster_participants.py [--dry-run]
"""

import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
sys.path.insert(0, str(SCRATCH))

import crossref_nonparticipants as cx  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

AUTHORITY_IDS = ROOT / "authority_ids.json"
LINKS_CSV = ROOT / "analytics_output" / "roster_participant_links.csv"
TODAY = date.today().isoformat()

FIELDNAMES = [
    "roster_full_name", "roster_wikidata_qid", "roster_birth_year",
    "matched_person_id", "matched_full_name_ru", "match_score",
    "conf_birth_year", "conf_existing_wikidata", "qid_action",
]


def best_match(person, conf):
    best_score, best = 0, None
    for c in conf:
        score = cx.match_score(person, c)
        if score > best_score:
            best_score, best = score, c
    return best_score, best


def main():
    dry_run = "--dry-run" in sys.argv

    wiki = cx.load_wiki_data()
    conf = cx.load_conf_data()

    authority = json.loads(AUTHORITY_IDS.read_text(encoding="utf-8"))
    persons = authority.setdefault("persons", {})

    rows = []
    injected = 0
    for person in wiki:
        score, match = best_match(person, conf)
        if score < 80 or not match:
            continue

        pid = match.get("id")
        qid = (person.get("wikidata_qid") or "").strip()
        existing = persons.get(pid, {})
        existing_wd = existing.get("wikidata") or match.get("wikidata") or ""

        action = "none"
        if qid and not existing_wd:
            action = "inject" if not dry_run else "would-inject"
            if not dry_run:
                rec = persons.setdefault(pid, {})
                rec["wikidata"] = qid
                rec.setdefault("confidence", "candidate")
                rec.setdefault("checked_at", TODAY)
                rec.setdefault("source", "roster_match")
                injected += 1
        elif qid and existing_wd and qid != existing_wd:
            action = "conflict"  # roster Q-ID disagrees with existing — review

        rows.append({
            "roster_full_name": person.get("full_name", ""),
            "roster_wikidata_qid": qid,
            "roster_birth_year": person.get("birth_year") or "",
            "matched_person_id": pid or "",
            "matched_full_name_ru": match.get("full_name_ru", ""),
            "match_score": score,
            "conf_birth_year": match.get("birth_year") or "",
            "conf_existing_wikidata": existing_wd,
            "qid_action": action,
        })

    rows.sort(key=lambda r: (-int(r["match_score"]), r["roster_full_name"]))

    LINKS_CSV.parent.mkdir(exist_ok=True)
    with LINKS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Participant links: {len(rows)}  ->  {LINKS_CSV}")
    conflicts = sum(1 for r in rows if r["qid_action"] == "conflict")
    pending = sum(1 for r in rows if r["qid_action"] in ("inject", "would-inject"))
    print(f"  Q-ID conflicts (review): {conflicts} | Q-ID to inject: {pending}")

    if dry_run:
        print("  [dry-run] authority_ids.json not modified")
        return

    if injected:
        with AUTHORITY_IDS.open("w", encoding="utf-8") as f:
            json.dump(authority, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Injected {injected} Wikidata Q-IDs into {AUTHORITY_IDS} "
              f"(confidence='candidate'; review before promoting).")
    else:
        print("No new Q-IDs to inject.")


if __name__ == "__main__":
    main()
