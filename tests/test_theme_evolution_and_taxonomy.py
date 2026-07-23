"""Theme evolution helper smoke + nagari taxonomy offline tests."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nagari"))


def test_theme_share_csv_writable(tmp_path, monkeypatch):
    from generate_publication_pages import generate_theme_evolution_page

    # Only run if meso source exists in the worktree.
    src = ROOT / "analytics_output" / "meso_codes_deepseek.csv"
    if not src.exists():
        pytest.skip("meso_codes_deepseek.csv not present")
    # generate writes into cwd analytics_output + findings/
    monkeypatch.chdir(ROOT)
    generate_theme_evolution_page()
    out = ROOT / "analytics_output" / "theme_share_by_year.csv"
    assert out.exists()
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows
    assert "year" in rows[0] and "share" in rows[0]
    page = ROOT / "findings" / "theme-evolution.html"
    assert page.exists()
    html = page.read_text(encoding="utf-8")
    assert "Эволюция тем" in html or "meso" in html.lower()


def test_taxonomy_classifies_dictionary():
    from nagari_group_archive.taxonomy import classify

    cl = classify("Новый словарь monier-williams и PWG на github")
    assert "словарь" in cl.labels or cl.primary == "словарь"
    assert cl.parent in ("лексикография", "инструменты")


def test_taxonomy_misc_fallback():
    from nagari_group_archive.taxonomy import classify

    cl = classify("привет всем, как дела?")
    assert cl.primary == "разное"


def test_lemma_identity_without_map():
    from nagari_group_archive._lemma import lemmatize, tokens

    assert "санскрит" in lemmatize("Санскрит и грамматика")
    assert tokens("короткие токены аб")  # keeps longer tokens
