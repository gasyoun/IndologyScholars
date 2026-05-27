import os
import re
import sys
import hashlib
import unicodedata
from collections import defaultdict

from pipeline.schema import SmartHTMLParser, CACHE_DIR, extract_program_last_updated
from pipeline.biography import normalize_person_name, get_or_create_person

# Clean title helper
def clean_title(title):
    title = title.strip()
    title = re.sub(r'\s*\(\s*онлайн\s*\)\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(\s*zoom\s*\)\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(
        r'\s+\d{1,2}[:\.]\d{2}\s*[—–-]\s*\d{1,2}[:\.]\d{2}\.?\s*перерыв.*$',
        '',
        title,
        flags=re.IGNORECASE,
    )
    title = re.sub(r'\s+\d{1,2}[:\.]\d{2}\s*[—–-]\s*\d{1,2}[:\.]\d{2}\s*$', '', title)
    if title.endswith('.'):
        title = title[:-1]
    return title.strip()


# Preprocess line helper to remove leading time
def preprocess_line(line):
    line = line.strip()
    line = re.sub(r'^\s*\d{1,2}\s*[\.:]\s*\d{2}\s*\.?\s*', '', line)
    line = re.sub(r'^\s*\d{1,2}\s*\.\s*', '', line)
    return line.strip()


def canonical_id_text(value):
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text


def stable_hash(*parts, length=10):
    basis = "|".join(canonical_id_text(part) for part in parts)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:length]


def stable_session_id(series_slug, year, day_or_venue, session_title, time_text, source_url, source_line):
    prefix = "SESS_R" if series_slug == "roerich" else "SESS"
    digest = stable_hash(series_slug, year, day_or_venue, session_title, time_text, source_url, source_line)
    return f"{prefix}_{digest}"


def stable_presentation_id(series_slug, year, title, first_speaker, session_order):
    digest = stable_hash(series_slug, year, title, normalize_person_name(first_speaker or ""), str(session_order))
    return f"PRES_{digest}"


def infer_zograf_calendar_date(year, line):
    month_match = re.search(r'\b(\d{1,2})\s*(?:мая|РμР°СЏ)\b', line, flags=re.IGNORECASE)
    if month_match:
        day = int(month_match.group(1))
        if 1 <= day <= 31:
            return f"{year}-05-{day:02d}"

    numeric_match = re.search(r'\b(\d{1,2})[./-]0?5(?:[./-]\d{2,4})?\b', line)
    if numeric_match:
        day = int(numeric_match.group(1))
        if 1 <= day <= 31:
            return f"{year}-05-{day:02d}"

    return None


def ensure_zograf_event_day_venue(cursor, event_id, year, day_number, source_url, source_line, previous_edv_id=None):
    day_id = f"D{year}_{day_number}"
    edv_id = f"DV{year}_{day_number}_1"

    cursor.execute(
        "SELECT event_day_venue_id FROM event_day_venue WHERE event_day_id = ? ORDER BY occurrence_order LIMIT 1",
        (day_id,),
    )
    existing = cursor.fetchone()
    if existing:
        return existing[0]

    cursor.execute("SELECT 1 FROM event_day WHERE event_day_id = ?", (day_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO event_day VALUES (?,?,?,?,?,?,?)",
            (
                day_id,
                event_id,
                day_number,
                infer_zograf_calendar_date(year, source_line),
                source_line,
                source_url,
                "Generated from parsed Zograf programme date not present in seed table.",
            ),
        )

    venue_id = "V001"
    room_text = "unspecified"
    time_text = "unspecified"
    if previous_edv_id:
        cursor.execute(
            "SELECT venue_id, room_text_raw, time_text_raw FROM event_day_venue WHERE event_day_venue_id = ?",
            (previous_edv_id,),
        )
        previous = cursor.fetchone()
        if previous:
            venue_id, room_text, time_text = previous

    cursor.execute(
        "INSERT OR IGNORE INTO event_day_venue VALUES (?,?,?,?,?,?,?,?)",
        (edv_id, day_id, venue_id, 1, room_text, time_text, source_url, source_line),
    )
    return edv_id

# Regex to detect presentations
TALK_REGEX = re.compile(
    r'^([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,2}|\s*[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z][а-яёa-z\-]+|\s*[А-ЯЁA-Z][а-яёa-z\-]+\s+[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z]\.)\s*\(([^)]+)\)\.?\s*(.+)$'
)

# Extended regex: comma-separated co-authors sharing a single affil (e.g. PDF programs 2026+)
TALK_REGEX_COAUTHORS = re.compile(
    r'^([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,3}'
    r'(?:\s*,\s*[А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,3})+)\s*'
    r'\(([^)]+)\)\.?\s*(.+)$'
)

# Detect two consecutive "Author (City). Author (City). Title" — co-authors with distinct affils
TALK_REGEX_TWO_AFFIL = re.compile(
    r'^([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,3})\s*\(([^)]+)\)\.\s*'
    r'([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,3})\s*\(([^)]+)\)\.\s*(.+)$'
)

INITIAL_AUTHOR = (
    r'(?:(?:[А-ЯЁA-Z]\.\s*){1,2}[А-ЯЁA-Z][а-яёa-z\-]+|'
    r'[А-ЯЁA-Z][а-яёa-z\-]+\s*(?:[А-ЯЁA-Z]\.?\s*){1,2})'
)

TALK_REGEX_INITIALS_AFFIL = re.compile(
    rf'^({INITIAL_AUTHOR})\s*\(([^)]+)\)\.?\s*(.+)$'
)

TALK_REGEX_TWO_AFFIL_INITIALS = re.compile(
    rf'^({INITIAL_AUTHOR})\s*\(([^)]+)\)\s*,?\s*'
    rf'({INITIAL_AUTHOR})\s*\(([^)]+)\)\.?\s*(.+)$'
)

TALK_REGEX_COAUTHORS_INITIALS = re.compile(
    rf'^({INITIAL_AUTHOR}(?:\s*,\s*{INITIAL_AUTHOR})+)\s*\(([^)]+)\)\.?\s*(.+)$'
)

TALK_REGEX_COAUTHORS_NO_AFFIL = re.compile(
    rf'^({INITIAL_AUTHOR}(?:\s*,\s*{INITIAL_AUTHOR})+)\.\s*(.+)$'
)

TALK_REGEX_NO_AFFIL = re.compile(
    r'^((?:[А-ЯЁA-Z]\.\s*){1,2}[А-ЯЁA-Z][а-яёa-z\-]+|'
    r'[А-ЯЁA-Z][а-яёa-z\-]+\s*(?:[А-ЯЁA-Z]\.\s*){1,2})\.\s*(.+)$'
)

TALK_REGEX_ACADEMIC_NO_AFFIL = re.compile(
    r'^(?:Акад|Проф)\.\s*((?:[А-ЯЁA-Z]\.\s*){1,2}[А-ЯЁA-Z][а-яёa-z\-]+)\.\s*(.+)$',
    flags=re.IGNORECASE,
)

TALK_REGEX_LATIN_COAUTHORS = re.compile(
    r'^\[?([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+)+)\]?\s*,\s*'
    r'([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+)+)\s*\(([^)]+)\)\.?\s*(.+)$'
)

PACKED_AUTHOR_SIGNATURE = re.compile(
    r'(?:[А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+){1,2}|'
    r'[А-ЯЁ][а-яё\-]+\s*(?:[А-ЯЁ]\.\s*){1,2}|'
    r'(?:[А-ЯЁ]\.\s*){1,2}[А-ЯЁ][а-яё\-]+)\s*\([^)]+\)\.?\s*'
)

PACKED_INITIAL_AUTHOR_SIGNATURE = re.compile(
    rf'({INITIAL_AUTHOR}(?:\s*,\s*{INITIAL_AUTHOR})*)\s*\(([^)]+)\)\.?\s*'
)

LATIN_SPEAKER_ALIASES = {
    "Olga Vecherina": "О. П. Вечерина",
    "Ruzana Pskhu": "Р. В. Псху",
}


def split_packed_zograf_lines(lines):
    """Separate multiple programme entries collapsed into a single HTML paragraph."""
    expanded = []
    latin_marker = re.compile(r'\[?Olga Vecherina\]?\s*,\s*Ruzana Pskhu\s*\(')
    for line in lines:
        cleaned = preprocess_line(line)
        if TALK_REGEX_TWO_AFFIL.match(cleaned):
            expanded.append(line)
            continue

        boundaries = []
        for match in PACKED_AUTHOR_SIGNATURE.finditer(line):
            position = match.start()
            if position <= 0:
                continue
            matched_str = match.group(0)
            if re.search(r'\b(?:1[0-9]{3}|20[0-9]{2})\s*[—–-]\s*(?:1[0-9]{3}|20[0-9]{2})\b', matched_str):
                continue
            prefix = line[:position].rstrip()
            if prefix and prefix[-1] in ".!?":
                boundaries.append(position)
        for match in PACKED_INITIAL_AUTHOR_SIGNATURE.finditer(line):
            position = match.start()
            if position <= 0:
                continue
            if line[:position].rstrip().endswith(","):
                continue
            affiliation = match.group(2).lower()
            if re.search(
                r'москв|спб|петербург|обнинск|казан|пенза|краснодар|новосибирск|'
                r'вильнюс|гамбург|маврики|гент|онлайн',
                affiliation,
            ):
                boundaries.append(position)
        latin_match = latin_marker.search(line)
        if latin_match and latin_match.start() > 0:
            boundaries.append(latin_match.start())
        if not boundaries:
            expanded.append(line)
            continue
        previous = 0
        for position in sorted(set(boundaries)):
            fragment = line[previous:position].strip()
            if fragment:
                expanded.append(fragment)
            previous = position
        fragment = line[previous:].strip()
        if fragment:
            expanded.append(fragment)
    return expanded


def parse_zograf_talk_line(line):
    """Return parsed speakers and title for one candidate programme entry."""
    cleaned_line = preprocess_line(line)
    m_two = TALK_REGEX_TWO_AFFIL.match(cleaned_line)
    if m_two:
        return [
            (m_two.group(1).strip(), m_two.group(2).strip()),
            (m_two.group(3).strip(), m_two.group(4).strip()),
        ], clean_title(m_two.group(5))

    m_two_initials = TALK_REGEX_TWO_AFFIL_INITIALS.match(cleaned_line)
    if m_two_initials:
        return [
            (m_two_initials.group(1).strip(), m_two_initials.group(2).strip()),
            (m_two_initials.group(3).strip(), m_two_initials.group(4).strip()),
        ], clean_title(m_two_initials.group(5))

    m_co = TALK_REGEX_COAUTHORS.match(cleaned_line)
    if m_co:
        names = split_coauthor_names(m_co.group(1))
        affil = m_co.group(2).strip()
        return [(name, affil) for name in names], clean_title(m_co.group(3))

    m_co_initials = TALK_REGEX_COAUTHORS_INITIALS.match(cleaned_line)
    if m_co_initials:
        names = split_coauthor_names(m_co_initials.group(1))
        affil = m_co_initials.group(2).strip()
        return [(name, affil) for name in names], clean_title(m_co_initials.group(3))

    m_co_no_affil = TALK_REGEX_COAUTHORS_NO_AFFIL.match(cleaned_line)
    if m_co_no_affil:
        names = split_coauthor_names(m_co_no_affil.group(1))
        return [(name, "Не указана") for name in names], clean_title(m_co_no_affil.group(2))

    m_single = TALK_REGEX.match(cleaned_line)
    if m_single:
        return [(m_single.group(1).strip(), m_single.group(2).strip())], clean_title(m_single.group(3))

    m_initials = TALK_REGEX_INITIALS_AFFIL.match(cleaned_line)
    if m_initials:
        return [(m_initials.group(1).strip(), m_initials.group(2).strip())], clean_title(m_initials.group(3))

    m_latin = TALK_REGEX_LATIN_COAUTHORS.match(cleaned_line)
    if m_latin:
        return [
            (LATIN_SPEAKER_ALIASES.get(m_latin.group(1).strip(), m_latin.group(1).strip()), m_latin.group(3).strip()),
            (LATIN_SPEAKER_ALIASES.get(m_latin.group(2).strip(), m_latin.group(2).strip()), m_latin.group(3).strip()),
        ], clean_title(m_latin.group(4))

    m_academic = TALK_REGEX_ACADEMIC_NO_AFFIL.match(cleaned_line)
    if m_academic:
        return [(m_academic.group(1).strip(), "Не указана")], clean_title(m_academic.group(2))

    m_no_affil = TALK_REGEX_NO_AFFIL.match(cleaned_line)
    if m_no_affil:
        return [(m_no_affil.group(1).strip(), "Не указана")], clean_title(m_no_affil.group(2))

    return None


def is_zograf_structure_line(line, year):
    """Identify lines that end a wrapped talk entry rather than extend its title."""
    value = preprocess_line(line)
    lower = value.lower()
    if not value:
        return True
    if re.search(r'\d{1,2}\s*[—–-]\s*\d{1,2}\s*мая', lower):
        return True
    if "мая" in lower and (str(year) in lower or len(value) < 65 or re.match(r'^\d{1,2}\s+мая', lower)):
        return True
    if re.search(r'\d{1,2}[:\.]\d{2}\s*[-—–]\s*\d{1,2}[:\.]\d{2}', value):
        return True
    if re.match(r'^\d{1,2}[:\.]\d{2}(?:\.|\s|$)', value):
        return True
    return lower.startswith((
        "\u0443\u0442\u0440\u0435\u043d\u043d\u0435\u0435 \u0437\u0430\u0441\u0435\u0434\u0430\u043d\u0438\u0435",
        "\u0434\u043d\u0435\u0432\u043d\u043e\u0435 \u0437\u0430\u0441\u0435\u0434\u0430\u043d\u0438\u0435",
        "\u0432\u0435\u0447\u0435\u0440\u043d\u0435\u0435 \u0437\u0430\u0441\u0435\u0434\u0430\u043d\u0438\u0435",
        "перерыв", "открытие", "приветств", "выступления", "предс.",
        "председатель", "подведение итогов", "заключительное",
        "день ", "понедельник", "вторник", "среда", "четверг", "пятница",
        "институт ", "восточный факультет", "конференция проводится",
        "последнее обновление", "« пред.", "след.", "вернуться",
    ))


def has_nonparticipant_affiliation(speakers_with_affil):
    """Catch title fragments such as a scholar's lifespan parsed as an affiliation."""
    for _speaker, affiliation in speakers_with_affil:
        if re.search(r'\b(?:1[0-9]{3}|20[0-9]{2})\s*[—–-]\s*(?:1[0-9]{3}|20[0-9]{2})\b', affiliation):
            return True
    return False


def coalesce_zograf_talk_lines(lines, year):
    """Join title wraps and detached-title layouts into one logical talk line."""
    repaired = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if (
            re.fullmatch(r'(?:[А-ЯЁA-Z]\.\s*){1,2}', line)
            and idx + 1 < len(lines)
        ):
            repaired.append(f"{line} {lines[idx + 1]}".strip())
            idx += 2
            continue
        repaired.append(line)
        idx += 1
    expanded = split_packed_zograf_lines(repaired)
    merged = []
    pending = None
    for idx, line in enumerate(expanded):
        candidate = parse_zograf_talk_line(line)
        next_line = expanded[idx + 1] if idx + 1 < len(expanded) else None
        next_is_title_text = (
            next_line is not None
            and parse_zograf_talk_line(next_line) is None
            and not is_zograf_structure_line(next_line, year)
        )
        starts_talk = candidate is not None and not has_nonparticipant_affiliation(candidate[0])
        if starts_talk and not candidate[1] and pending is not None and not next_is_title_text:
            starts_talk = False

        if starts_talk:
            if pending is not None:
                merged.append(pending)
            pending = line
        elif pending is not None and not is_zograf_structure_line(line, year):
            pending = f"{pending} {line}".strip()
        else:
            if pending is not None:
                merged.append(pending)
                pending = None
            merged.append(line)
    if pending is not None:
        merged.append(pending)
    return merged


def read_program_text(year, conference="zograf"):
    html_path = os.path.join(CACHE_DIR, f"{conference}_{year}.html")
    pdf_path = os.path.join(CACHE_DIR, f"{conference}_{year}.pdf")

    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        if year == 2016 and conference == "zograf":
            # Fix missing parenthetical city affiliation for Burmistrov in 2016 to enable correct splitting
            html = re.sub(
                r'(С\.\s*&nbsp;\s*Л\.\s*&nbsp;\s*Бурмистров)\.(\s*</(?:em|i)>\s*</strong>\s*Пауль)',
                r'\1 (СПб).\2',
                html
            )
        parser = SmartHTMLParser()
        parser.feed(html)
        return parser.get_text()

    if os.path.exists(pdf_path):
        try:
            from pypdf import PdfReader
        except ImportError:
            print(f"  WARNING: pypdf not installed, cannot read {pdf_path}", file=sys.stderr)
            return None
        reader = PdfReader(pdf_path)
        pages_text = []
        for page in reader.pages:
            t = page.extract_text() or ""
            pages_text.append(t)
        return "\n".join(pages_text)

    return None


def split_coauthor_names(speaker_block):
    """Split 'Ivanov A B, Petrov C D' into ['Ivanov A B', 'Petrov C D']."""
    parts = re.split(r'\s*,\s*(?=[А-ЯЁA-Z])', speaker_block)
    return [p.strip() for p in parts if p.strip()]


def populate_zograf_talks(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT event_id, year, source_url FROM event WHERE event_series_id = 1")
    z_events = cursor.fetchall()
    
    for event_id, year, source_url in z_events:
        text = read_program_text(year, conference="zograf")
        if text is None:
            continue

        lines = coalesce_zograf_talk_lines([line.strip() for line in text.split('\n') if line.strip()], year)
        
        day_number = 0
        current_day_id = None
        current_edv_id = None
        last_valid_edv_id = None
        current_session_id = None
        session_order = 0
        
        for line in lines:
            if year == 2014 and "состоится доклад профессора Х. Линдтнера" in line:
                break
            if "мая" in line and (str(year) in line or len(line) < 60) and not TALK_REGEX.match(preprocess_line(line)):
                if re.search(r'\d{1,2}\s*[—–-]\s*\d{1,2}\s*мая', line):
                    pass
                else:
                    day_number += 1
                    current_day_id = f"D{year}_{day_number}"
                    current_edv_id = ensure_zograf_event_day_venue(
                        cursor, event_id, year, day_number, source_url, line, last_valid_edv_id
                    )
                    last_valid_edv_id = current_edv_id
                    current_session_id = None
            
            time_match = re.search(r'(\d{2}[:\.]\d{2})\s*[-—–]\s*(\d{2}[:\.]\d{2})', line)
            if time_match and not TALK_REGEX.match(preprocess_line(line)):
                start_time, end_time = time_match.group(1), time_match.group(2)
                sess_title = line.replace(time_match.group(0), '').strip()
                if not sess_title:
                    sess_title = "Утреннее заседание" if int(start_time.replace('.', ':').split(':')[0]) < 14 else "Вечернее заседание"
                
                if current_edv_id:
                    session_order += 1
                    current_session_id = stable_session_id(
                        "zograf", year, current_edv_id, sess_title, time_match.group(0), source_url, f"{session_order}|{line}"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, sess_title, "panel", start_time, end_time, time_match.group(0), None, source_url, line, None))
                    conn.commit()
            
            cleaned_line = preprocess_line(line)
            speakers_with_affil = []
            title_raw = None

            candidate = parse_zograf_talk_line(line)
            if candidate:
                speakers_with_affil, title_raw = candidate

            if speakers_with_affil and title_raw:
                if not current_session_id:
                    if not current_edv_id:
                        day_number = 1
                        current_day_id = f"D{year}_1"
                        current_edv_id = ensure_zograf_event_day_venue(
                            cursor, event_id, year, day_number, source_url, "Automatic default day", last_valid_edv_id
                        )
                        last_valid_edv_id = current_edv_id

                    session_order += 1
                    current_session_id = stable_session_id(
                        "zograf", year, current_edv_id, "Научное заседание", "11:00–18:00", source_url, f"{session_order}|Automatic default session"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, "Научное заседание", "panel", "11:00", "18:00", "11:00–18:00", None, source_url, "Automatic default session", None))
                    conn.commit()

                pres_id = stable_presentation_id("zograf", year, title_raw, speakers_with_affil[0][0], session_order)
                is_online_val = 1 if 'онлайн' in line.lower() else 0
                cursor.execute("INSERT INTO presentation VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (pres_id, current_session_id, title_raw, None, "ru", None, is_online_val, None, source_url, line, None))

                for order_idx, (speaker_raw, affil_raw) in enumerate(speakers_with_affil, start=1):
                    person_id = get_or_create_person(conn, speaker_raw, source_url)
                    role = "speaker" if order_idx == 1 else "coauthor"
                    cursor.execute("INSERT INTO presentation_person VALUES (?,?,?,?,?,?,?,?)",
                                   (pres_id, person_id, role, order_idx, affil_raw, None, source_url, None))
                conn.commit()


def populate_roerich_talks(conn):
    cursor = conn.cursor()
    ROERICH_YEARS = sorted(list(range(2007, 2026)))
    ROMAN_MAP = {
        2025: "LXV", 2024: "LXIV", 2023: "LXIII", 2022: "LXII", 2021: "LXI",
        2020: "LX", 2019: "LIX", 2018: "LVIII", 2017: "LVII", 2016: "LVI",
        2015: "LV", 2014: "LIV", 2013: "LIII", 2012: "LII", 2011: "LI",
        2010: "L", 2009: "XLIX", 2008: "XLVIII", 2007: "XLVII"
    }
    
    for year in ROERICH_YEARS:
        filename = f"roerich_{year}.html"
        filepath = os.path.join(CACHE_DIR, filename)
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
            
        parser = SmartHTMLParser()
        parser.feed(html)
        text = parser.get_text()
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        start_date = f"{year}-12-09"
        end_date = f"{year}-12-11"
        theme = "Древняя и средневековая Индия и Центральная Азия. История. Филология. Культура"
        
        for line in lines[:40]:
            date_match = re.search(r'(\d{1,2})[–-]\s*(\d{1,2})\s+декабря\s+(\d{4})', line)
            if date_match:
                start_date = f"{year}-12-{int(date_match.group(1)):02d}"
                end_date = f"{year}-12-{int(date_match.group(2)):02d}"
                break
                
        event_id = f"ER{year}"
        roman = ROMAN_MAP.get(year, "unspecified")
        
        cursor.execute("INSERT OR IGNORE INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (event_id, 2, year - 1960, roman, year, theme, None, start_date, end_date, "in_person", 0, None, None, f"https://ancient.ivran.ru/novosti?year={year}", extract_program_last_updated(year, "roerich"), None))
        
        day_number = 0
        current_day_id = None
        current_edv_id = None
        current_session_id = None
        session_order = 0
        
        for line in lines:
            day_match = re.search(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b', line)
            if day_match:
                day_number += 1
                current_day_id = f"DR{year}_{day_number}"
                day_date = f"{day_match.group(3)}-{int(day_match.group(2)):02d}-{int(day_match.group(1)):02d}"
                
                cursor.execute("INSERT OR IGNORE INTO event_day VALUES (?,?,?,?,?,?,?)",
                               (current_day_id, event_id, day_number, day_date, line, f"https://ancient.ivran.ru/novosti?year={year}", None))
                               
                current_edv_id = f"DVR{year}_{day_number}_1"
                cursor.execute("INSERT OR IGNORE INTO event_day_venue VALUES (?,?,?,?,?,?,?,?)",
                               (current_edv_id, current_day_id, "V100", 1, "222 ауд.", "11:00", f"https://ancient.ivran.ru/novosti?year={year}", "IV RAS"))
                
                current_session_id = None
                conn.commit()
                
            if ("заседание" in line.lower() or "открытие" in line.lower()) and ":" in line and not TALK_REGEX.match(preprocess_line(line)):
                parts = line.split(":", 1)
                sess_title = parts[0].strip()
                time_n_room = parts[1].strip()
                
                time_match = re.search(r'(\d{2}\.\d{2})\s*[-—–]\s*(\d{2}\.\d{2})', time_n_room)
                start_t, end_t, raw_t = None, None, None
                if time_match:
                    start_t, end_t = time_match.group(1).replace('.', ':'), time_match.group(2).replace('.', ':')
                    raw_t = time_match.group(0)
                    
                room_match = re.search(r'\(([^)]+)\)', time_n_room)
                room = room_match.group(1).strip() if room_match else None
                
                if current_edv_id:
                    session_order += 1
                    current_session_id = stable_session_id(
                        "roerich", year, current_edv_id, sess_title, raw_t, f"https://ancient.ivran.ru/novosti?year={year}", f"{session_order}|{line}"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, sess_title, "panel", start_t, end_t, raw_t, None, f"https://ancient.ivran.ru/novosti?year={year}", line, room))
                    conn.commit()
            
            if "модератор" in line.lower() and current_session_id:
                cursor.execute("UPDATE session SET chair_text_raw = ? WHERE session_id = ?", (line, current_session_id))
                conn.commit()
                
            candidate = parse_zograf_talk_line(line)
            if candidate:
                speakers_with_affil, title_raw = candidate
                if not title_raw:
                    continue
                
                if not current_day_id:
                    day_number = 1
                    current_day_id = f"DR{year}_1"
                    day_date = f"{year}-12-09"
                    cursor.execute("INSERT OR IGNORE INTO event_day VALUES (?,?,?,?,?,?,?)",
                                   (current_day_id, event_id, 1, day_date, "Понедельник", f"https://ancient.ivran.ru/novosti?year={year}", None))
                    current_edv_id = f"DVR{year}_1_1"
                    cursor.execute("INSERT OR IGNORE INTO event_day_venue VALUES (?,?,?,?,?,?,?,?)",
                                   (current_edv_id, current_day_id, "V100", 1, "222 ауд.", "11:00", f"https://ancient.ivran.ru/novosti?year={year}", "IV RAS"))
                
                if not current_session_id:
                    session_order += 1
                    current_session_id = stable_session_id(
                        "roerich", year, current_edv_id, "Научное заседание", "11:00–18:00", f"https://ancient.ivran.ru/novosti?year={year}", f"{session_order}|Default"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, "Научное заседание", "panel", "11:00", "18:00", "11:00–18:00", None, f"https://ancient.ivran.ru/novosti?year={year}", "Default", None))
                
                pres_id = stable_presentation_id("roerich", year, title_raw, speakers_with_affil[0][0], session_order)
                is_online_val = 1 if 'онлайн' in line.lower() else 0
                cursor.execute("INSERT INTO presentation VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (pres_id, current_session_id, title_raw, None, "ru", None, is_online_val, None, f"https://ancient.ivran.ru/novosti?year={year}", line, None))
                
                for order_idx, (speaker_raw, affil_raw) in enumerate(speakers_with_affil, start=1):
                    person_id = get_or_create_person(conn, speaker_raw, f"https://ancient.ivran.ru/novosti?year={year}")
                    role = "speaker" if order_idx == 1 else "coauthor"
                    cursor.execute("INSERT INTO presentation_person VALUES (?,?,?,?,?,?,?,?)",
                                   (pres_id, person_id, role, order_idx, affil_raw, None, f"https://ancient.ivran.ru/novosti?year={year}", None))
                conn.commit()
