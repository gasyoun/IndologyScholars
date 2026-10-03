"""Audit recurring person-identity gaps instead of fixing one profile at a time.

Outputs:
- analytics_output/identity_alias_candidates.csv
- analytics_output/birth_year_gap_audit.csv
- analytics_output/identity_trend_summary.json
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_and_populate_db import normalize_person_name  # noqa: E402

SITE_DATA = ROOT / "site_data.json"
ALIASES = ROOT / "curation" / "person_aliases.csv"
ANALYTICS = ROOT / "analytics_output"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_site_data() -> dict:
    return json.loads(SITE_DATA.read_text(encoding="utf-8"))


def key_parts(norm_key: str) -> tuple[str, list[str]]:
    parts = [part for part in norm_key.split() if part]
    if not parts:
        return "", []
    return parts[0], parts[1:]


def scholar_display(scholar: dict) -> str:
    return scholar.get("full_name_ru") or scholar.get("original_fullname") or scholar.get("name") or ""


def scholar_key(scholar: dict) -> str:
    return normalize_person_name(scholar_display(scholar))


def load_curated_aliases() -> dict[tuple[str, str], dict]:
    accepted = {}
    for row in read_csv(ALIASES):
        status = (row.get("status") or "").strip().lower()
        if status not in {"accepted", "confirmed", "manual", "high"}:
            continue
        alias_key = normalize_person_name(row.get("alias_name") or "")
        target_key = normalize_person_name(row.get("target_name") or "")
        if alias_key and target_key:
            accepted[(alias_key, target_key)] = row
    return accepted


def match_rule(alias_initials: list[str], target_initials: list[str]) -> tuple[str, int]:
    if not alias_initials or not target_initials:
        return "", 0
    if alias_initials == target_initials[: len(alias_initials)]:
        return "initial_prefix", 95 if len(alias_initials) > 1 else 90
    if len(alias_initials) == 1 and len(target_initials) > 1 and alias_initials[0] == target_initials[1]:
        return "patronymic_initial_only", 70
    if set(alias_initials).issubset(set(target_initials)):
        return "initial_subset", 60
    return "", 0


def build_alias_candidates(scholars: list[dict], curated: dict[tuple[str, str], dict]) -> list[dict]:
    known_by_surname = defaultdict(list)
    unknown_initialled = []

    for scholar in scholars:
        norm_key = scholar_key(scholar)
        surname, initials = key_parts(norm_key)
        if not surname:
            continue
        row = {
            "person_id": scholar.get("id") or "",
            "name": scholar_display(scholar),
            "normalized_key": norm_key,
            "surname": surname,
            "initials": " ".join(initials),
            "birth_year": scholar.get("birth_year") or "",
            "total_talks": int(scholar.get("total_talks") or 0),
            "first_year": scholar.get("first_year") or "",
            "last_year": scholar.get("last_year") or "",
            "url_slug": scholar.get("url_slug") or "",
        }
        if scholar.get("birth_year") and len(initials) >= 1:
            known_by_surname[surname].append(row)
        elif not scholar.get("birth_year") and 1 <= len(initials) <= 2:
            unknown_initialled.append(row)

    rows = []
    for alias in unknown_initialled:
        same_surname = known_by_surname.get(alias["surname"], [])
        scored = []
        alias_initials = alias["initials"].split()
        for target in same_surname:
            target_initials = target["initials"].split()
            rule, score = match_rule(alias_initials, target_initials)
            if not rule:
                continue
            scored.append((score, rule, target))
        scored.sort(key=lambda item: (-item[0], -item[2]["total_talks"], item[2]["name"]))
        for score, rule, target in scored[:5]:
            status = "accepted" if (alias["normalized_key"], target["normalized_key"]) in curated else "review"
            confidence = "high" if score >= 90 and len(scored) == 1 else "medium" if score >= 70 else "low"
            if len(scored) > 1 and status != "accepted":
                confidence = "ambiguous"
            rows.append(
                {
                    "alias_person_id": alias["person_id"],
                    "alias_name": alias["name"],
                    "alias_normalized_key": alias["normalized_key"],
                    "alias_talks": alias["total_talks"],
                    "target_person_id": target["person_id"],
                    "target_name": target["name"],
                    "target_normalized_key": target["normalized_key"],
                    "target_birth_year": target["birth_year"],
                    "target_talks": target["total_talks"],
                    "match_rule": rule,
                    "score": score,
                    "confidence": confidence,
                    "curation_status": status,
                }
            )
    return rows


def build_birth_gap_rows(scholars: list[dict], alias_candidates: list[dict]) -> list[dict]:
    best_by_alias = {}
    for row in alias_candidates:
        current = best_by_alias.get(row["alias_person_id"])
        if not current or int(row["score"]) > int(current["score"]):
            best_by_alias[row["alias_person_id"]] = row

    rows = []
    for scholar in scholars:
        if scholar.get("birth_year"):
            continue
        norm_key = scholar_key(scholar)
        surname, initials = key_parts(norm_key)
        best = best_by_alias.get(scholar.get("id") or "")
        rows.append(
            {
                "person_id": scholar.get("id") or "",
                "name": scholar_display(scholar),
                "normalized_key": norm_key,
                "total_talks": int(scholar.get("total_talks") or 0),
                "first_year": scholar.get("first_year") or "",
                "last_year": scholar.get("last_year") or "",
                "initials_only": 1 if surname and 1 <= len(initials) <= 2 else 0,
                "best_alias_target": best.get("target_name", "") if best else "",
                "best_alias_rule": best.get("match_rule", "") if best else "",
                "best_alias_confidence": best.get("confidence", "") if best else "",
                "curation_status": best.get("curation_status", "") if best else "",
            }
        )
    rows.sort(key=lambda row: (-int(row["total_talks"]), row["name"]))
    return rows


def main() -> None:
    data = load_site_data()
    scholars = data.get("scholars") or []
    curated = load_curated_aliases()
    alias_rows = build_alias_candidates(scholars, curated)
    birth_rows = build_birth_gap_rows(scholars, alias_rows)

    write_csv(
        ANALYTICS / "identity_alias_candidates.csv",
        alias_rows,
        [
            "alias_person_id",
            "alias_name",
            "alias_normalized_key",
            "alias_talks",
            "target_person_id",
            "target_name",
            "target_normalized_key",
            "target_birth_year",
            "target_talks",
            "match_rule",
            "score",
            "confidence",
            "curation_status",
        ],
    )
    write_csv(
        ANALYTICS / "birth_year_gap_audit.csv",
        birth_rows,
        [
            "person_id",
            "name",
            "normalized_key",
            "total_talks",
            "first_year",
            "last_year",
            "initials_only",
            "best_alias_target",
            "best_alias_rule",
            "best_alias_confidence",
            "curation_status",
        ],
    )

    summary = {
        "schema_version": "1.0.0",
        "total_scholars": len(scholars),
        "unknown_birth_years": len(birth_rows),
        "initials_only_unknown_birth_years": sum(int(row["initials_only"]) for row in birth_rows),
        "alias_candidates": len(alias_rows),
        "curated_aliases_configured": len(curated),
        "active_accepted_alias_candidates": sum(1 for row in alias_rows if row["curation_status"] == "accepted"),
        "high_confidence_review_candidates": sum(
            1 for row in alias_rows if row["curation_status"] != "accepted" and row["confidence"] == "high"
        ),
    }
    (ANALYTICS / "identity_trend_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        "identity audit: "
        f"{summary['unknown_birth_years']} unknown birth years; "
        f"{summary['alias_candidates']} alias candidates; "
        f"{summary['curated_aliases_configured']} curated aliases configured"
    )


if __name__ == "__main__":
    main()
