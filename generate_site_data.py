import sqlite3
import json
import datetime
import re

from publication_helpers import GENERATION_COHORTS, assign_unique_slugs, generation_cohort, load_authority_overrides, normalize_time_interval
from title_normalization import THEME_OVERRIDES_BY_PRESENTATION_ID, canonical_title

DB_PATH = "conferences.db"
OUTPUT_FILE = "site_data.json"
DATA_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "2026-05-24"

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

def extract_geography(affiliation_text):
    if not affiliation_text:
        return {"ru": "Не указана", "en": "Not specified"}
    aff_low = affiliation_text.lower()
    
    cities = [
        ("санкт-петербург", "Санкт-Петербург", "St. Petersburg"),
        ("спб", "Санкт-Петербург", "St. Petersburg"),
        ("ленинград", "Санкт-Петербург", "St. Petersburg"),
        ("москва", "Москва", "Moscow"),
        ("краснодар", "Краснодар", "Krasnodar"),
        ("нижний новгород", "Нижний Новгород", "Nizhny Novgorod"),
        ("томск", "Томск", "Tomsk"),
        ("новосибирск", "Новосибирск", "Novosibirsk"),
        ("владивосток", "Владивосток", "Vladivostok"),
        ("улан-удэ", "Улан-Удэ", "Ulan-Ude"),
        ("казань", "Казань", "Kazan"),
        ("пенза", "Пенза", "Penza"),
        ("обнинск", "Обнинск", "Obninsk"),
        ("элиста", "Элиста", "Elista"),
        ("копенгаген", "Копенгаген", "Copenhagen"),
        ("copenhagen", "Копенгаген", "Copenhagen"),
        ("тарту", "Тарту", "Tartu"),
        ("tartu", "Тарту", "Tartu"),
        ("вильнюс", "Вильнюс", "Vilnius"),
        ("vilnius", "Вильнюс", "Vilnius"),
        ("париж", "Париж", "Paris"),
        ("paris", "Париж", "Paris"),
        ("оксфорд", "Оксфорд", "Oxford"),
        ("oxford", "Оксфорд", "Oxford"),
        ("дели", "Дели", "Delhi"),
        ("delhi", "Дели", "Delhi")
    ]
    
    for keyword, ru, en in cities:
        if keyword in aff_low:
            return {"ru": ru, "en": en}
            
    return {"ru": "Не указана", "en": "Not specified"}

def clean_title(title):
    if not title:
        return ""
    # Strip (онлайн), [онлайн], (он-лайн), (online), [online], ( zoom ), [ zoom ], case insensitive
    cleaned = re.sub(r'\s*[\(\[][оО]н[-]?лайн[\)\]]\s*', ' ', title)
    cleaned = re.sub(r'\s*[\(\[][oO]nline[\)\]]\s*', ' ', cleaned)
    cleaned = re.sub(r'\s*[\(\[][zZ]oom[\)\]]\s*', ' ', cleaned)
    # Remove multiple spaces and strip
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def classify_gender(full_name_ru, display_name):
    name_to_check = (full_name_ru or display_name or "").strip()
    parts = name_to_check.split()
    
    # 1. Patronymics check
    for p in parts:
        p_low = p.lower()
        if p_low.endswith(('вна', 'евна', 'овна', 'ична', 'инична')):
            return "F"
        if p_low.endswith(('вич', 'евич', 'ович', 'ич', 'чич')):
            return "M"
            
    # 2. First name check
    female_first_names = ["маргарита", "наталия", "надежда", "елена", "ирина", "ольга", "татьяна", "анна", "мария", "софия", "евгения", "галина", "светлана", "людмила", "александра", "екатерина", "юлия", "любовь", "нина", "дарья", "лариса", "ксен", "ярослав", "вера", "тамара", "алена", "виктория", "марина", "жанна", "светлана", "надежда", "марианна"]
    male_first_names = ["михаил", "бабасан", "павел", "андрей", "иван", "сергей", "алексей", "дмитрий", "владимир", "николай", "александр", "петр", "федор", "степан", "григорий", "ярослав", "василий", "георгий", "юрий", "максим", "кирилл", "артем", "роман", "евгений", "виктор", "леонид", "олег", "игорь", "святослав", "марцис", "макс", "эрман", "никита", "семен"]
    
    for p in parts:
        p_low = p.lower()
        if p_low in female_first_names:
            return "F"
        if p_low in male_first_names:
            return "M"
            
    # 3. Last name endings check
    for p in parts:
        p_low = p.lower()
        if p_low.endswith(('ова', 'ева', 'ина', 'ая', 'ына')):
            return "F"
        if p_low.endswith(('ов', 'ев', 'ин', 'ий', 'ын')):
            return "M"
            
    # Guess based on last letter of first word (usually last name or first name)
    if parts:
        last_letter = parts[0][-1].lower()
        if last_letter in ['а', 'я', 'и']:
            return "F"
            
    return "M"

import csv

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
    mapping = {}
    try:
        with open("analytics_output/gumilyov_scale.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (str(row["year"]).strip(), str(row["series_id"]).strip(), str(row["title"]).strip())
                mapping[key] = row["gumilyov_level"]
    except FileNotFoundError:
        pass
    return mapping


def gumilyov_level_for(year, series, title, source_title=None, raw_title=None):
    series_id = "1" if "Zograf" in str(series or "") else "2"
    for candidate in (raw_title, title, source_title):
        key = (str(year).strip(), series_id, str(candidate or "").strip())
        if key in _GUMILYOV_MAPPING:
            return int(_GUMILYOV_MAPPING[key])
    return 2

def load_tags_mapping():
    mapping = {}
    try:
        with open("analytics_output/presentation_tags.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tags = row["tags"].split("|") if row["tags"] else []
                mapping[row["presentation_id"]] = tags
    except FileNotFoundError:
        pass
    return mapping

# Pre-load the mappings once globally
_THEME_MAPPING = load_theme_mapping()
_GUMILYOV_MAPPING = load_gumilyov_mapping()
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
    res = meta.get(code)
    if not res:
        res = {"ru": str(code), "en": str(code)}
    res["code"] = code
    return res

def classify_theme(year, series, title, presentation_id=None, fallback_title=None):
    code = THEME_OVERRIDES_BY_PRESENTATION_ID.get(str(presentation_id or ""))
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

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    cursor.execute(f"SELECT person_id, display_name, birth_year, death_year, full_name_ru, full_name_en{degree_select} FROM person")
    persons_raw = cursor.fetchall()

    person_meta = {}
    for r_p in persons_raw:
        pid, display_name = r_p[0], r_p[1]
        birth_year = r_p[2]
        death_year = r_p[3]
        full_name_ru = r_p[4]
        full_name_en = r_p[5]
        degree = r_p[6] if has_degree else None
        degree_year = r_p[7] if has_degree else None
        degree_source_url = r_p[8] if has_degree else None

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
            "is_student": is_student,
            "is_independent": is_independent,
            "has_changed_affiliations": has_changed_affiliations,
            "all_affiliations": unique_affils,
            "birth_year": birth_year,
            "death_year": death_year,
            "full_name_ru": full_name_ru,
            "full_name_en": full_name_en,
            "gender": gender,
            "zograf_first": zograf_first,
            "zograf_last": zograf_last,
            "roerich_first": roerich_first,
            "roerich_last": roerich_last,
            "degree": degree,
            "degree_year": degree_year,
            "degree_source_url": degree_source_url
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
                s.session_id
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
            pres_id, title, year, series, affiliation, is_online, calendar_date, session_title, time_text, sess_id = t
            
            # Clean title (strip 'онлайн') and apply source-verified title repairs.
            source_title = clean_title(title)
            cleaned_title = canonical_title(pres_id, source_title)
            
            # Classify theme
            theme = classify_theme(year, series, cleaned_title, pres_id, source_title)
            t_code = theme["code"]
            theme_counts[t_code] = theme_counts.get(t_code, 0) + 1
            
            # Gumilyov scale
            g_scale = gumilyov_level_for(year, series, cleaned_title, source_title, title)
            
            # Day of the week calculation
            day_of_week = get_day_of_week(calendar_date)
            
            # Geography extraction
            geo = extract_geography(affiliation)
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
            
            talks.append({
                "presentation_id": pres_id,
                "title": cleaned_title,
                "year": year,
                "series": series,
                "affiliation": affiliation,
                "geography": geo,
                "theme": theme,
                "gumilyov_scale": g_scale,
                "tags": p_tags,
                "is_online": bool(is_online),
                "date": calendar_date,
                "day_of_week": day_of_week,
                "session_title": session_title,
                "time_interval": normalize_time_interval(time_text, "Не указано"),
                "is_first_talk": is_first,
                "is_last_talk": is_last,
                "order_in_session": order_idx + 1,
                "total_in_session": len(s_list),
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
        scholars.append({
            "id": pid,
            "name": meta["std_name"],
            "original_fullname": r[1],
            "full_name_ru": meta["full_name_ru"] or meta["std_name"],
            "full_name_en": meta["full_name_en"] or meta["std_name"],
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
            "has_changed_affiliations": meta["has_changed_affiliations"],
            "all_affiliations": meta["all_affiliations"],
            "talks": talks
        })
        
    # Assign SEO-friendly URL slugs (Latin transliteration with manual overrides
    # from authority_ids.json -> persons[id].preferred_latin_name).
    authority_overrides = load_authority_overrides()
    assign_unique_slugs(scholars, authority_overrides)

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
        
        # Geography extraction
        geo = extract_geography(affiliation)
        
        # Order in session
        s_list = session_pres_map.get(sess_id, [pres_id])
        try:
            order_idx = s_list.index(pres_id)
        except ValueError:
            order_idx = 0
            
        is_first = (order_idx == 0)
        is_last = (order_idx == len(s_list) - 1)
        
        series_key = "Zograf" if "Zograf" in series else "Roerich"
        # Clean title and apply source-verified title repairs.
        source_title = clean_title(title)
        cleaned_title = canonical_title(pres_id, source_title)
        
        # Classify theme
        theme = classify_theme(year_val, series, cleaned_title, pres_id, source_title)
        
        # Gumilyov scale
        g_scale = gumilyov_level_for(year_val, series, cleaned_title, source_title, title)

        p_tags = _TAGS_MAPPING.get(str(pres_id), [])

        series_key = "Zograf" if "Zograf" in series else "Roerich"
        timeline[year][series_key].append({
            "presentation_id": pres_id,
            "speaker": meta["std_name"],
            "speaker_original": meta["std_name"],
            "speaker_id": pid,
            "speaker_slug": slug_by_id.get(pid),
            "is_student": meta["is_student"],
            "is_independent": meta["is_independent"],
            "affiliation": affiliation,
            "geography": geo,
            "title": cleaned_title,
            "theme": theme,
            "gumilyov_scale": g_scale,
            "tags": p_tags,
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
    geo_coordinates = {
        "Москва": {"lat": 55.7558, "lon": 37.6173},
        "Санкт-Петербург": {"lat": 59.9343, "lon": 30.3351},
        "Краснодар": {"lat": 45.0393, "lon": 38.9872},
        "Казань": {"lat": 55.7963, "lon": 49.1088},
        "Новосибирск": {"lat": 55.0084, "lon": 82.9357},
        "Улан-Удэ": {"lat": 51.8344, "lon": 107.5845},
        "Пенза": {"lat": 53.1959, "lon": 45.0183},
        "Обнинск": {"lat": 55.1120, "lon": 36.5865},
        "Нижний Новгород": {"lat": 56.3269, "lon": 44.0059},
        "Томск": {"lat": 56.4977, "lon": 84.9744},
        "Элиста": {"lat": 46.3078, "lon": 44.2558},
        "Рим": {"lat": 41.9028, "lon": 12.4964},
        "Неаполь": {"lat": 40.8518, "lon": 14.2681},
        "Милан": {"lat": 45.4642, "lon": 9.1900},
        "Париж": {"lat": 48.8566, "lon": 2.3522},
        "Лион": {"lat": 45.7640, "lon": 4.8357},
        "Берлин": {"lat": 52.5200, "lon": 13.4050},
        "Мюнхен": {"lat": 48.1351, "lon": 11.5820},
        "Лондон": {"lat": 51.5074, "lon": -0.1278},
        "Оксфорд": {"lat": 51.7520, "lon": -1.2577},
        "Кембридж": {"lat": 52.2053, "lon": 0.1218},
        "Киев": {"lat": 50.4501, "lon": 30.5234},
        "Минск": {"lat": 53.9006, "lon": 27.5590},
        "Астана": {"lat": 51.1694, "lon": 71.4288},
        "Алматы": {"lat": 43.2220, "lon": 76.8512},
        "Ташкент": {"lat": 41.2995, "lon": 69.2401},
        "Дели": {"lat": 28.6139, "lon": 77.2090},
        "Мумбаи": {"lat": 19.0760, "lon": 72.8777},
        "Пуна": {"lat": 18.5204, "lon": 73.8567},
        "Ченнаи": {"lat": 13.0827, "lon": 80.2707},
        "Тарту": {"lat": 58.3780, "lon": 26.7290},
        "Прага": {"lat": 50.0755, "lon": 14.4378},
        "Варшава": {"lat": 52.2297, "lon": 21.0122},
        "Будапешт": {"lat": 47.4979, "lon": 19.0402},
        "Вена": {"lat": 48.2082, "lon": 16.3738},
        "Стокгольм": {"lat": 59.3293, "lon": 18.0686},
        "Осло": {"lat": 59.9139, "lon": 10.7522},
        "Копенгаген": {"lat": 55.6761, "lon": 12.5683},
        "Хельсинки": {"lat": 60.1695, "lon": 24.9354},
    }
    
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
        "F": female_count
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

    # 5. Affiliations Leaderboard
    def normalize_affiliation(aff):
        if not aff: return None
        a = aff.lower()
        if 'ивр ' in a or 'восточных рукописей' in a: return 'ИВР РАН'
        if 'ив ран' in a or 'востоковедения ран' in a or 'ивран' in a: return 'ИВ РАН'
        if 'спбгу' in a or 'петербургский' in a: return 'СПбГУ'
        if 'мгу' in a or 'ломоносова' in a: return 'МГУ'
        if 'вшэ' in a or 'высшая школа' in a: return 'НИУ ВШЭ'
        if 'рггу' in a or 'гуманитарный' in a: return 'РГГУ'
        if 'маэ' in a or 'кунсткамера' in a: return 'МАЭ РАН'
        if 'эрмитаж' in a: return 'Государственный Эрмитаж'
        if 'институт философии' in a or 'иф ран' in a: return 'ИФ РАН'
        if 'независим' in a or 'independent' in a: return 'Независимые исследователи'
        return None
        
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

    print(f"Successfully generated JSON data payload in {OUTPUT_FILE} with full temporal, position order, and student/independent academic metadata!")
    conn.close()

if __name__ == "__main__":
    main()
