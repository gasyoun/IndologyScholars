import os
import re
import csv
import json
import sqlite3
import hashlib
from pathlib import Path

PERSON_ID_MAP_PATH = "person_ids.json"
PERSON_ALIAS_PATH = "curation/person_aliases.csv"

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
                first = parts[2]
            else:
                last = parts[0]
                first = parts[1]
            return f"{last.lower()} {first[0].lower()} {patronymic[0].lower()}"

    # Fallback
    words = [w.lower() for w in re.findall(r'[А-ЯЁа-яёA-Za-z\-]+', name)]
    return " ".join(words)


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
    "minaeva м д": ("Минаева Мария Дмитриевна", "Minaeva Maria Dmitrievna", 1999, None),
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
    "атманова ю г": ("Атманова Юлия Георгиевна", "Atmanova Yulia Георгиевна", 1985, None),
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
    "sheлкович в м": ("Шелкович Владимир Михайлович", "Shelkovich Vladimir Mikhailovich", 1949, 2013),
    "шелкович в м": ("Шелкович Владимир Михайлович", "Shelkovich Vladimir Mikhailovich", 1949, 2013),
    "пахомов с в": ("Пахомов Сергей Владимирович", "Pakhomov Sergey Vladimirovich", 1968, None),
    "куликов л и": ("Куликов Леонид Игоревич", "Kulikov Leonid Igorevich", 1964, None),
    "краснодембская н г": ("Краснодембская Нина Георгиевна", "Krasnodembskaya Nina Georgievna", 1939, 2024),
    "номахмадов с х": ("Шомахмадов Сафарали Хайбуллоевич", "Shomakhmadov Safarali Khaibulloevich", 1976, None),
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
    "соколова о с": ("Соколова Ольга Сергеевна", "Sokolova Olga Sergeyevna", 1987, None),
    "лемешкина к в": ("Лемешкина Ксения Вячеславовна", "Lemeshkina Ksenia Vyacheslavovna", 1985, None),
    "маретина к а": ("Маретина Ксения Александровна", "Maretina Ksenia Александровна", 1982, None),
    "аникина а а": ("Аникина Анна Андреевна", "Anikina Anna Andreevna", 1986, None),
    "бычихина о в": ("Бычихина Ольга Владимировна", "Bychikhina Olga Владимировна", 1978, None),
    "яковлева м н": ("Яковлева Мария Николаевна", "Yakovleva Maria Nikolaevna", 1989, None),
    "ершова е м": ("Ершова Елизавета Михайловна", "Ershova Elizaveta Mikhailovna", 1993, None),
    "голубев с в": ("Голубев Сергей Владимирович", "Golubev Sergey Владимирович", 1980, None),
    "челнокова а в": ("Челнокова Анна Витальевна", "Chelnokova Anna Vitalyevna", 1971, None),
    
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
    "доктор исторических наук": ("доктор исторических наук", "2012", "https://www.hse.ru/org/persons/209813167/"),
    "комиссаров д а": ("кандидат филологических наук", "2012", "https://www.hse.ru/org/persons/209813167/"),
    "роберт о": ("доктор исторических наук", "2012", "https://www.hse.ru/org/persons/209813167/"),
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

# Authoritative biographical corrections
BIOGRAPHICAL_DATA.update({
    "вертоградова в в": ("Вертоградова Виктория Викторовна", "Vertogradova Victoria Viktorovna", 1933, None),
    "цветкова с о": ("Цветкова Светлана Олеговна", "Tsvetkova Svetlana Olegovna", 1978, None),
    "вечерина о п": ("Вечерина Ольга Павловна", "Vecherina Olga Pavlovna", 1960, 2023),
    "жутаев д и": ("Жутаев Дар Игоревич", "Zhutaev Dar Igorevich", 1969, 2020),
    "крапивина р н": ("Крапивина Раиса Николаевна", "Krapivina Raisa Nikolaevna", 1953, None),
    "ложкина а в": ("Ложкина Анастасия Витальевна", "Lozhkina Anastasia Vitalyevna", 1992, None),
    "комиссаров д а": ("Комиссаров Дмитрий Алексеевич", "Komissarov Dmitry Alekseevich", 1977, None),
    "алиханова ю м": ("Алиханова Юлия Марковна", "Alikhanova Yulia Markovna", 1936, 2024),
    "огнева е д": ("Огнева Елена Дмитриевна", "Ogneva Elena Dmitrievna", 1944, None),
    "шохин в к": ("Шохин Владимир Кириллович", "Shokhin Vladimir Kirillovich", 1951, None),
    "котин и ю": ("Котин Игорь Юрьевич", "Kotin Igor Yurievich", 1968, None),
    "самозванцев а м": ("Самозванцев Андрей Михайлович", "Samozvantsev Andrey Mikhailovich", 1949, 2009),
    "эрман в г": ("Эрман Владимир Гансович", "Erman Vladimir Gansovich", 1928, 2017),
    "попова и ф": ("Попова Ирина Фёдоровна", "Popova Irina Fyodorovna", 1961, None),
    "невелева с л": ("Невелева Светлана Леонидовна", "Neveleva Svetlana Leonidovna", 1937, None),

    # Verified birth dates and overrides
    "видунас в": ("Видунас Витис", "Vytis Vidunas", 1960, None),
    "бейнорюс а": ("Бейнорюс Аудрюс", "Audrius Beinorius", 1964, None),
    "яскунас в": ("Яскунас Валдас", "Valdas Jaskunas", 1973, None),
    "светлов р в": ("Светлов Роман Викторович", "Svetlov Roman Viktorovich", 1963, None),
    "кожевникова м н": ("Kozhevnikova Margarita Nikolaevna", "Kozhevnikova Margarita Nikolaevna", 1961, None),
    "яковлев в м": ("Яковлев Виктор Михайлович", "Yakovlev Viktor Mikhailovich", 1941, 2022),
    "хохлов а н": ("Хохлов Александр Николаевич", "Khokhlov Alexander Nikolaevich", 1929, 2015),
    "дылыкова в с": ("Дылыкова Вилена Санджиевна", "Dylykova Vilena Sandzhievna", 1938, None),
    "коробов в": ("Коробов Владимир Борисович", "Korobov Vladimir Borisovich", 1957, None),
    "коробов владимир борисович": ("Коробов Владимир Борисович", "Korobov Vladimir Borisovich", 1957, None),
    "пахомов с а": ("Пахомов Сергей Владимирович", "Pakhomov Sergey Vladimirovich", 1968, None),
    "загумённов б и": ("Загуменнов Борис Иванович", "Zagumennov Boris Ivanovich", 1947, None),
    "шoмaxмадов а х": ("Шомахмадов Сафарали Хайбуллоевич", "Shomakhmadov Safarali Khaibulloevich", 1976, None),
    "шомахмадов а х": ("Шомахмадов Сафарали Хайбуллоевич", "Shomakhmadov Safarali Khaibulloevich", 1976, None),
    "шарыгин г с": ("Шарыгин Глеб Витальевич", "Gleb Sharygin", 1987, None),
    "краснодембская н": ("Краснодембская Нина Георгиевна", "Krasnodembskaya Nina Georgievna", 1939, 2024),
    "лундышева о в": ("Лундышева Ольга Владимировна", "Lundysheva Olga Vladimirovna", 1982, None),
    "сладков а л": ("Сладков Андрей Леонидович", "Sladkov Andrey Leonidovich", 1976, None),
})


PERSON_ID_OVERRIDES = None

def load_person_id_overrides():
    global PERSON_ID_OVERRIDES
    if PERSON_ID_OVERRIDES is not None:
        return PERSON_ID_OVERRIDES
        
    if not Path(PERSON_ID_MAP_PATH).exists():
        PERSON_ID_OVERRIDES = {}
        return PERSON_ID_OVERRIDES
    with open(PERSON_ID_MAP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    PERSON_ID_OVERRIDES = data.get("normalized_keys", {})
    return PERSON_ID_OVERRIDES


person_aliases = None

def load_person_aliases():
    """Load curated source-name variants that should collapse into a canonical person."""
    global person_aliases
    if person_aliases is not None:
        return person_aliases

    accepted = {"accepted", "confirmed", "manual", "high"}
    person_aliases = {}
    if not Path(PERSON_ALIAS_PATH).exists():
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


def person_id_for_key(norm_key):
    override = load_person_id_overrides().get(norm_key)
    if override:
        return override
    digest = hashlib.sha1(norm_key.encode("utf-8")).hexdigest()[:8]
    return f"PERS_{digest}"


def _apply_degree(cursor, pid, deg):
    if not deg:
        return
    cursor.execute(
        "UPDATE person SET degree = ?, degree_year = ?, degree_source_url = ? WHERE person_id = ?",
        (deg[0], deg[1], deg[2], pid)
    )


def get_or_create_person(conn, name, source_url):
    name = name.strip()
    norm_key = canonical_person_key(name)
    source_norm_key = normalize_person_name(name)
    pid = person_id_for_key(norm_key)
    
    cursor = conn.cursor()
    cursor.execute("SELECT person_id, display_name FROM person WHERE person_id = ?", (pid,))
    row = cursor.fetchone()
    if row:
        current_display = row[1]
        # Prefer full name if currently initials-only
        if len(name) > len(current_display) and '.' not in name:
            cursor.execute("UPDATE person SET display_name = ? WHERE person_id = ?", (name, pid))
        return pid

    bio = BIOGRAPHICAL_DATA.get(norm_key) or BIOGRAPHICAL_DATA.get(source_norm_key)
    if bio:
        disp = bio[0]
        full_ru = bio[0]
        full_en = bio[1]
        b_year = bio[2]
        d_year = bio[3]
    else:
        disp = name
        full_ru = name if not any(c in 'abcdefghijklmnopqrstuvwxyz' for c in name.lower()) else None
        full_en = name if any(c in 'abcdefghijklmnopqrstuvwxyz' for c in name.lower()) else None
        b_year = None
        d_year = None

    cursor.execute(
        "INSERT INTO person (person_id, display_name, full_name_ru, full_name_en, birth_year, death_year, normalized_key, source_url) VALUES (?,?,?,?,?,?,?,?)",
        (pid, disp, full_ru, full_en, b_year, d_year, norm_key, source_url)
    )
    
    deg = DEGREE_DATA.get(norm_key) or DEGREE_DATA.get(source_norm_key)
    if deg:
        _apply_degree(cursor, pid, deg)
        
    conn.commit()
    return pid
