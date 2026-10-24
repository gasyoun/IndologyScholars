"""Two-level curated topic taxonomy for nagari (H1518 Wave 1).

Parents hold child labels; each child is a compiled regex over lemmatized
subject+body text. The original eight flat tags remain as children so the
legacy ``topics_by_year`` series does not regress when reclassified.

Expanded 18-08-2026 from a 6-parent/12-child skeleton (PR #135) to 9
parents / 34 children, seeded from ``data/processed/misc_audit.csv`` top
terms and ``data/phrases.csv`` top collocations measured on the cleaned
(footer/quote-stripped) corpus -- see ``nagari_group_archive._lemma``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nagari_group_archive._lemma import lemmatize

# Parent -> child -> pattern (applied to lemmatized text).
PARENTS: dict[str, dict[str, re.Pattern]] = {
    "лексикография": {
        "словарь": re.compile(
            r"словар|dictionary|lexicon|кош[аеу]?|koś|monier|monier-williams|"
            r"бётлинг|böhtlingk|бётлингк|бюлер|b[üu]hler|апте|\bapte\b|\bpwg?\b|\bmw\b|тезаурус|"
            r"pwg|pwk|vcp|amarakosa|амарак|macdonell|whitney",
            re.I,
        ),
        "этимология": re.compile(r"этимолог|etymolog|корень|√|dhātu|дхату", re.I),
        "сравнительное_языкознание": re.compile(
            r"родствен.{0,15}слов|cognate|индоевропей|indo-european|сравнительн.{0,15}язык|"
            r"праязык|proto-indo|дравидск|заимствован(?!ие в право)|пантеон|pantheon",
            re.I,
        ),
        "терминология": re.compile(r"термин(?!ал)|глоссари|определени.{0,15}слов|значени слов", re.I),
        "исправление_опечаток": re.compile(
            r"опечатк|список.{0,15}правильн.{0,15}написани|typo\b|список исправлени",
            re.I,
        ),
    },
    "грамматика": {
        "учебник": re.compile(
            r"учебник|самоучител|граммати|grammar|урок|"
            r"упражнени|морфолог",
            re.I,
        ),
        "панини": re.compile(r"панини|pāṇini|panini|аштадхьяи|aṣṭādhyāyī|sutra|сутра", re.I),
        "спряжение_глагол": re.compile(
            r"глагол(?!а санскрит)|спряжени|verb\b|conjugat|каузатив|интенсив|"
            r"дхатупатх|dhātupāṭha|десятеричн",
            re.I,
        ),
        "склонение_падеж": re.compile(
            r"падеж|склонени|declens|каракa|kāraka|винительн|творительн|"
            r"родительн падеж|местн падеж",
            re.I,
        ),
        "сандхи_фонетика": re.compile(
            r"сандхи|sandhi|анусвара|anusvāra|висарга|visarga|звук(?! записи)|фонетик|phonet|"
            r"произношени|ретрофлекс",
            re.I,
        ),
        "синтаксис": re.compile(r"синтаксис|syntax|предложени(?! отменить)|порядок слов", re.I),
        "словообразование_сложные_слова": re.compile(
            r"словосложени|словообразовани|сложн.{0,10}слов(?!о поэтому)|samāsa|самаса|"
            r"bahuvrīhi|бахуврихи|tatpuruṣa|татпуруша",
            re.I,
        ),
        "частицы_служебные_слова": re.compile(r"частиц(?!а санскрит)|союз(?!а)|предлог(?!ать)", re.I),
        "часть_речи": re.compile(r"часть речи|части речи|part of speech", re.I),
        "метрика_чхандас": re.compile(r"чхандас|chandas|метрик.{0,10}санскрит|метр(?!ополит)|размер стиха", re.I),
    },
    "тексты": {
        "текст": re.compile(
            r"махабхарат|рамаян|\bгита\b|бхагавад|шлок|стих|"
            r"упаниш|панишад|upaniṣad|"
            r"веды|ведийск|пуран|rigveda|ṛgveda|bhagavad|панчатантр|pañcatantra",
            re.I,
        ),
        "чтение": re.compile(
            r"читаем_с_орс|читаем с орс|разбор|медленное чтение|satsang|"
            r"padavibhāg|анвая|anvaya|mūlam|pratipadārtha",
            re.I,
        ),
        "йога_васиштха": re.compile(r"йога.{0,10}васиштх|yoga.{0,10}vasi[sṣ]th|васиштх", re.I),
        "комментарии_ачарьи": re.compile(
            r"ачарь|ācārya|коммент(?!арий к письм)|bhāṣya|бхашья|śaṅkara|шанкар|мадхусудан",
            re.I,
        ),
        "мантра_бхакти": re.compile(r"мантр(?!ис)|бхакти|bhakti|джапа|japa|молитв", re.I),
        "стотра_гимн": re.compile(
            r"стотр|stotra|сахасранам|sahasranāma|сукт|sūkta|гимн(?! записи)|нама.{0,10}вишн",
            re.I,
        ),
    },
    "инструменты": {
        "сайт": re.compile(
            r"сайт|\bsite\b|github|веб-?страниц|приложение|"
            r"sanskrit-lexicon|api\b|база данных",
            re.I,
        ),
        "шрифт": re.compile(
            r"шрифт|\bfont\b|unicode|юникод|кодировк|deva?nagari|деванагари|"
            r"transliterat|транслитер|раскладк|клавиатур|крякозябр|typing|text editor",
            re.I,
        ),
        "pdf": re.compile(r"\bpdf\b|\.pdf|ocr|распозна|отскан|djvu", re.I),
        "программа_приложение": re.compile(
            r"программ(?!у чтения)|software|приложени(?! к письм)|\bapp\b|инструмент(?! исследован)|"
            r"\bsandic\b",
            re.I,
        ),
        "корпус_данные": re.compile(
            r"корпус(?!а санскрит)|corpus|параллельн.{0,10}текст|компиляци.{0,10}текст|dataset",
            re.I,
        ),
    },
    "книги_и_раздача": {
        "книга": re.compile(
            r"книг|моногра|издани|скан(?!дировать)|учебн?ое пособ|библиотек|книгохран|печатн|bookzealots",
            re.I,
        ),
        "обмен_файлами": re.compile(r"rapidshare|файлообменник|ссылк.{0,10}скачать|торрент|torrent", re.I),
    },
    "организация_группы": {
        "курс_практикум": re.compile(r"курс(?!ив)|практикум|занятие|семинар|вебинар|webinar", re.I),
        "встреча_событие": re.compile(r"встреч(?!ается)|событи|конференци|conference|очн.{0,10}встреч", re.I),
        "знакомство": re.compile(r"меня зовут|позвольте представ|новый участник|добро пожаловать", re.I),
        "администрирование_группы": re.compile(
            r"модератор|правила группы|администр(?!ация индии)|подписк.{0,10}настро",
            re.I,
        ),
    },
    "переводы_и_издания": {
        "перевод_вопрос": re.compile(
            r"перевести|переведите|как переводится|помогите.{0,15}перевод|"
            r"правильный перевод|перевод.{0,10}санскрит",
            re.I,
        ),
        "издание_версия": re.compile(r"издани(?! от русск)|критическ.{0,10}издани|редакци текста|version of the text", re.I),
        "билингва_английский": re.compile(r"\benglish\b|на английск|перевод на английск|translation into", re.I),
    },
    "история_и_культура": {
        "индия_путешествие": re.compile(r"инди[яию]|india\b|путешестви.{0,10}инди|ашрам", re.I),
        "традиция_философия": re.compile(
            r"традици|философ(?!ия языка)|адвайта|advaita|веданта|vedānta|санкхья|sāṃkhya",
            re.I,
        ),
        "персона_ученый": re.compile(
            r"кнауэр|knauer|биограф.{0,10}учен|indolog(?!ical dictionary)|"
            r"зализняк|zaliznyak|елизаренкова|elizarenkova",
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


# -- Subject preprocessing (H1518 Step 3: adopted convention, no reuse target
#    found -- Indology/indology_archive_research/topics.py does not exist in
#    this checkout as of 18-08-2026, org citation is stale). --
_RE_PREFIX = re.compile(r"^\s*(re|fwd|fw)\s*:\s*", re.I)
_LIST_TAG = re.compile(r"^\s*\[[^\]]{1,40}\]\s*")
_NOISY_SUBJECT = re.compile(r"^\s*(test|тест|digest|дайджест)\b", re.I)


def clean_subject(subject: str) -> str:
    """Strip Re:/Fwd:/[list-tag] prefixes repeatedly (threads accumulate them)."""
    s = subject or ""
    prev = None
    while prev != s:
        prev = s
        s = _RE_PREFIX.sub("", s)
        s = _LIST_TAG.sub("", s)
    return s.strip()


def is_noisy_subject(subject: str) -> bool:
    """True for digest/test subjects that should not seed topic terms."""
    return bool(_NOISY_SUBJECT.match((subject or "").strip()))


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
