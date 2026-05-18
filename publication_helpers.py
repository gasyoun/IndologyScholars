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

THEME_LABELS = {
    "AcademicHistory": ("История науки и архивы", "History of Scholarship"),
    "Linguistics": ("Лингвистика и филология", "Linguistics & Philology"),
    "Philosophy": ("Философия и религия", "Philosophy & Religion"),
    "Art": ("Искусство и литература", "Art & Literature"),
    "History": ("История и этнография", "History & Ethnography"),
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
        return {"persons": {}, "organizations": {}}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return {
        "persons": payload.get("persons") or {},
        "organizations": payload.get("organizations") or {},
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


def json_ld(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return payload.replace("</", "<\\/")


def load_site_data(path="site_data.js"):
    text = Path(path).read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)


def theme_label(code, lang="en"):
    ru, en = THEME_LABELS.get(code or "History", THEME_LABELS["History"])
    return ru if lang == "ru" else en


def theme_path(code):
    return f"themes/{slugify(code or 'History', 'theme')}.html"


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
    html = f"""<!DOCTYPE html>
<html lang="{esc(language)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_html}</title>
    <meta name="description" content="{desc_html}">
    <meta name="robots" content="{esc(robots)}">
    <link rel="canonical" href="{canonical}">
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
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1rem;
        }}
        .card {{
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            background: var(--panel);
        }}
        .card strong {{ color: #fff; }}
        .meta {{
            color: var(--soft);
            font-size: 0.92rem;
            margin-top: 0.3rem;
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
    </style>
</head>
<body>
    <main class="page">
        <nav class="top-nav" aria-label="Primary">
            <a href="/IndologyScholars/">Dashboard</a>
            <a href="/IndologyScholars/scholars/">Scholars</a>
            <a href="/IndologyScholars/conferences/">Conferences</a>
            <a href="/IndologyScholars/themes/">Themes</a>
            <a href="/IndologyScholars/cities/">Cities</a>
            <a href="/IndologyScholars/institutions/">Institutions</a>
            <a href="/IndologyScholars/search.html">Search</a>
            <a href="/IndologyScholars/download-data.html">Data</a>
            <a href="/IndologyScholars/data-quality.html">Quality</a>
            <a href="/IndologyScholars/en.html">English</a>
            <a href="/IndologyScholars/how-to-cite.html">Cite</a>
        </nav>
{body}
        <div class="footer">© 2026 {esc(SITE_NAME)}. Generated from the normalized conference archive.</div>
    </main>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
