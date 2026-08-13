"""Offline tests for H2678 flash remainder helpers (no API)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.deepseek_call_log import estimate_usd, log_deepseek_call  # noqa: E402


def test_estimate_usd_flash_cache_miss_rates():
    assert estimate_usd({"prompt_tokens": 1_000_000, "completion_tokens": 0}) == 0.14
    assert estimate_usd({"prompt_tokens": 0, "completion_tokens": 1_000_000}) == 0.28


def test_log_deepseek_call_writes_jsonl_without_secrets(tmp_path: Path):
    dest = tmp_path / "calls.jsonl"
    log_deepseek_call(
        script="scratch/theme_coding_llm.py",
        model="deepseek-v4-flash",
        ids=["PRES_test"],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        ok=True,
        path=dest,
    )
    row = json.loads(dest.read_text(encoding="utf-8").strip())
    assert row["script"] == "scratch/theme_coding_llm.py"
    assert row["model"] == "deepseek-v4-flash"
    assert row["ids"] == ["PRES_test"]
    assert row["ok"] is True
    dumped = json.dumps(row)
    assert "sk-" not in dumped
    assert "Authorization" not in dumped
