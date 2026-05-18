import os
import datetime
import requests
from bs4 import BeautifulSoup

CACHE_DIR = "html_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_latest_zograf(year):
    filename = f"zograf_{year}.html"
    filepath = os.path.join(CACHE_DIR, filename)
    
    # If already cached, no need to re-fetch
    if os.path.exists(filepath):
        print(f"Zograf program for {year} already cached: {filepath}")
        return
        
    print(f"Searching for Zograf Readings program YYYY={year}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # Heuristic 1: Scan IOM RAS news/announcements search
    search_url = "http://www.orientalstudies.ru/rus/index.php?option=com_search&searchword=%D0%B7%D0%BE%D0%B3%D1%80%D0%B0%D1%84%D1%81%D0%BA%D0%B8%D0%B5+%D1%87%D1%82%D0%B5%D0%BD%D0%B8%D1%8F"
    try:
        r = requests.get(search_url, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Look for links containing "Зографские чтения" and the year
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text()
                if str(year) in text or str(year) in href:
                    if "com_events" in href or "com_publications" in href:
                        full_url = "http://www.orientalstudies.ru" + href if href.startswith('/') else href
                        print(f"Found potential Zograf page for {year}: {full_url}")
                        
                        # Fetch and save
                        resp = requests.get(full_url, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(resp.text)
                            print(f"Successfully cached Zograf program to {filepath}")
                            return
    except Exception as e:
        print(f"Error checking Zograf online directory: {e}")
        
    # Heuristic 2: Fallback template (Zograf readings usually use com_events structure)
    fallback_url = f"http://www.orientalstudies.ru/rus/index.php?option=com_events&Itemid=39&pub=zograf_{year}"
    print(f"Trying Zograf fallback template URL: {fallback_url}")
    try:
        resp = requests.get(fallback_url, headers=headers, timeout=10)
        if resp.status_code == 200 and "Зограф" in resp.text:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"Cached Zograf fallback program for {year} successfully!")
        else:
            print(f"Fallback page for Zograf {year} not available or does not contain conference listings.")
    except Exception as e:
        print(f"Fallback fetch failed for Zograf {year}: {e}")

def fetch_latest_roerich(year):
    filename = f"roerich_{year}.html"
    filepath = os.path.join(CACHE_DIR, filename)
    
    if os.path.exists(filepath):
        print(f"Roerich program for {year} already cached: {filepath}")
        return
        
    print(f"Searching for Roerich Readings program YYYY={year}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # Roerich readings are hosted on IV RAS ancient division
    roerich_news_url = f"https://ancient.ivran.ru/novosti?year={year}"
    try:
        r = requests.get(roerich_news_url, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Look for news containing "Рериховские чтения"
            found_program = False
            for card in soup.find_all('div', class_='news-card'):
                text = card.get_text()
                if "Рериховские чтения" in text or "рериховских чтений" in text.lower():
                    # Extract link
                    link = card.find('a', href=True)
                    if link:
                        full_href = "https://ancient.ivran.ru" + link['href'] if link['href'].startswith('/') else link['href']
                        print(f"Found Roerich news article for {year}: {full_href}")
                        
                        # Fetch the news detail page containing the program
                        resp = requests.get(full_href, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(resp.text)
                            print(f"Successfully cached Roerich program to {filepath}")
                            found_program = True
                            break
            
            if not found_program:
                # If no specific card is found, cache the main news page for that year which might list them
                print(f"No specific news article card found. Caching news overview for {year}.")
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print(f"Successfully cached Roerich main news overview to {filepath}")
    except Exception as e:
        print(f"Error checking Roerich online directory: {e}")

def main():
    current_year = datetime.datetime.now().year
    print(f"Executing active crawler for year {current_year}...")
    
    fetch_latest_zograf(current_year)
    fetch_latest_roerich(current_year)

if __name__ == "__main__":
    main()
