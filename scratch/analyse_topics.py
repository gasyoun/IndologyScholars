import sqlite3
import re
import sys

# Reconfigure stdout to force UTF-8 printing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_analysis():
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    
    # Fetch all presentations with their titles, series_id, and year
    cursor.execute("""
        SELECT p.title, e.event_series_id, e.year, pe.display_name
        FROM presentation p
        JOIN session s ON p.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
        JOIN person pe ON pp.person_id = pe.person_id
    """)
    
    rows = cursor.fetchall()
    print(f"Loaded {len(rows)} presentations for analytical matching.")

    # 1. Classical Texts matching keys (Cyrillic lowercase substrings)
    TEXT_KEYWORDS = {
        "Ригведа": ["ригвед", "rgveda"],
        "Атхарваведа": ["атхарвавед", "atharvaveda"],
        "Махабхарата": ["махабхарат", "mahabharata"],
        "Рамаяна": ["рамаян", "ramayana"],
        "Упанишады": ["упанишад", "upanishad"],
        "Веды / Ведийский корпус": ["ведийс", "ведическ", "веды", "vedic"],
        "Панини / Аштадхьяи": ["панини", "аштадхья", "panini"],
        "Бхагавадгита": ["бхагавадгит", "bhagavad"],
        "Сутры": ["сутр", "sutra"],
        "Пураны": ["пуран", "purana"],
        "Дхаммапада": ["дхаммапад", "dhammapada"],
        "Ману (Манусмрити)": ["ману", "manu"],
        "Артхашастра": ["артхашастр", "arthashastra"],
        "Калидаса": ["калидас", "kalidasa"],
        "Натьяшастра": ["натьяшастр", "natyashastra"],
        "Бхартрихари": ["бхартрихар", "bhartrihari"]
    }

    # 2. Regional / Country matching keys (Cyrillic lowercase substrings)
    REGION_KEYWORDS = {
        "Индия (общие вопросы)": ["инди", "india"],
        "Тибет / Гималаи": ["тибет", "гимала", "tibet"],
        "Шри-Ланка / Цейлон": ["шри-ланк", "шри ланк", "цейлон", "сингаль", "sri lanka"],
        "Непал": ["непал", "nepal"],
        "Юго-Восточная Азия / Ява / Камбоджа / Бали": ["юго-вост", "юва", "ява", "камбодж", "бали", "java"],
        "Центральная Азия / Хотан / Дуньхуан": ["центральн", "хотан", "дуньхуан", "турфан", "куч", "central asia"],
        "Китай / Япония / Дальний Восток": ["китай", "япон", "дальн", "china"]
    }

    # Initialize statistics
    text_stats = {name: {"total": 0, "zograf": 0, "roerich": 0} for name in TEXT_KEYWORDS}
    region_stats = {name: {"total": 0, "zograf": 0, "roerich": 0} for name in REGION_KEYWORDS}
    
    text_years = {name: [] for name in TEXT_KEYWORDS}
    region_years = {name: [] for name in REGION_KEYWORDS}
    
    # Process
    for title, series_id, year, author in rows:
        title_lower = title.lower()
        
        # Text matching
        for text_name, substrings in TEXT_KEYWORDS.items():
            matched = False
            for s in substrings:
                if s in title_lower:
                    matched = True
                    break
            if matched:
                text_stats[text_name]["total"] += 1
                if series_id == 1:
                    text_stats[text_name]["zograf"] += 1
                else:
                    text_stats[text_name]["roerich"] += 1
                text_years[text_name].append(year)
        
        # Region matching
        for reg_name, substrings in REGION_KEYWORDS.items():
            matched = False
            for s in substrings:
                if s in title_lower:
                    matched = True
                    break
            if matched:
                region_stats[reg_name]["total"] += 1
                if series_id == 1:
                    region_stats[reg_name]["zograf"] += 1
                else:
                    region_stats[reg_name]["roerich"] += 1
                region_years[reg_name].append(year)

    print("\n=== TOP TEXT MENTIONS IN CONFERENCE TITLES ===")
    for text_name, stats in sorted(text_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        print(f"- {text_name}: Total: {stats['total']} | Zograf (SPb): {stats['zograf']} | Roerich (Msk): {stats['roerich']}")
        
    print("\n=== TOP REGIONAL FOCUS IN CONFERENCE TITLES ===")
    for reg_name, stats in sorted(region_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        print(f"- {reg_name}: Total: {stats['total']} | Zograf (SPb): {stats['zograf']} | Roerich (Msk): {stats['roerich']}")

    # Methodological focus (Linguistics vs Philosophy)
    lang_regexes = ["лингв", "язык", "граммат", "фонет", "лексик", "глагол", "падеж", "пракрит", "диалект", "санскрит"]
    phil_regexes = ["филос", "религ", "буддиз", "миф", "бог", "ритуал", "космо", "учени", "йог"]

    lang_count = {"total": 0, "zograf": 0, "roerich": 0}
    phil_count = {"total": 0, "zograf": 0, "roerich": 0}

    for title, series_id, year, author in rows:
        title_lower = title.lower()
        is_lang = any(s in title_lower for s in lang_regexes)
        is_phil = any(s in title_lower for s in phil_regexes)
        
        if is_lang:
            lang_count["total"] += 1
            if series_id == 1:
                lang_count["zograf"] += 1
            else:
                lang_count["roerich"] += 1
        if is_phil:
            phil_count["total"] += 1
            if series_id == 1:
                phil_count["zograf"] += 1
            else:
                phil_count["roerich"] += 1

    print("\n=== METHODOLOGICAL FOCUS (LINGUISTICS VS PHILOSOPHY/MYTH) ===")
    print(f"- Linguistics / Language: Total: {lang_count['total']} | Zograf (SPb): {lang_count['zograf']} | Roerich (Msk): {lang_count['roerich']}")
    print(f"- Philosophy / Religion / Myth: Total: {phil_count['total']} | Zograf (SPb): {phil_count['zograf']} | Roerich (Msk): {phil_count['roerich']}")

    conn.close()

if __name__ == "__main__":
    run_analysis()
