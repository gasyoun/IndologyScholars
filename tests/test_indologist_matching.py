"""Unit tests for the indologist-collection scrapers in scratch/.

These cover the core that the project status notes claimed had "0 false
positives" but that had no automated test: the name matcher and normaliser,
the non-destructive merge (the data-loss guard), the en-bridge title splitter,
and the no-BOM atomic writer.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
sys.path.insert(0, str(SCRATCH))

import scrape_common as sc          # noqa: E402
import crossref_nonparticipants as cx  # noqa: E402
import enwiki_bridge as eb          # noqa: E402
import expand_wikipedia_indologists as ex  # noqa: E402
import wikidata_enrich as we        # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────

def conf(full):
    return {"full_name_ru": full, "display_name": full,
            "zograf_talks": 1, "roerich_talks": 0, "total_talks": 1}


def wiki(surname, given, full=None):
    return {"surname": surname, "given_name": given,
            "full_name": full or f"{given} {surname}"}


# ── normalize_name ───────────────────────────────────────────────────

def test_normalize_yo_to_e():
    assert sc.normalize_name("Бётлингк") == sc.normalize_name("Бетлингк")


def test_normalize_case_and_spaces():
    assert sc.normalize_name("  Иван   Минаев ") == "иван минаев"


# ── match_score: the "0 false positives" core ────────────────────────

def test_same_surname_first_name_matches():
    assert cx.match_score(wiki("Минаев", "Иван Павлович"),
                          conf("Минаев Иван Павлович")) >= 95


def test_yo_insensitive_match():
    assert cx.match_score(wiki("Бётлингк", "Оттон Николаевич"),
                          conf("Бетлингк Оттон Николаевич")) >= 95


def test_initial_matches_full_given():
    # conference record carries only an initial: "Щербатской Ф."
    assert cx.match_score(wiki("Щербатской", "Фёдор Ипполитович"),
                          conf("Щербатской Ф.")) >= 80


def test_different_given_same_surname_rejected():
    # the documented guard: Иванов Вячеслав != Иванов Владимир
    assert cx.match_score(wiki("Иванов", "Вячеслав Всеволодович"),
                          conf("Иванов Владимир Николаевич")) == 0


def test_surname_mismatch_rejected():
    assert cx.match_score(wiki("Минаев", "Иван"),
                          conf("Ольденбург Сергей Фёдорович")) == 0


def test_empty_surname_scores_zero():
    assert cx.match_score(wiki("", "Иван"), conf("Минаев Иван")) == 0


# ── enwiki_bridge.split_ru_title ─────────────────────────────────────

def test_split_ru_title_basic():
    assert eb.split_ru_title("Щербатской, Фёдор Ипполитович") == (
        "Щербатской", "Фёдор Ипполитович", "Фёдор Ипполитович Щербатской")


def test_split_ru_title_strips_parenthetical():
    surname, given, _ = eb.split_ru_title("Минаев, Иван Павлович (индолог)")
    assert surname == "Минаев"
    assert given == "Иван Павлович"


# ── non-destructive merge (the data-loss guard) ──────────────────────

def _seed_master(tmp_path, monkeypatch):
    master = {
        "description": "x", "total_people": 2,
        "people": [
            {"wikipedia_title": "Минаев, Иван Павлович",
             "full_name": "Иван Павлович Минаев",
             "wikidata_qid": "Q171275", "birth_year": 1840},
            {"wikipedia_title": "Тест, Тест Тестович",
             "full_name": "Тест Тестович Тест", "wikidata_qid": ""},
        ],
        "new_from_institutions": [{"full_name": "X"}],
    }
    p = tmp_path / "master.json"
    p.write_text(json.dumps(master, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ex, "OUTPUT", p)
    return p


def test_empty_parse_never_shrinks(tmp_path, monkeypatch):
    _seed_master(tmp_path, monkeypatch)
    m, added, enriched = ex.merge_into_master([])
    assert (added, enriched) == (0, 0)
    assert len(m["people"]) == 2
    assert m.get("new_from_institutions")  # preserved, not dropped


def test_merge_enriches_without_clobbering(tmp_path, monkeypatch):
    _seed_master(tmp_path, monkeypatch)
    m, added, enriched = ex.merge_into_master([
        {"wikipedia_title": "Тест, Тест Тестович",
         "full_name": "Тест Тестович Тест",
         "wikidata_qid": "Q999", "birth_year": 1900},
        {"wikipedia_title": "Новиков, Новый Человек",
         "full_name": "Новый Человек Новиков", "wikidata_qid": "Q1"},
    ])
    assert added == 1        # Новиков appended
    assert enriched == 1     # Тест got an empty field filled
    titles = {p["wikipedia_title"] for p in m["people"]}
    assert "Новиков, Новый Человек" in titles
    minaev = next(p for p in m["people"] if p["wikipedia_title"].startswith("Минаев"))
    assert minaev["wikidata_qid"] == "Q171275"   # curated value untouched
    test_rec = next(p for p in m["people"] if p["wikipedia_title"].startswith("Тест"))
    assert test_rec["wikidata_qid"] == "Q999"    # empty field was filled


# ── atomic_write_json: UTF-8, no BOM ─────────────────────────────────

def test_atomic_write_no_bom(tmp_path):
    p = tmp_path / "out.json"
    sc.atomic_write_json(p, {"ключ": "значение"})
    raw = p.read_bytes()
    assert raw[:3].hex() != "efbbbf"             # CLAUDE.md BOM rule
    assert json.loads(raw.decode("utf-8"))["ключ"] == "значение"


# ── wikidata_enrich: claim date parsing ──────────────────────────────

def test_year_literal_parsing():
    assert we._year("+1840-01-01T00:00:00Z") == 1840
    assert we._year("-0500-00-00T00:00:00Z") == -500
    assert we._year("") is None


def test_parse_entity_dates():
    doc = {"entities": {"Q76423": {"claims": {
        "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1815-06-11T00:00:00Z"}}}}],
        "P570": [{"mainsnak": {"datavalue": {"value": {"time": "+1904-04-01T00:00:00Z"}}}}],
    }}}}
    assert we.parse_entity_dates(doc, "Q76423") == (1815, 1904)


def test_parse_entity_dates_missing():
    assert we.parse_entity_dates({"entities": {"Q1": {"claims": {}}}}, "Q1") == (None, None)
