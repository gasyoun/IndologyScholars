import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from publication_helpers import (
    AUTHOR_NAME,
    SITE_NAME,
    SITE_URL,
    clean_text,
    describe_year_span,
    esc,
    load_site_data,
    page_shell,
    site_url,
    slugify,
    theme_label,
    theme_path,
    clean_person_urls,
    is_public_authority_record,
)


OUTPUT_DIR = Path("scholars")
AUTHORITY_PATH = Path("authority_ids.json")
LEGACY_REDIRECTS_PATH = Path("legacy_redirects.json")
SLUG_REDIRECTS_PATH = Path("slug_redirects.json")
BUILD_DATE = dt.date.today().isoformat()


def conference_path(series, year):
    key = "zograf" if "Zograf" in (series or "") else "roerich"
    return f"conferences/{key}-{year}.html"


def city_path(city):
    return f"cities/{slugify(city, 'city')}.html"


def dashboard_search_href(query):
    return f"../index.html?search={quote(clean_text(query))}"


def load_authority_ids():
    if not AUTHORITY_PATH.exists():
        return {"persons": {}, "organizations": {}}
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def load_legacy_redirects():
    if not LEGACY_REDIRECTS_PATH.exists():
        return {}
    return json.loads(LEGACY_REDIRECTS_PATH.read_text(encoding="utf-8")).get("redirects", {})


def load_slug_redirects():
    if not SLUG_REDIRECTS_PATH.exists():
        return {}
    return json.loads(SLUG_REDIRECTS_PATH.read_text(encoding="utf-8"))


def good_city(city):
    return city and city not in ("Не указана", "Not specified")


def format_lifespan(scholar, lang="ru"):
    birth = scholar.get("birth_year")
    death = scholar.get("death_year")
    if birth and death:
        return f" ({birth}-{death})"
    if birth:
        return f" (род. {birth})" if lang == "ru" else f" (b. {birth})"
    return ""


def scholar_description(scholar):
    name = scholar.get("full_name_ru") or scholar.get("name")
    total = scholar.get("total_talks", 0)
    years = describe_year_span(scholar.get("first_year"), scholar.get("last_year"))
    theme = theme_label(scholar.get("dominant_theme"), "ru")
    return f"{name}: {total} докладов в архиве Зографских и Рериховских чтений, период активности {years}, основной профиль: {theme}."


def unique_affiliations(scholar, limit=16):
    values = []
    seen = set()
    for value in scholar.get("all_affiliations") or []:
        key = clean_text(value).lower()
        if key and key not in seen:
            seen.add(key)
            values.append(value)
    return values[:limit]


def unique_cities(scholar):
    values = []
    seen = set()
    for talk in scholar.get("talks", []):
        city = (talk.get("geography") or {}).get("ru")
        if good_city(city) and city not in seen:
            seen.add(city)
            values.append(city)
    return values


def chip_links(items, href_factory, class_name="chip"):
    if not items:
        return '<span class="meta">No records</span>'
    return "".join(f'<a class="{class_name}" href="{href_factory(item)}">{esc(item)}</a>' for item in items)


def talk_card(talk):
    theme = talk.get("theme") or {}
    theme_code = theme.get("code", "History")
    city = (talk.get("geography") or {}).get("ru")
    city_html = ""
    if good_city(city):
        city_html = f' · <a href="../{city_path(city)}">{esc(city)}</a>'
    videos = talk.get("videos") or []
    video_html = ""
    if videos:
        links = " · ".join(
            f'<a href="{esc(v["url"])}" rel="noopener" target="_blank">▶ YouTube</a>'
            for v in videos
        )
        video_html = f'<div class="meta">{links}</div>'
    return f"""
        <article class="talk">
            <strong>{esc(talk.get("title"))}</strong>
            <div class="meta">
                <a href="../{conference_path(talk.get("series"), talk.get("year"))}">{esc(talk.get("series"))} {esc(talk.get("year"))}</a>
                · <a href="../{theme_path(theme_code)}">{esc(theme_label(theme_code))}</a>{city_html}
            </div>
            <div class="meta">{esc(talk.get("date"))} · {esc((talk.get("day_of_week") or {}).get("ru"))} · {esc(talk.get("time_interval"))}</div>
            <div class="meta">{esc(talk.get("session_title") or "Секция не указана")}</div>
            {video_html}
        </article>
    """


def related_scholars(scholar, scholars_by_theme, scholars_by_city):
    candidate_ids = []
    theme = scholar.get("dominant_theme")
    if theme:
        candidate_ids.extend(scholars_by_theme.get(theme, []))
    for city in unique_cities(scholar):
        candidate_ids.extend(scholars_by_city.get(city, []))

    seen = set()
    related = []
    for candidate in candidate_ids:
        if candidate["id"] == scholar["id"] or candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        related.append(candidate)
    related.sort(key=lambda item: (-item.get("total_talks", 0), item.get("full_name_ru") or item.get("name")))
    return related[:8]


def profile_structured_data(scholar, authority):
    path = f"scholars/{scholar['url_slug']}.html"
    name_ru = scholar.get("full_name_ru") or scholar.get("name")
    name_en = scholar.get("full_name_en") or scholar.get("name")
    same_as = []
    person_authority = (authority.get("persons") or {}).get(scholar["id"], {})
    
    if is_public_authority_record(person_authority):
        urls_dict = clean_person_urls(person_authority)
        for key in ("orcid", "wikidata", "viaf", "openalex", "google_scholar", "official_url", "scopus_author_id", "researcher_id", "rinc_author_id"):
            val = urls_dict.get(key)
            if val:
                same_as.append(val)

    person = {
        "@type": "Person",
        "@id": site_url(path) + "#person",
        "identifier": scholar["id"],
        "name": name_en or name_ru,
        "alternateName": [value for value in [name_ru, name_en, scholar.get("name"), scholar.get("original_fullname")] if value],
        "description": scholar_description(scholar),
        "knowsAbout": [theme_label(scholar.get("dominant_theme")), theme_label(scholar.get("dominant_theme"), "ru")],
        "affiliation": [{"@type": "Organization", "name": aff} for aff in unique_affiliations(scholar, limit=8)],
    }
    if scholar.get("birth_year"):
        person["birthDate"] = str(scholar["birth_year"])
    if scholar.get("death_year"):
        person["deathDate"] = str(scholar["death_year"])
    if same_as:
        person["sameAs"] = same_as

    return [
        {
            "@context": "https://schema.org",
            "@type": "ProfilePage",
            "name": f"{name_ru} | {SITE_NAME}",
            "description": scholar_description(scholar),
            "url": site_url(path),
            "dateModified": BUILD_DATE,
            "mainEntity": person,
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
                {"@type": "ListItem", "position": 2, "name": "Scholars", "item": site_url("scholars/")},
                {"@type": "ListItem", "position": 3, "name": name_ru, "item": site_url(path)},
            ],
        },
    ]


def build_indexes(scholars):
    by_theme = defaultdict(list)
    by_city = defaultdict(list)
    for scholar in scholars:
        if scholar.get("dominant_theme"):
            by_theme[scholar["dominant_theme"]].append(scholar)
        for city in unique_cities(scholar):
            by_city[city].append(scholar)
    return by_theme, by_city


def render_profile(scholar, related, authority):
    name_ru = scholar.get("full_name_ru") or scholar.get("name")
    name_en = scholar.get("full_name_en") or scholar.get("name")
    description = scholar_description(scholar)
    path = f"scholars/{scholar['url_slug']}.html"
    theme_code = scholar.get("dominant_theme") or "History"
    cities = unique_cities(scholar)
    affiliations = unique_affiliations(scholar)

    related_html = "".join(
        f'<article class="card"><strong><a href="{item["url_slug"]}.html">{esc(item.get("full_name_ru") or item.get("name"))}</a></strong><div class="meta">{esc(item.get("total_talks"))} talks · {esc(theme_label(item.get("dominant_theme")))}</div></article>'
        for item in related
    ) or '<p class="meta">No related scholars found in this generated index.</p>'

    status = []
    if scholar.get("is_student"):
        status.append("Student / postgraduate")
    if scholar.get("is_independent"):
        status.append("Independent researcher")

    person_authority = (authority.get("persons") or {}).get(scholar["id"], {})

    external_links_html = ""
    if is_public_authority_record(person_authority):
        urls_dict = clean_person_urls(person_authority)
        if urls_dict:
            links = []
            labels = {
                "orcid": "ORCID",
                "wikidata": "Wikidata",
                "viaf": "VIAF",
                "openalex": "OpenAlex",
                "google_scholar": "Google Scholar",
                "official_url": "Official profile",
                "scopus_author_id": "Scopus",
                "researcher_id": "ResearcherID",
                "rinc_author_id": "РИНЦ / eLIBRARY"
            }
            for key, label in labels.items():
                url = urls_dict.get(key)
                if url:
                    links.append(f'<a class="chip" href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>')
            if links:
                external_links_html = f"""
        <h2>External Identifiers</h2>
        <div class="chip-row">{''.join(links)}</div>"""

    body = f"""
        <header>
            <h1>{esc(name_ru)}<span class="life">{esc(format_lifespan(scholar, "ru"))}</span></h1>
            <p>{esc(name_en)}{esc(format_lifespan(scholar, "en"))}</p>
            <p>{esc(description)}</p>
        </header>

        <section class="grid">
            <article class="card"><strong>Talks</strong><div class="metric">{esc(scholar.get("total_talks"))}</div><div class="meta">Presentation records</div></article>
            <article class="card"><strong>Activity</strong><div class="metric">{esc(describe_year_span(scholar.get("first_year"), scholar.get("last_year")))}</div><div class="meta">Observed conference years</div></article>
            <article class="card"><strong>Theme</strong><div class="metric"><a href="../{theme_path(theme_code)}">{esc(theme_label(theme_code))}</a></div><div class="meta">{esc(theme_label(theme_code, "ru"))}</div></article>
            <article class="card"><strong>Conference split</strong><div class="meta">Zograf: {esc(scholar.get("zograf_talks"))} · Roerich: {esc(scholar.get("roerich_talks"))}</div></article>
        </section>

        <h2>Affiliations</h2>
        <div class="chip-row">{chip_links(affiliations, dashboard_search_href)}</div>

        <h2>Geographic Centers</h2>
        <div class="chip-row">{chip_links(cities, lambda city: '../' + city_path(city))}</div>

        <h2>Status Tags</h2>
        <div class="chip-row">{''.join(f'<span class="chip">{esc(item)}</span>' for item in status) or '<span class="meta">No special status tags.</span>'}</div>{external_links_html}

        <h2>Presentations</h2>
        <section class="list">{''.join(talk_card(talk) for talk in scholar.get("talks", []))}</section>

        <h2>Related Scholars</h2>
        <section class="grid">{related_html}</section>
    """

    extra_css = """
    <style>
        .life { color: var(--soft); font-size: 0.62em; font-weight: 500; margin-left: 0.4rem; }
        .metric { font-size: 1.4rem; font-weight: 700; margin-top: 0.2rem; }
        .chip-row { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    </style>
    """
    return page_shell(
        f"{name_ru} | {SITE_NAME}",
        description,
        path,
        body,
        profile_structured_data(scholar, authority),
        extra_head=extra_css,
    )


def render_scholars_index(scholars):
    cards = []
    for scholar in sorted(scholars, key=lambda item: item.get("full_name_ru") or item.get("name")):
        name = scholar.get("full_name_ru") or scholar.get("name")
        years = describe_year_span(scholar.get("first_year"), scholar.get("last_year"))
        cards.append(
            f'<article class="card"><strong><a href="{scholar["url_slug"]}.html">{esc(name)}</a></strong>'
            f'<div class="meta">{esc(scholar.get("total_talks"))} talks · {esc(years)} · {esc(theme_label(scholar.get("dominant_theme")))}</div></article>'
        )
    body = f"""
        <header>
            <h1>Scholar Profiles</h1>
            <p>Static index of generated scholar profile pages for the Indology Scholars archive.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    structured = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Scholar Profiles",
            "description": "Static index of generated scholar profile pages.",
            "url": site_url("scholars/"),
            "dateModified": BUILD_DATE,
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
                {"@type": "ListItem", "position": 2, "name": "Scholars", "item": site_url("scholars/")},
            ],
        },
    ]
    return page_shell(
        f"Scholar Profiles | {SITE_NAME}",
        "Static index of generated scholar profile pages for the Indology Scholars archive.",
        "scholars/",
        body,
        structured,
    )


def render_legacy_redirect(legacy_id, target_scholar):
    target_slug = target_scholar["url_slug"]
    target_href = f"{target_slug}.html"
    target_url = site_url(f"scholars/{target_slug}.html")
    name = target_scholar.get("full_name_ru") or target_scholar.get("name")
    title = f"{clean_text(name)} moved | {SITE_NAME}"
    description = f"Legacy profile URL for {clean_text(name)}. The canonical profile is {target_url}."
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(description)}">
    <meta name="robots" content="noindex,follow">
    <link rel="canonical" href="{esc(target_url)}">
    <meta http-equiv="refresh" content="0; url={esc(target_href)}">
    <script>window.location.replace("{esc(target_href)}");</script>
</head>
<body data-legacy-redirect="{esc(legacy_id)}">
    <p><a href="{esc(target_href)}">{esc(name)}</a></p>
</body>
</html>
"""


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    data = load_site_data("site_data.json")
    scholars = data.get("scholars", [])
    by_theme, by_city = build_indexes(scholars)
    authority = load_authority_ids()
    legacy_redirects = load_legacy_redirects()
    slug_redirects = load_slug_redirects()
    scholars_by_id = {scholar["id"]: scholar for scholar in scholars}

    written_files = {"index.html"}
    generated_slugs = set()
    for scholar in scholars:
        slug = scholar["url_slug"]
        generated_slugs.add(slug)
        related = related_scholars(scholar, by_theme, by_city)
        html = render_profile(scholar, related, authority)
        canonical_filename = f"{slug}.html"
        (OUTPUT_DIR / canonical_filename).write_text(html, encoding="utf-8", newline="\n")
        written_files.add(canonical_filename)

        # Redirect from the legacy PERS_<hash>.html path to the new slug-based canonical.
        pers_filename = f"{scholar['id']}.html"
        if pers_filename != canonical_filename:
            redirect_html = render_legacy_redirect(scholar["id"], scholar)
            (OUTPUT_DIR / pers_filename).write_text(redirect_html, encoding="utf-8", newline="\n")
            written_files.add(pers_filename)

    for legacy_id, target_id in legacy_redirects.items():
        target_scholar = scholars_by_id.get(target_id)
        if not target_scholar:
            raise ValueError(f"Legacy redirect {legacy_id} points to missing scholar {target_id}")
        if legacy_id == target_scholar["url_slug"]:
            continue  # Would self-redirect; canonical already written above.
        legacy_filename = f"{legacy_id}.html"
        html = render_legacy_redirect(legacy_id, target_scholar)
        (OUTPUT_DIR / legacy_filename).write_text(html, encoding="utf-8", newline="\n")
        written_files.add(legacy_filename)

    # Slug-rename redirects: old published slug → new canonical slug.
    for old_slug, target_id in slug_redirects.items():
        target_scholar = scholars_by_id.get(target_id)
        if not target_scholar:
            continue
        if old_slug == target_scholar["url_slug"]:
            continue  # Already the canonical slug; no redirect needed.
        old_filename = f"{old_slug}.html"
        html = render_legacy_redirect(old_slug, target_scholar)
        (OUTPUT_DIR / old_filename).write_text(html, encoding="utf-8", newline="\n")
        written_files.add(old_filename)

    for stale in OUTPUT_DIR.glob("*.html"):
        if stale.name not in written_files:
            stale.unlink()

    (OUTPUT_DIR / "index.html").write_text(render_scholars_index(scholars), encoding="utf-8", newline="\n")

    print(
        f"Successfully generated {len(generated_slugs)} canonical scholar profile pages "
        f"in '{OUTPUT_DIR}/' (plus PERS_<hash> redirects, {len(legacy_redirects)} legacy redirects, "
        f"and {len(slug_redirects)} slug-rename redirects)."
    )


if __name__ == "__main__":
    main()
