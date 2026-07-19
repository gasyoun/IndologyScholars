"""H459 regression tests for the Renou main-site rule table (generate_renou_layer.py).

Locks in the anchoring fix for the measured 7.1% mid-word-Cyrillic-substring
defect (docs/renou-precision-audit.md): "тика" (ṭīkā) no longer fires inside
Эро-тика/прак-тика/семан-тика/грамма-тика, "ману" (Manu) no longer fires
inside Ра-ману-джа/манускрипт, and genuine Russian morphological prefixes
(коммент->комментарий, бхашь->бхашья, панини) keep matching their declined
forms. Also locks in the matched_field/matched_field_text export (scope
item 2): a hit sourced from a subject tag must be attributed to "tag" with
the literal tag text, not silently folded into an opaque combined blob.
"""
from __future__ import annotations

import re

from generate_renou_layer import RULE_ROWS, apply_rules, compile_rules, normalized_rules


def make_row(title: str = "", tags: str = "", meso_codes: str = "", theme_en: str = "", theme_code: str = "", presentation_id: str = "PRES_test"):
    return {
        "presentation_id": presentation_id,
        "title": title,
        "year": "2020",
        "series": "Zograf Readings",
        "tags": tags,
        "meso_codes": meso_codes,
        "theme_en": theme_en,
        "theme_code": theme_code,
        "public_path": "",
        "source_url": "",
    }


def compiled_rules():
    return compile_rules(normalized_rules())


def codes_for(row, axis: str) -> set[str]:
    _, matches = apply_rules([row], compiled_rules())
    return {m["renou_code"] for m in matches if m["renou_axis"] == axis and m["presentation_id"] == row["presentation_id"]}


def test_tika_no_longer_matches_mid_word():
    # The clearest false positive from the precision audit: a paper on the
    # Ṛgveda, previously misfiled as commentary literature because "erotica"
    # ends in the letters of "ṭīkā".
    row = make_row(title="Эротика в Ригведе: мужское и женское начало")
    assert "bhasya" not in codes_for(row, "register")
    assert "rgveda" in codes_for(row, "register")
    assert "I" in codes_for(row, "state")


def test_tika_no_longer_matches_related_generic_words():
    for word in ["практика", "семантика", "грамматика", "проблематика", "поэтика", "герменевтика"]:
        row = make_row(title=f"Некоторая {word} исследования")
        assert "bhasya" not in codes_for(row, "register"), f"{word!r} should not fire register:bhasya"


def test_manu_no_longer_matches_ramanuja_or_manuscript():
    row = make_row(title="Рамануджа и его учение")
    assert "smrti" not in codes_for(row, "register")
    row2 = make_row(title="Санскритский манускрипт из частной коллекции")
    assert "smrti" not in codes_for(row2, "register")


def test_manu_still_matches_as_a_standalone_word():
    row = make_row(title="Законы Ману и дхармашастра")
    assert "smrti" in codes_for(row, "register")


def test_commentary_prefix_still_matches_inflected_forms():
    # Left-anchoring must not break legitimate Russian morphological
    # continuations of a prefix stem.
    row = make_row(title="Комментарий Шанкары к Брахма-сутрам")
    assert "bhasya" in codes_for(row, "register")


def test_panini_still_matches():
    row = make_row(title="Панини и его грамматика")
    assert "II" in codes_for(row, "state")


def test_pali_does_not_match_unrelated_russian_words():
    # "капали"/"спали" contain "пали" mid-word and are unrelated Russian verbs.
    row = make_row(title="Капли воды капали на землю, пока все спали")
    assert "V" not in codes_for(row, "state")


def test_no_duplicate_unanchored_latin_tokens_in_cyrillic_run():
    # jaina / vyākaraṇa / kāvya were present a second time, unanchored, inside
    # the Cyrillic alternation of three separate rules — pure redundancy with
    # the already-anchored \\b(...)\\b Latin group above them.
    for rule in RULE_ROWS:
        pattern = rule["pattern"] if isinstance(rule, dict) else rule[4]
        latin_group_match = re.match(r"\\b\((.*?)\)\\b", pattern)
        if not latin_group_match:
            continue
        latin_tokens = {t.lower() for t in latin_group_match.group(1).split("|")}
        remainder = pattern[latin_group_match.end():]
        for alt in remainder.split("|"):
            alt = alt.strip("(?<![а-яё])").strip("(?![а-яё])")
            if alt and alt.isascii() and alt.lower() in latin_tokens:
                raise AssertionError(f"{alt!r} duplicated unanchored in Cyrillic run of {pattern!r}")


def test_matched_field_attributes_tag_hits_separately_from_title():
    row = make_row(
        title="Эротика в Ригведе: мужское и женское начало",
        tags="Literature & Poetry",
    )
    _, matches = apply_rules([row], compiled_rules())
    kavya_hits = [m for m in matches if m["renou_code"] == "kavya"]
    assert kavya_hits, "expected the Poetry tag to fire register:kavya"
    assert kavya_hits[0]["matched_field"] == "tag"
    assert kavya_hits[0]["matched_field_text"] == "Literature & Poetry"
    rgveda_hits = [m for m in matches if m["renou_code"] == "rgveda"]
    assert rgveda_hits[0]["matched_field"] == "title"
    assert rgveda_hits[0]["matched_field_text"] == ""


def test_no_cyrillic_matched_term_occurs_only_mid_word_in_title():
    """The acceptance predicate from H459 / docs/renou-precision-audit.md:
    a Cyrillic matched_term may not occur ONLY mid-word (every occurrence
    preceded by another Cyrillic letter) inside its own title. Exercised here
    against a battery of the specific false positives the audit measured;
    the full-corpus check (0 of 1559 rows, was 121) is run manually via
    generate_renou_layer.py + the H459 acceptance script, not in this
    fixture-only unit test (no site_data_scholars.json fixture is set up
    here).
    """
    cyrillic_letter = "а-яёА-ЯЁ"
    titles = [
        "Эротика в Ригведе: мужское и женское начало",
        "Практика медитации в буддийской традиции",
        "Семантика ведийского текста",
        "Грамматика классического санскрита",
        "Рамануджа и его учение",
        "Санскритский манускрипт из частной коллекции",
        "Капли воды капали на землю, пока все спали",
        "Шведы и их вклад в индологию",
    ]
    _, matches = apply_rules([make_row(title=t, presentation_id=t) for t in titles], compiled_rules())
    for m in matches:
        term = m["matched_term"]
        if not re.fullmatch(f"[{cyrillic_letter}]+", term):
            continue
        title = m["title"]
        positions = [mm.start() for mm in re.finditer(re.escape(term), title, flags=re.IGNORECASE)]
        assert positions, f"{term!r} reported matched but absent from title {title!r}"
        all_mid_word = all(
            pos > 0 and re.match(f"[{cyrillic_letter}]", title[pos - 1])
            for pos in positions
        )
        assert not all_mid_word, f"{term!r} occurs only mid-word in title {title!r}"
