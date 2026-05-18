import requests
from bs4 import BeautifulSoup
import sqlite3
import re

def initialize_database():
    conn = sqlite3.connect('indology_scholars.db')
    cursor = conn.cursor()
    
    # Создание основной таблицы для сырых данных
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scholars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            extracted_name TEXT,
            raw_biography TEXT,
            source_url TEXT
        )
    ''')
    conn.commit()
    return conn

def scrape_karttunen_database(conn):
    base_url = "https://whowaswho-indology.info"
    slugs = [
        'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i-j', 'k', 'l', 'm', 
        'n', 'o', 'p-q', 'r', 's', 't', 'u-v', 'w', 'x-z'
    ]
    
    cursor = conn.cursor()
    
    for slug in slugs:
        page_url = f"{base_url}/{slug}/"
        print(f"Извлечение данных: {page_url}")
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; IndologyResearchBot/2.0)'}
            response = requests.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка соединения {page_url}: {e}")
            continue
            
        soup = BeautifulSoup(response.content, 'html.parser')
        content_div = soup.find('div', class_='entry-content')
        
        if not content_div:
            print(f"Контент не найден для {slug}.")
            continue
            
        current_name = "Unknown"
        current_block = [] 
        
        for element in content_div.find_all(['p', 'ul', 'ol', 'blockquote', 'h3']):
            text = element.get_text(separator=' ', strip=True)
            if not text:
                continue
                
            # Ищем начало новой статьи: Заглавные буквы, запятая, Имя
            is_new_entry = bool(re.match(r'^[\*\s]*[A-ZÄÖÜÅŠŽČ\-\s]{2,},\s+[A-Z]', text))
            
            if is_new_entry:
                # Сохраняем предыдущего ученого
                if current_block:
                    full_raw_text = "\n\n".join(current_block)
                    cursor.execute('''
                        INSERT INTO scholars (extracted_name, raw_biography, source_url)
                        VALUES (?, ?, ?)
                    ''', (current_name, full_raw_text, page_url))
                
                # Начинаем собирать нового ученого
                name_match = re.split(r'\.', text, maxsplit=1)
                current_name = name_match[0].replace('*', '').strip() if name_match else "Unknown"
                current_block = [text] 
            else:
                # Продолжение текущей статьи (например, списки трудов)
                if current_block:
                    current_block.append(text)
                
        # Сохранение последнего ученого на странице
        if current_block:
            full_raw_text = "\n\n".join(current_block)
            cursor.execute('''
                INSERT INTO scholars (extracted_name, raw_biography, source_url)
                VALUES (?, ?, ?)
            ''', (current_name, full_raw_text, page_url))
            
    conn.commit()
    print("Парсинг завершен. Данные сохранены полностью, включая библиографии.")

if __name__ == "__main__":
    db = initialize_database()
    scrape_karttunen_database(db)
    db.close()
