#!/usr/bin/env python3
"""Regenerate the README snapshot captions/tables from the fresh site_data.json.

validate_publication.py (H5426) pins the README snapshot caption AND the
summary-table numbers to site_data.json's own fields. Nothing maintained
those lines automatically, so any data change that moved `generated` past
the last manual sync failed the Validate Publication Build (seen 2026-10-01:
payload regenerated to 2026-10-01, READMEs still said 2026-09-25).

Every pattern must replace exactly one line; a missed or duplicated match is
a hard error so drift can never pass silently again.
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent


def replace_one(text: str, pattern: str, replacement: str, label: str) -> str:
    new, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match, found {count}")
    return new


def main() -> None:
    data = json.loads((ROOT / "site_data.json").read_text(encoding="utf-8"))
    s = data["summary"]
    generated = data["generated"]
    years = (
        f"{s['years_covered']}, с {s['start_year']} по {s['end_year']} г.",
        f"{s['years_covered']}, from {s['start_year']} to {s['end_year']}",
    )

    ru_rows = {
        r"^\| Профили докладчиков \| .*\|$": f"| Профили докладчиков | {s['total_scholars']} |",
        r"^\| Уникальные доклады \| .*\|$": f"| Уникальные доклады | {s['unique_presentations']} |",
        r"^\| Авторские участия \| .*\|$": f"| Авторские участия | {s['total_presentations']} |",
        r"^\| Программные годы \| .*\|$": f"| Программные годы | {years[0]} |",
        r"^\| Участники обеих площадок \| .*\|$": f"| Участники обеих площадок | {s['overlap_scholars']} |",
        r"^\| Только Зографские чтения \| .*\|$": f"| Только Зографские чтения | {s['zograf_only_scholars']} |",
        r"^\| Только Рериховские чтения \| .*\|$": f"| Только Рериховские чтения | {s['roerich_only_scholars']} |",
    }
    en_rows = {
        r"^\| Speaker profiles \| .*\|$": f"| Speaker profiles | {s['total_scholars']} |",
        r"^\| Unique talks \| .*\|$": f"| Unique talks | {s['unique_presentations']} |",
        r"^\| Author participations \| .*\|$": f"| Author participations | {s['total_presentations']} |",
        r"^\| Programme years \| .*\|$": f"| Programme years | {years[1]} |",
        r"^\| Speakers found at both series \| .*\|$": f"| Speakers found at both series | {s['overlap_scholars']} |",
        r"^\| Zograf Readings only \| .*\|$": f"| Zograf Readings only | {s['zograf_only_scholars']} |",
        r"^\| Roerich Readings only \| .*\|$": f"| Roerich Readings only | {s['roerich_only_scholars']} |",
    }

    targets = {
        "README.md": [
            *[(r"снимок `site_data\.json` от \d{4}-\d{2}-\d{2}",
               f"снимок `site_data.json` от {generated}")],
            *ru_rows.items(),
        ],
        "README_EN.md": [
            *[(r"`site_data\.json` summary of \d{4}-\d{2}-\d{2}",
               f"`site_data.json` summary of {generated}")],
            *en_rows.items(),
        ],
    }

    for name, edits in targets.items():
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        for pattern, replacement in edits:
            text = replace_one(text, pattern, replacement, f"{name}:{pattern[:40]}")
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{name}: synced to site_data.json @ {generated}")


if __name__ == "__main__":
    main()
