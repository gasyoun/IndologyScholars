"""H3269: affiliation org-tail aliases + independent-researcher shorthand."""

from publication_helpers import normalize_affiliation


def test_independent_shorthand_ni():
    assert normalize_affiliation("НИ") == "Независимые исследователи"
    assert normalize_affiliation("ни") == "Независимые исследователи"
    assert normalize_affiliation("НИ, Лозанна") == "Независимые исследователи"
    assert normalize_affiliation("ни, Лозанна") == "Независимые исследователи"
    assert (
        normalize_affiliation("Наталья Афонасьевна НИ")
        == "Независимые исследователи"
    )


def test_independent_shorthand_does_not_eat_cities():
    assert normalize_affiliation("Нижний Новгород") is None
    assert normalize_affiliation("Калининград") is None


def test_urao_and_sheremetev_castle():
    assert normalize_affiliation("УРАО, Нижний Новгород") == "УРАО"
    assert (
        normalize_affiliation("ГБУ «Замок Шереметьева», онлайн")
        == "ГБУ Замок Шереметьева"
    )


def test_existing_independent_and_ivran_still_work():
    assert normalize_affiliation("независимый исследователь") == "Независимые исследователи"
    assert normalize_affiliation("ИВР РАН") == "ИВР РАН"
