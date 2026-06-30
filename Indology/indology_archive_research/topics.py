"""Human-readable subject-line taxonomy for INDOLOGY archive metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass


PREFIX_RE = re.compile(
    r"^\s*(?:(?:re|fw|fwd)\s*:\s*)*(?:\[[^\]]+\]\s*)*", re.IGNORECASE
)
BRACKET_RE = re.compile(r"\[[^\]]+\]")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TopicRule:
    name: str
    pattern: re.Pattern[str]


TOPIC_RULES: tuple[TopicRule, ...] = (
    TopicRule(
        "List administration",
        re.compile(r"\b(digest|unsubscribe|subscription|moderator|list\s+admin|mailman)\b", re.I),
    ),
    TopicRule(
        "Announcements and events",
        re.compile(
            r"\b(call for papers|cfp|conference|workshop|symposium|seminar|"
            r"lecture|webinar|summer school|course|program|programme|"
            r"position|postdoc|phd|fellowship|job|vacancy|studentship)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Bibliographic requests",
        re.compile(
            r"\b(article request|pdf|copy|scan|bibliograph|reference|"
            r"looking for|searching for|does anyone|where can i find|"
            r"seeking|needed|request|offprint)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Digital resources and tools",
        re.compile(
            r"\b(unicode|font|keyboard|software|database|digital|online|"
            r"website|web site|searchable|etext|e-text|ocr|xml|html|"
            r"dictionary|corpus|github|gretil|sanskrit library|sal|"
            r"download|encoding|transliteration)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Buddhism and Jainism",
        re.compile(
            r"\b(buddh|pali|jain|jaina|prakrit|abhidharma|bodhisattva|"
            r"theravada|mahayana|vajrayana|tripitaka|tipitaka)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Veda and ritual",
        re.compile(
            r"\b(veda|vedic|rigveda|rgveda|yajurveda|samaveda|atharvaveda|"
            r"brahmana|aranyaka|upanishad|upanisad|srauta|shrauta|ritual|"
            r"agnihotra|soma)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Grammar and linguistics",
        re.compile(
            r"\b(grammar|grammatical|linguistic|linguistics|panini|"
            r"pāṇini|ashtadhyayi|aṣṭādhyāyī|vyakarana|vyākaraṇa|"
            r"phonolog|morpholog|syntax|etymolog|nirukta|sandhi|"
            r"compound|samasa|samāsa)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Manuscripts and epigraphy",
        re.compile(
            r"\b(manuscript|ms\.?|mss\.?|palm[- ]leaf|codicolog|palaeograph|"
            r"paleograph|inscription|epigraph|copper[- ]plate|birch[- ]bark|"
            r"catalogue|catalog)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Texts and philology",
        re.compile(
            r"\b(edition|translation|commentary|text|philolog|mahabharata|"
            r"mahābhārata|ramayana|rāmāyaṇa|purana|purāṇa|kavya|kāvya|"
            r"gita|gītā|tantra|shastra|śāstra|sutra|sūtra)\b",
            re.I,
        ),
    ),
    TopicRule(
        "Teaching and pedagogy",
        re.compile(
            r"\b(teaching|pedagog|student|classroom|syllabus|textbook|"
            r"primer|learn sanskrit|sanskrit course|exam)\b",
            re.I,
        ),
    ),
    TopicRule(
        "History and culture",
        re.compile(
            r"\b(history|historical|king|dynasty|temple|iconograph|"
            r"religion|culture|india|south asia|persianate|calendar|"
            r"astronom|astrolog|medicine|ayurveda|āyurveda)\b",
            re.I,
        ),
    ),
)


def clean_subject(subject: str) -> str:
    """Normalize a subject for matching and display."""

    text = subject or ""
    text = BRACKET_RE.sub(" ", text)
    text = PREFIX_RE.sub("", text)
    text = text.replace("\u00a0", " ")
    text = SPACE_RE.sub(" ", text).strip(" -:\t\r\n")
    return text


def is_noisy_subject(subject: str) -> bool:
    """Return True for subjects likely to be list mechanics or low signal."""

    cleaned = clean_subject(subject).lower()
    if not cleaned:
        return True
    return bool(
        re.search(r"\bdigest,\s+vol\b|\bissue\s+\d+\b|\btest\b|\bunsubscribe\b", cleaned)
    )


def classify_subject(subject: str) -> tuple[str, list[str]]:
    """Return a primary topic and all matching topic labels."""

    cleaned = clean_subject(subject)
    matches = [rule.name for rule in TOPIC_RULES if rule.pattern.search(cleaned)]
    if not matches:
        matches = ["General scholarly discussion"]
    return matches[0], matches

