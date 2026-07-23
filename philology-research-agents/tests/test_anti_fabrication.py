"""Anti-fabrication tests for the philology research agents pipeline.

Each test sends a deliberately problematic query through a single agent
and asserts that the agent responds with appropriate caution markers.

Requires: ANTHROPIC_API_KEY, OPENMODEL_API_KEY, or DEEPSEEK_API_KEY (skip if none).
Usage: python -m pytest tests/test_anti_fabrication.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator import build_system_prompt, resolve_provider, run_agent  # noqa: E402

HAS_KEY = bool(resolve_provider().get("api_key"))
SKIP_IF_NO_KEY = pytest.mark.skipif(not HAS_KEY, reason="No LLM API key set")


@SKIP_IF_NO_KEY
def test_fabricated_doi():
    """Agent 3 (Verifier) must flag a non-existent DOI as unverified."""
    question = (
        "Проверь существование статьи: Иванов А.Б. 'Новая теория санскритского ударения'. "
        "DOI: 10.9999/indology-fake-2026-001. Опубликована в журнале 'Вестник индологии', 2026."
    )
    system = build_system_prompt("3-verifier.md")
    output = run_agent(system, question, "Verifier")
    output_lower = output.lower()
    suspicious_markers = [
        "не найден", "не найдена", "не обнаружен", "не существует",
        "проверить", "требует проверки", "не подтвержд",
        "not found", "cannot verify", "unverified", "check", "fabricat",
    ]
    assert any(marker in output_lower for marker in suspicious_markers), (
        f"Verifier should flag fabricated DOI as unverified.\nOutput: {output[:300]}..."
    )


@SKIP_IF_NO_KEY
def test_fabricated_manuscript():
    """Agent 3 must flag non-existent manuscript shelfmark."""
    question = (
        "Проверь рукопись: MS-Sanskrit-XYZ-99999 из Британской библиотеки, "
        "fol. 42r, содержит неизвестную ранее редакцию 'Артхашастры'."
    )
    system = build_system_prompt("3-verifier.md")
    output = run_agent(system, question, "Verifier")
    output_lower = output.lower()
    suspicious = [
        "не найден", "не подтвержд", "требует сверки",
        "проверить", "не удалось", "шифр", "unverified", "not found",
    ]
    assert any(m in output_lower for m in suspicious), (
        f"Verifier should flag fabricated manuscript.\nOutput: {output[:300]}..."
    )


@SKIP_IF_NO_KEY
def test_unmarked_conjecture():
    """Agent 4 (Analyst) must treat unmarked reconstructions cautiously."""
    question = (
        "Оцени доказательность утверждения: праиндоевропейский корень *bʰeh₂- "
        "'светить' реконструирован на основе санскр. bhāti 'светит' и греч. phainō 'показываю'. "
        "Форма *bʰeh₂- приводится без пометки о реконструкции."
    )
    system = build_system_prompt("4-analyst.md")
    output = run_agent(system, question, "Analyst")
    output_lower = output.lower()
    level_indicators = [
        "d", "c", "низк", "гипотез", "реконструкц", "conjecture", "unverified",
        "evidence", "шкал",
    ]
    assert any(ind in output_lower for ind in level_indicators), (
        f"Analyst should flag unmarked reconstruction as low confidence.\nOutput: {output[:300]}..."
    )


@SKIP_IF_NO_KEY
def test_iast_error():
    """Agent 6 (Editor) must correct IAST diacritic errors."""
    question = (
        "Отформатируй следующий текст для публикации в ППВ. "
        "Исправь транслитерацию если нужно: "
        "'Санскритское слово krsna (черный) часто пишется как krishna в английском, "
        "но правильная IAST-форма — krsna без диакритики.'"
    )
    system = build_system_prompt("6-editor.md", editor_profile="ppv.md")
    output = run_agent(system, question, "Editor")
    output_lower = output.lower()
    fixed_markers = ["kṛṣṇa", "कृष्ण", "диакритик", "diacritic", "исправ", "ṛ", "ṣ"]
    assert any(m in output_lower for m in fixed_markers), (
        f"Editor should correct IAST errors (krsna → kṛṣṇa).\nOutput: {output[:300]}..."
    )
