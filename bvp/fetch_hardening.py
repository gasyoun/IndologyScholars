#!/usr/bin/env python3
"""Small, source-agnostic hardening primitives for the BVP fetcher."""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class Backoff:
    """Return an adaptive pause after consecutive network-class failures."""

    def __init__(
        self,
        threshold: int = 5,
        steps: tuple[float, ...] = (60.0, 300.0, 600.0),
    ) -> None:
        self.threshold = threshold
        self.steps = steps
        self.consecutive = 0

    def record_error(self) -> float:
        self.consecutive += 1
        if self.consecutive < self.threshold:
            return 0.0
        tier = min(
            self.consecutive // self.threshold - 1,
            len(self.steps) - 1,
        )
        return self.steps[tier]

    def record_success(self) -> None:
        self.consecutive = 0


class FailLedger:
    """Persistent, append-only set of URLs that failed permanently."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.known: set[str] = set()

    def load(self) -> set[str]:
        if self.path.exists():
            self.known = {
                line.strip()
                for line in self.path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                if line.strip()
            }
        return self.known

    def add(self, url: str) -> None:
        if url in self.known:
            return
        self.known.add(url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(url + "\n")

    def __contains__(self, url: str) -> bool:
        return url in self.known
