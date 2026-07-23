"""Two-level curated topic taxonomy for nagari (H1518 Wave 1).

Parents hold child labels; each child is a compiled regex over lemmatized
subject+body text. The original eight flat tags remain as children so the
legacy ``topics_by_year`` series does not regress when reclassified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nagari_group_archive._lemma import lemmatize

# Parent → child → pattern (applied to lemmatized text).
PARENTS: dict[str, dict[str, re.Pattern]] = {
    "лексикография": {
        "словарь": re.compile(
            r"словар|dictionary|lexicon|кош[аеу]?|koś|monier|monier-williams|"
            r"бётлинг|böhtlingk|бётлингк|апте|\bapte\b|\bpwg?\b|\bmw\b|тезаурус|"
            r"pwg|pwk|vcp|amarakosa|амарак",
            re.I,
        ),
        "этимология": re.compile(r"этимолог|etymolog|корень|√|dhātu|дхату", re.I),
    },
    "грамматика": {
        "учебник": re.compile(
            r"учебник|самоучител|граммати|grammar|пани[нь]и|p[āa]nini|урок|"
            r"упражнени|склонени|спряжени|сандхи|sandhi|морфолог",
            re.I,
        ),
        "панини": re.compile(r"панини|pāṇini|panini|аштадхьяи|aṣṭādhyāyī|sutra|сутра", re.I),
    },
    "тексты": {
        "текст": re.compile(
            r"махабхарат|рамаян|\bгита\b|бхагавад|шлок|стих|перевод|упаниш|"
            r"веды|ведийск|пуран|коммент|rigveda|ṛgveda|bhagavad",
            re.I,
        ),
        "чтение": re.compile(r"читаем_с_орс|читаем с орс|разбор|медленное чтение|satsang", re.I),
    },
    "инструменты": {
        "сайт": re.compile(
            r"сайт|\bsite\b|github|программ|приложение|веб|\bapp\b|"
            r"sanskrit-lexicon|api|база данных",
            re.I,
        ),
        "шрифт": re.compile(
            r"шрифт|\bfont\b|unicode|юникод|кодировк|deva?nagari|деванагари|"
            r"transliterat|транслитер|раскладк|клавиатур",
            re.I,
        ),
        "pdf": re.compile(r"\bpdf\b|\.pdf|ocr|распозна|отскан|djvu", re.I),
    },
    "книги_и_раздача": {
        "книга": re.compile(
            r"книг|моногра|издани|скан|учебн?ое пособ|библиотек|книгохран|печатн|bookzealots",
            re.I,
        ),
    },
    "прочее": {
        "астрология": re.compile(r"астролог|джьот|jyoti|ведическ.*астрон", re.I),
    },
}

# Preserve original flat 8-tag order as a compatibility view.
LEGACY_TAG_ORDER = [
    "словарь", "учебник", "книга", "pdf", "сайт", "шрифт", "астрология", "текст",
]


@dataclass
class Classification:
    primary: str
    labels: list[str]
    parent: str


def classify(text: str, lemma_map: dict | None = None) -> Classification:
    """Return primary child label, all matching labels, and parent of primary."""
    lem = lemmatize(text or "", lemma_map)
    hits: list[tuple[str, str]] = []  # (parent, child)
    for parent, children in PARENTS.items():
        for child, pattern in children.items():
            if pattern.search(lem) or pattern.search(text or ""):
                hits.append((parent, child))
    if not hits:
        return Classification(primary="разное", labels=["разное"], parent="прочее")
    # Prefer first hit in legacy order when present.
    labels = list(dict.fromkeys(c for _, c in hits))
    primary = next((t for t in LEGACY_TAG_ORDER if t in labels), labels[0])
    parent = next((p for p, c in hits if c == primary), hits[0][0])
    return Classification(primary=primary, labels=labels, parent=parent)


def parent_of(child: str) -> str:
    for parent, children in PARENTS.items():
        if child in children:
            return parent
    if child == "разное":
        return "прочее"
    return "прочее"
