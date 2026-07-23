"""Stdlib form→lemma lookup for the nagari live pipeline (H1518).

The offline layer may build ``data/lemma_map.json`` with pymorphy2/natasha;
this module only *reads* that map. Missing map → identity lemmatization.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DEFAULT_MAP = Path(__file__).resolve().parents[1] / "data" / "lemma_map.json"
TOKEN_RE = re.compile(r"[а-яёА-ЯЁa-zA-ZāīūṛṝḷḹṃṁḥñṅṇṭḍśṣĀĪŪṚṜḶḸṂṀḤÑṄṆṬḌŚṢ]+", re.U)


@lru_cache(maxsize=1)
def load_lemma_map(path: str | None = None) -> dict[str, str]:
    p = Path(path) if path else DEFAULT_MAP
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).casefold(): str(v) for k, v in data.items() if k and v}


def lemmatize_token(token: str, lemma_map: dict[str, str] | None = None) -> str:
    if not token:
        return ""
    m = lemma_map if lemma_map is not None else load_lemma_map()
    key = token.casefold()
    return m.get(key, key)


def lemmatize(text: str, lemma_map: dict[str, str] | None = None) -> str:
    """Replace each alphabetic token with its lemma (or the token itself)."""
    m = lemma_map if lemma_map is not None else load_lemma_map()

    def repl(match: re.Match) -> str:
        return lemmatize_token(match.group(0), m)

    return TOKEN_RE.sub(repl, text or "")


def tokens(text: str, lemma_map: dict[str, str] | None = None, min_len: int = 3) -> list[str]:
    m = lemma_map if lemma_map is not None else load_lemma_map()
    out = []
    for raw in TOKEN_RE.findall(text or ""):
        if len(raw) < min_len:
            continue
        out.append(lemmatize_token(raw, m))
    return out
