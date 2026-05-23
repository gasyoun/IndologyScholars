import sqlite3
import re

SPB_PATTERNS = re.compile(
    r"СПб|Санкт-Петербург|Ленинград|ИВР|МАЭ|Кунсткам|РХГА|ЕУСПб|ГМИР|РНБ|Герцен|С\.-Петербург|С\.-Петерб|Эрмитаж",
    re.I
)
MOSCOW_PATTERNS = re.compile(
    r"Москва|МГУ|ИВ РАН|ВШЭ|ИКВИА|Высш|РГГУ|ИФ РАН|Институт философии|ИМЛИ|РУДН|ИСАА|ИЭА|этнологии и антропологии|ИЯз|ИЯ РАН|Институт языкознания|МГИМО|ПСТГУ|МГХПА|РГСУ|МПГУ|РАНХиГС|РХТУ|РГХПУ",
    re.I
)

def infer_city(affil):
    if not affil:
        return "Unknown"
    affil_clean = affil.strip()
    if not affil_clean or affil_clean == "":
        return "Unknown"
        
    if SPB_PATTERNS.search(affil_clean):
        return "SPb"
    elif MOSCOW_PATTERNS.search(affil_clean):
        return "Moscow"
    else:
        return "Regions/Foreign"

def main():
    con = sqlite3.connect("conferences.db")
    cursor = con.cursor()
    cursor.execute("SELECT DISTINCT affiliation_text_raw FROM presentation_person")
    affils = [r[0] for r in cursor.fetchall() if r[0]]
    
    mapping = []
    for aff in affils:
        city = infer_city(aff)
        mapping.append(f"{aff} ===> {city}")
        
    with open("scratch/city_mapping.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(mapping)))
    print("Wrote updated mappings to scratch/city_mapping.txt")

if __name__ == '__main__':
    main()
