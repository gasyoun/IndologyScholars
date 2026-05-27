import os
import re
import csv
import io
from html.parser import HTMLParser

MD_PATH = "zograf-roerich-db.md"
CACHE_DIR = "html_cache"

class SmartHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.block_tags = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'ol', 'ul'}

    def handle_starttag(self, tag, attrs):
        if tag in self.block_tags:
            self._add_newline()

    def handle_endtag(self, tag):
        if tag in self.block_tags:
            self._add_newline()

    def handle_data(self, data):
        self.text_parts.append(data)

    def _add_newline(self):
        if self.text_parts and not self.text_parts[-1].endswith('\n'):
            self.text_parts.append('\n')

    def get_text(self):
        return "".join(self.text_parts)


def extract_csv_from_md(md_path, csv_name):
    if not os.path.exists(md_path):
        return []
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = r'###\s+' + re.escape(csv_name) + r'\s*\n\n```csv\n(.*?)\n```'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        pattern_alt = r'###\s+' + re.escape(csv_name.replace('.csv', '')) + r'\s*\n\n```csv\n(.*?)\n```'
        match = re.search(pattern_alt, content, re.DOTALL)
    if not match:
        return []
    
    csv_data = match.group(1)
    reader = csv.DictReader(io.StringIO(csv_data))
    return list(reader)


def extract_program_last_updated(year, conference="zograf"):
    """Extract the source-page modification date when the programme exposes one."""
    html_path = os.path.join(CACHE_DIR, f"{conference}_{year}.html")
    if not os.path.exists(html_path):
        return None
    with open(html_path, "r", encoding="utf-8") as handle:
        html = handle.read()
    match = re.search(
        r"Последнее\s+обновление\s*\(\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*\)",
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    day, month, source_year = match.groups()
    return f"{int(source_year):04d}-{int(month):02d}-{int(day):02d}"


def init_db(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS event_series")
    cursor.execute("DROP TABLE IF EXISTS place")
    cursor.execute("DROP TABLE IF EXISTS organization")
    cursor.execute("DROP TABLE IF EXISTS venue")
    cursor.execute("DROP TABLE IF EXISTS event")
    cursor.execute("DROP TABLE IF EXISTS event_day")
    cursor.execute("DROP TABLE IF EXISTS event_day_venue")
    cursor.execute("DROP TABLE IF EXISTS person")
    cursor.execute("DROP TABLE IF EXISTS session")
    cursor.execute("DROP TABLE IF EXISTS presentation")
    cursor.execute("DROP TABLE IF EXISTS presentation_person")
    cursor.execute("DROP TABLE IF EXISTS media")
    
    cursor.execute("""
    CREATE TABLE event_series (
        event_series_id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_name_en TEXT NOT NULL UNIQUE,
        series_name_ru TEXT,
        notes TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE place (
        place_id TEXT PRIMARY KEY,
        address_text TEXT,
        city TEXT,
        region TEXT,
        country TEXT,
        postal_code TEXT,
        latitude REAL,
        longitude REAL,
        source_url TEXT,
        notes TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE organization (
        organization_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL UNIQUE,
        display_name_ru TEXT,
        org_type TEXT,
        parent_org_id TEXT,
        source_url TEXT,
        notes TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE venue (
        venue_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL UNIQUE,
        venue_type TEXT,
        organization_id TEXT,
        place_id TEXT,
        source_url TEXT,
        notes TEXT,
        FOREIGN KEY(organization_id) REFERENCES organization(organization_id),
        FOREIGN KEY(place_id) REFERENCES place(place_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE event (
        event_id TEXT PRIMARY KEY,
        event_series_id INTEGER,
        ordinal_int INTEGER,
        ordinal_roman TEXT,
        year INTEGER NOT NULL,
        theme_ru TEXT,
        theme_en TEXT,
        start_date TEXT,
        end_date TEXT,
        format TEXT DEFAULT 'unspecified',
        is_online INTEGER DEFAULT 0,
        online_platform TEXT,
        program_post_id TEXT,
        source_url TEXT NOT NULL,
        program_last_updated TEXT,
        notes TEXT,
        FOREIGN KEY(event_series_id) REFERENCES event_series(event_series_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE event_day (
        event_day_id TEXT PRIMARY KEY,
        event_id TEXT,
        day_number INTEGER NOT NULL,
        calendar_date TEXT,
        day_label_raw TEXT,
        source_url TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY(event_id) REFERENCES event(event_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE event_day_venue (
        event_day_venue_id TEXT PRIMARY KEY,
        event_day_id TEXT,
        venue_id TEXT,
        occurrence_order INTEGER NOT NULL DEFAULT 1,
        room_text_raw TEXT,
        time_text_raw TEXT,
        source_url TEXT NOT NULL,
        source_snippet TEXT,
        FOREIGN KEY(event_day_id) REFERENCES event_day(event_day_id),
        FOREIGN KEY(venue_id) REFERENCES venue(venue_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE person (
        person_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL UNIQUE,
        full_name_ru TEXT,
        full_name_en TEXT,
        birth_year INTEGER,
        death_year INTEGER,
        degree TEXT,
        degree_year TEXT,
        degree_source_url TEXT,
        normalized_key TEXT,
        source_url TEXT,
        notes TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE session (
        session_id TEXT PRIMARY KEY,
        event_day_venue_id TEXT,
        session_title TEXT,
        session_type TEXT,
        start_time TEXT,
        end_time TEXT,
        time_text_raw TEXT,
        chair_text_raw TEXT,
        source_url TEXT NOT NULL,
        source_snippet TEXT,
        notes TEXT,
        FOREIGN KEY(event_day_venue_id) REFERENCES event_day_venue(event_day_venue_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE presentation (
        presentation_id TEXT PRIMARY KEY,
        session_id TEXT,
        title TEXT,
        abstract TEXT,
        language TEXT DEFAULT 'unspecified',
        keywords TEXT,
        is_online INTEGER DEFAULT 0,
        order_in_session INTEGER,
        source_url TEXT NOT NULL,
        source_snippet TEXT,
        notes TEXT,
        FOREIGN KEY(session_id) REFERENCES session(session_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE presentation_person (
        presentation_id TEXT,
        person_id TEXT,
        role TEXT DEFAULT 'unspecified',
        author_order INTEGER,
        affiliation_text_raw TEXT,
        organization_id TEXT,
        source_url TEXT NOT NULL,
        notes TEXT,
        PRIMARY KEY (presentation_id, person_id, role),
        FOREIGN KEY(presentation_id) REFERENCES presentation(presentation_id),
        FOREIGN KEY(person_id) REFERENCES person(person_id),
        FOREIGN KEY(organization_id) REFERENCES organization(organization_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE media (
        media_id TEXT PRIMARY KEY,
        attached_to_type TEXT NOT NULL,
        attached_to_id TEXT NOT NULL,
        media_type TEXT NOT NULL,
        media_url TEXT NOT NULL,
        media_title TEXT,
        mime_type TEXT,
        source_url TEXT NOT NULL,
        notes TEXT
    )""")
    conn.commit()


def populate_seeded_data(conn):
    cursor = conn.cursor()
    # 1. Event Series
    cursor.execute("INSERT INTO event_series (event_series_id, series_name_en, series_name_ru, notes) VALUES (?, ?, ?, ?)",
                   (1, "Zograf Readings", "Зографские чтения", "Annual Saint Petersburg indological conference"))
    cursor.execute("INSERT INTO event_series (event_series_id, series_name_en, series_name_ru, notes) VALUES (?, ?, ?, ?)",
                   (2, "Roerich Readings", "Рериховские чтения", "Annual Moscow indological conference"))
    
    # 2. Extract Curated Zograf Data from Markdown
    places = extract_csv_from_md(MD_PATH, "Places.csv")
    for r in places:
        cursor.execute("INSERT INTO place VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (r['place_id'], r['address_text'], r['city'], r['region'], r['country'], r['postal_code'], None, None, r['source_url'], r['notes']))
                       
    orgs = extract_csv_from_md(MD_PATH, "Organizations.csv")
    for r in orgs:
        cursor.execute("INSERT INTO organization VALUES (?,?,?,?,?,?,?)",
                       (r['organization_id'], r['display_name'], r['display_name_ru'], r['org_type'], r['parent_organization_id'], r['source_url'], r['notes']))
                       
    venues = extract_csv_from_md(MD_PATH, "Venues.csv")
    for r in venues:
        cursor.execute("INSERT INTO venue VALUES (?,?,?,?,?,?,?)",
                       (r['venue_id'], r['display_name'], r['venue_type'], r['organization_id'], r['place_id'], r['source_url'], r['notes']))
                       
    events = extract_csv_from_md(MD_PATH, "Events.csv")
    for r in events:
        is_online_val = 1 if r['is_online'].lower() == 'true' else 0
        cursor.execute("INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (r['event_id'], 1, int(r['ordinal_int']), r['ordinal_roman'], int(r['year']), r['theme_ru'], None, r['start_date'], r['end_date'], r['format'], is_online_val, r['online_platform'], r['program_post_id'], r['source_url'], extract_program_last_updated(int(r['year']), "zograf"), r['notes']))
                       
    days = extract_csv_from_md(MD_PATH, "EventDays.csv")
    for r in days:
        cursor.execute("INSERT INTO event_day VALUES (?,?,?,?,?,?,?)",
                       (r['event_day_id'], r['event_id'], int(r['day_number']), r['calendar_date'], r['day_label_raw'], r['source_url'], r['notes']))
                       
    day_venues = extract_csv_from_md(MD_PATH, "EventDayVenues.csv")
    for r in day_venues:
        cursor.execute("INSERT INTO event_day_venue VALUES (?,?,?,?,?,?,?,?)",
                       (r['event_day_venue_id'], r['event_day_id'], r['venue_id'], int(r['occurrence_order']), r['room_text_raw'], r['time_text_raw'], r['source_url'], r['source_snippet']))
                       
    media = extract_csv_from_md(MD_PATH, "Media.csv")
    for r in media:
        cursor.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?)",
                       (r['media_id'], r['attached_to_type'], r['attached_to_id'], r['media_type'], r['media_url'], r['media_title'], r['mime_type'], r['source_url'], r['notes']))
 
    # 3. Add Roerich Readings Seed Metadata
    # Place: IV RAS Moscow
    cursor.execute("INSERT INTO place VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("L100", "ул. Рождественка, д. 12", "Moscow", "Moscow Region", "Russia", "107031", 55.7628, 37.6253, "https://ancient.ivran.ru/rerihovskie-chteniya", "IV RAS main building address"))
    # Org: IV RAS Moscow
    cursor.execute("INSERT INTO organization VALUES (?,?,?,?,?,?,?)",
                   ("O100", "Institute of Oriental Studies of the Russian Academy of Sciences", "Институт востоковедения РАН", "institute", "O001", "https://ancient.ivran.ru/rerihovskie-chteniya", "Primary organizer and venue of Roerich Readings"))
    # Venue: IV RAS Main Venue
    cursor.execute("INSERT INTO venue VALUES (?,?,?,?,?,?,?)",
                   ("V100", "IV RAS (Rozhdestvenka, 12)", "building", "O100", "L100", "https://ancient.ivran.ru/rerihovskie-chteniya", "IV RAS main building"))
    
    conn.commit()
