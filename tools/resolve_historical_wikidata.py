"""Resolve biographical facts for the historical prosopography tranche from Wikidata.

H484 (Phase 2). Fills ``curation/historical_persons.csv`` -- the *source of truth*
for indologists who never presented at the Zograf/Roerich readings and therefore
never enter ``person`` through ``get_or_create_person``.

Reuse (per the repo's check-prior-art rule)
-------------------------------------------
* HTTP + on-disk cache + retry + UTF-8 console: ``scratch/scrape_common.py``
  (same ``sys.path.insert(SCRATCH)`` idiom as ``tools/build_non_participant_registry.py``).
* Wikidata time-literal parsing: ``scratch/wikidata_enrich.py._year`` (handles BCE).

Only the rank filter below is new. ``wikidata_enrich.parse_entity_dates`` takes the
*first* claim regardless of rank, which silently prefers a deprecated statement when
one is listed first. For 18th–19th c. figures Wikidata routinely carries paired
Julian/Gregorian birth statements (Петров: 25 June / 7 July 1814); at year
granularity those agree, but a deprecated *wrong-year* claim would not. So we drop
deprecated claims and prefer ``preferred`` rank.

Why the QIDs are pinned rather than searched
--------------------------------------------
``wbsearchentities`` ranks by index, not identity. Two failures were observed while
assembling this roster:

* "Герасим Степанович Лебедев" returns ``Q19147816`` -- a *book about* Lebedev --
  next to the person ``Q2028881``;
* Павел Яковлевич Петров and Семён Иванович Тюляев return **no hit at all**, though
  both have items (``Q4360844`` / ``Q109485804``, reached via the ru.wikipedia sitelink).

A search-at-build-time resolver would therefore be both wrong and unstable. Every QID
below was verified by hand against the entity's label + description and is pinned.
This script fetches facts for pinned identities; it never guesses one.

Network: Wikidata REST answered from the authoring host on 10-07-2026, though
``.ai_state.md`` records it as timing out. Runs are idempotent and cached; on a fetch
failure the row is reported and the existing CSV value is preserved, never blanked.

Usage::

    python tools/resolve_historical_wikidata.py            # refresh the CSV
    python tools/resolve_historical_wikidata.py --dry-run  # print, write nothing
"""
from __future__ import annotations

import argparse
import csv
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
sys.path.insert(0, str(SCRATCH))
sys.path.insert(0, str(ROOT))

import scrape_common as sc  # noqa: E402  (needs the sys.path above)
from wikidata_enrich import _year  # noqa: E402

OUT_CSV = ROOT / "curation" / "historical_persons.csv"
ROLES_CSV = ROOT / "curation" / "historical_person_roles.csv"

ENTITYDATA = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
WIKIDATA_PAGE = "https://www.wikidata.org/wiki/{qid}"
API = "https://www.wikidata.org/w/api.php"

P_BIRTH, P_DEATH, P_OCCUPATION = "P569", "P570", "P106"
P_EMPLOYER, P_EDUCATED_AT = "P108", "P69"
P_START, P_END = "P580", "P582"

ROLE_FIELDNAMES = [
    "wikidata_qid",
    "display_name",
    "role",
    "organization_ru",
    "organization_qid",
    "from_year",
    "to_year",
    "source_url",
]

FIELDNAMES = [
    "registry_id",
    "display_name",
    "full_name_ru",
    "full_name_en",
    "birth_year",
    "death_year",
    "wikidata_qid",
    "source_url",
    "ruwiki_url",
    "description_ru",
    "occupations_ru",
    "status",
    "note",
]

# (surname, first, patronymic, QID, registry_id or "")
#
# display_name is built surname-first on purpose. ``pipeline.biography`` derives the
# person key from name order: canonical_person_key("Минаев Иван Павлович") -> "минаев и п",
# but canonical_person_key("Иван Павлович Минаев") -> "иван м п". The RIND_ registry
# stores given-name-first, so migrating those rows verbatim would mint historical persons
# into a bogus key namespace -- and they would never merge with the same human if he ever
# turned up as a presenter. Surname-first keeps one spine (roadmap R5).
#
# registry_id links back to curation/non_participant_indologists.csv: those 17 rows are
# *migrated*, not duplicated (the registry page filters them out by registry_id).
ROSTER = [
    ("Сталь-фон-Гольштейн", "Александр", "Августович", "Q565707", "RIND_5ac74908"),
    ("Мерварт", "Александр", "Михайлович", "Q3523976", "RIND_1777ba54"),
    ("Баранников", "Алексей", "Петрович", "Q4077715", "RIND_bae26e83"),
    ("Востриков", "Андрей", "Иванович", "Q502136", "RIND_9628ede6"),
    ("Смирнов", "Борис", "Леонидович", "Q4424594", "RIND_62e1c507"),
    ("Бродов", "Василий", "Васильевич", "Q15064697", "RIND_12e52989"),
    ("Кальянов", "Владимир", "Иванович", "Q4210614", "RIND_8e141a37"),
    ("Минаев", "Иван", "Павлович", "Q171275", "RIND_1672f0cd"),
    ("Серебряков", "Игорь", "Дмитриевич", "Q658050", "RIND_0606e272"),
    # Q12486524 (which non_participant_indologists.csv carries, marked `verified`) is the
    # WRONG PERSON -- a "scholar of Indonesian studies" with no dates at all. The indologist
    # is Q19933264, reachable only via the ru.wikipedia sitelink; wbsearchentities returns
    # nothing for either spelling of her name. Corrected here, 10-07-2026.
    ("Антонова", "Кока", "Александровна", "Q19933264", "RIND_739b0ae4"),
    ("Гусева", "Наталья", "Романовна", "Q4152723", "RIND_53cce0ec"),
    ("Бётлингк", "Оттон", "Николаевич", "Q76423", "RIND_034456a2"),
    ("Ульяновский", "Ростислав", "Александрович", "Q111784145", "RIND_759d8e52"),
    ("Тюляев", "Семён", "Иванович", "Q109485804", "RIND_514f0ef6"),
    ("Ольденбург", "Сергей", "Фёдорович", "Q171848", "RIND_da3e06ff"),
    ("Щербатской", "Фёдор", "Ипполитович", "Q1341741", "RIND_1058b44f"),
    ("Макаев", "Энвер", "Ахмедович", "Q4275228", "RIND_c2d6a988"),
    # Not in the RIND_ registry: the first-rank figures named by the H484 target list,
    # plus four whose Sanskrit/Vedic work is attested in the entity description.
    ("Лебедев", "Герасим", "Степанович", "Q2028881", ""),
    ("Ленц", "Роберт", "Христианович", "Q15134863", ""),
    ("Коссович", "Каэтан", "Андреевич", "Q3920365", ""),
    ("Петров", "Павел", "Яковлевич", "Q4360844", ""),
    ("Обермиллер", "Евгений", "Евгеньевич", "Q1633918", ""),
    ("Рерих", "Юрий", "Николаевич", "Q358957", ""),
    ("Васильев", "Василий", "Павлович", "Q721077", ""),
    ("Миллер", "Всеволод", "Фёдорович", "Q235796", ""),
    ("Овсянико-Куликовский", "Дмитрий", "Николаевич", "Q3712323", ""),
]


def _ranked_claims(entity, prop):
    """Preferred rank if any, else normal rank. Deprecated statements are dropped."""
    claims = entity.get("claims", {}).get(prop, [])
    live = [c for c in claims if c.get("rank") != "deprecated"]
    return [c for c in live if c.get("rank") == "preferred"] or live


def _claim_year(entity, prop):
    """(chosen_year, [other_years]) -- never silently arbitrate a real disagreement.

    Wikidata routinely carries several date statements per person. Two shapes occur:

    * **Agreeing at year granularity** -- a day-precision Julian date beside a
      year-precision Gregorian one (Коссович P570: 1883-01-26 and 1883). Harmless.
    * **Disagreeing at year granularity** -- Коссович P569 has *two normal-rank* claims,
      1814-05-02 (day precision) and 1815 (year precision). Rank cannot break this tie,
      and picking the first is arbitrary. We choose the most specific claim and return
      the rest, so the caller can mark the row disputed rather than pretend certainty.

    Selection: preferred rank wins; otherwise the highest precision; ties keep source order.
    """
    candidates = []
    for claim in _ranked_claims(entity, prop):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue  # 'unknown value' / 'no value' assert ignorance, not a date
        value = snak["datavalue"]["value"]
        year = _year(value.get("time", ""))
        if year is not None:
            candidates.append((claim.get("rank") == "preferred", value.get("precision", 0), year))
    if not candidates:
        return None, []

    best = max(candidates, key=lambda c: (c[0], c[1]))
    chosen = best[2]
    others = sorted({y for _, _, y in candidates} - {chosen})
    return chosen, others


def _occupation_qids(entity):
    out = []
    for claim in _ranked_claims(entity, P_OCCUPATION):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            out.append(snak["datavalue"]["value"]["id"])
    return out


def _qualifier_year(claim, prop):
    for qual in claim.get("qualifiers", {}).get(prop, []):
        if qual.get("snaktype") == "value":
            year = _year(qual["datavalue"]["value"].get("time", ""))
            if year is not None:
                return year
    return None


def _institutional_claims(entity):
    """[(role, org_qid, from_year, to_year)] from P108 (employer) and P69 (educated at).

    Phase 1 left ``person_role.organization_id`` NULL because affiliation strings were never
    reconciled to ``organization``; we keep that, carrying the org's Wikidata label in notes.
    Dates come from the P580/P582 qualifiers when present -- most 19th-c. statements have none,
    and a missing qualifier stays NULL rather than being guessed from the lifespan.
    """
    out = []
    for prop, role in ((P_EMPLOYER, "affiliation"), (P_EDUCATED_AT, "education")):
        for claim in _ranked_claims(entity, prop):
            snak = claim.get("mainsnak", {})
            if snak.get("snaktype") != "value":
                continue
            out.append(
                (
                    role,
                    snak["datavalue"]["value"]["id"],
                    _qualifier_year(claim, P_START),
                    _qualifier_year(claim, P_END),
                )
            )
    return out


def fetch_labels(qids, *, use_cache=True):
    """Batched wbgetentities call for occupation labels (50 ids per request)."""
    labels, qids = {}, sorted(set(qids))
    for i in range(0, len(qids), 50):
        chunk = qids[i : i + 50]
        data = sc.api_get(
            API,
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": "labels",
                "languages": "ru|en",
                "format": "json",
            },
            cache=use_cache,
        )
        if not data:
            continue
        for qid, ent in data.get("entities", {}).items():
            lab = ent.get("labels", {})
            labels[qid] = (lab.get("ru") or lab.get("en") or {}).get("value", qid)
    return labels


def fetch_person(qid, *, use_cache=True):
    doc = sc.get_json(ENTITYDATA.format(qid=qid), cache=use_cache, verbose=True)
    if not doc:
        return None
    entity = doc.get("entities", {}).get(qid, {})
    if not entity:
        return None
    labels = entity.get("labels", {})
    descriptions = entity.get("descriptions", {})
    # Special:EntityData sitelinks carry `title`, never `url` (that needs ?props=sitelinks/urls).
    ruwiki_title = entity.get("sitelinks", {}).get("ruwiki", {}).get("title", "")
    ruwiki = (
        "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(ruwiki_title.replace(" ", "_"))
        if ruwiki_title
        else ""
    )
    birth_year, birth_alt = _claim_year(entity, P_BIRTH)
    death_year, death_alt = _claim_year(entity, P_DEATH)
    return {
        "label_en": (labels.get("en") or {}).get("value", ""),
        "description_ru": (descriptions.get("ru") or descriptions.get("en") or {}).get("value", ""),
        "birth_year": birth_year,
        "death_year": death_year,
        "birth_alt": birth_alt,
        "death_alt": death_alt,
        "occupation_qids": _occupation_qids(entity),
        "roles": _institutional_claims(entity),
        "ruwiki_url": ruwiki,
    }


def load_existing():
    if not OUT_CSV.exists():
        return {}
    with OUT_CSV.open(encoding="utf-8", newline="") as fh:
        return {r["wikidata_qid"]: r for r in csv.DictReader(fh)}


def main():
    sc.setup_utf8()
    ap = argparse.ArgumentParser(description="Refresh curation/historical_persons.csv")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    ap.add_argument("--no-cache", action="store_true", help="bypass the scratch HTTP cache")
    args = ap.parse_args()
    use_cache = not args.no_cache

    existing = load_existing()
    rows, failures = [], []

    print("=== Historical prosopography: Wikidata resolution ===")
    for surname, first, patronymic, qid, registry_id in ROSTER:
        info = fetch_person(qid, use_cache=use_cache)
        display_name = f"{surname} {first} {patronymic}".strip()
        if not info:
            failures.append((qid, display_name))
            if qid in existing:
                rows.append(existing[qid])  # preserve a curated row, never blank it
            continue

        disputes = []
        if info["birth_alt"]:
            disputes.append(
                f"birth_year disputed on Wikidata: chose {info['birth_year']}, "
                f"also attested {', '.join(map(str, info['birth_alt']))}"
            )
        if info["death_alt"]:
            disputes.append(
                f"death_year disputed on Wikidata: chose {info['death_year']}, "
                f"also attested {', '.join(map(str, info['death_alt']))}"
            )

        if not info["death_year"]:
            status = "needs_death_year"
        elif disputes:
            status = "disputed"
        else:
            status = "verified"

        row = {
            "registry_id": registry_id,
            "display_name": display_name,
            "full_name_ru": display_name,
            "full_name_en": info["label_en"],
            "birth_year": info["birth_year"] or "",
            "death_year": info["death_year"] or "",
            "wikidata_qid": qid,
            "source_url": WIKIDATA_PAGE.format(qid=qid),
            "ruwiki_url": info["ruwiki_url"],
            "description_ru": info["description_ru"],
            "occupations_ru": "",
            "status": status,
            "note": "; ".join(disputes),
        }
        row["_occ"] = info["occupation_qids"]
        row["_roles"] = info["roles"]
        rows.append(row)
        flag = "  <-- " + row["note"] if disputes else ""
        print(
            f"  {qid:11} {display_name[:34]:36} "
            f"b={row['birth_year'] or '????'} d={row['death_year'] or '????'}  {status}{flag}"
        )

    needed = [q for r in rows for q in r.get("_occ", [])]
    needed += [org for r in rows for _, org, _, _ in r.get("_roles", [])]
    labels = fetch_labels(needed, use_cache=use_cache)

    role_rows = []
    for row in rows:
        occ = row.pop("_occ", [])
        if occ:
            row["occupations_ru"] = "; ".join(labels.get(q, q) for q in occ)
        for role, org_qid, from_year, to_year in row.pop("_roles", []):
            role_rows.append(
                {
                    "wikidata_qid": row["wikidata_qid"],
                    "display_name": row["display_name"],
                    "role": role,
                    "organization_ru": labels.get(org_qid, org_qid),
                    "organization_qid": org_qid,
                    "from_year": from_year or "",
                    "to_year": to_year or "",
                    "source_url": row["source_url"],
                }
            )

    missing_death = [r["display_name"] for r in rows if not r["death_year"]]
    if missing_death:
        print(f"\n  WARNING: no death_year for {len(missing_death)}: {', '.join(missing_death)}")
        print("  For a figure of this period an empty death_year is a data defect")
        print("  (roadmap risk P3), not an unknown. The seeder refuses such rows.")
    if failures:
        print(f"\n  WARNING: {len(failures)} unreachable Q-ID(s); existing values preserved:")
        for qid, name in failures:
            print(f"    {qid} {name}")

    if args.dry_run:
        print(f"\n--dry-run: {len(rows)} rows, {len(role_rows)} roles resolved, nothing written.")
        return 0

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (str(r["birth_year"] or "9999"), r["display_name"])):
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    print(f"\nWrote {len(rows)} rows -> {OUT_CSV.relative_to(ROOT)}")

    with ROLES_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ROLE_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in sorted(role_rows, key=lambda r: (r["display_name"], r["role"], r["organization_ru"])):
            writer.writerow(row)
    dated = sum(1 for r in role_rows if r["from_year"] or r["to_year"])
    print(f"Wrote {len(role_rows)} roles ({dated} with a date qualifier) -> {ROLES_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
