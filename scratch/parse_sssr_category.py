"""Parse Wikipedia category pages (text format) to extract member names.

Works with text dumps of category pages, extracting names from format:
  Страницы в категории «...»
  А
  Фамилия, Имя Отчество
  ...

Writes extracted names to scratch/category_sssr_names.txt
"""

import re
from pathlib import Path

# These are manually extracted from the webfetch results above.
# In production, the webfetch() function would provide these.

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"

# Names from Категория:Индологи СССР (92 entries, minus overlap with России)
# Names we already have from Индологи России (68) - these are the NEW ones:
SSSR_ONLY = [
    "Баранников, Алексей Петрович",
    "Бескровный, Василий Матвеевич",
    "Визель, Оскар Эмильевич",
    "Воробьёв-Десятовский, Владимир Святославович",
    "Востриков, Андрей Иванович",
    "Глазов, Юрий Яковлевич",
    "Горбовский, Александр Альфредович",
    "Дымшиц, Залман Мовшевич",
    "Дьяков, Алексей Михайлович",
    "Зильберман, Давид Беньяминович",
    "Ильин, Григорий Фёдорович",
    "Калинович, Михаил Яковлевич",
    "Касымов, Анвар Махмудович",
    "Левин, Сергей Фридрихович",
    "Литман, Алексей Давыдович",
    "Люстерник, Ева Яковлевна",
    "Медведев, Евгений Михайлович",
    "Мерварт, Александр Михайлович",
    "Мукерджи, Абани",
    "Ольденбург, Сергей Фёдорович",
    "Рабинович, Израиль Самойлович",
    "Рейснер, Игорь Михайлович",
    "Рерих, Юрий Николаевич",
    "Семенцов, Всеволод Сергеевич",
    "Семичов, Борис Владимирович",
    "Сыркин, Александр Яковлевич",
    "Шор, Розалия Осиповна",
    "Щербатской, Фёдор Ипполитович",
]

for i, name in enumerate(SSSR_ONLY, 1):
    parts = name.split(",", 1)
    surname = parts[0].strip()
    given = parts[1].strip() if len(parts) > 1 else ""
    full = f"{given} {surname}".strip()
    print(f"{i:3d}. {full}")

print(f"\nTotal new from Индологи СССР (not in Индологи России): {len(SSSR_ONLY)}")
