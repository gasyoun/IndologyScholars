import sqlite3
import json
import datetime
import re
from collections import defaultdict

from classification_overrides import CLASSIFICATION_OVERRIDES, THEME_LABEL_OVERRIDES
from metadata_normalization import load_verified_affiliation_spans, public_affiliation, split_leading_affiliation
from publication_helpers import GENERATION_COHORTS, assign_unique_slugs, build_presentation_slug_map, classify_gender, generation_cohort, iso9_transliterate, load_authority_overrides, normalize_affiliation, normalize_time_interval
from title_normalization import THEME_OVERRIDES_BY_PRESENTATION_ID, TITLE_EDITORIAL_NOTES_BY_PRESENTATION_ID, canonical_title
import pipeline.genealogy as gen

DB_PATH = "conferences.db"
OUTPUT_FILE = "site_data.json"
DATA_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "2026-05-25"

def format_to_initials(name):
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[\.,;\s]+$', '', name)
    
    # 1. Pattern: Initials Last (e.g. "В. В. Вертоградова" or "В.В.Вертоградова" or "В. Вертоградова")
    m1 = re.match(r'^([А-ЯЁA-Z]\.?)\s*([А-ЯЁA-Z]\.?\s*)?([А-ЯЁA-Z][а-яёa-z\-]+)$', name)
    if m1:
        init1 = m1.group(1).replace('.', '').strip()
        init2 = m1.group(2).replace('.', '').strip() if m1.group(2) else ""
        last = m1.group(3)
        if init2:
            return f"{init1}. {init2}. {last}"
        else:
            return f"{init1}. {last}"
            
    # 2. Pattern: Last Initials (e.g. "Вертоградова В. В." or "Вертоградова В.В.")
    m2 = re.match(r'^([А-ЯЁA-Z][а-яёa-z\-]+)\s+([А-ЯЁA-Z]\.?)\s*([А-ЯЁA-Z]\.?)?$', name)
    if m2:
        last = m2.group(1)
        init1 = m2.group(2).replace('.', '').strip()
        init2 = m2.group(3).replace('.', '').strip() if m2.group(3) else ""
        if init2:
            return f"{init1}. {init2}. {last}"
        else:
            return f"{init1}. {last}"
            
    # 3. Pattern: Full Name (e.g. "Александрова Наталия Владимировна" or "Наталия Владимировна Александрова")
    parts = name.split()
    if len(parts) == 3:
        patronymic_idx = -1
        for idx, p in enumerate(parts):
            if p.endswith(('вич', 'вна', 'чна', 'чич', 'вна.', 'вич.')):
                patronymic_idx = idx
                break
        
        if patronymic_idx == 2:
            last = parts[0]
            first = parts[1]
            patr = parts[2]
            return f"{first[0]}. {patr[0]}. {last}"
        elif patronymic_idx == 1:
            last = parts[2]
            first = parts[0]
            patr = parts[1]
            return f"{first[0]}. {patr[0]}. {last}"
            
    if len(parts) == 2:
        if parts[0].endswith(('ова', 'ева', 'ина', 'ын', 'ий', 'ев', 'ов', 'их', 'ых', 'ко', 'ук', 'юк')):
            last = parts[0]
            first = parts[1]
        else:
            first = parts[0]
            last = parts[1]
        return f"{first[0]}. {last}"
        
    return name

def get_day_of_week(date_str):
    if not date_str:
        return {"ru": "Не указан", "en": "Not specified"}
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        wd = dt.weekday()
        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        days_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return {"ru": days_ru[wd], "en": days_en[wd]}
    except Exception:
        return {"ru": "Не указан", "en": "Not specified"}

def _load_city_aliases():
    try:
        with open("assets/data/geography.json", encoding="utf-8") as f:
            data = json.load(f)
            return [(item["keyword"], item["ru"], item["en"]) for item in data.get("city_aliases", [])]
    except FileNotFoundError:
        return []

_CITY_ALIASES = _load_city_aliases()


def extract_geography(affiliation_text):
    if not affiliation_text:
        return {"ru": "Не указана", "en": "Not specified"}
    aff_low = affiliation_text.lower()
    for keyword, ru, en in _CITY_ALIASES:
        if keyword in aff_low:
            return {"ru": ru, "en": en}
    return {"ru": "Не указана", "en": "Not specified"}


def aggregate_public_affiliations(talks):
    """Collapse tentative and confirmed appearances of the same institution."""
    by_institution = {}
    suffix = " (?)"
    for talk in talks:
        affiliation = str(talk.get("affiliation") or "").strip()
        if not affiliation:
            continue
        base = affiliation[:-len(suffix)] if affiliation.endswith(suffix) else affiliation
        current = by_institution.get(base)
        if current is None or (current.endswith(suffix) and not affiliation.endswith(suffix)):
            by_institution[base] = affiliation
    return list(by_institution.values())


def aggregate_affiliation_notes(talks):
    notes = list(dict.fromkeys(t["affiliation_note"] for t in talks if t.get("affiliation_note")))
    return [
        note for note in notes
        if not any(other != note and other.startswith(note) for other in notes)
    ]


def clean_title(title):
    if not title:
        return ""
    # Strip (онлайн), [онлайн], (он-лайн), (online), [online], ( zoom ), [ zoom ], case insensitive
    cleaned = re.sub(r'\s*[\(\[][оО]н[-]?лайн[\)\]]\s*', ' ', title)
    cleaned = re.sub(r'\s*[\(\[][oO]nline[\)\]]\s*', ' ', cleaned)
    cleaned = re.sub(r'\s*[\(\[][zZ]oom[\)\]]\s*', ' ', cleaned)
    cleaned = re.sub(r'\s*[\.\,;:]?\s*(?:онлайн|online|zoom)\.?\s*$', '', cleaned, flags=re.IGNORECASE)
    # Remove multiple spaces and strip
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

import csv

def load_city_trajectory():
    """Return {person_id: {coverage_pct, city_only_talks, ...}} from audit CSV."""
    data = {}
    try:
        with open("analytics_output/city_trajectory_summary.csv", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                pid = str(row.get("person_id") or "").strip()
                if not pid:
                    continue
                data[pid] = {
                    "coverage_pct": float(row.get("coverage_pct", 0)),
                    "city_only_talks": int(row.get("city_only_talks", 0)),
                    "institution_talks": int(row.get("institution_talks", 0)),
                    "matched_city_labels": int(row.get("matched_city_labels", 0)),
                    "unique_cities": str(row.get("unique_cities", "")),
                    "unique_institutions": str(row.get("unique_institutions", "")),
                }
    except Exception:
        pass
    return data


def load_eastern_faculty_alumni():
    rows = {}
    try:
        with open("curation/eastern_faculty_alumni.csv", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                pid = str(row.get("person_id") or "").strip()
                if not pid or str(row.get("status") or "").strip().lower() == "rejected":
                    continue
                rows[pid] = row
    except FileNotFoundError:
        pass
    return rows

def load_theme_mapping():
    mapping = {"by_title": {}, "by_id": {}}
    try:
        with open("analytics_output/theme_codes_final_v2.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (str(row["year"]).strip(), str(row["series"]).strip(), str(row["title"]).strip())
                mapping["by_title"][key] = row["l1"]
                if row.get("presentation_id"):
                    mapping["by_id"][row["presentation_id"]] = row["l1"]
    except FileNotFoundError:
        pass
    return mapping

def load_gumilyov_mapping():
    mapping = {"by_id": {}, "by_key": {}}
    try:
        with open("analytics_output/gumilyov_scale.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (str(row["year"]).strip(), str(row["series_id"]).strip(), str(row["title"]).strip())
                mapping["by_key"][key] = row["gumilyov_level"]
                if row.get("presentation_id"):
                    mapping["by_id"][row["presentation_id"]] = row["gumilyov_level"]
    except FileNotFoundError:
        pass
    return mapping


def load_meso_mapping():
    mapping = {}
    try:
        with open("analytics_output/meso_codes_deepseek.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                pid = str(row.get("presentation_id") or "").strip()
                codes_list = []
                for code in str(row.get("meso_codes") or "").split("|"):
                    c = code.strip()
                    if not c:
                        continue
                    if c == "bengal_bhakti_modernity":
                        codes_list.extend(["bengal", "bhakti_vaishnava"])
                    else:
                        codes_list.append(c)
                if pid and codes_list:
                    mapping[pid] = list(dict.fromkeys(codes_list))
    except FileNotFoundError:
        pass
    return mapping


def gumilyov_level_for(year, series, title, presentation_id=None, source_title=None, raw_title=None):
    manual = CLASSIFICATION_OVERRIDES.get(str(presentation_id or ""), {})
    if manual.get("gumilyov_level"):
        return int(manual["gumilyov_level"])
    if presentation_id and str(presentation_id) in _GUMILYOV_MAPPING["by_id"]:
        return int(_GUMILYOV_MAPPING["by_id"][str(presentation_id)])
    series_id = "1" if "Zograf" in str(series or "") else "2"
    for candidate in (raw_title, title, source_title):
        key = (str(year).strip(), series_id, str(candidate or "").strip())
        if key in _GUMILYOV_MAPPING["by_key"]:
            return int(_GUMILYOV_MAPPING["by_key"][key])
    return None


def meso_codes_for(presentation_id):
    manual = CLASSIFICATION_OVERRIDES.get(str(presentation_id or ""), {})
    if "meso_codes" in manual:
        return list(manual.get("meso_codes") or [])
    return list(_MESO_MAPPING.get(str(presentation_id or ""), []))


def load_tags_mapping():
    mapping = {}
    try:
        with open("article/hypothesis_output/title_keyword_tokens.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                pid = str(row.get("presentation_id") or "").strip()
                tokens = [
                    token.strip()
                    for token in str(row.get("tokens") or row.get("unique_tokens") or "").split("|")
                    if token.strip()
                ]
                if pid and tokens:
                    mapping[pid] = list(dict.fromkeys(tokens))
    except FileNotFoundError:
        pass
    try:
        with open("analytics_output/presentation_tags.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tags = row["tags"].split("|") if row["tags"] else []
                if row["presentation_id"] not in mapping or not mapping[row["presentation_id"]]:
                    mapping[row["presentation_id"]] = tags
    except FileNotFoundError:
        pass
    return mapping

# Pre-load the mappings once globally
_THEME_MAPPING = load_theme_mapping()
_GUMILYOV_MAPPING = load_gumilyov_mapping()
_MESO_MAPPING = load_meso_mapping()
_TAGS_MAPPING = load_tags_mapping()

def get_theme_meta(code):
    """Return dict with ru/en labels for a given L1 code."""
    meta = {
        "history_and_culture": {"ru": "История, этнография и общество", "en": "History, Culture & Society"},
        "religion_and_philosophy": {"ru": "Религия и философия", "en": "Religion & Philosophy"},
        "literature_and_poetry": {"ru": "Литература и поэзия", "en": "Literature & Poetry"},
        "linguistics_and_philology": {"ru": "Лингвистика и филология", "en": "Linguistics & Philology"},
        "art_and_material_culture": {"ru": "Искусство и материальная культура", "en": "Art & Material Culture"},
        "unspecified": {"ru": "Разное / Не классифицировано", "en": "Other / Unspecified"}
    }
    meta.update({code: {"ru": labels[0], "en": labels[1]} for code, labels in THEME_LABEL_OVERRIDES.items()})
    res = meta.get(code)
    if not res:
        res = {"ru": str(code), "en": str(code)}
    res["code"] = code
    return res

def classify_theme(year, series, title, presentation_id=None, fallback_title=None):
    manual = CLASSIFICATION_OVERRIDES.get(str(presentation_id or ""), {})
    code = manual.get("theme_code") or THEME_OVERRIDES_BY_PRESENTATION_ID.get(str(presentation_id or ""))
    if not code:
        code = _THEME_MAPPING.get("by_id", {}).get(str(presentation_id or ""))
    if not code:
        candidates = [title]
        if fallback_title and fallback_title != title:
            candidates.append(fallback_title)
        for candidate in candidates:
            key = (str(year).strip(), str(series).strip(), str(candidate).strip())
            code = _THEME_MAPPING.get("by_title", {}).get(key)
            if code:
                break
    code = code or "unspecified"
    return get_theme_meta(code)


def build_historical_scholars(conn, authority_overrides):
    """Scholar records for `person_kind='historical'` figures (H484, Phase 2).

    These never presented, so they are NOT in `scholars` (which joins presentation_person)
    and must not be -- that list drives the cited count of 268. They are emitted separately,
    as `historical_scholars`, and given memorial profile pages by generate_scholars_pages.

    Every talk-derived field is zeroed/emptied. The dict carries the full participant key
    set so the shared profile renderer (which reads e.g. total_talks, talks, generation_code,
    all_affiliations) never hits a missing key on a zero-talk person.
    """
    cur = conn.cursor()
    person_cols = {r[1] for r in cur.execute("PRAGMA table_info(person)")}
    if "person_kind" not in person_cols:
        return []  # DB predates the H484 schema; nothing to emit.

    disciplines_by_person = defaultdict(list)
    for pid, code, conf in cur.execute(
        "SELECT pd.person_id, d.discipline_id, pd.confidence "
        "FROM person_discipline pd JOIN discipline d ON d.discipline_id = pd.discipline_id "
        "WHERE d.discipline_id != 'unattested' ORDER BY pd.confidence DESC, d.discipline_id"
    ):
        disciplines_by_person[pid].append({"code": code, "confidence": conf})

    roles_by_person = defaultdict(list)
    for pid, role, from_year, to_year, notes in cur.execute(
        "SELECT person_id, role, from_year, to_year, notes FROM person_role"
    ):
        roles_by_person[pid].append(
            {"role": role, "from_year": from_year, "to_year": to_year, "organization": notes}
        )

    scholars = []
    for r in cur.execute(
        "SELECT person_id, display_name, full_name_ru, full_name_en, birth_year, death_year, "
        "degree, degree_year, degree_source_url, source_url, notes "
        "FROM person WHERE person_kind = 'historical' ORDER BY birth_year, display_name"
    ):
        pid, display_name = r[0], r[1]
        full_name_ru = r[2] or display_name
        full_name_en = r[3] or (iso9_transliterate(full_name_ru) if full_name_ru else display_name)
        birth_year, death_year = r[4], r[5]
        cohort = generation_cohort(birth_year)
        scholars.append({
            "id": pid,
            "name": format_to_initials(display_name),
            "normalized_key": None,
            "original_fullname": display_name,
            "full_name_ru": full_name_ru,
            "full_name_en": full_name_en,
            "birth_year": birth_year,
            "generation_code": cohort["code"] if cohort else None,
            "generation_label_ru": cohort["ru"] if cohort else None,
            "generation_label_en": cohort["en"] if cohort else None,
            "death_year": death_year,
            "degree": r[6],
            "degree_year": r[7],
            "degree_source_url": r[8],
            "gender": None,
            "zograf_first": None,
            "zograf_last": None,
            "roerich_first": None,
            "roerich_last": None,
            "dominant_theme": None,
            "thematic_breadth": None,
            "total_talks": 0,
            "zograf_talks": 0,
            "roerich_talks": 0,
            "first_year": None,
            "last_year": None,
            "is_student": False,
            "is_independent": False,
            "is_eastern_faculty_alumnus": False,
            "eastern_faculty_alumnus_status": None,
            "eastern_faculty_alumnus_source_url": None,
            "eastern_faculty_alumnus_note": None,
            "has_changed_affiliations": False,
            "all_affiliations": [],
            "affiliation_notes": [],
            "orcid": None,
            "wikidata": r[9],  # Wikidata entity URL, the memorial figure's source authority
            "elibrary": None,
            "talks": [],
            # Historical-only fields (participants lack these; harmless extra keys).
            "person_kind": "historical",
            "wikidata_source_url": r[9],
            "disciplines": disciplines_by_person.get(pid, []),
            "roles": roles_by_person.get(pid, []),
            "note": r[10],
        })

    if scholars:
        assign_unique_slugs(scholars, authority_overrides)
    return scholars


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    verified_affiliation_spans = load_verified_affiliation_spans()
    eastern_faculty_alumni = load_eastern_faculty_alumni()
    
    # Load ORCID and Wikidata from data_assertion
    cursor.execute("""
        SELECT entity_id, attribute, value 
        FROM data_assertion 
        WHERE entity_type = 'person' AND attribute IN ('orcid', 'wikidata', 'elibrary')
    """)
    lod_assertions = {}
    for eid, attr, val in cursor.fetchall():
        if eid not in lod_assertions:
            lod_assertions[eid] = {}
        lod_assertions[eid][attr] = val

    # Pre-fetch session order mapping
    cursor.execute("""
        SELECT pr.presentation_id, pr.session_id
        FROM presentation pr
        ORDER BY pr.presentation_id ASC
    """)
    pres_session_list = cursor.fetchall()
    session_pres_map = {}
    for pid, sess_id in pres_session_list:
        if sess_id not in session_pres_map:
            session_pres_map[sess_id] = []
        session_pres_map[sess_id].append(pid)
        
    # Compile presenter metadata (student, independent, affiliation change, biographical info)
    # Degree columns exist only after a rebuild with the updated schema; detect
    # them so this script also runs against an older DB without crashing.
    person_cols = {r[1] for r in cursor.execute("PRAGMA table_info(person)").fetchall()}
    has_degree = {"degree", "degree_year", "degree_source_url"} <= person_cols
    degree_select = ", degree, degree_year, degree_source_url" if has_degree else ""
    cursor.execute(f"SELECT person_id, display_name, birth_year, death_year, full_name_ru, full_name_en, normalized_key{degree_select} FROM person")
    persons_raw = cursor.fetchall()

    person_meta = {}
    for r_p in persons_raw:
        pid, display_name = r_p[0], r_p[1]
        birth_year = r_p[2]
        death_year = r_p[3]
        full_name_ru = r_p[4]
        full_name_en = r_p[5]
        normalized_key = r_p[6]
        degree = r_p[7] if has_degree else None
        degree_year = r_p[8] if has_degree else None
        degree_source_url = r_p[9] if has_degree else None
        eastern_faculty_row = eastern_faculty_alumni.get(pid, {})

        std_name = format_to_initials(display_name)
        
        # Check student and independent status based on all historical affiliations
        cursor.execute("SELECT affiliation_text_raw FROM presentation_person WHERE person_id = ?", (pid,))
        affils = [r[0] for r in cursor.fetchall() if r[0]]
        
        is_student = False
        is_independent = False
        for a in affils:
            a_low = a.lower()
            if any(term in a_low for term in ["студент", "аспирант", "магистрант", "бакалавр", "student", "postgraduate", "phd"]):
                is_student = True
            if any(term in a_low for term in ["независимый", "ни ", " ни", "independent", "без аффилиации"]):
                is_independent = True
                
        # Check if affiliation changed over the years
        cursor.execute("""
            SELECT DISTINCT pp.affiliation_text_raw
            FROM presentation_person pp
            WHERE pp.person_id = ? AND pp.affiliation_text_raw IS NOT NULL AND pp.affiliation_text_raw != ''
        """, (pid,))
        unique_affils = [r[0] for r in cursor.fetchall()]
        has_changed_affiliations = len(unique_affils) > 1
        
        # Calculate Gender
        gender = classify_gender(full_name_ru, display_name)
        
        # Calculate Zograf first/last years seen
        cursor.execute("""
            SELECT MIN(e.year), MAX(e.year)
            FROM presentation pr
            JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            WHERE pp.person_id = ? AND e.event_series_id = 1
        """, (pid,))
        z_res = cursor.fetchone()
        zograf_first = z_res[0] if z_res and z_res[0] else None
        zograf_last = z_res[1] if z_res and z_res[1] else None
        
        # Calculate Roerich first/last years seen
        cursor.execute("""
            SELECT MIN(e.year), MAX(e.year)
            FROM presentation pr
            JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            WHERE pp.person_id = ? AND e.event_series_id = 2
        """, (pid,))
        r_res = cursor.fetchone()
        roerich_first = r_res[0] if r_res and r_res[0] else None
        roerich_last = r_res[1] if r_res and r_res[1] else None
        
        person_meta[pid] = {
            "std_name": std_name,
            "normalized_key": normalized_key,
            "is_student": is_student,
            "is_independent": is_independent,
            "has_changed_affiliations": has_changed_affiliations,
            "all_affiliations": unique_affils,
            "birth_year": birth_year,
            "death_year": death_year,
            "full_name_ru": full_name_ru,
            "full_name_en": full_name_en or (iso9_transliterate(full_name_ru) if full_name_ru else None),
            "gender": gender,
            "zograf_first": zograf_first,
            "zograf_last": zograf_last,
            "roerich_first": roerich_first,
            "roerich_last": roerich_last,
            "degree": degree,
            "degree_year": degree_year,
            "degree_source_url": degree_source_url,
            "is_eastern_faculty_alumnus": bool(eastern_faculty_row),
            "eastern_faculty_alumnus_status": eastern_faculty_row.get("status"),
            "eastern_faculty_alumnus_source_url": eastern_faculty_row.get("source_url"),
            "eastern_faculty_alumnus_note": eastern_faculty_row.get("source_note"),
            "orcid": lod_assertions.get(pid, {}).get("orcid"),
            "wikidata": lod_assertions.get(pid, {}).get("wikidata"),
            "elibrary": lod_assertions.get(pid, {}).get("elibrary")
        }
    
    # Load video media keyed by presentation_id (so each talk can render its YouTube link)
    cursor.execute("""
        SELECT attached_to_id, media_url, media_title
        FROM media
        WHERE attached_to_type = 'presentation' AND media_type = 'video'
    """)
    videos_by_pres = {}
    for pres_id, url, title in cursor.fetchall():
        videos_by_pres.setdefault(pres_id, []).append({"url": url, "title": title})

    # 1. Fetch all scholars
    cursor.execute("""
        SELECT
            p.person_id,
            p.display_name,
            p.normalized_key,
            COUNT(DISTINCT pr.presentation_id) as total_talks,
            SUM(CASE WHEN e.event_series_id = 1 THEN 1 ELSE 0 END) as zograf_talks,
            SUM(CASE WHEN e.event_series_id = 2 THEN 1 ELSE 0 END) as roerich_talks,
            MIN(e.year) as first_year_seen,
            MAX(e.year) as last_year_seen
        FROM person p
        JOIN presentation_person pp ON pp.person_id = p.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        GROUP BY p.person_id
        ORDER BY total_talks DESC, p.display_name ASC
    """)
    scholars_raw = cursor.fetchall()
    
    geo_counts = {}
    scholars = []
    for r in scholars_raw:
        pid = r[0]
        meta = person_meta[pid]
        
        # Get all talks for this scholar
        cursor.execute("""
            SELECT 
                pr.presentation_id,
                pr.title, 
                e.year, 
                es.series_name_en, 
                pp.affiliation_text_raw,
                pr.is_online,
                ed.calendar_date,
                s.session_title,
                s.time_text_raw,
                s.session_id,
                pr.source_url
            FROM presentation pr
            JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            JOIN event_series es ON es.event_series_id = e.event_series_id
            WHERE pp.person_id = ?
            ORDER BY e.year DESC
        """, (pid,))
        talks_raw = cursor.fetchall()
        
        talks = []
        theme_counts = {}
        for t in talks_raw:
            pres_id, title, year, series, affiliation, is_online, calendar_date, session_title, time_text, sess_id, source_url = t
            
            # Clean public titles while retaining embedded source metadata separately.
            source_title = clean_title(title)
            public_source_title, embedded_affiliation = split_leading_affiliation(source_title)
            cleaned_title = canonical_title(pres_id, public_source_title)
            affiliation_meta = public_affiliation(
                pid, year, affiliation, embedded_affiliation, verified_affiliation_spans
            )
            displayed_affiliation = affiliation_meta["display"]
            
            # Classify theme
            theme = classify_theme(year, series, cleaned_title, pres_id, source_title)
            t_code = theme["code"]
            theme_counts[t_code] = theme_counts.get(t_code, 0) + 1
            
            # Gumilyov scale
            g_scale = gumilyov_level_for(year, series, cleaned_title, pres_id, source_title, title)
            
            # Day of the week calculation
            day_of_week = get_day_of_week(calendar_date)
            
            # Geography extraction
            geo = extract_geography(displayed_affiliation or affiliation)
            if geo["ru"] != "Не указана":
                gkey = geo["ru"]
                if gkey not in geo_counts:
                    geo_counts[gkey] = {"ru": geo["ru"], "en": geo["en"], "count": 0}
                geo_counts[gkey]["count"] += 1
            
            # Position order in session
            s_list = session_pres_map.get(sess_id, [pres_id])
            try:
                order_idx = s_list.index(pres_id)
            except ValueError:
                order_idx = 0
            
            is_first = (order_idx == 0)
            is_last = (order_idx == len(s_list) - 1)
            
            p_tags = _TAGS_MAPPING.get(str(pres_id), [])
            manual_classification = CLASSIFICATION_OVERRIDES.get(str(pres_id), {})
            
            talks.append({
                "presentation_id": pres_id,
                "title": cleaned_title,
                "title_editorial_note": TITLE_EDITORIAL_NOTES_BY_PRESENTATION_ID.get(str(pres_id)),
                "year": year,
                "series": series,
                "affiliation": displayed_affiliation,
                "affiliation_reported": affiliation,
                "affiliation_basis": affiliation_meta["basis"],
                "affiliation_source_url": affiliation_meta["source_url"],
                "affiliation_note": affiliation_meta["note"],
                "geography": geo,
                "theme": theme,
                "gumilyov_scale": g_scale,  # legacy alias of argument_level
                "argument_level": g_scale,
                "tags": p_tags,
                "meso_codes": meso_codes_for(pres_id),
                "classification_reason": manual_classification.get("reason"),
                "classification_reviewed": bool(manual_classification),
                "is_online": bool(is_online),
                "date": calendar_date,
                "day_of_week": day_of_week,
                "session_title": session_title,
                "time_interval": normalize_time_interval(time_text, "Не указано"),
                "is_first_talk": is_first,
                "is_last_talk": is_last,
                "order_in_session": order_idx + 1,
                "total_in_session": len(s_list),
                "source_url": source_url,
                "videos": videos_by_pres.get(pres_id, [])
            })
            
        # Determine dominant theme and academic breadth
        dominant_theme = None
        thematic_breadth = "Specialized"
        
        if theme_counts:
            dominant_pool = {k: v for k, v in theme_counts.items() if k != "unspecified"} or theme_counts
            sorted_themes = sorted(dominant_pool.items(), key=lambda x: (-x[1], x[0]))
            dominant_theme = sorted_themes[0][0]
            if len(theme_counts) > 1:
                thematic_breadth = "Interdisciplinary"
            
        cohort = generation_cohort(meta["birth_year"])
        public_affiliations = aggregate_public_affiliations(talks)
        affiliation_notes = aggregate_affiliation_notes(talks)
        scholars.append({
            "id": pid,
            "name": meta["std_name"],
            "normalized_key": meta["normalized_key"],
            "original_fullname": r[1],
            "full_name_ru": meta["full_name_ru"] or meta["std_name"],
            "full_name_en": meta["full_name_en"] or iso9_transliterate(meta["full_name_ru"]) if meta.get("full_name_ru") else meta["std_name"],
            "birth_year": meta["birth_year"],
            "generation_code": cohort["code"] if cohort else None,
            "generation_label_ru": cohort["ru"] if cohort else None,
            "generation_label_en": cohort["en"] if cohort else None,
            "death_year": meta["death_year"],
            "degree": meta.get("degree"),
            "degree_year": meta.get("degree_year"),
            "degree_source_url": meta.get("degree_source_url"),
            "gender": meta["gender"],
            "zograf_first": meta["zograf_first"],
            "zograf_last": meta["zograf_last"],
            "roerich_first": meta["roerich_first"],
            "roerich_last": meta["roerich_last"],
            "dominant_theme": dominant_theme,
            "thematic_breadth": thematic_breadth,
            "total_talks": r[3],
            "zograf_talks": r[4],
            "roerich_talks": r[5],
            "first_year": r[6],
            "last_year": r[7],
            "is_student": meta["is_student"],
            "is_independent": meta["is_independent"],
            "is_eastern_faculty_alumnus": meta["is_eastern_faculty_alumnus"],
            "eastern_faculty_alumnus_status": meta.get("eastern_faculty_alumnus_status"),
            "eastern_faculty_alumnus_source_url": meta.get("eastern_faculty_alumnus_source_url"),
            "eastern_faculty_alumnus_note": meta.get("eastern_faculty_alumnus_note"),
            "has_changed_affiliations": len(public_affiliations) > 1,
            "all_affiliations": public_affiliations,
            "affiliation_notes": affiliation_notes,
            "orcid": meta.get("orcid"),
            "wikidata": meta.get("wikidata"),
            "elibrary": meta.get("elibrary"),
            "talks": talks
        })
        
    # Assign SEO-friendly URL slugs (Latin transliteration with manual overrides
    # from authority_ids.json -> persons[id].preferred_latin_name).
    authority_overrides = load_authority_overrides()
    assign_unique_slugs(scholars, authority_overrides)

    # Historical figures (H484): emitted separately from `scholars` so the cited count of
    # 268 speakers is untouched; they get memorial profile pages of their own.
    historical_scholars = build_historical_scholars(conn, authority_overrides)

    # Load teacher-student relationships
    rels = gen.load_relationships(include_candidates=False)
    advisor_map = gen.by_advisor(rels)
    student_map = gen.by_student(rels)
    
    scholar_by_key = {s["normalized_key"]: s for s in scholars if s.get("normalized_key")}
    
    for s in scholars:
        s_key = s.get("normalized_key")
        s["advisors"] = []
        s["students"] = []
        
        if s_key:
            # Advisors of this scholar (where this scholar is student)
            for r in student_map.get(s_key, []):
                adv_slug = None
                adv_id = None
                if r.advisor_key in scholar_by_key:
                    adv_slug = scholar_by_key[r.advisor_key]["url_slug"]
                    adv_id = scholar_by_key[r.advisor_key]["id"]
                s["advisors"].append({
                    "name": r.advisor_name,
                    "key": r.advisor_key,
                    "relationship_type": r.relationship_type,
                    "period_start": r.period_start,
                    "period_end": r.period_end,
                    "evidence_url": r.evidence_url,
                    "evidence_note": r.evidence_note,
                    "notes": r.notes,
                    "slug": adv_slug,
                    "id": adv_id
                })
                
            # Students of this scholar (where this scholar is advisor)
            for r in advisor_map.get(s_key, []):
                stud_slug = None
                stud_id = None
                if r.student_key in scholar_by_key:
                    stud_slug = scholar_by_key[r.student_key]["url_slug"]
                    stud_id = scholar_by_key[r.student_key]["id"]
                s["students"].append({
                    "name": r.student_name,
                    "key": r.student_key,
                    "relationship_type": r.relationship_type,
                    "period_start": r.period_start,
                    "period_end": r.period_end,
                    "evidence_url": r.evidence_url,
                    "evidence_note": r.evidence_note,
                    "notes": r.notes,
                    "slug": stud_slug,
                    "id": stud_id
                })

    # Discipline facet (H473). Drives the "Indology in Russia" umbrella section and
    # the "Sanskritology in Russia" facet page, plus the discipline chips on profiles.
    discipline_labels = {
        code: {"label_ru": ru, "label_en": en, "parent": parent, "status": status}
        for code, ru, en, parent, status in cursor.execute(
            "SELECT discipline_id, label_ru, label_en, parent_discipline_id, status FROM discipline"
        )
    }
    disciplines_by_person = {}
    for person_id, code, confidence, method, evidence in cursor.execute(
        "SELECT person_id, discipline_id, confidence, method, evidence "
        "FROM person_discipline ORDER BY confidence DESC, discipline_id"
    ):
        meta = discipline_labels.get(code, {})
        disciplines_by_person.setdefault(person_id, []).append({
            "code": code,
            "label_ru": meta.get("label_ru", code),
            "label_en": meta.get("label_en"),
            "status": meta.get("status"),
            "confidence": confidence,
            "method": method,
            "evidence": evidence,
        })
    for s in scholars:
        s["disciplines"] = disciplines_by_person.get(s["id"], [])

    # Load city-to-institution trajectory audit
    city_trajectory = load_city_trajectory()
    for s in scholars:
        pid = s.get("id", "")
        traj = city_trajectory.get(pid, {})
        s["affiliation_coverage_pct"] = traj.get("coverage_pct", 100.0)
        s["affiliation_city_only_talks"] = traj.get("city_only_talks", 0)
        s["affiliation_institution_talks"] = traj.get("institution_talks", 0)
        s["affiliation_matched_city_labels"] = traj.get("matched_city_labels", 0)
        # Only show for scholars with city-only labels and less than 100% coverage
        s["show_affiliation_transparency"] = (
            s["affiliation_city_only_talks"] > 0 and s["affiliation_coverage_pct"] < 100.0
        )

    # Compute network metrics per scholar (co-authors, session co-presence, thematic breadth)
    cursor.execute("""
        SELECT pp.person_id,
               COUNT(DISTINCT CASE WHEN pp2.role='coauthor' THEN pp2.person_id END) as coauthors,
               COUNT(DISTINCT CASE WHEN pp2.role='speaker' AND pp2.person_id != pp.person_id THEN pp2.person_id END) as session_mates
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        LEFT JOIN presentation_person pp2 ON pp2.presentation_id = pp.presentation_id AND pp2.person_id != pp.person_id
        WHERE pp.role = 'speaker'
        GROUP BY pp.person_id
    """)
    network_stats = {row[0]: {"coauthors": row[1], "session_mates": row[2]} for row in cursor.fetchall()}

    for s in scholars:
        pid = s.get("id", "")
        stats = network_stats.get(pid, {})
        s["network_coauthor_count"] = stats.get("coauthors", 0)
        s["network_session_mate_count"] = stats.get("session_mates", 0)
        # Thematic breadth badge
        s["show_thematic_badge"] = s.get("thematic_breadth") == "Interdisciplinary"

    slug_by_id = {s["id"]: s["url_slug"] for s in scholars}

    # 2. Fetch all timeline talks grouped by Year and Series
    cursor.execute("""
        SELECT 
            pr.presentation_id,
            e.year,
            es.series_name_en,
            p.person_id,
            pp.affiliation_text_raw,
            pr.title,
            pr.is_online,
            v.display_name,
            ed.day_label_raw,
            s.session_title,
            ed.calendar_date,
            s.time_text_raw,
            s.session_id,
            e.program_last_updated,
            e.source_url
        FROM presentation pr
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN venue v ON v.venue_id = edv.venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        ORDER BY e.year DESC, es.event_series_id ASC, ed.day_number ASC, pr.presentation_id ASC
    """)
    timeline_raw = cursor.fetchall()
    
    timeline = {}
    for r in timeline_raw:
        pres_id, year_val, series, pid, affiliation, title, is_online, venue_name, day_label, session_title, calendar_date, time_text, sess_id, program_last_updated, source_url = r
        year = str(year_val)
        meta = person_meta[pid]
        
        if year not in timeline:
            timeline[year] = {"Zograf": [], "Roerich": []}
        
        # Day of the week
        day_of_week = get_day_of_week(calendar_date)
        
        # Order in session
        s_list = session_pres_map.get(sess_id, [pres_id])
        try:
            order_idx = s_list.index(pres_id)
        except ValueError:
            order_idx = 0
            
        is_first = (order_idx == 0)
        is_last = (order_idx == len(s_list) - 1)
        
        series_key = "Zograf" if "Zograf" in series else "Roerich"
        # Clean public titles while retaining embedded source metadata separately.
        source_title = clean_title(title)
        public_source_title, embedded_affiliation = split_leading_affiliation(source_title)
        cleaned_title = canonical_title(pres_id, public_source_title)
        affiliation_meta = public_affiliation(
            pid, year_val, affiliation, embedded_affiliation, verified_affiliation_spans
        )
        displayed_affiliation = affiliation_meta["display"]
        geo = extract_geography(displayed_affiliation or affiliation)
        
        # Classify theme
        theme = classify_theme(year_val, series, cleaned_title, pres_id, source_title)
        
        # Gumilyov scale
        g_scale = gumilyov_level_for(year_val, series, cleaned_title, pres_id, source_title, title)

        p_tags = _TAGS_MAPPING.get(str(pres_id), [])
        manual_classification = CLASSIFICATION_OVERRIDES.get(str(pres_id), {})

        series_key = "Zograf" if "Zograf" in series else "Roerich"
        timeline[year][series_key].append({
            "presentation_id": pres_id,
            "speaker": meta["std_name"],
            "speaker_original": meta["std_name"],
            "speaker_id": pid,
            "speaker_slug": slug_by_id.get(pid),
            "is_student": meta["is_student"],
            "is_independent": meta["is_independent"],
            "affiliation": displayed_affiliation,
            "affiliation_reported": affiliation,
            "affiliation_basis": affiliation_meta["basis"],
            "affiliation_source_url": affiliation_meta["source_url"],
            "affiliation_note": affiliation_meta["note"],
            "geography": geo,
            "title": cleaned_title,
            "title_editorial_note": TITLE_EDITORIAL_NOTES_BY_PRESENTATION_ID.get(str(pres_id)),
            "theme": theme,
            "gumilyov_scale": g_scale,  # legacy alias of argument_level
            "argument_level": g_scale,
            "tags": p_tags,
            "meso_codes": meso_codes_for(pres_id),
            "classification_reason": manual_classification.get("reason"),
            "classification_reviewed": bool(manual_classification),
            "is_online": bool(is_online),
            "venue": venue_name,
            "day": day_label,
            "date": calendar_date,
            "day_of_week": day_of_week,
            "session": session_title,
            "time_interval": normalize_time_interval(time_text, "Не указано"),
            "program_last_updated": program_last_updated,
            "source_url": source_url,
            "is_first_talk": is_first,
            "is_last_talk": is_last,
            "order_in_session": order_idx + 1,
            "total_in_session": len(s_list),
            "videos": videos_by_pres.get(pres_id, [])
        })

    presentation_slugs = build_presentation_slug_map(
        talk
        for year_data in timeline.values()
        for series_talks in year_data.values()
        for talk in series_talks
    )
    for scholar in scholars:
        for talk in scholar["talks"]:
            talk["public_path"] = f"p/{presentation_slugs[talk['presentation_id']]}.html"
    for year_data in timeline.values():
        for series_talks in year_data.values():
            for talk in series_talks:
                talk["public_path"] = f"p/{presentation_slugs[talk['presentation_id']]}.html"

    # 3. Calculate year-by-year statistics for charts
    cursor.execute("""
        SELECT e.year, 
               SUM(CASE WHEN e.event_series_id = 1 THEN 1 ELSE 0 END) as zograf_talks,
               SUM(CASE WHEN e.event_series_id = 2 THEN 1 ELSE 0 END) as roerich_talks
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        GROUP BY e.year
        ORDER BY e.year ASC
    """)
    stats_raw = cursor.fetchall()
    stats = []
    for r in stats_raw:
        stats.append({
            "year": r[0],
            "zograf": r[1],
            "roerich": r[2],
            "total": r[1] + r[2]
        })

    # Format geography stats
    try:
        with open("assets/data/geography.json", encoding="utf-8") as f:
            geo_coordinates = json.load(f).get("coordinates", {})
    except FileNotFoundError:
        geo_coordinates = {}
    
    geography_stats = list(geo_counts.values())
    for g in geography_stats:
        coords = geo_coordinates.get(g["ru"], None)
        if coords:
            g["lat"] = coords["lat"]
            g["lon"] = coords["lon"]
        else:
            g["lat"] = None
            g["lon"] = None
            
    geography_stats.sort(key=lambda x: x["count"], reverse=True)

    # 4. Calculate Gender and Age stats
    male_count = sum(1 for s in scholars if s["gender"] == "M")
    female_count = sum(1 for s in scholars if s["gender"] == "F")
    gender_stats = {
        "M": male_count,
        "F": female_count,
        "U": len(scholars) - male_count - female_count
    }
    
    age_groups = {
        "young": 0,       # < 35
        "mid_career": 0,  # 35-50
        "senior": 0,      # 50-70
        "elders": 0       # 70+
    }
    for s in scholars:
        if s["birth_year"]:
            try:
                age = 2026 - int(s["birth_year"])
                if age < 35:
                    age_groups["young"] += 1
                elif age <= 50:
                    age_groups["mid_career"] += 1
                elif age <= 70:
                    age_groups["senior"] += 1
                else:
                    age_groups["elders"] += 1
            except Exception:
                pass

    generation_stats = [
        {
            "code": cohort["code"],
            "label_ru": cohort["ru"],
            "label_en": cohort["en"],
            "count": sum(1 for item in scholars if item.get("generation_code") == cohort["code"]),
        }
        for cohort in GENERATION_COHORTS
    ]
    unknown_generation_count = sum(1 for item in scholars if not item.get("generation_code"))
    if unknown_generation_count:
        generation_stats.append({
            "code": "unknown",
            "label_ru": "Год рождения не установлен",
            "label_en": "Birth year not established",
            "count": unknown_generation_count,
        })

    # Extract co-occurrence collaboration network
    network_nodes = []
    for s in scholars:
        series = "Both"
        if s["zograf_talks"] > 0 and s["roerich_talks"] == 0:
            series = "Zograf"
        elif s["roerich_talks"] > 0 and s["zograf_talks"] == 0:
            series = "Roerich"
            
        network_nodes.append({
            "id": s["id"],
            "slug": s["url_slug"],
            "name": s["name"],
            "talks": s["total_talks"],
            "theme": s["dominant_theme"] or "History",
            "series": series
        })

    cursor.execute("""
        SELECT pp1.person_id, pp2.person_id, COUNT(DISTINCT p1.session_id) as weight
        FROM presentation_person pp1
        JOIN presentation p1 ON pp1.presentation_id = p1.presentation_id
        JOIN presentation p2 ON p1.session_id = p2.session_id AND p1.presentation_id != p2.presentation_id
        JOIN presentation_person pp2 ON p2.presentation_id = pp2.presentation_id
        WHERE pp1.person_id < pp2.person_id
        GROUP BY pp1.person_id, pp2.person_id
    """)
    links_raw = cursor.fetchall()
    network_links = []
    for p1, p2, w in links_raw:
        network_links.append({
            "source": p1,
            "target": p2,
            "weight": w
        })


    # Extract co-occurrence collaboration network
    network_nodes = []
    for s in scholars:
        series = "Both"
        if s["zograf_talks"] > 0 and s["roerich_talks"] == 0:
            series = "Zograf"
        elif s["roerich_talks"] > 0 and s["zograf_talks"] == 0:
            series = "Roerich"
            
        network_nodes.append({
            "id": s["id"],
            "slug": s["url_slug"],
            "name": s["name"],
            "talks": s["total_talks"],
            "theme": s["dominant_theme"] or "History",
            "series": series
        })

    cursor.execute("""
        SELECT pp1.person_id, pp2.person_id, COUNT(DISTINCT p1.session_id) as weight, GROUP_CONCAT(e.year)
        FROM presentation_person pp1
        JOIN presentation p1 ON pp1.presentation_id = p1.presentation_id
        JOIN presentation p2 ON p1.session_id = p2.session_id AND p1.presentation_id != p2.presentation_id
        JOIN session s ON p1.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN presentation_person pp2 ON p2.presentation_id = pp2.presentation_id
        WHERE pp1.person_id < pp2.person_id
        GROUP BY pp1.person_id, pp2.person_id
    """)
    links_raw = cursor.fetchall()
    network_links = []
    for p1, p2, w, years_str in links_raw:
        years = list(set(int(y) for y in str(years_str).split(','))) if years_str else []
        network_links.append({
            "source": p1,
            "target": p2,
            "weight": w,
            "years": years
        })

    # 5. Affiliations Leaderboard
    inst_map = {}
    for s in scholars:
        # Keep track of unique scholars per inst
        for t in s["talks"]:
            norm = normalize_affiliation(t["affiliation"])
            if norm:
                if norm not in inst_map:
                    inst_map[norm] = {"name": norm, "total_talks": 0, "scholars_set": set()}
                inst_map[norm]["total_talks"] += 1
                inst_map[norm]["scholars_set"].add(s["id"])
                
    institutions_stats = []
    for k, v in inst_map.items():
        institutions_stats.append({
            "name": k,
            "total_talks": v["total_talks"],
            "unique_scholars": len(v["scholars_set"])
        })
    institutions_stats.sort(key=lambda x: x["total_talks"], reverse=True)

    # 6. Word Cloud (N-gram)
    import re
    stop_words = set(['в', 'на', 'и', 'с', 'по', 'к', 'для', 'о', 'из', 'от', 'за', 'до', 'как', 'не', 'что', 'или', 'а', 'же', 'то', 'у', 'об', 'это', 'при', 'он', 'его', 'было', 'быть', 'так', 'только', 'этом', 'ли', 'бы', 'их', 'ее', 'если', 'все', 'во', 'мы', 'нам', 'под', 'над', 'проблема', 'вопрос', 'исследование', 'текст', 'перевод', 'анализ', 'опыт', 'некоторые', 'книги', 'слова', 'язык', 'языка', 'словарь', 'история', 'век', 'года', 'проблемы', 'книга', 'текста', 'тексты', 'the', 'of', 'and', 'in', 'to', 'a', 'on', 'for', 'with', 'by', 'an', 'as', 'at', 'from'])
    word_freq = {}
    for s in scholars:
        for t in s["talks"]:
            # Extract words
            words = re.findall(r'[а-яА-Яa-zA-Z]{4,}', t["title"].lower())
            for w in words:
                if w not in stop_words:
                    word_freq[w] = word_freq.get(w, 0) + 1
    
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:60]
    word_cloud = [{"text": w[0], "weight": w[1]} for w in top_words]

    # Summary values are used by the dashboard, publication pages, and validation.
    total_presentations = sum(len(year_data["Zograf"]) + len(year_data["Roerich"]) for year_data in timeline.values())
    unique_presentations = conn.execute("SELECT COUNT(*) FROM presentation").fetchone()[0]
    stat_years = [row["year"] for row in stats]
    summary = {
        "total_scholars": len(scholars),
        "total_presentations": total_presentations,
        "unique_presentations": unique_presentations,
        "author_participations": total_presentations,
        "total_events": sum(1 for _ in conn.execute("SELECT 1 FROM event")),
        "years_covered": len(stat_years),
        "start_year": min(stat_years) if stat_years else None,
        "end_year": max(stat_years) if stat_years else None,
        "overlap_scholars": sum(1 for s in scholars if s["zograf_talks"] > 0 and s["roerich_talks"] > 0),
        "zograf_only_scholars": sum(1 for s in scholars if s["zograf_talks"] > 0 and s["roerich_talks"] == 0),
        "roerich_only_scholars": sum(1 for s in scholars if s["roerich_talks"] > 0 and s["zograf_talks"] == 0)
    }

    # Write as a javascript module file
    site_data = {
        "schema_version": DATA_SCHEMA_VERSION,
        "generated": datetime.date.today().isoformat(),
        "build": {
            "source": "IndologyScholars",
            "pipeline_version": PIPELINE_VERSION,
            "generator": "generate_site_data.py"
        },
        "summary": summary,
        "scholars": scholars,
        "historical_scholars": historical_scholars,
        "timeline": timeline,
        "stats": stats,
        "geography_stats": geography_stats,
        "gender_stats": gender_stats,
        "age_stats": age_groups,
        "generation_stats": generation_stats,
        "institutions_stats": institutions_stats,
        "word_cloud": word_cloud,
        "network": {
            "nodes": network_nodes,
            "links": network_links
        }
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(site_data, f, ensure_ascii=False, separators=(",", ":"))

    # Generate optimized chunks for performance
    scholars_summary = []
    for s in scholars:
        s_copy = dict(s)
        s_copy.pop("talks", None)
        scholars_summary.append(s_copy)

    site_data_summary = {
        "schema_version": DATA_SCHEMA_VERSION,
        "generated": datetime.date.today().isoformat(),
        "build": site_data["build"],
        "summary": summary,
        "stats": stats,
        "geography_stats": geography_stats,
        "gender_stats": gender_stats,
        "age_stats": age_groups,
        "generation_stats": generation_stats,
        "institutions_stats": institutions_stats,
        "word_cloud": word_cloud,
        "scholars": scholars_summary
    }

    with open("site_data_summary.json", "w", encoding="utf-8") as f:
        json.dump(site_data_summary, f, ensure_ascii=False, separators=(",", ":"))

    with open("site_data_scholars.json", "w", encoding="utf-8") as f:
        json.dump(scholars, f, ensure_ascii=False, separators=(",", ":"))

    with open("site_data_timeline.json", "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, separators=(",", ":"))

    # Write separate timeline files per year
    for year, year_data in timeline.items():
        with open(f"site_data_timeline_{year}.json", "w", encoding="utf-8") as f:
            json.dump(year_data, f, ensure_ascii=False, separators=(",", ":"))

    with open("site_data_network.json", "w", encoding="utf-8") as f:
        json.dump(site_data["network"], f, ensure_ascii=False, separators=(",", ":"))

    print(f"Successfully generated JSON data payload in {OUTPUT_FILE} and optimized split chunks!")
    conn.close()

if __name__ == "__main__":
    main()
