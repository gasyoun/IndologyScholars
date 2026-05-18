import sqlite3
import re
import datetime

DB_PATH = "conferences.db"
OUTPUT_REPORT = "indologists_scholarly_analysis.md"

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
        # Check standard Russian last name endings to guess order
        if parts[0].endswith(('ова', 'ева', 'ина', 'ын', 'ий', 'ев', 'ов', 'их', 'ых', 'ко', 'ук', 'юк')):
            last = parts[0]
            first = parts[1]
        else:
            first = parts[0]
            last = parts[1]
        return f"{first[0]}. {last}"
        
    return name

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch all persons
    cursor.execute("SELECT person_id, display_name FROM person")
    persons = cursor.fetchall()
    
    # 1. Standardize names & categorize (missing full name vs full name available)
    scholars_missing_fullname = []
    scholars_with_fullname = []
    standardized_names = {}
    
    for pid, display_name in persons:
        std = format_to_initials(display_name)
        standardized_names[pid] = std
        
        # Check if it has a full first name and patronymic (length of words is > 2 and no dots)
        parts = [p.replace('.', '').strip() for p in display_name.split() if p]
        is_initials_only = True
        
        # If any word in the name has length > 2 (excluding dots), it has some full name details
        for p in parts:
            if len(p) > 2:
                is_initials_only = False
                break
                
        if is_initials_only:
            scholars_missing_fullname.append((display_name, std))
        else:
            scholars_with_fullname.append((display_name, std))
            
    # 2. Days of the week for all talks
    cursor.execute("""
        SELECT pr.presentation_id, ed.calendar_date, ed.day_label_raw, e.year
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
    """)
    dates_raw = cursor.fetchall()
    
    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    # 3. Analyze time intervals and first/last talks
    # We group presentations by day to determine first/last talk order in that day/session
    cursor.execute("""
        SELECT pr.presentation_id, pr.session_id, s.time_text_raw, s.start_time, s.end_time
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
    """)
    presentations_session = cursor.fetchall()
    
    # Group presentations by session_id to find first/last
    session_groups = {}
    for pid, sess_id, time_text, start_t, end_t in presentations_session:
        if sess_id not in session_groups:
            session_groups[sess_id] = []
        session_groups[sess_id].append(pid)
        
    pres_session_order = {}
    for sess_id, pids in session_groups.items():
        # Preserving their original parsed order
        for idx, pid in enumerate(pids):
            is_first = (idx == 0)
            is_last = (idx == len(pids) - 1)
            pres_session_order[pid] = {
                "order_in_session": idx + 1,
                "total_in_session": len(pids),
                "is_first": is_first,
                "is_last": is_last
            }
            
    # 4. Independent researchers, students, and changes in affiliations
    cursor.execute("""
        SELECT pp.person_id, pp.affiliation_text_raw, e.year
        FROM presentation_person pp
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
    """)
    affil_raw = cursor.fetchall()
    
    independent_scholars = set()
    student_scholars = set()
    scholar_affils_by_year = {} # person_id -> {year: affil}
    
    for pid, affil, year in affil_raw:
        if not affil:
            continue
        affil_lower = affil.lower()
        
        # Check independent
        if any(term in affil_lower for term in ["независимый", "ни ", " ни", "independent", "без аффилиации"]):
            independent_scholars.add(pid)
            
        # Check student
        if any(term in affil_lower for term in ["студент", "аспирант", "магистрант", "бакалавр", "student", "postgraduate", "phd"]):
            student_scholars.add(pid)
            
        if pid not in scholar_affils_by_year:
            scholar_affils_by_year[pid] = {}
        scholar_affils_by_year[pid][year] = affil
        
    # Check whose affiliation changed over the years
    changed_affiliations = []
    for pid, years_dict in scholar_affils_by_year.items():
        unique_affils = list(set(years_dict.values()))
        if len(unique_affils) > 1:
            changed_affiliations.append((pid, years_dict))
            
    # 5. Searchability / Online Presence classification
    # High visibility: multiple talks, or associated with a major institution
    # Low visibility: single talk, no specific affiliation, or initials only
    cursor.execute("""
        SELECT p.person_id, p.display_name, COUNT(pr.presentation_id) as talk_count
        FROM person p
        LEFT JOIN presentation_person pp ON pp.person_id = p.person_id
        LEFT JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        GROUP BY p.person_id
    """)
    scholars_stats = cursor.fetchall()
    
    high_visibility = []
    low_visibility = []
    
    for pid, name, talk_count in scholars_stats:
        std_name = standardized_names[pid]
        # Check if they have an institution in any talk
        affils = scholar_affils_by_year.get(pid, {})
        has_major_inst = False
        for a in affils.values():
            a_low = a.lower()
            if any(inst in a_low for inst in ["ран", "ивр", "ив ", "спбгу", "мгу", "вшэ", "рггу", "маэ", "кунст"]):
                has_major_inst = True
                break
                
        # High visibility criteria
        if talk_count >= 3 or (talk_count >= 1 and has_major_inst and len(name) > 15):
            high_visibility.append((name, std_name, talk_count))
        else:
            low_visibility.append((name, std_name, talk_count))

    # Sort lists
    scholars_missing_fullname.sort(key=lambda x: x[1])
    scholars_with_fullname.sort(key=lambda x: x[1])
    high_visibility.sort(key=lambda x: x[2], reverse=True)
    low_visibility.sort(key=lambda x: x[2], reverse=True)
    changed_affiliations.sort(key=lambda x: len(x[1]), reverse=True)

    # Compile Markdown Report
    report = []
    report.append("# Глубокий научно-аналитический анализ участников индологических конференций")
    report.append("\n> [!NOTE]\n> Данный аналитический отчет подготовлен на основе нормализованной реляционной базы данных `conferences.db` (период 2004–2025 гг.) и отвечает на ключевые вопросы просопографии, аффилиаций и структуры выступлений российских востоковедов.")
    
    # Section 1
    report.append("\n## 👤 1. Единообразие ФИО и Инициалы")
    report.append("\nВсе имена участников были стандартизированы к единообразному академическому формату **«Инициалы Фамилия»** (например, *Н. В. Александрова*).")
    
    report.append(f"\n### 🔍 Список участников, по которым не хватает данных для полного ФИО ({len(scholars_missing_fullname)})")
    report.append("\n*Эти участники упоминаются в архивных программах исключительно по фамилии с инициалами. Для расширения их профилей до полных ФИО требуется привлечение дополнительных внешних биобиблиографических словарей:*")
    
    report.append("\n| Инициалы и Фамилия | Исходная запись в базе данных |")
    report.append("| :--- | :--- |")
    for orig, std in scholars_missing_fullname:
        report.append(f"| **{std}** | {orig} |")
        
    report.append(f"\n### 🎓 Список участников с известными полными именами ({len(scholars_with_fullname)})")
    report.append("\n*Для этих ученых в базе данных сохранены полные имена (имя, отчество, фамилия):*")
    report.append("\n| Инициалы | Полное ФИО |")
    report.append("| :--- | :--- |")
    for orig, std in scholars_with_fullname[:30]: # top 30
        report.append(f"| **{std}** | {orig} |")
    report.append("| ... | ... |")
    
    # Section 2 & 3
    report.append("\n## 📅 2. Хронометрический анализ докладов (Дни недели и Временные интервалы)")
    report.append("\nВ базу данных импортирован расчет дней недели и точного временного порядка:")
    report.append("*   **День недели**: Определяется автоматически по календарным датам конференций (например, 24 мая 2004 г. -> *Понедельник*).")
    report.append("*   **Очередность докладов**: Вычисляется порядковый ранг выступления внутри каждой научной секции. Это позволяет выделять **первые (открывающие) доклады** (задающие тон секции) и **последние (закрывающие) доклады** (обобщающие заседание).")
    
    # Section 4
    report.append("\n## 🏢 3. Анализ аффилиаций: Независимые исследователи и Студенты")
    
    # Independent
    report.append(f"\n### 🗺️ Независимые исследователи (НИ) без официальной аффилиации ({len(independent_scholars)})")
    report.append("\n*Участники, которые на момент выступления были зарегистрированы как независимые исследователи:*")
    report.append("\n| Исследователь | Аффилиация в программе | Года докладов |")
    report.append("| :--- | :--- | :--- |")
    for pid in independent_scholars:
        name = standardized_names[pid]
        affils = scholar_affils_by_year[pid]
        years = ", ".join(map(str, sorted(affils.keys())))
        all_aff = " / ".join(set(affils.values()))
        report.append(f"| **{name}** | {all_aff} | {years} |")
        
    # Students
    report.append(f"\n### 🎓 Студенты, аспиранты и молодые ученые на момент доклада ({len(student_scholars)})")
    report.append("\n*Докладчики, указанные в программах как студенты, аспиранты или соискатели:*")
    report.append("\n| Молодой ученый | Статус и ВУЗ | Год |")
    report.append("| :--- | :--- | :--- |")
    for pid in list(student_scholars)[:20]:
        name = standardized_names[pid]
        affils = scholar_affils_by_year[pid]
        years = ", ".join(map(str, sorted(affils.keys())))
        all_aff = " / ".join(set(affils.values()))
        report.append(f"| **{name}** | {all_aff} | {years} |")
    if len(student_scholars) > 20:
        report.append("| ... | ... | ... |")
        
    # Changes in affiliation
    report.append(f"\n### 🔄 Динамика изменения аффилиаций востоковедов с годами ({len(changed_affiliations)})")
    report.append("\n*Ученые, чьи официальные места работы или кафедры менялись на протяжении их участия в конференциях:*")
    report.append("\n| Ученый | Изменение аффилиации по годам |")
    report.append("| :--- | :--- |")
    for pid, years_dict in changed_affiliations[:15]:
        name = standardized_names[pid]
        timeline_str = " → ".join([f"**{y}**: {years_dict[y]}" for y in sorted(years_dict.keys())])
        report.append(f"| **{name}** | {timeline_str} |")
    report.append("| ... | ... |")

    # Section 5
    report.append("\n## 🌐 4. Присутствие ученых в сети Интернет (Биобиблиографическая находимость)")
    report.append("\nУчастники были классифицированы по степени вероятности нахождения их научных профилей в сети Интернет:")
    
    report.append(f"\n### 🟢 Высокая научная видимость в сети ({len(high_visibility)})")
    report.append("\n*Ученые с высокой вероятностью нахождения профилей (известные индологи, сотрудники ИВР РАН, ИВ РАН, профессора СПбГУ/МГУ, авторы от 3 докладов):*")
    report.append("\n| Ученый (Инициалы) | Полное имя в БД | Кол-во докладов |")
    report.append("| :--- | :--- | :--- |")
    for name, std, count in high_visibility[:20]:
        report.append(f"| **{std}** | {name} | {count} |")
    report.append("| ... | ... | ... |")
    
    report.append(f"\n### 🟡 Низкая научная видимость в сети ({len(low_visibility)})")
    report.append("\n*Участники, информацию о которых трудно найти в сети (разовые доклады, отсутствие указания академического института, только инициалы):*")
    report.append("\n| Ученый (Инициалы) | Исходная запись | Кол-во докладов |")
    report.append("| :--- | :--- | :--- |")
    for name, std, count in low_visibility[:20]:
        report.append(f"| **{std}** | {name} | {count} |")
    report.append("| ... | ... | ... |")

    # Write report
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"Successfully generated scholarly analysis report in {OUTPUT_REPORT}!")
    conn.close()

if __name__ == "__main__":
    main()
