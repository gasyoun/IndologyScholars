import pytest
from title_normalization import (
    repair_random_hyphenation,
    normalize_proper_name_casing,
    canonical_title,
    TITLE_OVERRIDES_BY_PRESENTATION_ID
)

def test_repair_random_hyphenation():
    assert repair_random_hyphenation("древне- индийский") == "древнеиндийский"
    assert repair_random_hyphenation("южно- азиатский") == "южноазиатский"
    assert repair_random_hyphenation("индо- арийский") == "индоарийский"
    assert repair_random_hyphenation("обычное-слово") == "обычное-слово"

def test_normalize_proper_name_casing():
    assert normalize_proper_name_casing("сюжет из махабхараты") == "сюжет из Махабхараты"
    assert normalize_proper_name_casing("гимн в ригведе и рамаяне") == "гимн в ригведе и Рамаяне"
    assert normalize_proper_name_casing("поездка в индию") == "поездка в Индию"

def test_canonical_title_overrides():
    # Test known override ID
    pid = "PRES_8a6912982a"
    original = "Some broken text from HTML"
    expected = TITLE_OVERRIDES_BY_PRESENTATION_ID[pid]
    assert canonical_title(pid, original) == expected

def test_canonical_title_cleaning():
    # Affiliation strip (if split_leading_affiliation separates it)
    # Online/zoom suffix strip
    assert canonical_title(None, "Доклад о философии (СПбГУ)") == "Доклад о философии (СПбГУ)"
    assert canonical_title(None, "Исследование буддизма. online ") == "Исследование буддизма"
    # Trailing time strip
    assert canonical_title(None, "Доклад на секции - 14:30") == "Доклад на секции"
    assert canonical_title(None, "Выступление 15.00 секция 2") == "Выступление"
