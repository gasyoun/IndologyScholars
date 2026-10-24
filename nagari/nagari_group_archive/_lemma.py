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

# The Google Groups unsubscribe/footer block is auto-appended verbatim to
# nearly every message and re-appears in every quoted reply below it -- left
# unstripped it dominates term/phrase frequency counts (H1518 finding,
# 18-08-2026). Cut the body at the first footer marker; this also drops the
# quoted-reply chain below it, which is standard signature-block position.
_FOOTER_MARKERS = (
    "Чтобы отменить подписку",
    "чтобы отменить подписку",
    "unsubscribe@googlegroups.com",
    "Вы получили это сообщение, поскольку подписаны",
    "groups.google.com/d/msgid/nagari",
)
_QUOTE_LINE = re.compile(r"^\s*>+", re.M)
# A raw email address inline is, in this corpus, always part of a quote-intro
# line ("On ... <name> <email> wrote:", "..., пользователь <name> <email>
# написал:", etc.) or the unsubscribe footer -- never legitimate discussion
# content. Google Groups' many client/locale intro formats accumulated over
# 20 years often wrap the name+email and the wrote:/написал: keyword onto
# separate lines, so anchoring on the keyword alone misses them; anchoring on
# the email address itself is the reliable cut point (H1518 finding,
# 18-08-2026). A residual keyword-only fallback (no email on the line, e.g. a
# bare "Имя Фамилия:" before a nested quote) covers what that misses.
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_QUOTE_INTRO_NO_EMAIL = re.compile(
    r"^.{0,80}(wrote|пишет|написал[аи]?)\s*:\s*$", re.M,
)


def strip_footer_and_quotes(body: str) -> str:
    """Cut the Google Groups footer + any quoted-reply chain from a message body."""
    text = body or ""
    cut = len(text)
    for marker in _FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    m = _EMAIL.search(text)
    if m:
        cut = min(cut, m.start())
    m = _QUOTE_INTRO_NO_EMAIL.search(text)
    if m:
        cut = min(cut, m.start())
    text = text[:cut]
    # Drop remaining ">"-quoted lines (older replies quoted inline, not just below).
    text = _QUOTE_LINE.sub("", text)
    return text


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
