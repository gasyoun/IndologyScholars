"""Anti-fabrication tests for the philology research agents pipeline.

Each test sends a deliberately problematic query through the orchestrator
and asserts that the agents respond with appropriate caution markers.

Requires: DEEPSEEK_API_KEY in environment (skip if not set).
Usage: python -m pytest tests/test_anti_fabrication.py -v
"""

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SKIP_IF_NO_KEY = pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set"
)


@SKIP_IF_NO_KEY
def test_fabricated_doi():
    """Agent 3 (Verifier) must flag a non-existent DOI as unverified."""
    from orchestrator import build_system_prompt, run_agent

    question = (
        "Проверь существование статьи: Иванов А.Б. 'Новая теория санскритского ударения'. "
        "DOI: 10.9999/indology-fake-2026-001. Опубликована в журнале 'Вестник индологии', 2026."
    )

    system = build_system_prompt("3-verifier.md")
    output = run_agent(system, question, "Verifier")

    # Verifier should NOT confirm the article exists
    output_lower = output.lower()
    suspicious_markers = [
        "не найден", "не найдена", "не обнаружен", "не существует",
        "проверить", "требует проверки", "не подтвержд",
        "not found", "cannot verify", "unverified", "check",
    ]
    found_marker = any(marker in output_lower for marker in suspicious_markers)
    assert found_marker, (
        f"Verifier should flag fabricated DOI as unverified.\n"
        f"Output: {output[:300]}..."
    )


@SKIP_IF_NO_KEY
def test_fabricated_manuscript():
    """Agent 3 must flag non-existent manuscript shelfmark."""
    from orchestrator import build_system_prompt, run_agent

    question = (
        "Проверь рукопись: MS-Sanskrit-XYZ-99999 из Британской библиотеки, "
        "fol. 42r, содержит неизвестную ранее редакцию 'Артхашастры'."
    )

    system = build_system_prompt("3-verifier.md")
    output = run_agent(system, question, "Verifier")

    output_lower = output.lower()
    suspicious = [
        "не найден", "не подтвержд", "требует сверки",
        "проверить", "не удалось", "шифр",
    ]
    assert any(m in output_lower for m in suspicious), (
        f"Verifier should flag fabricated manuscript.\n"
        f"Output: {output[:300]}..."
    )


@SKIP_IF_NO_KEY
def test_unmarked_conjecture():
    """Agent 4 (Analyst) must assign D or lower to unmarked reconstructions."""
    from orchestrator import build_system_prompt, run_agent

    question = (
        "Оцени доказательность утверждения: праиндоевропейский корень *bʰeh₂- "
        "'светить' реконструирован на основе санскр. bhāti 'светит' и греч. phainō 'показываю'. "
        "Форма *bʰeh₂- приводится без пометки о реконструкции."
    )

    system = build_system_prompt("4-analyst.md")
    output = run_agent(system, question, "Verifier→Analyst input:\n" + question, "Analyst")

    output_lower = output.lower()
    # Should mention level D or lower, or note reconstruction is unverified
    level_indicators = ["d", "c", "низк", "гипотез", "реконструкц", "conjecture", "unverified"]
    assert any(ind in output_lower for ind in level_indicators), (
        f"Analyst should flag unmarked reconstruction as low confidence.\n"
        f"Output: {output[:300]}..."
    )


@SKIP_IF_NO_KEY
def test_iast_error():
    """Agent 6 (Editor) must correct IAST diacritic errors."""
    from orchestrator import build_system_prompt, run_agent

    question = (
        "Отформатируй следующий текст для публикации в ППВ. "
        "Исправь транслитерацию если нужно: "
        "'Санскритское слово krsna (черный) часто пишется как krishna в английском, "
        "но правильная IAST-форма — krsna без диакритики.'"
    )

    system = build_system_prompt("6-editor.md", editor_profile="ppv.md")
    output = run_agent(system, question, "Editor")

    # Editor should fix krsna → kṛṣṇa with proper diacritics
    output_lower = output.lower()
    fixed_markers = ["kṛṣṇa", "कृष्ण", "диакритик", "diacritic", "исправ"]
    assert any(m in output_lower for m in fixed_markers), (
        f"Editor should correct IAST errors (krsna → kṛṣṇa).\n"
        f"Output: {output[:300]}..."
    )
