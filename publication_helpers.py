import html
import json
import re
from collections import Counter
from pathlib import Path
import jinja2

from classification_overrides import THEME_LABEL_OVERRIDES

SITE_URL = "https://gasyoun.github.io/IndologyScholars/"
SITE_NAME = "Russian Indological Research Archive"
SITE_NAME_RU = "Российский индологический научный архив"
AUTHOR_NAME = "Dr. Mārcis Gasūns"
OG_IMAGE_PATH = "assets/og-image.png"
OG_IMAGE_URL = SITE_URL + OG_IMAGE_PATH
PUBLIC_IDS_PATH = Path("public_ids.json")
PUBLIC_ID_CSS = ""

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
THEME_LABELS.update(THEME_LABEL_OVERRIDES)

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


def build_presentation_slug_map(records, id_key="presentation_id", title_key="title", max_length=96):
    """Build stable title-based slugs for presentation pages."""
    bases = {}
    for record in records:
        pid = clean_text(record.get(id_key) or "")
        if not pid or pid in bases:
            continue
        fallback = pid.lower().replace("_", "-")
        base = slugify(record.get(title_key) or "", fallback=fallback)
        if len(base) > max_length:
            base = base[:max_length].strip("-") or fallback
        bases[pid] = base

    counts = Counter(bases.values())
    used = set()
    mapping = {}
    for pid in sorted(bases, key=lambda key: (bases[key], key)):
        base = bases[pid]
        suffix = pid.replace("PRES_", "").lower()[-6:] or "talk"
        candidate = base if counts[base] == 1 else f"{base}-{suffix}"
        if len(candidate) > max_length + 7:
            candidate = f"{base[:max_length].strip('-')}-{suffix}"
        dedupe = 2
        while candidate in used:
            candidate = f"{base}-{suffix}-{dedupe}"
            dedupe += 1
        mapping[pid] = candidate
        used.add(candidate)
    return mapping


def assign_public_ids(kind, records, id_key, initial_sort_key, path=PUBLIC_IDS_PATH):
    """Assign compact public IDs once, while retaining retired assignments."""
    target = Path(path)
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
    else:
        payload = {
            "description": (
                "Compact public identifiers assigned once to stable internal records. "
                "Existing assignments are retained when the site is rebuilt."
            ),
            "scholars": {},
            "presentations": {},
        }

    assignments = payload.setdefault(kind, {})
    values = list(assignments.values())
    if any(not isinstance(value, int) or value < 1 for value in values):
        raise ValueError(f"Invalid public ID assignment in {target} for {kind}")
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate public ID assignment in {target} for {kind}")

    next_id = max(values, default=0) + 1
    changed = not target.exists()
    for record in sorted(records, key=initial_sort_key):
        internal_id = clean_text(record.get(id_key) or "")
        if internal_id and internal_id not in assignments:
            assignments[internal_id] = next_id
            next_id += 1
            changed = True

    if changed:
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    return {
        internal_id: assignments[internal_id]
        for internal_id in (clean_text(record.get(id_key) or "") for record in records)
        if internal_id in assignments
    }


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


def _wikipedia_url(value):
    s = str(value or "").strip()
    if re.match(r"^https?://[a-z-]+\.wikipedia\.org/wiki/.+", s):
        return s
    return None


def _vk_url(value):
    s = str(value or "").strip()
    if s.startswith("https://vk.com/") or s.startswith("http://vk.com/"):
        return s
    s = s.lstrip("@")
    if re.match(r"^[A-Za-z0-9_.]+$", s):
        return f"https://vk.com/{s}"
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
    add_valid("wikipedia", "wikipedia", _wikipedia_url)
    add_valid("vk", "vk", _vk_url)
    add_valid("scopus_author_id", "scopus_author_id", _scopus_url)
    add_valid("researcher_id", "researcher_id", _researcher_id_url)
    add_valid("rinc_author_id", "rinc_author_id", _rinc_url)
    add_valid("samskrtam_ru", "samskrtam_ru", _official_url)

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



import os
import textwrap
import urllib.request
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

def get_roboto_font():
    font_path = "assets/Roboto-Bold.ttf"
    if not os.path.exists(font_path):
        os.makedirs("assets", exist_ok=True)
        url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
        urllib.request.urlretrieve(url, font_path)
    return font_path

def create_dynamic_og_image(lines, filepath):
    if Image is None:
        return # Fallback if Pillow fails
    if os.path.exists(filepath):
        return
        
    width, height = 1200, 630
    bg_color = (15, 23, 42) # #0f172a
    text_color = (255, 255, 255)
    accent_color = (136, 192, 208)
    
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    font_path = get_roboto_font()
    
    try:
        font_large = ImageFont.truetype(font_path, 80)
        font_small = ImageFont.truetype(font_path, 48)
        font_tiny = ImageFont.truetype(font_path, 36)
    except Exception:
        font_large = font_small = font_tiny = ImageFont.load_default()
        
    y = 120
    margin = 80
    
    main_text = lines[0]
    wrapped_main = textwrap.wrap(main_text, width=28)
    if len(wrapped_main) > 3:
        wrapped_main = wrapped_main[:2] + [wrapped_main[2] + "..."]
        
    for line in wrapped_main:
        draw.text((margin, y), line, font=font_large, fill=text_color)
        y += 100
        
    y += 40
    for line in lines[1:]:
        draw.text((margin, y), line, font=font_small, fill=accent_color)
        y += 70
        
    draw.text((margin, height - 80), "Российский индологический научный архив", font=font_tiny, fill=(100, 116, 139))
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath)



def trim_description(text, limit=155):
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


_JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
_BASE_TEMPLATE = None

def page_shell(title, description, canonical_path, body, structured_data=None, extra_head="", robots="index, follow", language="ru", custom_og_image=None):
    global _BASE_TEMPLATE
    if _BASE_TEMPLATE is None:
        try:
            _BASE_TEMPLATE = _JINJA_ENV.get_template("base.html")
        except Exception:
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(Path(__file__).parent / "templates")))
            _BASE_TEMPLATE = env.get_template("base.html")
            
    canonical = site_url(canonical_path)
    desc = trim_description(description)
    
    if language == "en":
        nav_items = [
            ("Archive", "/IndologyScholars/"),
            ("Search", "/IndologyScholars/search.html"),
            ("Scholars", "/IndologyScholars/s/"),
            ("Papers", "/IndologyScholars/p/"),
            ("Conferences", "/IndologyScholars/conferences/"),
            ("Themes", "/IndologyScholars/themes/"),
            ("Generations", "/IndologyScholars/generations/"),
        ]
        more_label = "More"
        more_nav_items = [
            ("Findings", "/IndologyScholars/findings/"),
            ("Visualizations", "/IndologyScholars/findings/visualisations.html"),
            ("Named texts", "/IndologyScholars/topics/"),
            ("Data", "/IndologyScholars/download-data.html"),
            ("Meso-levels", "/IndologyScholars/meso/"),
            ("Keywords", "/IndologyScholars/keywords/"),
            ("Gumilyov", "/IndologyScholars/gumilyov/"),
            ("Criteria", "/IndologyScholars/classification-criteria.html"),
            ("Videos", "/IndologyScholars/videos/"),
            ("Cities", "/IndologyScholars/cities/"),
            ("Institutions", "/IndologyScholars/institutions/"),
            ("Collaboration", "/IndologyScholars/collaboration/"),
            ("NLP Analysis", "/IndologyScholars/nlp/"),
            ("Quality", "/IndologyScholars/data-quality.html"),
            ("English", "/IndologyScholars/en.html"),
            ("Cite", "/IndologyScholars/how-to-cite.html"),
            ("Metrics", "/IndologyScholars/metrics-guide.html"),
        ]
    else:
        nav_items = [
            ("Архив", "/IndologyScholars/"),
            ("Поиск", "/IndologyScholars/search.html"),
            ("Исследователи", "/IndologyScholars/s/"),
            ("Доклады", "/IndologyScholars/p/"),
            ("Конференции", "/IndologyScholars/conferences/"),
            ("Рубрики", "/IndologyScholars/themes/"),
            ("Поколения", "/IndologyScholars/generations/"),
        ]
        more_label = "Еще"
        more_nav_items = [
            ("Выводы", "/IndologyScholars/findings/"),
            ("Визуализации", "/IndologyScholars/findings/visualisations.html"),
            ("Сюжеты", "/IndologyScholars/topics/"),
            ("Данные", "/IndologyScholars/download-data.html"),
            ("Мезоуровни", "/IndologyScholars/meso/"),
            ("Ключевые слова", "/IndologyScholars/keywords/"),
            ("Гумилев", "/IndologyScholars/gumilyov/"),
            ("Критерии", "/IndologyScholars/classification-criteria.html"),
            ("Видео", "/IndologyScholars/videos/"),
            ("Города", "/IndologyScholars/cities/"),
            ("Институции", "/IndologyScholars/institutions/"),
            ("Коллаборация", "/IndologyScholars/collaboration/"),
            ("NLP-анализ", "/IndologyScholars/nlp/"),
            ("Качество", "/IndologyScholars/data-quality.html"),
            ("English", "/IndologyScholars/en.html"),
            ("Цитирование", "/IndologyScholars/how-to-cite.html"),
            ("Метрики", "/IndologyScholars/metrics-guide.html"),
        ]
        
    footer_text = (
        f"© 2026 {SITE_NAME}. Generated from the normalized conference archive."
        if language == "en"
        else f"© 2026 {SITE_NAME}. Сгенерировано из нормализованного архива конференций."
    )
    
    structured_data_json = ""
    if structured_data:
        structured_data_json = json_ld(structured_data)
        
    html = _BASE_TEMPLATE.render(
        language=language,
        title=title,
        description=desc,
        robots=robots,
        canonical=canonical,
        og_image_url=site_url(custom_og_image) if custom_og_image else OG_IMAGE_URL,
        extra_head=extra_head,
        structured_data_json=structured_data_json,
        nav_items=nav_items,
        more_label=more_label,
        more_nav_items=more_nav_items,
        body=body,
        footer_text=footer_text
    )
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
