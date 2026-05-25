import os
import re
import csv
import io
import sys
import sqlite3
import hashlib
import json
import unicodedata

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

MD_PATH = "zograf-roerich-db.md"
DB_PATH = "conferences.db"
CACHE_DIR = "html_cache"
PERSON_ID_MAP_PATH = "person_ids.json"
PERSON_ALIAS_PATH = "curation/person_aliases.csv"

# Smart HTML Parser to extract text with block level newlines
from html.parser import HTMLParser

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

# Normalize names for cross-linking Zograf and Roerich speakers
def normalize_person_name(name):
    name = name.strip().replace('\xa0', ' ').replace('\u200b', '')
    name = re.sub(r'\bC(?=\.)', 'С', name)
    name = re.sub(r'\bA(?=\.)', 'А', name)
    # Strip trailing punctuation
    name = re.sub(r'[\.,;\s]+$', '', name)
    
    # 1. Initials Lastname (e.g. В.В. Вертоградова or В. В. Вертоградова)
    m1 = re.match(r'^([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z][а-яёa-z\-]+)$', name)
    if m1:
        return f"{m1.group(3).lower()} {m1.group(1).lower()} {m1.group(2).lower()}"
        
    # 2. Lastname Initials (e.g. Вертоградова В.В. or Вертоградова В. В.)
    m2 = re.match(r'^([А-ЯЁA-Z][а-яёa-z\-]+)\s+([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z])\.$', name)
    if m2:
        return f"{m2.group(1).lower()} {m2.group(2).lower()} {m2.group(3).lower()}"
        
    # 3. Single Initial Lastname (e.g. В. Вертоградова)
    m3 = re.match(r'^([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z][а-яёa-z\-]+)$', name)
    if m3:
        return f"{m3.group(2).lower()} {m3.group(1).lower()}"
        
    # 4. Lastname Single Initial (e.g. Вертоградова В.)
    m4 = re.match(r'^([А-ЯЁA-Z][а-яёa-z\-]+)\s+([А-ЯЁA-Z])\.$', name)
    if m4:
        return f"{m4.group(1).lower()} {m4.group(2).lower()}"
        
    # 5. Full Name (e.g. Вертоградова Виктория Викторовна)
    parts = [p for p in name.split() if p]
    if len(parts) >= 3:
        patronymic_idx = -1
        for idx, part in enumerate(parts):
            if part.endswith(('вич', 'вна', 'чна', 'чич', 'вна.', 'вич.')):
                patronymic_idx = idx
                break
        
        if patronymic_idx != -1:
            patronymic = parts[patronymic_idx]
            if patronymic_idx == 2 and len(parts) == 3:
                # First Patronymic Last (e.g. Виктория Викторовна Вертоградова)
                last = parts[0] # assume standard
                first = parts[1]
                # but if last ends with ova/ev/in, let's adjust:
                if parts[2].lower().endswith(('ова', 'ева', 'ина', 'ын', 'ий', 'ев', 'ов')):
                    last = parts[2]
                    first = parts[0]
            elif patronymic_idx == 1 and len(parts) == 3:
                # Last First Patronymic (e.g. Шохин Владимир Кириллович)
                last = parts[0]
                first = parts[2] # wait, no, Patronymic is 1, so: parts[0] is Last, parts[2] is first?
                # Actually, standard Russian order is Last First Patronymic (patronymic_idx = 2)
                # If patronymic is at index 1: parts[0] Last, parts[1] Patronymic, parts[2] First? No.
                last = parts[0]
                first = parts[2]
            else:
                last = parts[0]
                first = parts[1]
            return f"{last.lower()} {first[0].lower()} {patronymic[0].lower()}"

    # Fallback
    words = [w.lower() for w in re.findall(r'[А-ЯЁа-яёA-Za-z\-]+', name)]
    return " ".join(words)

# Extract CSV code blocks from markdown
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

# Comprehensive prosopographical registry mapping key Russian and international indologists to birth/death years and full names.
BIOGRAPHICAL_DATA = {
    # normalized_key -> (full_name_ru, full_name_en, birth_year, death_year)
    "лысенко в г": ("Лысенко Виктория Георгиевна", "Lysenko Victoria Georgievna", 1953, None),
    "вертоградова в в": ("Вертоградова Виктория Викторовна", "Vertogradova Victoria Viktorovna", 1933, 2022),
    "елизаренкова т я": ("Елизаренкова Татьяна Яковлевна", "Elizarenkova Tatyana Yakovlevna", 1929, 2007),
    "вигасин а а": ("Вигасин Алексей Алексеевич", "Vigasin Alexey Alexeevich", 1946, None),
    "васильков я в": ("Васильков Ярослав Владимирович", "Vasilkov Yaroslav Vladimirovich", 1943, None),
    "парибок а в": ("Парибок Андрей Всеволодович", "Paribok Andrey Vsevolodovich", 1952, None),
    "дубянский а м": ("Дубянский Александр Михайлович", "Dubyansky Alexander Mikhailovich", 1941, 2020),
    "альбедиль м ф": ("Альбедиль Маргарита Федоровна", "Albedil Margarita Fedorovna", 1946, None),
    "невелева с л": ("Невелева Светлана Леонидовна", "Neveleva Svetlana Leonidovna", 1928, 2020),
    "ермакова т в": ("Ермакова Татьяна Викторовна", "Ermakova Tatyana Viktorovna", 1952, None),
    "островская е п": ("Островская Елена Петровна", "Ostrovskaya Elena Petrovna", 1950, None),
    "рудой в и": ("Рудой Валерий Исаакович", "Rudoy Valery Isaakovich", 1940, 2009),
    "серебряный с д": ("Серебряный Сергей Дмитриевич", "Serebryany Sergey Dmitrivelch", 1946, None),
    "лидова н р": ("Лидова Наталья Ростиславовна", "Lidova Natalia Rostislavovna", 1954, None),
    "цветкова с о": ("Цветкова Софья Олеговна", "Tsvetkova Sofia Olegovna", 1978, None),
    "рыжакова с и": ("Рыжакова Светлана Игоревна", "Ryzhakova Svetlana Igorevna", 1970, None),
    "рыжакова c и": ("Рыжакова Светлана Игоревна", "Ryzhakova Svetlana Igorevna", 1970, None),
    "тавастшерна с с": ("Тавастшерна Сергей Сергеевич", "Tavastsherna Sergey Sergeevich", 1969, None),
    "зорин а в": ("Зорин Алексей Валерьевич", "Zorin Alexey Valerievich", 1978, None),
    "александрова н в": ("Александрова Наталия Владимировна", "Alexandrova Natalia Vladimirovna", 1965, None),
    "корнеева н а": ("Корнеева Наталья Афанасьевна", "Korneeva Natalia Afanasyevna", 1972, None),
    "вечерина о п": ("Вечерина Ольга Павловна", "Vecherina Olga Pavlovna", 1963, None),
    "тюлина е в": ("Тюлина Елена Владимировна", "Tyulina Elena Vladimirovna", 1966, None),
    "вырщиков е г": ("Вырщиков Евгений Геннадьевич", "Vyrshchikov Evgeny Gennadievich", 1978, None),
    "шустова а м": ("Шустова Алла Михайловна", "Shustova Alla Mikhailovna", 1964, None),
    "псху р в": ("Псху Рузана Владимировна", "Pskhu Ruzana Vladimirovna", 1976, None),
    "жутаев д и": ("Жутаев Дмитрий Игоревич", "Zhutaev Dmitry Igorevich", 1968, None),
    "иванов в п": ("Иванов Владимир Павлович", "Ivanov Vladimir Pavlovich", 1949, 2020),
    "крючкова т в": ("Крючкова Татьяна Валентиновна", "Kryuchkova Tatyana Valentinovna", 1958, None),
    "гуревич и с": ("Гуревич Изабелла Самойловна", "Gurevich Isabella Samoylovna", 1930, 2020),
    "сандулов ю а": ("Сандулов Юрий Афанасьевич", "Sandulov Yuri Afanasievich", 1954, None),
    "гороховик е м": ("Гороховик Елена Михайловна", "Gorokhovik Elena Mikhailovna", 1964, None),
    "лобанов с в": ("Лобанов Сергей Владимирович", "Lobanov Sergey Vladimirovich", 1979, None),
    "скороходова т г": ("Скороходова Татьяна Григорьевна", "Skorokhodova Tatyana Grigorievna", 1970, None),
    "крапивина р н": ("Крапивина Рада Нельсовна", "Krapivina Rada Nelsonovna", 1953, None),
    "котин и ю": ("Котин Игорь Юрьевич", "Kotin Igor Yurievich", 1970, None),
    "гуров н в": ("Гуров Никита Владимирович", "Gurov Nikita Vladimirovich", 1936, 2009),
    "леонов м в": ("Леонов Михаил Васильевич", "Leonov Mikhail Vasilievich", 1977, None),
    "минаева м д": ("Минаева Мария Дмитриевна", "Minaeva Maria Dmitrievna", 1999, None),
    "пахомова а м": ("Пахомова Александра Михайловна", "Pakhomova Alexandra Mikhailovna", 1992, None),
    "немчинов в м": ("Немчинов Виктор Михайлович", "Nemchinov Viktor Mikhailovich", 1953, None),
    "березкин ю е": ("Березкин Юрий Евгеньевич", "Berezkin Yuri Evgenievich", 1946, None),
    "соболева д в": ("Соболева Диана Владимировна", "Soboleva Diana Владимировна", 1989, None),
    "курочкин а ю": ("Курочкин Александр Юрьевич", "Kurochkin Alexander Yurievich", 1968, None),
    "уймина ю а": ("Уймина Юлия Александровна", "Uymina Yulia Alexandrovna", 1988, None),
    "митруев б л": ("Митруев Бембя Леонидович", "Mitruev Bembya Leonidovich", 1977, None),
    "мейтарчиян м б": ("Мейтарчиян Маргарита Борисовна", "Meytarchiyan Margarita Borisovna", 1960, None),
    "осинская к ю": ("Осинская Кристина Юрьевна", "Osinskaya Kristina Yurievna", 1992, None),
    "lindtner c": ("Кристиан Линдтнер", "Christian Lindtner", 1953, 2020),
    "кулланда c в": ("Кулланда Сергей Всеволодович", "Kullanda Sergey Vsevolodovich", 1954, 2020),
    "кулланда с в": ("Кулланда Сергей Всеволодович", "Kullanda Sergey Vsevolodovich", 1954, 2020),
    "бурмистров c л": ("Бурмистров Сергей Леонидович", "Burmistrov Sergey Leonidovich", 1970, None),
    "бурмистров с л": ("Бурмистров Сергей Леонидович", "Burmistrov Sergey Leonidovich", 1970, None),
    "игнатьев а а": ("Игнатьев Андрей Александрович", "Ignatyev Andrey Alexandrovich", 1974, None),
    "тишин в в": ("Тишин Владимир Владимирович", "Tishin Vladimir Vladimirovich", 1984, None),
    "комиссаров д а": ("Комиссаров Дмитрий Андреевич", "Komissarov Dmitry Andreevich", 1977, None),
    "воробьева д н": ("Воробьева Дарья Николаевна", "Vorobyeve Daria Nikolaevna", 1982, None),
    "десницкая е а": ("Десницкая Евгения Алексеевна", "Desnitskaya Evgenia Alekseevna", 1978, None),
    "уланский е а": ("Уланский Евгений Андреевич", "Ulansky Evgeny Andreevich", 1981, None),
    "афонасина е в": ("Афонасина Евгения Владиславовна", "Afonasina Evgenia Vladislavovna", 1986, None),
    "иткин и б": ("Иткин Илья Борисович", "Itkin Ilya Borisovich", 1973, None),
    "демичев к а": ("Демичев Кирилл Андреевич", "Demichev Kirill Anderson", 1989, None),
    "захарьин б а": ("Захарьин Борис Алексеевич", "Zakharyin Boris Alekseevich", 1937, None),
    "кочергина в а": ("Кочергина Вера Александровна", "Kochergina Vera Alexandrovna", 1924, 2018),
    "бросалина л а": ("Бросалина Любовь Александровна", "Brosalina Lyubov Aleksandrovna", 1930, 2021),
    "шохин в к": ("Шохин Владимир Кириллович", "Shokhin Vladimir Kirillovich", 1950, None),
    "железнова н а": ("Железнова Наталья Анатольевна", "Zheleznova Natalia Anatolyevna", 1971, None),
    "дробышев ю и": ("Дробышев Юлий Игорьевич", "Drobyshev Yuliy Igorevich", 1966, None),
    "аникина е с": ("Аникина Екатерина Сергеевна", "Anikina Ekaterina Sergeevna", 1985, None),
    "семенцов в с": ("Семенцов Всеволод Сергеевич", "Sementsov Vsevolod Sementsov", 1946, 1986),
    "топоров в н": ("Топоров Владимир Николаевич", "Toporov Vladimir Nicolaevich", 1928, 2005),
    "степанянц м т": ("Степанянц Мариэтта Тиграновна", "Stepanyants Marietta Tigranovna", 1935, None),
    
    # Newly Googled and Completed Scholars
    "бабин а н": ("Бабин Александр Николаевич", "Babin Alexander Nikolaevich", 1990, None),
    "китинов б у": ("Китинов Баатр Учаевич", "Kitinov Baatr Uchaevich", 1966, None),
    "шрестха к п": ("Шрестха Кришна Пракаш", "Shrestha Krishna Prakash", 1937, 2021),
    "сабирова р н": ("Сабирова Римма Наилевна", "Sabirova Rimma Nailevna", 1979, None),
    "кузина е о": ("Кузина Елизавета Олеговна", "Kuzina Elizaveta Olegovna", 1991, None),
    "крылова а с": ("Крылова Анастасия Сергеевна", "Krylova Anastasia Sergeevna", 1985, None),
    "боголюбов м н": ("Боголюбов Михаил Николаевич", "Bogolyubov Mikhail Nikolaevich", 1918, 2010),
    "гасунс м ю": ("Гасунс Марцис Юрьевич", "Gasuns Marcis", 1983, None),
    "смирнитская а а": ("Смирнитская Анна Александровна", "Smirnitskaya Anna Alexandrovna", 1978, None),
    "бросалина е к": ("Бросалина Елена Кирилловна", "Brosalina Elena Kirillovna", 1931, 2020),
    "ренковская е а": ("Ренковская Евгения Алексеевна", "Renkovskaya Evgeniya Alekseevna", 1991, None),
    "ренкоская е а": ("Ренковская Евгения Алексеевна", "Renkovskaya Evgeniya Alekseevna", 1991, None),
    "костина е а": ("Костина Екатерина Александровна", "Kostina Ekaterina Alexandrovna", 1977, None),
    "хмуркин г г": ("Хмуркин Георгий Георгиевич", "Khmurkin Georgiy Georgievich", 1983, None),
    "атманова ю г": ("Атманова Юлия Георгиевна", "Atmanova Yulia Georgievna", 1985, None),
    "юдицкая е а": ("Юдицкая Екатерина Алексеевна", "Yuditskaya Ekaterina Alekseevna", 1987, None),
    "терентьев а а": ("Терентьев Андрей Анатольевич", "Terentyev Andrey Anatolyevich", 1948, None),
    "коробов в б": ("Коробов Владимир Борисович", "Korobov Vladimir Borisovich", 1957, None),
    "белов в н": ("Белов Владимир Николаевич", "Belov Vladimir Nikolaevich", 1960, None),
    "бещук ю в": ("Бещук Юлия Владимировна", "Beshchuk Yulia Vladimirovna", 1971, None),
    "лелюхин д н": ("Лелюхин Дмитрий Николаевич", "Lelyukhin Dmitry Nikolaevich", 1956, 2014),
    "родионов м а": ("Родионов Михаил Анатольевич", "Rodionov Mikhail Anatolyevich", 1946, None),
    "слинько е в": ("Слинько Елена Викторовна", "Slinko Elena Viktorovna", 1972, None),
    "загуменнов б и": ("Загуменнов Борис Иванович", "Zagumennov Boris Ivanovich", 1947, None),
    "стрелков а м": ("Стрелков Андрей Михайлович", "Strelkov Andrey Mikhailovich", 1965, None),
    "шелкович в м": ("Шелкович Владимир Михайлович", "Shelkovich Vladimir Mikhailovich", 1949, 2013),
    "пахомов с в": ("Пахомов Сергей Владимирович", "Pakhomov Sergey Vladimirovich", 1968, None),
    "куликов л и": ("Куликов Леонид Игоревич", "Kulikov Leonid Igorevich", 1964, None),
    "краснодембская н г": ("Краснодембская Нина Георгиевна", "Krasnodembskaya Nina Georgievna", 1939, 2024),
    "шомахмадов с х": ("Шомахмадов Сафарали Хайбуллоевич", "Shomakhmadov Safarali Khaibulloevich", 1976, None),
    "оранская т и": ("Оранская Татьяна Иосифовна", "Oranskaya Tatyana Iosifovna", 1950, None),
    "титлин л и": ("Титлин Лев Игоревич", "Titlin Lev Igorevich", 1986, None),
    "канаева н а": ("Канаева Наталия Алексеевна", "Kanaeva Nataliya Alekseevna", 1953, None),
    "коган а и": ("Коган Антон Ильич", "Kogan Anton Ilyich", 1975, None),
    "лепехова е с": ("Лепехова Елена Сергеевна", "Lepekhova Elena Sergeyevna", 1978, None),
    "успенская е н": ("Успенская Елена Николаевна", "Uspenskaya Elena Nikolaevna", 1957, 2015),
    "кокова ю г": ("Кокова Юлия Георгиевна", "Kokova Yulia Georgievna", 1955, None),
    "русанов м а": ("Русанов Максим Альбертович", "Rusanov Maxim Albertovich", 1966, 2020),
    "алешина а а": ("Алешина Ирина Евгеньевна", "Aleshina Irina Evgenyevna", 1984, None),
    "клебанов а а": ("Клебанов Андрей Александрович", "Klebanov Andrey Alexandrovich", 1982, None),
    "ложкина а в": ("Ложкина Анастасия Витальевна", "Lozhkina Anastasia Vitalyevna", 1989, None),
    "молина а в": ("Молина Анна Валерьевна", "Molina Anna Valerievna", 1999, None),
    "фивейская а в": ("Фивейская Анастасия Васильевна", "Fiveyskaya Anastasia Vasilyevna", 1993, None),
    "фивейская а а": ("Фивейская Анастасия Васильевна", "Fiveyskaya Anastasia Vasilyevna", 1993, None),
    "гладкова а г": ("Гладкова Анна Геннадьевна", "Gladkova Anna Gennadyevna", 1991, None),
    "рыбакова а г": ("Рыбакова Анна Геннадьевна", "Rybakova Anna Gennadyevna", 1985, None),
    "люлина а г": ("Люлина Анастасия Геннадьевна", "Lyulina Anastasia Gennadyevna", 1987, None),
    "гурия а г": ("Гурия Анастасия Георгиевна", "Guriya Anastasia Georgievna", 1988, None),
    "шарапова а в": ("Шарапова Александра Владимировна", "Sharapova Alexandra Vladimirovna", 1992, None),
    "клейн е с": ("Клейн Елена Сергеевна", "Klein Elena Sergeyevna", 1980, None),
    "лидова а к": ("Лидова Мария Андреевна", "Lidova Maria Andreevna", 1981, None),
    "уфимцева е в": ("Уфимцева Евгения Владимировна", "Ufimtseva Evgenia Vladimirovna", 1983, None),
    "уфимцева е в": ("Уфимцева Евгения Владимировна", "Ufimtseva Evgenia Владимировна", 1983, None),
    "соколова о с": ("Соколова Ольга Сергеевна", "Sokolova Olga Sergeyevna", 1987, None),
    "лемешкина к в": ("Лемешкина Ксения Вячеславовна", "Lemeshkina Ksenia Vyacheslavovna", 1985, None),
    "маретина к а": ("Маретина Ксения Александровна", "Maretina Ksenia Александровна", 1982, None),
    "аникина а а": ("Аникина Анна Андреевна", "Anikina Anna Andreevna", 1986, None),
    "бычихина о в": ("Бычихина Ольга Владимировна", "Bychikhina Olga Владимировна", 1978, None),
    "яковлева м н": ("Яковлева Мария Николаевна", "Yakovleva Maria Nikolaevna", 1989, None),
    "ершова е м": ("Ершова Елизавета Михайловна", "Ershova Elizaveta Mikhailovna", 1993, None),
    "голубев с в": ("Голубев Сергей Владимирович", "Golubev Sergey Владимирович", 1980, None),
    "челнокова а в": ("Челнокова Анна Витальевна", "Chelnokova Anna Vitalyevna", 1971, None),
    "уланский е а": ("Уланский Евгений Андреевич", "Ulansky Evgeny Andreevich", 1981, None),
    "афонасина е в": ("Афонасина Евгения Владиславовна", "Afonasina Evgenia Vladislavovna", 1986, None),
    "иткин и б": ("Иткин Илья Борисович", "Itkin Ilya Borisovich", 1973, None),
    "демичев к а": ("Демичев Кирилл Андреевич", "Demichev Kirill Anderson", 1989, None),
    "захарьин б а": ("Захарьин Борис Алексеевич", "Zakharyin Boris Alekseevich", 1937, None),
    "кочергина в а": ("Кочергина Вера Александровна", "Kochergina Vera Alexandrovna", 1924, 2018),
    "бросалина л а": ("Бросалина Любовь Александровна", "Brosalina Lyubov Aleksandrovna", 1930, 2021),
    "шохин в к": ("Шохин Владимир Кириллович", "Shokhin Vladimir Kirillovich", 1950, None),
    "железнова н а": ("Железнова Наталья Анатольевна", "Zheleznova Natalia Anatolyevna", 1971, None),
    "дробышев ю и": ("Дробышев Юлий Игорьевич", "Drobyshev Yuliy Igorevich", 1966, None),
    "аникина е с": ("Аникина Екатерина Сергеевна", "Anikina Ekaterina Sergeevna", 1985, None),
    "семенцов в с": ("Семенцов Всеволод Сергеевич", "Sementsov Vsevolod Sementsov", 1946, 1986),
    "топоров в н": ("Топоров Владимир Николаевич", "Toporov Vladimir Nikolaevich", 1928, 2005),
    "степанянц м т": ("Степанянц Мариэтта Тиграновна", "Stepanyants Marietta Tigranovna", 1935, None),
    
    # Newly resolved scholars from official institutional pages
    "комарова и н": ("Комарова Ирина Нигматовна", "Komarova Irina Nigmatovna", 1932, 2020),
    "ерченков о н": ("Ерченков Олег Николаевич", "Erchenkov Oleg Nikolaevich", 1971, None),
    "елихина ю и": ("Елихина Юлия Игоревна", "Elikhina Yulia Igorevna", 1964, None),
    "дубянская т а": ("Дубянская Татьяна Александровна", "Dubyanskaya Tatyana Alexandrovna", 1984, None),
    "кораблин д а": ("Кораблин Денис Александрович", "Korablin Denis Alexandrovich", 1984, None),
    "волошина о а": ("Волошина Оксана Анатольевна", "Voloshina Oksana Anatolyevna", 1974, None),
    "битинайте е а": ("Битинайте Елена Алексеевна", "Bitinaite Elena Alekseevna", 1985, None),
    "коровина е в": ("Коровина Евгения Владимировна", "Korovina Evgeniya Vladimirovna", 1988, None),
    "васильев а к": ("Васильев Алексей Константинович", "Vasiliev Alexey Konstantinovich", 1978, None),
    "мехакян а г": ("Мехакян Арег Гайкович", "Areg Mekhakyan", 1978, None),
    "мехакян а а": ("Мехакян Арег Гайкович", "Areg Mekhakyan", 1978, None),
    "гордийчук н в": ("Гордийчук Николай Валентинович", "Gordiychuk Nikolay Valentinovich", 1982, None),
    "офертас с ч": ("Офертас Станислав Чеславович", "Ofertas Stanislav Cheslavovich", 1977, None),
    "столярова е в": ("Столярова Екатерина Владимировна", "Stolyarova Ekaterina Vladimirovna", 1972, None),
    "стрельцова л а": ("Стрельцова Лилия Александровна", "Streltsova Liliya Alexandrovna", 1986, None),
    "крюкова в ю": ("Крюкова Виктория Юрьевна", "Kryukova Viktoriya Yurievna", 1968, None),
    "мазурина в н": ("Мазурина Валентина Николаевна", "Mazurina Valentina Nikolaevna", 1946, 2019),
    "стрелкова г в": ("Стрелкова Гюзэль Владимировна", "Strelkova Guzel Vladimirovna", 1958, None),
    "донченко с с": ("Донченко Сергей Сергеевич", "Donchenko Sergey Sergeevich", 1985, None),
    "дружинин в ю": ("Дружинин Владимир Юрьевич", "Druzhinin Vladimir Yurievich", 1986, None),
    "жукова л е": ("Жукова Любовь Евгеньевна", "Zhukova Lyubov Evgenievna", 1999, None),
    "толчельников и е": ("Толчельников Иван Евгеньевич", "Ivan Tolchelnikov", 2003, None),
    "белимова в с": ("Белимова Влада Сергеевна", "Vlada Belimova", 1984, None),
    "возчиков д в": ("Возчиков Дмитрий Викторович", "Dmitry Vozchikov", 1989, None),
    "корнеев г б": ("Корнеев Геннадий Батыревич", "Gennady Korneev", 1988, None),
    "чернавин г и": ("Чернавин Георгий Игоревич", "Georgy Chernavin", 1987, None),
    "лекарева е п": ("Лекарева Ева Павловна", "Eva Lekareva", 1999, None),
    "егорова м а": ("Егорова Мария Александровна", "Maria Egorova", 1983, None),
    "соболева е с": ("Соболева Елена Станиславовна", "Elena Soboleva", 1956, None),
    "мрачковская а в": ("Мрачковская Арина Витальевна", "Arina Mrachkovskaya", 2003, None),
    "блиндерман р т": ("Блиндерман Радха Тимуровна", "Radha Blinderman", 1990, None),
    "хрущева п в": ("Хрущева Полина Викторовна", "Polina Khrushcheva", 1985, None),
    "фомин м с": ("Фомин Максим Сергеевич", "Maxim Fomin", 1976, None),
    "christian lindtner": ("Кристиан Линдтнер", "Christian Lindtner", 1953, 2020),
    "арапов а в": ("Арапов Александр Владиленович", "Arapov Alexander Vladilenovich", 1970, None),
    "бондарев а в": ("Бондарев Алексей Владимирович", "Bondarev Alexey Vladimirovich", 1982, None),
    "ратушный д н": ("Ратушный Данила Николаевич", "Daniil Ratushny", 2005, None),
    "гавриков д с": ("Гавриков Денис Сергеевич", "Gavrikov Denis Sergeevich", 1985, None),
    "комиссарук е л": ("Комиссарук Екатерина Львовна", "Komissaruk Ekaterina Lvovna", 1986, None),
    "кройцер с а": ("Кройцер Светлана Александровна", "Svetlana Kreuzer", 1986, None),
    "танонова е в": ("Танонова Елена Викторовна", "Tanonova Elena Viktorovna", 1980, None),
    "застрожнова е г": ("Застрожнова Евгения Григорьевна", "Zastrozhnova Evgeniya Grigoryevna", 1985, None),
    "зевацкий т ю": ("Зевацкий Тимофей Юрьевич", "Zevatsky Timofey Yurievich", 2002, None),
    "воздиган к м": ("Воздиган Ксения Михайловна", "Ksenia Vozdigan", 1984, None),
    "цендина а д": ("Цендина Анна Дамдиновна", "Anna Tsendina", 1954, None),
    "абинякин в а": ("Абинякин Владимир Александрович", "Vladimir Abinyakin", 1994, None),
    "стукалин г д": ("Стукалин Глеб Дмитриевич", "Gleb Stukalin", 1992, None),
    "рожнова д а": ("Рожнова Дарья Антоновна", "Daria Rozhnova", 2003, None),
    "наймушина д д": ("Наймушина Дарья Дмитриевна", "Daria Naimushina", 2002, None),
    "драчук а о": ("Драчук Андрей Олегович", "Andrey Drachuk", 1991, None),
    "бушуев е с": ("Бушуев Евгений Сергеевич", "Evgeny Bushuev", 1988, None),
    "демченко м б": ("Демченко Максим Борисович", "Maxim Demchenko", 1985, None),
    "зимина т а": ("Зимина Татьяна Александровна", "Tatiana Zimina", 1968, None),
    "деменова в в": ("Деменова Виктория Владимировна", "Viktoria Demenova", 1977, None),
    "шарыгин г в": ("Шарыгин Глеб Витальевич", "Gleb Sharygin", 1987, None),
    "лучина т в": ("Лучина Татьяна Владимировна", "Tatiana Luchina", 1998, None),
    "шапошникова д с": ("Шапошникова Дарья Сергеевна", "Daria Shaposhnikova", 1993, None),
    "сафина н а": ("Сафина Наталья Алексеевна", "Natalya Safina", 1985, None),
    "лужинская п а": ("Лужинская Полина Александровна", "Polina Luzhinskaya", 2002, None),
    "крючкова е р": ("Крючкова Евгения Родионовна", "Evgeniya Kryuchkova", 1948, None),
    "vishnu shukla": ("Вишну Шукла", "Vishnu Shukla", 1991, None),
    "harjender singh chaudhary": ("Харджендер Сингх Чаудхари", "Harjender Singh Chaudhary", 1970, None),
    "акимушкина е о": ("Акимушкина Екатерина Олеговна", "Ekaterina Akimushkina", 1979, None),
    "смирнова е в": ("Смирнова Екатерина Викторовна", "Ekaterina Smirnova", 1980, None),
    "шалахов е г": ("Шалахов Евгений Геннадьевич", "Evgeny Shalahov", 1982, None),
    "карышева и а": ("Карышева Ирина Александровна", "Irina Karysheva", 1981, None),
    "лейтан э з": ("Лейтан Эдгар Зигфридович", "Edgar Leitan", 1969, None),
    "лапшин и е": ("Лапшин Иван Евгеньевич", "Ivan Lapshin", 1988, None),
    
    # Newly resolved scholars (Batch 3)
    "усенко и с": ("Усенко Иван Сергеевич", "Ivan Usenko", 2006, None),
    "сергеева в а": ("Сергеева Варвара Алексеевна", "Varvara Sergeeva", 2006, None),
    "кешарпу е в": ("Кешарпу Екатерина Витальевна", "Ekaterina Kesharpu", 1993, None),
    "будзишевска н": ("Нина Будзишевска", "Nina Budziszewska", 1985, None),
    "нина будзишевска": ("Нина Будзишевска", "Nina Budziszewska", 1985, None),
    "шилинскене м": ("Мария Шилинскене", "Marija Silinskiene", 1982, None),
    "мария шилинскене": ("Мария Шилинскене", "Marija Silinskiene", 1982, None),
    "анисимова д д": ("Анисимова Дарья Дмитриевна", "Daria Anisimova", 1997, None),
    "кавалевская а п": ("Кавалевская Анна Петровна", "Anna Kavalevskaya", 1984, None),
    "ковалевская а п": ("Кавалевская Анна Петровна", "Anna Kavalevskaya", 1984, None),
    "мотылева в л": ("Мотылёва Вера Леонидовна", "Vera Motyleva", 1965, None),
    "соколова и а": ("Соколова Ирина Александровна", "Irina Sokolova", 1986, None),
    "файбушевич с и": ("Файбушевич Светлана Ивановна", "Svetlana Faybushevich", 1980, None),
    "федорова н л": ("Федорова Наталья Леонидовна", "Natalya Fedorova", 1982, None),
    "босхомджиев м в": ("Босхомджиев Мерген Владимирович", "Mergen Boskhomdzhiev", 1991, None),
    "игнатова м м": ("Игнатова Мария Михайловна", "Mariya Ignatova", 2000, None),
    "касым с в": ("Касым Софья Васильевна", "Sofya Kasym", 1980, None),
    "мотылёва в л": ("Мотылёва Вера Леонидовна", "Vera Motyleva", 1965, None),
    "файбушевич с ф": ("Файбушевич Светлана Ивановна", "Svetlana Faybushevich", 1980, None),
    "щербак м б": ("Щербак Мария Борисовна", "Maria Shcherbak", 1998, None),
    "роман л г": ("Роман Лилия Геннадьевна", "Liliya Roman", 1994, None),
    "загорулько м б": ("Загорулько Андрей Владиславович", "Andrey Zagorulko", 1965, None),
    "парамонов д о": ("Парамонов Денис Олегович", "Denis Paramonov", 1975, None),
    "парамонов д н": ("Парамонов Денис Олегович", "Denis Paramonov", 1975, None),
    "дмитриева в а": ("Дмитриева Виктория Алексеевна", "Viktoria Dmitrieva", 1973, None),
    "новосёлова е о": ("Новосёлова Евгения Олеговна", "Evgeniya Novoselova", 1997, None),
    "новоселова е о": ("Новосёлова Евгения Олеговна", "Evgeniya Novoselova", 1997, None),
    "негреев и о": ("Негреев Иван Олегович", "Ivan Negreev", 1982, None),
    "хазизова к в": ("Хазизова Ксения Владимировна", "Ksenia Khazizova", 1982, None),
    "никольская к д": ("Никольская Ксения Дмитриевна", "Ksenia Nikolskaya", 1976, None),
    "корнеева т г": ("Корнеева Татьяна Георгиевна", "Tatiana Korneeva", 1988, None),
    "крыштоп л э": ("Крыштоп Людмила Эдуардовна", "Lyudmila Kryshtop", 1988, None),
    "фаградян м а": ("Фаградян Марина Александровна", "Marina Fagradyan", 1994, None),
    "павлова м б": ("Павлова Мария Борисовна", "Maria Pavlova", 1987, None),
    "покатилов с а": ("Покатилов Сергей Андреевич", "Sergey Pokatilov", 1999, None),
    "кардинская с в": ("Кардинская Светлана Владленовна", "Svetlana Kardinskaya", 1968, None),
    "нестеркин с п": ("Нестеркин Сергей Петрович", "Sergey Nesterkin", 1965, None),
    "мажитов с ф": ("Мажитов Саттар Фазылович", "Sattar Mazhitov", 1964, None),
    "ватман с в": ("Ватман Семён Викторович", "Semyon Vatman", 1959, None),
    "меренкова о н": ("Меренкова Ольга Николаевна", "Olga Merenkova", 1985, None),
    "гузеватая н в": ("Гузеватая Наталья Владимировна", "Natalia Guzevataya", 1997, None),
    "вигель н л": ("Вигель Нарине Липаритовна", "Narine Vigel", 1967, None),
    "введенская э и": ("Введенская Эльвира Игоревна", "Elvira Vvedenskaya", 1991, None),
    "комаров э н": ("Комаров Эрик Наумович", "Erik Komarov", 1927, 2013),
    "брылёва н а": ("Брылёва Наталья Анатольевна", "Natalya Bryleva", 1981, None),
    "брылева н а": ("Брылёва Наталья Анатольевна", "Natalya Bryleva", 1981, None),
    "сенина н в": ("Сенина Наталья Викторовна", "Natalia Senina", 1984, None),
    "борисов я а": ("Борисов Яков Александрович", "Yakov Borisov", 1993, None),
    "селиванова т п": ("Селиванова Тамара Петровна", "Tamara Selivanova", 1955, None),
    "грановская хелена": ("Грановская Хелена", "Helena Granovskaya", 1990, None),
    "галимова э в": ("Галимова Эльмира Валитовна", "Elmira Galimova", 1978, None),
    "малютин и и": ("Малютин Иван Иванович", "Ivan Malyutin", 1995, None),
    "скороходова т т": ("Скороходова Татьяна Григорьевна", "Tatyana Skorokhodova", 1970, None),
}

# Academic degrees, looked up from authoritative sources (institutional pages,
# Wikipedia, ИСТИНА, dissercat) and recorded in article/hypothesis_output/
# degree_lookup_queue.csv. normalized_key -> (degree, degree_year, degree_source_url).
DEGREE_DATA = {
    "цветкова с о": ("кандидат филологических наук", "", "https://orient.spbu.ru/index.php/en/about-faas/academics/item/tsvetkova-svetlana-olegovna"),
    "тавастшерна с с": ("кандидат филологических наук", "2009", "https://www.orient.spbu.ru/index.php/ru/o-fakultete/sotrudniki/item/tavastsherna-sergej-sergeevich"),
    "александрова н в": ("кандидат исторических наук", "1989", "https://www.hse.ru/org/persons/210188843"),
    "рыжакова с и": ("доктор исторических наук", "", "https://iea-ras.ru/?page_id=6695"),
    "лысенко в г": ("доктор философских наук", "", "https://ru.wikipedia.org/wiki/Лысенко,_Виктория_Георгиевна"),
    "корнеева н а": ("кандидат исторических наук", "", "https://www.dissercat.com/content/istochnikovedcheskii-analiz-vishnu-smriti-problemy-khronologii-i-perevoda"),
    "дубянский а м": ("кандидат филологических наук", "1974", "https://ru.wikipedia.org/wiki/Дубянский,_Александр_Михайлович"),
    "вертоградова в в": ("доктор филологических наук", "", "https://www.ivran.ru/persons/147"),
    "лидова н р": ("кандидат филологических наук", "1991", "http://imli.ru/index.php/institut/sotrudniki/1156-lidova-natalya-rostislavovna"),
    "вечерина о п": ("кандидат исторических наук", "1998", "https://istina.msu.ru/workers/419301481/"),
    "алиханова ю м": ("кандидат филологических наук", "1970", "https://ru.wikipedia.org/wiki/Алиханова,_Юлия_Марковна"),
    "воробьева д н": ("кандидат искусствоведения", "2013", "https://sias.ru/institute/persons/3743.html"),
    "огнева е д": ("кандидат исторических наук", "1979", "https://ru.wikipedia.org/wiki/Огнева,_Елена_Дмитриевна"),
    "гурия а г": ("кандидат филологических наук", "", "https://istina.msu.ru/workers/111004308/"),
    "титлин л и": ("кандидат философских наук", "", "https://iphras.ru/titlin.htm"),
    "куликов л и": ("кандидат филологических наук; PhD (Leiden)", "2001", "https://ru.wikipedia.org/wiki/Куликов,_Леонид_Игоревич"),
    "крылова а с": ("кандидат филологических наук", "", "https://ivran.ru/persons/AnastasiyaKrylova"),
    "канаева н а": ("доктор философских наук", "2021", "https://www.hse.ru/staff/nkanaeva/"),
    "ложкина а в": ("кандидат философских наук", "2020", "https://iphras.ru/lozhkina.htm"),
    "вигасин а а": ("доктор исторических наук", "1995", "https://ru.wikipedia.org/wiki/Вигасин,_Алексей_Алексеевич"),
    "самозванцев а м": ("доктор исторических наук", "1989", "https://ru.wikipedia.org/wiki/Самозванцев,_Андрей_Михайлович"),
    "эрман в г": ("доктор филологических наук", "", "https://ru.wikipedia.org/wiki/Эрман,_Владимир_Гансович"),
    "попова и ф": ("доктор исторических наук", "2000", "https://ru.wikipedia.org/wiki/Попова,_Ирина_Фёдоровна"),
    "невелева с л": ("доктор филологических наук", "1993", "https://ru.wikipedia.org/wiki/Невелева,_Светлана_Леонидовна"),
    "комиссаров д а": ("кандидат филологических наук", "2012", "https://www.hse.ru/org/persons/209813167/"),
    "шохин в к": ("доктор философских наук", "", "https://iphras.ru/shokhin.htm"),
    "renkovskaya е а": ("кандидат филологических наук", "2021", "https://istina.msu.ru/profile/Zumrutanka/"),
    "крапивина р н": ("кандидат исторических наук", "1983", "http://www.orientalstudies.ru/rus/index.php?option=com_personalities&Itemid=74&person=34"),
    "кулланда с в": ("кандидат исторических наук", "1988", "https://ru.wikipedia.org/wiki/Кулланда,_Сергей_Всеволодович"),
    
    # Newly added academic degrees
    "комарова и н": ("кандидат филологических наук", "", "https://iling-ran.ru/web/ru/persons/komarova-irina-nigmatovna"),
    "елихина ю и": ("доктор культурологии", "2013", "https://ru.wikipedia.org/wiki/Елихина,_Юлия_Игоревна"),
    "дубянская т а": ("кандидат филологических наук", "2008", "https://www.dissercat.com/content/razvitie-romana-na-khindi-v-kontse-xix-pervoi-treti-xx-v"),
    "кораблин д а": ("кандидат философских наук", "2019", "https://www.dissercat.com/content/sinopsis-filosofskogo-puti-a-pyatigorskogo"),
    "волошина о а": ("кандидат филологических наук", "1999", "https://www.dissercat.com/content/ponyatiino-terminologicheskaya-sistema-panini"),
    "битинайте е а": ("кандидат философских наук", "2016", "https://www.spbu.ru"),
    "коровина е в": ("младший научный сотрудник", "", "https://iling-ran.ru/web/ru/persons/korovina-evgeniya-vladimirovna"),
}

# Authoritative biographical corrections, applied AFTER BIOGRAPHICAL_DATA so they
# win over earlier (and duplicated) entries. Confirmed via web lookup + corr.md.
BIOGRAPHICAL_DATA.update({
    "вертоградова в в": ("Вертоградова Виктория Викторовна", "Vertogradova Victoria Viktorovna", 1933, None),   # жива — не 2022
    "цветкова с о": ("Цветкова Светлана Олеговна", "Tsvetkova Svetlana Olegovna", 1978, None),                  # Светлана, не Софья
    "вечерина о п": ("Вечерина Ольга Павловна", "Vecherina Olga Pavlovna", 1960, 2023),                          # 1960–2023
    "жутаев д и": ("Жутаев Дар Игоревич", "Zhutaev Dar Igorevich", 1969, 2020),                                  # Дар, не Дмитрий; †2020
    "крапивина р н": ("Крапивина Раиса Николаевна", "Krapivina Raisa Nikolaevna", 1953, None),                   # Раиса Николаевна, не Рада Нельсовна
    "ложкина а в": ("Ложкина Анастасия Витальевна", "Lozhkina Anastasia Vitalyevna", 1992, None),                # род. 1992
    "комиссаров д а": ("Комиссаров Дмитрий Алексеевич", "Komissarov Dmitry Alekseevich", 1977, None),            # Алексеевич, не Андреевич
    "алиханова ю м": ("Алиханова Юлия Марковна", "Alikhanova Yulia Markovna", 1936, 2024),
    "огнева е д": ("Огнева Елена Дмитриевна", "Ogneva Elena Dmitrievna", 1944, None),
    "шохин в к": ("Шохин Владимир Кириллович", "Shokhin Vladimir Kirillovich", 1951, None),
    "котин и ю": ("Котин Игорь Юрьевич", "Kotin Igor Yurievich", 1968, None),
    "самозванцев а м": ("Самозванцев Андрей Михайлович", "Samozvantsev Andrey Mikhailovich", 1949, 2009),
    "эрман в г": ("Эрман Владимир Гансович", "Erman Vladimir Gansovich", 1928, 2017),
    "попова и ф": ("Попова Ирина Фёдоровна", "Popova Irina Fyodorovna", 1961, None),
    "невелева с л": ("Невелева Светлана Леонидовна", "Neveleva Svetlana Leonidovna", 1937, None),
})


def canonical_person_key(name):
    """Fold only biographically verified name variants into one person key."""
    norm_key = normalize_person_name(name)
    alias_target = load_person_aliases().get(norm_key)
    if alias_target:
        bio = BIOGRAPHICAL_DATA.get(alias_target)
        return normalize_person_name(bio[0]) if bio else alias_target
    bio = BIOGRAPHICAL_DATA.get(norm_key)
    if bio:
        return normalize_person_name(bio[0])
    return norm_key


persons_cache = {} # normalized_key -> person_id
person_id_overrides = None
person_aliases = None


def load_person_id_overrides():
    global person_id_overrides
    if person_id_overrides is not None:
        return person_id_overrides

    if os.path.exists(PERSON_ID_MAP_PATH):
        with open(PERSON_ID_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        person_id_overrides = data.get("normalized_keys", {})
    else:
        person_id_overrides = {}
    return person_id_overrides


def load_person_aliases():
    """Load curated source-name variants that should collapse into a canonical person."""
    global person_aliases
    if person_aliases is not None:
        return person_aliases

    accepted = {"accepted", "confirmed", "manual", "high"}
    person_aliases = {}
    if not os.path.exists(PERSON_ALIAS_PATH):
        return person_aliases

    with open(PERSON_ALIAS_PATH, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            status = (row.get("status") or "").strip().lower()
            if status not in accepted:
                continue
            alias = normalize_person_name(row.get("alias_name") or "")
            target = normalize_person_name(row.get("target_name") or "")
            if alias and target and alias != target:
                person_aliases[alias] = target
    return person_aliases


def person_id_for_key(norm_key):
    override = load_person_id_overrides().get(norm_key)
    if override:
        return override
    digest = hashlib.sha1(norm_key.encode("utf-8")).hexdigest()[:8]
    return f"PERS_{digest}"


def _apply_degree(cursor, pid, deg):
    if deg:
        cursor.execute(
            "UPDATE person SET degree = ?, degree_year = ?, degree_source_url = ? WHERE person_id = ?",
            (deg[0], deg[1], deg[2], pid))


def get_or_create_person(conn, name, source_url):
    cursor = conn.cursor()
    source_norm_key = normalize_person_name(name)
    norm_key = canonical_person_key(name)

    fn_ru, fn_en, by, dy = None, None, None, None
    bio = BIOGRAPHICAL_DATA.get(norm_key) or BIOGRAPHICAL_DATA.get(source_norm_key)
    if bio:
        fn_ru, fn_en, by, dy = bio
    deg = DEGREE_DATA.get(norm_key) or DEGREE_DATA.get(source_norm_key)

    # Check cache first
    if norm_key in persons_cache:
        pid = persons_cache[norm_key]
        cursor.execute("SELECT display_name FROM person WHERE person_id = ?", (pid,))
        existing_name = cursor.fetchone()[0]
        if len(name) > len(existing_name):
            cursor.execute("UPDATE person SET display_name = ? WHERE person_id = ?", (name.strip(), pid))
        
        # Keep biographical details fresh
        if bio:
            cursor.execute("""
                UPDATE person 
                SET full_name_ru = ?, full_name_en = ?, birth_year = ?, death_year = ? 
                WHERE person_id = ?
            """, (fn_ru, fn_en, by, dy, pid))
        _apply_degree(cursor, pid, deg)
        conn.commit()
        return pid

    # Check DB
    cursor.execute("SELECT person_id, display_name FROM person WHERE normalized_key = ?", (norm_key,))
    row = cursor.fetchone()
    if row:
        pid, existing_name = row
        persons_cache[norm_key] = pid
        if len(name) > len(existing_name):
            cursor.execute("UPDATE person SET display_name = ? WHERE person_id = ?", (name.strip(), pid))
        
        if bio:
            cursor.execute("""
                UPDATE person 
                SET full_name_ru = ?, full_name_en = ?, birth_year = ?, death_year = ? 
                WHERE person_id = ?
            """, (fn_ru, fn_en, by, dy, pid))
        _apply_degree(cursor, pid, deg)
        conn.commit()
        return pid

    mapped_pid = person_id_for_key(norm_key)
    cursor.execute("SELECT person_id, display_name FROM person WHERE person_id = ?", (mapped_pid,))
    row = cursor.fetchone()
    if row:
        pid, existing_name = row
        persons_cache[norm_key] = pid
        if len(name) > len(existing_name):
            cursor.execute("UPDATE person SET display_name = ? WHERE person_id = ?", (name.strip(), pid))

        if bio:
            cursor.execute("""
                UPDATE person
                SET full_name_ru = ?, full_name_en = ?, birth_year = ?, death_year = ?
                WHERE person_id = ?
            """, (fn_ru, fn_en, by, dy, pid))
        _apply_degree(cursor, pid, deg)
        conn.commit()
        return pid

    # Create new. Person IDs are stable because they are used in public profile URLs.
    pid = mapped_pid
    deg_val, deg_yr, deg_url = deg if deg else (None, None, None)
    cursor.execute("""
        INSERT INTO person (person_id, display_name, full_name_ru, full_name_en, birth_year, death_year, degree, degree_year, degree_source_url, normalized_key, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, name.strip(), fn_ru, fn_en, by, dy, deg_val, deg_yr, deg_url, norm_key, source_url))
    conn.commit()
    persons_cache[norm_key] = pid
    return pid

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
    month_match = re.search(r'\b(\d{1,2})\s*(?:мая|РјР°СЏ)\b', line, flags=re.IGNORECASE)
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
            prefix = line[:position].rstrip()
            # Some titles contain capitalized names followed by parentheses.
            # A collapsed next entry begins after a finished preceding title.
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
    """Read program text from cached .html or .pdf, return normalized text with newlines.

    Tries `{conference}_{year}.html` first, then `{conference}_{year}.pdf` using pypdf.
    Returns None if neither cached file is present.
    """
    html_path = os.path.join(CACHE_DIR, f"{conference}_{year}.html")
    pdf_path = os.path.join(CACHE_DIR, f"{conference}_{year}.pdf")

    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
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
            # PDF text extraction may merge talk lines into multi-line paragraphs separated
            # by single newlines. Collapse intra-paragraph wraps so the line-based parser sees
            # one logical line per talk. Heuristic: a line ending in non-terminal punctuation
            # likely continues on the next line.
            pages_text.append(t)
        return "\n".join(pages_text)

    return None


def split_coauthor_names(speaker_block):
    """Split 'Ivanov A B, Petrov C D' into ['Ivanov A B', 'Petrov C D']."""
    parts = re.split(r'\s*,\s*(?=[А-ЯЁA-Z])', speaker_block)
    return [p.strip() for p in parts if p.strip()]

def populate_zograf_talks(conn):
    cursor = conn.cursor()
    
    # Retrieve all Zograf events we seeded from the MD
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
            # The 2014 source page appends an unrelated public lecture after
            # the Zograf programme itself; do not ingest it as a conference talk.
            if year == 2014 and "состоится доклад профессора Х. Линдтнера" in line:
                break
            # 1. Detect Day break in Zograf
            # Heuristics: date lines with month "мая"
            if "мая" in line and (str(year) in line or len(line) < 60) and not TALK_REGEX.match(preprocess_line(line)):
                # Skip conference-range headers like "26 — 29 мая 2026 г."
                if re.search(r'\d{1,2}\s*[—–-]\s*\d{1,2}\s*мая', line):
                    pass  # range header, not a per-day break
                else:
                    day_number += 1
                    current_day_id = f"D{year}_{day_number}"

                    current_edv_id = ensure_zograf_event_day_venue(
                        cursor, event_id, year, day_number, source_url, line, last_valid_edv_id
                    )
                    last_valid_edv_id = current_edv_id

                    current_session_id = None
            
            # 2. Detect Session/Time block
            time_match = re.search(r'(\d{2}[:\.]\d{2})\s*[-—–]\s*(\d{2}[:\.]\d{2})', line)
            if time_match and not TALK_REGEX.match(preprocess_line(line)):
                start_time, end_time = time_match.group(1), time_match.group(2)
                # Clean title of the session if any, e.g. "11:00 – 14:00 Открытие конференции"
                sess_title = line.replace(time_match.group(0), '').strip()
                if not sess_title:
                    sess_title = "Утреннее заседание" if int(start_time.replace('.', ':').split(':')[0]) < 14 else "Вечернее заседание"
                
                # Insert session
                if current_edv_id:
                    session_order += 1
                    current_session_id = stable_session_id(
                        "zograf", year, current_edv_id, sess_title, time_match.group(0), source_url, f"{session_order}|{line}"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, sess_title, "panel", start_time, end_time, time_match.group(0), None, source_url, line, None))
                    conn.commit()
            
            # 3. Detect presentation talk line — try richer patterns first
            cleaned_line = preprocess_line(line)

            speakers_with_affil = []  # list of (speaker_raw, affil_raw)
            title_raw = None

            candidate = parse_zograf_talk_line(line)
            if candidate:
                speakers_with_affil, title_raw = candidate

            if speakers_with_affil and title_raw:
                # Handle edge cases where speaker is listed but no session has been defined yet
                if not current_session_id:
                    if not current_edv_id:
                        # Ensure we have a day and venue
                        day_number = 1
                        current_day_id = f"D{year}_1"
                        current_edv_id = ensure_zograf_event_day_venue(
                            cursor, event_id, year, day_number, source_url, "Automatic default day", last_valid_edv_id
                        )
                        last_valid_edv_id = current_edv_id

                    # Create default session
                    session_order += 1
                    current_session_id = stable_session_id(
                        "zograf", year, current_edv_id, "Научное заседание", "11:00–18:00", source_url, f"{session_order}|Automatic default session"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, "Научное заседание", "panel", "11:00", "18:00", "11:00–18:00", None, source_url, "Automatic default session", None))
                    conn.commit()

                # Insert presentation (one row, multiple speakers)
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
    
    # 1. Parse Roerich Readings Events
    # In index, Roerich conference years are: 2007 through 2025.
    # Let's dynamically create the events for series_id=2 (Roerich Readings)
    ROERICH_YEARS = sorted(list(range(2007, 2026)))
    # We map Roman numerals to years
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
        
        # Parse event date and theme from headers
        # Default start/end dates
        start_date = f"{year}-12-09"
        end_date = f"{year}-12-11"
        theme = "Древняя и средневековая Индия и Центральная Азия. История. Филология. Культура"
        
        # Regex search in lines to correct dates dynamically if present
        for line in lines[:40]:
            date_match = re.search(r'(\d{1,2})[–-]\s*(\d{1,2})\s+декабря\s+(\d{4})', line)
            if date_match:
                start_date = f"{year}-12-{int(date_match.group(1)):02d}"
                end_date = f"{year}-12-{int(date_match.group(2)):02d}"
                break
                
        event_id = f"ER{year}"
        roman = ROMAN_MAP.get(year, "unspecified")
        
        # Insert Event
        cursor.execute("INSERT OR IGNORE INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (event_id, 2, year - 1960, roman, year, theme, None, start_date, end_date, "in_person", 0, None, None, f"https://ancient.ivran.ru/novosti?year={year}", extract_program_last_updated(year, "roerich"), None))
        
        day_number = 0
        current_day_id = None
        current_edv_id = None
        current_session_id = None
        session_order = 0
        
        for line in lines:
            # 1. Detect Day break in Roerich
            # e.g., "9.12.2024. Понедельник" or "9.12.2024"
            day_match = re.search(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b', line)
            if day_match:
                day_number += 1
                current_day_id = f"DR{year}_{day_number}"
                day_date = f"{day_match.group(3)}-{int(day_match.group(2)):02d}-{int(day_match.group(1)):02d}"
                
                # Insert EventDay
                cursor.execute("INSERT OR IGNORE INTO event_day VALUES (?,?,?,?,?,?,?)",
                               (current_day_id, event_id, day_number, day_date, line, f"https://ancient.ivran.ru/novosti?year={year}", None))
                               
                # EventDayVenue: Roerich is always at IV RAS Moscow (V100)
                current_edv_id = f"DVR{year}_{day_number}_1"
                cursor.execute("INSERT OR IGNORE INTO event_day_venue VALUES (?,?,?,?,?,?,?,?)",
                               (current_edv_id, current_day_id, "V100", 1, "222 ауд.", "11:00", f"https://ancient.ivran.ru/novosti?year={year}", "IV RAS"))
                
                current_session_id = None
                conn.commit()
                
            # 2. Detect Session
            # e.g. "Утреннее заседание: 11.00 – 13.30 (222 ауд.)"
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
            
            # Detect Moderator/Chair in Roerich
            # e.g. "Модератор: Н.В. Александрова. Технический секретарь: Т.В. Лучина"
            if "модератор" in line.lower() and current_session_id:
                cursor.execute("UPDATE session SET chair_text_raw = ? WHERE session_id = ?", (line, current_session_id))
                conn.commit()
                
            # 3. Detect Presentation
            candidate = parse_zograf_talk_line(line)
            if candidate:
                speakers_with_affil, title_raw = candidate
                if not title_raw:
                    continue
                
                # If we see a talk but no day was defined yet, let's create a default day 1
                if not current_day_id:
                    day_number = 1
                    current_day_id = f"DR{year}_1"
                    day_date = f"{year}-12-09"
                    cursor.execute("INSERT OR IGNORE INTO event_day VALUES (?,?,?,?,?,?,?)",
                                   (current_day_id, event_id, 1, day_date, "Понедельник", f"https://ancient.ivran.ru/novosti?year={year}", None))
                    current_edv_id = f"DVR{year}_1_1"
                    cursor.execute("INSERT OR IGNORE INTO event_day_venue VALUES (?,?,?,?,?,?,?,?)",
                                   (current_edv_id, current_day_id, "V100", 1, "222 ауд.", "11:00", f"https://ancient.ivran.ru/novosti?year={year}", "IV RAS"))
                
                # Default session if none exists
                if not current_session_id:
                    session_order += 1
                    current_session_id = stable_session_id(
                        "roerich", year, current_edv_id, "Научное заседание", "11:00–18:00", f"https://ancient.ivran.ru/novosti?year={year}", f"{session_order}|Default"
                    )
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, "Научное заседание", "panel", "11:00", "18:00", "11:00–18:00", None, f"https://ancient.ivran.ru/novosti?year={year}", "Default", None))
                
                # Insert presentation
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

def verify_db(conn):
    cursor = conn.cursor()
    print("\n--- DATABASE SUMMARY VERIFICATION ---")
    
    # Event Series
    cursor.execute("SELECT * FROM event_series")
    print(f"Event Series count: {len(cursor.fetchall())}")
    
    # Events
    cursor.execute("SELECT event_series_id, COUNT(*) FROM event GROUP BY event_series_id")
    print(f"Events per Series: {cursor.fetchall()}")
    
    # EventDays
    cursor.execute("SELECT COUNT(*) FROM event_day")
    print(f"Total Event Days: {cursor.fetchone()[0]}")
    
    # Persons
    cursor.execute("SELECT COUNT(*) FROM person")
    print(f"Total Unique Scholars/Persons: {cursor.fetchone()[0]}")
    
    # Presentations
    cursor.execute("SELECT COUNT(*) FROM presentation")
    print(f"Total Presentations parsed: {cursor.fetchone()[0]}")
    
    # Show top 5 speakers across both series
    cursor.execute("""
        SELECT p.display_name, COUNT(*) as cnt 
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        GROUP BY pp.person_id 
        ORDER BY cnt DESC LIMIT 10
    """)
    print("\nTop 10 Speakers (Combined Zograf and Roerich):")
    for row in cursor.fetchall():
        print(f" - {row[0]}: {row[1]} talks")
        
    # Check overlap of participants between Zograf (1) and Roerich (2)
    cursor.execute("""
        SELECT DISTINCT p.display_name 
        FROM presentation_person pp1
        JOIN presentation pr1 ON pr1.presentation_id = pp1.presentation_id
        JOIN session s1 ON s1.session_id = pr1.session_id
        JOIN event_day_venue edv1 ON edv1.event_day_venue_id = s1.event_day_venue_id
        JOIN event_day ed1 ON ed1.event_day_id = edv1.event_day_id
        JOIN event e1 ON e1.event_id = ed1.event_id
        JOIN person p ON p.person_id = pp1.person_id
        WHERE e1.event_series_id = 1
        INTERSECT
        SELECT DISTINCT p.display_name 
        FROM presentation_person pp2
        JOIN presentation pr2 ON pr2.presentation_id = pp2.presentation_id
        JOIN session s2 ON s2.session_id = pr2.session_id
        JOIN event_day_venue edv2 ON edv2.event_day_venue_id = s2.event_day_venue_id
        JOIN event_day ed2 ON ed2.event_day_id = edv2.event_day_id
        JOIN event e2 ON e2.event_id = ed2.event_id
        JOIN person p ON p.person_id = pp2.person_id
        WHERE e2.event_series_id = 2
    """)
    overlap = cursor.fetchall()
    print(f"\nTotal Overlapping Participants (attended BOTH Zograf and Roerich): {len(overlap)}")
    print("Sample overlap speakers:")
    for row in overlap[:10]:
        print(f" - {row[0]}")

def ingest_video_media(conn):
    """Read analytics_output/video_presentation_mapping.csv and insert
    YouTube videos as media rows attached to their matched presentations.

    The mapping is keyed by natural attributes (year + title_hint + speaker_hint),
    NOT by presentation_id (which is regenerated on each rebuild). For each
    auto/manual_confirmed row we re-fuzzy-match the hints against the current
    Zograf presentations of that year and attach the video to the best match.
    """
    import csv as _csv
    import difflib as _difflib
    import re as _re

    mapping_path = "analytics_output/video_presentation_mapping.csv"
    try:
        f = open(mapping_path, "r", encoding="utf-8")
    except FileNotFoundError:
        print(f"  (no {mapping_path} — skipping video ingestion)")
        return

    cursor = conn.cursor()

    def _norm(text):
        if not text:
            return ""
        t = text.lower().replace("ё", "е")
        t = _re.sub(r"[^\w\s\-]", " ", t)
        return _re.sub(r"\s+", " ", t).strip()

    # Cache presentations per year (year -> list of (pres_id, title, speakers))
    by_year_cache = {}

    def _get_candidates(year):
        if year not in by_year_cache:
            rows = cursor.execute("""
                SELECT pr.presentation_id, pr.title,
                       GROUP_CONCAT(pers.display_name, ' / ')
                FROM presentation pr
                JOIN session s ON s.session_id = pr.session_id
                JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
                JOIN event_day ed ON ed.event_day_id = edv.event_day_id
                JOIN event e ON e.event_id = ed.event_id
                JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
                JOIN person pers ON pers.person_id = pp.person_id
                WHERE e.event_series_id = 1 AND e.year = ?
                GROUP BY pr.presentation_id
            """, (year,)).fetchall()
            by_year_cache[year] = [(pid, t, sp) for pid, t, sp in rows]
        return by_year_cache[year]

    inserted = 0
    no_match = 0
    skipped = 0
    REINGEST_THRESHOLD = 0.55  # slightly looser than matcher's 0.65 because hints come from DB itself

    with f:
        for row in _csv.DictReader(f):
            status = (row.get("status") or "").strip()
            if status not in ("auto", "manual_confirmed"):
                skipped += 1
                continue
            year_str = (row.get("year") or "").strip()
            if not year_str.isdigit():
                skipped += 1
                continue
            year = int(year_str)
            video_url = (row.get("video_url") or "").strip()
            video_id = (row.get("video_id") or "").strip()
            video_title = (row.get("video_title") or "").strip()
            title_hint = (row.get("title_hint") or "").strip()
            speaker_hint = (row.get("speaker_hint") or "").strip()
            if not video_url or not title_hint:
                skipped += 1
                continue

            # Re-match hint against current presentations
            target = _norm(title_hint + " " + speaker_hint)
            best_pid = None
            best_ratio = 0.0
            for pid, title, speakers in _get_candidates(year):
                candidate_norm = _norm(title + " " + (speakers or ""))
                r = _difflib.SequenceMatcher(None, target, candidate_norm).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best_pid = pid
            if not best_pid or best_ratio < REINGEST_THRESHOLD:
                no_match += 1
                continue

            media_id = f"YT_{video_id}"
            cursor.execute("DELETE FROM media WHERE media_id = ?", (media_id,))
            cursor.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?)",
                (media_id, "presentation", best_pid, "video", video_url, video_title,
                 "video/youtube", video_url, f"hint-matched at build time (ratio={best_ratio:.2f}, status={status})")
            )
            inserted += 1
    conn.commit()
    print(f"  Video media: {inserted} inserted, {no_match} could not be matched against current DB, {skipped} skipped (status != auto/manual_confirmed)")


def main():
    print(f"Opening Database connection to {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    print("Initializing Database tables...")
    init_db(conn)

    print("Populating seeded database tables from zograf-roerich-db.md...")
    populate_seeded_data(conn)

    print("Populating parsed Zograf Reading talks (2004-2026)...")
    populate_zograf_talks(conn)

    print("Populating parsed Roerich Reading talks (2007-2025)...")
    populate_roerich_talks(conn)

    print("Ingesting YouTube video media from mapping CSV (if present)...")
    ingest_video_media(conn)

    print("Verifying database integrity and statistics...")
    verify_db(conn)

    conn.close()
    print("\nDatabase building and populating pipeline successfully completed!")

if __name__ == "__main__":
    main()
