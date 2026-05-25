"""Public metadata normalization without overwriting programme provenance."""
from __future__ import annotations

import csv
import re
from pathlib import Path


VERIFIED_AFFILIATIONS_PATH = Path("curation/verified_affiliation_spans.csv")
INSTITUTION_MARKER_RE = re.compile(
    r"(?:университет|факультет|институт|академ|ран\b|спбгу|мгу\b|вшэ|рггу|маэ|ивр?\b)",
    flags=re.IGNORECASE,
)
LEADING_PARENTHETICAL_RE = re.compile(r"^\s*\(([^()]+)\)\s*[.,;:]?\s*")
MISSING_AFFILIATION = {"", "не указана", "не указано", "not specified"}
LOCATION_ONLY_RE = re.compile(
    r"^(?:спб\.?|санкт-петербург|москва|пенза|казань|обнинск|краснодар|"
    r"вильнюс|гент|калининград|новосибирск|томск)(?:\s*[-–—]\s*.+)?$",
    flags=re.IGNORECASE,
)


def compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_reported_affiliation(value: str | None) -> str | None:
    """Canonicalize only institutional labels explicitly present in a source."""
    text = compact_text(value)
    if not text or text.lower() in MISSING_AFFILIATION:
        return None
    if LOCATION_ONLY_RE.match(text):
        return None
    lower = text.lower()
    if "спбгу" in lower:
        if "восточн" in lower and "факульт" in lower:
            return "СПбГУ, Восточный факультет"
        return "СПбГУ"
    return text if INSTITUTION_MARKER_RE.search(text) else None


def split_leading_affiliation(title: str | None) -> tuple[str, str | None]:
    """Move a leading institutional parenthetical from a title to metadata.

    This covers parser leaks such as ``(СПбГУ). Древнеиндийские диалекты...``
    without stripping legitimate title-initial parentheses lacking an
    institutional marker.
    """
    value = compact_text(title)
    match = LEADING_PARENTHETICAL_RE.match(value)
    if not match or not INSTITUTION_MARKER_RE.search(match.group(1)):
        return value, None
    affiliation = canonical_reported_affiliation(match.group(1))
    return value[match.end():].strip(), affiliation


def load_verified_affiliation_spans(path: Path = VERIFIED_AFFILIATIONS_PATH) -> dict[str, list[dict]]:
    spans: dict[str, list[dict]] = {}
    if not path.exists():
        return spans
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            person_id = compact_text(row.get("person_id"))
            if person_id:
                spans.setdefault(person_id, []).append(row)
    return spans


def public_affiliation(
    person_id: str | None,
    year: int | str | None,
    programme_value: str | None,
    embedded_affiliation: str | None,
    spans: dict[str, list[dict]],
) -> dict:
    """Return a public institution while retaining the programme observation.

    Location-only markers and omissions are not institutional affiliations.
    A verified span may supply a more precise institution within its explicitly
    stated dates. If the span has no recorded end, later city-only or missing
    entries retain that institution as an explicitly tentative continuation.
    """
    raw = compact_text(programme_value)
    observed = embedded_affiliation or canonical_reported_affiliation(raw)
    value_year = int(year) if str(year or "").isdigit() else None
    matched = None
    for candidate in spans.get(str(person_id or ""), []):
        start = int(candidate["start_year"]) if candidate.get("start_year") else None
        end = int(candidate["end_year"]) if candidate.get("end_year") else None
        if value_year is not None and (start is None or value_year >= start) and (end is None or value_year <= end):
            matched = candidate
            break
    if matched:
        verified_display = compact_text(matched.get("affiliation_ru"))
        if observed and (
            observed.lower() not in verified_display.lower()
            and verified_display.lower() not in observed.lower()
        ):
            return {
                "display": observed,
                "basis": "programme",
                "reported": raw or None,
                "source_url": None,
                "note": None,
            }
        start = int(matched["start_year"]) if matched.get("start_year") else None
        tentative_continuation = bool(
            not observed
            and not compact_text(matched.get("end_year"))
            and value_year is not None
            and start is not None
            and value_year > start
        )
        display = verified_display
        note = compact_text(matched.get("note"))
        if tentative_continuation:
            display = f"{display} (?)"
            inference_note = (
                "Продолжение прежней аффилиации предполагается до появления "
                "свидетельства о смене; в программе этого года учреждение не названо."
            )
            note = f"{note} {inference_note}".strip()
        return {
            "display": display,
            "basis": "inferred_continuation" if tentative_continuation else "verified_span",
            "reported": raw or None,
            "source_url": compact_text(matched.get("source_url")) or None,
            "note": note or None,
        }
    return {
        "display": observed,
        "basis": "programme" if observed else None,
        "reported": raw or None,
        "source_url": None,
        "note": None,
    }
