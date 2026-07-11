"""Regression tests for `normalize_person_name` — the person-key parser.

The key derived here is the join spine: it decides which presentations, degrees,
disciplines and biographical rows fold onto one person, and it seeds the
deterministic `PERS_<sha1>` id. A wrong key silently forks or merges people.

The hard case is a surname whose own ending matches a patronymic suffix
(`-вич/-вна/-чна/-чич`): Коссович, Шелкович, Файбушевич. Two bugs lived here:

* H496 stopped such a surname from being read as the patronymic when it comes
  FIRST (surname-first order), and
* this suite pins the second half — the GIVEN-NAME-FIRST order, where the
  patronymic sits at index 1 and the surname (possibly `-вич`-ending) is last.
  Before the fix that branch took the given name as the surname
  (`Владимир Михайлович Шелкович` -> `владимир ш м`).

Both name orders must collapse to the same key, in every abbreviation form.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.biography import normalize_person_name as key  # noqa: E402


# (input, expected key). Each -вич/-вна surname appears in BOTH name orders and
# in the initial-forms the programme parsers actually emit.
CASES = [
    # surname-first (H496 covered this half)
    ("Шелкович Владимир Михайлович", "шелкович в м"),
    ("Файбушевич Светлана Ивановна", "файбушевич с и"),
    ("Коссович Каэтан Андреевич", "коссович к а"),
    # given-name-first (the half fixed here)
    ("Владимир Михайлович Шелкович", "шелкович в м"),
    ("Светлана Ивановна Файбушевич", "файбушевич с и"),
    ("Каэтан Андреевич Коссович", "коссович к а"),
    # initials, both spacings and both orders
    ("Шелкович В.М.", "шелкович в м"),
    ("Шелкович В. М.", "шелкович в м"),
    ("В.М. Шелкович", "шелкович в м"),
    ("В. М. Шелкович", "шелкович в м"),
    ("С.И. Файбушевич", "файбушевич с и"),
    # single initial
    ("Шелкович В.", "шелкович в"),
    ("Файбушевич С.", "файбушевич с"),
    # ordinary (non -вич) full names must be unaffected, both orders
    ("Вертоградова Виктория Викторовна", "вертоградова в в"),
    ("Виктория Викторовна Вертоградова", "вертоградова в в"),
    ("Шохин Владимир Кириллович", "шохин в к"),
]


@pytest.mark.parametrize("name, expected", CASES)
def test_person_key(name, expected):
    assert key(name) == expected


def test_both_orders_agree_for_patronymic_suffixed_surnames():
    """The load-bearing property: surname-first and given-first collapse to one key."""
    for surname_first, given_first in [
        ("Шелкович Владимир Михайлович", "Владимир Михайлович Шелкович"),
        ("Файбушевич Светлана Ивановна", "Светлана Ивановна Файбушевич"),
        ("Коссович Каэтан Андреевич", "Каэтан Андреевич Коссович"),
    ]:
        assert key(surname_first) == key(given_first)
