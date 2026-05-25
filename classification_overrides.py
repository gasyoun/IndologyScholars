"""Expert-reviewed presentation classifications used by public site generators."""

THEME_LABEL_OVERRIDES = {
    "ethnography": ("Этнография", "Ethnography"),
    "academic_history": ("История индологии", "History of Indology"),
    "religious_studies": ("Религиоведение", "Religious Studies"),
    "linguistics": ("Лингвистика", "Linguistics"),
    "literature": ("Литература", "Literature"),
}

MESO_LABELS = {
    "life_cycle_rituals": "Обряды жизненного цикла",
    "history_of_indology": "История индологии",
    "expeditions": "Экспедиции",
    "assam": "Ассам",
    "travel_history": "История путешествий",
    "himalaya": "Гималаи",
    "ritual_studies": "Ритуалистика",
    "etymology": "Этимологии",
    "new_indo_aryan_languages": "Новоиндийские языки",
    "fieldwork": "Полевые исследования",
    "modern_literature": "Современная литература",
    "english_literature": "Английская литература",
    "twentieth_century": "XX век",
    "metrics": "Метрика",
    "prosody": "Стихосложение",
    "literary_studies": "Литературоведение",
    "bengal": "Бенгалия",
    "comparative_analysis": "Сравнительный анализ",
    "vaishnava": "Вайшнавы",
    "jain": "Джайны",
    "cosmology": "Космология",
    "board_games": "Настольные игры",
    "eighteenth_century": "XVIII век",
    "nineteenth_century": "XIX век",
}

# A correction assigns a disciplinary rubric, an argument scale, and multiple
# meso-level entry points independently. Levels concern the scope of the
# argument, not the size or location of its subject.
CLASSIFICATION_OVERRIDES = {
    "PRES_f7cb0da910": {
        "theme_code": "ethnography",
        "gumilyov_level": 1,
        "meso_codes": ["ethnography_performance", "nepal_newar_kathmandu", "life_cycle_rituals"],
        "reason": "Описан ограниченный этнографический кейс: предметы и украшения внутри одного комплекса обрядов неваров; этноним не делает вывод региональным.",
    },
    "PRES_8906b4fcc3": {
        "theme_code": "academic_history",
        "gumilyov_level": 1,
        "meso_codes": ["history_of_indology", "expeditions", "assam", "twentieth_century"],
        "reason": "Доклад посвящен одной российской экспедиции 1911-1912 гг.; это кейс истории индологии, а не обобщение об Ассаме.",
    },
    "PRES_347181c549": {
        "theme_code": "academic_history",
        "gumilyov_level": 1,
        "meso_codes": ["history_of_indology", "travel_history", "himalaya", "nineteenth_century"],
        "reason": "Связка двух русских путешественников и конкретного маршрута относится к истории индологии и остается частным историческим сюжетом.",
    },
    "PRES_128cecab0d": {
        "theme_code": "religious_studies",
        "gumilyov_level": 1,
        "meso_codes": ["ritual_studies"],
        "reason": "Мадхупарка рассматривается в определенном ведийском ритуале; это религиоведческий микрокейс ритуалистики.",
    },
    "PRES_edb6f3ab45": {
        "theme_code": "linguistics",
        "gumilyov_level": 1,
        "meso_codes": ["etymology", "new_indo_aryan_languages", "himalaya", "fieldwork"],
        "reason": "Этимологии ограниченной лексики одного языка являются лингвистическим микрокейсом; принадлежность языка гималайскому ареалу не повышает масштаб аргумента.",
    },
    "PRES_a4e21c2702": {
        "theme_code": "literature",
        "gumilyov_level": 1,
        "meso_codes": ["modern_literature", "english_literature", "twentieth_century"],
        "reason": "Интертекстуальное чтение одного романа Рушди через «Рамаяну» является частным литературоведческим анализом.",
    },
    "PRES_99759d2e3f": {
        "theme_code": "literature",
        "gumilyov_level": 1,
        "meso_codes": ["metrics", "prosody", "literary_studies", "bengal"],
        "reason": "Типология систем стихосложения ограничена бенгальской поэтической традицией и относится к литературоведческому микромасштабу.",
    },
    "PRES_2b2a1fc14b": {
        "theme_code": "ethnography",
        "gumilyov_level": 1,
        "meso_codes": ["comparative_analysis", "vaishnava", "jain", "cosmology", "board_games", "eighteenth_century", "nineteenth_century"],
        "reason": "Сравнение двух вариантов конкретной игры знания остается анализом ограниченного типа артефактов; само слово «сравнительный» не означает макрообобщение.",
    },
}
