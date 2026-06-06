"""Fixture tests for the institutional web scraper (no network).

ivran.ru is unreachable from outside .ru, so the live scrape can only run on
the maintainer's machine — but the HTML parsing and novelty-keying are pure
functions and are tested here against fixtures mirroring the documented markup.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scratch"))

import scrape_institutions_web as iw  # noqa: E402


STAFF_FIXTURE = """
<div class="letter"><h2>В</h2>
  <p><a href="/persons/EugeniaVanina">Ванина&nbsp;Е.Ю.</a></p>
  <p><a href="/persons/IvanHistorian">Иванов И.И.</a></p>
</div>
<div class="letter"><h2>Г</h2>
  <p><a href="https://www.ivran.ru/persons/Glushkova">Глушкова И.П.</a></p>
  <a href="/about">О институте</a>
</div>
"""


def test_extract_staff_links_parses_names_and_absolutises_urls():
    links = iw.extract_staff_links(STAFF_FIXTURE, "/persons/", "https://www.ivran.ru")
    by_name = {l["name"]: l["url"] for l in links}
    assert "Ванина Е.Ю." in by_name            # &nbsp; collapsed to space
    assert by_name["Ванина Е.Ю."] == "https://www.ivran.ru/persons/EugeniaVanina"
    assert by_name["Глушкова И.П."] == "https://www.ivran.ru/persons/Glushkova"
    assert len(links) == 3                       # /about link excluded


def test_extract_person_detail_strips_scripts_and_tags():
    html = ('<html><head><style>.x{}</style></head><body>'
            '<script>var a=1;</script>'
            '<div id="content"><h1>Ванина Е.Ю.</h1>'
            '<p>Отдел истории и культуры Древнего Востока. Специалист по '
            'истории Индии.</p></div></body></html>')
    text = iw.extract_person_detail(html)
    assert "var a=1" not in text
    assert ".x{}" not in text
    assert "истории Индии" in text


def test_is_indologist_keyword_filter():
    assert iw.is_indologist("Специалист по санскриту и культуре Южной Азии")
    assert iw.is_indologist("Отдел истории Индии")
    assert not iw.is_indologist("Отдел Африки, специалист по экономике Египта")


def test_staff_surname_initial_key():
    assert iw.staff_surname_initial_key("Ванина Е.Ю.") == "ванина е"
    assert iw.staff_surname_initial_key("Глушкова И.П.") == "глушкова и"
    assert iw.staff_surname_initial_key("") == ""
