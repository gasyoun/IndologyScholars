import pytest

from publication_helpers import classify_gender


# First name and patronymic must agree; either alone should also decide
# (Фома is absent from the name lists, so only the patronymic carries it).
@pytest.mark.parametrize("name,expected", [
    ("Иванова Мария Петровна", "F"),
    ("Петров Иван Сергеевич", "M"),
    ("Смирнова Ольга Ильинична", "F"),
    ("Сидоров Пётр Ильич", "M"),
    ("Кузнецов Семён Кузьмич", "M"),
    ("Орлов Фома Лукич", "M"),
])
def test_full_name_with_patronymic(name, expected):
    assert classify_gender(name) == expected


# Regression: "ярослав" sat in BOTH first-name lists, and the female list was
# checked first, so every patronymic-less Ярослав was coded F.
def test_yaroslav_is_male():
    assert classify_gender("Ярослав Бондарь") == "M"


# Regression: the female list contained the dead entry "ксен" which never
# matched "Ксения" under exact-match comparison.
def test_kseniya_recognised():
    assert classify_gender("Ксения Бондарь") == "F"


# Regression: a previous duplicate classifier matched the substring "ич"
# anywhere in the full name, so -ич surnames were coded male even with an
# unambiguous female first name.
@pytest.mark.parametrize("name,expected", [
    ("Татьяна Маркович", "F"),
    ("Елена Бабич", "F"),
])
def test_ich_surnames_left_to_first_name_stage(name, expected):
    assert classify_gender(name) == expected


@pytest.mark.parametrize("name,expected", [
    ("Иванова Анна", "F"),
    ("Петров Алексей", "M"),
    ("Шарма Прия", None),       # non-Russian name without usable morphology
    ("Smith John", None),        # Latin script falls through every stage
    ("", None),
    (None, None),
])
def test_fallback_stages_and_unknown(name, expected):
    assert classify_gender(name) == expected


def test_surname_declension_fallback():
    # No patronymic, first name not in the lists: surname declension decides.
    assert classify_gender("Э. Вертоградова") == "F"
    assert classify_gender("Э. Вертоградов") == "M"


def test_display_name_fallback_argument():
    assert classify_gender(None, "Мария Иванова") == "F"
    assert classify_gender("", "Сергей Иванов") == "M"
