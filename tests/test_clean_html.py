"""Regression tests for scratch/expand_wikipedia_indologists.clean_html.

`clean_html` strips ru.wikipedia HTML fragments to plain text for name and
affiliation extraction. It is implemented on top of the stdlib HTML parser
(no tag-matching regexes — CodeQL py/bad-tag-filter). These tests pin the
behaviours that two earlier regex/parser revisions got wrong: bare-ampersand
corruption, word merging across comments, and leaking <script>/<style> bodies.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scratch"))

import expand_wikipedia_indologists as ex  # noqa: E402


def test_bare_ampersand_preserved_no_data_loss():
    # A literal '&' (not a real entity) must not delete the following word or
    # inject a stray ';'.
    assert ex.clean_html("R&department") == "R&department"
    assert ex.clean_html("Procter&Gamble") == "Procter&Gamble"
    assert ex.clean_html("A&B&C истории") == "A&B&C истории"


def test_comment_cdata_pi_separate_words():
    assert ex.clean_html("Иван<!--c-->Петров") == "Иван Петров"
    assert ex.clean_html("Имя<![CDATA[junk]]>Фамилия") == "Имя Фамилия"
    assert ex.clean_html("a<?pi data?>b") == "a b"
    assert ex.clean_html("before<!--\nmulti\nline\n-->after") == "before after"


def test_entities_decoded():
    assert ex.clean_html("a &amp; b") == "a & b"
    assert ex.clean_html("&eacute;cole") == "école"
    assert ex.clean_html("M&uuml;ller") == "Müller"
    assert ex.clean_html("год &#1072; буква") == "год а буква"
    assert ex.clean_html("Гос.&nbsp;университет") == "Гос. университет"


def test_script_style_bodies_dropped_any_case():
    assert ex.clean_html("<SCRIPT>alert(1)</SCRIPT>Иванов") == "Иванов"
    assert ex.clean_html("<STYLE>.a{color:red}</STYLE>Имя") == "Имя"
    assert ex.clean_html("pre<script>js()</script>post") == "pre post"
    # malformed end tag must still close the script element
    assert ex.clean_html('<script>bad()</script foo="bar">visible') == "visible"


def test_plain_text_and_inline_tags():
    assert ex.clean_html("Просто текст 1920") == "Просто текст 1920"
    assert ex.clean_html("<b>Имя</b> <i>Фам</i>") == "Имя Фам"
    assert ex.clean_html("a<br/>b") == "a b"
    assert ex.clean_html("") == ""


def test_no_markup_leaks_into_output():
    out = ex.clean_html('<div class="infobox"><tr><th>Род</th><td>деятельности</td></tr></div>')
    assert "<" not in out and ">" not in out
    assert "Род" in out and "деятельности" in out


def test_no_data_loss_on_entity_like_literal_text():
    # Unknown, double-encoded, or non-entity '&word;'/'&digits;' tokens are real
    # source text and must survive. Regression for the deleted post-decode entity
    # regexes, which used to run on already-decoded text and erase these.
    assert ex.clean_html("x &foo; y") == "x &foo; y"
    assert ex.clean_html("x &123; y") == "x &123; y"
    assert ex.clean_html("see note &1; below") == "see note &1; below"
    assert ex.clean_html("Tom &amp;amp; Jerry") == "Tom &amp; Jerry"
    assert ex.clean_html("Black &amp;white; photography") == "Black &white; photography"


def test_css_class_name_in_prose_not_deleted():
    # Plain text mentioning the .mw-parser-output class (or any prose before a
    # later brace group) must survive — regression for the removed CSS-cleanup
    # regex, whose greedy span deleted everything in between.
    txt = "Стиль .mw-parser-output {цвет} задаётся темой"
    assert ex.clean_html(txt) == txt
    assert ex.clean_html("A .mw-parser-output is a CSS class {literal}") == (
        "A .mw-parser-output is a CSS class {literal}"
    )
    # The parser still drops real <style> bodies (the regex's former job):
    assert ex.clean_html("<style>.mw-parser-output{x}</style>Имя") == "Имя"


def test_malformed_input_never_crashes():
    for s in ("<script", "</style ", "&amp", "<!--", "-->", "&#", "<![CDATA[", "<?", "a&b<c>d"):
        ex.clean_html(s)  # must not raise
