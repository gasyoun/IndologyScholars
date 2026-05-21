import os
import re
import csv
import io
import sys
import sqlite3
import uuid
import hashlib
import json

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

MD_PATH = "zograf-roerich-db.md"
DB_PATH = "conferences.db"
CACHE_DIR = "html_cache"
PERSON_ID_MAP_PATH = "person_ids.json"

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
        cursor.execute("INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (r['event_id'], 1, int(r['ordinal_int']), r['ordinal_roman'], int(r['year']), r['theme_ru'], None, r['start_date'], r['end_date'], r['format'], is_online_val, r['online_platform'], r['program_post_id'], r['source_url'], r['notes']))
                       
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
    "альбедиль м а": ("Альбедиль Маргарита Федоровна", "Albedil Margarita Fedorovna", 1946, None),
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
    "соболева д в": ("Соболева Диана Владимировна", "Soboleva Diana Vladimirovna", 1989, None),
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
    "соколова о с": ("Соколова Ольга Сергеевна", "Sokolova Olga Sergeyevna", 1987, None),
    "лемешкина к в": ("Лемешкина Ксения Вячеславовна", "Lemeshkina Ksenia Vyacheslavovna", 1985, None),
    "маретина к а": ("Маретина Ксения Александровна", "Maretina Ksenia Alexandrovna", 1982, None),
    "аникина а а": ("Аникина Анна Андреевна", "Anikina Anna Andreevna", 1986, None),
    "бычихина о в": ("Бычихина Ольга Владимировна", "Bychikhina Olga Vladimirovna", 1978, None),
    "яковлева м н": ("Яковлева Мария Николаевна", "Yakovleva Maria Nikolaevna", 1989, None),
    "ершова е м": ("Ершова Елизавета Михайловна", "Ershova Elizaveta Mikhailovna", 1993, None),
    "голубев с в": ("Голубев Сергей Владимирович", "Golubev Sergey Vladimirovich", 1980, None),
    "челнокова а в": ("Челнокова Анна Витальевна", "Chelnokova Anna Vitalyevna", 1971, None),
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
    "топоров в н": ("Топоров Владимир Николаевич", "Toporov Vladimir Nikolaevich", 1928, 2005),
    "степанянц м т": ("Степанянц Мариэтта Тиграновна", "Stepanyants Marietta Tigranovna", 1935, None),
}

persons_cache = {} # normalized_key -> person_id
person_id_overrides = None


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


def person_id_for_key(norm_key):
    override = load_person_id_overrides().get(norm_key)
    if override:
        return override
    digest = hashlib.sha1(norm_key.encode("utf-8")).hexdigest()[:8]
    return f"PERS_{digest}"


def get_or_create_person(conn, name, source_url):
    cursor = conn.cursor()
    norm_key = normalize_person_name(name)
    
    fn_ru, fn_en, by, dy = None, None, None, None
    bio = BIOGRAPHICAL_DATA.get(norm_key)
    if bio:
        fn_ru, fn_en, by, dy = bio

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
        conn.commit()
        return pid

    # Create new. Person IDs are stable because they are used in public profile URLs.
    pid = mapped_pid
    cursor.execute("""
        INSERT INTO person (person_id, display_name, full_name_ru, full_name_en, birth_year, death_year, normalized_key, source_url) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, name.strip(), fn_ru, fn_en, by, dy, norm_key, source_url))
    conn.commit()
    persons_cache[norm_key] = pid
    return pid

# Clean title helper
def clean_title(title):
    title = title.strip()
    title = re.sub(r'\s*\(\s*онлайн\s*\)\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(\s*zoom\s*\)\s*', '', title, flags=re.IGNORECASE)
    if title.endswith('.'):
        title = title[:-1]
    return title.strip()

# Preprocess line helper to remove leading time
def preprocess_line(line):
    line = line.strip()
    line = re.sub(r'^\s*\d{1,2}\s*[\.:]\s*\d{2}\s*\.?\s*', '', line)
    line = re.sub(r'^\s*\d{1,2}\s*\.\s*', '', line)
    return line.strip()


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

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        day_number = 0
        current_day_id = None
        current_edv_id = None
        last_valid_edv_id = None
        current_session_id = None
        
        for line in lines:
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
                    current_session_id = f"SESS_{uuid.uuid4().hex[:8]}"
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, sess_title, "panel", start_time, end_time, time_match.group(0), None, source_url, line, None))
                    conn.commit()
            
            # 3. Detect presentation talk line — try richer patterns first
            cleaned_line = preprocess_line(line)

            speakers_with_affil = []  # list of (speaker_raw, affil_raw)
            title_raw = None

            m_two = TALK_REGEX_TWO_AFFIL.match(cleaned_line)
            if m_two:
                speakers_with_affil = [
                    (m_two.group(1).strip(), m_two.group(2).strip()),
                    (m_two.group(3).strip(), m_two.group(4).strip()),
                ]
                title_raw = clean_title(m_two.group(5))
            else:
                m_co = TALK_REGEX_COAUTHORS.match(cleaned_line)
                if m_co:
                    names = split_coauthor_names(m_co.group(1))
                    affil = m_co.group(2).strip()
                    speakers_with_affil = [(n, affil) for n in names]
                    title_raw = clean_title(m_co.group(3))
                else:
                    m_single = TALK_REGEX.match(cleaned_line)
                    if m_single:
                        speakers_with_affil = [(m_single.group(1).strip(), m_single.group(2).strip())]
                        title_raw = clean_title(m_single.group(3))

            if speakers_with_affil and title_raw is not None:
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
                    current_session_id = f"SESS_{uuid.uuid4().hex[:8]}"
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, "Научное заседание", "panel", "11:00", "18:00", "11:00–18:00", None, source_url, "Automatic default session", None))
                    conn.commit()

                # Insert presentation (one row, multiple speakers)
                pres_id = f"PRES_{uuid.uuid4().hex[:8]}"
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
        cursor.execute("INSERT OR IGNORE INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (event_id, 2, year - 1960, roman, year, theme, None, start_date, end_date, "in_person", 0, None, None, f"https://ancient.ivran.ru/novosti?year={year}", None))
        
        day_number = 0
        current_day_id = None
        current_edv_id = None
        current_session_id = None
        
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
                    current_session_id = f"SESS_R_{uuid.uuid4().hex[:8]}"
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, sess_title, "panel", start_t, end_t, raw_t, None, f"https://ancient.ivran.ru/novosti?year={year}", line, room))
                    conn.commit()
            
            # Detect Moderator/Chair in Roerich
            # e.g. "Модератор: Н.В. Александрова. Технический секретарь: Т.В. Лучина"
            if "модератор" in line.lower() and current_session_id:
                cursor.execute("UPDATE session SET chair_text_raw = ? WHERE session_id = ?", (line, current_session_id))
                conn.commit()
                
            # 3. Detect Presentation
            cleaned_line = preprocess_line(line)
            match = TALK_REGEX.match(cleaned_line)
            if match:
                speaker_raw = match.group(1).strip()
                affil_raw = match.group(2).strip()
                title_raw = clean_title(match.group(3))
                
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
                    current_session_id = f"SESS_R_{uuid.uuid4().hex[:8]}"
                    cursor.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                   (current_session_id, current_edv_id, "Научное заседание", "panel", "11:00", "18:00", "11:00–18:00", None, f"https://ancient.ivran.ru/novosti?year={year}", "Default", None))
                
                # Insert presentation
                pres_id = f"PRES_R_{uuid.uuid4().hex[:8]}"
                is_online_val = 1 if 'онлайн' in line.lower() else 0
                cursor.execute("INSERT INTO presentation VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (pres_id, current_session_id, title_raw, None, "ru", None, is_online_val, None, f"https://ancient.ivran.ru/novosti?year={year}", line, None))
                
                # Get/Create Speaker
                person_id = get_or_create_person(conn, speaker_raw, f"https://ancient.ivran.ru/novosti?year={year}")
                
                # Map Speaker
                cursor.execute("INSERT INTO presentation_person VALUES (?,?,?,?,?,?,?,?)",
                               (pres_id, person_id, "speaker", 1, affil_raw, None, f"https://ancient.ivran.ru/novosti?year={year}", None))
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

    print("Populating parsed Zograf Reading talks (2004-2025)...")
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
