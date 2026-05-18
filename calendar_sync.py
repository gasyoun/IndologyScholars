import sqlite3
import re
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_calendar():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def get_calendar_id(service, calendar_name="Indology"):
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for entry in calendar_list['items']:
            if entry['summary'].lower() == calendar_name.lower():
                return entry['id']
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    raise ValueError(f"Календарь '{calendar_name}' не найден. Создайте его вручную.")

def parse_date(date_str, current_year=2026):
    if not date_str:
        return None, None, False

    year_match = re.search(r'\b(1[4-9]\d{2}|20\d{2})\b', date_str)
    hist_year = year_match.group(1) if year_match else "Unknown"

    exact_match = re.search(r'\b(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})\b', date_str)
    if exact_match:
        day, month, _ = exact_match.groups()
        return f"{current_year}-{int(month):02d}-{int(day):02d}", hist_year, True
    else:
        # Резервная дата: 30 января
        return f"{current_year}-01-30", hist_year, False

def create_anniversary_events():
    service = authenticate_google_calendar()
    try:
        calendar_id = get_calendar_id(service, "Indology")
    except ValueError as e:
        print(e)
        return

    conn = sqlite3.connect('indology_scholars.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT last_name, first_names, birth_date, death_date FROM structured_scholars')
        scholars = cursor.fetchall()
    except sqlite3.OperationalError:
        print("База данных не найдена.")
        return

    events_created = 0

    for row in scholars:
        last_name, first_names = row[0] or "Unknown", row[1] or ""
        b_date_raw, d_date_raw = row[2], row[3]
        full_name = f"{first_names} {last_name}".strip()

        # События: Дни рождения
        b_event_date, b_year, b_exact = parse_date(b_date_raw)
        if b_event_date and b_year != "Unknown":
            desc = f"Историческая дата рождения: {b_date_raw}"
            if not b_exact: desc += "\n\nПримечание: Точный месяц и день неизвестны. Дата установлена на 30 января."
            
            event = {
                'summary': f"Birth Anniversary: {full_name} (b. {b_year})",
                'description': desc,
                'start': {'date': b_event_date},
                'end': {'date': b_event_date},
                'recurrence': ['RRULE:FREQ=YEARLY'],
            }
            service.events().insert(calendarId=calendar_id, body=event).execute()
            events_created += 1

        # События: Дни смерти
        d_event_date, d_year, d_exact = parse_date(d_date_raw)
        if d_event_date and d_year != "Unknown":
            desc = f"Историческая дата смерти: {d_date_raw}"
            if not d_exact: desc += "\n\nПримечание: Точный месяц и день неизвестны. Дата установлена на 30 января."
            
            event = {
                'summary': f"Death Anniversary: {full_name} (d. {d_year})",
                'description': desc,
                'start': {'date': d_event_date},
                'end': {'date': d_event_date},
                'recurrence': ['RRULE:FREQ=YEARLY'],
            }
            service.events().insert(calendarId=calendar_id, body=event).execute()
            events_created += 1

    print(f"Успешно добавлено {events_created} событий в календарь 'Indology'.")
    conn.close()

if __name__ == "__main__":
    create_anniversary_events()
