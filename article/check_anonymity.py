"""Fail if the PPV anonymous manuscript leaks author-identifying metadata."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "article" / "ppv_submission_article_anonymous.md"

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "author name",
        re.compile(
            "Gas(?:\u016b|u)ns|Gasyoun|M(?:\u0101|a)rcis|Yurievich|"
            "\u0413\u0430\u0441\u0443\u043d\u0441|"
            "\u041c\u0430\u0440\u0446\u0438\u0441|"
            "\u042e\u0440\u044c\u0435\u0432\u0438\u0447",
            re.IGNORECASE,
        ),
    ),
    ("email address", re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")),
    ("ORCID", re.compile(r"\b\d{4}-\d{4}-\d{4}-[\dX]{4}\b", re.IGNORECASE)),
    (
        "postal address",
        re.compile(
            "Usacheva|Obninsk|Kaluga|249030|"
            "\u0423\u0441\u0430\u0447\u0435\u0432|"
            "\u041e\u0431\u043d\u0438\u043d\u0441\u043a|"
            "\u041a\u0430\u043b\u0443\u0433",
            re.IGNORECASE,
        ),
    ),
    ("affiliation phrase", re.compile(r"\bindependent researcher\b", re.IGNORECASE)),
    (
        "draft preface",
        re.compile(
            "\u041a\u0443\u0434\u0430 \u0432\u0441\u0442\u0440\u043e\u0438\u0442\u044c|"
            "\u041a\u0442\u043e \u0442\u0430\u043a\u043e\u0439 \u0443\u0447\u0435\u043d\u044b\u0439",
            re.IGNORECASE,
        ),
    ),
]


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def snippet(text: str, start: int, end: int) -> str:
    return text[max(0, start - 30): min(len(text), end + 30)].replace("\n", " ").strip()


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []

    for label, pattern in FORBIDDEN_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                f"{path}:{line_number(text, match.start())}: {label}: "
                f"{snippet(text, match.start(), match.end())}"
            )

    body = re.sub(r"^<!--.*?-->\s*", "", text, count=1, flags=re.DOTALL).lstrip()
    if not body.startswith("\u0423\u0414\u041a "):
        findings.append(f"{path}:1: anonymous article should start with UDK after optional comment")

    return findings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(arg) for arg in argv] if argv else [DEFAULT_TARGET]
    findings: list[str] = []
    for target in targets:
        findings.extend(check_file(target))

    if findings:
        print("Anonymity check failed:")
        for finding in findings:
            print(f"  {finding}")
        return 1

    print("Anonymity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
