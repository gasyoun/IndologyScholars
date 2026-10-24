"""Entity gazetteer matcher for the nagari live pipeline (H1518 Step 4).

Loads ``gazetteers/*.tsv`` (canonical / type / aliases / qid, |-separated
aliases) and matches lemmatized+raw text against each alias with a
word-boundary regex -- stdlib only, no live dependency on
``indic_transliteration`` (alias folding is done once, by hand, when the TSV
rows are authored/updated offline).
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

GAZETTEER_DIR = Path(__file__).resolve().parent / "gazetteers"
GAZETTEER_FILES = ("texts.tsv", "scholars.tsv", "dictionaries.tsv", "tools_places.tsv")


def _word_pattern(alias: str) -> re.Pattern:
    escaped = re.escape(alias.strip())
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.I)


@lru_cache(maxsize=1)
def load_gazetteer() -> list[tuple[str, str, list[re.Pattern]]]:
    """Return [(canonical, type, [alias patterns])] across all gazetteer files."""
    entries: list[tuple[str, str, list[re.Pattern]]] = []
    for fname in GAZETTEER_FILES:
        path = GAZETTEER_DIR / fname
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                canonical = (row.get("canonical") or "").strip()
                etype = (row.get("type") or "").strip()
                aliases_raw = (row.get("aliases") or "").strip()
                if not canonical or not etype:
                    continue
                aliases = [canonical] + [a for a in aliases_raw.split("|") if a.strip()]
                patterns = [_word_pattern(a) for a in aliases]
                entries.append((canonical, etype, patterns))
    return entries


def match(text: str) -> list[tuple[str, str]]:
    """Return [(canonical, type)] for every gazetteer entity found in text."""
    hay = text or ""
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for canonical, etype, patterns in load_gazetteer():
        if canonical in seen:
            continue
        if any(p.search(hay) for p in patterns):
            hits.append((canonical, etype))
            seen.add(canonical)
    return hits
