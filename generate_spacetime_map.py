import csv
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SITE_DATA_PATH = ROOT / "site_data.json"
OVERRIDES_PATH = ROOT / "curation" / "spacetime_overrides.csv"
OUTPUT_JSON_PATH = ROOT / "analytics_output" / "spacetime_index.json"
OUTPUT_UNMATCHED_PATH = ROOT / "analytics_output" / "spacetime_unmatched.csv"
OUTPUT_HTML_PATH = ROOT / "spacetime.html"
OUTPUT_TIMELINE_HTML_PATH = ROOT / "spacetime-timeline.html"
TIMELAPSE_MIN_YEAR = -3000
TIMELAPSE_MAX_YEAR = 2100


@dataclass(frozen=True)
class PlaceRule:
    id: str
    label_ru: str
    label_en: str
    lat: float
    lon: float
    scope: str
    confidence: float
    patterns: tuple[str, ...]
    fallback: bool = False


@dataclass(frozen=True)
class TimeRule:
    id: str
    label_ru: str
    label_en: str
    center_year: int
    start_year: int
    end_year: int
    confidence: float
    patterns: tuple[str, ...]
    default_place_id: str | None = None


PLACE_RULES = [
    PlaceRule("tamil_nadu", "Тамилнад / тамильский Юг", "Tamil Nadu / Tamil South", 11.1271, 78.6569, "region", 0.86, (
        r"\bтамил", r"\btamil", r"\bчола", r"\bтирумур", r"\btirumur", r"\bтирумулар", r"\bnataraja", r"\bнатарадж",
        r"\bмелаттур", r"\bmelattur", r"\bmarganatyam", r"\bмарганатьям",
    )),
    PlaceRule("kerala", "Керала", "Kerala", 10.8505, 76.2711, "region", 0.86, (
        r"\bкерал", r"\bkerala", r"\bмалаял", r"\bmalayal", r"\bпадаяни", r"\bpadayani", r"\bмудиетту", r"\bmudiyettu",
        r"\bтиятту", r"\btheyyam", r"\bkathakali", r"\bкатхакали",
    )),
    PlaceRule("karnataka_tulu", "Карнатака / Тулунаду", "Karnataka / Tulu Nadu", 13.3409, 74.7421, "region", 0.86, (
        r"\bкарнатак", r"\bkarnatak", r"\bтулунаду", r"\btulunadu", r"\btulu", r"\bbhuta", r"\bбхута",
    )),
    PlaceRule("andhra_telangana", "Андхра / Телангана", "Andhra / Telangana", 16.5062, 80.6480, "region", 0.82, (
        r"\bандхр", r"\bandhra", r"\bтелугу", r"\btelugu", r"\bтеланган",
    )),
    PlaceRule("south_india", "Южная Индия", "South India", 12.9716, 77.5946, "macroregion", 0.74, (
        r"\bюжн\w*\s+инд", r"\bsouth\s+india", r"\bдравид", r"\bdravid",
    )),
    PlaceRule("sri_lanka", "Шри-Ланка / Цейлон", "Sri Lanka / Ceylon", 7.8731, 80.7718, "country", 0.9, (
        r"\bшри-?ланк", r"\bцейлон", r"\bsri\s*lanka", r"\bceylon", r"\bведд", r"\bvedda",
    )),
    PlaceRule("bengal", "Бенгалия", "Bengal", 23.6850, 87.8550, "region", 0.84, (
        r"\bбенгал", r"\bbengal", r"\bтагор", r"\btagore", r"\bрабиндранат", r"\bчайт",
    )),
    PlaceRule("assam", "Ассам", "Assam", 26.2006, 92.9376, "region", 0.88, (
        r"\bассам", r"\bassam", r"\bsattriya", r"\bсаттрия", r"\bанкхья", r"\bankhya",
    )),
    PlaceRule("odisha", "Одиша / Орисса", "Odisha / Orissa", 20.9517, 85.0985, "region", 0.84, (
        r"\bодиш", r"\bорисс", r"\bodisha", r"\borissa", r"\bпури\b", r"\bpuri\b",
    )),
    PlaceRule("rajasthan", "Раджастхан", "Rajasthan", 27.0238, 74.2179, "region", 0.86, (
        r"\bраджаст", r"\brajasthan", r"\bбхеру", r"\bbheru", r"\bгарба", r"\bgarba",
    )),
    PlaceRule("gujarat", "Гуджарат", "Gujarat", 22.2587, 71.1924, "region", 0.86, (
        r"\bгуджарат", r"\bgujarat", r"\bбхаваи", r"\bbhavai",
    )),
    PlaceRule("maharashtra", "Махараштра", "Maharashtra", 19.7515, 75.7139, "region", 0.82, (
        r"\bмахарашт", r"\bmaharash", r"\bмаратх", r"\bmarath",
    )),
    PlaceRule("haryana", "Харьяна", "Haryana", 29.0588, 76.0856, "region", 0.82, (
        r"\bхарья", r"\bharyana",
    )),
    PlaceRule("kashmir", "Кашмир", "Kashmir", 34.0837, 74.7973, "region", 0.86, (
        r"\bкашмир", r"\bkashmir", r"\bабхинавагупт", r"\babhinavagupta",
    )),
    PlaceRule("gandhara_taxila", "Гандхара / Таксила", "Gandhara / Taxila", 33.7463, 72.8397, "historical_region", 0.78, (
        r"\bгандхар", r"\bgandhara", r"\bтаксил", r"\btaxila", r"\bпанини", r"\bpāṇini", r"\bpanini",
    )),
    PlaceRule("harappa_indus", "Хараппа / долина Инда", "Harappa / Indus Valley", 30.6305, 72.8676, "archaeological_site", 0.8, (
        r"\bхарапп", r"\bharapp", r"\bпротоинд", r"\bproto-?ind", r"\bиндск\w*\s+цивилизац", r"\bindus\s+(valley|civilization|script|texts?)",
    )),
    PlaceRule("vedic_northwest", "Ведийский северо-запад", "Vedic North-West India", 30.9000, 75.8500, "historical_region", 0.72, (
        r"\bригвед", r"\brigveda", r"\bрв\b", r"\bведийск", r"\bvedic",
    )),
    PlaceRule("varanasi", "Варанаси / Бенарес", "Varanasi / Banaras", 25.3176, 82.9739, "city", 0.86, (
        r"\bваранаси", r"\bбенарес", r"\bbanaras", r"\bvaranasi", r"\bkashi\b", r"\bкаши\b",
    )),
    PlaceRule("ayodhya", "Айодхья", "Ayodhya", 26.7922, 82.1998, "city", 0.86, (
        r"\bайодх", r"\bayodh",
    )),
    PlaceRule("nepal_kathmandu", "Непал / Катманду", "Nepal / Kathmandu", 27.7172, 85.3240, "region", 0.88, (
        r"\bнепал", r"\bnepal", r"\bкатманду", r"\bkathmandu", r"\bневар", r"\bnewar", r"\bпатан\b", r"\bpatan\b",
    )),
    PlaceRule("tibet", "Тибет", "Tibet", 31.6927, 88.0924, "region", 0.88, (
        r"\bтибет", r"\btibet", r"\bлхас", r"\blhasa", r"\bгелук", r"\bgeluk", r"\bдзонк",
    )),
    PlaceRule("ladakh", "Ладакх", "Ladakh", 34.1526, 77.5770, "region", 0.9, (
        r"\bладак", r"\bladakh",
    )),
    PlaceRule("himalaya", "Гималаи", "Himalaya", 30.0668, 79.0193, "macroregion", 0.74, (
        r"\bгимала", r"\bhimalay", r"\bкумаон", r"\bkumaon", r"\bхимачал", r"\bhimachal",
    )),
    PlaceRule("central_asia", "Центральная Азия", "Central Asia", 43.2220, 76.8512, "macroregion", 0.72, (
        r"\bцентральн\w*\s+ази", r"\bcentral\s+asia", r"\bсиньцзян", r"\bxinjiang", r"\bуйгур",
    )),
    PlaceRule("mongolia", "Монголия", "Mongolia", 46.8625, 103.8467, "country", 0.82, (
        r"\bмонгол", r"\bmongol", r"\bулан-батор", r"\bulaanbaatar",
    )),
    PlaceRule("china", "Китай", "China", 35.8617, 104.1954, "country", 0.78, (
        r"\bкитай", r"\bchina", r"\bкитайск",
    )),
    PlaceRule("japan", "Япония", "Japan", 36.2048, 138.2529, "country", 0.78, (
        r"\bяпон", r"\bjapan",
    )),
    PlaceRule("india_general", "Индия", "India", 22.9734, 78.6569, "country", 0.55, (
        r"\bиндии\b", r"\bиндия\b", r"\bиндийск", r"\bindia\b", r"\bindian\b",
    ), fallback=True),
]

PLACE_RULE_BY_ID = {rule.id: rule for rule in PLACE_RULES}

TIME_RULES = [
    TimeRule("harappa_indus", "Хараппа / хараппская цивилизация, III тыс. - XVII-XVI вв. до н. э.", "Harappa / Indus Valley, 3rd millennium-17th/16th c. BCE", -2300, -3000, -1600, 0.74, (
        r"\bхарапп", r"\bharapp", r"\bпротоинд", r"\bproto-?ind", r"\bиндск\w*\s+цивилизац", r"\bindus\s+(valley|civilization|script|texts?)",
    ), "harappa_indus"),
    TimeRule("rigveda", "Ригведа, условно XV в. до н. э.", "Rigveda, conventionally 15th c. BCE", -1500, -1700, -1200, 0.72, (
        r"\bригвед", r"\brigveda", r"\bрв\b",
    ), "vedic_northwest"),
    TimeRule("vedic_period", "Ведийский период, условно XII в. до н. э.", "Vedic period, conventionally 12th c. BCE", -1200, -1500, -800, 0.62, (
        r"\bведийск", r"\bvedic", r"\bатхарвав", r"\batharvav", r"\bсамхит",
    ), "vedic_northwest"),
    TimeRule("upanishads", "Ранние упанишады, условно VII в. до н. э.", "Early Upanishads, conventionally 7th c. BCE", -700, -800, -500, 0.64, (
        r"\bупаниш", r"\bupani",
    ), "india_general"),
    TimeRule("panini", "Панини, условно V в. до н. э.", "Panini, conventionally 5th c. BCE", -500, -550, -450, 0.7, (
        r"\bпанини", r"\bpāṇini", r"\bpanini", r"\bаштаи?дхья", r"\baṣṭādhyāyī", r"\bashtadhyayi",
    ), "gandhara_taxila"),
    TimeRule("early_buddhism", "Ранний буддизм, условно V в. до н. э.", "Early Buddhism, conventionally 5th c. BCE", -500, -550, -400, 0.64, (
        r"\bранн\w*\s+будд", r"\bearly\s+buddh", r"\bбудда\b", r"\bbuddha\b",
    ), "india_general"),
    TimeRule("pali_canon", "Палийский канон, условно I в. до н. э.", "Pali canon, conventionally 1st c. BCE", -100, -200, 100, 0.62, (
        r"\bпали", r"\bpali", r"\bпалийск",
    ), "sri_lanka"),
    TimeRule("ashoka_maurya", "Ашока / Маурьи, III в. до н. э.", "Aśoka / Maurya, 3rd c. BCE", -250, -320, -180, 0.72, (
        r"\bашок", r"\ba[śs]oka", r"\bмаур", r"\bmaurya",
    ), "india_general"),
    TimeRule("sangam", "Сангамская эпоха, условно I в.", "Sangam age, conventionally 1st c. CE", 100, -100, 300, 0.62, (
        r"\bсангам", r"\bsangam", r"\bпаттупп", r"\bpattupp",
    ), "tamil_nadu"),
    TimeRule("classical_sanskrit", "Классический санскрит, условно V в.", "Classical Sanskrit, conventionally 5th c. CE", 450, 300, 600, 0.5, (
        r"\bкалидас", r"\bkalidasa", r"\bгупт", r"\bgupta",
    ), "india_general"),
    TimeRule("tamil_bhakti", "Тамильская бхакти, условно VII-IX вв.", "Tamil Bhakti, conventionally 7th-9th c. CE", 800, 600, 900, 0.62, (
        r"\bна?янар", r"\bnayan", r"\bальвар", r"\balvar", r"\bтирумур", r"\btirumur", r"\bбхакти",
    ), "tamil_nadu"),
    TimeRule("chola", "Чола, условно XI в.", "Chola period, conventionally 11th c. CE", 1000, 850, 1250, 0.66, (
        r"\bчола", r"\bchola",
    ), "tamil_nadu"),
    TimeRule("chaitanya", "Чайтанья, XVI в.", "Chaitanya, 16th c. CE", 1500, 1480, 1535, 0.68, (
        r"\bчайтан", r"\bchaitanya",
    ), "bengal"),
    TimeRule("mughal", "Могольский период, условно XVII в.", "Mughal period, conventionally 17th c. CE", 1600, 1526, 1707, 0.58, (
        r"\bмогол", r"\bmughal",
    ), "india_general"),
    TimeRule("colonial_india", "Колониальная Индия, условно XIX в.", "Colonial India, conventionally 19th c. CE", 1850, 1757, 1947, 0.54, (
        r"\bколони", r"\bcolonial", r"\bбритан", r"\bbritish", r"\bост-инд",
    ), "india_general"),
    TimeRule("vivekananda", "Вивекананда, 1890-е", "Vivekananda, 1890s", 1893, 1880, 1902, 0.7, (
        r"\bвивекананд", r"\bvivekananda",
    ), "bengal"),
    TimeRule("tagore", "Рабиндранат Тагор, начало XX в.", "Rabindranath Tagore, early 20th c.", 1910, 1890, 1941, 0.7, (
        r"\bтагор", r"\btagore", r"\bрабиндранат",
    ), "bengal"),
    TimeRule("gandhi", "М. К. Ганди, 1920-1940-е", "M. K. Gandhi, 1920s-1940s", 1930, 1915, 1948, 0.72, (
        r"\bганди", r"\bgandhi",
    ), "gujarat"),
    TimeRule("roerich", "Рерихи, 1920-1950-е", "Roerichs, 1920s-1950s", 1930, 1920, 1960, 0.66, (
        r"\bрерих", r"\broerich",
    ), "himalaya"),
    TimeRule("independence_modern", "Независимая Индия, после 1947", "Independent India, after 1947", 1950, 1947, 2026, 0.5, (
        r"\bнезависим\w*\s+инд", r"\bindependent\s+india", r"\bсовременн\w*\s+инд", r"\bmodern\s+india",
    ), "india_general"),
]


def load_site_data(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def norm_text(value: str) -> str:
    value = (value or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", value)


def talk_text(talk: dict) -> str:
    chunks = [
        talk.get("title") or "",
        " ".join(talk.get("tags") or []),
        " ".join(talk.get("meso_codes") or []),
        (talk.get("theme") or {}).get("ru") or "",
        (talk.get("theme") or {}).get("en") or "",
    ]
    return norm_text(" ".join(chunks))


def rule_matches(patterns: tuple[str, ...], text: str) -> list[str]:
    matches = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append(pattern)
    return matches


def place_to_payload(rule: PlaceRule, source: str, matched: list[str] | None = None) -> dict:
    return {
        "id": rule.id,
        "label_ru": rule.label_ru,
        "label_en": rule.label_en,
        "lat": rule.lat,
        "lon": rule.lon,
        "scope": rule.scope,
        "confidence": rule.confidence,
        "source": source,
        "matched": matched or [],
    }


def time_to_payload(rule: TimeRule, matched: list[str] | None = None) -> dict:
    return {
        "id": rule.id,
        "label_ru": rule.label_ru,
        "label_en": rule.label_en,
        "center_year": rule.center_year,
        "start_year": rule.start_year,
        "end_year": rule.end_year,
        "confidence": rule.confidence,
        "source": "rule",
        "matched": matched or [],
        "default_place_id": rule.default_place_id,
    }


def apply_place_rules(text: str) -> list[dict]:
    matches = []
    for rule in PLACE_RULES:
        matched = rule_matches(rule.patterns, text)
        if matched:
            matches.append((rule, matched))

    specific = [(rule, matched) for rule, matched in matches if not rule.fallback]
    if specific:
        matches = specific

    return [place_to_payload(rule, "rule", matched) for rule, matched in matches]


def apply_time_rules(text: str) -> list[dict]:
    results = []
    for rule in TIME_RULES:
        matched = rule_matches(rule.patterns, text)
        if matched:
            results.append(time_to_payload(rule, matched))
    return results


def load_overrides(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    overrides: dict[str, list[dict]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(row for row in handle if not row.lstrip().startswith("#"))
        for row in reader:
            presentation_id = (row.get("presentation_id") or "").strip()
            if not presentation_id:
                continue
            overrides.setdefault(presentation_id, []).append(row)
    return overrides


def apply_overrides(record: dict, rows: list[dict]) -> None:
    for row in rows:
        confidence = float(row.get("confidence") or 1.0)
        source_url = (row.get("source_url") or "").strip()
        notes = (row.get("notes") or "").strip()

        place_id = (row.get("place_id") or "").strip()
        lat = (row.get("lat") or "").strip()
        lon = (row.get("lon") or "").strip()
        if place_id and place_id in PLACE_RULE_BY_ID:
            place = place_to_payload(PLACE_RULE_BY_ID[place_id], "override")
            place["confidence"] = confidence
            place["source_url"] = source_url
            place["notes"] = notes
            record["places"].append(place)
        elif lat and lon:
            record["places"].append({
                "id": place_id or f"manual:{record['presentation_id']}",
                "label_ru": (row.get("place_label_ru") or "").strip() or place_id or "Ручная точка",
                "label_en": (row.get("place_label_en") or "").strip() or place_id or "Manual point",
                "lat": float(lat),
                "lon": float(lon),
                "scope": (row.get("place_scope") or "manual").strip(),
                "confidence": confidence,
                "source": "override",
                "source_url": source_url,
                "notes": notes,
                "matched": [],
            })

        start_year = (row.get("start_year") or "").strip()
        end_year = (row.get("end_year") or "").strip()
        if start_year or end_year:
            start = int(start_year or end_year)
            end = int(end_year or start_year)
            record["times"].append({
                "id": (row.get("time_id") or "").strip() or f"manual:{record['presentation_id']}",
                "label_ru": (row.get("time_label_ru") or "").strip() or "Ручная датировка",
                "label_en": (row.get("time_label_en") or "").strip() or "Manual dating",
                "center_year": round((start + end) / 2),
                "start_year": start,
                "end_year": end,
                "confidence": confidence,
                "source": "override",
                "source_url": source_url,
                "notes": notes,
                "matched": [],
                "default_place_id": place_id or None,
            })


def dedupe_places(places: list[dict]) -> list[dict]:
    deduped = {}
    for place in places:
        key = place["id"]
        old = deduped.get(key)
        if not old or place.get("source") == "override" or place.get("confidence", 0) > old.get("confidence", 0):
            deduped[key] = place
    return sorted(deduped.values(), key=lambda row: (-row.get("confidence", 0), row["label_ru"]))


def dedupe_times(times: list[dict]) -> list[dict]:
    deduped = {}
    for time in times:
        key = time["id"]
        old = deduped.get(key)
        if not old or time.get("source") == "override" or time.get("confidence", 0) > old.get("confidence", 0):
            deduped[key] = time
    return sorted(deduped.values(), key=lambda row: (row["center_year"], -row.get("confidence", 0)))


def ensure_default_time_places(record: dict) -> None:
    place_ids = {place["id"] for place in record["places"]}
    for time in record["times"]:
        place_id = time.get("default_place_id")
        if place_id and place_id not in place_ids and place_id in PLACE_RULE_BY_ID:
            place = place_to_payload(PLACE_RULE_BY_ID[place_id], "time_default")
            place["confidence"] = min(place["confidence"], time.get("confidence", 0.5))
            record["places"].append(place)
            place_ids.add(place_id)


def build_records(site_data: dict, overrides: dict[str, list[dict]]) -> list[dict]:
    records = []
    for scholar in site_data.get("scholars", []):
        speaker = scholar.get("name") or scholar.get("full_name_ru") or scholar.get("id")
        for talk in scholar.get("talks", []):
            text = talk_text(talk)
            record = {
                "presentation_id": talk.get("presentation_id"),
                "title": talk.get("title") or "",
                "speaker": speaker,
                "scholar_id": scholar.get("id"),
                "scholar_slug": scholar.get("url_slug"),
                "conference_year": talk.get("year"),
                "series": talk.get("series"),
                "public_path": talk.get("public_path"),
                "theme_code": (talk.get("theme") or {}).get("code"),
                "theme_ru": (talk.get("theme") or {}).get("ru"),
                "meso_codes": talk.get("meso_codes") or [],
                "places": apply_place_rules(text),
                "times": apply_time_rules(text),
            }
            apply_overrides(record, overrides.get(record["presentation_id"], []))
            ensure_default_time_places(record)
            record["places"] = dedupe_places(record["places"])
            record["times"] = dedupe_times(record["times"])
            records.append(record)
    records.sort(key=lambda row: (row.get("conference_year") or 9999, row["title"]))
    return records


def write_unmatched(records: list[dict]) -> None:
    OUTPUT_UNMATCHED_PATH.parent.mkdir(exist_ok=True)
    with OUTPUT_UNMATCHED_PATH.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "presentation_id",
            "title",
            "speaker",
            "conference_year",
            "series",
            "public_path",
            "meso_codes",
            "needs_place",
            "needs_time",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            needs_place = not record["places"]
            needs_time = not record["times"]
            if not needs_place and not needs_time:
                continue
            writer.writerow({
                "presentation_id": record["presentation_id"],
                "title": record["title"],
                "speaker": record["speaker"],
                "conference_year": record["conference_year"],
                "series": record["series"],
                "public_path": record["public_path"],
                "meso_codes": "|".join(record["meso_codes"]),
                "needs_place": int(needs_place),
                "needs_time": int(needs_time),
            })


def build_summary(records: list[dict]) -> dict:
    meso_counts: dict[str, int] = {}
    for record in records:
        for code in record["meso_codes"]:
            meso_counts[code] = meso_counts.get(code, 0) + 1

    timed = [record for record in records if record["times"]]
    time_starts = [time.get("start_year", time["center_year"]) for record in timed for time in record["times"]]
    time_ends = [time.get("end_year", time["center_year"]) for record in timed for time in record["times"]]
    return {
        "total_records": len(records),
        "mappable_records": sum(1 for record in records if record["places"]),
        "timed_records": len(timed),
        "spacetime_records": sum(1 for record in records if record["places"] and record["times"]),
        "time_min": min([TIMELAPSE_MIN_YEAR, *time_starts]),
        "time_max": max([TIMELAPSE_MAX_YEAR, *time_ends]),
        "meso_counts": dict(sorted(meso_counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def write_json(records: list[dict]) -> None:
    payload = {
        "schema_version": "spacetime-v1",
        "generated": dt.date.today().isoformat(),
        "summary": build_summary(records),
        "records": records,
        "place_rules": [
            {key: value for key, value in rule.__dict__.items() if key != "patterns"}
            for rule in PLACE_RULES
        ],
        "time_rules": [
            {key: value for key, value in rule.__dict__.items() if key != "patterns"}
            for rule in TIME_RULES
        ],
        "manual_overrides_path": "curation/spacetime_overrides.csv",
    }
    OUTPUT_JSON_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Карта и исторический таймлапс | Архив российской индологии</title>
    <meta name="description" content="Карта сюжетных регионов и исторических датировок докладов архива IndologyScholars.">
    <link rel="canonical" href="https://gasyoun.github.io/IndologyScholars/spacetime.html">
    <link rel="icon" href="/IndologyScholars/assets/favicon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <style>
        :root {
            color-scheme: dark;
            --bg: #06110f;
            --panel: rgba(11, 20, 18, 0.94);
            --panel2: #101b18;
            --border: rgba(255,255,255,0.12);
            --text: #eef5f1;
            --muted: #a9b8b1;
            --accent: #4fb494;
            --gold: #d6ad67;
            --blue: #74a7ff;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            background: var(--bg);
            color: var(--text);
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        .app {
            display: grid;
            grid-template-columns: minmax(330px, 420px) minmax(0, 1fr);
            height: 100vh;
        }
        aside {
            background: var(--panel);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            min-height: 0;
        }
        header {
            padding: 1.1rem 1.2rem 0.9rem;
            border-bottom: 1px solid var(--border);
        }
        h1 {
            font-size: 1.15rem;
            line-height: 1.25;
            margin: 0 0 0.45rem;
            letter-spacing: 0;
        }
        .sub {
            color: var(--muted);
            font-size: 0.86rem;
            line-height: 1.45;
        }
        .controls {
            padding: 1rem 1.2rem;
            display: grid;
            gap: 0.85rem;
            border-bottom: 1px solid var(--border);
        }
        label {
            display: grid;
            gap: 0.35rem;
            color: var(--muted);
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        select, input[type="search"] {
            width: 100%;
            border: 1px solid var(--border);
            background: #0b1513;
            color: var(--text);
            border-radius: 6px;
            padding: 0.55rem 0.65rem;
            font: inherit;
            min-width: 0;
        }
        input[type="range"] {
            width: 100%;
            accent-color: var(--accent);
        }
        .mode {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            border: 1px solid var(--border);
            border-radius: 7px;
            overflow: hidden;
        }
        .mode button,
        .mode a {
            border: 0;
            color: var(--muted);
            background: #0b1513;
            padding: 0.55rem;
            cursor: pointer;
            font: inherit;
            text-align: center;
            text-decoration: none;
        }
        .mode button.active {
            background: rgba(79, 180, 148, 0.22);
            color: var(--text);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.45rem;
        }
        .stat {
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 0.55rem;
            background: rgba(255,255,255,0.035);
        }
        .stat strong {
            display: block;
            font-size: 1rem;
            color: var(--accent);
        }
        .stat span {
            font-size: 0.72rem;
            color: var(--muted);
        }
        .yearline {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
            flex-wrap: wrap;
            color: var(--muted);
            font-size: 0.82rem;
        }
        .yearline strong { color: var(--gold); font-size: 1rem; }
        .date-count strong { font-size: 0.95rem; }
        .results {
            min-height: 0;
            overflow: auto;
            padding: 0.8rem 1.2rem 1.2rem;
        }
        .item {
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding: 0.7rem 0;
        }
        .item a {
            color: var(--text);
            text-decoration: none;
            border-bottom: 1px solid rgba(255,255,255,0.16);
        }
        .meta {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.45;
        }
        .hint {
            border: 1px solid rgba(214, 173, 103, 0.35);
            border-radius: 7px;
            background: rgba(214, 173, 103, 0.1);
            padding: 0.75rem;
            color: #ead2a8;
            line-height: 1.45;
        }
        .hint strong {
            display: block;
            color: var(--text);
            margin-bottom: 0.25rem;
        }
        .hint button {
            margin-top: 0.55rem;
            border: 1px solid rgba(214, 173, 103, 0.55);
            border-radius: 6px;
            background: rgba(214, 173, 103, 0.16);
            color: var(--text);
            padding: 0.35rem 0.55rem;
            font: inherit;
            cursor: pointer;
        }
        .tag {
            display: inline-block;
            margin: 0.25rem 0.25rem 0 0;
            padding: 0.1rem 0.35rem;
            border-radius: 4px;
            background: rgba(79, 180, 148, 0.14);
            color: #a7f0d6;
            font-size: 0.72rem;
            text-decoration: none;
            border-bottom: 0;
        }
        .tag:hover {
            background: rgba(79, 180, 148, 0.26);
            color: var(--text);
        }
        #map {
            height: 100vh;
            width: 100%;
            background: #08110f;
        }
        .leaflet-popup-content-wrapper, .leaflet-popup-tip {
            background: var(--panel2);
            color: var(--text);
            border: 1px solid var(--border);
        }
        .popup-title {
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .popup-list {
            max-height: 250px;
            overflow: auto;
            font-size: 0.82rem;
            line-height: 1.35;
        }
        .popup-list a { color: var(--text); }
        @media (max-width: 860px) {
            .app { grid-template-columns: 1fr; height: auto; }
            aside { min-height: 55vh; }
            #map { height: 65vh; }
        }
    </style>
</head>
<body>
    <div class="app">
        <aside>
            <header>
                <h1>Карта сюжетов и исторический таймлапс</h1>
                <div class="sub">Географические и временные привязки извлекаются из названий, тегов и мезоуровней докладов. Это рабочий слой гипотез, не атлас окончательных утверждений.</div>
            </header>
            <div class="controls">
                <div class="mode" aria-label="Режим">
                    <button type="button" id="mode-map" class="active">Карта</button>
                    <button type="button" id="mode-time">Таймлапс</button>
                    <a href="spacetime-timeline.html">Хроника</a>
                </div>
                <label>Поиск
                    <input type="search" id="search" placeholder="Ригведа, Панини, Тамилнад...">
                </label>
                <label>Мезоуровень
                    <select id="meso-filter"><option value="">Все мезоуровни</option></select>
                </label>
                <label>Историческая дата
                    <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem;">
                        <input type="range" id="time-slider" min="-3000" max="2100" value="-500" step="25" style="flex: 1; margin: 0;">
                        <button id="play-btn" type="button" style="border: 1px solid var(--border); background: #0b1513; color: var(--text); border-radius: 6px; padding: 0.35rem 0.6rem; cursor: pointer; font-size: 0.8rem; min-width: 44px; display: inline-flex; justify-content: center; align-items: center;">▶</button>
                    </div>
                    <div class="yearline"><span>Окно: ±250 лет</span><span class="date-count">в окне даты: <strong id="date-count">0</strong></span><strong id="year-label">500 до н. э.</strong></div>
                </label>
                <div class="stats">
                    <div class="stat"><strong id="stat-records">0</strong><span>докладов</span></div>
                    <div class="stat"><strong id="stat-places">0</strong><span>точек</span></div>
                    <div class="stat"><strong id="stat-time">0</strong><span>с датой</span></div>
                </div>
            </div>
            <div class="results" id="results"></div>
        </aside>
        <main id="map"></main>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map', { zoomControl: true }).setView([23.5, 79], 4);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 18
        }).addTo(map);

        const markerLayer = L.layerGroup().addTo(map);
        const state = {
            data: null,
            mode: 'map',
            search: '',
            meso: new URLSearchParams(location.search).get('meso') || '',
            centerYear: -500,
            window: 250
        };

        const els = {
            search: document.getElementById('search'),
            meso: document.getElementById('meso-filter'),
            slider: document.getElementById('time-slider'),
            year: document.getElementById('year-label'),
            dateCount: document.getElementById('date-count'),
            results: document.getElementById('results'),
            statRecords: document.getElementById('stat-records'),
            statPlaces: document.getElementById('stat-places'),
            statTime: document.getElementById('stat-time'),
            modeMap: document.getElementById('mode-map'),
            modeTime: document.getElementById('mode-time')
        };

        function escapeHtml(value) {
            return String(value || '').replace(/[&<>"']/g, char => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
            }[char]));
        }

        function formatYear(year) {
            if (year < 0) return `${Math.abs(year)} до н. э.`;
            if (year === 0) return 'рубеж эр';
            return `${year} н. э.`;
        }

        function formatYearRange(time) {
            const start = Number(time.start_year ?? time.center_year);
            const end = Number(time.end_year ?? time.center_year);
            if (start === end) return formatYear(start);
            return `${formatYear(start)} - ${formatYear(end)}`;
        }

        function mesoLabel(code) {
            return String(code || '').replaceAll('_', ' ');
        }

        function mesoHref(code) {
            return `${location.pathname}?meso=${encodeURIComponent(code)}`;
        }

        function renderTag(code) {
            return `<a class="tag" href="${mesoHref(code)}" data-meso="${escapeHtml(code)}">${escapeHtml(mesoLabel(code))}</a>`;
        }

        function recordText(record) {
            return [
                record.title,
                record.speaker,
                record.series,
                record.theme_ru,
                ...(record.meso_codes || []),
                ...(record.places || []).map(p => `${p.label_ru} ${p.label_en}`),
                ...(record.times || []).map(t => `${t.label_ru} ${t.label_en}`)
            ].join(' ').toLowerCase();
        }

        function matchesSearchAndMeso(record) {
            if (state.meso && !(record.meso_codes || []).includes(state.meso)) return false;
            if (state.search && !recordText(record).includes(state.search.toLowerCase())) return false;
            return true;
        }

        function timeOverlapsWindow(time) {
            const start = Number(time.start_year ?? time.center_year);
            const end = Number(time.end_year ?? time.center_year);
            return start <= state.centerYear + state.window && end >= state.centerYear - state.window;
        }

        function matchesActiveTime(record) {
            return (record.times || []).some(timeOverlapsWindow);
        }

        function timeMatchesSearch(time) {
            const query = state.search.toLowerCase();
            if (!query) return false;
            return `${time.id} ${time.label_ru} ${time.label_en}`.toLowerCase().includes(query);
        }

        function recordMatches(record) {
            if (!matchesSearchAndMeso(record)) return false;
            if (state.mode === 'time') {
                return matchesActiveTime(record);
            }
            return true;
        }

        function nearestTime(records) {
            let best = null;
            records.forEach(record => {
                (record.times || []).forEach(time => {
                    const start = Number(time.start_year ?? time.center_year);
                    const end = Number(time.end_year ?? time.center_year);
                    const distance = state.centerYear < start ? start - state.centerYear : state.centerYear > end ? state.centerYear - end : 0;
                    const searchRank = timeMatchesSearch(time) ? 0 : 1;
                    if (!best || searchRank < best.searchRank || (searchRank === best.searchRank && distance < best.distance)) {
                        best = { ...time, distance, searchRank };
                    }
                });
            });
            return best;
        }

        function timeHints(records) {
            const rows = [];
            const seen = new Set();
            records.forEach(record => {
                (record.times || []).forEach(time => {
                    const key = `${time.id}:${time.start_year}:${time.end_year}`;
                    if (seen.has(key)) return;
                    seen.add(key);
                    const start = Number(time.start_year ?? time.center_year);
                    const end = Number(time.end_year ?? time.center_year);
                    const distance = state.centerYear < start ? start - state.centerYear : state.centerYear > end ? state.centerYear - end : 0;
                    rows.push({ time, distance, searchRank: timeMatchesSearch(time) ? 0 : 1 });
                });
            });
            return rows
                .sort((a, b) => a.searchRank - b.searchRank || a.distance - b.distance || a.time.center_year - b.time.center_year)
                .slice(0, 3)
                .map(row => `${escapeHtml(row.time.label_ru)} (${escapeHtml(formatYearRange(row.time))})`)
                .join('; ');
        }

        function filteredRecords() {
            return (state.data.records || []).filter(recordMatches);
        }

        function dateFilteredRecords() {
            return (state.data.records || []).filter(record => matchesSearchAndMeso(record) && record.times.length && matchesActiveTime(record));
        }

        function aggregatePlaces(records) {
            const places = new Map();
            records.forEach(record => {
                record.places.forEach(place => {
                    const key = place.id;
                    if (!places.has(key)) {
                        places.set(key, { ...place, records: [] });
                    }
                    places.get(key).records.push(record);
                });
            });
            return [...places.values()];
        }

        function renderMesoOptions() {
            const counts = state.data.summary.meso_counts || {};
            Object.entries(counts).forEach(([code, count]) => {
                const option = document.createElement('option');
                option.value = code;
                option.textContent = `${code.replaceAll('_', ' ')} (${count})`;
                els.meso.appendChild(option);
            });
            els.meso.value = state.meso;
        }

        function renderMarkers(records) {
            markerLayer.clearLayers();
            const mappable = records.filter(record => record.places && record.places.length > 0);
            const places = aggregatePlaces(mappable);
            places.forEach(place => {
                const radius = Math.max(7, Math.min(26, 6 + Math.sqrt(place.records.length) * 3.2));
                const marker = L.circleMarker([place.lat, place.lon], {
                    radius,
                    color: state.mode === 'time' ? '#d6ad67' : '#4fb494',
                    fillColor: state.mode === 'time' ? '#d6ad67' : '#4fb494',
                    fillOpacity: 0.62,
                    weight: 2
                });
                const sample = place.records.slice(0, 14).map(record => {
                    const href = record.public_path ? `<a href="${escapeHtml(record.public_path)}">${escapeHtml(record.title)}</a>` : escapeHtml(record.title);
                    const times = record.times.map(t => t.label_ru).join('; ');
                    return `<div style="margin-bottom:0.45rem">${href}<br><span style="color:#a9b8b1">${escapeHtml(record.speaker)} · ${record.conference_year || ''}${times ? ' · ' + escapeHtml(times) : ''}</span></div>`;
                }).join('');
                marker.bindPopup(`<div class="popup-title">${escapeHtml(place.label_ru)} · ${place.records.length}</div><div class="popup-list">${sample}</div>`);
                marker.addTo(markerLayer);
            });
            if (places.length) {
                const bounds = L.latLngBounds(places.map(place => [place.lat, place.lon]));
                map.fitBounds(bounds.pad(0.25), { animate: false });
            }
            els.statPlaces.textContent = places.length;
        }

        function renderResults(records) {
            els.statRecords.textContent = records.length;
            els.statTime.textContent = records.filter(record => record.times.length).length;
            if (!records.length) {
                els.results.innerHTML = renderEmptyState();
                return;
            }
            els.results.innerHTML = records.slice(0, 80).map(record => {
                const href = record.public_path ? `<a href="${escapeHtml(record.public_path)}">${escapeHtml(record.title)}</a>` : escapeHtml(record.title);
                const places = record.places.map(p => p.label_ru).join(', ');
                const times = record.times.map(t => t.label_ru).join(', ');
                const meso = (record.meso_codes || []).slice(0, 3).map(renderTag).join(' ');
                return `<div class="item">${href}<div class="meta">${escapeHtml(record.speaker)} · ${record.conference_year || ''} · ${escapeHtml(record.series || '')}<br>${escapeHtml(places)}${times ? '<br>' + escapeHtml(times) : ''}</div>${meso}</div>`;
            }).join('');
        }

        function renderEmptyState() {
            const scoped = (state.data.records || []).filter(matchesSearchAndMeso);
            if (state.mode === 'time' && scoped.length) {
                const candidates = scoped.filter(record => record.times.length && record.places.length);
                if (candidates.length) {
                    const nearest = nearestTime(candidates);
                    const hints = timeHints(candidates);
                    const jump = nearest ? `<button type="button" data-jump-year="${nearest.center_year}">Показать ${escapeHtml(formatYear(nearest.center_year))}</button>` : '';
                    return `<div class="item hint"><strong>Найдено ${scoped.length} по поиску и тегам, но выбранная историческая дата отсекает их.</strong> Таймлапс показывает доклады, чья датировка пересекается с окном ±${state.window} лет вокруг бегунка. Ближайшие датировки: ${hints || 'нет датировок'}. ${jump}</div>`;
                }
                return `<div class="item hint"><strong>Найдено ${scoped.length}, но для таймлапса им не хватает даты или точки на карте.</strong> Карта и таймлапс используют только записи, где есть и историческая датировка, и географическая привязка. Все датированные записи можно смотреть в отдельной хронике.</div>`;
            }
            if (scoped.length) {
                return `<div class="item hint"><strong>Найдено ${scoped.length}, но на карте их некуда поставить.</strong> У этих докладов пока нет географической привязки. Попробуйте отдельную хронику или другой мезоуровень.</div>`;
            }
            return '<div class="item"><div class="meta">Нет докладов для выбранного фильтра.</div></div>';
        }

        function render() {
            els.year.textContent = formatYear(state.centerYear);
            els.modeMap.classList.toggle('active', state.mode === 'map');
            els.modeTime.classList.toggle('active', state.mode === 'time');
            const records = filteredRecords();
            els.dateCount.textContent = dateFilteredRecords().length;
            renderMarkers(records);
            renderResults(records);
        }

        function updateUrl() {
            const params = new URLSearchParams(location.search);
            if (state.meso) params.set('meso', state.meso); else params.delete('meso');
            const url = `${location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
            history.replaceState(null, '', url);
        }

        els.search.addEventListener('input', event => {
            state.search = event.target.value.trim();
            render();
        });
        els.meso.addEventListener('change', event => {
            state.meso = event.target.value;
            updateUrl();
            render();
        });
        let playTimeout = null;
        const playBtn = document.getElementById('play-btn');

        function playNext() {
            let val = Number(els.slider.value);
            const max = Number(els.slider.max);
            const min = Number(els.slider.min);
            if (val >= max) {
                val = min;
            } else {
                val += 25;
            }
            els.slider.value = val;
            state.centerYear = val;
            render();

            const count = dateFilteredRecords().length;
            const delay = count === 0 ? 200 : 1200;
            playTimeout = setTimeout(playNext, delay);
        }

        function togglePlay() {
            if (playTimeout) {
                clearTimeout(playTimeout);
                playTimeout = null;
                playBtn.textContent = '▶';
            } else {
                playBtn.textContent = '⏸';
                const count = dateFilteredRecords().length;
                const delay = count === 0 ? 200 : 1200;
                playTimeout = setTimeout(playNext, delay);
            }
        }
        playBtn.addEventListener('click', togglePlay);

        els.slider.addEventListener('input', event => {
            if (playTimeout) {
                clearTimeout(playTimeout);
                playTimeout = null;
                playBtn.textContent = '▶';
            }
            state.centerYear = Number(event.target.value);
            render();
        });
        els.modeMap.addEventListener('click', () => {
            state.mode = 'map';
            render();
        });
        els.modeTime.addEventListener('click', () => {
            state.mode = 'time';
            render();
        });
        els.results.addEventListener('click', event => {
            const tag = event.target.closest('[data-meso]');
            if (tag) {
                event.preventDefault();
                state.meso = tag.dataset.meso;
                els.meso.value = state.meso;
                updateUrl();
                render();
                return;
            }
            const jump = event.target.closest('[data-jump-year]');
            if (jump) {
                state.centerYear = Number(jump.dataset.jumpYear);
                els.slider.value = state.centerYear;
                render();
            }
        });

        fetch('analytics_output/spacetime_index.json')
            .then(response => response.json())
            .then(data => {
                state.data = data;
                const min = data.summary.time_min ?? -3000;
                const max = data.summary.time_max ?? 2100;
                els.slider.min = Math.floor(min / 25) * 25;
                els.slider.max = Math.ceil(max / 25) * 25;
                state.centerYear = Math.max(Number(els.slider.min), Math.min(-500, Number(els.slider.max)));
                els.slider.value = state.centerYear;
                renderMesoOptions();
                render();
            })
            .catch(error => {
                els.results.innerHTML = `<div class="item"><div class="meta">Не удалось загрузить analytics_output/spacetime_index.json: ${escapeHtml(error.message)}</div></div>`;
            });
    </script>
</body>
</html>
"""


TIMELINE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Историческая хронология | Архив российской индологии</title>
    <meta name="description" content="Длинная хронология исторических датировок докладов архива IndologyScholars.">
    <link rel="canonical" href="https://gasyoun.github.io/IndologyScholars/spacetime-timeline.html">
    <link rel="icon" href="/IndologyScholars/assets/favicon.svg" type="image/svg+xml">
    <style>
        :root {
            color-scheme: dark;
            --bg: #07110f;
            --panel: #101b18;
            --border: rgba(255,255,255,0.12);
            --text: #eef5f1;
            --muted: #a9b8b1;
            --accent: #4fb494;
            --gold: #d6ad67;
            --blue: #74a7ff;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            background: var(--bg);
            color: var(--text);
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        a { color: inherit; }
        .shell {
            width: min(1120px, calc(100% - 2rem));
            margin: 0 auto;
        }
        header {
            padding: 1.4rem 0 1rem;
            border-bottom: 1px solid var(--border);
        }
        .topline {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
        }
        .back {
            display: inline-block;
            color: var(--muted);
            font-size: 0.84rem;
            text-decoration: none;
            margin-bottom: 0.45rem;
        }
        h1 {
            font-size: clamp(1.45rem, 2.8vw, 2.2rem);
            line-height: 1.15;
            margin: 0;
            letter-spacing: 0;
        }
        .summary {
            color: var(--muted);
            font-size: 0.9rem;
            text-align: right;
            line-height: 1.45;
            min-width: 180px;
        }
        .summary strong {
            display: block;
            color: var(--accent);
            font-size: 1.35rem;
        }
        .controls {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(220px, 310px);
            gap: 0.75rem;
            padding: 1rem 0;
            position: sticky;
            top: 0;
            background: rgba(7, 17, 15, 0.96);
            backdrop-filter: blur(10px);
            z-index: 2;
            border-bottom: 1px solid var(--border);
        }
        label {
            display: grid;
            gap: 0.35rem;
            color: var(--muted);
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        select, input[type="search"] {
            width: 100%;
            border: 1px solid var(--border);
            background: #0b1513;
            color: var(--text);
            border-radius: 6px;
            padding: 0.58rem 0.65rem;
            font: inherit;
        }
        .timeline {
            padding: 0.4rem 0 3rem;
        }
        .event {
            display: grid;
            grid-template-columns: minmax(132px, 190px) minmax(0, 1fr);
            gap: 1rem;
            padding: 1rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.09);
        }
        .date {
            color: var(--gold);
            font-weight: 700;
            line-height: 1.35;
        }
        .time-label {
            color: #ead2a8;
            font-size: 0.82rem;
            font-weight: 500;
            margin-top: 0.25rem;
        }
        .roman-numeral {
            color: var(--accent);
            font-weight: 700;
            font-family: Georgia, "Times New Roman", serif;
            margin-left: 0.3rem;
            font-size: 0.82rem;
        }
        .title {
            font-weight: 700;
            line-height: 1.35;
        }
        .title a {
            text-decoration: none;
            border-bottom: 1px solid rgba(255,255,255,0.16);
        }
        .meta {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.45;
        }
        .tag {
            display: inline-block;
            margin: 0.35rem 0.25rem 0 0;
            padding: 0.1rem 0.35rem;
            border-radius: 4px;
            background: rgba(79, 180, 148, 0.14);
            color: #a7f0d6;
            font-size: 0.74rem;
            text-decoration: none;
        }
        .tag:hover {
            background: rgba(79, 180, 148, 0.26);
            color: var(--text);
        }
        .empty {
            color: var(--muted);
            padding: 1.3rem 0;
        }
        @media (max-width: 720px) {
            .topline { display: block; }
            .summary { text-align: left; margin-top: 1rem; }
            .controls { grid-template-columns: 1fr; position: static; }
            .event { grid-template-columns: 1fr; gap: 0.35rem; }
        }
    </style>
</head>
<body>
    <header>
        <div class="shell topline">
            <div>
                <a class="back" href="spacetime.html">&larr; карта и таймлапс</a>
                <h1>Историческая хронология</h1>
            </div>
            <div class="summary"><strong id="event-count">0</strong><span id="record-count">датированных событий</span></div>
        </div>
    </header>
    <section class="shell controls">
        <label>Поиск
            <input type="search" id="search" placeholder="Хараппа, Панини, Ригведа...">
        </label>
        <label>Мезоуровень
            <select id="meso-filter"><option value="">Все мезоуровни</option></select>
        </label>
    </section>
    <main class="shell timeline" id="timeline"></main>

    <script>
        const state = {
            data: null,
            search: '',
            meso: new URLSearchParams(location.search).get('meso') || ''
        };

        const els = {
            search: document.getElementById('search'),
            meso: document.getElementById('meso-filter'),
            timeline: document.getElementById('timeline'),
            eventCount: document.getElementById('event-count'),
            recordCount: document.getElementById('record-count')
        };

        function escapeHtml(value) {
            return String(value || '').replace(/[&<>"']/g, char => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
            }[char]));
        }

        function formatYear(year) {
            if (year < 0) return `${Math.abs(year)} до н. э.`;
            if (year === 0) return 'рубеж эр';
            return `${year} н. э.`;
        }

        function formatYearRange(time) {
            const start = Number(time.start_year ?? time.center_year);
            const end = Number(time.end_year ?? time.center_year);
            if (start === end) return formatYear(start);
            return `${formatYear(start)} - ${formatYear(end)}`;
        }

        function mesoLabel(code) {
            return String(code || '').replaceAll('_', ' ');
        }

        function renderTag(code) {
            return `<a class="tag" href="${location.pathname}?meso=${encodeURIComponent(code)}" data-meso="${escapeHtml(code)}">${escapeHtml(mesoLabel(code))}</a>`;
        }

        function recordText(record) {
            return [
                record.title,
                record.speaker,
                record.series,
                record.theme_ru,
                ...(record.meso_codes || []),
                ...(record.places || []).map(p => `${p.label_ru} ${p.label_en}`),
                ...(record.times || []).map(t => `${t.label_ru} ${t.label_en}`)
            ].join(' ').toLowerCase();
        }

        function recordMatches(record) {
            if (state.meso && !(record.meso_codes || []).includes(state.meso)) return false;
            if (state.search && !recordText(record).includes(state.search.toLowerCase())) return false;
            return (record.times || []).length > 0;
        }

        function buildEvents() {
            const events = [];
            (state.data.records || []).filter(recordMatches).forEach(record => {
                (record.times || []).forEach(time => events.push({ record, time }));
            });
            return events.sort((a, b) => {
                const aStart = Number(a.time.start_year ?? a.time.center_year);
                const bStart = Number(b.time.start_year ?? b.time.center_year);
                return aStart - bStart || a.time.center_year - b.time.center_year || a.record.title.localeCompare(b.record.title, 'ru');
            });
        }

        function renderMesoOptions() {
            const counts = state.data.summary.meso_counts || {};
            Object.entries(counts).forEach(([code, count]) => {
                const option = document.createElement('option');
                option.value = code;
                option.textContent = `${mesoLabel(code)} (${count})`;
                els.meso.appendChild(option);
            });
            els.meso.value = state.meso;
        }

        function conferenceUrl(series, year) {
            const slug = String(series || '').toLowerCase().includes('roerich') ? 'roerich' : 'zograf';
            return `conferences/${slug}-${year}.html`;
        }

        const ROMAN_NUMERALS = {
            'harappa_indus': 'I',
            'rigveda': 'II',
            'vedic_period': 'III',
            'upanishads': 'IV',
            'panini': 'V',
            'early_buddhism': 'VI',
            'pali_canon': 'VII',
            'ashoka_maurya': 'VIII',
            'sangam': 'IX',
            'classical_sanskrit': 'X',
            'tamil_bhakti': 'XI',
            'chola': 'XII',
            'chaitanya': 'XIII',
            'mughal': 'XIV',
            'colonial_india': 'XV',
            'vivekananda': 'XVI',
            'tagore': 'XVII',
            'gandhi': 'XVIII',
            'roerich': 'XIX',
            'independence_modern': 'XX'
        };

        function render() {
            const events = buildEvents();
            const recordIds = new Set(events.map(event => event.record.presentation_id));
            els.eventCount.textContent = events.length;
            els.recordCount.textContent = `${recordIds.size} докладов`;
            if (!events.length) {
                els.timeline.innerHTML = '<div class="empty">Нет датированных событий для выбранного фильтра.</div>';
                return;
            }
            els.timeline.innerHTML = events.map(({ record, time }, idx) => {
                const href = record.public_path ? `<a href="${escapeHtml(record.public_path)}">${escapeHtml(record.title)}</a>` : escapeHtml(record.title);
                const speakerHtml = `<a href="s/${escapeHtml(record.scholar_slug)}.html" style="text-decoration: underline; text-decoration-color: var(--accent);">${escapeHtml(record.speaker)}</a>`;
                const confHref = conferenceUrl(record.series, record.conference_year);
                const confHtml = `<a href="${escapeHtml(confHref)}" style="text-decoration: underline; text-decoration-color: var(--gold);">${escapeHtml(record.series || '')} ${record.conference_year || ''}</a>`;
                const places = (record.places || []).map(place => 
                    `<a href="#" data-search="${escapeHtml(place.label_ru)}" style="text-decoration: underline; text-decoration-style: dotted; color: var(--muted);">${escapeHtml(place.label_ru)}</a>`
                ).join(', ');
                const tags = (record.meso_codes || []).slice(0, 4).map(renderTag).join(' ');
                const roman = ROMAN_NUMERALS[time.id] || '';
                const romanHtml = roman ? ` <span class="roman-numeral">(${roman})</span>` : '';
                return `<article class="event">
                    <div>
                        <div class="date">${escapeHtml(formatYearRange(time))}</div>
                        <div class="time-label">${escapeHtml(time.label_ru)}${romanHtml}</div>
                    </div>
                    <div style="position: relative;">
                        <div style="position: absolute; top: 0; right: 0; font-size: 0.76rem; color: var(--muted); opacity: 0.8; text-align: right; line-height: 1.3;">
                            #${idx + 1} <span style="opacity: 0.55; font-family: monospace; font-size: 0.72rem; margin-left: 0.35rem;">${escapeHtml(record.presentation_id)}</span>
                        </div>
                        <div class="title" style="padding-right: 145px;">${href}</div>
                        <div class="meta">${speakerHtml} · ${confHtml}${places ? '<br>' + places : ''}</div>
                        ${tags}
                    </div>
                </article>`;
            }).join('');
        }

        function updateUrl() {
            const params = new URLSearchParams(location.search);
            if (state.meso) params.set('meso', state.meso); else params.delete('meso');
            history.replaceState(null, '', `${location.pathname}${params.toString() ? '?' + params.toString() : ''}`);
        }

        els.search.addEventListener('input', event => {
            state.search = event.target.value.trim();
            render();
        });
        els.meso.addEventListener('change', event => {
            state.meso = event.target.value;
            updateUrl();
            render();
        });
        els.timeline.addEventListener('click', event => {
            const tag = event.target.closest('[data-meso]');
            if (tag) {
                event.preventDefault();
                state.meso = tag.dataset.meso;
                els.meso.value = state.meso;
                updateUrl();
                render();
                return;
            }
            const place = event.target.closest('[data-search]');
            if (place) {
                event.preventDefault();
                state.search = place.dataset.search;
                els.search.value = state.search;
                render();
                return;
            }
        });

        fetch('analytics_output/spacetime_index.json')
            .then(response => response.json())
            .then(data => {
                state.data = data;
                renderMesoOptions();
                render();
            })
            .catch(error => {
                els.timeline.innerHTML = `<div class="empty">Не удалось загрузить analytics_output/spacetime_index.json: ${escapeHtml(error.message)}</div>`;
            });
    </script>
</body>
</html>
"""


def write_html() -> None:
    OUTPUT_HTML_PATH.write_text(HTML, encoding="utf-8")


def write_timeline_html() -> None:
    OUTPUT_TIMELINE_HTML_PATH.write_text(TIMELINE_HTML, encoding="utf-8")


def main() -> None:
    site_data = load_site_data(SITE_DATA_PATH)
    overrides = load_overrides(OVERRIDES_PATH)
    records = build_records(site_data, overrides)
    write_json(records)
    write_unmatched(records)
    write_html()
    write_timeline_html()

    summary = build_summary(records)
    print(
        "Generated spacetime layer: "
        f"{summary['mappable_records']}/{summary['total_records']} mappable, "
        f"{summary['timed_records']} time-anchored, "
        f"{summary['spacetime_records']} with both."
    )
    print(f"Wrote {OUTPUT_JSON_PATH.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_UNMATCHED_PATH.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_HTML_PATH.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_TIMELINE_HTML_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
