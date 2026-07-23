"""Offline unit tests for the philology orchestrator (no API key required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator import (  # noqa: E402
    AGENTS,
    build_system_prompt,
    load_md,
    main,
    run_pipeline,
)


def test_all_agent_prompts_exist_and_nonempty():
    for filename, _label, _desc in AGENTS:
        path = ROOT / "agents" / filename
        assert path.exists(), f"missing {filename}"
        text = load_md(f"agents/{filename}")
        assert len(text) > 100, f"{filename} too short"


def test_shared_context_files_exist():
    for name in ("source-hierarchy.md", "evidence-scale.md", "conventions.md"):
        text = load_md(f"shared/{name}")
        assert len(text) > 50, name


def test_build_system_prompt_includes_agent_and_shared():
    system = build_system_prompt("3-verifier.md", editor_profile="ppv.md")
    assert "Verifier" in system or "Верификатор" in system or "вериф" in system.lower()
    assert len(system) > 500


def test_dry_run_pipeline_writes_structure(tmp_path):
    out = tmp_path / "out.md"
    text = run_pipeline("Тестовый вопрос о *bhū-.", editor_profile="ppv.md", output_file=str(out), dry_run=True)
    assert out.exists()
    assert "Researcher" in text or "Исследователь" in text
    assert "dry-run" in text
    # Six agent sections
    assert text.count("## ") >= 6


def test_main_dry_run_exit_zero():
    assert main(["--dry-run", "Does *arya- mean 'noble'?"]) == 0


def test_main_requires_question():
    assert main([]) == 1
