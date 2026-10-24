"""Append-only JSONL logger for first-party DeepSeek calls.

Writes usage, model, and ids only — never the API key or Authorization header.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH = Path("analytics_output") / "deepseek_flash_calls.jsonl"
FLASH_IN_PER_M = 0.14
FLASH_OUT_PER_M = 0.28


def estimate_usd(usage: dict[str, Any] | None) -> float:
    usage = usage or {}
    inp = int(usage.get("prompt_tokens") or 0)
    out = int(usage.get("completion_tokens") or 0)
    return inp * FLASH_IN_PER_M / 1_000_000 + out * FLASH_OUT_PER_M / 1_000_000


def log_deepseek_call(
    *,
    script: str,
    model: str,
    ids: Iterable[str],
    usage: dict[str, Any] | None = None,
    ok: bool = True,
    error: str | None = None,
    path: Path | str | None = None,
) -> None:
    dest = Path(path) if path else DEFAULT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    usage = dict(usage or {})
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": script,
        "model": model,
        "ids": [str(i) for i in ids],
        "n": 0,
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
        "usd_est": round(estimate_usd(usage), 6),
        "ok": bool(ok),
        "error": error,
    }
    record["n"] = len(record["ids"])
    with dest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
