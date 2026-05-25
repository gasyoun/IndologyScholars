import csv
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
    normalize_time_interval,
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

SCHOLAR_PROFILE_OVERRIDES = {
    "PERS_829c1de5": {
        "label": "Сравнительная мифология и эпос",
        "theme_code": "literature_and_poetry",
        "note": "Эпический и сравнительно-мифологический контур: «Махабхарата», паломничество, фольклорные мотивы и межкультурные параллели.",
    }
}


CITY_LINK_ALIASES = {
    "спб": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
    "москва": "Москва",
    "пенза": "Пенза",
    "казань": "Казань",
    "краснодар": "Краснодар",
    "обнинск": "Обнинск",
    "новосибирск": "Новосибирск",
    "улан-удэ": "Улан-Удэ",
    "элиста": "Элиста",
    "вильнюс": "Вильнюс",
    "дели": "Дели",
    "нижний новгород": "Нижний Новгород",
}


def conference_path(series, year):
    key = "zograf" if "Zograf" in (series or "") else "roerich"
    return f"conferences/{key}-{year}.html"


def series_label(series):
    return "Зографские чтения" if "Zograf" in (series or "") else "Рериховские чтения"


def ru_plural(number, one, few, many):
    value = abs(int(number))
    if 11 <= value % 100 <= 14:
        return many
    if value % 10 == 1:
        return one
    if 2 <= value % 10 <= 4:
        return few
    return many


def talks_count_label(count):
    return f"{count} {ru_plural(count, 'доклад', 'доклада', 'докладов')}"


def city_path(city):
    return f"cities/{slugify(city, 'city')}.html"


def institution_path(name):
    return f"institutions/{slugify(name, 'institution')}.html"


def dashboard_search_href(query):
    return f"../index.html?search={quote(clean_text(query))}"


def search_href(query):
    return f"../search.html?q={quote(clean_text(query))}"


def load_csv_rows(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def meso_path(code):
    return f"meso/{slugify(code, 'meso')}.html"


def title_case_ru(label):
    label = clean_text(label)
    return label[:1].upper() + label[1:] if label else ""


def load_meso_context():
    meso_items = {}
    meso_by_presentation = defaultdict(list)

    for row in load_csv_rows("article/hypothesis_output/title_keyword_microseries.csv"):
        code = clean_text(row.get("microseries") or "")
        if code:
            meso_items[code] = {
                "label": clean_text(row.get("label") or code),
                "kind": "Мини-серия",
            }

    for row in load_csv_rows("article/hypothesis_output/title_keyword_linguistics_subfields.csv"):
        approach = clean_text(row.get("approach") or "")
        if approach:
            code = f"linguistics_{approach}"
            meso_items[code] = {
                "label": title_case_ru(row.get("label") or approach),
                "kind": "Подраздел рубрики «Лингвистика и филология»",
            }

    for row in load_csv_rows("article/hypothesis_output/title_keyword_microseries_titles.csv"):
        code = clean_text(row.get("microseries") or "")
        pid = clean_text(row.get("presentation_id") or "")
        if code and pid:
            meso_by_presentation[pid].append(code)

    for row in load_csv_rows("article/hypothesis_output/title_keyword_linguistics_subfield_titles.csv"):
        approach = clean_text(row.get("approach") or "")
        pid = clean_text(row.get("presentation_id") or "")
        if approach and pid:
            meso_by_presentation[pid].append(f"linguistics_{approach}")

    return meso_items, meso_by_presentation


def series_participation_line(scholar, name_ru, label, count_key, first_key, last_key):
    count = int(scholar.get(count_key) or 0)
    href = search_href((name_ru or "") + " " + label)
    if not count:
        return f'<div class="series-line"><a href="{esc(href)}">{esc(label)}</a>: не участвовал</div>'
    years = describe_year_span(scholar.get(first_key), scholar.get(last_key))
    return f'<div class="series-line"><a href="{esc(href)}">{esc(label)}</a>: {esc(talks_count_label(count))} · {esc(years)}</div>'


def normalize_affiliation_link_label(aff):
    value = clean_text(aff).lower()
    if "ивр" in value or "восточных рукописей" in value:
        return "ИВР РАН"
    if "ив ран" in value or "востоковедения ран" in value:
        return "ИВ РАН"
    if "спбгу" in value or "петербургский" in value:
        return "СПбГУ"
    if "мгу" in value or "ломоносова" in value:
        return "МГУ"
    if "вшэ" in value or "высшая школа" in value:
        return "НИУ ВШЭ"
    if "рггу" in value or "гуманитарный" in value:
        return "РГГУ"
    if "маэ" in value or "кунсткамер" in value:
        return "МАЭ РАН"
    if "эрмитаж" in value:
        return "Государственный Эрмитаж"
    if "институт философии" in value or "иф ран" in value:
        return "ИФ РАН"
    if "независим" in value or "independent" in value:
        return "Независимые исследователи"
    return None


def affiliation_href(value):
    institution = normalize_affiliation_link_label(value)
    if institution:
        return "../" + institution_path(institution)
    city = CITY_LINK_ALIASES.get(clean_text(value).lower())
    if city:
        return "../" + city_path(city)
    return dashboard_search_href(value)


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
        return f" ({birth}–{death})"
    if birth:
        return f" (род. {birth})" if lang == "ru" else f" (b. {birth})"
    return ""


def format_degree(scholar):
    """Russian academic degree line with year and source link (empty if none)."""
    degree = clean_text(scholar.get("degree") or "")
    if not degree:
        return ""
    text = esc(degree)
    year = clean_text(str(scholar.get("degree_year") or ""))
    if year:
        text += f", {esc(year)}"
    url = clean_text(scholar.get("degree_source_url") or "")
    if url:
        text += f' · <a href="{esc(url)}" target="_blank" rel="noopener">источник</a>'
    return f'<p class="degree">{text}</p>'


def scholar_profile_meta(scholar):
    override = SCHOLAR_PROFILE_OVERRIDES.get(scholar.get("id"))
    if override:
        return override["label"], override.get("theme_code") or scholar.get("dominant_theme") or "History", override.get("note", "")
    theme_code = scholar.get("dominant_theme") or "History"
    return theme_label(theme_code, "ru"), theme_code, ""


def scholar_description(scholar):
    name = scholar.get("full_name_ru") or scholar.get("name")
    total = scholar.get("total_talks", 0)
    years = describe_year_span(scholar.get("first_year"), scholar.get("last_year"))
    theme, _, _ = scholar_profile_meta(scholar)
    return f"{name}: {talks_count_label(total)} в архиве Зографских и Рериховских чтений, период активности {years}, основной профиль: {theme}."


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
        return '<span class="meta">Нет данных</span>'
    return "".join(f'<a class="{class_name}" href="{href_factory(item)}">{esc(item)}</a>' for item in items)


GENERIC_TAGS = {
    "индия",
    "индийский",
    "древний",
    "средневековый",
    "современный",
    "текст",
    "литература",
    "москва",
    "новый",
    "петербург",
    "санкт",
    "старый",
    "тема",
    "форма",
}

PUBLIC_KEYWORD_LABELS = {
    "рамаян": "Рамаяна",
    "махабхарат": "Махабхарата",
    "южная_индия": "Южная Индия",
}


def public_keyword_label(keyword):
    return PUBLIC_KEYWORD_LABELS.get(clean_text(keyword).lower(), keyword)


def talk_meso_codes(talk, meso_by_presentation):
    pid = clean_text(talk.get("presentation_id") or "")
    return list(dict.fromkeys(meso_by_presentation.get(pid, [])))


def meso_label(code, meso_items):
    return (meso_items.get(code) or {}).get("label") or code.replace("_", " ")


def linked_meso_chip(code, meso_items, prefix="../", class_name="mini-chip"):
    href = prefix + meso_path(code)
    return f'<a class="{class_name}" href="{esc(href)}">{esc(meso_label(code, meso_items))}</a>'


def linked_keyword_chip(keyword, class_name="mini-chip"):
    return f'<a class="{class_name}" href="{esc(search_href(keyword))}">{esc(public_keyword_label(keyword))}</a>'


def clean_tags(talk):
    values = []
    seen = set()
    for tag in talk.get("tags") or []:
        value = clean_text(tag).lower()
        if len(value) < 3 or value in GENERIC_TAGS or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def scholar_context(scholar, meso_by_presentation):
    meso = set()
    tags = set()
    themes = set()
    cities = set(unique_cities(scholar))
    conference_years = set()
    for talk in scholar.get("talks", []):
        meso.update(talk_meso_codes(talk, meso_by_presentation))
        tags.update(clean_tags(talk))
        theme_code = (talk.get("theme") or {}).get("code")
        if theme_code and theme_code != "unspecified":
            themes.add(theme_code)
        year = talk.get("year")
        series = series_label(talk.get("series"))
        if year and series:
            conference_years.add(f"{series} {year}")
    return {
        "meso": meso,
        "tags": tags,
        "themes": themes,
        "cities": cities,
        "conference_years": conference_years,
    }


def relation_reasons(base_context, candidate_context, meso_items, limit=3):
    reasons = []
    common_meso = sorted(
        base_context["meso"] & candidate_context["meso"],
        key=lambda code: meso_label(code, meso_items),
    )
    if common_meso:
        labels = ", ".join(meso_label(code, meso_items) for code in common_meso[:2])
        reasons.append(f"общие мезоуровни: {labels}")

    common_tags = sorted(base_context["tags"] & candidate_context["tags"])
    if common_tags:
        reasons.append(f"общие ключевые слова: {', '.join(common_tags[:3])}")

    common_conferences = sorted(base_context["conference_years"] & candidate_context["conference_years"])
    if common_conferences:
        reasons.append(f"та же площадка/год: {', '.join(common_conferences[:2])}")

    common_themes = sorted(base_context["themes"] & candidate_context["themes"])
    if common_themes:
        reasons.append(f"общая рубрика: {', '.join(theme_label(code, 'ru') for code in common_themes[:2])}")

    common_cities = sorted(base_context["cities"] & candidate_context["cities"])
    if common_cities:
        reasons.append(f"общий центр: {', '.join(common_cities[:2])}")

    return reasons[:limit]


def related_scholars(scholar, scholars, meso_by_presentation, meso_items):
    base_context = scholar_context(scholar, meso_by_presentation)
    scored = []
    for candidate in scholars:
        if candidate["id"] == scholar["id"]:
            continue
        candidate_context = scholar_context(candidate, meso_by_presentation)
        common_meso = base_context["meso"] & candidate_context["meso"]
        common_tags = base_context["tags"] & candidate_context["tags"]
        common_themes = base_context["themes"] & candidate_context["themes"]
        common_cities = base_context["cities"] & candidate_context["cities"]
        common_conferences = base_context["conference_years"] & candidate_context["conference_years"]
        score = (
            len(common_meso) * 10
            + len(common_conferences) * 5
            + len(common_tags) * 3
            + len(common_themes) * 2
            + len(common_cities)
        )
        if score <= 0:
            continue
        scored.append(
            {
                "scholar": candidate,
                "score": score,
                "reasons": relation_reasons(base_context, candidate_context, meso_items),
            }
        )
    scored.sort(
        key=lambda item: (
            -item["score"],
            -(item["scholar"].get("total_talks") or 0),
            item["scholar"].get("full_name_ru") or item["scholar"].get("name"),
        )
    )
    return scored[:8]


def talk_context_html(talk, meso_by_presentation, meso_items):
    meso_codes = talk_meso_codes(talk, meso_by_presentation)
    tags = clean_tags(talk)
    parts = []
    if meso_codes:
        meso_links = "".join(linked_meso_chip(code, meso_items) for code in meso_codes[:4])
        parts.append(f'<span class="context-label">Срезы:</span> {meso_links}')
    if tags:
        tag_links = "".join(linked_keyword_chip(tag) for tag in tags[:4])
        parts.append(f'<span class="context-label">Ключевые слова:</span> {tag_links}')
    if not parts:
        return ""
    return f'<div class="meta talk-context">{" ".join(parts)}</div>'


def talk_card(talk, meso_by_presentation=None, meso_items=None):
    meso_by_presentation = meso_by_presentation or {}
    meso_items = meso_items or {}
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
    time_interval = normalize_time_interval(talk.get("time_interval"), "Не указано")
    talk_time = f'{esc(talk.get("date"))} · {esc((talk.get("day_of_week") or {}).get("ru"))} · {esc(time_interval)}'
    raw_session = clean_text(talk.get("session_title") or "")
    if raw_session.strip(" .").lower() in {"", "перерыв"}:
        raw_session = "Секция не указана"
    session = esc(raw_session)
    pid = clean_text(talk.get("presentation_id") or "")
    anchor_attr = f' id="{esc(pid)}"' if pid else ""
    title_href = f'../{conference_path(talk.get("series"), talk.get("year"))}'
    if pid:
        title_href = f"{title_href}#{pid}"
    return f"""
        <article class="talk"{anchor_attr}>
            <strong><a href="{esc(title_href)}">{esc(talk.get("title"))}</a></strong>
            <div class="meta">
                <a href="../{conference_path(talk.get("series"), talk.get("year"))}">{esc(series_label(talk.get("series")))} {esc(talk.get("year"))}</a>
                · <a href="../{theme_path(theme_code)}">{esc(theme_label(theme_code, "ru"))}</a>{city_html}
            </div>
            <div class="meta talk-meta-row"><span>{talk_time}</span><span class="talk-meta-session">{session}</span></div>
            {talk_context_html(talk, meso_by_presentation, meso_items)}
            {video_html}
        </article>
    """


def scholar_meso_counts(scholar, meso_by_presentation):
    counts = defaultdict(int)
    for talk in scholar.get("talks", []):
        for code in talk_meso_codes(talk, meso_by_presentation):
            counts[code] += 1
    return counts


def scholar_keyword_counts(scholar):
    counts = defaultdict(int)
    for talk in scholar.get("talks", []):
        for tag in clean_tags(talk):
            counts[tag] += 1
    return counts


def scholar_context_block(scholar, meso_by_presentation, meso_items):
    meso_counts = scholar_meso_counts(scholar, meso_by_presentation)
    keyword_counts = scholar_keyword_counts(scholar)
    meso_links = []
    for code, count in sorted(meso_counts.items(), key=lambda item: (-item[1], meso_label(item[0], meso_items)))[:8]:
        href = "../" + meso_path(code)
        meso_links.append(
            f'<a class="chip" href="{esc(href)}">{esc(meso_label(code, meso_items))} · {esc(talks_count_label(count))}</a>'
        )
    keyword_links = []
    for keyword, count in sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))[:10]:
        display_keyword = public_keyword_label(keyword)
        label = f"{display_keyword} · {count}" if count > 1 else display_keyword
        keyword_links.append(f'<a class="chip" href="{esc(search_href(keyword))}">{esc(label)}</a>')

    rows = []
    if meso_links:
        rows.append(f'<div><strong>Мезоуровни</strong><div class="chip-row">{"".join(meso_links)}</div></div>')
    if keyword_links:
        rows.append(f'<div><strong>Ключевые слова</strong><div class="chip-row">{"".join(keyword_links)}</div></div>')
    if not rows:
        rows.append('<p class="meta">Для этого профиля пока нет устойчивых мезоуровней или ключевых контуров.</p>')
    return f"""
        <h2>Мезоуровни и ключевые контуры</h2>
        <section class="context-block">{''.join(rows)}</section>
    """


def archive_records_label(count):
    return f"{ru_plural(count, 'запись', 'записи', 'записей')} в архиве"


def activity_label(scholar):
    first_year = scholar.get("first_year")
    last_year = scholar.get("last_year")
    return "год участия" if first_year and first_year == last_year else "годы участия"


def profile_structured_data(scholar, authority):
    path = f"scholars/{scholar['url_slug']}.html"
    name_ru = scholar.get("full_name_ru") or scholar.get("name")
    name_en = scholar.get("full_name_en") or scholar.get("name")
    profile_label, _, _ = scholar_profile_meta(scholar)
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
        "knowsAbout": [profile_label],
        "affiliation": [{"@type": "Organization", "name": aff} for aff in unique_affiliations(scholar, limit=8)],
    }
    if scholar.get("birth_year"):
        person["birthDate"] = str(scholar["birth_year"])
    if scholar.get("death_year"):
        person["deathDate"] = str(scholar["death_year"])
    if scholar.get("degree"):
        person["hasCredential"] = {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": scholar["degree"],
        }
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


def render_profile(scholar, related, authority, meso_by_presentation, meso_items):
    name_ru = scholar.get("full_name_ru") or scholar.get("name")
    name_en = scholar.get("full_name_en") or scholar.get("name")
    description = scholar_description(scholar)
    path = f"scholars/{scholar['url_slug']}.html"
    profile_label, theme_code, profile_note = scholar_profile_meta(scholar)
    cities = unique_cities(scholar)
    affiliations = unique_affiliations(scholar)
    life_ru = format_lifespan(scholar, "ru").strip()
    life_en = format_lifespan(scholar, "en").strip()
    ru_heading = f'{esc(name_ru)} <span class="life">{esc(life_ru)}</span>' if life_ru else esc(name_ru)
    en_heading = " ".join(part for part in [name_en, life_en] if part)
    profile_note_html = f'<p class="profile-note">{esc(profile_note)}</p>' if profile_note else ""
    series_html = (
        series_participation_line(scholar, name_ru, "Зографские чтения", "zograf_talks", "zograf_first", "zograf_last")
        + series_participation_line(scholar, name_ru, "Рериховские чтения", "roerich_talks", "roerich_first", "roerich_last")
    )
    generation_html = ""
    if scholar.get("generation_code"):
        generation_html = (
            f'<article class="card"><strong>Поколение</strong>'
            f'<div class="metric"><a href="../generations/#{esc(scholar["generation_code"])}">{esc(scholar.get("generation_label_ru"))}</a></div>'
            f'<div class="meta">Когорта по году рождения</div></article>'
        )
    else:
        generation_html = (
            '<article class="card"><strong>Поколение</strong>'
            '<div class="metric"><a href="../generations/#unknown">Год рождения не установлен</a></div>'
            '<div class="meta">Требуется биографическая верификация</div></article>'
        )

    related_cards = []
    for relation in related:
        item = relation["scholar"]
        item_profile_label, item_theme_code, _ = scholar_profile_meta(item)
        reason_html = ""
        if relation.get("reasons"):
            reason_html = f'<div class="meta related-reasons">{esc("; ".join(relation["reasons"]))}</div>'
        related_cards.append(
            f'<article class="card"><strong><a href="{item["url_slug"]}.html">{esc(item.get("full_name_ru") or item.get("name"))}</a></strong>'
            f'<div class="meta">{esc(talks_count_label(item.get("total_talks") or 0))} · <a href="../{theme_path(item_theme_code)}">{esc(item_profile_label)}</a></div>'
            f'{reason_html}</article>'
        )
    related_html = "".join(related_cards) or '<p class="meta">Связанные авторы в этом индексе не найдены.</p>'

    status = []
    if scholar.get("is_student"):
        status.append("студент / аспирант")
    if scholar.get("is_independent"):
        status.append("независимый исследователь")

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
            <h1>{ru_heading}</h1>
            <p>{esc(en_heading)}</p>
            {format_degree(scholar)}
            <p>{esc(description)}</p>
            {profile_note_html}
        </header>

        <section class="grid">
            <article class="card"><strong>Доклады</strong><div class="metric">{esc(scholar.get("total_talks"))}</div><div class="meta">{esc(archive_records_label(scholar.get("total_talks") or 0))}</div></article>
            <article class="card"><strong>Активность</strong><div class="metric">{esc(describe_year_span(scholar.get("first_year"), scholar.get("last_year")))}</div><div class="meta">{esc(activity_label(scholar))}</div></article>
            <article class="card"><strong>Рубрика</strong><div class="metric"><a href="../{theme_path(theme_code)}">{esc(profile_label)}</a></div></article>
            <article class="card"><strong>Площадки</strong><div class="meta">{series_html}</div></article>
            {generation_html}
        </section>

        <h2>Аффилиации</h2>
        <div class="chip-row">{chip_links(affiliations, affiliation_href)}</div>

        <h2>Географические центры</h2>
        <div class="chip-row">{chip_links(cities, lambda city: '../' + city_path(city))}</div>

        <h2>Статусы</h2>
        <div class="chip-row">{''.join(f'<span class="chip">{esc(item)}</span>' for item in status) or '<span class="meta">Особые статусы не указаны.</span>'}</div>{external_links_html}

        {scholar_context_block(scholar, meso_by_presentation, meso_items)}

        <h2>Доклады</h2>
        <section class="list">{''.join(talk_card(talk, meso_by_presentation, meso_items) for talk in scholar.get("talks", []))}</section>

        <h2>Связанные авторы</h2>
        <section class="grid">{related_html}</section>
    """

    extra_css = """
    <style>
        .life { color: var(--soft); font-size: 0.62em; font-weight: 500; margin-left: 0.4rem; }
        .degree { color: var(--soft); font-size: 0.95rem; font-weight: 600; margin: 0.15rem 0 0.5rem; }
        .degree a { font-weight: 400; font-size: 0.85em; }
        .profile-note { color: var(--soft); max-width: 860px; }
        .metric { font-size: 1.4rem; font-weight: 700; margin-top: 0.2rem; }
        .chip-row { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .series-line + .series-line { margin-top: 0.28rem; }
        .context-block { display: grid; gap: 0.95rem; margin-bottom: 1.4rem; }
        .context-block strong { display: block; margin-bottom: 0.45rem; }
        .mini-chip { display: inline-block; margin: 0.18rem 0.25rem 0.18rem 0; padding: 0.18rem 0.45rem; border: 1px solid rgba(148,163,184,0.32); border-radius: 999px; font-size: 0.82rem; }
        .context-label { color: var(--soft); font-weight: 650; margin-right: 0.25rem; }
        .talk-context { margin-top: 0.45rem; line-height: 1.8; }
        .related-reasons { margin-top: 0.45rem; font-size: 0.86rem; }
        .talk-meta-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 1rem; align-items: baseline; }
        .talk-meta-session { text-align: right; white-space: nowrap; }
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
        profile_label, theme_code, _ = scholar_profile_meta(scholar)
        cards.append(
            f'<article class="card"><strong><a href="{scholar["url_slug"]}.html">{esc(name)}</a></strong>'
            f'<div class="meta">{esc(talks_count_label(scholar.get("total_talks") or 0))} · {esc(years)} · <a href="../{theme_path(theme_code)}">{esc(profile_label)}</a></div></article>'
        )
    body = f"""
        <header>
            <h1>Профили исследователей</h1>
            <p>Статический указатель сгенерированных профилей исследователей.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    structured = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Профили исследователей",
            "description": "Статический указатель сгенерированных профилей исследователей.",
            "url": site_url("scholars/"),
            "dateModified": BUILD_DATE,
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE_URL},
                {"@type": "ListItem", "position": 2, "name": "Исследователи", "item": site_url("scholars/")},
            ],
        },
    ]
    return page_shell(
        f"Профили исследователей | {SITE_NAME}",
        "Статический указатель сгенерированных профилей исследователей.",
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
    meso_items, meso_by_presentation = load_meso_context()
    authority = load_authority_ids()
    legacy_redirects = load_legacy_redirects()
    slug_redirects = load_slug_redirects()
    scholars_by_id = {scholar["id"]: scholar for scholar in scholars}

    written_files = {"index.html"}
    generated_slugs = set()
    for scholar in scholars:
        slug = scholar["url_slug"]
        generated_slugs.add(slug)
        related = related_scholars(scholar, scholars, meso_by_presentation, meso_items)
        html = render_profile(scholar, related, authority, meso_by_presentation, meso_items)
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
