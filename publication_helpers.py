import html
import json
import re
from pathlib import Path


SITE_URL = "https://gasyoun.github.io/IndologyScholars/"
SITE_NAME = "Russian Indological Research Archive"
SITE_NAME_RU = "Российский индологический научный архив"
AUTHOR_NAME = "Dr. Mārcis Gasūns"
OG_IMAGE_PATH = "assets/og-image.png"
OG_IMAGE_URL = SITE_URL + OG_IMAGE_PATH

GENERATION_COHORTS = [
    {"code": "pre-1940", "start": None, "end": 1939, "ru": "Предшественники (до 1940)", "en": "Predecessors (before 1940)"},
    {"code": "1940s", "start": 1940, "end": 1949, "ru": "Когорта Василькова (1940-е)", "en": "Vasilkov cohort (1940s)"},
    {"code": "1950s", "start": 1950, "end": 1959, "ru": "Поколение 1950-х", "en": "1950s cohort"},
    {"code": "1960s", "start": 1960, "end": 1969, "ru": "Поколение 1960-х", "en": "1960s cohort"},
    {"code": "1970s", "start": 1970, "end": 1979, "ru": "Поколение 1970-х", "en": "1970s cohort"},
    {"code": "1980s", "start": 1980, "end": 1989, "ru": "Поколение 1980-х", "en": "1980s cohort"},
    {"code": "1990s", "start": 1990, "end": 1999, "ru": "Поколение 1990-х", "en": "1990s cohort"},
    {"code": "2000s", "start": 2000, "end": None, "ru": "Когорта Толчельникова (2000-е)", "en": "Tolchelnikov cohort (2000s)"},
]


def generation_cohort(birth_year):
    if birth_year is None:
        return None
    year = int(birth_year)
    for cohort in GENERATION_COHORTS:
        if (cohort["start"] is None or year >= cohort["start"]) and (cohort["end"] is None or year <= cohort["end"]):
            return cohort
    return None

THEME_LABELS = {
    "history_and_culture": ("История, этнография и общество", "History, Culture & Society"),
    "religion_and_philosophy": ("Религия и философия", "Religion & Philosophy"),
    "literature_and_poetry": ("Литература и поэзия", "Literature & Poetry"),
    "linguistics_and_philology": ("Лингвистика и филология", "Linguistics & Philology"),
    "art_and_material_culture": ("Искусство и материальная культура", "Art & Material Culture"),
    "unspecified": ("Разное / Не классифицировано", "Other / Unspecified"),
}

CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_time_interval(value, fallback=""):
    text = clean_text(value)
    if not text:
        return fallback

    def time_repl(match):
        hour = int(match.group(1))
        return f"{hour:02d}:{match.group(2)}"

    text = re.sub(r"(?<!\d)([01]?\d|2[0-3])\.(\d{2})(?!\d)", time_repl, text)
    text = re.sub(r"(\b\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2}\b)", r"\1 – \2", text)
    return text


def esc(value):
    return html.escape(clean_text(value), quote=True)


def slugify(value, fallback="item"):
    text = clean_text(value).lower()
    text = "".join(CYRILLIC_TO_LATIN.get(ch, ch) for ch in text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or fallback


PATRONYMIC_SUFFIXES = ("вич", "вна", "чна", "чич", "инична", "ична")


def _looks_like_initial(token):
    return bool(re.match(r"^[А-ЯЁA-Z]\.?$", token or ""))


def _looks_like_patronymic(token):
    return bool(token) and token.lower().endswith(PATRONYMIC_SUFFIXES)


def load_authority_overrides(path="authority_ids.json"):
    target = Path(path)
    if not target.exists():
        return {"persons": {}, "organizations": {}, "places": {}}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return {
        "persons": payload.get("persons") or {},
        "organizations": payload.get("organizations") or {},
        "places": payload.get("places") or {},
    }


def person_slug(scholar, authority_overrides=None):
    overrides = authority_overrides or {}
    pid = scholar.get("id") or scholar.get("person_id") or ""
    person_auth = (overrides.get("persons") or {}).get(pid) or {}
    fallback = (pid or "scholar").lower()

    preferred = person_auth.get("preferred_latin_name")
    if preferred:
        return slugify(preferred, fallback=fallback)

    source = (
        scholar.get("full_name_ru")
        or scholar.get("display_name")
        or scholar.get("name")
        or ""
    )
    parts = [p for p in source.split() if p]
    parts = [p for p in parts if not _looks_like_initial(p)]
    parts = [p for p in parts if not _looks_like_patronymic(p)]

    if len(parts) >= 2:
        candidate = f"{parts[0]} {parts[1]}"
    elif parts:
        candidate = parts[0]
    else:
        candidate = source or fallback

    return slugify(candidate, fallback=fallback)


def assign_unique_slugs(scholars, authority_overrides=None, slug_key="url_slug"):
    """Compute url_slug for each scholar, disambiguating collisions in place."""
    from collections import Counter

    for scholar in scholars:
        scholar[slug_key] = person_slug(scholar, authority_overrides)

    counts = Counter(s[slug_key] for s in scholars)
    taken = set()
    for scholar in scholars:
        slug = scholar[slug_key]
        if counts[slug] == 1 and slug not in taken:
            taken.add(slug)
            continue
        birth = scholar.get("birth_year")
        pid = scholar.get("id", "")
        if birth:
            candidate = f"{slug}-{birth}"
        elif pid:
            candidate = f"{slug}-{pid[-6:].lower()}"
        else:
            candidate = slug
        base = candidate
        suffix = 2
        while candidate in taken:
            candidate = f"{base}-{suffix}"
            suffix += 1
        scholar[slug_key] = candidate
        taken.add(candidate)


def site_url(path=""):
    return SITE_URL + str(path).lstrip("/")


def _normalize_external_id(value, prefix):
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return prefix + s


PUBLIC_AUTHORITY_CONFIDENCE = {"confirmed", "manual", "high"}


def is_public_authority_record(person_authority):
    if not person_authority:
        return False
    confidence = str(person_authority.get("confidence") or "").strip().lower()
    return confidence in PUBLIC_AUTHORITY_CONFIDENCE


def _orcid_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://orcid\.org/", "", s)
    s = s.upper()
    if re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", s):
        return f"https://orcid.org/{s}"
    return None


def _wikidata_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://www\.wikidata\.org/wiki/", "", s)
    if re.match(r"^Q\d+$", s):
        return f"https://www.wikidata.org/wiki/{s}"
    return None


def _viaf_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://viaf\.org/viaf/", "", s).strip("/")
    if re.match(r"^\d+$", s):
        return f"https://viaf.org/viaf/{s}"
    return None


def _openalex_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://openalex\.org/", "", s)
    if re.match(r"^A\d+$", s):
        return f"https://openalex.org/{s}"
    return None


def _google_scholar_url(value):
    s = str(value or "").strip()
    if s.startswith("https://scholar.google.") and "citations?user=" in s:
        return s
    if re.match(r"^[A-Za-z0-9_-]+$", s):
        return f"https://scholar.google.com/citations?user={s}"
    return None


def _scopus_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://www\.scopus\.com/authid/detail\.uri\?authorId=", "", s)
    if re.match(r"^\d+$", s):
        return f"https://www.scopus.com/authid/detail.uri?authorId={s}"
    return None


def _researcher_id_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://www\.webofscience\.com/wos/author/record/", "", s)
    if re.match(r"^[A-Z]{1,3}-\d{4}-\d{4}$", s) or re.match(r"^[A-Z0-9-]+$", s):
        return f"https://www.webofscience.com/wos/author/record/{s}"
    return None


def _rinc_url(value):
    s = str(value or "").strip()
    s = re.sub(r"^https?://(?:www\.)?elibrary\.ru/author_profile\.asp\?id=", "", s)
    if re.match(r"^\d+$", s):
        return f"https://www.elibrary.ru/author_profile.asp?id={s}"
    return None


def _official_url(value):
    s = str(value or "").strip()
    if s.startswith("https://") or s.startswith("http://"):
        return s
    return None


def clean_person_urls(person_authority):
    if not person_authority:
        return {}
    urls = {}

    def add_valid(key, target_key, normalizer):
        val = person_authority.get(key)
        if val:
            norm = normalizer(val)
            if norm:
                urls[target_key] = norm

    add_valid("orcid", "orcid", _orcid_url)
    add_valid("wikidata", "wikidata", _wikidata_url)
    add_valid("viaf", "viaf", _viaf_url)
    add_valid("openalex", "openalex", _openalex_url)
    add_valid("google_scholar", "google_scholar", _google_scholar_url)
    add_valid("scopus_author_id", "scopus_author_id", _scopus_url)
    add_valid("researcher_id", "researcher_id", _researcher_id_url)
    add_valid("rinc_author_id", "rinc_author_id", _rinc_url)

    # url or official_url
    url_val = person_authority.get("official_url") or person_authority.get("url")
    if url_val:
        norm = _official_url(url_val)
        if norm:
            urls["official_url"] = norm

    return urls


def _collect_alt_names(*sources):
    names = []
    for source in sources:
        if not source:
            continue
        if isinstance(source, str):
            names.append(source)
        elif isinstance(source, (list, tuple)):
            names.extend(s for s in source if s)
    return list(dict.fromkeys(n for n in names if n))


def place_structured_data(city_ru, city_en, geo, place_auth, canonical_path):
    place_auth = place_auth or {}
    place = {
        "@type": "Place",
        "@id": site_url(canonical_path) + "#place",
        "name": city_ru,
    }
    alt = _collect_alt_names(
        city_en if city_en and city_en != city_ru else None,
        place_auth.get("alternateName"),
    )
    if alt:
        place["alternateName"] = alt
    if geo and geo.get("lat") is not None and geo.get("lon") is not None:
        place["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": geo["lat"],
            "longitude": geo["lon"],
        }
    country = place_auth.get("country") or "Russia"
    country_ru = place_auth.get("country_ru") or ("Россия" if country == "Russia" else None)
    country_node = {"@type": "Country", "name": country}
    if country_ru:
        country_node["alternateName"] = country_ru
    place["containedInPlace"] = country_node
    same_as = []
    qid = place_auth.get("wikidata")
    if qid:
        same_as.append(_normalize_external_id(qid, "https://www.wikidata.org/wiki/"))
    extra = place_auth.get("sameAs")
    if isinstance(extra, str):
        same_as.append(extra)
    elif isinstance(extra, list):
        same_as.extend(extra)
    same_as = [u for u in same_as if u]
    if same_as:
        place["sameAs"] = list(dict.fromkeys(same_as))
    return place


def organization_structured_data(short_name, org_auth, canonical_path):
    org_auth = org_auth or {}
    org = {
        "@type": "ResearchOrganization",
        "@id": site_url(canonical_path) + "#org",
        "name": short_name,
    }
    alt = _collect_alt_names(
        org_auth.get("name_en") if org_auth.get("name_en") != short_name else None,
        org_auth.get("full_name_ru") if org_auth.get("full_name_ru") != short_name else None,
        org_auth.get("alternateName"),
    )
    if alt:
        org["alternateName"] = alt
    if org_auth.get("url"):
        org["url"] = org_auth["url"]
    same_as = []
    if org_auth.get("wikidata"):
        same_as.append(_normalize_external_id(org_auth["wikidata"], "https://www.wikidata.org/wiki/"))
    if org_auth.get("ror"):
        same_as.append(_normalize_external_id(org_auth["ror"], "https://ror.org/"))
    extra = org_auth.get("sameAs")
    if isinstance(extra, str):
        same_as.append(extra)
    elif isinstance(extra, list):
        same_as.extend(extra)
    same_as = [u for u in same_as if u]
    if same_as:
        org["sameAs"] = list(dict.fromkeys(same_as))
    return org


def json_ld(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return payload.replace("</", "<\\/")


def load_site_data(path="site_data.json"):
    text = Path(path).read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def theme_label(code, lang="en"):
    ru, en = THEME_LABELS.get(code or "unspecified", THEME_LABELS["unspecified"])
    return ru if lang == "ru" else en


def theme_path(code):
    return f"themes/{slugify(code or 'unspecified', 'theme')}.html"


def describe_year_span(first_year, last_year):
    if not first_year and not last_year:
        return "not dated"
    if first_year == last_year:
        return str(first_year)
    return f"{first_year}-{last_year}"


def trim_description(text, limit=155):
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def page_shell(title, description, canonical_path, body, structured_data=None, extra_head="", robots="index, follow", language="ru"):
    canonical = site_url(canonical_path)
    title_html = esc(title)
    desc = trim_description(description)
    desc_html = esc(desc)
    structured = ""
    if structured_data:
        structured = f'\n    <script type="application/ld+json">\n{json_ld(structured_data)}\n    </script>'
    if language == "en":
        nav_items = [
            ("Dashboard", "/IndologyScholars/"),
            ("Scholars", "/IndologyScholars/scholars/"),
            ("Conferences", "/IndologyScholars/conferences/"),
            ("Themes", "/IndologyScholars/themes/"),
            ("Named texts", "/IndologyScholars/topics/"),
            ("Generations", "/IndologyScholars/generations/"),
            ("Meso-levels", "/IndologyScholars/meso/"),
            ("Gumilyov", "/IndologyScholars/gumilyov/"),
            ("Videos", "/IndologyScholars/videos/"),
            ("Findings", "/IndologyScholars/findings/"),
            ("Cities", "/IndologyScholars/cities/"),
            ("Institutions", "/IndologyScholars/institutions/"),
            ("Search", "/IndologyScholars/search.html"),
            ("Data", "/IndologyScholars/download-data.html"),
            ("Quality", "/IndologyScholars/data-quality.html"),
            ("English", "/IndologyScholars/en.html"),
            ("Cite", "/IndologyScholars/how-to-cite.html"),
            ("Metrics", "/IndologyScholars/metrics-guide.html"),
        ]
    else:
        nav_items = [
            ("Панель", "/IndologyScholars/"),
            ("Исследователи", "/IndologyScholars/scholars/"),
            ("Конференции", "/IndologyScholars/conferences/"),
            ("Рубрики", "/IndologyScholars/themes/"),
            ("Сюжеты", "/IndologyScholars/topics/"),
            ("Поколения", "/IndologyScholars/generations/"),
            ("Мезоуровни", "/IndologyScholars/meso/"),
            ("Гумилев", "/IndologyScholars/gumilyov/"),
            ("Видео", "/IndologyScholars/videos/"),
            ("Выводы", "/IndologyScholars/findings/"),
            ("Города", "/IndologyScholars/cities/"),
            ("Институции", "/IndologyScholars/institutions/"),
            ("Поиск", "/IndologyScholars/search.html"),
            ("Данные", "/IndologyScholars/download-data.html"),
            ("Качество", "/IndologyScholars/data-quality.html"),
            ("English", "/IndologyScholars/en.html"),
            ("Цитирование", "/IndologyScholars/how-to-cite.html"),
            ("Метрики", "/IndologyScholars/metrics-guide.html"),
        ]
    nav_html = "\n".join(f'            <a href="{esc(href)}">{esc(label)}</a>' for label, href in nav_items)
    footer_text = (
        f"© 2026 {esc(SITE_NAME)}. Generated from the normalized conference archive."
        if language == "en"
        else f"© 2026 {esc(SITE_NAME)}. Сгенерировано из нормализованного архива конференций."
    )
    html = f"""<!DOCTYPE html>
<html lang="{esc(language)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_html}</title>
    <meta name="description" content="{desc_html}">
    <meta name="robots" content="{esc(robots)}">
    <link rel="canonical" href="{canonical}">
    <link rel="alternate" hreflang="{esc(language)}" href="{canonical}">
    <link rel="alternate" hreflang="x-default" href="{canonical}">
    <link rel="icon" href="/IndologyScholars/assets/favicon.svg" type="image/svg+xml">
    <meta name="theme-color" content="#0a0e1a">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{title_html}">
    <meta property="og:description" content="{desc_html}">
    <meta property="og:image" content="{OG_IMAGE_URL}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title_html}">
    <meta name="twitter:description" content="{desc_html}">
    <meta name="twitter:image" content="{OG_IMAGE_URL}">
    {extra_head}{structured}
    <style>
        :root {{
            color-scheme: dark;
            --bg: #0a0e1a;
            --panel: rgba(17,24,44,0.76);
            --panel-strong: rgba(22,33,61,0.92);
            --border: rgba(255,255,255,0.1);
            --text: #f3f4f6;
            --muted: #a8b0bf;
            --soft: #7d8797;
            --accent: #8b5cf6;
            --accent2: #ec4899;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        a {{ color: #c4b5fd; text-decoration: none; }}
        a:hover {{ color: #f0abfc; }}
        .page {{
            max-width: 1160px;
            margin: 0 auto;
            padding: 2rem;
        }}
        .top-nav {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 2rem;
        }}
        .top-nav a, .chip {{
            border: 1px solid var(--border);
            border-radius: 8px;
            background: rgba(255,255,255,0.04);
            padding: 0.45rem 0.7rem;
            color: var(--muted);
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }}
        header {{
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
            margin-bottom: 1.75rem;
        }}
        h1 {{
            font-size: clamp(2rem, 5vw, 3.4rem);
            line-height: 1.05;
            margin: 0 0 0.75rem;
            letter-spacing: 0;
        }}
        h2 {{
            font-size: 1.45rem;
            margin: 2rem 0 1rem;
            letter-spacing: 0;
        }}
        p {{ color: var(--muted); max-width: 820px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
            gap: 1rem;
        }}
        .card {{
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            background: var(--panel);
        }}
        .card strong {{ color: #fff; }}
        .metric {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #fff;
            margin-top: 0.35rem;
        }}
        .meta {{
            color: var(--soft);
            font-size: 0.92rem;
            margin-top: 0.3rem;
        }}
        .link-block {{
            max-width: 900px;
            margin: 1rem 0;
        }}
        .link-block > strong {{
            color: #fff;
            display: block;
            margin-bottom: 0.45rem;
        }}
        .chip-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }}
        .list {{
            display: grid;
            gap: 0.75rem;
        }}
        .talk {{
            border-left: 3px solid var(--accent);
            background: rgba(255,255,255,0.035);
            padding: 0.8rem 1rem;
            border-radius: 0 8px 8px 0;
        }}
        .footer {{
            color: var(--soft);
            margin-top: 3rem;
            border-top: 1px solid var(--border);
            padding-top: 1rem;
            font-size: 0.9rem;
        }}
        .search-box {{
            width: 100%;
            max-width: 720px;
            padding: 0.8rem 1rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--panel-strong);
            color: var(--text);
            font-size: 1rem;
        }}
        .caveat-block {{
            border: 1px solid rgba(139,92,246,0.35);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            background: rgba(139,92,246,0.07);
            padding: 0.9rem 1.1rem;
            margin: 1.25rem 0 1.75rem;
            max-width: 820px;
        }}
        .caveat-block strong {{
            color: #c4b5fd;
            display: block;
            margin-bottom: 0.35rem;
        }}
        .caveat-block p {{
            font-size: 0.93rem;
            margin: 0;
            color: var(--muted);
        }}
    </style>
</head>
<body>
    <main class="page">
        <nav class="top-nav" aria-label="Primary">
{nav_html}
        </nav>
{body}
        <div class="footer">{footer_text}</div>
    </main>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
