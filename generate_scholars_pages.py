import sqlite3
import os
import re

DB_PATH = "conferences.db"
OUTPUT_DIR = "scholars"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Helper functions identical to main site generator
def format_to_initials(name):
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[\.,;\s]+$', '', name)
    parts = name.split()
    if len(parts) == 3:
        patronymic_idx = -1
        for idx, p in enumerate(parts):
            if p.endswith(('вич', 'вна', 'чна', 'чич', 'вна.', 'вич.')):
                patronymic_idx = idx
                break
        if patronymic_idx == 2:
            return f"{parts[1][0]}. {parts[2][0]}. {parts[0]}"
        elif patronymic_idx == 1:
            return f"{parts[0][0]}. {parts[1][0]}. {parts[2]}"
    if len(parts) == 2:
        return f"{parts[0][0]}. {parts[1]}"
    return name

def clean_title(title):
    if not title:
        return ""
    cleaned = re.sub(r'\s*[\(\[][оО]н[-]?лайн[\)\]]\s*', ' ', title)
    cleaned = re.sub(r'\s*[\(\[][oO]nline[\)\]]\s*', ' ', cleaned)
    cleaned = re.sub(r'\s*[\(\[][zZ]oom[\)\]]\s*', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def classify_gender(full_name_ru, display_name):
    name_to_check = (full_name_ru or display_name or "").strip()
    parts = name_to_check.split()
    for p in parts:
        p_low = p.lower()
        if p_low.endswith(('вна', 'евна', 'овна', 'ична', 'инична')):
            return "F"
        if p_low.endswith(('вич', 'евич', 'ович', 'ич', 'чич')):
            return "M"
    female_first_names = ["маргарита", "наталия", "надежда", "елена", "ирина", "ольга", "татьяна", "анна", "мария", "софия", "евгения", "галина", "светлана", "людмила", "александра", "екатерина", "юлия", "любовь", "нина", "дарья", "лариса", "ксен", "ярослав", "вера", "тамара", "алена", "виктория", "марина", "жанна", "светлана", "надежда", "марианна"]
    for p in parts:
        if p.lower() in female_first_names:
            return "F"
    for p in parts:
        p_low = p.lower()
        if p_low.endswith(('ова', 'ева', 'ина', 'ая', 'ына')):
            return "F"
        if p_low.endswith(('ов', 'ев', 'ин', 'ий', 'ын')):
            return "M"
    if parts:
        last_letter = parts[0][-1].lower()
        if last_letter in ['а', 'я', 'и']:
            return "F"
    return "M"

def classify_theme(title):
    title_low = (title or "").lower()
    if any(term in title_low for term in ["рерих", "зограф", "конгресс", "биогр", "архив", "востоковед", "индолог", "экспедиц", "дневник", "переписк", "письм", "коллекц", "музей"]):
        return {
            "ru": "История науки и архивы",
            "en": "History of Scholarship",
            "code": "AcademicHistory"
        }
    if any(term in title_low for term in ["язык", "грамматик", "санскрит", "пали", "глагол", "фонет", "морфол", "лингв", "лексико", "диалект", "слово", "перевод", "синтакс", "словарь", "этимол", "текстолог"]):
        return {
            "ru": "Лингвистика и филология",
            "en": "Linguistics & Philology",
            "code": "Linguistics"
        }
    if any(term in title_low for term in ["философ", "религ", "будди", "будд", "шива", "текст", "упанишад", "учен", "йог", "индуиз", "ведичес", "кришн", "теософ", "миф", "ритуал", "божес", "космо", "сакрал"]):
        return {
            "ru": "Философия и религия",
            "en": "Philosophy & Religion",
            "code": "Philosophy"
        }
    if any(term in title_low for term in ["литератур", "поэз", "драм", "театр", "искусств", "архитект", "живоп", "поэт", "роман", "повес", "песн", "эпос", "фолькл", "сказ", "миниатюр", "изобраз"]):
        return {
            "ru": "Искусство и литература",
            "en": "Art & Literature",
            "code": "Art"
        }
    if any(term in title_low for term in ["этногр", "культур", "быт", "традиц", "обыча", "истори", "археол", "племен", "каст", "общес", "социал", "государс", "династ", "обряд", "одежд", "празд", "населен", "геогр"]):
        return {
            "ru": "История и этнография",
            "en": "History & Ethnography",
            "code": "History"
        }
    return {
        "ru": "История и этнография",
        "en": "History & Ethnography",
        "code": "History"
    }

def get_day_of_week(date_str):
    if not date_str:
        return {"ru": "Не указан", "en": "Not specified"}
    import datetime
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
        ("элиста", "Элиста", "Elista"),
        ("копенгаген", "Копенгаген", "Copenhagen"),
        ("тарту", "Тарту", "Tartu"),
        ("вильнюс", "Вильнюс", "Vilnius"),
        ("париж", "Париж", "Paris"),
        ("оксфорд", "Оксфорд", "Oxford"),
        ("дели", "Дели", "Delhi")
    ]
    for keyword, ru, en in cities:
        if keyword in aff_low:
            return {"ru": ru, "en": en}
    return {"ru": "Не указана", "en": "Not specified"}

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
        
    cursor.execute("SELECT person_id, display_name, birth_year, death_year, full_name_ru, full_name_en FROM person")
    persons = cursor.fetchall()
    
    for r_p in persons:
        pid, display_name, birth_year, death_year, full_name_ru, full_name_en = r_p
        
        # Build scholar names
        std_name = format_to_initials(display_name)
        full_name_ru_val = full_name_ru or std_name
        full_name_en_val = full_name_en or std_name
        
        # Gender
        gender = classify_gender(full_name_ru_val, display_name)
        gender_ru = "Мужчина" if gender == "M" else "Женщина"
        gender_en = "Male" if gender == "M" else "Female"
        
        # Calculate first and last Zograf/Roerich
        # Zograf (event_series_id = 1)
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
        z_first = z_res[0] if z_res and z_res[0] else None
        z_last = z_res[1] if z_res and z_res[1] else None
        
        # Roerich (event_series_id = 2)
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
        r_first = r_res[0] if r_res and r_res[0] else None
        r_last = r_res[1] if r_res and r_res[1] else None
        
        # Fetch all presentations with sessions and days
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
                v.display_name
            FROM presentation pr
            JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN venue v ON v.venue_id = edv.venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            JOIN event_series es ON es.event_series_id = e.event_series_id
            WHERE pp.person_id = ?
            ORDER BY e.year DESC, es.event_series_id ASC
        """, (pid,))
        talks_raw = cursor.fetchall()
        
        # Compile affiliations, cities, themes
        affiliations = set()
        cities = set()
        themes = set()
        talks = []
        theme_counts = {}
        
        is_student = False
        is_independent = False
        
        for t in talks_raw:
            pres_id, title, year, series, affiliation, is_online, calendar_date, session_title, time_text, sess_id, venue_display = t
            cleaned_title = clean_title(title)
            
            # Sub-category checks for roles
            if affiliation:
                aff_low = affiliation.lower()
                if any(term in aff_low for term in ["студент", "аспирант", "магистрант", "бакалавр", "student", "postgraduate", "phd"]):
                    is_student = True
                if any(term in aff_low for term in ["независимый", "ни ", " ни", "independent", "без аффилиации"]):
                    is_independent = True
                affiliations.add(affiliation)
                
                # Extract city
                geo = extract_geography(affiliation)
                if geo["ru"] != "Не указана":
                    cities.add(geo["ru"])
            
            # Theme classification
            theme = classify_theme(cleaned_title)
            t_code = theme["code"]
            theme_counts[t_code] = theme_counts.get(t_code, 0) + 1
            themes.add(theme["ru"])
            
            # Position order in session
            s_list = session_pres_map.get(sess_id, [pres_id])
            try:
                order_idx = s_list.index(pres_id)
            except ValueError:
                order_idx = 0
            
            is_first = (order_idx == 0)
            is_last = (order_idx == len(s_list) - 1)
            
            day_of_week = get_day_of_week(calendar_date)
            
            talks.append({
                "title": cleaned_title,
                "year": year,
                "series": "Зографские чтения" if "Zograf" in series else "Рериховские чтения",
                "series_en": "Zograf Readings" if "Zograf" in series else "Roerich Readings",
                "is_online": bool(is_online),
                "theme_ru": theme["ru"],
                "theme_en": theme["en"],
                "theme_code": theme["code"],
                "date": calendar_date or "Не указана",
                "day_ru": day_of_week["ru"],
                "day_en": day_of_week["en"],
                "time": time_text or "Не указано",
                "session_ru": session_title or "Секционный доклад",
                "venue": venue_display or "Научный центр",
                "is_first": is_first,
                "is_last": is_last,
                "order": order_idx + 1,
                "total": len(s_list)
            })
            
        # Dominant theme & breadth
        dom_theme_code = "History"
        dom_theme_ru = "История и этнография"
        dom_theme_en = "History & Ethnography"
        if theme_counts:
            sorted_t = sorted(theme_counts.items(), key=lambda x: (-x[1], x[0]))
            dom_theme_code = sorted_t[0][0]
            # Resolve dominant labels
            sample_themes = {
                "AcademicHistory": ("История науки и архивы", "History of Scholarship"),
                "Linguistics": ("Лингвистика и филология", "Linguistics & Philology"),
                "Philosophy": ("Философия и религия", "Philosophy & Religion"),
                "Art": ("Искусство и литература", "Art & Literature"),
                "History": ("История и этнография", "History & Ethnography")
            }
            dom_theme_ru, dom_theme_en = sample_themes.get(dom_theme_code, ("История и этнография", "History & Ethnography"))
            
        breadth_ru = "Междисциплинарный исследователь" if len(theme_counts) > 1 else "Узкий специалист"
        breadth_en = "Interdisciplinary Scholar" if len(theme_counts) > 1 else "Specialized Specialist"
        
        # Formulate HTML lifespan
        lifespan_ru = ""
        lifespan_en = ""
        if birth_year:
            if death_year:
                lifespan_ru = f" ({birth_year}–{death_year})"
                lifespan_en = f" ({birth_year}–{death_year})"
            else:
                lifespan_ru = f" (род. {birth_year})"
                lifespan_en = f" (b. {birth_year})"
                
        # Generate clean affiliations list html
        aff_tags_ru = ""
        aff_tags_en = ""
        for aff in sorted(affiliations):
            aff_tags_ru += f'<span class="aff-tag" onclick="filterByKeyword(\'{aff}\')">{aff}</span>'
            aff_tags_en += f'<span class="aff-tag" onclick="filterByKeyword(\'{aff}\')">{aff}</span>'
            
        city_lookup = {
            "Санкт-Петербург": "St. Petersburg",
            "Москва": "Moscow",
            "Краснодар": "Krasnodar",
            "Нижний Новгород": "Nizhny Novgorod",
            "Томск": "Tomsk",
            "Новосибирск": "Novosibirsk",
            "Владивосток": "Vladivostok",
            "Улан-Удэ": "Ulan-Ude",
            "Казань": "Kazan",
            "Пенза": "Penza",
            "Элиста": "Elista",
            "Копенгаген": "Copenhagen",
            "Тарту": "Tartu",
            "Вильнюс": "Vilnius",
            "Париж": "Paris",
            "Оксфорд": "Oxford",
            "Дели": "Delhi"
        }
        
        city_tags_ru = ""
        city_tags_en = ""
        for city in sorted(cities):
            city_tags_ru += f'<span class="city-tag" onclick="filterByKeyword(\'{city}\')">{city}</span>'
            c_en = city_lookup.get(city, city)
            city_tags_en += f'<span class="city-tag" onclick="filterByKeyword(\'{c_en}\')">{c_en}</span>'
            
        # Zograf / Roerich first/last text strings
        zograf_timeline_ru = f"Впервые: {z_first} г. | Последний раз: {z_last} г." if z_first else "Никогда не выступал"
        zograf_timeline_en = f"First: {z_first} | Last: {z_last}" if z_first else "Never presented"
        
        roerich_timeline_ru = f"Впервые: {r_first} г. | Последний раз: {r_last} г." if r_first else "Никогда не выступал"
        roerich_timeline_en = f"First: {r_first} | Last: {r_last}" if r_first else "Never presented"
        
        # Build talk rows HTML
        talk_rows_html_ru = ""
        talk_rows_html_en = ""
        for tk in talks:
            online_badge_ru = '<span class="badge badge-online">Zoom / Онлайн</span>' if tk["is_online"] else ""
            online_badge_en = '<span class="badge badge-online">Zoom / Online</span>' if tk["is_online"] else ""
            
            first_badge_ru = '<span class="badge badge-first">Открывающий доклад</span>' if tk["is_first"] else ""
            first_badge_en = '<span class="badge badge-first">Opening Talk</span>' if tk["is_first"] else ""
            
            last_badge_ru = '<span class="badge badge-last">Закрывающий доклад</span>' if tk["is_last"] else ""
            last_badge_en = '<span class="badge badge-last">Closing Talk</span>' if tk["is_last"] else ""
            
            seq_badge_ru = f'<span class="badge badge-order">{tk["order"]}-й доклад из {tk["total"]}</span>'
            seq_badge_en = f'<span class="badge badge-order">Talk {tk["order"]} of {tk["total"]}</span>'
            
            talk_rows_html_ru += f"""
            <div class="talk-card">
                <div class="talk-header">
                    <span class="talk-year">{tk["year"]} ({tk["series"]})</span>
                    <span class="badge badge-theme theme-{tk["theme_code"]}">{tk["theme_ru"]}</span>
                </div>
                <h4 class="talk-title">{tk["title"]}</h4>
                <div class="talk-details">
                    <div><strong>Секция:</strong> {tk["session_ru"]}</div>
                    <div><strong>Время:</strong> {tk["date"]} ({tk["day_ru"]}), {tk["time"]}</div>
                    <div><strong>Место проведения:</strong> {tk["venue"]}</div>
                </div>
                <div style="margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    {online_badge_ru} {first_badge_ru} {last_badge_ru} {seq_badge_ru}
                </div>
            </div>
            """
            
            talk_rows_html_en += f"""
            <div class="talk-card">
                <div class="talk-header">
                    <span class="talk-year">{tk["year"]} ({tk["series_en"]})</span>
                    <span class="badge badge-theme theme-{tk["theme_code"]}">{tk["theme_en"]}</span>
                </div>
                <h4 class="talk-title">{tk["title"]}</h4>
                <div class="talk-details">
                    <div><strong>Session:</strong> {tk["session_ru"]}</div>
                    <div><strong>Time:</strong> {tk["date"]} ({tk["day_en"]}), {tk["time"]}</div>
                    <div><strong>Venue:</strong> {tk["venue"]}</div>
                </div>
                <div style="margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    {online_badge_en} {first_badge_en} {last_badge_en} {seq_badge_en}
                </div>
            </div>
            """
            
        # Academic status tags
        status_badges_ru = ""
        status_badges_en = ""
        if is_student:
            status_badges_ru += '<span class="status-badge student-badge">Студент / Аспирант</span>'
            status_badges_en += '<span class="status-badge student-badge">Student / PG</span>'
        if is_independent:
            status_badges_ru += '<span class="status-badge independent-badge">Независимый исследователь (НИ)</span>'
            status_badges_en += '<span class="status-badge independent-badge">Independent Researcher (IR)</span>'
            
        html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{full_name_ru_val} | Российский индологический архив</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --card-bg: rgba(31, 41, 55, 0.45);
            --card-border: rgba(255, 255, 255, 0.07);
            --text-primary: #ffffff;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-primary: #8b5cf6;
            --accent-secondary: #3b82f6;
            --accent-glow: rgba(139, 92, 246, 0.15);
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            --font-display: 'Outfit', sans-serif;
            --font-body: 'Inter', sans-serif;
            --font-mono: 'Fira Code', monospace;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-primary);
            color: var(--text-primary);
            font-family: var(--font-body);
            line-height: 1.6;
            padding: 2rem 1rem;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(59, 130, 246, 0.08) 0%, transparent 40%);
            background-attachment: fixed;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}

        /* Header Navigation */
        .back-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-secondary);
            text-decoration: none;
            font-family: var(--font-display);
            font-weight: 500;
            font-size: 0.95rem;
            padding: 0.6rem 1.2rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--card-border);
            border-radius: 9999px;
            cursor: pointer;
            transition: var(--transition);
            margin-bottom: 2rem;
        }}

        .back-btn:hover {{
            color: #ffffff;
            background: var(--accent-glow);
            border-color: var(--accent-primary);
            box-shadow: 0 0 15px rgba(139, 92, 246, 0.2);
            transform: translateX(-4px);
        }}

        /* Profile Header */
        .profile-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 2.5rem;
            backdrop-filter: blur(12px);
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }}

        .profile-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 1.5rem;
            margin-bottom: 1.5rem;
        }}

        .profile-title h1 {{
            font-family: var(--font-display);
            font-weight: 700;
            font-size: 2.2rem;
            line-height: 1.2;
            color: #ffffff;
            margin-bottom: 0.5rem;
        }}

        .profile-title .lifespan {{
            color: var(--text-secondary);
            font-weight: 400;
            font-size: 1.4rem;
            margin-left: 0.5rem;
        }}

        .status-badges {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }}

        .status-badge {{
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .student-badge {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}

        .independent-badge {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        /* Profile Details Grid */
        .details-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }}

        .detail-item {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 8px;
            padding: 1rem;
        }}

        .detail-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}

        .detail-value {{
            font-family: var(--font-display);
            font-weight: 600;
            font-size: 1.05rem;
            color: #ffffff;
        }}

        .theme-badge {{
            display: inline-block;
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            margin-top: 0.25rem;
        }}

        /* Tags lists */
        .tags-section {{
            margin-bottom: 1.5rem;
        }}

        .tags-title {{
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .tags-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .aff-tag, .city-tag {{
            font-size: 0.85rem;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            padding: 0.3rem 0.8rem;
            color: var(--text-secondary);
            cursor: pointer;
            transition: var(--transition);
        }}

        .aff-tag:hover {{
            background: rgba(139, 92, 246, 0.08);
            border-color: var(--accent-primary);
            color: #ffffff;
        }}

        .city-tag:hover {{
            background: rgba(59, 130, 246, 0.08);
            border-color: var(--accent-secondary);
            color: #ffffff;
        }}

        /* Timeline / Talks section */
        .section-title {{
            font-family: var(--font-display);
            font-weight: 700;
            font-size: 1.6rem;
            color: #ffffff;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .talks-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .talk-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 1.5rem;
            transition: var(--transition);
        }}

        .talk-card:hover {{
            border-color: rgba(139, 92, 246, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }}

        .talk-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .talk-year {{
            font-family: var(--font-mono);
            font-weight: 600;
            font-size: 0.9rem;
            color: var(--accent-secondary);
        }}

        .talk-title {{
            font-family: var(--font-display);
            font-size: 1.2rem;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 0.75rem;
        }}

        .talk-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.5rem 1.5rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 0.75rem;
        }}

        .talk-details strong {{
            color: var(--text-primary);
        }}

        /* Theme color badging */
        .badge-theme {{
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            text-transform: uppercase;
        }}

        .theme-Philosophy {{ background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }}
        .theme-Linguistics {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .theme-History {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .theme-Art {{ background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }}
        .theme-AcademicHistory {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}

        .badge {{
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            display: inline-block;
        }}

        .badge-online {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-first {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-last {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-order {{ background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); border: 1px solid rgba(255, 255, 255, 0.1); }}

        /* Footer Copyright */
        footer {{
            margin-top: 4rem;
            border-top: 1px solid var(--card-border);
            padding-top: 1.5rem;
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-muted);
            font-family: var(--font-display);
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Back Button -->
        <a href="../index.html" class="back-btn">
            <span>←</span>
            <span class="lang-ru-inline">Назад на главную</span>
            <span class="lang-en-inline">Back to Dashboard</span>
        </a>

        <!-- Profile Card -->
        <div class="profile-card">
            <div class="profile-header">
                <div class="profile-title">
                    <h1 class="lang-ru">{full_name_ru_val}<span class="lifespan">{lifespan_ru}</span></h1>
                    <h1 class="lang-en">{full_name_en_val}<span class="lifespan">{lifespan_en}</span></h1>
                    
                    <div class="status-badges">
                        {status_badges_ru}
                    </div>
                </div>
            </div>

            <!-- Scholar Meta Fields -->
            <div class="details-grid">
                <div class="detail-item">
                    <div class="detail-label">
                        <span class="lang-ru">Пол</span>
                        <span class="lang-en">Gender</span>
                    </div>
                    <div class="detail-value">
                        <span class="lang-ru">{gender_ru}</span>
                        <span class="lang-en">{gender_en}</span>
                    </div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">
                        <span class="lang-ru">Научный профиль</span>
                        <span class="lang-en">Research Profile</span>
                    </div>
                    <div class="detail-value">
                        <span class="lang-ru">{breadth_ru}</span>
                        <span class="lang-en">{breadth_en}</span>
                        <br>
                        <span class="badge-theme theme-{dom_theme_code}" style="margin-top: 0.4rem;">
                            <span class="lang-ru">{dom_theme_ru}</span>
                            <span class="lang-en">{dom_theme_en}</span>
                        </span>
                    </div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">
                        <span class="lang-ru">Зографские чтения</span>
                        <span class="lang-en">Zograf Readings</span>
                    </div>
                    <div class="detail-value" style="font-size: 0.9rem;">
                        <span class="lang-ru">{zograf_timeline_ru}</span>
                        <span class="lang-en">{zograf_timeline_en}</span>
                    </div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">
                        <span class="lang-ru">Рериховские чтения</span>
                        <span class="lang-en">Roerich Readings</span>
                    </div>
                    <div class="detail-value" style="font-size: 0.9rem;">
                        <span class="lang-ru">{roerich_timeline_ru}</span>
                        <span class="lang-en">{roerich_timeline_en}</span>
                    </div>
                </div>
            </div>

            <!-- Affiliations -->
            <div class="tags-section" style="display: { 'block' if affiliations else 'none' };">
                <div class="tags-title">
                    <span class="lang-ru">Аффилиации за все годы</span>
                    <span class="lang-en">Affiliation History</span>
                </div>
                <div class="tags-list">
                    {aff_tags_ru}
                </div>
            </div>

            <!-- Cities -->
            <div class="tags-section" style="display: { 'block' if cities else 'none' };">
                <div class="tags-title">
                    <span class="lang-ru">Географические центры</span>
                    <span class="lang-en">Geographical Centers</span>
                </div>
                <div class="tags-list">
                    {city_tags_ru}
                </div>
            </div>
        </div>

        <!-- Presentations list -->
        <div>
            <h3 class="section-title">
                <span>📚</span>
                <span class="lang-ru">Научные доклады ({len(talks)})</span>
                <span class="lang-en">Presented Papers ({len(talks)})</span>
            </h3>

            <div class="talks-list lang-ru">
                {talk_rows_html_ru}
            </div>
            
            <div class="talks-list lang-en">
                {talk_rows_html_en}
            </div>
        </div>

        <!-- Footer -->
        <footer>
            <div class="lang-ru">© 2026 Российский индологический научный архив, д-р Марцис Гасунс. Все права защищены.</div>
            <div class="lang-en">© 2026 Russian Indological Research Archive, Dr. Mārcis Gasūns. All rights reserved.</div>
        </footer>
    </div>

    <script>
        // Set language display based on dashboard preferences
        function applyLanguage() {{
            const lang = localStorage.getItem('indology_lang') || 'ru';
            
            document.querySelectorAll('.lang-ru').forEach(el => el.style.display = lang === 'ru' ? 'block' : 'none');
            document.querySelectorAll('.lang-en').forEach(el => el.style.display = lang === 'en' ? 'block' : 'none');
            
            document.querySelectorAll('.lang-ru-inline').forEach(el => el.style.display = lang === 'ru' ? 'inline' : 'none');
            document.querySelectorAll('.lang-en-inline').forEach(el => el.style.display = lang === 'en' ? 'inline' : 'none');
        }}

        // Helper function to link back to dashboard with search keyword
        function filterByKeyword(keyword) {{
            window.location.href = '../index.html?search=' + encodeURIComponent(keyword);
        }}

        applyLanguage();
    </script>
</body>
</html>"""
        
        # Write individual file
        with open(os.path.join(OUTPUT_DIR, f"{pid}.html"), "w", encoding="utf-8") as f_out:
            f_out.write(html_content)
            
    conn.close()
    print(f"Successfully generated {len(persons)} premium static scholar profile pages in '{OUTPUT_DIR}/'!")

if __name__ == "__main__":
    main()
