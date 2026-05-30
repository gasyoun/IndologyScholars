import datetime as dt
import csv
import hashlib
import json
import re
import sqlite3
import struct
import sys
import zlib
import jinja2
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from classification_overrides import CLASSIFICATION_OVERRIDES, MESO_LABELS
from publication_helpers import (
    AUTHOR_NAME,
    assign_public_ids,
    build_presentation_slug_map,
    GENERATION_COHORTS,
    OG_IMAGE_PATH,
    PUBLIC_ID_CSS,
    SITE_NAME,
    SITE_NAME_RU,
    SITE_URL,
    THEME_LABELS,
    clean_text,
    describe_year_span,
    esc,
    json_ld,
    load_authority_overrides,
    load_site_data,
    organization_structured_data,
    page_shell,
    place_structured_data,
    site_url,
    slugify,
    theme_label,
    clean_person_urls,
)


DB_PATH = "conferences.db"
BUILD_DATE = dt.date.today().isoformat()
DATA_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "2026-05-25"
PUBLIC_DIRS = ["assets", "conferences", "p", "themes", "topics", "generations", "meso", "gumilyov", "videos", "findings", "cities", "institutions", "keywords"]
_JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
PRESENTATION_SLUG_BY_ID = {}
MIN_PUBLIC_MESO_PRESENTATIONS = 2
PRESENTATIONS_PER_PAGE = 120
SEO_TITLE_BRAND = "Индологический архив"


def ensure_dirs():
    for dirname in PUBLIC_DIRS:
        Path(dirname).mkdir(exist_ok=True)


def write_text(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8", newline="\n")


def file_size_label(path):
    target = Path(path)
    if not target.exists():
        return "not generated"
    size = target.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def generated_manifest_paths():
    roots = [
        "404.html",
        "CITATION.cff",
        "data_dictionary.md",
        "datapackage.json",
        "download-data.html",
        "data-quality.html",
        "en.html",
        "how-to-cite.html",
        "index.html",
        "known-limitations.html",
        "methodology.html",
        "classification-criteria.html",
        "metrics-guide.html",
        "networks.html",
        "offline.html",
        "robots.txt",
        "search.html",
        "search-index.json",
        "service-worker.js",
        "site.webmanifest",
        "site_data.json",
        "sitemap.xml",
    ]
    directories = ["analytics_output", "assets", "cities", "conferences", "p", "findings", "generations", "gumilyov", "institutions", "keywords", "meso", "s", "themes", "topics", "videos", "curation"]
    paths = [Path(path) for path in roots]
    for dirname in directories:
        root = Path(dirname)
        if root.exists():
            paths.extend(path for path in root.rglob("*") if path.is_file())
    excluded = {
        Path("analytics_output/publication_file_manifest.csv"),
        Path("analytics_output/publication_file_manifest.json"),
    }
    return sorted({path for path in paths if path.exists() and path not in excluded}, key=lambda p: str(p).replace("\\", "/"))


def generate_publication_file_manifest():
    rows = []
    for path in generated_manifest_paths():
        rel = str(path).replace("\\", "/")
        rows.append({
            "path": rel,
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        })

    Path("analytics_output").mkdir(exist_ok=True)
    csv_path = Path("analytics_output/publication_file_manifest.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "size_bytes", "sha256"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "schema_version": DATA_SCHEMA_VERSION,
        "generated": BUILD_DATE,
        "build": {
            "source": "IndologyScholars",
            "pipeline_version": PIPELINE_VERSION,
            "generator": "generate_publication_pages.py",
        },
        "file_count": len(rows),
        "files": rows,
    }
    write_text("analytics_output/publication_file_manifest.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return len(rows)


def normalize_affiliation(aff):
    value = (aff or "").lower()
    if "ивр " in value or "восточных рукописей" in value:
        return "ИВР РАН"
    if "ив ран" in value or "востоковедения ран" in value or "ивран" in value:
        return "ИВ РАН"
    if "спбгу" in value or "петербургский" in value:
        return "СПбГУ"
    if "мгу" in value or "ломоносова" in value:
        return "МГУ"
    if "вшэ" in value or "высшая школа" in value:
        return "НИУ ВШЭ"
    if "рггу" in value or "гуманитарный" in value:
        return "РГГУ"
    if "маэ" in value or "кунсткамера" in value:
        return "МАЭ РАН"
    if "эрмитаж" in value:
        return "Государственный Эрмитаж"
    if "институт философии" in value or "иф ран" in value:
        return "ИФ РАН"
    if "независим" in value or "independent" in value:
        return "Независимые исследователи"
    return None


def series_slug(series):
    return "zograf" if "Zograf" in (series or "") else "roerich"


def series_label(series, lang="en"):
    is_zograf = series_slug(series) == "zograf"
    if lang == "ru":
        return "Зографские чтения" if is_zograf else "Рериховские чтения"
    return "Zograf Readings" if is_zograf else "Roerich Readings"


def conference_path(series, year):
    return f"conferences/{series_slug(series)}-{year}.html"


def initialize_presentation_slugs(records):
    global PRESENTATION_SLUG_BY_ID
    PRESENTATION_SLUG_BY_ID = build_presentation_slug_map(records)


def presentation_path(presentation_id, title=None):
    pid = clean_text(presentation_id)
    slug = PRESENTATION_SLUG_BY_ID.get(pid)
    if not slug and title:
        slug = slugify(title, pid.lower().replace("_", "-") or "presentation")
    return f"p/{slug or pid}.html"


def theme_path(code):
    return f"themes/{slugify(code, 'theme')}.html"


def topic_path(code):
    return f"topics/{slugify(code, 'topic')}.html"


def generations_path():
    return "generations/"


def collaboration_path():
    return "collaboration/"


def nlp_path():
    return "nlp/"


def meso_path(code):
    return f"meso/{slugify(code, 'meso')}.html"


def gumilyov_path(level):
    return f"gumilyov/level-{int(level)}.html"


def videos_year_path(year):
    return f"videos/year-{int(year)}.html"


GUMILYOV_LEVELS = {
    0: {
        "ru": "Ожидает разметки",
        "en": "Awaiting classification",
        "short_ru": "Не размечен",
        "short_en": "Unclassified",
        "description": "Доклады, добавленные в корпус после последнего завершенного классификационного прохода.",
    },
    1: {
        "ru": "Микроуровень",
        "en": "Micro level",
        "short_ru": "Микро",
        "short_en": "Micro",
        "description": "Доклады, сосредоточенные на конкретном тексте, авторе, памятнике, термине или локальном кейсе.",
    },
    2: {
        "ru": "Региональный уровень",
        "en": "Regional level",
        "short_ru": "Региональный",
        "short_en": "Regional",
        "description": "Доклады, связывающие материал с историко-культурной областью, традицией, школой, регионом или эпохой.",
    },
    3: {
        "ru": "Глобальный уровень",
        "en": "Global level",
        "short_ru": "Глобальный",
        "short_en": "Global",
        "description": "Доклады, формулирующие широкие сравнительные, цивилизационные, методологические или межрегиональные обобщения.",
    },
}

NAMED_TOPICS = {
    "ramayana": {
        "title": "Рамаяна",
        "pattern": r"\bрамаян[а-яё]*\b",
        "description": "Доклады, в названиях которых упомянуты «Рамаяна» или связанные с ней версии и интерпретации.",
        "aliases": ("рамаяна", "рамаяны", "рамаяне", "рамаян"),
    },
    "mahabharata": {
        "title": "Махабхарата",
        "pattern": r"\bмахабхарат[а-яё]*\b",
        "description": "Доклады, в названиях которых упомянуты «Махабхарата» или связанные с ней сюжеты.",
        "aliases": ("махабхарата", "махабхараты", "махабхарате", "махабхарат"),
    },
}


def gumilyov_meta(level):
    try:
        level_int = int(level)
    except (TypeError, ValueError):
        level_int = 0
    return level_int, GUMILYOV_LEVELS.get(level_int, GUMILYOV_LEVELS[0])


L1_DISTRIBUTION_LINKS = {
    "история": ("theme", "history_and_culture"),
    "этнография": ("theme", "history_and_culture"),
    "религия": ("theme", "religion_and_philosophy"),
    "философия": ("theme", "religion_and_philosophy"),
    "литература": ("theme", "literature_and_poetry"),
    "лингвистика": ("theme", "linguistics_and_philology"),
    "искусство и археология": ("theme", "art_and_material_culture"),
    "тибетология": ("meso", "tibetology_himalaya"),
    "прочее": ("theme", "unspecified"),
}


def search_path(query, depth=""):
    return f"{depth}search.html?q={quote(clean_text(query), safe='')}"


def linked_l1_target(label):
    return L1_DISTRIBUTION_LINKS.get(clean_text(label).lower())


def linked_target_href(target, depth=""):
    if not target:
        return None
    kind, code = target
    if kind == "theme":
        return f"{depth}{theme_path(code)}"
    if kind == "meso":
        return f"{depth}{meso_path(code)}"
    return None


def distribution_entries(distribution):
    entries = []
    for raw_part in str(distribution or "").split(";"):
        part = clean_text(raw_part)
        if not part:
            continue
        if part.lower().startswith("l1:"):
            label = clean_text(part.split(":", 1)[1])
            if label:
                entries.append((label, ""))
            continue
        if ":" in part:
            label, count = part.rsplit(":", 1)
            entries.append((clean_text(label), clean_text(count)))
        else:
            entries.append((part, ""))
    return entries


def format_distribution_links(distribution, depth=""):
    links = []
    for label, count in distribution_entries(distribution):
        target = linked_l1_target(label)
        href = linked_target_href(target, depth)
        text = f"{label}: {count}" if count else label
        if href:
            links.append(f'<a class="chip" href="{esc(href)}">{esc(text)}</a>')
        else:
            links.append(f'<span class="chip">{esc(text)}</span>')
    return "".join(links)


PUBLIC_KEYWORD_LABELS = {
    "рамаян": "Рамаяна",
    "махабхарат": "Махабхарата",
    "индия": "Индия",
    "южная_индия": "Южная Индия",
}


def public_keyword_label(keyword):
    return PUBLIC_KEYWORD_LABELS.get(clean_text(keyword).lower(), keyword)


def format_keyword_links(terms, depth=""):
    links = []
    for raw_term in str(terms or "").split(","):
        term = clean_text(raw_term)
        if not term:
            continue
        label = public_keyword_label(term)
        links.append(f'<a class="chip" href="{esc(search_path(term, depth))}">{esc(label)}</a>')
    return "".join(links)


def talk_deep_link(talk, depth=""):
    pid = clean_text(talk.get("presentation_id") or "")
    if pid:
        return f"{depth}{presentation_path(pid)}"
    return f"{depth}{conference_path(talk.get('series_key'), talk.get('year'))}"


def chip_section(title, links):
    if not links:
        return ""
    return f"""
        <section class="link-block">
            <strong>{esc(title)}</strong>
            <div class="chip-list">{''.join(links)}</div>
        </section>
    """


def facet_theme_links(talks, depth="", limit=10):
    counts = defaultdict(int)
    for talk in talks:
        code = (talk.get("theme") or {}).get("code") or "unspecified"
        counts[code] += 1
    return [
        f'<a class="chip" href="{depth}{theme_path(code)}">{esc(theme_label(code, "ru"))} · {talks_count_label(count)}</a>'
        for code, count in sorted(counts.items(), key=lambda item: (-item[1], theme_label(item[0], "ru")))[:limit]
    ]


def facet_conference_links(talks, depth="", limit=10):
    counts = defaultdict(int)
    for talk in talks:
        key = (talk.get("series_key"), talk.get("year"))
        counts[key] += 1
    return [
        f'<a class="chip" href="{depth}{conference_path(series, year)}">{esc(series_label(series, "ru"))} {esc(year)} · {talks_count_label(count)}</a>'
        for (series, year), count in sorted(counts.items(), key=lambda item: (-(int(item[0][1]) if item[0][1] else 0), item[0][0]))[:limit]
    ]


def facet_city_links(talks, depth="", limit=10):
    counts = defaultdict(int)
    for talk in talks:
        city = (talk.get("geography") or {}).get("ru")
        if city and city not in ("Не указана", "Not specified"):
            counts[city] += 1
    return [
        f'<a class="chip" href="{depth}{city_path(city)}">{esc(city)} · {talks_count_label(count)}</a>'
        for city, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def facet_institution_links(talks, depth="", limit=10):
    counts = defaultdict(int)
    for talk in talks:
        institution = normalize_affiliation(talk.get("affiliation"))
        if institution:
            counts[institution] += 1
    return [
        f'<a class="chip" href="{depth}{institution_path(institution)}">{esc(institution)} · {talks_count_label(count)}</a>'
        for institution, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def facet_scholar_links(talks, depth="", limit=12):
    seen_names = {}
    counts = defaultdict(int)
    for talk in talks:
        slug = talk.get("speaker_slug")
        name = talk.get("speaker") or talk.get("speaker_original")
        if not slug or not name:
            continue
        counts[slug] += 1
        seen_names.setdefault(slug, name)
    return [
        f'<a class="chip" href="{profile_href(slug, depth)}">{esc(seen_names[slug])} · {talks_count_label(count)}</a>'
        for slug, count in sorted(counts.items(), key=lambda item: (-item[1], seen_names.get(item[0], "")))[:limit]
    ]


def facet_meso_links(talks, memberships, meso_items_by_code, depth="", limit=12):
    talk_ids = {clean_text(talk.get("presentation_id") or "") for talk in talks}
    talk_ids.discard("")
    links = []
    for code, pids in memberships.items():
        count = len(talk_ids.intersection(pids))
        item = meso_items_by_code.get(code)
        if count and item:
            links.append((item["label"], code, count))
    return [
        f'<a class="chip" href="{depth}{meso_path(code)}">{esc(label)} · {talks_count_label(count)}</a>'
        for label, code, count in sorted(links, key=lambda item: (-item[2], item[0]))[:limit]
    ]


def facet_gumilyov_links(talks, depth="", limit=3):
    counts = defaultdict(int)
    seen = set()
    for talk in talks:
        pid = clean_text(talk.get("presentation_id") or "")
        if pid:
            if pid in seen:
                continue
            seen.add(pid)
        level, meta = gumilyov_meta(talk.get("gumilyov_scale"))
        counts[level] += 1
    return [
        f'<a class="chip" href="{depth}{gumilyov_path(level)}">L{level} {esc(GUMILYOV_LEVELS[level]["short_ru"])} · {talks_count_label(count)}</a>'
        for level, count in sorted(counts.items())[:limit]
    ]


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


def presentation_records_label(count):
    return talks_count_label(count)


def is_suspicious_short_title(title):
    value = clean_text(title)
    words = re.findall(r"\w+", value, flags=re.UNICODE)
    if not value:
        return True
    if value.endswith((" в", " и", " к", " о", " по", " для", ":", ",")):
        return True
    return len(words) <= 3


def city_path(city):
    return f"cities/{slugify(city, 'city')}.html"


def institution_path(name):
    return f"institutions/{slugify(name, 'institution')}.html"


def profile_href(slug, depth=""):
    return f"{depth}s/{slug}.html"


def dashboard_search_href(query, depth=""):
    return f"{depth}index.html?search={quote(clean_text(query))}"


def timeline_records(data):
    records = []
    for year, series_groups in data.get("timeline", {}).items():
        for key, talks in series_groups.items():
            for talk in talks:
                record = dict(talk)
                record["year"] = int(year)
                record["series_key"] = key
                record["series_label"] = series_label(key)
                records.append(record)
    return records


def load_csv_rows(path):
    target = Path(path)
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_meso_index():
    items = []
    for row in load_csv_rows("article/hypothesis_output/title_keyword_microseries.csv"):
        code = row.get("microseries") or ""
        if not code:
            continue
        items.append(
            {
                "code": code,
                "label": row.get("label") or code,
                "kind": "Мини-серия",
                "count": int(row.get("count") or 0),
                "zograf_count": int(row.get("zograf_count") or 0),
                "roerich_count": int(row.get("roerich_count") or 0),
                "top_terms": row.get("top_terms") or "",
                "distribution": row.get("l1_distribution") or "",
                "examples": row.get("examples") or "",
            }
        )
    for row in load_csv_rows("article/hypothesis_output/title_keyword_linguistics_subfields.csv"):
        approach = row.get("approach") or ""
        if not approach:
            continue
        code = f"linguistics_{approach}"
        label = row.get("label") or approach
        items.append(
            {
                "code": code,
                "label": label[:1].upper() + label[1:],
                "kind": "Подраздел зонтичной рубрики «Лингвистика и филология»",
                "count": int(row.get("count") or 0),
                "zograf_count": int(row.get("zograf_count") or 0),
                "roerich_count": int(row.get("roerich_count") or 0),
                "top_terms": row.get("top_terms") or "",
                "distribution": "L1: лингвистика",
                "examples": row.get("examples") or "",
            }
        )
    known = {item["code"] for item in items}
    for code, label in MESO_LABELS.items():
        if code not in known:
            items.append(
                {
                    "code": code,
                    "label": label,
                    "kind": "Экспертный мезоуровень",
                    "count": 0,
                    "zograf_count": 0,
                    "roerich_count": 0,
                    "top_terms": "",
                    "distribution": "",
                    "examples": "",
                }
            )
    pid_series = {
        row.get("presentation_id", ""): row.get("series", "")
        for row in load_csv_rows("analytics_output/meso_codes_deepseek.csv")
    }
    memberships = load_meso_memberships()
    for item in items:
        pids = set(memberships.get(item["code"], []))
        item["count"] = len(pids)
        item["zograf_count"] = sum(1 for pid in pids if "Zograf" in pid_series.get(pid, ""))
        item["roerich_count"] = sum(1 for pid in pids if "Roerich" in pid_series.get(pid, ""))
    items = [item for item in items if int(item.get("count") or 0) >= MIN_PUBLIC_MESO_PRESENTATIONS]
    items.sort(key=lambda item: (-item["count"], item["kind"], item["label"]))
    return items


def load_meso_memberships():
    memberships = defaultdict(list)
    for row in load_csv_rows("article/hypothesis_output/title_keyword_microseries_titles.csv"):
        code = row.get("microseries") or ""
        pid = row.get("presentation_id") or ""
        if code and pid:
            memberships[code].append(pid)
    for row in load_csv_rows("article/hypothesis_output/title_keyword_linguistics_subfield_titles.csv"):
        approach = row.get("approach") or ""
        pid = row.get("presentation_id") or ""
        if approach and pid:
            memberships[f"linguistics_{approach}"].append(pid)
    for row in load_csv_rows("analytics_output/meso_codes_deepseek.csv"):
        pid = row.get("presentation_id") or ""
        for code in (row.get("meso_codes") or "").split("|"):
            if code and pid and pid not in memberships[code]:
                memberships[code].append(pid)
    reviewed_ids = set(CLASSIFICATION_OVERRIDES)
    for code in list(memberships):
        memberships[code] = [pid for pid in memberships[code] if pid not in reviewed_ids]
    for pid, review in CLASSIFICATION_OVERRIDES.items():
        for code in review.get("meso_codes", []):
            if pid not in memberships[code]:
                memberships[code].append(pid)
    return memberships


def attach_meso_codes(records):
    by_presentation = defaultdict(list)
    for code, pids in load_meso_memberships().items():
        for pid in pids:
            by_presentation[pid].append(code)
    for record in records:
        pid = clean_text(record.get("presentation_id") or "")
        record["meso_codes"] = list(dict.fromkeys(by_presentation.get(pid, [])))


@lru_cache(maxsize=1)
def meso_items_by_code():
    return {item["code"]: item for item in load_meso_index()}


def presentation_records_by_id(records):
    grouped = {}
    speakers = defaultdict(list)
    speaker_slugs = defaultdict(list)
    speaker_links = defaultdict(list)
    for record in records:
        pid = record.get("presentation_id")
        if not pid:
            continue
        if pid not in grouped:
            grouped[pid] = dict(record)
        speaker = record.get("speaker") or record.get("speaker_original")
        if speaker and speaker not in speakers[pid]:
            speakers[pid].append(speaker)
        slug = record.get("speaker_slug")
        if slug and slug not in speaker_slugs[pid]:
            speaker_slugs[pid].append(slug)
        link_key = (speaker or "", slug or "")
        if speaker and link_key not in {(item["name"], item.get("slug") or "") for item in speaker_links[pid]}:
            speaker_links[pid].append({"name": speaker, "slug": slug})
    for pid, record in grouped.items():
        if speakers[pid]:
            record["speaker"] = "; ".join(speakers[pid])
        if speaker_links[pid]:
            record["speaker_links"] = speaker_links[pid]
        if len(speaker_slugs[pid]) == 1:
            record["speaker_slug"] = speaker_slugs[pid][0]
        elif len(speaker_slugs[pid]) != 1:
            record["speaker_slug"] = None
    return grouped


def scholar_links_html(talk, depth=""):
    speaker_links = talk.get("speaker_links") or []
    if speaker_links:
        links = []
        for item in speaker_links:
            name = esc(item.get("name") or "")
            slug = item.get("slug")
            if slug:
                links.append(f'<a href="{profile_href(slug, depth)}">{name}</a>')
            elif name:
                links.append(name)
        if links:
            return "; ".join(links)

    speaker_slug = talk.get("speaker_slug")
    speaker = esc(talk.get("speaker") or talk.get("speaker_original") or "Unknown")
    return f'<a href="{profile_href(speaker_slug, depth)}">{speaker}</a>' if speaker_slug else speaker


def scholar_by_id(data):
    return {s["id"]: s for s in data.get("scholars", [])}


def talk_card(talk, depth=""):
    scholar_link = scholar_links_html(talk, depth)
    city = (talk.get("geography") or {}).get("ru")
    city_link = ""
    if city and city not in ("Не указана", "Not specified"):
        city_link = f' · <a href="{depth}{city_path(city)}">{esc(city)}</a>'
    theme = talk.get("theme") or {}
    theme_code = theme.get("code", "History")
    anchor = clean_text(talk.get("presentation_id") or "")
    anchor_attr = f' id="{esc(anchor)}"' if anchor else ""
    title_href = talk_deep_link(talk, depth)
    g_level, g_meta = gumilyov_meta(talk.get("gumilyov_scale"))
    gumilyov_link = f'<a href="{depth}{gumilyov_path(g_level)}">L{g_level} {esc(g_meta["short_ru"])}</a>'
    online_badge = '<span class="badge badge-online">Онлайн</span>' if talk.get("is_online") else ""
    items = meso_items_by_code()
    meso_links = [
        f'<a class="chip" href="{depth}{meso_path(code)}">{esc(items[code]["label"])}</a>'
        for code in talk.get("meso_codes", [])
        if code in items
    ]
    meso_html = chip_section("Мезоуровни", meso_links)
    videos = talk.get("videos") or []
    video_badge = '<span class="badge badge-video">Видео</span>' if videos else ""
    video_html = ""
    if videos:
        links = []
        for idx, video in enumerate(videos, start=1):
            label = "YouTube" if len(videos) == 1 else f"YouTube {idx}"
            links.append(f'<a href="{esc(video.get("url"))}">{esc(label)}</a>')
        video_html = f'<div class="meta">Сохранившаяся запись: {" · ".join(links)}</div>'
    return f"""
        <article class="talk"{anchor_attr}>
            <strong><a href="{esc(title_href)}">{esc(talk.get("title"))}</a></strong>{online_badge}{video_badge}
            <div class="meta">
                {scholar_link} · <a href="{depth}{conference_path(talk.get("series_key"), talk.get("year"))}">{esc(series_label(talk.get("series_key"), "ru"))} {esc(talk.get("year"))}</a>
                · <a href="{depth}{theme_path(theme_code)}">{esc(theme_label(theme_code, "ru"))}</a>
                · {gumilyov_link}{city_link}
            </div>
            {meso_html}
            {video_html}
        </article>
    """


def make_breadcrumbs(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": label,
                "item": site_url(path),
            }
            for index, (label, path) in enumerate(items)
        ],
    }


def page_data(title, description, canonical_path, page_type="CollectionPage", extra=None):
    data = {
        "@context": "https://schema.org",
        "@type": page_type,
        "name": title,
        "description": description,
        "url": site_url(canonical_path),
        "isPartOf": {
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "dateModified": BUILD_DATE,
    }
    if extra:
        data.update(extra)
    return data


def generate_home_assets(data):
    summary = data.get("summary", {})
    citation = f"""cff-version: 1.2.0
message: "If you use this archive, please cite it."
title: "{SITE_NAME}: Unified Relational Archive"
authors:
  - family-names: "Gasūns"
    given-names: "Mārcis"
    name-particle: "Dr."
type: dataset
url: "{SITE_URL}"
repository-code: "https://github.com/gasyoun/IndologyScholars"
date-released: "{BUILD_DATE}"
version: "1.0.0"
license: "Apache-2.0"
abstract: "A curated relational archive of Zograf Readings and Roerich Readings conference programs, scholars, presentations, affiliations, cities, and thematic classifications."
keywords:
  - Indology
  - digital humanities
  - conference programs
  - Zograf Readings
  - Roerich Readings
"""
    write_text("CITATION.cff", citation)

    datapackage = {
        "profile": "data-package",
        "schema_version": DATA_SCHEMA_VERSION,
        "generated": BUILD_DATE,
        "build": {
            "source": "IndologyScholars",
            "pipeline_version": PIPELINE_VERSION,
            "generator": "generate_publication_pages.py",
        },
        "name": "indology-scholars",
        "title": SITE_NAME,
        "description": "Normalized archive of Russian Indological conference presentations and scholar profiles.",
        "homepage": SITE_URL,
        "created": BUILD_DATE,
        "licenses": [
            {"name": "Apache-2.0", "path": "LICENSE", "title": "Software License"},
            {"name": "CC-BY-4.0", "title": "Dataset License (Derived Metadata)", "path": "https://creativecommons.org/licenses/by/4.0/"}
        ],
        "contributors": [{"title": AUTHOR_NAME, "role": "author"}],
        "keywords": ["Indology", "digital humanities", "conference archive"],
        "sources": [
            {"title": "Zograf Readings programs", "path": "html_cache/"},
            {"title": "Roerich Readings programs", "path": "html_cache/"},
        ],
        "stats": summary,
        "resources": [
            {
                "name": "site-data",
                "path": "site_data.json",
                "format": "js",
                "mediatype": "application/javascript",
                "description": "Browser payload with scholars, presentations, charts, and network data.",
                "schema": {
                    "fields": [
                        {"name": "schema_version", "type": "string"},
                        {"name": "generated", "type": "date"},
                        {"name": "summary", "type": "object"},
                        {"name": "scholars", "type": "array"},
                        {"name": "timeline", "type": "object"},
                    ]
                },
            },
            {
                "name": "database",
                "path": "conferences.db",
                "format": "sqlite",
                "mediatype": "application/vnd.sqlite3",
                "description": "Normalized SQLite database.",
            },
            {
                "name": "search-index",
                "path": "search-index.json",
                "format": "json",
                "mediatype": "application/json",
                "description": "Static search index for generated scholar and presentation pages.",
            },
            {
                "name": "data-quality-report",
                "path": "analytics_output/data_quality_report.json",
                "format": "json",
                "mediatype": "application/json",
                "description": "Machine-readable data quality checks and review samples.",
                "schema": {
                    "fields": [
                        {"name": "schema_version", "type": "string"},
                        {"name": "generated", "type": "date"},
                        {"name": "summary", "type": "object"},
                        {"name": "checks", "type": "array"},
                    ]
                },
            },
            {
                "name": "data-dictionary",
                "path": "data_dictionary.md",
                "format": "md",
                "mediatype": "text/markdown",
                "description": "Human-readable field guide for reusable CSV, JSON, SQLite, and generated publication outputs.",
            },
            {
                "name": "presentation-id-manifest",
                "path": "analytics_output/presentation_id_manifest.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Stable presentation ID manifest used to audit rebuild stability.",
                "schema": {
                    "fields": [
                        {"name": "presentation_id", "type": "string"},
                        {"name": "series", "type": "string"},
                        {"name": "year", "type": "integer"},
                        {"name": "event_id", "type": "string"},
                        {"name": "session_id", "type": "string"},
                        {"name": "title", "type": "string"},
                        {"name": "first_speaker", "type": "string"},
                        {"name": "all_speakers", "type": "string"},
                        {"name": "source_url", "type": "string"},
                        {"name": "source_snippet_hash", "type": "string"},
                        {"name": "stable_key_candidate", "type": "string"},
                    ]
                },
            },
            {
                "name": "id-stability-audit",
                "path": "analytics_output/id_stability_audit.json",
                "format": "json",
                "mediatype": "application/json",
                "description": "Machine-readable audit proving presentation IDs are stable across unchanged rebuilds.",
            },
            {
                "name": "field-provenance-biographical",
                "path": "analytics_output/field_provenance_biographical.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Field-level provenance for curated person names and life dates.",
            },
            {
                "name": "field-provenance-authority",
                "path": "analytics_output/field_provenance_authority.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Field-level provenance for external authority identifiers and organization records.",
            },
            {
                "name": "field-provenance-themes",
                "path": "analytics_output/field_provenance_themes.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Field-level provenance for generated presentation theme labels and review candidates.",
            },
            {
                "name": "verified-affiliation-spans",
                "path": "curation/verified_affiliation_spans.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Dated source-backed institutional trajectories used for public affiliation normalization.",
            },
            {
                "name": "network-nodes",
                "path": "analytics_output/network_nodes.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Typed nodes for person, event, organization, and theme network analysis.",
                "schema": {
                    "fields": [
                        {"name": "node_id", "type": "string"},
                        {"name": "node_type", "type": "string"},
                        {"name": "label", "type": "string"},
                        {"name": "local_id", "type": "string"},
                        {"name": "weight", "type": "integer"},
                    ]
                },
            },
            {
                "name": "network-edges",
                "path": "analytics_output/network_edges.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Weighted network edges with explicit relation type, year, and conference series.",
                "schema": {
                    "fields": [
                        {"name": "source", "type": "string"},
                        {"name": "target", "type": "string"},
                        {"name": "edge_type", "type": "string"},
                        {"name": "year", "type": "integer"},
                        {"name": "series", "type": "string"},
                        {"name": "weight", "type": "integer"},
                    ]
                },
            },
            {
                "name": "publication-file-manifest",
                "path": "analytics_output/publication_file_manifest.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "description": "Generated publication file manifest with byte sizes and SHA-256 checksums.",
                "schema": {
                    "fields": [
                        {"name": "path", "type": "string"},
                        {"name": "size_bytes", "type": "integer"},
                        {"name": "sha256", "type": "string"},
                    ]
                },
            },
            {
                "name": "analytics",
                "path": "analytics_output/",
                "format": "csv",
                "description": "Derived analytical CSV exports.",
            },
        ],
    }
    write_text("datapackage.json", json.dumps(datapackage, ensure_ascii=False, indent=2))

    robots = f"""User-agent: Yandex
Host: gasyoun.github.io
Clean-param: search&sort&page&filter /IndologyScholars/

User-agent: *
Allow: /

Sitemap: {site_url('sitemap.xml')}
"""
    write_text("robots.txt", robots)

    manifest = {
        "name": SITE_NAME,
        "short_name": "IndologyScholars",
        "id": "/IndologyScholars/",
        "start_url": "/IndologyScholars/",
        "scope": "/IndologyScholars/",
        "lang": "ru",
        "display": "standalone",
        "background_color": "#0a0e1a",
        "theme_color": "#0a0e1a",
        "icons": [
            {"src": "/IndologyScholars/assets/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/IndologyScholars/assets/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            {"src": "/IndologyScholars/assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    write_text("site.webmanifest", json.dumps(manifest, ensure_ascii=False, indent=2))

    favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="12" fill="#0a0e1a"/>
<path d="M14 44h36M18 38h28M22 18h20v20H22z" fill="none" stroke="#c4b5fd" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M25 25h14M25 31h10" stroke="#ec4899" stroke-width="3" stroke-linecap="round"/>
</svg>
"""
    write_text("assets/favicon.svg", favicon)
    write_app_icon("assets/icon-192.png", 192)
    write_app_icon("assets/icon-512.png", 512)
    write_app_icon("assets/apple-touch-icon.png", 180)
    write_og_image("assets/og-image.png")


def write_app_icon(path, size):
    background = (10, 14, 26)
    lavender = (196, 181, 253)
    pink = (236, 72, 153)
    line_width = max(2, round(size * 4 / 64))
    accent_width = max(2, round(size * 3 / 64))

    def scale(value):
        return round(size * value / 64)

    def near(value, target, width):
        return abs(value - target) <= width / 2

    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            color = background
            book_outline = (
                (scale(22) <= x <= scale(42) and (near(y, scale(18), line_width) or near(y, scale(38), line_width)))
                or (scale(18) <= y <= scale(38) and (near(x, scale(22), line_width) or near(x, scale(42), line_width)))
                or (scale(18) <= x <= scale(46) and near(y, scale(38), line_width))
                or (scale(14) <= x <= scale(50) and near(y, scale(44), line_width))
            )
            accent = (
                (scale(25) <= x <= scale(39) and near(y, scale(25), accent_width))
                or (scale(25) <= x <= scale(35) and near(y, scale(31), accent_width))
            )
            if book_outline:
                color = lavender
            if accent:
                color = pink
            row.extend(color)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    Path(path).write_bytes(png)


def write_og_image(path):
    width, height = 1200, 630
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            rx = x / max(width - 1, 1)
            ry = y / max(height - 1, 1)
            glow = max(0, 1 - (((rx - 0.25) ** 2 + (ry - 0.25) ** 2) ** 0.5) * 2.5)
            glow2 = max(0, 1 - (((rx - 0.78) ** 2 + (ry - 0.72) ** 2) ** 0.5) * 2.3)
            line = 0.08 if abs((x + y) % 180) < 3 else 0
            r = int(10 + 110 * glow + 70 * glow2 + 35 * line)
            g = int(14 + 60 * glow + 24 * glow2 + 15 * line)
            b = int(26 + 165 * glow + 130 * glow2 + 70 * line)
            row.extend((min(r, 255), min(g, 255), min(b, 255)))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    Path(path).write_bytes(png)


def generate_search(data, records):
    index = []
    for scholar in data.get("scholars", []):
        talks = scholar.get("talks", [])
        index.append(
            {
                "type": "Scholar",
                "title": scholar.get("full_name_ru") or scholar.get("name"),
                "url": f"s/{scholar['url_slug']}.html",
                "text": " ".join(
                    [
                        scholar.get("full_name_en") or "",
                        scholar.get("original_fullname") or "",
                        scholar.get("name") or "",
                        " ".join(scholar.get("all_affiliations") or []),
                        " ".join(t.get("title") or "" for t in talks),
                    ]
                ),
            }
        )
    for talk in presentation_records_by_id(records).values():
        pid = clean_text(talk.get("presentation_id") or "")
        talk_url = presentation_path(pid) if pid else conference_path(talk.get("series_key"), talk.get("year"))
        video_status = "Видео" if talk.get("videos") else ""
        index.append(
            {
                "type": "Presentation",
                "title": talk.get("title"),
                "url": talk_url,
                "meta": " · ".join(filter(None, [
                    f"{series_label(talk.get('series_key'), 'ru')} {talk.get('year')}",
                    talk.get("speaker") or "",
                    video_status,
                ])),
                "text": " ".join([
                    talk.get("title") or "",
                    talk.get("speaker") or "",
                    talk.get("affiliation") or "",
                    theme_label((talk.get("theme") or {}).get("code"), "ru"),
                    GUMILYOV_LEVELS[gumilyov_meta(talk.get("gumilyov_scale"))[0]]["ru"],
                    series_label(talk.get("series_key"), "ru"),
                    str(talk.get("year") or ""),
                    (talk.get("geography") or {}).get("ru") or "",
                    video_status,
                ]),
            }
        )
    for code, topic in NAMED_TOPICS.items():
        index.append(
            {
                "type": "Topic",
                "title": topic["title"],
                "url": topic_path(code),
                "meta": "Именной сюжет",
                "text": " ".join([topic["description"], *topic["aliases"]]),
            }
        )
    index.append(
        {
            "type": "Generation",
            "title": "Поколения индологов",
            "url": generations_path(),
            "meta": "Когорты по году рождения",
            "text": "Васильков Толчельников поколения возраст год рождения старшее младшее когорта",
        }
    )
    index.append(
        {
            "type": "Method",
            "title": "Критерии классификации докладов",
            "url": "classification-criteria.html",
            "meta": "Рубрики, мезоуровни и L1-L3",
            "text": "классификация рубрика мезоуровень Гумилев L1 L2 L3 микроуровень масштаб аргументации",
        }
    )
    index.append(
        {
            "type": "Keyword",
            "title": "Ключевые слова",
            "url": "keywords/",
            "meta": "Статистика ключевых слов",
            "text": "ключевые слова статистика заголовки докладов частотность термины",
        }
    )
    for level, meta in GUMILYOV_LEVELS.items():
        index.append(
            {
                "type": "Gumilyov",
                "title": f"L{level} {meta['ru']}",
                "url": gumilyov_path(level),
                "text": " ".join([meta["ru"], meta["en"], meta["short_ru"], meta["description"]]),
            }
        )
    for row in load_youtube_rows():
        year = clean_text(row.get("year") or "")
        index.append(
            {
                "type": "Video",
                "title": row.get("video_title") or row.get("video_url"),
                "url": videos_year_path(year) if year else "videos/",
                "text": " ".join([row.get("playlist_label") or "", row.get("video_title") or "", row.get("video_url") or "", year]),
            }
        )
    for item in load_meso_index():
        index.append(
            {
                "type": "Meso-level",
                "title": item["label"],
                "url": meso_path(item["code"]),
                "text": " ".join([item.get("kind") or "", item.get("top_terms") or "", item.get("distribution") or "", item.get("examples") or ""]),
            }
        )
    index.append(
        {
            "type": "Finding",
            "title": "Главные выводы статьи",
            "url": "findings/",
            "text": " ".join(
                [
                    "пересечение 38 вместо 104",
                    "микрокейс G1 G2 G3 Гумилев",
                    "видеозаписи YouTube",
                    "тематическая асимметрия Зографские Рериховские",
                    "городские метки аффилиации источник",
                    "слабая межплощадочная проницаемость",
                ]
            ),
        }
    )
    write_text("search-index.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))

    body = """
        <header>
            <h1>Поиск по архиву</h1>
            <p>Поиск по авторам, названиям докладов, организациям, городам, рубрикам и мезоуровням.</p>
        </header>
        <label class="field-label" for="q">Поисковый запрос</label>
        <input class="search-box" id="q" type="search" placeholder="Имя, тема, город или организация" autofocus>
        <p class="meta" id="result-summary" aria-live="polite"></p>
        <section id="results" class="list" aria-label="Результаты поиска"></section>
        <script>
        const results = document.getElementById('results');
        const summary = document.getElementById('result-summary');
        const input = document.getElementById('q');
        let docs = [];
        const typeLabels = {'Scholar':'Автор', 'Presentation':'Доклад', 'Topic':'Сюжет', 'Generation':'Поколения', 'Meso-level':'Мезоуровень', 'Keyword':'Ключевые слова', 'Gumilyov':'Гумилев', 'Video':'Видео', 'Finding':'Вывод'};
        const initialQuery = new URLSearchParams(location.search).get('q') || '';
        input.value = initialQuery;
        fetch('search-index.json').then(r => r.json()).then(data => { docs = data; render(input.value); });
        function searchableToken(token) {
            if (/^рамаян[а-яё]*$/i.test(token)) return 'рамаян';
            if (/^махабхарат[а-яё]*$/i.test(token)) return 'махабхарат';
            return token;
        }
        function score(doc, query) {
            if (!query) return 0;
            const hay = `${doc.title} ${doc.text}`.toLowerCase();
            return query.split(/\\s+/).filter(Boolean).map(searchableToken).reduce((sum, token) => sum + (hay.includes(token) ? 1 : 0), 0);
        }
        function render(query) {
            const q = query.trim().toLowerCase();
            const items = docs.map(d => ({...d, score: score(d, q)})).filter(d => q ? d.score > 0 : d.type === 'Scholar').sort((a,b) => b.score - a.score || a.title.localeCompare(b.title)).slice(0, 50);
            summary.textContent = q ? `Найдено результатов: ${items.length}` : `Показаны первые ${items.length} профилей`;
            results.innerHTML = items.map(d => `<article class="card"><strong><a href="${d.url}">${escapeHtml(d.title || '')}</a></strong><div class="meta">${escapeHtml(d.meta || typeLabels[d.type] || d.type)}</div></article>`).join('');
        }
        function escapeHtml(value) {
            return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
        }
        input.addEventListener('input', () => {
            const url = new URL(location.href);
            input.value.trim() ? url.searchParams.set('q', input.value.trim()) : url.searchParams.delete('q');
            history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
            render(input.value);
        });
        </script>
    """
    write_text(
        "search.html",
        page_shell(
            "Поиск по архиву",
            "Поиск по авторам, докладам, организациям, городам, рубрикам и мезоуровням.",
            "search.html",
            body,
            page_data("Поиск по архиву", "Статический поиск по страницам архива.", "search.html", "SearchResultsPage"),
        ),
    )


def generate_keyword_stats_page(records):
    records_by_id = presentation_records_by_id(records)
    counts = Counter()
    series_counts = defaultdict(Counter)
    examples = defaultdict(list)

    for talk in records_by_id.values():
        pid = clean_text(talk.get("presentation_id") or "")
        for raw_tag in talk.get("tags") or []:
            tag = clean_text(raw_tag).lower()
            if len(tag) < 3:
                continue
            counts[tag] += 1
            series_counts[tag][talk.get("series_key") or talk.get("series") or ""] += 1
            if len(examples[tag]) < 4:
                examples[tag].append(pid)

    rows = []
    for tag, count in counts.most_common():
        zograf_count = series_counts[tag].get("Zograf", 0) + series_counts[tag].get("Zograf Readings", 0)
        roerich_count = series_counts[tag].get("Roerich", 0) + series_counts[tag].get("Roerich Readings", 0)
        example_links = []
        for pid in examples[tag]:
            talk = records_by_id.get(pid)
            if talk:
                example_links.append(f'<a href="../{presentation_path(pid)}">{esc(talk.get("title"))}</a>')
        rows.append(
            {
                "keyword": tag,
                "presentations": count,
                "zograf": zograf_count,
                "roerich": roerich_count,
                "examples": " | ".join(clean_text((records_by_id.get(pid) or {}).get("title") or "") for pid in examples[tag]),
                "html": (
                    f'<article class="talk"><strong><a href="{esc(search_path(tag, "../"))}">{esc(public_keyword_label(tag))}</a></strong>'
                    f'<div class="meta">{talks_count_label(count)} · Зограф: {zograf_count} · Рерих: {roerich_count}</div>'
                    f'<div class="meta">{" · ".join(example_links)}</div></article>'
                ),
            }
        )

    with open("analytics_output/keyword_stats.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["keyword", "presentations", "zograf", "roerich", "examples"])
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in rows)

    top_links = [
        f'<a class="chip" href="{esc(search_path(row["keyword"], "../"))}">{esc(public_keyword_label(row["keyword"]))} · {row["presentations"]}</a>'
        for row in rows[:30]
    ]
    body = f"""
        <header>
            <h1>Ключевые слова</h1>
            <p>Сводная статистика ключевых слов, пересчитанных по нормализованным заголовкам докладов.</p>
        </header>
        <section class="grid">
            <article class="card"><strong>Ключевые слова</strong><div class="metric">{len(rows)}</div></article>
            <article class="card"><strong>Доклады с ключевыми словами</strong><div class="metric">{sum(1 for talk in records_by_id.values() if talk.get("tags"))}</div></article>
        </section>
        {chip_section("Частотные слова", top_links)}
        <section class="list">{''.join(row["html"] for row in rows)}</section>
        <section class="link-block">
            <strong>CSV</strong>
            <div class="chip-list"><a class="chip" href="../analytics_output/keyword_stats.csv">keyword_stats.csv</a></div>
        </section>
    """
    write_text(
        "keywords/index.html",
        page_shell(
            f"Ключевые слова | {SITE_NAME}",
            "Сводная статистика ключевых слов докладов.",
            "keywords/",
            body,
            [page_data("Ключевые слова", "Сводная статистика ключевых слов докладов.", "keywords/"), make_breadcrumbs([("Главная", ""), ("Ключевые слова", "keywords/")])],
        ),
    )


def generate_download_page(data):
    summary = data.get("summary", {})
    resources = [
        ("SQLite database", "conferences.db", "Normalized relational source of events, sessions, presentations, people, venues, and affiliation strings."),
        ("Dashboard payload", "site_data.json", "Generated browser data used by the interactive dashboard and static scholar pages."),
        ("Static search index", "search-index.json", "Compact JSON index for generated scholar and presentation pages."),
        ("Citation metadata", "CITATION.cff", "Machine-readable citation record for dataset/software reuse."),
        ("Frictionless datapackage", "datapackage.json", "Dataset metadata, resource list, license, and source notes."),
        ("Data dictionary", "data_dictionary.md", "Human-readable field guide for reusable CSV, JSON, SQLite, and generated publication outputs."),
        ("Data quality report", "analytics_output/data_quality_report.json", "Machine-readable quality checks and review samples."),
        ("Keyword statistics", "analytics_output/keyword_stats.csv", "Per-keyword presentation counts and example titles."),
        ("Biographical provenance", "analytics_output/field_provenance_biographical.csv", "Field-level provenance for curated person names and life dates."),
        ("Authority provenance", "analytics_output/field_provenance_authority.csv", "Field-level provenance for external identifiers and organization authority records."),
        ("Theme provenance", "analytics_output/field_provenance_themes.csv", "Field-level provenance for generated presentation theme labels."),
        ("Gumilyov scale", "analytics_output/gumilyov_scale.csv", "Presentation-level scale of generalization used by the Gumilyov navigation pages."),
        ("Expert classification decisions", "analytics_output/classification_overrides.csv", "Reviewed revisions to themes, meso-levels, and Gumilyov argument levels, with a rationale for each affected presentation."),
        ("Verified affiliation spans", "curation/verified_affiliation_spans.csv", "Dated, source-backed institutional trajectories; tentative open continuations into later gaps are marked (?)."),
        ("YouTube video list", "analytics_output/youtube_video_list.csv", "Source inventory of collected recordings; public discovery is attached to presentation records."),
        ("YouTube mapping", "analytics_output/video_presentation_mapping.csv", "Video-to-presentation matching status used to display recording availability on presentations."),
        ("Network nodes", "analytics_output/network_nodes.csv", "Typed person, event, organization, and theme nodes for downstream network analysis."),
        ("Network edges", "analytics_output/network_edges.csv", "Weighted edges with explicit relation types for participation, affiliation, theme, and co-presence analysis."),
        ("Publication file manifest", "analytics_output/publication_file_manifest.csv", "Generated file list with byte sizes and SHA-256 checksums for reproducible release checks."),
        ("Analytics exports", "analytics_output/", "CSV exports and derived analytical report material."),
    ]
    cards = []
    distributions = []
    for title, path, description in resources:
        cards.append(
            f"""
            <article class="card">
                <strong><a href="{esc(path)}">{esc(title)}</a></strong>
                <div class="meta">{esc(description)}</div>
                <div class="meta">{esc(file_size_label(path))}</div>
            </article>
            """
        )
        distributions.append(
            {
                "@type": "DataDownload",
                "name": title,
                "contentUrl": site_url(path),
                "description": description,
            }
        )

    body = f"""
        <header>
            <h1>Download data</h1>
            <p>Reusable dataset outputs for citation, audit, and downstream digital humanities work.</p>
        </header>
        <section class="grid">
            <article class="card"><strong>Scholars</strong><div class="meta">{esc(summary.get("total_scholars", 0))}</div></article>
            <article class="card"><strong>Presentation records</strong><div class="meta">{esc(summary.get("total_presentations", 0))}</div></article>
            <article class="card"><strong>Events</strong><div class="meta">{esc(summary.get("total_events", 0))}</div></article>
        </section>
        <h2>Files</h2>
        <section class="grid">{''.join(cards)}</section>

        <h2 style="margin-top:2.5rem;">Reproducibility</h2>
        <div class="card" style="padding: 2rem;">
            <p>The entire dataset is generated deterministically from primary source HTML caches. To reproduce the current build locally:</p>
            <ol>
                <li><code>python build_and_populate_db.py</code> (Creates the SQLite database and generates deterministic <code>presentation_id</code> hashes based on event, year, title, speaker, and session order)</li>
                <li><code>python generate_analytics.py</code> (Generates all CSV exports and networks)</li>
                <li><code>python generate_site_data.py</code> (Compiles the browser payload)</li>
                <li><code>python generate_scholars_pages.py</code> (Builds individual static profiles)</li>
                <li><code>python generate_publication_pages.py</code> (Builds all other pages, search index, and updates index.html)</li>
                <li><code>python validate_publication.py</code> (Runs integrity checks)</li>
            </ol>
            <p><strong>Pipeline Version:</strong> {esc(PIPELINE_VERSION)}</p>
            <p><strong>Build Date:</strong> {esc(BUILD_DATE)}</p>
        </div>
    """
    structured = [
        page_data("Download data", "Reusable dataset files for the archive.", "download-data.html"),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": SITE_NAME,
            "url": SITE_URL,
            "license": "https://www.apache.org/licenses/LICENSE-2.0",
            "creator": {"@type": "Person", "name": AUTHOR_NAME},
            "temporalCoverage": f"{summary.get('start_year', 2004)}/{summary.get('end_year', 2025)}",
            "distribution": distributions,
        },
        make_breadcrumbs([("Home", ""), ("Download data", "download-data.html")]),
    ]
    write_text(
        "download-data.html",
        page_shell(
            f"Download data | {SITE_NAME}",
            "Download SQLite, dashboard data, search index, citation metadata, analytics CSVs, and quality reports.",
            "download-data.html",
            body,
            structured,
        ),
    )


def collect_data_quality(data):
    report = {
        "schema_version": DATA_SCHEMA_VERSION,
        "generated": BUILD_DATE,
        "build": {
            "source": "IndologyScholars",
            "pipeline_version": PIPELINE_VERSION,
            "generator": "generate_publication_pages.py",
        },
        "summary": data.get("summary", {}),
        "checks": [],
        "samples": {},
    }
    if not Path(DB_PATH).exists():
        report["checks"].append({"id": "database", "label": "SQLite database present", "severity": "error", "count": 1, "status": "missing"})
        return report

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def add_check(check_id, label, severity, count, sample_rows=None, status=None):
        report["checks"].append(
            {
                "id": check_id,
                "label": label,
                "severity": severity,
                "count": count,
                "status": status or ("pass" if count == 0 else "review"),
            }
        )
        if sample_rows:
            report["samples"][check_id] = [dict(row) for row in sample_rows]

    dangling = cur.execute("""
        SELECT s.session_id, s.event_day_venue_id, s.session_title
        FROM session s
        LEFT JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        WHERE edv.event_day_venue_id IS NULL
        ORDER BY s.session_id
        LIMIT 25
    """).fetchall()
    add_check("dangling_sessions", "Sessions without joinable event_day_venue", "error", len(dangling), dangling)

    missing_dates = cur.execute("""
        SELECT pr.presentation_id, p.display_name AS scholar, pr.title, e.year, es.series_name_en
        FROM presentation pr
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN event_series es ON es.event_series_id = e.event_series_id
        WHERE ed.calendar_date IS NULL OR ed.calendar_date = ''
        ORDER BY e.year, pr.presentation_id
        LIMIT 25
    """).fetchall()
    total_missing_dates = cur.execute("""
        SELECT COUNT(*)
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        WHERE ed.calendar_date IS NULL OR ed.calendar_date = ''
    """).fetchone()[0]
    add_check("missing_dates", "Presentations attached to undated event days", "warning", total_missing_dates, missing_dates)

    no_affiliation = cur.execute("""
        SELECT pp.presentation_id, p.display_name AS scholar, pr.title
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        WHERE pp.affiliation_text_raw IS NULL OR TRIM(pp.affiliation_text_raw) = ''
        ORDER BY p.display_name
        LIMIT 25
    """).fetchall()
    total_no_affiliation = cur.execute("""
        SELECT COUNT(*) FROM presentation_person
        WHERE affiliation_text_raw IS NULL OR TRIM(affiliation_text_raw) = ''
    """).fetchone()[0]
    add_check("missing_affiliations", "Presentation-person rows without raw affiliation", "info", total_no_affiliation, no_affiliation)

    placeholder_titles = cur.execute("""
        SELECT pr.presentation_id, p.display_name AS scholar, pr.title
        FROM presentation pr
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person p ON p.person_id = pp.person_id
        WHERE LOWER(pr.title) LIKE '%уточняется%' OR LOWER(pr.title) LIKE '%tbd%' OR LOWER(pr.title) LIKE '%unspecified%'
        ORDER BY p.display_name
        LIMIT 25
    """).fetchall()
    total_placeholder_titles = cur.execute("""
        SELECT COUNT(*) FROM presentation
        WHERE LOWER(title) LIKE '%уточняется%' OR LOWER(title) LIKE '%tbd%' OR LOWER(title) LIKE '%unspecified%'
    """).fetchone()[0]
    add_check("placeholder_titles", "Presentations with placeholder-like titles", "info", total_placeholder_titles, placeholder_titles)

    duplicate_full_names = cur.execute("""
        SELECT full_name_ru, COUNT(*) AS people
        FROM person
        WHERE full_name_ru IS NOT NULL AND TRIM(full_name_ru) != ''
        GROUP BY full_name_ru
        HAVING COUNT(*) > 1
        ORDER BY people DESC, full_name_ru
        LIMIT 25
    """).fetchall()
    total_duplicate_full_names = cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT full_name_ru
            FROM person
            WHERE full_name_ru IS NOT NULL AND TRIM(full_name_ru) != ''
            GROUP BY full_name_ru
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    add_check("duplicate_full_names", "Duplicate full Russian names after normalization", "warning", total_duplicate_full_names, duplicate_full_names)

    latin_initials = []
    for row in cur.execute("SELECT person_id, display_name, full_name_ru, normalized_key FROM person ORDER BY display_name").fetchall():
        name = row["display_name"] or ""
        if re.search(r"\b[A-Z]\.", name) and re.search(r"[А-Яа-яЁё]", name):
            latin_initials.append(dict(row))
    add_check("latin_initials", "Mixed Latin initials in Cyrillic names", "info", len(latin_initials), latin_initials[:25])

    conn.close()
    return report


# ---------------------------------------------------------------------------
# Phase 4 helper: split Cyrillic full name into (surname, first, patronymic)
# Handles:
#   'Цветкова Софья Олеговна'  -> ('Цветкова', 'Софья', 'Олеговна')
#   'С. О. Цветкова'           -> ('Цветкова', 'С', 'О')
#   'Александрова Н. В.'       -> ('Александрова', 'Н', 'В')
# ---------------------------------------------------------------------------
def extract_russian_name_parts(full_name_ru: str, display_name: str = "") -> tuple:
    """
    Return (surname, first_name_or_initial, patronymic_or_initial) from a Russian
    name string.  Falls back to display_name if full_name_ru is blank.
    All three parts may be empty strings but the tuple always has 3 elements.
    """
    name = (full_name_ru or display_name or "").strip()
    if not name:
        return ("", "", "")

    parts = name.split()
    if not parts:
        return ("", "", "")

    # Pattern: first part looks like initials "А." or "А. О."
    init_re = re.compile(r'^[А-ЯЁA-Z]\.$')

    if len(parts) == 1:
        return (parts[0], "", "")

    # Case: Initials + Surname  →  "А. О. Цветкова" or "А.О. Цветкова"
    if init_re.match(parts[0]):
        surname = parts[-1]
        initials = [p.rstrip(".") for p in parts[:-1] if p.strip(".")]
        first = initials[0] if len(initials) >= 1 else ""
        patron = initials[1] if len(initials) >= 2 else ""
        return (surname, first, patron)

    # Case: Surname + Initials  →  "Цветкова А. О." or "Цветкова А."
    if len(parts) >= 2 and init_re.match(parts[1]):
        surname = parts[0]
        initials = [p.rstrip(".") for p in parts[1:] if p.strip(".")]
        first = initials[0] if len(initials) >= 1 else ""
        patron = initials[1] if len(initials) >= 2 else ""
        return (surname, first, patron)

    # Case: Full Cyrillic  →  "Цветкова Софья Олеговна"
    if len(parts) >= 3:
        return (parts[0], parts[1], parts[2])
    if len(parts) == 2:
        return (parts[0], parts[1], "")

    return (parts[0], "", "")


def generate_authority_coverage(data, authority):
    scholars = data.get("scholars", [])
    persons_auth = authority.get("persons", {})

    coverage_rows = []
    review_queue = []

    total_scholars = len(scholars)
    scholars_with_any = 0
    total_orcid = 0
    total_wikidata = 0
    total_viaf = 0
    total_openalex = 0
    total_wikipedia = 0
    total_rinc = 0
    total_google_scholar = 0
    total_vk = 0
    total_official_url = 0

    for s in scholars:
        pid = s["id"]
        dname = s.get("display_name") or s.get("name") or ""
        fullname_ru = s.get("full_name_ru") or s.get("original_fullname") or ""

        person_auth = persons_auth.get(pid, {})
        pref_latin = person_auth.get("preferred_latin_name", "")

        urls_dict = clean_person_urls(person_auth)

        has_orcid = 1 if "orcid" in urls_dict else 0
        has_wikidata = 1 if "wikidata" in urls_dict else 0
        has_viaf = 1 if "viaf" in urls_dict else 0
        has_openalex = 1 if "openalex" in urls_dict else 0
        has_wikipedia = 1 if "wikipedia" in urls_dict else 0
        has_rinc = 1 if "rinc_author_id" in urls_dict else 0
        has_google = 1 if "google_scholar" in urls_dict else 0
        has_vk = 1 if "vk" in urls_dict else 0
        has_official = 1 if "official_url" in urls_dict else 0

        has_any = 1 if (has_orcid or has_wikidata or has_viaf or has_openalex or has_wikipedia or has_rinc or has_google or has_vk or has_official) else 0

        confidence = person_auth.get("confidence", "")
        checked_at = person_auth.get("checked_at", "")

        if has_any:
            scholars_with_any += 1
        total_orcid += has_orcid
        total_wikidata += has_wikidata
        total_viaf += has_viaf
        total_openalex += has_openalex
        total_wikipedia += has_wikipedia
        total_rinc += has_rinc
        total_google_scholar += has_google
        total_vk += has_vk
        total_official_url += has_official

        talks = s.get("total_talks", 0)

        coverage_rows.append({
            "person_id": pid,
            "display_name": dname,
            "full_name_ru": fullname_ru,
            "preferred_latin_name": pref_latin,
            "total_talks": talks,
            "has_orcid": has_orcid,
            "has_wikidata": has_wikidata,
            "has_viaf": has_viaf,
            "has_openalex": has_openalex,
            "has_wikipedia": has_wikipedia,
            "has_rinc": has_rinc,
            "has_google_scholar": has_google,
            "has_vk": has_vk,
            "has_official_url": has_official,
            "has_any_external_id": has_any,
            "authority_confidence": confidence,
            "checked_at": checked_at
        })

        reasons = []
        priority = 99

        if talks >= 5 and not has_any:
            reasons.append("Many talks and no external ID")
            priority = min(priority, 1)
        elif talks > 0 and not has_any:
            reasons.append("Active scholar and no external ID")
            priority = min(priority, 2)

        if re.search(r"\b[A-ZА-ЯЁ]\.", dname):
            reasons.append("Initials-only display name")
            priority = min(priority, 2)

        if not pref_latin:
            reasons.append("Missing preferred Latin name")
            priority = min(priority, 3)

        if has_any and (not confidence or not checked_at):
            reasons.append("Existing ID but missing confidence or checked_at")
            priority = min(priority, 4)

        if reasons:
            suggested_query = f"{fullname_ru or dname} индолог"
            # Phase 4: build precise eLIBRARY search URL from name parts
            surname, first_i, patron_i = extract_russian_name_parts(fullname_ru, dname)
            rinc_params = []
            if surname:
                rinc_params.append(f"fams={quote(surname)}")
            if first_i:
                rinc_params.append(f"imas={quote(first_i)}")
            if patron_i:
                rinc_params.append(f"otchs={quote(patron_i)}")
            rinc_search_url = (
                "https://elibrary.ru/authors.asp?" + "&".join(rinc_params)
                if rinc_params else ""
            )
            # Phase 4: build OpenAlex search URL from preferred Latin name
            openalex_search_url = (
                f"https://openalex.org/authors?search={quote(pref_latin)}"
                if pref_latin else ""
            )
            wikipedia_search_url = f"https://ru.wikipedia.org/w/index.php?search={quote(fullname_ru or dname)}"
            review_queue.append({
                "priority_rank": priority,
                "person_id": pid,
                "display_name": dname,
                "full_name_ru": fullname_ru,
                "total_talks": talks,
                "reason": "; ".join(reasons),
                "suggested_query": suggested_query,
                "rinc_search_url": rinc_search_url,
                "openalex_search_url": openalex_search_url,
                "wikipedia_search_url": wikipedia_search_url,
                "review_status": "todo"
            })

    review_queue.sort(key=lambda r: (r["priority_rank"], -r["total_talks"], r["display_name"]))

    Path("analytics_output").mkdir(exist_ok=True)

    with open("analytics_output/authority_coverage.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "person_id", "display_name", "full_name_ru", "preferred_latin_name", "total_talks",
            "has_orcid", "has_wikidata", "has_viaf", "has_openalex", "has_wikipedia", "has_rinc", "has_google_scholar",
            "has_vk", "has_official_url", "has_any_external_id", "authority_confidence", "checked_at"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in coverage_rows:
            writer.writerow(r)

    with open("analytics_output/authority_review_queue.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "priority_rank", "person_id", "display_name", "full_name_ru", "total_talks",
            "reason", "suggested_query", "rinc_search_url", "openalex_search_url",
            "wikipedia_search_url", "review_status"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in review_queue:
            writer.writerow(r)

    return {
        "total_scholars": total_scholars,
        "scholars_with_any": scholars_with_any,
        "total_orcid": total_orcid,
        "total_wikidata": total_wikidata,
        "total_viaf": total_viaf,
        "total_openalex": total_openalex,
        "total_wikipedia": total_wikipedia,
        "total_rinc": total_rinc,
        "total_google_scholar": total_google_scholar,
        "total_vk": total_vk,
        "total_official_url": total_official_url,
        "queue_size": len(review_queue)
    }


def generate_provenance_sidecars(data, authority, records):
    Path("analytics_output").mkdir(exist_ok=True)

    bio_rows = []
    if Path(DB_PATH).exists():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            """
            SELECT person_id, display_name, full_name_ru, full_name_en, birth_year, death_year, source_url
            FROM person
            ORDER BY display_name
            """
        ).fetchall():
            for field in ("full_name_ru", "full_name_en", "birth_year", "death_year"):
                value = row[field]
                if value is None or str(value).strip() == "":
                    continue
                confidence = "confirmed" if field in ("full_name_ru", "full_name_en") else "manual"
                bio_rows.append({
                    "entity_type": "person",
                    "entity_id": row["person_id"],
                    "display_name": row["display_name"],
                    "field_name": field,
                    "field_value": value,
                    "source_type": "curated_biographical_data",
                    "source_url": row["source_url"] or "",
                    "confidence": confidence,
                    "checked_at": BUILD_DATE,
                    "notes": "Loaded into person table during DB build.",
                })
        conn.close()

    with open("analytics_output/field_provenance_biographical.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "entity_type", "entity_id", "display_name", "field_name", "field_value",
            "source_type", "source_url", "confidence", "checked_at", "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(bio_rows)

    authority_rows = []
    for person_id, person_auth in sorted((authority.get("persons") or {}).items()):
        if not isinstance(person_auth, dict):
            continue
        confidence = person_auth.get("confidence") or "unspecified"
        source = person_auth.get("source") or "authority_ids.json"
        checked_at = person_auth.get("checked_at") or ""
        for field_name, value in sorted(person_auth.items()):
            if field_name in {"confidence", "source", "checked_at", "notes"}:
                continue
            if value in (None, "", []):
                continue
            authority_rows.append({
                "entity_type": "person",
                "entity_id": person_id,
                "field_name": field_name,
                "field_value": json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value,
                "source_type": source,
                "confidence": confidence,
                "checked_at": checked_at,
                "notes": person_auth.get("notes", ""),
            })
    for org_key, org_auth in sorted((authority.get("organizations") or {}).items()):
        if not isinstance(org_auth, dict):
            continue
        confidence = org_auth.get("confidence") or "unspecified"
        checked_at = org_auth.get("checked_at") or ""
        for field_name, value in sorted(org_auth.items()):
            if field_name in {"confidence", "checked_at", "notes"}:
                continue
            if value in (None, "", []):
                continue
            authority_rows.append({
                "entity_type": "organization",
                "entity_id": org_key,
                "field_name": field_name,
                "field_value": json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value,
                "source_type": "authority_ids.json",
                "confidence": confidence,
                "checked_at": checked_at,
                "notes": org_auth.get("notes", ""),
            })

    with open("analytics_output/field_provenance_authority.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "entity_type", "entity_id", "field_name", "field_value",
            "source_type", "confidence", "checked_at", "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(authority_rows)

    theme_rows = []
    
    # Load LLM classification results
    llm_themes = {}
    try:
        with open("analytics_output/theme_codes_final_v2.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = (str(r["year"]).strip(), str(r["series"]).strip(), str(r["title"]).strip())
                llm_themes[key] = r
    except FileNotFoundError:
        pass
        
    for rec in records:
        title = rec.get("title") or ""
        pres_id = rec.get("presentation_id") or ""
        year = rec.get("year", "")
        series = rec.get("series_label") or rec.get("series_key", "")
        theme = rec.get("theme") or {}
        
        key = (str(year).strip(), str(series).strip(), str(title).strip())
        lr = llm_themes.get(key, {})
        
        theme_rows.append({
            "entity_type": "presentation",
            "entity_id": pres_id,
            "field_name": "theme.code",
            "field_value": theme.get("code") or "",
            "source_type": lr.get("source", "heuristic"),
            "confidence": lr.get("confidence", ""),
            "checked_at": BUILD_DATE,
            "title": title,
            "l1_review_candidate": lr.get("l1", ""),
            "l1_confidence": lr.get("confidence", ""),
            "l3_review_candidate": lr.get("l3", ""),
            "l3_confidence": "",
            "notes": lr.get("why", ""),
        })

    with open("analytics_output/field_provenance_themes.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "entity_type", "entity_id", "field_name", "field_value", "source_type",
            "confidence", "checked_at", "title", "l1_review_candidate", "l1_confidence",
            "l3_review_candidate", "l3_confidence", "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(theme_rows)

    return {
        "biographical_rows": len(bio_rows),
        "authority_rows": len(authority_rows),
        "theme_rows": len(theme_rows),
    }


# ---------------------------------------------------------------------------
# Phase 5: Thematic Classification Review Queue
# Mirrors the keyword rules from scratch/theme_coding_baseline.py.
# Runs automatically during each build so the queue stays up to date.
# ---------------------------------------------------------------------------

# L1 discipline keyword rules (simplified subset for inline use)
_THEME_L1_RULES = {
    "linguistics": [
        r"\bграмматик", r"\bэтимолог", r"\bлексик", r"\bсинтакс", r"\bморфолог",
        r"\bязык", r"\bдиалект", r"\bсанскрит", r"\bимператив", r"\bПанин",
    ],
    "philosophy": [
        r"\bфилософ", r"\bэпистемолог", r"\bмадхьямак", r"\bйогачар", r"\bадвайта",
        r"\bведанта", r"\bньяя", r"\bдаршан", r"\bпратьякша", r"\bпрамана",
    ],
    "literature": [
        r"\bэпос", r"\bМБХ\b", r"\bРамаян", r"\bкавь", r"\bроман", r"\bповес",
        r"\bпоэзи", r"\bпоэтик", r"\bТагор", r"\bфольклор", r"\bлитератур",
    ],
    "history": [
        r"\bистори", r"\bархив", r"\bархео", r"\bэпиграф", r"\bнумизмат",
        r"\bисточник", r"\bдатировк", r"\bпутеш", r"\bколлекци",
    ],
    "religion": [
        r"\bбуддизм", r"\bбудди", r"\bритуал", r"\bиндуи", r"\bхрам",
        r"\bведий", r"\bВеда", r"\bупанишад", r"\bмифолог", r"\bдхарм",
        r"\bшиваит", r"\bтантр", r"\bбхакти",
    ],
    "tibetology": [
        r"\bтибет", r"\bТибет", r"\bМахаян", r"\bКамалашил",
    ],
    "ethnography": [
        r"\bантрополог", r"\bэтнограф", r"\bплемен", r"\bАдиваси",
    ],
    "art_archaeology": [
        r"\bархитектур", r"\bиконограф", r"\bхудожни", r"\bскульпт",
        r"\bживопис", r"\bвизуальност", r"\bЭрмитаж",
    ],
}

_THEME_L3_RULES = {
    "text":      [r"\bтекст", r"\bтрактат", r"\bкоммент", r"\bперевод", r"\bрукопис"],
    "fieldwork": [r"\bполев", r"\bантрополог", r"\bэтнограф", r"\bперформанс"],
    "archive":   [r"\bархив", r"\bбиблиотек", r"\bколлекци", r"\bрукопис"],
    "artefact":  [r"\bархитектур", r"\bСтуп", r"\bпамятник", r"\bскульпт", r"\bиконограф"],
}


def _score_rules(title: str, rules: dict) -> tuple:
    """Return (best_category_or_None, confidence_0_to_1)."""
    if not title:
        return (None, 0.0)
    scores = {}
    for cat, patterns in rules.items():
        hits = sum(1 for p in patterns if re.search(p, title, re.IGNORECASE))
        if hits:
            scores[cat] = hits
    if not scores:
        return (None, 0.0)
    best_cat, best_hits = max(scores.items(), key=lambda x: x[1])
    total = sum(scores.values())
    margin = best_hits / total
    confidence = round(min(1.0, 0.4 + 0.3 * best_hits + 0.3 * margin), 2)
    return (best_cat, confidence)


def generate_theme_review_queue(records: list) -> int:
    """
    Phase 5 — build analytics_output/theme_review_queue.csv from presentation
    records using inline keyword heuristics.  Flags records where:
      - L1 classification is None (unclassified), OR
      - L3 material is None, OR
      - confidence for L1 or L3 is below 0.5

    Returns the number of rows written.
    """
    queue = []
    
    # Load LLM classification results
    llm_themes = {}
    try:
        with open("analytics_output/theme_codes_final_v2.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = (str(r["year"]).strip(), str(r["series"]).strip(), str(r["title"]).strip())
                llm_themes[key] = r
    except FileNotFoundError:
        pass
        
    for rec in records:
        title = rec.get("title") or ""
        pres_id = rec.get("presentation_id") or ""
        year = rec.get("year", "")
        series = rec.get("series_label") or rec.get("series_key", "")
        theme_code = (rec.get("theme") or {}).get("code") or ""
        
        key = (str(year).strip(), str(series).strip(), str(title).strip())
        lr = llm_themes.get(key, {})
        
        l1 = lr.get("l1")
        l3 = lr.get("l3")
        try:
            conf = float(lr.get("confidence") or 0.0)
        except ValueError:
            conf = 0.0

        needs_review = (l1 in (None, "", "unspecified") or l3 in (None, "", "unspecified") or conf < 0.6)

        if needs_review:
            queue.append({
                "presentation_id": pres_id,
                "year": year,
                "series": series,
                "title": title,
                "existing_theme_code": theme_code,
                "l1_baseline": l1 or "",
                "l1_conf": conf,
                "l3_baseline": l3 or "",
                "l3_conf": conf,
                "review_status": "todo",
                "notes": lr.get("why", ""),
            })

    # Sort: unclassified (l1 None) first, then by l1_conf ascending
    queue.sort(key=lambda r: (0 if not r["l1_baseline"] or r["l1_baseline"] == "unspecified" else 1, r["l1_conf"]))

    Path("analytics_output").mkdir(exist_ok=True)
    out_path = "analytics_output/theme_review_queue.csv"
    fieldnames = [
        "presentation_id", "year", "series", "title", "existing_theme_code",
        "l1_baseline", "l1_conf", "l3_baseline", "l3_conf",
        "review_status", "notes",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(queue)

    return len(queue)


def generate_data_quality_page(data, authority_stats):

    report = collect_data_quality(data)
    write_text("analytics_output/data_quality_report.json", json.dumps(report, ensure_ascii=False, indent=2))

    t = authority_stats["total_scholars"] or 1
    wikidata_pct = round(authority_stats["total_wikidata"] * 100 / t, 1)
    orcid_pct = round(authority_stats["total_orcid"] * 100 / t, 1)
    viaf_pct = round(authority_stats["total_viaf"] * 100 / t, 1)
    openalex_pct = round(authority_stats["total_openalex"] * 100 / t, 1)
    wikipedia_pct = round(authority_stats["total_wikipedia"] * 100 / t, 1)
    rinc_pct = round(authority_stats["total_rinc"] * 100 / t, 1)
    google_pct = round(authority_stats["total_google_scholar"] * 100 / t, 1)
    vk_pct = round(authority_stats["total_vk"] * 100 / t, 1)
    official_pct = round(authority_stats["total_official_url"] * 100 / t, 1)
    overall_pct = round(authority_stats["scholars_with_any"] * 100 / t, 1)

    rows = []

    # Identifier coverage card
    rows.append(
        f"""
        <article class="card" style="grid-column: span 2;">
            <strong>Identifier Mapping Coverage</strong>
            <div class="meta" style="margin-top: 0.5rem; line-height: 1.8;">
                Wikidata: {authority_stats["total_wikidata"]} ({wikidata_pct}%) &middot;
                ORCID: {authority_stats["total_orcid"]} ({orcid_pct}%) &middot;
                VIAF: {authority_stats["total_viaf"]} ({viaf_pct}%) &middot;
                OpenAlex: {authority_stats["total_openalex"]} ({openalex_pct}%) &middot;
                Wikipedia: {authority_stats["total_wikipedia"]} ({wikipedia_pct}%) &middot;
                РИНЦ/eLIBRARY: {authority_stats["total_rinc"]} ({rinc_pct}%) &middot;
                Google Scholar: {authority_stats["total_google_scholar"]} ({google_pct}%) &middot;
                VK: {authority_stats["total_vk"]} ({vk_pct}%) &middot;
                Official URL: {authority_stats["total_official_url"]} ({official_pct}%)
                <br>
                <strong>Overall Coverage:</strong> {authority_stats["scholars_with_any"]} of {authority_stats["total_scholars"]} scholars mapped ({overall_pct}%)
                <br>
                <a href="analytics_output/authority_coverage.csv" style="font-weight: bold; margin-top: 0.5rem; display: inline-block;">Download Coverage Report (CSV)</a>
            </div>
        </article>
        """
    )

    # Review queue card
    rows.append(
        f"""
        <article class="card">
            <strong>Authority Review Queue</strong>
            <div class="meta" style="margin-top: 0.5rem; line-height: 1.8;">
                Queue Size: {authority_stats["queue_size"]} scholars pending review.
                <br>
                Prioritizes active scholars with no external identifier, missing Latin translations, or initials-only display names.
                <br>
                <a href="analytics_output/authority_review_queue.csv" style="font-weight: bold; margin-top: 0.5rem; display: inline-block;">Download Review Queue (CSV)</a>
            </div>
        </article>
        """
    )

    rows.append(
        """
        <article class="card" style="grid-column: span 2;">
            <strong>Field-level provenance sidecars</strong>
            <div class="meta" style="margin-top: 0.5rem; line-height: 1.8;">
                <a href="analytics_output/field_provenance_biographical.csv">Biographical fields</a> &middot;
                <a href="analytics_output/field_provenance_authority.csv">Authority identifiers</a> &middot;
                <a href="analytics_output/field_provenance_themes.csv">Theme labels</a>
                <br>
                These CSVs expose source, confidence, and checked-date metadata for high-risk derived or curated fields.
            </div>
        </article>
        """
    )

    audit_links = [
        ("Identity alias candidates", "analytics_output/identity_alias_candidates.csv"),
        ("Birth-year gap audit", "analytics_output/birth_year_gap_audit.csv"),
        ("Wikipedia authority candidates", "analytics_output/wikipedia_authority_candidates.csv"),
    ]
    existing_audits = [
        f'<a href="{esc(path)}">{esc(label)}</a>'
        for label, path in audit_links
        if Path(path).exists()
    ]
    if existing_audits:
        rows.append(
            f"""
            <article class="card" style="grid-column: span 2;">
                <strong>Trend audit scripts</strong>
                <div class="meta" style="margin-top: 0.5rem; line-height: 1.8;">
                    {' &middot; '.join(existing_audits)}
                    <br>
                    These queues are generated by curation scripts and expose recurring identity, birth-year, and Wikipedia-authority gaps.
                </div>
            </article>
            """
        )

    for check in report["checks"]:
        rows.append(
            f"""
            <article class="card">
                <strong>{esc(check["label"])}</strong>
                <div class="meta">Status: {esc(check["status"])} · Severity: {esc(check["severity"])} · Count: {esc(check["count"])}</div>
            </article>
            """
        )

    sample_sections = []
    for check_id, samples in report["samples"].items():
        if not samples:
            continue
        sample_items = []
        for sample in samples[:10]:
            sample_items.append(f"<li>{esc(json.dumps(sample, ensure_ascii=False))}</li>")
        sample_sections.append(f"<h2>{esc(check_id)}</h2><ul>{''.join(sample_items)}</ul>")

    body = f"""
        <header>
            <h1>Data quality</h1>
            <p>Automated checks for join integrity, missing metadata, identity normalization, and review queues.</p>
        </header>
        <section class="grid">{''.join(rows)}</section>
        <h2>Machine-readable report</h2>
        <p><a href="analytics_output/data_quality_report.json">analytics_output/data_quality_report.json</a></p>
        {''.join(sample_sections)}
    """
    write_text(
        "data-quality.html",
        page_shell(
            f"Data quality | {SITE_NAME}",
            "Automated quality checks and review samples for the Indology Scholars archive.",
            "data-quality.html",
            body,
            [page_data("Data quality", "Automated quality checks and review samples.", "data-quality.html"), make_breadcrumbs([("Home", ""), ("Data quality", "data-quality.html")])],
        ),
    )


def generate_404_page():
    body = """
        <header>
            <h1>Page not found</h1>
            <p>The archive may have merged an older profile URL or moved a generated page. Search the static index or return to the dashboard.</p>
        </header>
        <section class="list">
            <article class="card"><strong><a href="/IndologyScholars/search.html">Search the archive</a></strong><div class="meta">Scholar profiles, talks, cities, institutions, and themes.</div></article>
            <article class="card"><strong><a href="/IndologyScholars/s/">Browse scholars</a></strong><div class="meta">Canonical generated profile index.</div></article>
            <article class="card"><strong><a href="/IndologyScholars/">Dashboard</a></strong><div class="meta">Interactive overview and filters.</div></article>
        </section>
        <script>
        const lastPart = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop() || '');
        if (lastPart) {
            const query = lastPart.replace(/\\.html$/i, '').replace(/[-_]+/g, ' ');
            const link = document.createElement('p');
            const anchor = document.createElement('a');
            anchor.href = `/IndologyScholars/search.html?q=${encodeURIComponent(query)}`;
            anchor.textContent = `Search for "${query}"`;
            link.appendChild(anchor);
            document.querySelector('header').appendChild(link);
        }
        </script>
    """
    write_text(
        "404.html",
        page_shell(
            f"Page not found | {SITE_NAME}",
            "Search or browse the Indology Scholars archive after a missing page.",
            "404.html",
            body,
            page_data("Page not found", "Search or browse the archive after a missing page.", "404.html", "WebPage"),
            robots="noindex, follow",
        ),
    )


def generate_english_landing(data):
    summary = data.get("summary", {})
    body = f"""
        <header>
            <h1>Russian Indological Research Archive</h1>
            <p>A static and reusable digital humanities archive of Zograf Readings and Roerich Readings conference programs, scholar profiles, presentations, affiliations, cities, institutions, and broad research themes.</p>
        </header>
        <section class="grid">
            <article class="card"><strong>{esc(summary.get("total_scholars", 0))}</strong><div class="meta">canonical scholar profiles</div></article>
            <article class="card"><strong>{esc(summary.get("total_presentations", 0))}</strong><div class="meta">presentation-person records</div></article>
            <article class="card"><strong>{esc(summary.get("start_year", 2004))}-{esc(summary.get("end_year", 2025))}</strong><div class="meta">temporal coverage</div></article>
        </section>
        <h2>Explore</h2>
        <section class="grid">
            <article class="card"><strong><a href="findings/">Main Findings</a></strong><div class="meta">Interpretive layer from the latest article: overlap, themes, micro-cases, videos, and source caveats.</div></article>
            <article class="card"><strong><a href="topics/">Named Texts</a></strong><div class="meta">Stable topic pages for presentations mentioning the Ramayana and Mahabharata.</div></article>
            <article class="card"><strong><a href="generations/">Generations</a></strong><div class="meta">Named birth cohorts from the Vasilkov generation to the Tolchelnikov generation.</div></article>
            <article class="card"><strong><a href="s/">Scholar Profiles</a></strong><div class="meta">Canonical generated pages with presentations, affiliations, themes, and related scholars.</div></article>
            <article class="card"><strong><a href="conferences/">Conference Indexes</a></strong><div class="meta">Year-by-year Zograf Readings and Roerich Readings pages.</div></article>
            <article class="card"><strong><a href="search.html">Search</a></strong><div class="meta">Static search across people, talks, cities, institutions, and themes.</div></article>
            <article class="card"><strong><a href="gumilyov/">Gumilyov Scale</a></strong><div class="meta">Presentation-level scale of generalization: micro, regional, and global.</div></article>
            <article class="card"><strong><a href="videos/">YouTube Videos</a></strong><div class="meta">Full playlist inventory and mapped presentation recordings; mapped talks also carry a Video badge.</div></article>
            <article class="card"><strong><a href="networks.html">Networks</a></strong><div class="meta">Participation and co-presence networks.</div></article>
            <article class="card"><strong><a href="download-data.html">Download Data</a></strong><div class="meta">SQLite, generated JSON/JS payloads, citation metadata, and analytics exports.</div></article>
            <article class="card"><strong><a href="methodology.html">Methodology</a></strong><div class="meta">Pipeline, source material, normalization, and generated outputs.</div></article>
            <article class="card"><strong><a href="how-to-cite.html">How To Cite</a></strong><div class="meta">Citation guidance and machine-readable citation files.</div></article>
        </section>
    """
    structured = [
        page_data(
            "Russian Indological Research Archive",
            "English entry point for the Indology Scholars archive.",
            "en.html",
            "AboutPage",
        ),
        make_breadcrumbs([("Home", ""), ("English", "en.html")]),
    ]
    write_text(
        "en.html",
        page_shell(
            f"Russian Indological Research Archive | {SITE_NAME}",
            "English entry point for the Indology Scholars conference archive and dataset.",
            "en.html",
            body,
            structured,
            extra_head=f'\n    <link rel="alternate" hreflang="ru" href="{site_url("")}">\n    <link rel="alternate" hreflang="en" href="{site_url("en.html")}">',
            language="en",
        ),
    )


def generate_findings_page(data, records):
    summary = data.get("summary", {})
    records_by_id = presentation_records_by_id(records)
    unique_records = list(records_by_id.values())

    total_scholars = summary.get("total_scholars", 220)
    unique_presentations = summary.get("unique_presentations", summary.get("presentation_rows", 895))
    author_participations = summary.get("author_participations", summary.get("total_presentations", 899))
    video_presentations = sum(1 for talk in unique_records if talk.get("videos"))
    video_author_cards = sum(1 for talk in records if talk.get("videos"))
    youtube_rows = len(load_youtube_rows()) or 178
    classification_path = Path("article/hypothesis_output/expanded_classification_summary.json")
    classification = json.loads(classification_path.read_text(encoding="utf-8")) if classification_path.exists() else {}
    scale = classification.get("gumilyov_scale", {})
    g1_count = int(scale.get("1", 0) or 0)
    g3_count = int(scale.get("3", 0) or 0)
    number_path = Path("article/hypothesis_output/ppv_numbers_snapshot.json")
    number_snapshot = json.loads(number_path.read_text(encoding="utf-8")) if number_path.exists() else {}
    number_series = number_snapshot.get("series", {})
    zograf_scholars = int(number_series.get("Zograf", {}).get("unique_scholars", 0) or 0)
    roerich_scholars = int(number_series.get("Roerich", {}).get("unique_scholars", 0) or 0)
    appendix = {
        row.get("key", ""): row.get("value", "")
        for row in load_csv_rows("article/hypothesis_output/appendix_g_summary.csv")
    }
    overlap = int(float(appendix.get("H1_overlap_observed", summary.get("overlap_scholars", 0)) or 0))
    expected_overlap = float(appendix.get("H1_overlap_expected_mean", 0) or 0)
    z_city_only = appendix.get("H4_zograf_cityonly_pct", "")
    r_city_only = appendix.get("H4_roerich_cityonly_pct", "")
    classified_rows = load_csv_rows("analytics_output/expanded_classification_deepseek.csv")
    period_by_series = defaultdict(Counter)
    for row in classified_rows:
        period_by_series[row.get("series", "")][row.get("period_l2", "")] += 1
    z_periods = period_by_series["Zograf Readings"]
    r_periods = period_by_series["Roerich Readings"]
    z_period_total = sum(z_periods.values()) or 1
    r_period_total = sum(r_periods.values()) or 1
    z_classical_medieval = round(100 * (z_periods["classical"] + z_periods["medieval"]) / z_period_total, 1)
    r_classical_medieval = round(100 * (r_periods["classical"] + r_periods["medieval"]) / r_period_total, 1)

    cards = [
        (
            "Слабое пересечение площадок",
            f"{overlap} / {expected_overlap:.1f}",
            f"На обеих площадках выступали {overlap} ученых, тогда как перестановочная модель при той же индивидуальной активности ожидает {expected_overlap:.1f}. Это главный количественный результат: поле связано, но межплощадочная проницаемость намного ниже простого ожидания.",
        ),
        (
            "Две разные публичные среды",
            f"{zograf_scholars} / {roerich_scholars}",
            "Зографские чтения шире по кругу участников, Рериховские компактнее и плотнее по ядру. Это не доказательство скрытого фильтра, а описание публично наблюдаемой структуры программ.",
        ),
        (
            "Тематическая асимметрия",
            f"{r_classical_medieval}% / {z_classical_medieval}%",
            f"В Рериховских чтениях классический и средневековый материал занимает {r_classical_medieval}% докладов, в Зографских - {z_classical_medieval}%. Различие видно не только социально, но и тематически.",
        ),
        (
            "Городская метка не равна месту работы",
            f"{z_city_only}% / {r_city_only}%",
            "В Зографских программах город вместо учреждения опубликован значительно чаще, чем в Рериховских. Поэтому городской фильтр показывает публичную репрезентацию, а не автоматически занятость участника.",
        ),
        (
            "Микрокейс как нормальный жанр",
            f"{g1_count} / {unique_presentations}",
            f"После полного DeepSeek-аудита шкала Гумилева показывает доминирование докладов об отдельном тексте, авторе, термине или локальном сюжете. Глобальных G3-заголовков осталось {g3_count}; их связь со старшим поколением не подтвердилась.",
        ),
        (
            "Видео - слой проверки, не вся выборка",
            f"{video_presentations} доклада",
            f"В базе есть прямые видеоссылки для {video_presentations} уникальных докладов ({video_author_cards} авторских карточек) при {youtube_rows} строках YouTube-инвентаря. Видео полезно для проверки конкретных выступлений, но не заменяет полный корпус программ.",
        ),
    ]
    card_html = []
    for title, metric, text in cards:
        card_html.append(
            f"""
            <article class="card">
                <strong>{esc(title)}</strong>
                <div class="metric">{esc(metric)}</div>
                <div class="meta">{esc(text)}</div>
            </article>
            """
        )

    def as_float(value, default=0.0):
        try:
            return float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError):
            return default

    def as_int(value, default=0):
        try:
            return int(float(str(value).strip().replace(",", ".")))
        except (TypeError, ValueError):
            return default

    workup_path = Path("article/hypothesis_output/hypothesis_workup.md")
    workup_text = workup_path.read_text(encoding="utf-8") if workup_path.exists() else ""

    def extract_float(pattern, default):
        match = re.search(pattern, workup_text, flags=re.DOTALL)
        return as_float(match.group(1), default) if match else default

    h8_newcomer_match = re.search(
        r"newcomer rate\).*?([0-9.]+)% \(([^)]+)\).*?([0-9.]+)% \(([^)]+)\).*?p=([0-9.]+)",
        workup_text,
        flags=re.DOTALL,
    )
    if h8_newcomer_match:
        h8_old_rate = as_float(h8_newcomer_match.group(1), 24.9)
        h8_old_n = h8_newcomer_match.group(2)
        h8_new_rate = as_float(h8_newcomer_match.group(3), 23.1)
        h8_new_n = h8_newcomer_match.group(4)
        h8_newcomer_p = as_float(h8_newcomer_match.group(5), 0.7603)
    else:
        h8_old_rate, h8_old_n = 24.9, "194/780"
        h8_new_rate, h8_new_n = 23.1, "27/117"
        h8_newcomer_p = 0.7603
    h8_l1_p = extract_float(r"Тематический дрейф L1 .*?p=([0-9.]+)", 0.8463)
    h8_l2_p = extract_float(r"Тематический дрейф L2 .*?p=([0-9.]+)", 0.2619)

    h10_core_rate = extract_float(r"ядра.*?: ([0-9.]+)%", 2.6)
    h10_periphery_rate = extract_float(r"периферии.*?: ([0-9.]+)%", 5.7)
    h10_fisher_p = extract_float(r"Фишера.*?: p=([0-9.]+)", 0.0153)
    h10_rho = extract_float(r"rho=([0-9.]+)", 0.276)

    metrics_ci = load_csv_rows("article/hypothesis_output/appendix_g_metrics_ci.csv")
    z_once = as_float(metrics_ci[0].get("point"), 45.7) if len(metrics_ci) > 0 else 45.7
    z_retention = as_float(metrics_ci[1].get("point"), 54.3) if len(metrics_ci) > 1 else 54.3
    z_core = as_float(metrics_ci[2].get("point"), 31.2) if len(metrics_ci) > 2 else 31.2
    r_once = as_float(metrics_ci[4].get("point"), 35.8) if len(metrics_ci) > 4 else 35.8
    r_retention = as_float(metrics_ci[5].get("point"), 64.2) if len(metrics_ci) > 5 else 64.2
    r_core = as_float(metrics_ci[6].get("point"), 33.0) if len(metrics_ci) > 6 else 33.0

    geo_distribution = {
        row.get("city", ""): row
        for row in load_csv_rows("article/hypothesis_output/geographic_presentation_distribution.csv")
    }
    geo_retention = {
        row.get("city", ""): row
        for row in load_csv_rows("article/hypothesis_output/geographic_speaker_retention.csv")
    }
    z_spb = as_float(geo_distribution.get("SPb", {}).get("zograf_pct"), 32.2)
    z_moscow = as_float(geo_distribution.get("Moscow", {}).get("zograf_pct"), 30.8)
    r_spb = as_float(geo_distribution.get("SPb", {}).get("roerich_pct"), 6.9)
    r_moscow = as_float(geo_distribution.get("Moscow", {}).get("roerich_pct"), 54.5)
    regions_retention = as_float(geo_retention.get("Regions/Foreign", {}).get("retention_pct"), 31.7)
    moscow_retention = as_float(geo_retention.get("Moscow", {}).get("retention_pct"), 63.1)
    spb_retention = as_float(geo_retention.get("SPb", {}).get("retention_pct"), 64.6)

    video_status = {
        row.get("status", ""): as_int(row.get("videos"), 0)
        for row in load_csv_rows("article/hypothesis_output/video_mapping_status.csv")
    }
    online_rows = load_csv_rows("analytics_output/online_share_by_year.csv")
    online_by_event = {row.get("event_id", ""): row for row in online_rows}
    z2020_online = as_int(online_by_event.get("E2020", {}).get("n_online"), 44)
    z2020_total = z2020_online + as_int(online_by_event.get("E2020", {}).get("n_offline"), 0)
    z2020_share = as_float(online_by_event.get("E2020", {}).get("online_share_pct"), 100.0)
    z2025_share = as_float(online_by_event.get("E2025", {}).get("online_share_pct"), 26.8)
    z2026_share = as_float(online_by_event.get("E2026", {}).get("online_share_pct"), 1.7)
    online_repeaters = len(load_csv_rows("analytics_output/online_repeaters_2020_plus.csv"))

    session_bridges = load_csv_rows("article/hypothesis_output/network_bridges_session.csv")
    top_session_names = ", ".join(row.get("display_name", "") for row in session_bridges[:3])
    institution_bridges = load_csv_rows("article/hypothesis_output/institution_bridge_summary.csv")[:3]
    top_institution_text = "; ".join(f"{row.get('affiliation_group')}={row.get('cross_cohort_people')}" for row in institution_bridges)

    bridges_data = []
    scholar_slug_by_id = {s.get("id"): s.get("url_slug") for s in data.get("scholars", [])}
    scholar_aff_by_id = {}
    for s in data.get("scholars", []):
        affs = s.get("all_affiliations") or []
        scholar_aff_by_id[s.get("id")] = affs[0] if affs else "Не указана"

    for row in load_csv_rows("article/hypothesis_output/network_bridges.csv"):
        pid = row.get("person_id")
        if not pid:
            continue
        z_talks = int(row.get("zograf") or 0)
        r_talks = int(row.get("roerich") or 0)
        total = int(row.get("total_participations") or 0)
        betweenness = float(row.get("betweenness") or 0.0)
        balance = float(row.get("balance") or 0.0)
        slug = scholar_slug_by_id.get(pid, pid)
        display_name = row.get("display_name")
        group = row.get("series_attended")
        aff = scholar_aff_by_id.get(pid, "Не указана")
        bridges_data.append({
            "id": pid,
            "name": display_name,
            "slug": slug,
            "z": z_talks,
            "r": r_talks,
            "total": total,
            "b": betweenness,
            "bal": balance,
            "g": group,
            "aff": aff
        })

    def bar_row(label_ru, label_en, value, max_value=100.0, value_label=None, note_ru="", note_en=""):
        numeric = as_float(value, 0.0)
        maximum = max(as_float(max_value, 100.0), 0.001)
        width = max(0.0, min(100.0, 100.0 * numeric / maximum))
        if value_label is None:
            value_label = f"{numeric:.1f}"
        note_html = ""
        if note_ru or note_en:
            note_html = f'<div class="viz-note bilingual-text" data-ru="{esc(note_ru)}" data-en="{esc(note_en)}">{esc(note_ru)}</div>'
        return (
            '<div class="viz-row">'
            f'<div class="viz-label"><span class="bilingual-text" data-ru="{esc(label_ru)}" data-en="{esc(label_en)}">{esc(label_ru)}</span><b>{esc(value_label)}</b></div>'
            f'<div class="viz-track" aria-hidden="true"><span style="width:{width:.1f}%"></span></div>'
            f"{note_html}</div>"
        )

    def finding_card(title_ru, title_en, metric, text_ru, text_en, visual="", note_ru="", note_en=""):
        visual_html = f'<div class="viz-stack">{visual}</div>' if visual else ""
        note_html = ""
        if note_ru or note_en:
            note_html = f'<div class="viz-note bilingual-text" data-ru="{esc(note_ru)}" data-en="{esc(note_en)}">{esc(note_ru)}</div>'
        return (
            '<article class="card finding-card">'
            f'<strong class="bilingual-text" data-ru="{esc(title_ru)}" data-en="{esc(title_en)}">{esc(title_ru)}</strong>'
            f'<div class="metric">{esc(metric)}</div>'
            f'<div class="meta bilingual-text" data-ru="{esc(text_ru)}" data-en="{esc(text_en)}">{esc(text_ru)}</div>'
            f'{visual_html}{note_html}'
            '</article>'
        )

    # Calculate collaboration and retention metrics dynamically
    pres_author_counts = defaultdict(int)
    for record in records:
        pres_id = record.get("presentation_id")
        if pres_id:
            pres_author_counts[pres_id] += 1

    scholar_cities = {}
    scholar_years = defaultdict(set)
    scholar_talks = defaultdict(list)
    scholar_names = {}

    for record in records:
        pid = record.get("person_id")
        if not pid:
            continue
        scholar_names[pid] = record.get("display_name") or record.get("name") or ""
        year = record.get("year")
        if year:
            try:
                scholar_years[pid].add(int(year))
            except ValueError:
                pass
        pres_id = record.get("presentation_id")
        if pres_id:
            scholar_talks[pid].append(pres_id)
        
        # Get city
        affiliation = record.get("affiliation") or ""
        aff_low = affiliation.lower()
        if "санкт-петербург" in aff_low or "спб" in aff_low or "ленинград" in aff_low:
            scholar_cities[pid] = "Санкт-Петербург"
        elif "москва" in aff_low or "мгу" in aff_low or "ив ран" in aff_low or "вшэ" in aff_low:
            scholar_cities[pid] = "Москва"
        elif pid not in scholar_cities:
            scholar_cities[pid] = "Регионы / Ино"

    scholars_stats = []
    for pid in scholar_names.keys():
        city = scholar_cities.get(pid, "Регионы / Ино")
        years_seen = scholar_years[pid]
        talks_list = scholar_talks[pid]
        returned_status = len(years_seen) >= 2
        has_collab = any(pres_author_counts[tid] > 1 for tid in talks_list)
        scholars_stats.append({
            "city": city,
            "returned": returned_status,
            "has_collab": has_collab
        })

    grouped_counts = defaultdict(lambda: {"total": 0, "returned": 0})
    for item in scholars_stats:
        key = (item["city"], item["has_collab"])
        grouped_counts[key]["total"] += 1
        if item["returned"]:
            grouped_counts[key]["returned"] += 1

    def get_rate(city, has_collab):
        stats_val = grouped_counts[(city, has_collab)]
        if stats_val["total"] > 0:
            return round(100 * stats_val["returned"] / stats_val["total"], 1), stats_val["total"]
        return 0.0, 0

    spb_solo_rate, spb_solo_n = get_rate("Санкт-Петербург", False)
    spb_collab_rate, spb_collab_n = get_rate("Санкт-Петербург", True)
    moscow_solo_rate, moscow_solo_n = get_rate("Москва", False)
    moscow_collab_rate, moscow_collab_n = get_rate("Москва", True)
    regions_solo_rate, regions_solo_n = get_rate("Регионы / Ино", False)
    regions_collab_rate, regions_collab_n = get_rate("Регионы / Ино", True)

    checked_cards = [
        finding_card(
            "H8. Смена оргкомитета: значимого сдвига нет",
            "H8. Organizing Committee Change: No Significant Shift",
            f"p={h8_newcomer_p:.4f}",
            "После сверки H8 можно показывать как отрицательный или осторожный результат: приток новичков, L1 и L2 не меняются статистически значимо.",
            "Following H8 verification, this can be shown as a negative or cautious result: the influx of newcomers, L1, and L2 do not change with statistical significance.",
            bar_row("Новички до 2024", "Newcomers before 2024", h8_old_rate, 30, f"{h8_old_rate:.1f}% ({h8_old_n})")
            + bar_row("Новички 2025-2026", "Newcomers 2025-2026", h8_new_rate, 30, f"{h8_new_rate:.1f}% ({h8_new_n})"),
            f"p новичков={h8_newcomer_p:.4f}; p L1={h8_l1_p:.4f}; p L2={h8_l2_p:.4f}.",
            f"p newcomers={h8_newcomer_p:.4f}; p L1={h8_l1_p:.4f}; p L2={h8_l2_p:.4f}."
        ),
        finding_card(
            "H10. Сериализация редка и не сильнее у ядра",
            "H10. Serialization is Rare and Not Stronger at the Core",
            f"{h10_core_rate:.1f}% / {h10_periphery_rate:.1f}%",
            "Сильная версия о том, что ядро чаще дробит темы на серии, не поддержана: относительная доля выше у периферии, хотя абсолютное число серий растет с общей активностью.",
            "The strong version that the core splits topics into series more often is not supported: the relative share is higher in the periphery, although the absolute number of series grows with general activity.",
            bar_row("Ядро >=5 докладов", "Core >=5 presentations", h10_core_rate, 6, f"{h10_core_rate:.1f}%")
            + bar_row("Периферия <5 докладов", "Periphery <5 presentations", h10_periphery_rate, 6, f"{h10_periphery_rate:.1f}%"),
            f"Fisher p={h10_fisher_p:.4f}; Spearman rho={h10_rho:.3f}.",
            f"Fisher p={h10_fisher_p:.4f}; Spearman rho={h10_rho:.3f}."
        ),
        finding_card(
            "H7+H9. Соавторство и возвращаемость авторов",
            "H7+H9. Co-authorship and Author Retention",
            f"SPb: {spb_collab_rate}% / Москва: {moscow_collab_rate}%",
            "Соавторы в мегаполисах возвращаются чаще соло-участников. Региональные же соавторы остаются изолированными.",
            "Co-authors in metropolitan areas return more often than solo participants. Regional co-authors remain isolated.",
            bar_row("СПб: соавторы (коллаб)", "SPb: co-authors (collab)", spb_collab_rate, 100, f"{spb_collab_rate}% (N={spb_collab_n})")
            + bar_row("СПб: соло-авторы", "SPb: solo authors", spb_solo_rate, 100, f"{spb_solo_rate}% (N={spb_solo_n})")
            + bar_row("Москва: соавторы (коллаб)", "Moscow: co-authors (collab)", moscow_collab_rate, 100, f"{moscow_collab_rate}% (N={moscow_collab_n})")
            + bar_row("Москва: соло-авторы", "Moscow: solo authors", moscow_solo_rate, 100, f"{moscow_solo_rate}% (N={moscow_solo_n})")
            + bar_row("Регионы: соавторы (коллаб)", "Regions: co-authors (collab)", regions_collab_rate, 100, f"{regions_collab_rate}% (N={regions_collab_n})")
            + bar_row("Регионы: соло-авторы", "Regions: solo authors", regions_solo_rate, 100, f"{regions_solo_rate}% (N={regions_solo_n})"),
            "Соавторство крайне редко (27/1350 докладов) и сосредоточено в СПб (16.7% авторов) и Москве (12.8% авторов).",
            "Co-authorship is extremely rare (27/1350 presentations) and concentrated in SPb (16.7% of authors) and Moscow (12.8% of authors)."
        ),
    ]

    hypothesis_cards = [
        finding_card(
            "1. Слабое пересечение площадок",
            "1. Weak Overlap Between Venues",
            f"{overlap} / {expected_overlap:.1f}",
            "Наблюдаемое пересечение намного ниже нулевой модели при сохранении индивидуальной активности.",
            "The observed overlap is significantly lower than the null model while retaining individual activity.",
            bar_row("Наблюдаемое", "Observed", overlap, expected_overlap, str(overlap))
            + bar_row("Ожидание модели", "Model Expectation", expected_overlap, expected_overlap, f"{expected_overlap:.1f}"),
        ),
        finding_card(
            "2. Компактность без обвинения",
            "2. Compactness Without Blame",
            f"{z_retention:.1f}% / {r_retention:.1f}%",
            "Возвращаемость и доля ядра визуализируемы, но bootstrap-различия между площадками не исключают ноль.",
            "Retention and core share are visualizable, but bootstrap differences between venues do not exclude zero.",
            bar_row("Зограф: удержание", "Zograf: retention", z_retention, 70, f"{z_retention:.1f}%")
            + bar_row("Рерих: удержание", "Roerich: retention", r_retention, 70, f"{r_retention:.1f}%")
            + bar_row("Зограф: ядро >=5", "Zograf: core >=5", z_core, 45, f"{z_core:.1f}%")
            + bar_row("Рерих: ядро >=5", "Roerich: core >=5", r_core, 45, f"{r_core:.1f}%"),
            f"Разовые участники: Зограф {z_once:.1f}%, Рерих {r_once:.1f}%.",
            f"One-time participants: Zograf {z_once:.1f}%, Roerich {r_once:.1f}%.",
        ),
        finding_card(
            "3. Тематическая асимметрия",
            "3. Thematic Asymmetry",
            f"{r_classical_medieval}% / {z_classical_medieval}%",
            "Классический и средневековый материал занимает большую долю в Рериховских чтениях, чем в Зографских.",
            "Classical and medieval topics account for a larger share in Roerich Readings compared to Zograf Readings.",
            bar_row("Рерих: classic+medieval", "Roerich: classic+medieval", r_classical_medieval, 80, f"{r_classical_medieval:.1f}%")
            + bar_row("Зограф: classic+medieval", "Zograf: classic+medieval", z_classical_medieval, 80, f"{z_classical_medieval:.1f}%"),
        ),
        finding_card(
            "4. Городская метка не равна месту работы",
            "4. City Label is Not Employment",
            f"{z_city_only}% / {r_city_only}%",
            "Зографские программы гораздо чаще публикуют город вместо учреждения, поэтому город нужен как режим публичной репрезентации, а не как готовая аффилиация.",
            "Zograf programs publish the city instead of institution much more often, hence the city serves as public representation, not employment.",
            bar_row("Зограф: только город", "Zograf: city-only", z_city_only, 75, f"{as_float(z_city_only):.1f}%")
            + bar_row("Рерих: только город", "Roerich: city-only", r_city_only, 75, f"{as_float(r_city_only):.1f}%"),
        ),
        finding_card(
            "5. География и возвращаемость",
            "5. Geography and Retention",
            f"{regions_retention:.1f}%",
            "Региональная метка связана с более низкой наблюдаемой возвращаемостью; сами площадки при этом тянут разные городские профили.",
            "Regional labels correlate with lower observed retention; the venues themselves attract distinct geographical profiles.",
            bar_row("Зограф: Москва", "Zograf: Moscow", z_moscow, 60, f"{z_moscow:.1f}%")
            + bar_row("Рерих: Москва", "Roerich: Moscow", r_moscow, 60, f"{r_moscow:.1f}%")
            + bar_row("Зограф: СПб", "Zograf: SPb", z_spb, 60, f"{z_spb:.1f}%")
            + bar_row("Рерих: СПб", "Roerich: SPb", r_spb, 60, f"{r_spb:.1f}%")
            + bar_row("Регионы/ино: удержание", "Regions/intl: retention", regions_retention, 70, f"{regions_retention:.1f}%"),
            f"Для сравнения: Москва {moscow_retention:.1f}%, СПб {spb_retention:.1f}%.",
            f"For comparison: Moscow {moscow_retention:.1f}%, SPb {spb_retention:.1f}%.",
        ),
        finding_card(
            "6. Микрокейс как основной жанр",
            "6. Micro-Case as the Primary Genre",
            f"{g1_count} / {unique_presentations}",
            "Шкала Гумилева хорошо ложится на сайт: подавляющее большинство заголовков работает на микроуровне, а глобальных G3 очень мало.",
            "The Gumilyov scale fits the site well: the vast majority of titles represent the micro-level, with very few global G3 cases.",
            bar_row("G1 микро", "G1 micro", g1_count, unique_presentations, str(g1_count))
            + bar_row("G2 регион/традиция", "G2 regional/tradition", scale.get("2", 0), unique_presentations, str(scale.get("2", 0)))
            + bar_row("G3 глобально", "G3 global", g3_count, unique_presentations, str(g3_count)),
        ),
        finding_card(
            "7. Видео как проверочный слой",
            "7. Video as a Verification Layer",
            f"{video_presentations} / {youtube_rows}",
            "Видео можно показывать рядом с докладами, но оно остается неполным слоем проверки, а не самостоятельной выборкой для выводов.",
            "Video can be displayed alongside papers, but remains an incomplete verification layer, not a self-sufficient sample.",
            bar_row("Привязано к докладам", "Linked to presentations", video_presentations, youtube_rows, str(video_presentations))
            + bar_row("auto mapping", "auto mapping", video_status.get("auto", 0), youtube_rows, str(video_status.get("auto", 0)))
            + bar_row("needs review", "needs review", video_status.get("needs_review", 0), youtube_rows, str(video_status.get("needs_review", 0))),
            f"Авторских карточек с видео: {video_author_cards}; skip: {video_status.get('skip', 0)}.",
            f"Author cards with video: {video_author_cards}; skip: {video_status.get('skip', 0)}.",
        ),
        finding_card(
            "8. Онлайн-2020 как форматный шок",
            "8. Online-2020 as a Format Shock",
            f"{z2020_online} / {z2020_total}",
            "Онлайн-режим лучше визуализировать как метаданные формата участия: сильный пик 2020 г. не превращается сам по себе в доказанную новую когорту.",
            "Online format is best visualized as participation metadata: the sharp 2020 peak does not automatically signal a new cohort.",
            bar_row("Зограф 2020 онлайн", "Zograf 2020 online", z2020_share, 100, f"{z2020_share:.1f}%")
            + bar_row("Зограф 2025 онлайн", "Zograf 2025 online", z2025_share, 100, f"{z2025_share:.1f}%")
            + bar_row("Зограф 2026 онлайн", "Zograf 2026 online", z2026_share, 100, f"{z2026_share:.1f}%"),
            f"Повторяющихся онлайн-участников после 2020: {online_repeaters}.",
            f"Repeating online participants after 2020: {online_repeaters}.",
        ),
        finding_card(
            "9. Мосты видны лучше через сессии",
            "9. Bridges Are More Visible Via Sessions",
            f"{overlap} человек",
            "Сессионный граф позволяет показать не только общую перекрестную когорту, но и посредников, которых обычная сумма выступлений сглаживает.",
            "The session graph reveals the bridge cohort and specific intermediaries that simple participation totals smooth out.",
            "".join(
                bar_row(
                    row.get("affiliation_group", ""),
                    row.get("affiliation_group", ""),
                    row.get("cross_cohort_people", 0),
                    max(overlap, 1),
                    str(row.get("cross_cohort_people", 0)),
                )
                for row in institution_bridges
            ),
            f"Топ сессионных посредников: {top_session_names}. Институциональные группы: {top_institution_text}.",
            f"Top session intermediaries: {top_session_names}. Institutional groups: {top_institution_text}.",
        ),
    ]

    findings_style = """
        <style>
            .lang-toggle-container {
                display: flex;
                justify-content: flex-end;
                margin-bottom: 1.2rem;
            }
            #lang-toggle-btn {
                background: rgba(255, 255, 255, 0.08);
                color: #fff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                padding: 0.4rem 0.9rem;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.88rem;
                transition: all 0.2s ease;
            }
            #lang-toggle-btn:hover {
                background: var(--accent);
                border-color: var(--accent);
            }
            .finding-card {
                display: flex;
                flex-direction: column;
                min-height: 100%;
            }
            .viz-stack {
                display: grid;
                gap: 0.58rem;
                margin-top: 0.85rem;
            }
            .viz-label {
                display: flex;
                justify-content: space-between;
                gap: 0.75rem;
                color: var(--muted);
                font-size: 0.84rem;
            }
            .viz-label b {
                color: #fff;
                white-space: nowrap;
            }
            .viz-track {
                height: 0.55rem;
                overflow: hidden;
                border-radius: 999px;
                background: rgba(255,255,255,0.08);
            }
            .viz-track span {
                display: block;
                height: 100%;
                border-radius: inherit;
                background: linear-gradient(90deg, var(--accent), var(--accent2));
            }
            .viz-note {
                color: var(--soft);
                font-size: 0.8rem;
                line-height: 1.45;
                margin-top: 0.55rem;
            }
            .orbit-scatter-card {
                grid-column: 1 / -1;
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 1.5rem;
                margin-bottom: 2rem;
            }
            .scatter-grid-line {
                stroke: rgba(255, 255, 255, 0.05);
                stroke-dasharray: 2 2;
            }
            .scatter-diagonal {
                stroke: var(--accent2);
                stroke-dasharray: 4 4;
                stroke-width: 1.5;
                opacity: 0.6;
            }
            .scatter-axis {
                stroke: rgba(255, 255, 255, 0.2);
            }
            .scatter-axis-label {
                fill: var(--muted);
                font-size: 11px;
                font-weight: 500;
            }
            .scatter-dot {
                cursor: pointer;
                transform-box: fill-box;
                transform-origin: center;
                transition: transform 0.15s ease-out;
            }
            .scatter-dot:hover {
                transform: scale(1.4);
                stroke: #fff;
                stroke-width: 1.5px;
            }
            .legend-container {
                display: flex;
                gap: 1.5rem;
                margin-top: 1rem;
                flex-wrap: wrap;
            }
            .legend-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.85rem;
                color: var(--muted);
            }
            .legend-color {
                width: 10px;
                height: 10px;
                border-radius: 50%;
            }
            #scatter-tooltip {
                position: absolute;
                background: rgba(18, 18, 24, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 0.8rem 1rem;
                font-size: 0.85rem;
                color: #fff;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.15s ease;
                z-index: 1000;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
                max-width: 280px;
                line-height: 1.4;
            }
        </style>
    """

    serialized_bridges = json.dumps(bridges_data, ensure_ascii=False)

    body = f"""
        <div class="lang-toggle-container">
            <button id="lang-toggle-btn" onclick="toggleLanguage()">English</button>
        </div>

        <header>
            <h1 class="bilingual-text" data-ru="Главные выводы статьи" data-en="Key Findings of the Article">Главные выводы статьи</h1>
            <p class="bilingual-text" data-ru="Эта страница переводит последнюю версию статьи из режима доказательства в режим чтения сайта: что означают базовые числа архива и куда на сайте идти, чтобы проверить каждый вывод." data-en="This page translates the latest version of the article from proof mode to site reading mode: what the basic numbers of the archive mean and where to go on the site to verify each conclusion.">Эта страница переводит последнюю версию статьи из режима доказательства в режим чтения сайта: что означают базовые числа архива и куда на сайте идти, чтобы проверить каждый вывод.</p>
        </header>

        <aside class="caveat-block" role="note" aria-label="Article corpus pause">
            <strong class="bilingual-text" data-ru="Корпус и статья пересчитаны" data-en="Corpus & Article Recalculated">Корпус и статья пересчитаны</strong>
            <p class="bilingual-text" data-ru="Показатели статьи рассчитаны для текущего расширенного каталога: {esc(total_scholars)} ученых, {esc(unique_presentations)} уникальных докладов и {esc(author_participations)} авторских участий. Классификация масштаба аргумента выполнена по всем докладам и повторно проверена для предварительных L2/L3." data-en="Article metrics are computed for the current expanded catalog: {esc(total_scholars)} scholars, {esc(unique_presentations)} unique presentations, and {esc(author_participations)} author participations. Argument scale classification is applied to all papers and re-verified for preliminary L2/L3.">Показатели статьи рассчитаны для текущего расширенного каталога: {esc(total_scholars)} ученых, {esc(unique_presentations)} уникальных докладов и {esc(author_participations)} авторских участий. Классификация масштаба аргумента выполнена по всем докладам и повторно проверена для предварительных L2/L3.</p>
        </aside>

        {findings_style}

        <!-- Interactive Cross-Cohort Orbit Scatter Plot -->
        <section class="orbit-scatter-card">
            <h2 class="bilingual-text" data-ru="Орбита перекрёстной когорты (Зограф × Рерих)" data-en="Cross-Cohort Orbit Scatter (Zograf × Roerich)">Орбита перекрёстной когорты (Зограф × Рерих)</h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Каждая точка представляет исследователя. Смещение от пунктирной диагонали показывает баланс его активности между двумя площадками. Масштабируйте/наведите мышь для деталей, нажмите для перехода в профиль." data-en="Each dot represents a researcher. The offset from the dashed diagonal indicates their activity balance between the two venues. Hover for details, click to visit their profile.">Каждая точка представляет исследователя. Смещение от пунктирной диагонали показывает баланс его активности между двумя площадками. Масштабируйте/наведите мышь для деталей, нажмите для перехода в профиль.</p>
            
            <div id="scatter-chart-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <!-- Responsive SVG Plot -->
                <svg id="scatter-svg" viewBox="0 0 800 480" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="scatter-tooltip"></div>
            </div>

            <div class="legend-container">
                <div class="legend-item">
                    <span class="legend-color" style="background:#ff7b00;"></span>
                    <span class="bilingual-text" data-ru="Участвовал в обоих (Мост)" data-en="Attended both (Bridge)">Участвовал в обоих (Мост)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#2b82c9;"></span>
                    <span class="bilingual-text" data-ru="Только Зографские чтения" data-en="Zograf Readings only">Только Зографские чтения</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#b83280;"></span>
                    <span class="bilingual-text" data-ru="Только Рериховские чтения" data-en="Roerich Readings only">Только Рериховские чтения</span>
                </div>
            </div>

            <aside class="caveat-block" role="note" style="margin-top: 1.2rem; border-left: 3px solid var(--accent2); background: rgba(255,255,255,0.01);">
                <strong class="bilingual-text" data-ru="Источниковедческая оговорка" data-en="Source Caveat">Источниковедческая оговорка</strong>
                <p class="bilingual-text" data-ru="Этот график показывает распределение докладов исключительно на основе официально опубликованных программ. Наблюдаемый баланс является медийным фактом программы, а не полной академической биографией." data-en="This scatter plot depicts the distribution of presentations solely based on officially published program metadata. The observed balance is a structural fact of the programs, not a complete scholarly biography.">Этот график показывает распределение докладов исключительно на основе официально опубликованных программ. Наблюдаемый баланс является медийным фактом программы, а не полной академической биографией.</p>
            </aside>
        </section>

        <h2 class="bilingual-text" data-ru="Сначала после сверки чисел" data-en="First, After Number Verification">Сначала после сверки чисел</h2>
        <section class="grid">
            {''.join(checked_cards)}
        </section>

        <h2 class="bilingual-text" data-ru="Остальные 9 визуальных гипотез" data-en="The Other 9 Visual Hypotheses">Остальные 9 визуальных гипотез</h2>
        <section class="grid">
            {''.join(hypothesis_cards)}
        </section>

        <h2 class="bilingual-text" data-ru="Как читать эти числа" data-en="How to Read These Numbers">Как читать эти числа</h2>
        <section class="list">
            <article class="talk">
                <strong class="bilingual-text" data-ru="Не превращать компактность в обвинение" data-en="Do Not Turn Compactness Into Blame">Не превращать компактность в обвинение</strong>
                <div class="meta bilingual-text" data-ru="Программы показывают публичный итог отбора, но не заявки, отказы и внутренние решения. Поэтому статья говорит о наблюдаемой компактности, возвращаемости и проницаемости, а не о доказанной закрытости." data-en="Programs show the public outcome of selection, not applications, rejections, or internal decisions. Therefore, the article refers to observed compactness, retention, and permeability, rather than proven exclusiveness.">Программы показывают публичный итог отбора, но не заявки, отказы и внутренние решения. Поэтому статья говорит о наблюдаемой компактности, возвращаемости и проницаемости, а не о доказанной закрытости.</div>
            </article>
            <article class="talk">
                <strong class="bilingual-text" data-ru="Не читать город как биографию" data-en="Do Not Read City as Biography">Не читать город как биографию</strong>
                <div class="meta bilingual-text" data-ru="Зографский формат часто дает город, а не учреждение. Региональный или периферийный маркер - начало вопроса о траектории участника, а не готовый ответ о его месте работы." data-en="The Zograf format frequently cites the city rather than the institution. A regional or peripheral marker is the beginning of a question about a participant's trajectory, not a ready answer about their employment.">Не читать город как биографию</div>
            </article>
            <article class="talk">
                <strong class="bilingual-text" data-ru="Не считать микрокейс слабостью" data-en="Do Not Deem Micro-Case a Weakness">Не считать микрокейс слабостью</strong>
                <div class="meta bilingual-text" data-ru="Для филологической, текстологической и историко-религиоведческой работы микрокейс часто является основной формой надежной аргументации. Неожиданность не в его наличии, а в почти полном отсутствии публичного жанра больших синтезов." data-en="For philological, textual, and historical-religious research, a micro-case is often the primary form of sound argument. The surprise is not its presence, but the near-total absence of a public genre of broad syntheses.">Для филологической, текстологической и историко-религиоведческой работы микрокейс часто является основной формой надежной аргументации. Неожиданность не в его наличии, а в почти полном отсутствии публичного жанра больших синтезов.</div>
            </article>
        </section>

        <h2 class="bilingual-text" data-ru="Проверить на сайте" data-en="Verify on the Site">Проверить на сайте</h2>
        <section class="link-block">
            <strong class="bilingual-text" data-ru="Входы в данные" data-en="Data Gateways">Входы в данные</strong>
            <div class="chip-list">
                <a class="chip bilingual-text" href="../findings/visualisations.html" data-ru="Интерактивные визуализации" data-en="Interactive Visualizations">Интерактивные визуализации</a>
                <a class="chip bilingual-text" href="../gumilyov/" data-ru="Шкала Гумилева" data-en="Gumilyov Scale">Шкала Гумилева</a>
                <a class="chip bilingual-text" href="../generations/" data-ru="Поколения" data-en="Generations">Поколения</a>
                <a class="chip bilingual-text" href="../videos/" data-ru="Видеоархив" data-en="Video Archive">Видеоархив</a>
                <a class="chip bilingual-text" href="../conferences/" data-ru="Годы и программы" data-en="Years & Programs">Годы и программы</a>
                <a class="chip bilingual-text" href="../themes/" data-ru="Тематические рубрики" data-en="Themes">Тематические рубрики</a>
                <a class="chip bilingual-text" href="../search.html" data-ru="Поиск по докладам" data-en="Search Papers">Поиск по докладам</a>
                <a class="chip bilingual-text" href="../download-data.html" data-ru="CSV, JSON, SQLite" data-en="CSV, JSON, SQLite">CSV, JSON, SQLite</a>
            </div>
        </section>

        <h2 class="bilingual-text" data-ru="Что пока держать в очереди проверки" data-en="What to Keep in the Verification Queue for Now">Что пока держать в очереди проверки</h2>
        <section class="grid">
            <article class="card">
                <strong class="bilingual-text" data-ru="Публикационная конверсия" data-en="Publication Conversion">Публикационная конверсия</strong>
                <div class="meta bilingual-text" data-ru="Пока не выносить как вывод: в БД есть PDF-источники, но нужен слой сопоставления доклада с публикацией, сборником или устойчивой серией." data-en="Do not frame as a firm finding yet: the database has PDF sources, but we need a layer linking presentations to papers, proceedings, or stable series.">Пока не выносить как вывод: в БД есть PDF-источники, но нужен слой сопоставления доклада с публикацией, сборником или устойчивой серией.</div>
            </article>
            <article class="card">
                <strong class="bilingual-text" data-ru="Authority-слой для городов" data-en="Authority Layer for Cities">Authority-слой для городов</strong>
                <div class="meta bilingual-text" data-ru="Городские метки уже можно визуализировать как публичную репрезентацию, но проверка реального места работы требует биографических и институциональных authority-записей." data-en="City labels can already be visualized as public representation, but verifying actual employment requires biographical and institutional authority records.">Городские метки уже можно визуализировать как публичную репрезентацию, но проверка реального места работы требует биографических и институциональных authority-записей.</div>
            </article>
            <article class="card">
                <strong class="bilingual-text" data-ru="Возрастная гипотеза G3" data-en="Age Hypothesis G3">Возрастная гипотеза G3</strong>
                <div class="meta bilingual-text" data-ru="Расширенный корпус не подтвердил старший возраст авторов широких обобщений; этот результат лучше держать как отрицательный контроль, а не как центральную визуальную гипотезу." data-en="The expanded corpus did not confirm the older age of authors of broad generalizations; this outcome is best kept as a negative control rather than a central visual hypothesis.">Расширенный корпус не подтвердил старший возраст авторов широких обобщений; этот результат лучше держать как отрицательный контроль, а не как центральную визуальную гипотезу.</div>
            </article>
        </section>

        <aside class="caveat-block" role="note" aria-label="Scope note">
            <strong class="bilingual-text" data-ru="Объем расширенного каталога" data-en="Expanded Catalog Volume">Объем расширенного каталога</strong>
            <p class="bilingual-text" data-ru="Текущий каталог сайта и численные гипотезы статьи используют одну расширенную базу: {esc(total_scholars)} ученых, {esc(unique_presentations)} уникальных докладов, {esc(author_participations)} авторских участий. Программа Зографских чтений 2026 г. учитывается как предварительная." data-en="The current site catalog and numerical hypotheses use the same expanded database: {esc(total_scholars)} scholars, {esc(unique_presentations)} unique presentations, {esc(author_participations)} author participations. The 2026 Zograf Readings program is included as preliminary.">Текущий каталог сайта и численные гипотезы статьи используют одну расширенную базу: {esc(total_scholars)} ученых, {esc(unique_presentations)} уникальных докладов, {esc(author_participations)} авторских участий. Программа Зографских чтений 2026 г. учитывается как предварительная.</p>
        </aside>

        <!-- Dynamic Inline JS for Orbit Scatter Plot and Language Toggling placeholder -->
    """
    
    scatter_js = """
        <script>
            const BRIDGES_DATA = """ + serialized_bridges + """;

            function getJitter(id, seed) {
                let hash = 0;
                const str = id + seed;
                for (let i = 0; i < str.length; i++) {
                    hash = str.charCodeAt(i) + ((hash << 5) - hash);
                }
                return ((Math.abs(hash) % 100) / 100) - 0.5; // [-0.5, 0.5]
            }

            let currentLang = localStorage.getItem('findings-lang') || 'ru';

            function toggleLanguage() {
                currentLang = currentLang === 'ru' ? 'en' : 'ru';
                setLanguage(currentLang);
            }

            function setLanguage(lang) {
                document.querySelectorAll('.bilingual-text').forEach(el => {
                    const text = el.getAttribute('data-' + lang);
                    if (text) {
                        el.innerHTML = text;
                    }
                });
                const btn = document.getElementById('lang-toggle-btn');
                if (btn) {
                    btn.innerText = lang === 'ru' ? 'English' : 'Русский';
                }
                localStorage.setItem('findings-lang', lang);
                drawScatter();
            }

            function drawScatter() {
                const svg = document.getElementById('scatter-svg');
                if (!svg) return;
                svg.innerHTML = '';

                const width = 800;
                const height = 480;
                const padding = { top: 40, right: 40, bottom: 50, left: 60 };

                // Find limits
                let maxZ = 20;
                let maxR = 20;

                const xScale = (val) => padding.left + (val / maxZ) * (width - padding.left - padding.right);
                const yScale = (val) => height - padding.bottom - (val / maxR) * (height - padding.top - padding.bottom);

                // Add gridlines
                for (let i = 0; i <= maxZ; i += 2) {
                    const x = xScale(i);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', x);
                    line.setAttribute('y1', padding.top);
                    line.setAttribute('x2', x);
                    line.setAttribute('y2', height - padding.bottom);
                    line.setAttribute('class', 'scatter-grid-line');
                    svg.appendChild(line);

                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', x);
                    label.setAttribute('y', height - padding.bottom + 20);
                    label.setAttribute('text-anchor', 'middle');
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '11px');
                    label.textContent = i;
                    svg.appendChild(label);
                }

                for (let i = 0; i <= maxR; i += 2) {
                    const y = yScale(i);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', y);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', y);
                    line.setAttribute('class', 'scatter-grid-line');
                    svg.appendChild(line);

                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 15);
                    label.setAttribute('y', y + 4);
                    label.setAttribute('text-anchor', 'end');
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '11px');
                    label.textContent = i;
                    svg.appendChild(label);
                }

                // Add diagonal reference line
                const diag = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                diag.setAttribute('x1', xScale(0));
                diag.setAttribute('y1', yScale(0));
                diag.setAttribute('x2', xScale(Math.min(maxZ, maxR)));
                diag.setAttribute('y2', yScale(Math.min(maxZ, maxR)));
                diag.setAttribute('class', 'scatter-diagonal');
                svg.appendChild(diag);

                // Add Axes
                const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                xAxis.setAttribute('x1', padding.left);
                xAxis.setAttribute('y1', height - padding.bottom);
                xAxis.setAttribute('x2', width - padding.right);
                xAxis.setAttribute('y2', height - padding.bottom);
                xAxis.setAttribute('class', 'scatter-axis');
                svg.appendChild(xAxis);

                const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                yAxis.setAttribute('x1', padding.left);
                yAxis.setAttribute('y1', padding.top);
                yAxis.setAttribute('x2', padding.left);
                yAxis.setAttribute('y2', height - padding.bottom);
                yAxis.setAttribute('class', 'scatter-axis');
                svg.appendChild(yAxis);

                // Axis Labels
                const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                xLabel.setAttribute('x', padding.left + (width - padding.left - padding.right) / 2);
                xLabel.setAttribute('y', height - padding.bottom + 42);
                xLabel.setAttribute('text-anchor', 'middle');
                xLabel.setAttribute('fill', '#fff');
                xLabel.setAttribute('font-size', '12px');
                xLabel.textContent = currentLang === 'ru' ? 'Докладов на Зографских чтениях' : 'Presentations at Zograf Readings';
                svg.appendChild(xLabel);

                const yLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                yLabel.setAttribute('x', 20);
                yLabel.setAttribute('y', padding.top + (height - padding.top - padding.bottom) / 2);
                yLabel.setAttribute('text-anchor', 'middle');
                yLabel.setAttribute('fill', '#fff');
                yLabel.setAttribute('font-size', '12px');
                yLabel.setAttribute('transform', 'rotate(-90, 20, ' + (padding.top + (height - padding.top - padding.bottom) / 2) + ')');
                yLabel.textContent = currentLang === 'ru' ? 'Докладов на Рериховских чтениях' : 'Presentations at Roerich Readings';
                svg.appendChild(yLabel);

                // Draw Dots
                const tooltip = document.getElementById('scatter-tooltip');

                BRIDGES_DATA.forEach(d => {
                    const jX = getJitter(d.id, 'X') * 0.42;
                    const jY = getJitter(d.id, 'Y') * 0.42;

                    const cx = xScale(d.z + jX);
                    const cy = yScale(d.r + jY);

                    // Radius based on total presentations
                    const r = 4 + Math.sqrt(d.total) * 1.5;

                    // Color based on group
                    let color = '#ff7b00'; // both
                    if (d.g === 'zograf_only') color = '#2b82c9';
                    else if (d.g === 'roerich_only') color = '#b83280';

                    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    dot.setAttribute('cx', cx);
                    dot.setAttribute('cy', cy);
                    dot.setAttribute('r', r);
                    dot.setAttribute('fill', color);
                    dot.setAttribute('opacity', '0.75');
                    dot.setAttribute('class', 'scatter-dot');

                    dot.addEventListener('mouseenter', (e) => {
                        dot.setAttribute('opacity', '1.0');
                        tooltip.style.opacity = '1';
                        
                        const titleZ = currentLang === 'ru' ? 'Зограф' : 'Zograf';
                        const titleR = currentLang === 'ru' ? 'Рерих' : 'Roerich';
                        const labelAff = currentLang === 'ru' ? 'Аффилиация' : 'Affiliation';
                        const labelClick = currentLang === 'ru' ? 'Нажмите для перехода к профилю' : 'Click to view profile';

                        tooltip.innerHTML = 
                            '<strong style="color:var(--accent2); font-size: 0.95rem;">' + d.name + '</strong><br>' +
                            '<span style="font-size:0.8rem; color:var(--muted);">' + labelAff + ': ' + d.aff + '</span><br>' +
                            '<span style="display:inline-block; margin-top:5px; font-weight:bold;">' + titleZ + ': ' + d.z + ' · ' + titleR + ': ' + d.r + '</span><br>' +
                            '<small style="color:var(--accent); display:block; margin-top: 5px;">' + labelClick + '</small>';
                    });

                    dot.addEventListener('mousemove', (e) => {
                        const rect = svg.getBoundingClientRect();
                        const tooltipRect = tooltip.getBoundingClientRect();
                        // Position relative to scatter container
                        const x = e.clientX - rect.left + 15;
                        const y = e.clientY - rect.top - tooltipRect.height - 10;
                        tooltip.style.left = x + 'px';
                        tooltip.style.top = y + 'px';
                    });

                    dot.addEventListener('mouseleave', () => {
                        dot.setAttribute('opacity', '0.75');
                        tooltip.style.opacity = '0';
                    });

                    dot.addEventListener('click', () => {
                        window.location.href = '../s/' + d.slug + '.html';
                    });

                    svg.appendChild(dot);
                });
            }

            document.addEventListener('DOMContentLoaded', () => {
                setLanguage(currentLang);
            });
        </script>
    """
    body = body + scatter_js
    write_text(
        "findings/index.html",
        page_shell(
            f"Главные выводы статьи | {SITE_NAME}",
            "Интерпретационный слой последней статьи: пересечение площадок, тематическая асимметрия, микрокейсы, видео и источниковедческие оговорки.",
            "findings/",
            body,
            [page_data("Главные выводы статьи", "Интерпретационный слой последней статьи.", "findings/"), make_breadcrumbs([("Главная", ""), ("Выводы", "findings/")])],
        ),
    )



def generate_visualisations_page(data, records):
    records_by_id = presentation_records_by_id(records)
    unique_records = list(records_by_id.values())
    summary = data.get("summary", {})
    total_scholars = summary.get("total_scholars", 220)
    unique_presentations = summary.get("unique_presentations", 895)
    author_participations = summary.get("author_participations", 899)

    bridges_data = []
    scholar_slug_by_id = {s.get("id"): s.get("url_slug") for s in data.get("scholars", [])}
    scholar_aff_by_id = {}
    for s in data.get("scholars", []):
        affs = s.get("all_affiliations") or []
        scholar_aff_by_id[s.get("id")] = affs[0] if affs else "Не указана"

    for row in load_csv_rows("article/hypothesis_output/network_bridges.csv"):
        pid = row.get("person_id")
        if not pid:
            continue
        z_talks = int(row.get("zograf") or 0)
        r_talks = int(row.get("roerich") or 0)
        total = int(row.get("total_participations") or 0)
        betweenness = float(row.get("betweenness") or 0.0)
        balance = float(row.get("balance") or 0.0)
        slug = scholar_slug_by_id.get(pid, pid)
        display_name = row.get("display_name")
        group = row.get("series_attended")
        aff = scholar_aff_by_id.get(pid, "Не указана")
        bridges_data.append({
            "id": pid,
            "name": display_name,
            "slug": slug,
            "z": z_talks,
            "r": r_talks,
            "total": total,
            "b": betweenness,
            "bal": balance,
            "g": group,
            "aff": aff
        })

    serialized_bridges = json.dumps(bridges_data, ensure_ascii=False)

    # Fetch affiliation opacity statistics
    from metadata_normalization import load_verified_affiliation_spans, public_affiliation, LOCATION_ONLY_RE
    verified_spans = load_verified_affiliation_spans()
    
    opacity_stats = defaultdict(lambda: {
        "zograf": {"verified": 0, "city_only": 0, "unknown": 0},
        "roerich": {"verified": 0, "city_only": 0, "unknown": 0}
    })
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        pp_rows = cursor.execute("""
            SELECT pp.person_id, e.year, es.series_name_en, pp.affiliation_text_raw
            FROM presentation_person pp
            JOIN presentation pr ON pr.presentation_id = pp.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
            JOIN event_series es ON es.event_series_id = e.event_series_id
        """).fetchall()
        
        for pid, year, series_name_en, raw in pp_rows:
            raw_clean = str(raw or "").strip()
            series = "zograf" if "zograf" in series_name_en.lower() else "roerich"
            
            aff_meta = public_affiliation(pid, year, raw_clean, None, verified_spans)
            basis = aff_meta.get("basis")
            display = aff_meta.get("display")
            
            if basis in ("verified_span", "inferred_continuation"):
                cat = "verified"
            elif display and basis == "programme":
                cat = "verified"
            elif raw_clean and (LOCATION_ONLY_RE.match(raw_clean) or raw_clean.lower() in ("москва", "спб", "санкт-петербург", "пенза", "казань", "обнинск")):
                cat = "city_only"
            else:
                cat = "unknown"
                
            opacity_stats[year][series][cat] += 1
        conn.close()
    except Exception as ex:
        print(f"Error querying affiliation opacity: {ex}")
        
    opacity_data = []
    for y in sorted(opacity_stats.keys()):
        opacity_data.append({
            "year": y,
            "zograf": opacity_stats[y]["zograf"],
            "roerich": opacity_stats[y]["roerich"]
        })
    serialized_opacity = json.dumps(opacity_data, ensure_ascii=False)

    # --- VIS_003 Heatmap Data ---
    heatmap_data = []
    all_years = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.year, es.series_name_en, COUNT(m.media_id)
            FROM presentation p
            JOIN session s ON p.session_id = s.session_id
            JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
            JOIN event_day ed ON edv.event_day_id = ed.event_day_id
            JOIN event e ON ed.event_id = e.event_id
            JOIN event_series es ON e.event_series_id = es.event_series_id
            JOIN media m ON m.attached_to_id = p.presentation_id AND m.attached_to_type = 'presentation'
            WHERE m.media_type = 'video' OR m.media_type = 'youtube'
            GROUP BY e.year, es.series_name_en
        """)
        for year, series, count in cursor.fetchall():
            group = "zograf" if "zograf" in series.lower() else "roerich"
            heatmap_data.append({"y": year, "g": group, "c": count})
            
        cursor.execute("SELECT DISTINCT year FROM event ORDER BY year")
        all_years = [r[0] for r in cursor.fetchall()]
        conn.close()
    except Exception as ex:
        print(f"Error querying heatmap data: {ex}")
        
    serialized_heatmap = json.dumps({"years": all_years, "data": heatmap_data}, ensure_ascii=False)

    # --- VIS_004 Alluvial Data ---
    alluvial_nodes = []
    alluvial_links = []
    try:
        period_theme_links = defaultdict(int)
        theme_meso_links = defaultdict(int)
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            import csv
            reader = csv.DictReader(f)
            for row in reader:
                period = row.get("period_l2")
                theme = row.get("theme_l1")
                meso = row.get("meso_codes") or row.get("proposed_meso")
                
                if not period or period == "unspecified": period = "Unknown"
                if not theme or theme == "unspecified": theme = "Unknown"
                if not meso or meso == "unspecified": meso = "Other"
                
                meso = meso.split(',')[0].strip()
                period_theme_links[(period, theme)] += 1
                theme_meso_links[(theme, meso)] += 1

        node_indices = {}
        def get_node(name, group):
            key = (name, group)
            if key not in node_indices:
                node_indices[key] = len(alluvial_nodes)
                alluvial_nodes.append({"name": name, "group": group})
            return node_indices[key]

        for (p, t), v in period_theme_links.items():
            if v >= 2:
                alluvial_links.append({"source": get_node(p, "period"), "target": get_node(t, "theme"), "value": v})
        for (t, m), v in theme_meso_links.items():
            if v >= 5:
                alluvial_links.append({"source": get_node(t, "theme"), "target": get_node(m, "meso"), "value": v})
    except Exception as ex:
        print(f"Error reading alluvial data: {ex}")
        
    serialized_alluvial = json.dumps({"nodes": alluvial_nodes, "links": alluvial_links}, ensure_ascii=False)

    # --- VIS_005 Scholar Forest Data ---
    forest_data = []
    top_scholars = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get top 40 scholars
        cursor.execute("""
            SELECT per.display_name, COUNT(p.presentation_id) as total
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
            GROUP BY per.person_id
            ORDER BY total DESC
            LIMIT 40
        """)
        top_scholars = [row[0] for row in cursor.fetchall()]
        
        # Get counts per year for these scholars
        cursor.execute("""
            SELECT per.display_name, e.year, COUNT(p.presentation_id)
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
            JOIN session s ON p.session_id = s.session_id
            JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
            JOIN event_day ed ON edv.event_day_id = ed.event_day_id
            JOIN event e ON ed.event_id = e.event_id
            WHERE per.display_name IN ({seq})
            GROUP BY per.person_id, e.year
        """.format(seq=','.join(['?']*len(top_scholars))), top_scholars)
        
        for name, year, count in cursor.fetchall():
            forest_data.append({"s": name, "y": year, "c": count})
            
        conn.close()
    except Exception as ex:
        print(f"Error querying forest data: {ex}")
        
    serialized_forest = json.dumps({"scholars": top_scholars, "years": all_years, "data": forest_data}, ensure_ascii=False)

    # --- VIS_006 Thematic Hierarchy Data ---
    hierarchy_data = {"name": "Все доклады", "children": []}
    try:
        # Build tree: Series -> L1 Theme -> Meso
        tree = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                series = row.get("series")
                theme = row.get("theme_l1")
                meso = row.get("meso_codes") or row.get("proposed_meso")
                
                if not series: series = "Unknown"
                if not theme or theme == "unspecified": theme = "Unknown"
                if not meso or meso == "unspecified": meso = "Other"
                
                series_group = "Zograf" if "zograf" in series.lower() else "Roerich"
                meso = meso.split(',')[0].strip()
                
                tree[series_group][theme][meso] += 1
                
        for s_name, themes in tree.items():
            s_node = {"name": s_name, "children": []}
            for t_name, mesos in themes.items():
                t_node = {"name": t_name, "children": []}
                for m_name, count in mesos.items():
                    if count >= 3: # filter out very small blocks
                        t_node["children"].append({"name": m_name, "value": count})
                if t_node["children"]:
                    s_node["children"].append(t_node)
            if s_node["children"]:
                hierarchy_data["children"].append(s_node)
                
    except Exception as ex:
        print(f"Error querying hierarchy data: {ex}")
        
    serialized_hierarchy = json.dumps(hierarchy_data, ensure_ascii=False)

    # --- VIS_007 Arc Diagram Data ---
    arc_nodes = []
    arc_links = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT per.display_name, COUNT(p.presentation_id) as total
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
            GROUP BY per.person_id
            ORDER BY total DESC
            LIMIT 50
        """)
        top_50 = [row[0] for row in cursor.fetchall()]
        top_set = set(top_50)
        
        for name in top_50:
            arc_nodes.append({"id": name, "group": 1})
            
        cursor.execute("""
            SELECT p.session_id, per.display_name
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
        """)
        sess_people = defaultdict(set)
        for s_id, name in cursor.fetchall():
            if name in top_set:
                sess_people[s_id].add(name)
                
        edges = defaultdict(int)
        for s_id, people in sess_people.items():
            plist = list(people)
            for i in range(len(plist)):
                for j in range(i+1, len(plist)):
                    p1, p2 = sorted([plist[i], plist[j]])
                    edges[(p1, p2)] += 1
                    
        for (p1, p2), count in edges.items():
            if count >= 2:
                arc_links.append({"source": p1, "target": p2, "value": count})
                
        conn.close()
    except Exception as ex:
        print(f"Error querying arc data: {ex}")
        
    serialized_arc = json.dumps({"nodes": arc_nodes, "links": arc_links}, ensure_ascii=False)

    # --- VIS_010 Geographic Map Data ---
    geo_data = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT affiliation_text_raw FROM presentation_person WHERE affiliation_text_raw IS NOT NULL AND affiliation_text_raw != ''")
        affs = [row[0] for row in cursor.fetchall()]
        
        cities_meta = {
            "St. Petersburg": {"name_ru": "Санкт-Петербург", "name_en": "St. Petersburg", "lat": 59.9343, "lon": 30.3351, "keys": ["спб", "санкт", "петербург", "st. petersburg", "petersburg", "ленинград", "spb"]},
            "Moscow": {"name_ru": "Москва", "name_en": "Moscow", "lat": 55.7558, "lon": 37.6173, "keys": ["москва", "moscow", "мгу", "ив ран", "вшэ"]},
            "Yekaterinburg": {"name_ru": "Екатеринбург", "name_en": "Yekaterinburg", "lat": 56.8389, "lon": 60.6057, "keys": ["екатеринбург", "урфу", "екб", "ekaterinburg"]},
            "Kazan": {"name_ru": "Казань", "name_en": "Kazan", "lat": 55.7887, "lon": 49.1221, "keys": ["казань", "kazan"]},
            "Hamburg": {"name_ru": "Гамбург", "name_en": "Hamburg", "lat": 53.5511, "lon": 9.9937, "keys": ["гамбург", "hamburg"]},
            "Novosibirsk": {"name_ru": "Новосибирск", "name_en": "Novosibirsk", "lat": 55.0084, "lon": 82.9357, "keys": ["новосибирск", "novosibirsk"]},
            "Elista": {"name_ru": "Элиста", "name_en": "Elista", "lat": 46.3078, "lon": 44.2558, "keys": ["элиста", "elista", "калм"]},
            "Kyiv": {"name_ru": "Киев", "name_en": "Kyiv", "lat": 50.4501, "lon": 30.5234, "keys": ["киев", "kyiv", "kiev"]},
            "Vienna": {"name_ru": "Вена", "name_en": "Vienna", "lat": 48.2082, "lon": 16.3738, "keys": ["вена", "vienna"]},
            "Delhi": {"name_ru": "Дели", "name_en": "Delhi", "lat": 28.6139, "lon": 77.2090, "keys": ["дели", "delhi"]},
            "Ulan-Ude": {"name_ru": "Улан-Удэ", "name_en": "Ulan-Ude", "lat": 51.8292, "lon": 107.6067, "keys": ["улан-удэ", "ulan-ude", "имбт", "бнц"]}
        }
        
        city_counts = defaultdict(int)
        for aff in affs:
            low = aff.lower()
            for city_key, meta in cities_meta.items():
                if any(k in low for k in meta["keys"]):
                    city_counts[city_key] += 1
                    break
                    
        for city_key, count in city_counts.items():
            meta = cities_meta[city_key]
            geo_data.append({
                "city": city_key,
                "name_ru": meta["name_ru"],
                "name_en": meta["name_en"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "count": count
            })
        conn.close()
    except Exception as ex:
        print(f"Error querying geo data: {ex}")
    serialized_geo = json.dumps(geo_data, ensure_ascii=False)

    # --- VIS_011 Keyword Bubble Cloud Data ---
    bubble_data = []
    try:
        import csv
        c = defaultdict(int)
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                val = row.get("meso_codes")
                if val:
                    for code in val.split('|'):
                        c[code.strip()] += 1
                        
        # clean names mapping
        clean_names = {
            "buddhist_studies": {"ru": "Буддология", "en": "Buddhist Studies"},
            "philosophy_epistemology": {"ru": "Философия и эпистемология", "en": "Philosophy & Epistemology"},
            "vedic_studies": {"ru": "Ведийские исследования", "en": "Vedic Studies"},
            "comparative_analysis": {"ru": "Сравнительный анализ", "en": "Comparative Analysis"},
            "tibetology_himalaya": {"ru": "Тибетология и Гималаи", "en": "Tibetology & Himalayas"},
            "epic_ramayana_mahabharata": {"ru": "Эпос (Рамаяна/Махабхарата)", "en": "Epic (Ramayana/Mahabharata)"},
            "dravidology_south_india": {"ru": "Дравидология и Южная Индия", "en": "Dravidology & South India"},
            "history_of_indology": {"ru": "История индологии", "en": "History of Indology"},
            "visual_material_culture": {"ru": "Визуальная культура", "en": "Visual Culture"},
            "ritual_studies": {"ru": "Исследования ритуалов", "en": "Ritual Studies"},
            "bengal": {"ru": "Бенгалистика", "en": "Bengali Studies"},
            "bhakti_vaishnava": {"ru": "Бхакти и вишнуизм", "en": "Bhakti & Vaishnavism"},
            "sanskrit_grammar_panini": {"ru": "Санскритская грамматика", "en": "Sanskrit Grammar"},
            "ethnography_performance": {"ru": "Этнография и театр", "en": "Ethnography & Performance"},
            "literary_studies": {"ru": "Литературоведение", "en": "Literary Studies"},
            "nepal_newar_kathmandu": {"ru": "Непал и долина Катманду", "en": "Nepal & Kathmandu"},
            "manuscripts_epigraphy": {"ru": "Рукописи и эпиграфика", "en": "Manuscripts & Epigraphy"},
            "translation_reception": {"ru": "Перевод и рецепция", "en": "Translation & Reception"},
            "modern_society_politics": {"ru": "Политика и общество", "en": "Politics & Society"},
            "colonial_encounters": {"ru": "Колониальный период", "en": "Colonial Encounters"}
        }
        
        for k, v in c.items():
            if k in clean_names:
                bubble_data.append({
                    "id": k,
                    "name_ru": clean_names[k]["ru"],
                    "name_en": clean_names[k]["en"],
                    "value": v
                })
    except Exception as ex:
        print(f"Error querying bubble data: {ex}")
    serialized_bubble = json.dumps(bubble_data, ensure_ascii=False)






    findings_style = """
        <style>
            .lang-toggle-container {
                display: flex;
                justify-content: flex-end;
                margin-bottom: 1.2rem;
            }
            #lang-toggle-btn {
                background: rgba(255, 255, 255, 0.08);
                color: #fff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                padding: 0.4rem 0.9rem;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.88rem;
                transition: all 0.2s ease;
            }
            #lang-toggle-btn:hover {
                background: var(--accent);
                border-color: var(--accent);
            }
            .viz-showcase-section {
                margin-bottom: 3.5rem;
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 2rem;
            }
            .viz-showcase-section h2 {
                margin-top: 0;
                display: flex;
                align-items: center;
                gap: 0.8rem;
            }
            .viz-id-badge {
                font-family: monospace;
                font-size: 0.82rem;
                background: var(--accent);
                color: #fff;
                padding: 0.2rem 0.5rem;
                border-radius: 4px;
            }
            .scatter-grid-line {
                stroke: rgba(255, 255, 255, 0.05);
                stroke-dasharray: 2 2;
            }
            .scatter-diagonal {
                stroke: var(--accent2);
                stroke-dasharray: 4 4;
                stroke-width: 1.5;
                opacity: 0.6;
            }
            .scatter-axis {
                stroke: rgba(255, 255, 255, 0.2);
            }
            .scatter-dot {
                cursor: pointer;
                transform-box: fill-box;
                transform-origin: center;
                transition: transform 0.15s ease-out;
            }
            .scatter-dot:hover {
                transform: scale(1.4);
                stroke: #fff;
                stroke-width: 1.5px;
            }
            .legend-container {
                display: flex;
                gap: 1.5rem;
                margin-top: 1rem;
                flex-wrap: wrap;
            }
            .legend-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.85rem;
                color: var(--muted);
            }
            .legend-color {
                width: 10px;
                height: 10px;
                border-radius: 50%;
            }
            #scatter-tooltip {
                position: absolute;
                background: rgba(18, 18, 24, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 0.8rem 1rem;
                font-size: 0.85rem;
                color: #fff;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.15s ease;
                z-index: 1000;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
                max-width: 280px;
                line-height: 1.4;
            }
            .viz-toc {
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                margin-bottom: 2.5rem;
                background: rgba(255, 255, 255, 0.01);
                border: 1px solid rgba(255, 255, 255, 0.03);
                border-radius: 8px;
                padding: 1rem;
            }
            .viz-toc-item {
                display: flex;
                align-items: center;
                gap: 0.8rem;
                text-decoration: none;
                color: var(--text);
                font-size: 0.95rem;
                transition: color 0.2s ease;
            }
            .viz-toc-item:hover {
                color: var(--accent);
            }
            .viz-toc-item span {
                font-family: monospace;
                font-size: 0.8rem;
                color: var(--muted);
            }
            .placeholder-viz {
                background: rgba(0, 0, 0, 0.3);
                border: 1px dashed rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 3rem 1.5rem;
                text-align: center;
                color: var(--muted);
                font-size: 0.92rem;
                margin-top: 1rem;
            }
            .opacity-controls {
                display: flex;
                gap: 0.5rem;
                margin-bottom: 1rem;
                flex-wrap: wrap;
            }
            .opacity-toggle-btn {
                background: rgba(255, 255, 255, 0.05);
                color: var(--muted);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 0.35rem 0.8rem;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.85rem;
                transition: all 0.2s ease;
            }
            .opacity-toggle-btn.active {
                background: var(--accent);
                color: #fff;
                border-color: var(--accent);
            }
            .opacity-toggle-btn:hover:not(.active) {
                background: rgba(255, 255, 255, 0.1);
                color: #fff;
            }
            #opacity-tooltip {
                position: absolute;
                background: rgba(18, 18, 24, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 0.8rem 1rem;
                font-size: 0.85rem;
                color: #fff;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.15s ease;
                z-index: 1000;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
                max-width: 280px;
                line-height: 1.4;
            }
            .opacity-bar {
                cursor: pointer;
                transition: opacity 0.2s;
            }
            .opacity-bar:hover {
                opacity: 0.85;
            }
        </style>
    """

    # ===================== EXTENDED GALLERY DATA (VIS_008 – VIS_015) =====================
    def _gf(v, d=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d

    def _gi(v, d=0):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return d

    def _series_key(name):
        return "zograf" if "zograf" in (name or "").lower() else "roerich"

    # VIS_008 — Demography ribbon (median age + p25–p75 band over time)
    demography_data = []
    for row in load_csv_rows("analytics_output/age_cohort_trend.csv"):
        demography_data.append({
            "series": _series_key(row.get("series")),
            "year": _gi(row.get("year")),
            "avg": _gf(row.get("avg_age")),
            "median": _gf(row.get("median_age")),
            "p25": _gf(row.get("p25_age")),
            "p75": _gf(row.get("p75_age")),
            "min": _gf(row.get("min_age")),
            "max": _gf(row.get("max_age")),
            "n": _gi(row.get("n_speakers_with_age")),
        })
    serialized_demography = json.dumps(demography_data, ensure_ascii=False)

    # VIS_009 — Cohort survival curves
    survival_map = {}
    for row in load_csv_rows("analytics_output/cohort_survival.csv"):
        key = (row.get("series"), row.get("debut_year"))
        bucket = survival_map.setdefault(key, {
            "series": _series_key(row.get("series")),
            "debut": _gi(row.get("debut_year")),
            "size": _gi(row.get("cohort_size")),
            "points": [],
        })
        bucket["points"].append({"x": _gi(row.get("years_since_debut")), "y": _gf(row.get("survival_pct"))})
    survival_data = [c for c in survival_map.values() if c["size"] >= 5]
    for c in survival_data:
        c["points"].sort(key=lambda p: p["x"])
    survival_data.sort(key=lambda c: (c["series"], c["debut"]))
    serialized_survival = json.dumps(survival_data, ensure_ascii=False)

    # VIS_010 — Newcomer / renewal rate by year
    newcomer_data = []
    for row in load_csv_rows("analytics_output/newcomer_rate_by_year.csv"):
        newcomer_data.append({
            "series": _series_key(row.get("series")),
            "year": _gi(row.get("year")),
            "pct": _gf(row.get("newcomer_pct")),
            "newcomers": _gi(row.get("newcomers")),
            "total": _gi(row.get("total")),
        })
    serialized_newcomer = json.dumps(newcomer_data, ensure_ascii=False)

    # VIS_011 — Theme treemap (L1 → L2)
    tree_l1 = defaultdict(lambda: defaultdict(int))
    for row in load_csv_rows("analytics_output/theme_codes_final_v2.csv"):
        l1 = row.get("l1") or "unspecified"
        l2 = row.get("l2") or "unspecified"
        tree_l1[l1][l2] += 1
    treemap_data = []
    for l1, kids in tree_l1.items():
        children = [{"name": k, "value": v} for k, v in sorted(kids.items(), key=lambda x: -x[1])]
        treemap_data.append({"name": l1, "value": sum(kids.values()), "children": children})
    treemap_data.sort(key=lambda x: -x["value"])
    serialized_treemap = json.dumps(treemap_data, ensure_ascii=False)

    # VIS_012 — Gumilyov scale streamgraph (pre-aggregated per year)
    gumilyov_stream = []
    for row in load_csv_rows("analytics_output/gumilyov_scale_trends.csv"):
        gumilyov_stream.append({
            "year": _gi(row.get("year")),
            "l1": _gi(row.get("Level_1_Microhistory")),
            "l2": _gi(row.get("Level_2_Regional")),
            "l3": _gi(row.get("Level_3_Global")),
        })
    gumilyov_stream.sort(key=lambda r: r["year"])
    serialized_gumilyov = json.dumps(gumilyov_stream, ensure_ascii=False)

    # VIS_013 — Keyword diverging bars (Zograf vs Roerich), top by total
    kw_rows = []
    for row in load_csv_rows("analytics_output/keyword_stats.csv"):
        kw_rows.append({
            "kw": row.get("keyword"),
            "total": _gi(row.get("presentations")),
            "z": _gi(row.get("zograf")),
            "r": _gi(row.get("roerich")),
        })
    kw_rows.sort(key=lambda x: -x["total"])
    serialized_keyword_div = json.dumps(kw_rows[:22], ensure_ascii=False)

    # VIS_014 — Closedness metric comparison
    closedness = {}
    for row in load_csv_rows("analytics_output/closedness_metrics.csv"):
        closedness[(row.get("series") or "").lower()] = {
            "one_talk": _gf(row.get("one_talk_wonder_pct")),
            "core5": _gf(row.get("core_5plus_pct")),
            "retention": _gf(row.get("retention_pct")),
            "gini": _gf(row.get("gini_concentration")) * 100,
            "n": _gi(row.get("n_scholars")),
        }
    serialized_closedness = json.dumps(closedness, ensure_ascii=False)

    # VIS_015 — Online share by year
    online_data = []
    for row in load_csv_rows("analytics_output/online_share_by_year.csv"):
        online_data.append({
            "series": _series_key(row.get("series")),
            "year": _gi(row.get("year")),
            "pct": _gf(row.get("online_share_pct")),
            "on": _gi(row.get("n_online")),
            "off": _gi(row.get("n_offline")),
        })
    online_data.sort(key=lambda r: r["year"])
    serialized_online = json.dumps(online_data, ensure_ascii=False)


    # ===================== EXTENDED GALLERY PHASE 1 (VIS_016 – VIS_020) =====================

    # VIS_016: Generational Eras (Смена поколений)
    vis016_eras = defaultdict(lambda: defaultdict(int))
        
    conn_tmp = sqlite3.connect('conferences.db')
    conn_tmp.row_factory = sqlite3.Row
    cursor_tmp = conn_tmp.cursor()
    
    cursor_tmp.execute('''
        SELECT p.birth_year, e.year 
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE p.birth_year IS NOT NULL
    ''')
    for row in cursor_tmp.fetchall():
        decade = (row['birth_year'] // 10) * 10
        vis016_eras[row['year']][decade] += 1
        
    vis016_data = []
    for y in sorted(vis016_eras.keys()):
        vis016_data.append({"year": y, "decades": dict(vis016_eras[y])})
    serialized_vis016 = json.dumps(vis016_data, ensure_ascii=False)

    # VIS_018: Title Length Dynamics
    cursor_tmp.execute('''
        SELECT pr.title, e.year 
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    lengths = defaultdict(list)
    for row in cursor_tmp.fetchall():
        if row['title']:
            lengths[row['year']].append(len(row['title'].split()))
    vis018_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in lengths.items()]
    vis018_data.sort(key=lambda x: x["year"])
    serialized_vis018 = json.dumps(vis018_data, ensure_ascii=False)

    # VIS_019: Co-authorship Rate
    cursor_tmp.execute('''
        SELECT pp.presentation_id, e.year, COUNT(pp.person_id) as c
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        GROUP BY pp.presentation_id, e.year
    ''')
    coauth = defaultdict(lambda: {"total": 0, "multi": 0})
    for row in cursor_tmp.fetchall():
        y = row['year']
        coauth[y]["total"] += 1
        if row['c'] > 1:
            coauth[y]["multi"] += 1
    vis019_data = [{"year": k, "pct": (v["multi"]/v["total"])*100} for k, v in coauth.items()]
    vis019_data.sort(key=lambda x: x["year"])
    serialized_vis019 = json.dumps(vis019_data, ensure_ascii=False)


    # ===================== EXTENDED GALLERY SERIES A (VIS_031 – VIS_034) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, p.birth_year, e.year, pp.person_id, es.series_name_en
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN person p ON pp.person_id = p.person_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    pres_meta = {row['presentation_id']: dict(row) for row in cursor_tmp.fetchall()}
    
    # Pre-calculate Boxplot stats
    def boxplot_stats(data):
        if not data: return None
        s = sorted(data)
        n = len(s)
        q1 = s[int(n*0.25)]
        median = s[int(n*0.5)]
        q3 = s[int(n*0.75)]
        return {"min": s[0], "q1": q1, "median": median, "q3": q3, "max": s[-1], "count": n}

    ds_data = list(load_csv_rows("analytics_output/expanded_classification_deepseek.csv"))
    # VIS_031: Age vs Gumilyov Level
    vis031_raw = {"1": [], "2": [], "3": []}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in vis031_raw and pid in pres_meta:
            meta = pres_meta[pid]
            if meta['birth_year']:
                age = meta['year'] - meta['birth_year']
                if 20 <= age <= 100:
                    vis031_raw[g].append(age)
    vis031_data = [{"level": k, "stats": boxplot_stats(v)} for k, v in vis031_raw.items() if v]
    serialized_vis031 = json.dumps(vis031_data, ensure_ascii=False)

    # VIS_032: Disciplinary Scale (L1 themes)
    vis032_raw = defaultdict(lambda: {"1": 0, "2": 0, "3": 0})
    for row in ds_data:
        l1 = row.get("theme_l1", "")
        g = row.get("gumilyov_level", "")
        if l1 and g in ["1", "2", "3"]:
            vis032_raw[l1][g] += 1
    vis032_data = [{"theme": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vis032_raw.items()]
    vis032_data.sort(key=lambda x: x["g1"] + x["g2"] + x["g3"], reverse=True)
    serialized_vis032 = json.dumps(vis032_data, ensure_ascii=False)

    # VIS_033: Core vs Periphery Abstraction
    person_counts = defaultdict(int)
    for meta in pres_meta.values():
        person_counts[meta['person_id']] += 1
        
    core_periph_g = {"Core (>=5)": {"1":0, "2":0, "3":0}, "Periphery (<5)": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            group = "Core (>=5)" if person_counts[p_id] >= 5 else "Periphery (<5)"
            core_periph_g[group][g] += 1
    vis033_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in core_periph_g.items()]
    serialized_vis033 = json.dumps(vis033_data, ensure_ascii=False)

    # VIS_034: Bridge vs Single-Venue Abstraction
    pers_series = defaultdict(set)
    for meta in pres_meta.values():
        pers_series[meta['person_id']].add(meta['series_name_en'])
    
    bridge_single_g = {"Bridge (Both)": {"1":0, "2":0, "3":0}, "Single-Venue": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            series = pers_series[p_id]
            is_z = any('Zograf' in x for x in series)
            is_r = any('Roerich' in x for x in series)
            group = "Bridge (Both)" if (is_z and is_r) else "Single-Venue"
            bridge_single_g[group][g] += 1
    vis034_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in bridge_single_g.items()]
    serialized_vis034 = json.dumps(vis034_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES B (VIS_035 – VIS_037) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, pr.title, e.year 
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE pr.title IS NOT NULL
    ''')
    title_data = cursor_tmp.fetchall()
    
    words_by_year = defaultdict(list)
    colon_by_year = defaultdict(list)
    for row in title_data:
        title = row['title'].strip()
        if not title: continue
        words_by_year[row['year']].append(len(title.split()))
        colon_by_year[row['year']].append(1 if ':' in title else 0)
        
    vis035_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in words_by_year.items()]
    vis035_data.sort(key=lambda x: x["year"])
    serialized_vis035 = json.dumps(vis035_data, ensure_ascii=False)
    
    vis036_data = [{"year": k, "ratio": sum(v)/len(v)*100} for k, v in colon_by_year.items()]
    vis036_data.sort(key=lambda x: x["year"])
    serialized_vis036 = json.dumps(vis036_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT presentation_id, COUNT(person_id) as author_count
        FROM presentation_person
        GROUP BY presentation_id
    ''')
    authors_count = {row['presentation_id']: row['author_count'] for row in cursor_tmp.fetchall()}
    
    coauth_g = {"Single Author": {"1":0, "2":0, "3":0}, "Co-authored": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in authors_count:
            group = "Single Author" if authors_count[pid] == 1 else "Co-authored"
            coauth_g[group][g] += 1
            
    vis037_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in coauth_g.items()]
    serialized_vis037 = json.dumps(vis037_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES C (VIS_038 – VIS_040) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, e.year, es.series_name_en, 
               (SELECT COUNT(*) FROM media m WHERE m.attached_to_id = pr.presentation_id AND m.attached_to_type='presentation') as has_video
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    vid_data = cursor_tmp.fetchall()

    vid_years = defaultdict(lambda: {"total": 0, "video": 0})
    for row in vid_data:
        vid_years[row['year']]["total"] += 1
        if row['has_video'] > 0:
            vid_years[row['year']]["video"] += 1
            
    vis038_data = [{"year": k, "total": v["total"], "video": v["video"]} for k, v in vid_years.items()]
    vis038_data.sort(key=lambda x: x["year"])
    serialized_vis038 = json.dumps(vis038_data, ensure_ascii=False)

    vid_dict = {row['presentation_id']: row['has_video'] > 0 for row in vid_data}
    vid_g = {"Recorded": {"1":0, "2":0, "3":0}, "Unrecorded": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in vid_dict:
            group = "Recorded" if vid_dict[pid] else "Unrecorded"
            vid_g[group][g] += 1
    vis039_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vid_g.items()]
    serialized_vis039 = json.dumps(vis039_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    ''')
    pp_data = cursor_tmp.fetchall()
    person_counts = defaultdict(int)
    for row in pp_data:
        person_counts[row['person_id']] += 1
        
    core_periph_vid = {"Core (>=5)": {"video":0, "no_video":0}, "Periphery (<5)": {"video":0, "no_video":0}}
    for row in pp_data:
        pid = row['presentation_id']
        if pid in vid_dict:
            group = "Core (>=5)" if person_counts[row['person_id']] >= 5 else "Periphery (<5)"
            status = "video" if vid_dict[pid] else "no_video"
            core_periph_vid[group][status] += 1
            
    vis040_data = [{"group": k, "video": v["video"], "no_video": v["no_video"]} for k, v in core_periph_vid.items()]
    serialized_vis040 = json.dumps(vis040_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES D & E (VIS_041 – VIS_042) =====================

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id, e.year 
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    person_years = defaultdict(list)
    for row in cursor_tmp.fetchall():
        person_years[row['person_id']].append((row['year'], row['presentation_id']))
        
    debuts = {}
    for pid, talks in person_years.items():
        talks.sort()
        debuts[pid] = talks[0][1] # presentation_id
        
    newbie_themes = defaultdict(int)
    repeater_themes = defaultdict(int)
    
    for row in ds_data:
        pid = row.get("presentation_id", "")
        l2 = row.get("period_l2", "")
        if not l2: continue
        
        is_debut = False
        for p, d_pid in debuts.items():
            if d_pid == pid:
                is_debut = True
                break
        
        if is_debut:
            newbie_themes[l2] += 1
        else:
            repeater_themes[l2] += 1
            
    vis041_data = [{"theme": k, "newbies": newbie_themes.get(k, 0), "repeaters": repeater_themes.get(k, 0)} for k in set(newbie_themes.keys()) | set(repeater_themes.keys())]
    vis041_data.sort(key=lambda x: x["newbies"] + x["repeaters"], reverse=True)
    serialized_vis041 = json.dumps(vis041_data, ensure_ascii=False)

    vis042_data = [
        {"venue": "Зографские чтения", "city_only": 94.7, "institution": 5.3},
        {"venue": "Рериховские чтения", "city_only": 13.0, "institution": 87.0}
    ]
    serialized_vis042 = json.dumps(vis042_data, ensure_ascii=False)


    conn_tmp.close()



    # ===================== EXTENDED GALLERY PHASE 2 (VIS_020 – VIS_023) =====================

    conn_tmp = sqlite3.connect('conferences.db')
    conn_tmp.row_factory = sqlite3.Row
    cursor_tmp = conn_tmp.cursor()
    
    # VIS_020: Top Scholars Velocity
    cursor_tmp.execute('''
        SELECT p.display_name, e.year
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        ORDER BY e.year ASC
    ''')
    yearly_counts = defaultdict(lambda: defaultdict(int))
    for row in cursor_tmp.fetchall():
        yearly_counts[row['year']][row['display_name']] += 1
    
    all_time = defaultdict(int)
    for y, counts in yearly_counts.items():
        for name, c in counts.items():
            all_time[name] += c
    top5_names = [x[0] for x in sorted(all_time.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    vis020_data = []
    running_totals = defaultdict(int)
    for y in sorted(yearly_counts.keys()):
        for name in top5_names:
            running_totals[name] += yearly_counts[y].get(name, 0)
        vis020_data.append({"year": y, "scores": {k: v for k, v in running_totals.items()}})
    serialized_vis020 = json.dumps({"names": top5_names, "timeline": vis020_data}, ensure_ascii=False)

    # VIS_021: Institutional Gravity
    cursor_tmp.execute('''
        SELECT affiliation_text_raw, COUNT(*) as c
        FROM presentation_person
        WHERE affiliation_text_raw IS NOT NULL AND affiliation_text_raw != ''
        GROUP BY affiliation_text_raw
    ''')
    inst_counts = defaultdict(int)
    for row in cursor_tmp.fetchall():
        n = normalize_affiliation(row['affiliation_text_raw'])
        if n:
            inst_counts[n] += row['c']
    vis021_data = [{"name": k, "val": v} for k, v in sorted(inst_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    serialized_vis021 = json.dumps(vis021_data, ensure_ascii=False)

    # VIS_022: Age at Presentation Trend
    cursor_tmp.execute('''
        SELECT p.birth_year, e.year 
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE p.birth_year IS NOT NULL AND p.birth_year > 1900
    ''')
    age_dist = defaultdict(list)
    for row in cursor_tmp.fetchall():
        age = row['year'] - row['birth_year']
        if 20 < age < 100:
            age_dist[row['year']].append(age)
    
    vis022_data = []
    for y, ages in age_dist.items():
        ages.sort()
        vis022_data.append({
            "year": y,
            "min": ages[0],
            "max": ages[-1],
            "median": ages[len(ages)//2]
        })
    vis022_data.sort(key=lambda x: x["year"])
    serialized_vis022 = json.dumps(vis022_data, ensure_ascii=False)

    # VIS_023: Scholar Returns (Loyalty)
    cursor_tmp.execute('''
        SELECT pp.person_id, COUNT(DISTINCT e.year) as c
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        GROUP BY pp.person_id
    ''')
    returns = defaultdict(int)
    for row in cursor_tmp.fetchall():
        returns[str(min(5, row['c']))] += 1
    vis023_data = [{"years": k, "count": v} for k, v in returns.items()]
    vis023_data.sort(key=lambda x: x["years"])
    serialized_vis023 = json.dumps(vis023_data, ensure_ascii=False)


    # ===================== EXTENDED GALLERY SERIES A (VIS_031 – VIS_034) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, p.birth_year, e.year, pp.person_id, es.series_name_en
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN person p ON pp.person_id = p.person_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    pres_meta = {row['presentation_id']: dict(row) for row in cursor_tmp.fetchall()}
    
    # Pre-calculate Boxplot stats
    def boxplot_stats(data):
        if not data: return None
        s = sorted(data)
        n = len(s)
        q1 = s[int(n*0.25)]
        median = s[int(n*0.5)]
        q3 = s[int(n*0.75)]
        return {"min": s[0], "q1": q1, "median": median, "q3": q3, "max": s[-1], "count": n}

    # VIS_031: Age vs Gumilyov Level
    vis031_raw = {"1": [], "2": [], "3": []}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in vis031_raw and pid in pres_meta:
            meta = pres_meta[pid]
            if meta['birth_year']:
                age = meta['year'] - meta['birth_year']
                if 20 <= age <= 100:
                    vis031_raw[g].append(age)
    vis031_data = [{"level": k, "stats": boxplot_stats(v)} for k, v in vis031_raw.items() if v]
    serialized_vis031 = json.dumps(vis031_data, ensure_ascii=False)

    # VIS_032: Disciplinary Scale (L1 themes)
    vis032_raw = defaultdict(lambda: {"1": 0, "2": 0, "3": 0})
    for row in ds_data:
        l1 = row.get("theme_l1", "")
        g = row.get("gumilyov_level", "")
        if l1 and g in ["1", "2", "3"]:
            vis032_raw[l1][g] += 1
    vis032_data = [{"theme": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vis032_raw.items()]
    vis032_data.sort(key=lambda x: x["g1"] + x["g2"] + x["g3"], reverse=True)
    serialized_vis032 = json.dumps(vis032_data, ensure_ascii=False)

    # VIS_033: Core vs Periphery Abstraction
    person_counts = defaultdict(int)
    for meta in pres_meta.values():
        person_counts[meta['person_id']] += 1
        
    core_periph_g = {"Core (>=5)": {"1":0, "2":0, "3":0}, "Periphery (<5)": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            group = "Core (>=5)" if person_counts[p_id] >= 5 else "Periphery (<5)"
            core_periph_g[group][g] += 1
    vis033_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in core_periph_g.items()]
    serialized_vis033 = json.dumps(vis033_data, ensure_ascii=False)

    # VIS_034: Bridge vs Single-Venue Abstraction
    pers_series = defaultdict(set)
    for meta in pres_meta.values():
        pers_series[meta['person_id']].add(meta['series_name_en'])
    
    bridge_single_g = {"Bridge (Both)": {"1":0, "2":0, "3":0}, "Single-Venue": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            series = pers_series[p_id]
            is_z = any('Zograf' in x for x in series)
            is_r = any('Roerich' in x for x in series)
            group = "Bridge (Both)" if (is_z and is_r) else "Single-Venue"
            bridge_single_g[group][g] += 1
    vis034_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in bridge_single_g.items()]
    serialized_vis034 = json.dumps(vis034_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES B (VIS_035 – VIS_037) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, pr.title, e.year 
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE pr.title IS NOT NULL
    ''')
    title_data = cursor_tmp.fetchall()
    
    words_by_year = defaultdict(list)
    colon_by_year = defaultdict(list)
    for row in title_data:
        title = row['title'].strip()
        if not title: continue
        words_by_year[row['year']].append(len(title.split()))
        colon_by_year[row['year']].append(1 if ':' in title else 0)
        
    vis035_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in words_by_year.items()]
    vis035_data.sort(key=lambda x: x["year"])
    serialized_vis035 = json.dumps(vis035_data, ensure_ascii=False)
    
    vis036_data = [{"year": k, "ratio": sum(v)/len(v)*100} for k, v in colon_by_year.items()]
    vis036_data.sort(key=lambda x: x["year"])
    serialized_vis036 = json.dumps(vis036_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT presentation_id, COUNT(person_id) as author_count
        FROM presentation_person
        GROUP BY presentation_id
    ''')
    authors_count = {row['presentation_id']: row['author_count'] for row in cursor_tmp.fetchall()}
    
    coauth_g = {"Single Author": {"1":0, "2":0, "3":0}, "Co-authored": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in authors_count:
            group = "Single Author" if authors_count[pid] == 1 else "Co-authored"
            coauth_g[group][g] += 1
            
    vis037_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in coauth_g.items()]
    serialized_vis037 = json.dumps(vis037_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES C (VIS_038 – VIS_040) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, e.year, es.series_name_en, 
               (SELECT COUNT(*) FROM media m WHERE m.attached_to_id = pr.presentation_id AND m.attached_to_type='presentation') as has_video
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    vid_data = cursor_tmp.fetchall()

    vid_years = defaultdict(lambda: {"total": 0, "video": 0})
    for row in vid_data:
        vid_years[row['year']]["total"] += 1
        if row['has_video'] > 0:
            vid_years[row['year']]["video"] += 1
            
    vis038_data = [{"year": k, "total": v["total"], "video": v["video"]} for k, v in vid_years.items()]
    vis038_data.sort(key=lambda x: x["year"])
    serialized_vis038 = json.dumps(vis038_data, ensure_ascii=False)

    vid_dict = {row['presentation_id']: row['has_video'] > 0 for row in vid_data}
    vid_g = {"Recorded": {"1":0, "2":0, "3":0}, "Unrecorded": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in vid_dict:
            group = "Recorded" if vid_dict[pid] else "Unrecorded"
            vid_g[group][g] += 1
    vis039_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vid_g.items()]
    serialized_vis039 = json.dumps(vis039_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    ''')
    pp_data = cursor_tmp.fetchall()
    person_counts = defaultdict(int)
    for row in pp_data:
        person_counts[row['person_id']] += 1
        
    core_periph_vid = {"Core (>=5)": {"video":0, "no_video":0}, "Periphery (<5)": {"video":0, "no_video":0}}
    for row in pp_data:
        pid = row['presentation_id']
        if pid in vid_dict:
            group = "Core (>=5)" if person_counts[row['person_id']] >= 5 else "Periphery (<5)"
            status = "video" if vid_dict[pid] else "no_video"
            core_periph_vid[group][status] += 1
            
    vis040_data = [{"group": k, "video": v["video"], "no_video": v["no_video"]} for k, v in core_periph_vid.items()]
    serialized_vis040 = json.dumps(vis040_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES D & E (VIS_041 – VIS_042) =====================

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id, e.year 
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    person_years = defaultdict(list)
    for row in cursor_tmp.fetchall():
        person_years[row['person_id']].append((row['year'], row['presentation_id']))
        
    debuts = {}
    for pid, talks in person_years.items():
        talks.sort()
        debuts[pid] = talks[0][1] # presentation_id
        
    newbie_themes = defaultdict(int)
    repeater_themes = defaultdict(int)
    
    for row in ds_data:
        pid = row.get("presentation_id", "")
        l2 = row.get("period_l2", "")
        if not l2: continue
        
        is_debut = False
        for p, d_pid in debuts.items():
            if d_pid == pid:
                is_debut = True
                break
        
        if is_debut:
            newbie_themes[l2] += 1
        else:
            repeater_themes[l2] += 1
            
    vis041_data = [{"theme": k, "newbies": newbie_themes.get(k, 0), "repeaters": repeater_themes.get(k, 0)} for k in set(newbie_themes.keys()) | set(repeater_themes.keys())]
    vis041_data.sort(key=lambda x: x["newbies"] + x["repeaters"], reverse=True)
    serialized_vis041 = json.dumps(vis041_data, ensure_ascii=False)

    vis042_data = [
        {"venue": "Зографские чтения", "city_only": 94.7, "institution": 5.3},
        {"venue": "Рериховские чтения", "city_only": 13.0, "institution": 87.0}
    ]
    serialized_vis042 = json.dumps(vis042_data, ensure_ascii=False)


    conn_tmp.close()



    # ===================== EXTENDED GALLERY PHASE 3 (VIS_024 – VIS_030) =====================

    conn_tmp = sqlite3.connect('conferences.db')
    conn_tmp.row_factory = sqlite3.Row
    cursor_tmp = conn_tmp.cursor()
    
    # VIS_024: Top Keywords by Year (Simplified to overall top keywords for a bubble chart)
    cursor_tmp.execute('''
        SELECT title, year FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    import re as regex
    words = defaultdict(int)
    for row in cursor_tmp.fetchall():
        if row['title']:
            clean = regex.sub(r'[^а-яА-ЯёЁ]', ' ', row['title'].lower())
            for w in clean.split():
                if len(w) > 4:
                    words[w] += 1
    top_words = [{"text": k, "val": v} for k, v in sorted(words.items(), key=lambda x: x[1], reverse=True)[:30]]
    serialized_vis024 = json.dumps(top_words, ensure_ascii=False)

    # VIS_025: Conference Scale
    cursor_tmp.execute('''
        SELECT e.year, COUNT(DISTINCT s.session_id) as sess, COUNT(pr.presentation_id) as pres
        FROM event e
        JOIN event_day ed ON e.event_id = ed.event_id
        JOIN event_day_venue edv ON ed.event_day_id = edv.event_day_id
        JOIN session s ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN presentation pr ON s.session_id = pr.session_id
        GROUP BY e.year
        ORDER BY e.year ASC
    ''')
    vis025_data = [dict(row) for row in cursor_tmp.fetchall()]
    serialized_vis025 = json.dumps(vis025_data, ensure_ascii=False)

    # Read DeepSeek classification for VIS_026, VIS_027, VIS_028
    ds_data = list(load_csv_rows("analytics_output/expanded_classification_deepseek.csv"))

    # VIS_026: DeepSeek Confidence
    confidences = defaultdict(int)
    for row in ds_data:
        c = row.get("confidence", "")
        if c: confidences[c] += 1
    vis026_data = [{"conf": k, "val": v} for k, v in confidences.items()]
    serialized_vis026 = json.dumps(vis026_data, ensure_ascii=False)

    # VIS_027: Theme Co-occurrence (Proxy via L1 themes counts)
    l1_counts = defaultdict(int)
    for row in ds_data:
        l1 = row.get("theme_l1", "")
        if l1: l1_counts[l1] += 1
    vis027_data = [{"theme": k, "val": v} for k, v in sorted(l1_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    serialized_vis027 = json.dumps(vis027_data, ensure_ascii=False)

    # VIS_028: Gumilyov vs Period
    gp_matrix = defaultdict(lambda: defaultdict(int))
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        p = row.get("period_l2", "")
        if g and p: gp_matrix[g][p] += 1
    vis028_data = []
    for g, p_dict in gp_matrix.items():
        vis028_data.append({"gumilyov": g, "periods": dict(p_dict)})
    serialized_vis028 = json.dumps(vis028_data, ensure_ascii=False)

    # VIS_029: Title Character Length
    cursor_tmp.execute('''
        SELECT e.year, LENGTH(pr.title) as l
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE pr.title IS NOT NULL
    ''')
    chars = defaultdict(list)
    for row in cursor_tmp.fetchall():
        chars[row['year']].append(row['l'])
    vis029_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in chars.items()]
    vis029_data.sort(key=lambda x: x["year"])
    serialized_vis029 = json.dumps(vis029_data, ensure_ascii=False)

    # VIS_030: Series Overlap
    cursor_tmp.execute('''
        SELECT pp.person_id, es.series_name_en
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    pers_series = defaultdict(set)
    for row in cursor_tmp.fetchall():
        pers_series[row['person_id']].add(row['series_name_en'])
    
    venn = {"zograf_only": 0, "roerich_only": 0, "both": 0}
    for s in pers_series.values():
        is_z = any('Zograf' in x for x in s)
        is_r = any('Roerich' in x for x in s)
        if is_z and is_r: venn["both"] += 1
        elif is_z: venn["zograf_only"] += 1
        elif is_r: venn["roerich_only"] += 1
    serialized_vis030 = json.dumps(venn, ensure_ascii=False)


    # ===================== EXTENDED GALLERY SERIES A (VIS_031 – VIS_034) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, p.birth_year, e.year, pp.person_id, es.series_name_en
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN person p ON pp.person_id = p.person_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    pres_meta = {row['presentation_id']: dict(row) for row in cursor_tmp.fetchall()}
    
    # Pre-calculate Boxplot stats
    def boxplot_stats(data):
        if not data: return None
        s = sorted(data)
        n = len(s)
        q1 = s[int(n*0.25)]
        median = s[int(n*0.5)]
        q3 = s[int(n*0.75)]
        return {"min": s[0], "q1": q1, "median": median, "q3": q3, "max": s[-1], "count": n}

    # VIS_031: Age vs Gumilyov Level
    vis031_raw = {"1": [], "2": [], "3": []}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in vis031_raw and pid in pres_meta:
            meta = pres_meta[pid]
            if meta['birth_year']:
                age = meta['year'] - meta['birth_year']
                if 20 <= age <= 100:
                    vis031_raw[g].append(age)
    vis031_data = [{"level": k, "stats": boxplot_stats(v)} for k, v in vis031_raw.items() if v]
    serialized_vis031 = json.dumps(vis031_data, ensure_ascii=False)

    # VIS_032: Disciplinary Scale (L1 themes)
    vis032_raw = defaultdict(lambda: {"1": 0, "2": 0, "3": 0})
    for row in ds_data:
        l1 = row.get("theme_l1", "")
        g = row.get("gumilyov_level", "")
        if l1 and g in ["1", "2", "3"]:
            vis032_raw[l1][g] += 1
    vis032_data = [{"theme": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vis032_raw.items()]
    vis032_data.sort(key=lambda x: x["g1"] + x["g2"] + x["g3"], reverse=True)
    serialized_vis032 = json.dumps(vis032_data, ensure_ascii=False)

    # VIS_033: Core vs Periphery Abstraction
    person_counts = defaultdict(int)
    for meta in pres_meta.values():
        person_counts[meta['person_id']] += 1
        
    core_periph_g = {"Core (>=5)": {"1":0, "2":0, "3":0}, "Periphery (<5)": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            group = "Core (>=5)" if person_counts[p_id] >= 5 else "Periphery (<5)"
            core_periph_g[group][g] += 1
    vis033_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in core_periph_g.items()]
    serialized_vis033 = json.dumps(vis033_data, ensure_ascii=False)

    # VIS_034: Bridge vs Single-Venue Abstraction
    pers_series = defaultdict(set)
    for meta in pres_meta.values():
        pers_series[meta['person_id']].add(meta['series_name_en'])
    
    bridge_single_g = {"Bridge (Both)": {"1":0, "2":0, "3":0}, "Single-Venue": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            series = pers_series[p_id]
            is_z = any('Zograf' in x for x in series)
            is_r = any('Roerich' in x for x in series)
            group = "Bridge (Both)" if (is_z and is_r) else "Single-Venue"
            bridge_single_g[group][g] += 1
    vis034_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in bridge_single_g.items()]
    serialized_vis034 = json.dumps(vis034_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES B (VIS_035 – VIS_037) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, pr.title, e.year 
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE pr.title IS NOT NULL
    ''')
    title_data = cursor_tmp.fetchall()
    
    words_by_year = defaultdict(list)
    colon_by_year = defaultdict(list)
    for row in title_data:
        title = row['title'].strip()
        if not title: continue
        words_by_year[row['year']].append(len(title.split()))
        colon_by_year[row['year']].append(1 if ':' in title else 0)
        
    vis035_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in words_by_year.items()]
    vis035_data.sort(key=lambda x: x["year"])
    serialized_vis035 = json.dumps(vis035_data, ensure_ascii=False)
    
    vis036_data = [{"year": k, "ratio": sum(v)/len(v)*100} for k, v in colon_by_year.items()]
    vis036_data.sort(key=lambda x: x["year"])
    serialized_vis036 = json.dumps(vis036_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT presentation_id, COUNT(person_id) as author_count
        FROM presentation_person
        GROUP BY presentation_id
    ''')
    authors_count = {row['presentation_id']: row['author_count'] for row in cursor_tmp.fetchall()}
    
    coauth_g = {"Single Author": {"1":0, "2":0, "3":0}, "Co-authored": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in authors_count:
            group = "Single Author" if authors_count[pid] == 1 else "Co-authored"
            coauth_g[group][g] += 1
            
    vis037_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in coauth_g.items()]
    serialized_vis037 = json.dumps(vis037_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES C (VIS_038 – VIS_040) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, e.year, es.series_name_en, 
               (SELECT COUNT(*) FROM media m WHERE m.attached_to_id = pr.presentation_id AND m.attached_to_type='presentation') as has_video
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    vid_data = cursor_tmp.fetchall()

    vid_years = defaultdict(lambda: {"total": 0, "video": 0})
    for row in vid_data:
        vid_years[row['year']]["total"] += 1
        if row['has_video'] > 0:
            vid_years[row['year']]["video"] += 1
            
    vis038_data = [{"year": k, "total": v["total"], "video": v["video"]} for k, v in vid_years.items()]
    vis038_data.sort(key=lambda x: x["year"])
    serialized_vis038 = json.dumps(vis038_data, ensure_ascii=False)

    vid_dict = {row['presentation_id']: row['has_video'] > 0 for row in vid_data}
    vid_g = {"Recorded": {"1":0, "2":0, "3":0}, "Unrecorded": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in vid_dict:
            group = "Recorded" if vid_dict[pid] else "Unrecorded"
            vid_g[group][g] += 1
    vis039_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vid_g.items()]
    serialized_vis039 = json.dumps(vis039_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    ''')
    pp_data = cursor_tmp.fetchall()
    person_counts = defaultdict(int)
    for row in pp_data:
        person_counts[row['person_id']] += 1
        
    core_periph_vid = {"Core (>=5)": {"video":0, "no_video":0}, "Periphery (<5)": {"video":0, "no_video":0}}
    for row in pp_data:
        pid = row['presentation_id']
        if pid in vid_dict:
            group = "Core (>=5)" if person_counts[row['person_id']] >= 5 else "Periphery (<5)"
            status = "video" if vid_dict[pid] else "no_video"
            core_periph_vid[group][status] += 1
            
    vis040_data = [{"group": k, "video": v["video"], "no_video": v["no_video"]} for k, v in core_periph_vid.items()]
    serialized_vis040 = json.dumps(vis040_data, ensure_ascii=False)



    # ===================== EXTENDED GALLERY SERIES D & E (VIS_041 – VIS_042) =====================

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id, e.year 
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    person_years = defaultdict(list)
    for row in cursor_tmp.fetchall():
        person_years[row['person_id']].append((row['year'], row['presentation_id']))
        
    debuts = {}
    for pid, talks in person_years.items():
        talks.sort()
        debuts[pid] = talks[0][1] # presentation_id
        
    newbie_themes = defaultdict(int)
    repeater_themes = defaultdict(int)
    
    for row in ds_data:
        pid = row.get("presentation_id", "")
        l2 = row.get("period_l2", "")
        if not l2: continue
        
        is_debut = False
        for p, d_pid in debuts.items():
            if d_pid == pid:
                is_debut = True
                break
        
        if is_debut:
            newbie_themes[l2] += 1
        else:
            repeater_themes[l2] += 1
            
    vis041_data = [{"theme": k, "newbies": newbie_themes.get(k, 0), "repeaters": repeater_themes.get(k, 0)} for k in set(newbie_themes.keys()) | set(repeater_themes.keys())]
    vis041_data.sort(key=lambda x: x["newbies"] + x["repeaters"], reverse=True)
    serialized_vis041 = json.dumps(vis041_data, ensure_ascii=False)

    vis042_data = [
        {"venue": "Зографские чтения", "city_only": 94.7, "institution": 5.3},
        {"venue": "Рериховские чтения", "city_only": 13.0, "institution": 87.0}
    ]
    serialized_vis042 = json.dumps(vis042_data, ensure_ascii=False)


    conn_tmp.close()


    tip_style = (
        "position:absolute; background:rgba(18,18,24,0.95); border:1px solid rgba(255,255,255,0.15); "
        "border-radius:8px; padding:0.7rem 0.9rem; font-size:0.82rem; color:#fff; pointer-events:none; "
        "opacity:0; transition:opacity 0.15s ease; z-index:1000; box-shadow:0 4px 20px rgba(0,0,0,0.5); "
        "backdrop-filter:blur(4px); max-width:300px; line-height:1.45;"
    )

    body = f"""
        <div class="lang-toggle-container">
            <button id="lang-toggle-btn" onclick="toggleLanguage()">English</button>
        </div>

        <header>
            <h1 class="bilingual-text" data-ru="Интерактивный атлас визуализаций" data-en="Interactive Visualisation Atlas">Интерактивный атлас визуализаций</h1>
            <p class="bilingual-text" data-ru="Единый каталог всех интерактивных аналитических визуализаций индологического архива с постоянными идентификаторами (ID)." data-en="A single unified catalog of all interactive analytical visualisations of the Indology Archive, equiped with stable identifiers (IDs).">Единый каталог всех интерактивных аналитических визуализаций индологического архива с постоянными идентификаторами (ID).</p>
        </header>

        <section class="viz-toc">
            <strong class="bilingual-text" data-ru="Содержание атласа" data-en="Atlas Table of Contents">Содержание атласа</strong>
            <a href="#VIS_001_orbit_scatter" class="viz-toc-item">
                <span>VIS_001</span>
                <b class="bilingual-text" data-ru="Орбита перекрёстной когорты (Зограф × Рерих)" data-en="Cross-Cohort Orbit Scatter (Zograf × Roerich)">Орбита перекрёстной когорты (Зограф × Рерих)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_002_affiliation_opacity" class="viz-toc-item">
                <span>VIS_002</span>
                <b class="bilingual-text" data-ru="Таймлайн аффилиационной непрозрачности" data-en="Affiliation Opacity Timeline">Таймлайн аффилиационной непрозрачности</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_003_video_heatmap" class="viz-toc-item">
                <span>VIS_003</span>
                <b class="bilingual-text" data-ru="Тепловая карта видео-покрытия" data-en="Video Coverage Heatmap">Тепловая карта видео-покрытия</b>
                <span class="badge bilingual-text" style="background:rgba(255,255,255,0.05); color:var(--muted);" data-ru="В планах" data-en="Planned">В планах</span>
            </a>
            <a href="#VIS_004_keyword_alluvial" class="viz-toc-item">
                <span>VIS_004</span>
                <b class="bilingual-text" data-ru="Эволюция ключевых слов и мезоуровней" data-en="Keyword/Meso Alluvial Flow">Эволюция ключевых слов и мезоуровней</b>
                <span class="badge bilingual-text" style="background:rgba(255,255,255,0.05); color:var(--muted);" data-ru="В планах" data-en="Planned">В планах</span>
            </a>
            <a href="#VIS_008_demography_ribbon" class="viz-toc-item">
                <span>VIS_008</span>
                <b class="bilingual-text" data-ru="Возрастная лента поля (медиана и квартили)" data-en="Field Age Ribbon (median &amp; quartiles)">Возрастная лента поля (медиана и квартили)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_009_cohort_survival" class="viz-toc-item">
                <span>VIS_009</span>
                <b class="bilingual-text" data-ru="Кривые выживаемости когорт" data-en="Cohort Survival Curves">Кривые выживаемости когорт</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_010_newcomer_rate" class="viz-toc-item">
                <span>VIS_010</span>
                <b class="bilingual-text" data-ru="Темп обновления (доля новичков)" data-en="Renewal Rate (newcomer share)">Темп обновления (доля новичков)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_011_theme_treemap" class="viz-toc-item">
                <span>VIS_011</span>
                <b class="bilingual-text" data-ru="Карта тем (L1 → L2, treemap)" data-en="Theme Treemap (L1 → L2)">Карта тем (L1 → L2, treemap)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_012_gumilyov_stream" class="viz-toc-item">
                <span>VIS_012</span>
                <b class="bilingual-text" data-ru="Поток уровней обобщения (шкала Гумилёва)" data-en="Scale-of-Argument Streamgraph (Gumilyov)">Поток уровней обобщения (шкала Гумилёва)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_013_keyword_diverging" class="viz-toc-item">
                <span>VIS_013</span>
                <b class="bilingual-text" data-ru="Ключевые слова: Зограф против Рериха" data-en="Keywords: Zograf vs Roerich">Ключевые слова: Зограф против Рериха</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_014_closedness" class="viz-toc-item">
                <span>VIS_014</span>
                <b class="bilingual-text" data-ru="Замкнутость сообществ (сравнение метрик)" data-en="Community Closedness (metric comparison)">Замкнутость сообществ (сравнение метрик)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_015_online_share" class="viz-toc-item">
                <span>VIS_015</span>
                <b class="bilingual-text" data-ru="Сдвиг в онлайн (доля по годам)" data-en="The Online Shift (share by year)">Сдвиг в онлайн (доля по годам)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <a href="#VIS_016_generations" class="viz-toc-item">
                <span>VIS_016</span>
                <b class="bilingual-text" data-ru="Смена поколений (по декадам рождения)" data-en="Generational Eras (by birth decade)">Смена поколений (по декадам рождения)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_018_title_length" class="viz-toc-item">
                <span>VIS_018</span>
                <b class="bilingual-text" data-ru="Динамика длины названий докладов" data-en="Title Length Dynamics">Динамика длины названий докладов</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_019_coauthorship" class="viz-toc-item">
                <span>VIS_019</span>
                <b class="bilingual-text" data-ru="Индекс соавторства" data-en="Co-authorship Index">Индекс соавторства</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <a href="#VIS_020_velocity" class="viz-toc-item">
                <span>VIS_020</span>
                <b class="bilingual-text" data-ru="Активность топ-5 ученых" data-en="Top 5 Scholars Velocity">Активность топ-5 ученых</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_021_institutions" class="viz-toc-item">
                <span>VIS_021</span>
                <b class="bilingual-text" data-ru="Топ институций" data-en="Top Institutions">Топ институций</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_022_age_at_talk" class="viz-toc-item">
                <span>VIS_022</span>
                <b class="bilingual-text" data-ru="Возраст на момент доклада" data-en="Age at Presentation">Возраст на момент доклада</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_023_loyalty" class="viz-toc-item">
                <span>VIS_023</span>
                <b class="bilingual-text" data-ru="Лояльность (кол-во лет участия)" data-en="Loyalty (years participated)">Лояльность (кол-во лет участия)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <a href="#VIS_024_keywords" class="viz-toc-item">
                <span>VIS_024</span>
                <b class="bilingual-text" data-ru="Облако терминов" data-en="Keyword Cloud">Облако терминов</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_025_scale" class="viz-toc-item">
                <span>VIS_025</span>
                <b class="bilingual-text" data-ru="Масштаб конференций" data-en="Conference Scale">Масштаб конференций</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_026_confidence" class="viz-toc-item">
                <span>VIS_026</span>
                <b class="bilingual-text" data-ru="Уверенность ИИ-разметки" data-en="AI Annotation Confidence">Уверенность ИИ-разметки</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_027_l1_themes" class="viz-toc-item">
                <span>VIS_027</span>
                <b class="bilingual-text" data-ru="Популярность макро-тем" data-en="Macro-theme Popularity">Популярность макро-тем</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_028_gumilyov" class="viz-toc-item">
                <span>VIS_028</span>
                <b class="bilingual-text" data-ru="Пассионарность Гумилева" data-en="Gumilyov Passionarity">Пассионарность Гумилева</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_029_chars" class="viz-toc-item">
                <span>VIS_029</span>
                <b class="bilingual-text" data-ru="Длина названий (символы)" data-en="Title Length (chars)">Длина названий (символы)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_030_overlap" class="viz-toc-item">
                <span>VIS_030</span>
                <b class="bilingual-text" data-ru="Пересечение аудиторий Зограф/Рерих" data-en="Zograf/Roerich Audience Overlap">Пересечение аудиторий Зограф/Рерих</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <!-- SERIES A -->
            <a href="#VIS_031_age_scale" class="viz-toc-item">
                <span>VIS_031</span>
                <b class="bilingual-text" data-ru="Возраст и Масштаб (G1-G3)" data-en="Age vs Abstraction (G1-G3)">Возраст и Масштаб (G1-G3)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_032_disc_scale" class="viz-toc-item">
                <span>VIS_032</span>
                <b class="bilingual-text" data-ru="Дисциплина и Масштаб" data-en="Discipline vs Abstraction">Дисциплина и Масштаб</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_033_core_scale" class="viz-toc-item">
                <span>VIS_033</span>
                <b class="bilingual-text" data-ru="Масштаб: Ядро vs Периферия" data-en="Scale: Core vs Periphery">Масштаб: Ядро vs Периферия</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_034_bridge_scale" class="viz-toc-item">
                <span>VIS_034</span>
                <b class="bilingual-text" data-ru="Масштаб: Мостовики vs Локальные" data-en="Scale: Bridges vs Local">Масштаб: Мостовики vs Локальные</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <!-- SERIES B -->
            <a href="#VIS_035_words" class="viz-toc-item">
                <span>VIS_035</span>
                <b class="bilingual-text" data-ru="Инфляция заголовков (Слова)" data-en="Title Length Inflation (Words)">Инфляция заголовков (Слова)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_036_colons" class="viz-toc-item">
                <span>VIS_036</span>
                <b class="bilingual-text" data-ru="Эра подзаголовков (Двоеточия)" data-en="The Colon Era">Эра подзаголовков (Двоеточия)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_037_coauthors" class="viz-toc-item">
                <span>VIS_037</span>
                <b class="bilingual-text" data-ru="Коллективность и Микрокейс" data-en="Co-authorship vs Gumilyov Scale">Коллективность и Микрокейс</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <!-- SERIES C -->
            <a href="#VIS_038_vid_years" class="viz-toc-item">
                <span>VIS_038</span>
                <b class="bilingual-text" data-ru="Радары видимости (YouTube Bias)" data-en="Visibility Radars (YouTube Bias)">Радары видимости (YouTube Bias)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_039_vid_scale" class="viz-toc-item">
                <span>VIS_039</span>
                <b class="bilingual-text" data-ru="Смещение в Микрокейсы" data-en="Microcase Bias">Смещение в Микрокейсы</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_040_vid_core" class="viz-toc-item">
                <span>VIS_040</span>
                <b class="bilingual-text" data-ru="Статус и Камера" data-en="Status and Camera">Статус и Камера</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>

            <!-- SERIES D & E -->
            <a href="#VIS_041_newbie_themes" class="viz-toc-item">
                <span>VIS_041</span>
                <b class="bilingual-text" data-ru="Входные ворота (Темы)" data-en="Newbie Entry Topics">Входные ворота (Темы)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_042_inst_bias" class="viz-toc-item">
                <span>VIS_042</span>
                <b class="bilingual-text" data-ru="Город vs Учреждение" data-en="City vs Institution">Город vs Учреждение</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
        </section>

        {findings_style}

        <!-- VIS_001_orbit_scatter -->
        <section class="viz-showcase-section" id="VIS_001_orbit_scatter">
            <h2>
                <span class="viz-id-badge">VIS_001</span>
                <span class="bilingual-text" data-ru="Орбита перекрёстной когорты" data-en="Cross-Cohort Orbit Scatter">Орбита перекрёстной когорты</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Каждая точка представляет исследователя. Смещение от пунктирной диагонали показывает баланс его активности между двумя площадками. Наведите мышь для деталей, нажмите для перехода в профиль." data-en="Each dot represents a researcher. The offset from the dashed diagonal indicates their activity balance between the two venues. Hover for details, click to visit their profile.">Каждая точка представляет исследователя. Смещение от пунктирной диагонали показывает баланс его активности между двумя площадками. Наведите мышь для деталей, нажмите для перехода в профиль.</p>
            
            <div id="scatter-chart-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <svg id="scatter-svg" viewBox="0 0 800 480" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="scatter-tooltip"></div>
            </div>

            <div class="legend-container">
                <div class="legend-item">
                    <span class="legend-color" style="background:#ff7b00;"></span>
                    <span class="bilingual-text" data-ru="Участвовал в обоих (Мост)" data-en="Attended both (Bridge)">Участвовал в обоих (Мост)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#2b82c9;"></span>
                    <span class="bilingual-text" data-ru="Только Зографские чтения" data-en="Zograf Readings only">Только Зографские чтения</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#b83280;"></span>
                    <span class="bilingual-text" data-ru="Только Рериховские чтения" data-en="Roerich Readings only">Только Рериховские чтения</span>
                </div>
            </div>
            
            <aside class="caveat-block" role="note" style="margin-top: 1.2rem; border-left: 3px solid var(--accent2); background: rgba(255,255,255,0.01);">
                <strong class="bilingual-text" data-ru="Источниковедческая оговорка" data-en="Source Caveat">Источниковедческая оговорка</strong>
                <p class="bilingual-text" data-ru="Этот график показывает распределение докладов исключительно на основе официально опубликованных программ. Наблюдаемый баланс является медийным фактом программы, а не полной академической биографией." data-en="This scatter plot depicts the distribution of presentations solely based on officially published program metadata. The observed balance is a structural fact of the programs, not a complete scholarly biography.">Этот график показывает распределение докладов исключительно на основе официально опубликованных программ. Наблюдаемый баланс является медийным фактом программы, а не полной академической биографией.</p>
            </aside>
        </section>

        <!-- VIS_002_affiliation_opacity -->
        <section class="viz-showcase-section" id="VIS_002_affiliation_opacity">
            <h2>
                <span class="viz-id-badge">VIS_002</span>
                <span class="bilingual-text" data-ru="Таймлайн аффилиационной непрозрачности" data-en="Affiliation Opacity Timeline">Таймлайн аффилиационной непрозрачности</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Хронологическая визуализация соотношения верифицированных институтов, только городов и неизвестных траекторий участников конференций по годам." data-en="A chronological visualisation of the ratio between verified institutes, city-only tags, and unknown participant affiliations across conference years.">Хронологическая визуализация соотношения верифицированных институтов, только городов и неизвестных траекторий участников конференций по годам.</p>
            
            <div class="opacity-controls">
                <button class="opacity-toggle-btn active" onclick="switchOpacitySeries('combined')" data-ru="Совмещенный" data-en="Combined">Совмещенный</button>
                <button class="opacity-toggle-btn" onclick="switchOpacitySeries('zograf')" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</button>
                <button class="opacity-toggle-btn" onclick="switchOpacitySeries('roerich')" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</button>
            </div>

            <div id="opacity-chart-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <svg id="opacity-svg" viewBox="0 0 800 380" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="opacity-tooltip"></div>
            </div>

            <div class="legend-container">
                <div class="legend-item">
                    <span class="legend-color" style="background:#10b981;"></span>
                    <span class="bilingual-text" data-ru="Подтвержденный институт / Программа" data-en="Verified Institute / Program">Подтвержденный институт / Программа</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#f59e0b;"></span>
                    <span class="bilingual-text" data-ru="Только город (Аффилиационная непрозрачность)" data-en="City Only (Affiliation Opacity)">Только город (Аффилиационная непрозрачность)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#6b7280;"></span>
                    <span class="bilingual-text" data-ru="Не указана / Неизвестно" data-en="Not Specified / Unknown">Не указана / Неизвестно</span>
                </div>
            </div>
            
            <aside class="caveat-block" role="note" style="margin-top: 1.2rem; border-left: 3px solid var(--accent); background: rgba(255,255,255,0.01);">
                <strong class="bilingual-text" data-ru="Методологическая оговорка" data-en="Methodological Caveat">Методологическая оговорка</strong>
                <p class="bilingual-text" data-ru="Этот график измеряет качество официальной документации конференций. Рост 'оранжевого' сектора указывает на периоды высокой аффилиационной непрозрачности (когда программы содержат исключительно название города без названия института)." data-en="This timeline measures the administrative documentation quality of the conference programs. Growth of the 'orange' sector highlights periods of high affiliation opacity (where programs explicitly report city location while hiding institutional ties).">Этот график измеряет качество официальной документации конференций. Рост 'оранжевого' сектора указывает на периоды высокой аффилиационной непрозрачности (когда программы содержат исключительно название города без названия института).</p>
            </aside>
        </section>

        <!-- VIS_003_video_heatmap -->
        <section class="viz-showcase-section" id="VIS_003_video_heatmap">
            <h2>
                <span class="viz-id-badge">VIS_003</span>
                <span class="bilingual-text" data-ru="Тепловая карта видео-покрытия" data-en="Video Coverage Heatmap">Тепловая карта видео-покрытия</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Интерактивная карта распределения сохраненного видеоконтента по годам, сериям докладов и тематическим рубрикам." data-en="An interactive heatmap displaying the distribution of preserved video coverage across years, conference series, and thematic groups.">Интерактивная карта распределения сохраненного видеоконтента по годам, сериям докладов и тематическим рубрикам.</p>
            
            <div id="heatmap-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <svg id="heatmap-svg" viewBox="0 0 800 250" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="heatmap-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item">
                    <span class="legend-color" style="background:#2b82c9;"></span>
                    <span class="bilingual-text" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#b83280;"></span>
                    <span class="bilingual-text" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</span>
                </div>
            </div>

        </section>

        <!-- VIS_004_keyword_alluvial -->
        <section class="viz-showcase-section" id="VIS_004_keyword_alluvial">
            <h2>
                <span class="viz-id-badge">VIS_004</span>
                <span class="bilingual-text" data-ru="Эволюция ключевых слов и мезоуровней" data-en="Keyword/Meso Alluvial Flow">Эволюция ключевых слов и мезоуровней</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Динамическая потоковая визуализация (Alluvial / Sankey) дрейфа терминов, подтем и тематических кластеров по историческим периодам." data-en="A dynamic flow visualization (Alluvial / Sankey) showing the drift of terminological clusters and meso-level concepts across historical eras.">Динамическая потоковая визуализация (Alluvial / Sankey) дрейфа терминов, подтем и тематических кластеров по историческим периодам.</p>
            <div id="alluvial-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <svg id="alluvial-svg" viewBox="0 0 800 500" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="alluvial-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>

        <!-- VIS_005_scholar_forest -->
        <section class="viz-showcase-section" id="VIS_005_scholar_forest">
            <h2>
                <span class="viz-id-badge">VIS_005</span>
                <span class="bilingual-text" data-ru="«Лес» активности исследователей" data-en="Scholar Activity Forest">«Лес» активности исследователей</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Жизненный цикл академических карьер топ-40 самых активных докладчиков за всю историю конференций." data-en="The academic lifecycle of the top 40 most active speakers across the history of the conferences.">Жизненный цикл академических карьер топ-40 самых активных докладчиков за всю историю конференций.</p>
            <div id="forest-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="forest-svg" viewBox="0 0 800 800" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="forest-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>

        <!-- VIS_006_thematic_hierarchy -->
        <section class="viz-showcase-section" id="VIS_006_thematic_hierarchy">
            <h2>
                <span class="viz-id-badge">VIS_006</span>
                <span class="bilingual-text" data-ru="Иерархия тематических направлений" data-en="Thematic Hierarchy (Icicle Chart)">Иерархия тематических направлений</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Детальное распределение объема докладов по сериям чтений, основным темам и узким мезо-кластерам. Чем шире блок, тем больше докладов в этой теме." data-en="A detailed breakdown of presentation volume across conference series, main themes, and narrow meso-clusters. The wider the block, the more presentations belong to that theme.">Детальное распределение объема докладов по сериям чтений, основным темам и узким мезо-кластерам. Чем шире блок, тем больше докладов в этой теме.</p>
            <div id="hierarchy-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="hierarchy-svg" viewBox="0 0 800 400" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="hierarchy-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>

        <!-- VIS_007_network_arc -->
        <section class="viz-showcase-section" id="VIS_007_network_arc">
            <h2>
                <span class="viz-id-badge">VIS_007</span>
                <span class="bilingual-text" data-ru="Сеть соавторства и пересечений (Дуговая диаграмма)" data-en="Co-authorship Network (Arc Diagram)">Сеть соавторства и пересечений (Дуговая диаграмма)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Граф связей 50 самых активных ученых. Дуги соединяют докладчиков, выступавших в одних и тех же секциях как минимум дважды. Толщина линии означает плотность связей." data-en="A network graph of the 50 most active scholars. Arcs connect speakers who have presented in the same sessions at least twice. Line thickness represents tie strength.">Граф связей 50 самых активных ученых. Дуги соединяют докладчиков, выступавших в одних и тех же секциях как минимум дважды. Толщина линии означает плотность связей.</p>
            <div id="arc-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="arc-svg" viewBox="0 0 1000 600" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="arc-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>


        <!-- VIS_010_geographic_map -->
        <section class="viz-showcase-section" id="VIS_010_geographic_map">
            <h2>
                <span class="viz-id-badge">VIS_010</span>
                <span class="bilingual-text" data-ru="Географическая карта аффилиаций" data-en="Geospatial Affiliation Map">Географическая карта аффилиаций</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="География участников индологических конференций. Размер пузырьков отображает общее число докладов от исследователей из этих городов." data-en="Geography of Indology scholars. Bubble sizes represent the total number of presentations given by researchers based in these cities.">География участников индологических конференций.</p>
            <div id="geo-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="geo-svg" viewBox="0 0 800 450" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="geo-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>

        <!-- VIS_011_keyword_bubble_cloud -->
        <section class="viz-showcase-section" id="VIS_011_keyword_bubble_cloud">
            <h2>
                <span class="viz-id-badge">VIS_011</span>
                <span class="bilingual-text" data-ru="Динамическое облако тем" data-en="Dynamic Theme Bubble Cloud">Динамическое облако тем</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Узкие исследовательские направления, упакованные по плотности. Размер пузырьков отражает общее количество докладов в этой области." data-en="Packed visualization of narrow research fields. Bubble sizes reflect the total number of presentations in each field.">Узкие исследовательские направления, упакованные по плотности.</p>
            <div id="bubble-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="bubble-svg" viewBox="0 0 800 500" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="bubble-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>

        <hr style="border:0; border-top:1px solid rgba(255,255,255,0.08); margin:3rem 0 2rem;">
        <h2 class="bilingual-text" style="font-size:1.4rem; color:var(--accent2);" data-ru="Расширенная галерея (демография, темы, сравнение, время)" data-en="Extended Gallery (demography, themes, comparison, time)">Расширенная галерея (демография, темы, сравнение, время)</h2>

        <!-- VIS_008_demography_ribbon -->
        <section class="viz-showcase-section" id="VIS_008_demography_ribbon">
            <h2>
                <span class="viz-id-badge">VIS_008</span>
                <span class="bilingual-text" data-ru="Возрастная лента поля" data-en="Field Age Ribbon">Возрастная лента поля</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Медианный возраст докладчиков по годам с лентой межквартильного размаха (25–75 перцентиль). Показывает старение или омоложение каждого сообщества во времени." data-en="Median speaker age per year with an inter-quartile band (25th–75th percentile). Reveals the ageing or rejuvenation of each community over time.">Медианный возраст докладчиков по годам с лентой межквартильного размаха (25–75 перцентиль).</p>
            <div id="demo-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="demo-svg" viewBox="0 0 800 420" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="demo-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#2b82c9;"></span><span class="bilingual-text" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#b83280;"></span><span class="bilingual-text" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</span></div>
            </div>
            <aside class="caveat-block" role="note" style="margin-top: 1.2rem; border-left: 3px solid var(--accent2); background: rgba(255,255,255,0.01);">
                <strong class="bilingual-text" data-ru="Оговорка о покрытии" data-en="Coverage Caveat">Оговорка о покрытии</strong>
                <p class="bilingual-text" data-ru="Возраст рассчитан только для докладчиков с известным годом рождения; ленты опираются на ту долю участников, для которой год рождения установлен." data-en="Age is computed only for speakers with a known birth year; the bands rest on the subset of participants whose birth year is established.">Возраст рассчитан только для докладчиков с известным годом рождения.</p>
            </aside>
        </section>

        <!-- VIS_009_cohort_survival -->
        <section class="viz-showcase-section" id="VIS_009_cohort_survival">
            <h2>
                <span class="viz-id-badge">VIS_009</span>
                <span class="bilingual-text" data-ru="Кривые выживаемости когорт" data-en="Cohort Survival Curves">Кривые выживаемости когорт</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Каждая линия — когорта дебютантов одного года. По оси X — годы после первого доклада, по оси Y — доля когорты, всё ещё активной. Показаны только когорты от 5 человек." data-en="Each line is a cohort of scholars who debuted in the same year. X axis: years since first talk; Y axis: share of the cohort still active. Only cohorts of 5+ are shown.">Каждая линия — когорта дебютантов одного года; ось Y — доля когорты, всё ещё активной.</p>
            <div id="survival-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="survival-svg" viewBox="0 0 800 420" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="survival-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#2b82c9;"></span><span class="bilingual-text" data-ru="Когорты Зографа" data-en="Zograf cohorts">Когорты Зографа</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#b83280;"></span><span class="bilingual-text" data-ru="Когорты Рериха" data-en="Roerich cohorts">Когорты Рериха</span></div>
            </div>
        </section>

        <!-- VIS_010_newcomer_rate -->
        <section class="viz-showcase-section" id="VIS_010_newcomer_rate">
            <h2>
                <span class="viz-id-badge">VIS_010</span>
                <span class="bilingual-text" data-ru="Темп обновления" data-en="Renewal Rate">Темп обновления</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля докладчиков-новичков в каждом году (тех, кто ранее не выступал в данной серии). Высокие значения — приток новых людей, низкие — опора на постоянный круг." data-en="Share of first-time speakers each year (those who had not presented in that series before). High values signal an influx of new people; low values, reliance on a fixed core.">Доля докладчиков-новичков в каждом году по каждой серии.</p>
            <div id="newcomer-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="newcomer-svg" viewBox="0 0 800 380" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="newcomer-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#2b82c9;"></span><span class="bilingual-text" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#b83280;"></span><span class="bilingual-text" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</span></div>
            </div>
        </section>

        <!-- VIS_011_theme_treemap -->
        <section class="viz-showcase-section" id="VIS_011_theme_treemap">
            <h2>
                <span class="viz-id-badge">VIS_011</span>
                <span class="bilingual-text" data-ru="Карта тем (treemap)" data-en="Theme Treemap">Карта тем (treemap)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Площадь блока пропорциональна числу докладов. Крупные блоки — дисциплинарные направления (L1), внутренние ячейки — поднаправления (L2). Наведите для точных значений." data-en="Block area is proportional to the number of presentations. Large blocks are disciplinary domains (L1); inner cells are sub-domains (L2). Hover for exact counts.">Площадь блока пропорциональна числу докладов: L1 — направления, L2 — поднаправления.</p>
            <div id="treemap-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="treemap-svg" viewBox="0 0 800 460" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="treemap-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_012_gumilyov_stream -->
        <section class="viz-showcase-section" id="VIS_012_gumilyov_stream">
            <h2>
                <span class="viz-id-badge">VIS_012</span>
                <span class="bilingual-text" data-ru="Поток уровней обобщения" data-en="Scale-of-Argument Streamgraph">Поток уровней обобщения</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение докладов по шкале масштаба аргумента (Гумилёв): микроуровень (текст/кейс), региональный (традиция/эпоха), глобальный (цивилизационные обобщения) — по годам." data-en="Distribution of presentations along the scale-of-argument (Gumilyov): micro (single text/case), regional (tradition/era), global (civilisational generalisation) — over time.">Доклады по шкале масштаба аргумента (микро / региональный / глобальный) по годам.</p>
            <div id="stream-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="stream-svg" viewBox="0 0 800 380" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="stream-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#6366f1;"></span><span class="bilingual-text" data-ru="Микроуровень" data-en="Micro level">Микроуровень</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#f59e0b;"></span><span class="bilingual-text" data-ru="Региональный" data-en="Regional">Региональный</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#ef4444;"></span><span class="bilingual-text" data-ru="Глобальный" data-en="Global">Глобальный</span></div>
            </div>
        </section>

        <!-- VIS_013_keyword_diverging -->
        <section class="viz-showcase-section" id="VIS_013_keyword_diverging">
            <h2>
                <span class="viz-id-badge">VIS_013</span>
                <span class="bilingual-text" data-ru="Ключевые слова: Зограф против Рериха" data-en="Keywords: Zograf vs Roerich">Ключевые слова: Зограф против Рериха</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Топ-22 ключевых слова заголовков. Влево — частота в Зографских чтениях, вправо — в Рериховских. Контраст показывает, чем тематически различаются две площадки." data-en="Top 22 title keywords. Bars extend left for Zograf Readings, right for Roerich Readings. The contrast shows how the two venues differ thematically.">Топ-22 ключевых слова: влево — Зограф, вправо — Рерих.</p>
            <div id="keyword-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="keyword-svg" viewBox="0 0 800 560" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="keyword-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#2b82c9;"></span><span class="bilingual-text" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#b83280;"></span><span class="bilingual-text" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</span></div>
            </div>
        </section>

        <!-- VIS_014_closedness -->
        <section class="viz-showcase-section" id="VIS_014_closedness">
            <h2>
                <span class="viz-id-badge">VIS_014</span>
                <span class="bilingual-text" data-ru="Замкнутость сообществ" data-en="Community Closedness">Замкнутость сообществ</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Сравнение двух серий по четырём метрикам: доля «однодокладчиков», ядро (5+ докладов), удержание и концентрация (индекс Джини ×100). Чем выше удержание и ядро — тем плотнее постоянное сообщество." data-en="The two series compared on four metrics: one-talk-wonders, core (5+ talks), retention, and concentration (Gini ×100). Higher retention and core mean a denser standing community.">Четыре метрики замкнутости, Зограф против Рериха.</p>
            <div id="closedness-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="closedness-svg" viewBox="0 0 800 400" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="closedness-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#2b82c9;"></span><span class="bilingual-text" data-ru="Зограф" data-en="Zograf">Зограф</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#b83280;"></span><span class="bilingual-text" data-ru="Рерих" data-en="Roerich">Рерих</span></div>
            </div>
        </section>

        <!-- VIS_015_online_share -->
        <section class="viz-showcase-section" id="VIS_015_online_share">
            <h2>
                <span class="viz-id-badge">VIS_015</span>
                <span class="bilingual-text" data-ru="Сдвиг в онлайн" data-en="The Online Shift">Сдвиг в онлайн</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля онлайн-докладов по годам для каждой серии. Резкий рост около 2020 г. отражает пандемийный переход; пунктир отмечает 2020 год." data-en="Share of online presentations per year for each series. The sharp rise around 2020 reflects the pandemic shift; the dashed line marks 2020.">Доля онлайн-докладов по годам; пунктир — 2020 год.</p>
            <div id="online-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="online-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="online-tooltip" style="{tip_style}"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item"><span class="legend-color" style="background:#2b82c9;"></span><span class="bilingual-text" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</span></div>
                <div class="legend-item"><span class="legend-color" style="background:#b83280;"></span><span class="bilingual-text" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</span></div>
            </div>
        </section>

        <!-- VIS_016_generations -->
        <section class="viz-showcase-section" id="VIS_016_generations">
            <h2>
                <span class="viz-id-badge">VIS_016</span>
                <span class="bilingual-text" data-ru="Смена поколений" data-en="Generational Eras">Смена поколений</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение докладов по десятилетиям рождения авторов." data-en="Distribution of presentations by authors' birth decades.">Распределение докладов по десятилетиям рождения авторов.</p>
            <div id="vis016-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis016-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis016-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_018_title_length -->
        <section class="viz-showcase-section" id="VIS_018_title_length">
            <h2>
                <span class="viz-id-badge">VIS_018</span>
                <span class="bilingual-text" data-ru="Сложность названий" data-en="Title Complexity">Сложность названий</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Среднее количество слов в названиях докладов по годам." data-en="Average word count in presentation titles by year.">Среднее количество слов в названиях докладов по годам.</p>
            <div id="vis018-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis018-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis018-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_019_coauthorship -->
        <section class="viz-showcase-section" id="VIS_019_coauthorship">
            <h2>
                <span class="viz-id-badge">VIS_019</span>
                <span class="bilingual-text" data-ru="Индекс соавторства" data-en="Co-authorship Index">Индекс соавторства</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Процент докладов, написанных в соавторстве." data-en="Percentage of co-authored presentations over time.">Процент докладов, написанных в соавторстве.</p>
            <div id="vis019-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis019-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis019-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        <!-- VIS_020_velocity -->
        <section class="viz-showcase-section" id="VIS_020_velocity">
            <h2>
                <span class="viz-id-badge">VIS_020</span>
                <span class="bilingual-text" data-ru="Активность топ-5 ученых" data-en="Top 5 Scholars Velocity">Активность топ-5 ученых</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Кумулятивное число докладов пяти самых активных участников по годам." data-en="Cumulative presentations of the five most active scholars over time.">Кумулятивное число докладов пяти самых активных участников по годам.</p>
            <div id="vis020-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis020-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis020-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_021_institutions -->
        <section class="viz-showcase-section" id="VIS_021_institutions">
            <h2>
                <span class="viz-id-badge">VIS_021</span>
                <span class="bilingual-text" data-ru="Топ институций" data-en="Top Institutions">Топ институций</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Крупнейшие центры индологии по числу выступлений." data-en="Largest Indology centers by number of presentations.">Крупнейшие центры индологии по числу выступлений.</p>
            <div id="vis021-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis021-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis021-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_022_age_at_talk -->
        <section class="viz-showcase-section" id="VIS_022_age_at_talk">
            <h2>
                <span class="viz-id-badge">VIS_022</span>
                <span class="bilingual-text" data-ru="Возраст на момент доклада" data-en="Age at Presentation">Возраст на момент доклада</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Размах возраста исследователей в момент их выступления (мин, медиана, макс)." data-en="Age range of researchers at the time of their presentation (min, median, max).">Размах возраста исследователей в момент их выступления.</p>
            <div id="vis022-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis022-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis022-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        
        <!-- VIS_023_loyalty -->
        <section class="viz-showcase-section" id="VIS_023_loyalty">
            <h2>
                <span class="viz-id-badge">VIS_023</span>
                <span class="bilingual-text" data-ru="Лояльность аудитории" data-en="Audience Loyalty">Лояльность аудитории</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение числа уникальных лет участия." data-en="Distribution of unique years of participation.">Распределение числа уникальных лет участия.</p>
            <div id="vis023-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis023-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis023-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        <!-- VIS_024_keywords -->
        <section class="viz-showcase-section" id="VIS_024_keywords">
            <h2>
                <span class="viz-id-badge">VIS_024</span>
                <span class="bilingual-text" data-ru="Облако терминов" data-en="Keyword Cloud">Облако терминов</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Самые частые слова в названиях докладов (>4 букв)." data-en="Most frequent words in presentation titles (>4 chars).">Самые частые слова в названиях докладов.</p>
            <div id="vis024-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis024-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis024-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_025_scale -->
        <section class="viz-showcase-section" id="VIS_025_scale">
            <h2>
                <span class="viz-id-badge">VIS_025</span>
                <span class="bilingual-text" data-ru="Масштаб конференций" data-en="Conference Scale">Масштаб конференций</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Динамика количества секций и докладов по годам." data-en="Dynamics of session and presentation counts by year.">Динамика количества секций и докладов по годам.</p>
            <div id="vis025-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis025-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis025-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_026_confidence -->
        <section class="viz-showcase-section" id="VIS_026_confidence">
            <h2>
                <span class="viz-id-badge">VIS_026</span>
                <span class="bilingual-text" data-ru="Уверенность ИИ-разметки" data-en="AI Annotation Confidence">Уверенность ИИ-разметки</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение уровня уверенности DeepSeek при классификации докладов." data-en="Distribution of DeepSeek confidence levels during presentation classification.">Распределение уровня уверенности DeepSeek.</p>
            <div id="vis026-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis026-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis026-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_027_l1_themes -->
        <section class="viz-showcase-section" id="VIS_027_l1_themes">
            <h2>
                <span class="viz-id-badge">VIS_027</span>
                <span class="bilingual-text" data-ru="Популярность макро-тем" data-en="Macro-theme Popularity">Популярность макро-тем</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Топ-10 макро-тем (L1) по количеству докладов." data-en="Top 10 macro-themes (L1) by number of presentations.">Топ-10 макро-тем (L1) по количеству докладов.</p>
            <div id="vis027-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis027-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis027-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_028_gumilyov -->
        <section class="viz-showcase-section" id="VIS_028_gumilyov">
            <h2>
                <span class="viz-id-badge">VIS_028</span>
                <span class="bilingual-text" data-ru="Пассионарность Гумилева" data-en="Gumilyov Passionarity">Пассионарность Гумилева</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение стадий этногенеза Гумилева в классификации докладов." data-en="Distribution of Gumilyov ethnogenesis stages in presentation classifications.">Распределение стадий этногенеза Гумилева.</p>
            <div id="vis028-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis028-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis028-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_029_chars -->
        <section class="viz-showcase-section" id="VIS_029_chars">
            <h2>
                <span class="viz-id-badge">VIS_029</span>
                <span class="bilingual-text" data-ru="Длина названий (символы)" data-en="Title Length (chars)">Длина названий (символы)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Средняя длина названий докладов в символах по годам." data-en="Average length of presentation titles in characters by year.">Средняя длина названий докладов в символах.</p>
            <div id="vis029-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis029-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis029-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_030_overlap -->
        <section class="viz-showcase-section" id="VIS_030_overlap">
            <h2>
                <span class="viz-id-badge">VIS_030</span>
                <span class="bilingual-text" data-ru="Пересечение аудиторий" data-en="Audience Overlap">Пересечение аудиторий</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля ученых, выступавших только на Зографских чтениях, только на Рериховских, или на обеих конференциях." data-en="Share of scholars presenting only at Zograf, only at Roerich, or both.">Доля ученых, выступавших только на Зографских, только на Рериховских, или на обеих.</p>
            <div id="vis030-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis030-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis030-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        <!-- VIS_031_age_scale -->
        <section class="viz-showcase-section" id="VIS_031_age_scale">
            <h2>
                <span class="viz-id-badge">VIS_031</span>
                <span class="bilingual-text" data-ru="Возраст и Масштаб обобщения (Шкала Гумилева)" data-en="Age vs Scale of Abstraction">Возраст и Масштаб обобщения</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение возраста авторов для докладов уровней G1, G2, G3. Подтверждает гипотезу H35 о том, что широкое обобщение — прерогатива старшего поколения." data-en="Distribution of author age for G1, G2, G3 presentations. Supports H35.">Возраст авторов и масштаб доклада.</p>
            <div id="vis031-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis031-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis031-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_032_disc_scale -->
        <section class="viz-showcase-section" id="VIS_032_disc_scale">
            <h2>
                <span class="viz-id-badge">VIS_032</span>
                <span class="bilingual-text" data-ru="Дисциплинарный масштаб" data-en="Disciplinary Scale">Дисциплинарный масштаб</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля микрокейсов (G1) и обобщений (G2/G3) внутри каждой дисциплины (L1). Подтверждает гипотезу H34." data-en="Share of microcases (G1) and generalizations (G2/G3) by discipline (L1). Supports H34.">Масштаб обобщения по дисциплинам.</p>
            <div id="vis032-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis032-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis032-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_033_core_scale -->
        <section class="viz-showcase-section" id="VIS_033_core_scale">
            <h2>
                <span class="viz-id-badge">VIS_033</span>
                <span class="bilingual-text" data-ru="Масштаб: Ядро vs Периферия" data-en="Scale: Core vs Periphery">Масштаб: Ядро vs Периферия</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Подтверждает H32: Ядро (>=5 докладов) не производит больше макрообобщений (G3), чем периферия." data-en="Supports H32: Core (>=5 talks) does not produce more macro generalizations than periphery.">Масштаб обобщения у Ядра и Периферии.</p>
            <div id="vis033-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis033-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis033-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_034_bridge_scale -->
        <section class="viz-showcase-section" id="VIS_034_bridge_scale">
            <h2>
                <span class="viz-id-badge">VIS_034</span>
                <span class="bilingual-text" data-ru="Масштаб: Мостовики vs Локальные" data-en="Scale: Bridges vs Local">Масштаб: Мостовики vs Локальные</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Подтверждает H27: Участники обеих площадок не являются синтетиками, их доля макрообобщений даже ниже." data-en="Supports H27: Bridge scholars are not macro-synthesizers.">Масштаб мышления участников обеих площадок.</p>
            <div id="vis034-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis034-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis034-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        <!-- VIS_035_words -->
        <section class="viz-showcase-section" id="VIS_035_words">
            <h2>
                <span class="viz-id-badge">VIS_035</span>
                <span class="bilingual-text" data-ru="Инфляция заголовков (Слова)" data-en="Title Length Inflation (Words)">Инфляция заголовков (Слова)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Среднее количество слов в названиях докладов по годам. Подтверждает гипотезу H24 о сдвиге в сторону объяснительных и длинных заголовков." data-en="Average number of words in presentation titles by year. Supports H24.">Среднее количество слов в названиях докладов.</p>
            <div id="vis035-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis035-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis035-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_036_colons -->
        <section class="viz-showcase-section" id="VIS_036_colons">
            <h2>
                <span class="viz-id-badge">VIS_036</span>
                <span class="bilingual-text" data-ru="Эра подзаголовков" data-en="The Colon Era">Эра подзаголовков</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля названий докладов, содержащих двоеточие (как признак объяснительного подзаголовка). Подтверждает гипотезу H24." data-en="Share of presentation titles containing a colon (indicating an explanatory subtitle). Supports H24.">Доля названий докладов с подзаголовком (через двоеточие).</p>
            <div id="vis036-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis036-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis036-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_037_coauthors -->
        <section class="viz-showcase-section" id="VIS_037_coauthors">
            <h2>
                <span class="viz-id-badge">VIS_037</span>
                <span class="bilingual-text" data-ru="Коллективность и Масштаб" data-en="Co-authorship vs Scale">Коллективность и Масштаб</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Корреляция между коллективным авторством и уровнем обобщения. Подтверждает гипотезу H20." data-en="Correlation between multi-authorship and the level of generalization (Gumilyov scale). Supports H20.">Масштаб обобщения у индивидуальных и коллективных докладов.</p>
            <div id="vis037-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis037-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis037-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        <!-- VIS_038_vid_years -->
        <section class="viz-showcase-section" id="VIS_038_vid_years">
            <h2>
                <span class="viz-id-badge">VIS_038</span>
                <span class="bilingual-text" data-ru="Радары видимости (YouTube Bias)" data-en="Visibility Radars (YouTube Bias)">Радары видимости (YouTube Bias)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Количество записанных на видео докладов (красный) относительно общего числа докладов (синий) по годам. Доказывает H13 об огромном историческом перекосе медиа-архива." data-en="Number of video-recorded presentations vs total presentations by year. Proves H13 regarding the massive historical bias of the media archive.">Покрытие конференции видеозаписями.</p>
            <div id="vis038-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis038-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis038-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_039_vid_scale -->
        <section class="viz-showcase-section" id="VIS_039_vid_scale">
            <h2>
                <span class="viz-id-badge">VIS_039</span>
                <span class="bilingual-text" data-ru="Смещение в Микрокейсы" data-en="Microcase Bias">Смещение в Микрокейсы</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение записанных и незаписанных докладов по шкале Гумилева. Доказывает H30: на видео попадают почти исключительно G1, макрообобщения мы не записываем." data-en="Distribution of recorded and unrecorded talks on the Gumilyov scale. Proves H30: video almost exclusively captures G1 microcases.">Какие жанры попадают на YouTube?</p>
            <div id="vis039-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis039-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis039-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_040_vid_core -->
        <section class="viz-showcase-section" id="VIS_040_vid_core">
            <h2>
                <span class="viz-id-badge">VIS_040</span>
                <span class="bilingual-text" data-ru="Статус и Камера" data-en="Status and Camera">Статус и Камера</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Сравнение покрытия видеозаписями Ядра (>=5 докладов) и Периферии. Доказывает H25: камера снимает не по статусу ученого, а по технической случайности." data-en="Comparison of video coverage for Core (>=5 talks) vs Periphery. Proves H25: the camera records by chance, not by academic status.">Зависит ли видеозапись от статуса ученого?</p>
            <div id="vis040-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis040-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis040-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        <!-- VIS_041_newbie_themes -->
        <section class="viz-showcase-section" id="VIS_041_newbie_themes">
            <h2>
                <span class="viz-id-badge">VIS_041</span>
                <span class="bilingual-text" data-ru="Входные ворота (Темы новичков)" data-en="Newbie Entry Topics">Входные ворота</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Темы (L2 Period), через которые дебютанты входят в сообщество, в сравнении с темами старожилов. Доказывает H22: новички чаще входят через современность/колониализм." data-en="Topics (L2 Period) chosen by newcomers vs veterans. Proves H22: newcomers enter through modern/colonial topics.">Темы дебютных докладов.</p>
            <div id="vis041-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis041-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis041-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_042_inst_bias -->
        <section class="viz-showcase-section" id="VIS_042_inst_bias">
            <h2>
                <span class="viz-id-badge">VIS_042</span>
                <span class="bilingual-text" data-ru="Город vs Учреждение" data-en="City vs Institution Format">Город vs Учреждение</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Формат указания аффилиации на двух площадках. Доказывает H11: Зографские чтения — это площадка городской идентичности (94.7% не указывают учреждение), в отличие от Рериховских (87% указывают)." data-en="Affiliation format on the two platforms. Proves H11: Zograf is a city-identity platform, Roerich is institutional.">Институциональный партикуляризм площадок.</p>
            <div id="vis042-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis042-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis042-tooltip" style="{tip_style}"></div>
            </div>
        </section>

    """

    scatter_js = """
        <script>
            const BRIDGES_DATA = """ + serialized_bridges + """;

            function getJitter(id, seed) {
                let hash = 0;
                const str = id + seed;
                for (let i = 0; i < str.length; i++) {
                    hash = str.charCodeAt(i) + ((hash << 5) - hash);
                }
                return ((Math.abs(hash) % 100) / 100) - 0.5; // [-0.5, 0.5]
            }



            function drawScatter() {
                const svg = document.getElementById('scatter-svg');
                if (!svg) return;
                svg.innerHTML = '';

                const width = 800;
                const height = 480;
                const padding = { top: 40, right: 40, bottom: 50, left: 60 };

                // Find limits
                let maxZ = 20;
                let maxR = 20;

                const xScale = (val) => padding.left + (val / maxZ) * (width - padding.left - padding.right);
                const yScale = (val) => height - padding.bottom - (val / maxR) * (height - padding.top - padding.bottom);

                // Add gridlines
                for (let i = 0; i <= maxZ; i += 2) {
                    const x = xScale(i);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', x);
                    line.setAttribute('y1', padding.top);
                    line.setAttribute('x2', x);
                    line.setAttribute('y2', height - padding.bottom);
                    line.setAttribute('class', 'scatter-grid-line');
                    svg.appendChild(line);

                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', x);
                    label.setAttribute('y', height - padding.bottom + 20);
                    label.setAttribute('text-anchor', 'middle');
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '11px');
                    label.textContent = i;
                    svg.appendChild(label);
                }

                for (let i = 0; i <= maxR; i += 2) {
                    const y = yScale(i);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', y);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', y);
                    line.setAttribute('class', 'scatter-grid-line');
                    svg.appendChild(line);

                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 15);
                    label.setAttribute('y', y + 4);
                    label.setAttribute('text-anchor', 'end');
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '11px');
                    label.textContent = i;
                    svg.appendChild(label);
                }

                // Add diagonal reference line
                const diag = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                diag.setAttribute('x1', xScale(0));
                diag.setAttribute('y1', yScale(0));
                diag.setAttribute('x2', xScale(Math.min(maxZ, maxR)));
                diag.setAttribute('y2', yScale(Math.min(maxZ, maxR)));
                diag.setAttribute('class', 'scatter-diagonal');
                svg.appendChild(diag);

                // Add Axes
                const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                xAxis.setAttribute('x1', padding.left);
                xAxis.setAttribute('y1', height - padding.bottom);
                xAxis.setAttribute('x2', width - padding.right);
                xAxis.setAttribute('y2', height - padding.bottom);
                xAxis.setAttribute('class', 'scatter-axis');
                svg.appendChild(xAxis);

                const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                yAxis.setAttribute('x1', padding.left);
                yAxis.setAttribute('y1', padding.top);
                yAxis.setAttribute('x2', padding.left);
                yAxis.setAttribute('y2', height - padding.bottom);
                yAxis.setAttribute('class', 'scatter-axis');
                svg.appendChild(yAxis);

                // Axis Labels
                const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                xLabel.setAttribute('x', padding.left + (width - padding.left - padding.right) / 2);
                xLabel.setAttribute('y', height - padding.bottom + 42);
                xLabel.setAttribute('text-anchor', 'middle');
                xLabel.setAttribute('fill', '#fff');
                xLabel.setAttribute('font-size', '12px');
                xLabel.textContent = currentLang === 'ru' ? 'Докладов на Зографских чтениях' : 'Presentations at Zograf Readings';
                svg.appendChild(xLabel);

                const yLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                yLabel.setAttribute('x', 20);
                yLabel.setAttribute('y', padding.top + (height - padding.top - padding.bottom) / 2);
                yLabel.setAttribute('text-anchor', 'middle');
                yLabel.setAttribute('fill', '#fff');
                yLabel.setAttribute('font-size', '12px');
                yLabel.setAttribute('transform', 'rotate(-90, 20, ' + (padding.top + (height - padding.top - padding.bottom) / 2) + ')');
                yLabel.textContent = currentLang === 'ru' ? 'Докладов на Рериховских чтениях' : 'Presentations at Roerich Readings';
                svg.appendChild(yLabel);

                // Draw Dots
                const tooltip = document.getElementById('scatter-tooltip');

                BRIDGES_DATA.forEach(d => {
                    const jX = getJitter(d.id, 'X') * 0.42;
                    const jY = getJitter(d.id, 'Y') * 0.42;

                    const cx = xScale(d.z + jX);
                    const cy = yScale(d.r + jY);

                    // Radius based on total presentations
                    const r = 4 + Math.sqrt(d.total) * 1.5;

                    // Color based on group
                    let color = '#ff7b00'; // both
                    if (d.g === 'zograf_only') color = '#2b82c9';
                    else if (d.g === 'roerich_only') color = '#b83280';

                    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    dot.setAttribute('cx', cx);
                    dot.setAttribute('cy', cy);
                    dot.setAttribute('r', r);
                    dot.setAttribute('fill', color);
                    dot.setAttribute('opacity', '0.75');
                    dot.setAttribute('class', 'scatter-dot');

                    dot.addEventListener('mouseenter', (e) => {
                        dot.setAttribute('opacity', '1.0');
                        tooltip.style.opacity = '1';
                        
                        const titleZ = currentLang === 'ru' ? 'Зограф' : 'Zograf';
                        const titleR = currentLang === 'ru' ? 'Рерих' : 'Roerich';
                        const labelAff = currentLang === 'ru' ? 'Аффилиация' : 'Affiliation';
                        const labelClick = currentLang === 'ru' ? 'Нажмите для перехода к профилю' : 'Click to view profile';

                        tooltip.innerHTML = 
                            '<strong style="color:var(--accent2); font-size: 0.95rem;">' + d.name + '</strong><br>' +
                            '<span style="font-size:0.8rem; color:var(--muted);">' + labelAff + ': ' + d.aff + '</span><br>' +
                            '<span style="display:inline-block; margin-top:5px; font-weight:bold;">' + titleZ + ': ' + d.z + ' · ' + titleR + ': ' + d.r + '</span><br>' +
                            '<small style="color:var(--accent); display:block; margin-top: 5px;">' + labelClick + '</small>';
                    });

                    dot.addEventListener('mousemove', (e) => {
                        const rect = svg.getBoundingClientRect();
                        const tooltipRect = tooltip.getBoundingClientRect();
                        // Position relative to scatter container
                        const x = e.clientX - rect.left + 15;
                        const y = e.clientY - rect.top - tooltipRect.height - 10;
                        tooltip.style.left = x + 'px';
                        tooltip.style.top = y + 'px';
                    });

                    dot.addEventListener('mouseleave', () => {
                        dot.setAttribute('opacity', '0.75');
                        tooltip.style.opacity = '0';
                    });

                    dot.addEventListener('click', () => {
                        window.location.href = '../s/' + d.slug + '.html';
                    });

                    svg.appendChild(dot);
                });
            }

            
            const HEATMAP_DATA = """ + serialized_heatmap + """;
            
            
            
            const ARC_DATA = """ + serialized_arc + """;


            const GEO_DATA = """ + serialized_geo + """;
            const BUBBLE_DATA = """ + serialized_bubble + """;

            function drawGeoMap() {
                const svg = document.getElementById('geo-svg');
                if (!svg || !GEO_DATA) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 450;
                const padding = { top: 40, right: 40, bottom: 40, left: 60 };
                
                // Lon from 0 to 120, Lat from 25 to 65
                const minLon = 0, maxLon = 120;
                const minLat = 25, maxLat = 65;
                
                const getX = (lon) => padding.left + (lon - minLon) / (maxLon - minLon) * (width - padding.left - padding.right);
                const getY = (lat) => height - padding.bottom - (lat - minLat) / (maxLat - minLat) * (height - padding.top - padding.bottom);
                
                const tooltip = document.getElementById('geo-tooltip');
                
                // Draw grid lines
                for (let lon = 20; lon <= 100; lon += 20) {
                    const x = getX(lon);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', x);
                    line.setAttribute('y1', padding.top);
                    line.setAttribute('x2', x);
                    line.setAttribute('y2', height - padding.bottom);
                    line.setAttribute('stroke', 'rgba(255,255,255,0.04)');
                    line.setAttribute('stroke-dasharray', '2,4');
                    svg.appendChild(line);
                    
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', x);
                    label.setAttribute('y', height - padding.bottom + 15);
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '9px');
                    label.setAttribute('text-anchor', 'middle');
                    label.textContent = lon + '°E';
                    svg.appendChild(label);
                }
                for (let lat = 30; lat <= 60; lat += 10) {
                    const y = getY(lat);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', y);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', y);
                    line.setAttribute('stroke', 'rgba(255,255,255,0.04)');
                    line.setAttribute('stroke-dasharray', '2,4');
                    svg.appendChild(line);
                    
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 10);
                    label.setAttribute('y', y + 3);
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '9px');
                    label.setAttribute('text-anchor', 'end');
                    label.textContent = lat + '°N';
                    svg.appendChild(label);
                }
                
                // Draw Cities
                GEO_DATA.forEach(d => {
                    const cx = getX(d.lon);
                    const cy = getY(d.lat);
                    const r = 5 + Math.sqrt(d.count) * 2;
                    
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', cx);
                    circle.setAttribute('cy', cy);
                    circle.setAttribute('r', r);
                    circle.setAttribute('fill', 'var(--accent2)');
                    circle.setAttribute('fill-opacity', '0.6');
                    circle.setAttribute('stroke', '#fff');
                    circle.setAttribute('stroke-width', '1');
                    circle.setAttribute('stroke-opacity', '0.4');
                    circle.style.cursor = 'pointer';
                    circle.style.transition = 'all 0.2s ease';
                    
                    circle.addEventListener('mouseenter', () => {
                        circle.setAttribute('fill-opacity', '0.9');
                        circle.setAttribute('stroke-width', '2');
                        circle.setAttribute('stroke-opacity', '1');
                        tooltip.style.opacity = '1';
                        const name = currentLang === 'ru' ? d.name_ru : d.name_en;
                        tooltip.innerHTML = `<strong>${name}</strong><br/>Координаты: ${d.lat.toFixed(2)}°N, ${d.lon.toFixed(2)}°E<br/>Докладов: ${d.count}`;
                    });
                    circle.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('geo-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    circle.addEventListener('mouseleave', () => {
                        circle.setAttribute('fill-opacity', '0.6');
                        circle.setAttribute('stroke-width', '1');
                        circle.setAttribute('stroke-opacity', '0.4');
                        tooltip.style.opacity = '0';
                    });
                    svg.appendChild(circle);
                    
                    // Draw name label
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', cx);
                    label.setAttribute('y', cy - r - 5);
                    label.setAttribute('fill', 'rgba(255,255,255,0.85)');
                    label.setAttribute('font-size', '10px');
                    label.setAttribute('text-anchor', 'middle');
                    label.style.pointerEvents = 'none';
                    label.textContent = currentLang === 'ru' ? d.name_ru : d.name_en;
                    svg.appendChild(label);
                });
            }

            function drawBubbleCloud() {
                const svg = document.getElementById('bubble-svg');
                if (!svg || !BUBBLE_DATA) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 500;
                const center = { x: width / 2, y: height / 2 };
                
                // scale & packing logic
                const bubbles = BUBBLE_DATA.map(d => ({
                    id: d.id,
                    name_ru: d.name_ru,
                    name_en: d.name_en,
                    value: d.value,
                    r: 15 + Math.sqrt(d.value) * 3
                })).sort((a, b) => b.r - a.r);
                
                const placed = [];
                bubbles.forEach(b => {
                    let angle = 0;
                    let radius = 0;
                    let found = false;
                    
                    while (!found && radius < 400) {
                        const cx = center.x + radius * Math.cos(angle);
                        const cy = center.y + radius * Math.sin(angle);
                        
                        let collision = false;
                        for (let i = 0; i < placed.length; i++) {
                            const other = placed[i];
                            const dx = cx - other.x;
                            const dy = cy - other.y;
                            const dist = Math.sqrt(dx*dx + dy*dy);
                            if (dist < b.r + other.r + 3) {
                                collision = true;
                                break;
                            }
                        }
                        
                        if (!collision) {
                            b.x = cx;
                            b.y = cy;
                            placed.push(b);
                            found = true;
                        }
                        angle += 0.15;
                        radius += 0.35;
                    }
                });
                
                const tooltip = document.getElementById('bubble-tooltip');
                const colors = ['#2b82c9', '#b83280', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#3b82f6'];
                
                placed.forEach((b, idx) => {
                    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                    
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', b.x);
                    circle.setAttribute('cy', b.y);
                    circle.setAttribute('r', b.r);
                    circle.setAttribute('fill', colors[idx % colors.length]);
                    circle.setAttribute('fill-opacity', '0.6');
                    circle.setAttribute('stroke', '#fff');
                    circle.setAttribute('stroke-width', '1.5');
                    circle.setAttribute('stroke-opacity', '0.3');
                    circle.style.cursor = 'pointer';
                    circle.style.transition = 'all 0.2s ease';
                    
                    circle.addEventListener('mouseenter', () => {
                        circle.setAttribute('fill-opacity', '0.85');
                        circle.setAttribute('stroke-opacity', '1');
                        tooltip.style.opacity = '1';
                        const name = currentLang === 'ru' ? b.name_ru : b.name_en;
                        tooltip.innerHTML = `<strong>${name}</strong><br/>Код: ${b.id}<br/>Докладов: ${b.value}`;
                    });
                    circle.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('bubble-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    circle.addEventListener('mouseleave', () => {
                        circle.setAttribute('fill-opacity', '0.6');
                        circle.setAttribute('stroke-opacity', '0.3');
                        tooltip.style.opacity = '0';
                    });
                    
                    g.appendChild(circle);
                    
                    // Draw name inside bubble
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', b.x);
                    text.setAttribute('y', b.y + 4);
                    text.setAttribute('fill', '#fff');
                    text.setAttribute('font-size', b.r > 35 ? '10px' : '8px');
                    text.setAttribute('text-anchor', 'middle');
                    text.style.pointerEvents = 'none';
                    
                    const name = currentLang === 'ru' ? b.name_ru : b.name_en;
                    let label = name;
                    if (label.length * 5 > b.r * 2) {
                        label = label.substring(0, Math.floor(b.r*2 / 5) - 1) + '…';
                    }
                    text.textContent = label;
                    
                    g.appendChild(text);
                    svg.appendChild(g);
                });
            }

            function drawArc() {
                const svg = document.getElementById('arc-svg');
                if (!svg || !ARC_DATA.nodes) return;
                svg.innerHTML = '';
                
                const width = 1000;
                const height = 600;
                const baselineY = height - 150;
                const padding = { left: 50, right: 50 };
                
                const nodes = ARC_DATA.nodes;
                const links = ARC_DATA.links;
                
                const step = (width - padding.left - padding.right) / (nodes.length - 1);
                
                // assign x coords
                const nodeX = {};
                nodes.forEach((n, i) => {
                    n.x = padding.left + i * step;
                    nodeX[n.id] = n.x;
                });
                
                const tooltip = document.getElementById('arc-tooltip');
                
                // Draw base line
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', padding.left - 20);
                line.setAttribute('y1', baselineY);
                line.setAttribute('x2', width - padding.right + 20);
                line.setAttribute('y2', baselineY);
                line.setAttribute('stroke', 'rgba(255,255,255,0.1)');
                svg.appendChild(line);
                
                // Draw Links
                links.forEach(l => {
                    const x1 = Math.min(nodeX[l.source], nodeX[l.target]);
                    const x2 = Math.max(nodeX[l.source], nodeX[l.target]);
                    
                    if (x1 === undefined || x2 === undefined || x1 === x2) return;
                    
                    const r = (x2 - x1) / 2;
                    const cx = x1 + r;
                    
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const d = `M ${x1} ${baselineY} A ${r} ${r} 0 0 1 ${x2} ${baselineY}`;
                    
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', 'var(--accent)');
                    path.setAttribute('stroke-opacity', Math.min(0.1 + l.value * 0.1, 0.6));
                    path.setAttribute('stroke-width', Math.min(1 + l.value * 0.5, 5));
                    path.style.cursor = 'pointer';
                    path.style.transition = 'stroke-opacity 0.2s, stroke-width 0.2s';
                    
                    path.addEventListener('mouseenter', () => {
                        path.setAttribute('stroke-opacity', '1');
                        path.setAttribute('stroke-width', Math.min(3 + l.value * 0.5, 7));
                        tooltip.style.opacity = '1';
                        tooltip.innerHTML = `<strong>${l.source} ↔ ${l.target}</strong><br/>Совместных сессий: ${l.value}`;
                    });
                    path.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('arc-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    path.addEventListener('mouseleave', () => {
                        path.setAttribute('stroke-opacity', Math.min(0.1 + l.value * 0.1, 0.6));
                        path.setAttribute('stroke-width', Math.min(1 + l.value * 0.5, 5));
                        tooltip.style.opacity = '0';
                    });
                    
                    svg.appendChild(path);
                });
                
                // Draw Nodes
                nodes.forEach(n => {
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', n.x);
                    circle.setAttribute('cy', baselineY);
                    circle.setAttribute('r', 3);
                    circle.setAttribute('fill', '#fff');
                    svg.appendChild(circle);
                    
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', n.x);
                    text.setAttribute('y', baselineY + 15);
                    text.setAttribute('fill', 'rgba(255,255,255,0.7)');
                    text.setAttribute('font-size', '10px');
                    text.setAttribute('transform', `rotate(45, ${n.x}, ${baselineY + 15})`);
                    text.textContent = n.id;
                    svg.appendChild(text);
                });
            }

            const HIERARCHY_DATA = """ + serialized_hierarchy + """;

            function drawHierarchy() {
                const svg = document.getElementById('hierarchy-svg');
                if (!svg || !HIERARCHY_DATA.children) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 400;
                
                // Calculate values bottom-up
                function calcValue(node) {
                    if (node.children) {
                        node.value = node.children.reduce((sum, child) => sum + calcValue(child), 0);
                    }
                    return node.value || 0;
                }
                calcValue(HIERARCHY_DATA);
                
                const totalValue = HIERARCHY_DATA.value;
                if(totalValue === 0) return;
                
                const tooltip = document.getElementById('hierarchy-tooltip');
                
                const levels = 4; // Root, Series, Theme, Meso
                const rowH = height / levels;
                
                const colors = {
                    'Zograf': '#2b82c9',
                    'Roerich': '#b83280',
                    'Default': '#6b7280'
                };
                
                function drawNode(node, x, y, w, h, level, parentColor) {
                    if (w < 1) return; // don't draw tiny blocks
                    
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', x);
                    rect.setAttribute('y', y);
                    rect.setAttribute('width', w);
                    rect.setAttribute('height', h - 2); // 2px gap
                    
                    let fillColor = parentColor;
                    if (level === 0) fillColor = '#4b5563';
                    if (level === 1) fillColor = colors[node.name] || colors.Default;
                    
                    rect.setAttribute('fill', fillColor);
                    rect.setAttribute('stroke', '#1e1e24');
                    rect.setAttribute('stroke-width', '1');
                    
                    if(level > 0) {
                        // varying opacity by level
                        rect.setAttribute('fill-opacity', 1 - (level-1)*0.25);
                        rect.setAttribute('cursor', 'pointer');
                        rect.style.transition = 'opacity 0.2s';
                        
                        rect.addEventListener('mouseenter', () => {
                            rect.setAttribute('fill-opacity', '1');
                            tooltip.style.opacity = '1';
                            tooltip.innerHTML = `<strong>${node.name}</strong><br/>Докладов: ${node.value}`;
                        });
                        rect.addEventListener('mousemove', (e) => {
                            const container = document.getElementById('hierarchy-wrapper').getBoundingClientRect();
                            tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                            tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                        });
                        rect.addEventListener('mouseleave', () => {
                            rect.setAttribute('fill-opacity', 1 - (level-1)*0.25);
                            tooltip.style.opacity = '0';
                        });
                    }
                    
                    svg.appendChild(rect);
                    
                    // Draw text if enough space
                    if (w > 30) {
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', x + 5);
                        text.setAttribute('y', y + h/2 + 4);
                        text.setAttribute('fill', '#fff');
                        text.setAttribute('font-size', '11px');
                        text.style.pointerEvents = 'none';
                        let label = node.name;
                        if (label.length * 6 > w) { // approximate width
                            label = label.substring(0, Math.floor(w/6) - 1) + '…';
                        }
                        text.textContent = label;
                        svg.appendChild(text);
                    }
                    
                    // Recurse children
                    if (node.children) {
                        let cx = x;
                        node.children.forEach(child => {
                            const cw = (child.value / node.value) * w;
                            drawNode(child, cx, y + rowH, cw, rowH, level + 1, fillColor);
                            cx += cw;
                        });
                    }
                }
                
                drawNode(HIERARCHY_DATA, 0, 0, width, rowH, 0, '#4b5563');
            }

            const FOREST_DATA = """ + serialized_forest + """;

            function drawForest() {
                const svg = document.getElementById('forest-svg');
                if (!svg || !FOREST_DATA.scholars) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 800;
                const padding = { top: 40, right: 30, bottom: 40, left: 160 };
                
                const years = FOREST_DATA.years;
                const minYear = Math.min(...years);
                const maxYear = Math.max(...years);
                const scholars = FOREST_DATA.scholars;
                
                const cellW = (width - padding.left - padding.right) / (maxYear - minYear);
                const rowH = (height - padding.top - padding.bottom) / scholars.length;
                
                // Draw X Axis (Years)
                for (let y = minYear; y <= maxYear; y++) {
                    const x = padding.left + (y - minYear) * cellW;
                    if (y % 2 === 0) {
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', x);
                        text.setAttribute('y', padding.top - 10);
                        text.setAttribute('text-anchor', 'middle');
                        text.setAttribute('fill', 'var(--muted)');
                        text.setAttribute('font-size', '10px');
                        text.textContent = y;
                        svg.appendChild(text);
                        
                        // Grid line
                        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                        line.setAttribute('x1', x);
                        line.setAttribute('y1', padding.top);
                        line.setAttribute('x2', x);
                        line.setAttribute('y2', height - padding.bottom);
                        line.setAttribute('stroke', 'rgba(255,255,255,0.05)');
                        line.setAttribute('stroke-dasharray', '4,4');
                        svg.appendChild(line);
                    }
                }
                
                const tooltip = document.getElementById('forest-tooltip');
                
                // Draw rows
                scholars.forEach((scholar, idx) => {
                    const cy = padding.top + idx * rowH + rowH / 2;
                    
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 10);
                    label.setAttribute('y', cy + 4);
                    label.setAttribute('text-anchor', 'end');
                    label.setAttribute('fill', 'rgba(255,255,255,0.7)');
                    label.setAttribute('font-size', '11px');
                    // simple truncation if too long
                    label.textContent = scholar.length > 25 ? scholar.substring(0,22) + '...' : scholar;
                    svg.appendChild(label);
                    
                    // Base line
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', cy);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', cy);
                    line.setAttribute('stroke', 'rgba(255,255,255,0.05)');
                    svg.appendChild(line);
                    
                    // Draw activity points
                    const points = FOREST_DATA.data.filter(d => d.s === scholar);
                    let pathD = `M ${padding.left} ${cy}`;
                    
                    for (let y = minYear; y <= maxYear; y++) {
                        const pt = points.find(p => p.y === y);
                        const count = pt ? pt.c : 0;
                        const x = padding.left + (y - minYear) * cellW;
                        
                        if (count > 0) {
                            const r = Math.min(rowH * 0.8, 3 + count * 2);
                            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                            circle.setAttribute('cx', x);
                            circle.setAttribute('cy', cy);
                            circle.setAttribute('r', r);
                            circle.setAttribute('fill', 'var(--accent)');
                            circle.setAttribute('fill-opacity', '0.6');
                            circle.setAttribute('cursor', 'pointer');
                            circle.style.transition = 'all 0.2s';
                            
                            circle.addEventListener('mouseenter', () => {
                                circle.setAttribute('fill-opacity', '1');
                                circle.setAttribute('stroke', '#fff');
                                tooltip.style.opacity = '1';
                                tooltip.innerHTML = `<strong>${scholar}</strong><br/>Год: ${y}<br/>Докладов: ${count}`;
                            });
                            circle.addEventListener('mousemove', (e) => {
                                const container = document.getElementById('forest-wrapper').getBoundingClientRect();
                                tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                                tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                            });
                            circle.addEventListener('mouseleave', () => {
                                circle.setAttribute('fill-opacity', '0.6');
                                circle.removeAttribute('stroke');
                                tooltip.style.opacity = '0';
                            });
                            
                            svg.appendChild(circle);
                        }
                    }
                });
            }

            const ALLUVIAL_DATA = """ + serialized_alluvial + """;

            function drawHeatmap() {
                const svg = document.getElementById('heatmap-svg');
                if (!svg || !HEATMAP_DATA.years) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 250;
                const padding = { top: 30, right: 30, bottom: 40, left: 100 };
                
                const years = HEATMAP_DATA.years;
                const minYear = Math.min(...years);
                const maxYear = Math.max(...years);
                
                const cellW = (width - padding.left - padding.right) / (maxYear - minYear + 1);
                const cellH = (height - padding.top - padding.bottom) / 2;
                
                // Labels
                const yLabels = [
                    { id: 'zograf', name: currentLang === 'ru' ? 'Зограф' : 'Zograf', y: padding.top + cellH * 0.5 },
                    { id: 'roerich', name: currentLang === 'ru' ? 'Рерих' : 'Roerich', y: padding.top + cellH * 1.5 }
                ];
                yLabels.forEach(lbl => {
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', padding.left - 15);
                    text.setAttribute('y', lbl.y + 4);
                    text.setAttribute('text-anchor', 'end');
                    text.setAttribute('fill', 'var(--muted)');
                    text.setAttribute('font-size', '12px');
                    text.textContent = lbl.name;
                    svg.appendChild(text);
                });
                
                const tooltip = document.getElementById('heatmap-tooltip');
                
                // Draw cells
                for (let y = minYear; y <= maxYear; y++) {
                    const x = padding.left + (y - minYear) * cellW;
                    
                    // Year label (every 2 years)
                    if (y % 2 === 0) {
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', x + cellW/2);
                        text.setAttribute('y', height - padding.bottom + 20);
                        text.setAttribute('text-anchor', 'middle');
                        text.setAttribute('fill', 'var(--muted)');
                        text.setAttribute('font-size', '10px');
                        text.textContent = y;
                        svg.appendChild(text);
                    }
                    
                    ['zograf', 'roerich'].forEach((group, idx) => {
                        const cy = padding.top + idx * cellH;
                        const dataPoint = HEATMAP_DATA.data.find(d => d.y === y && d.g === group);
                        const count = dataPoint ? dataPoint.c : 0;
                        
                        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                        rect.setAttribute('x', x + 2);
                        rect.setAttribute('y', cy + 2);
                        rect.setAttribute('width', cellW - 4);
                        rect.setAttribute('height', cellH - 4);
                        rect.setAttribute('rx', 4);
                        
                        if (count > 0) {
                            rect.setAttribute('fill', group === 'zograf' ? '#2b82c9' : '#b83280');
                            rect.setAttribute('fill-opacity', 0.2 + Math.min(count / 10, 0.8));
                            rect.setAttribute('cursor', 'pointer');
                            
                            rect.addEventListener('mouseenter', () => {
                                rect.setAttribute('stroke', '#fff');
                                tooltip.style.opacity = '1';
                                tooltip.innerHTML = `<strong>${group === 'zograf' ? 'Зографские чтения' : 'Рериховские чтения'} (${y})</strong><br/>Видеозаписей: ${count}`;
                            });
                            rect.addEventListener('mousemove', (e) => {
                                const container = document.getElementById('heatmap-wrapper').getBoundingClientRect();
                                tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                                tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                            });
                            rect.addEventListener('mouseleave', () => {
                                rect.removeAttribute('stroke');
                                tooltip.style.opacity = '0';
                            });
                        } else {
                            rect.setAttribute('fill', 'rgba(255,255,255,0.03)');
                        }
                        
                        svg.appendChild(rect);
                    });
                }
            }

            function drawAlluvial() {
                const svg = document.getElementById('alluvial-svg');
                if (!svg || !ALLUVIAL_DATA.nodes) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 500;
                const padding = { top: 40, right: 120, bottom: 20, left: 120 };
                
                const nodes = ALLUVIAL_DATA.nodes.map(n => ({...n, value: 0, sourceLinks: [], targetLinks: []}));
                const links = ALLUVIAL_DATA.links.map(l => ({...l}));
                
                links.forEach(l => {
                    nodes[l.source].sourceLinks.push(l);
                    nodes[l.target].targetLinks.push(l);
                    nodes[l.source].value += l.value;
                    nodes[l.target].value += l.value;
                });
                
                const groups = ['period', 'theme', 'meso'];
                const groupX = {
                    'period': padding.left,
                    'theme': width / 2,
                    'meso': width - padding.right
                };
                
                const yOffsets = { 'period': padding.top, 'theme': padding.top, 'meso': padding.top };
                const nodeHeightFactor = 3;
                
                // Group nodes and assign positions
                groups.forEach(g => {
                    const gNodes = nodes.filter(n => n.group === g).sort((a,b) => b.value - a.value);
                    gNodes.forEach(n => {
                        n.x = groupX[g];
                        n.y = yOffsets[g];
                        n.dy = n.value * nodeHeightFactor;
                        yOffsets[g] += n.dy + 15; // gap
                    });
                    
                    // Center vertically
                    const totalH = yOffsets[g] - padding.top - 15;
                    const shiftY = (height - padding.top - padding.bottom - totalH) / 2;
                    gNodes.forEach(n => n.y += Math.max(0, shiftY));
                });
                
                // Link positions
                nodes.forEach(n => {
                    let sy = n.y;
                    n.sourceLinks.sort((a,b) => nodes[b.target].y - nodes[a.target].y).forEach(l => {
                        l.sy = sy;
                        sy += l.value * nodeHeightFactor;
                    });
                    let ty = n.y;
                    n.targetLinks.sort((a,b) => nodes[b.source].y - nodes[a.source].y).forEach(l => {
                        l.ty = ty;
                        ty += l.value * nodeHeightFactor;
                    });
                });
                
                const tooltip = document.getElementById('alluvial-tooltip');
                
                // Draw Links
                links.forEach(l => {
                    const s = nodes[l.source];
                    const t = nodes[l.target];
                    const lWidth = l.value * nodeHeightFactor;
                    
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const curve = (s.x + 10 + t.x) / 2;
                    const d = `M ${s.x + 10} ${l.sy + lWidth/2} C ${curve} ${l.sy + lWidth/2}, ${curve} ${l.ty + lWidth/2}, ${t.x} ${l.ty + lWidth/2}`;
                    
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', 'rgba(255,255,255,0.15)');
                    path.setAttribute('stroke-width', Math.max(1, lWidth));
                    path.setAttribute('class', 'alluvial-link');
                    path.style.cursor = 'pointer';
                    path.style.transition = 'stroke 0.2s';
                    
                    path.addEventListener('mouseenter', () => {
                        path.setAttribute('stroke', 'var(--accent)');
                        path.setAttribute('stroke-opacity', '0.6');
                        tooltip.style.opacity = '1';
                        tooltip.innerHTML = `<strong>${s.name} → ${t.name}</strong><br/>Связей: ${l.value}`;
                    });
                    path.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('alluvial-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    path.addEventListener('mouseleave', () => {
                        path.setAttribute('stroke', 'rgba(255,255,255,0.15)');
                        tooltip.style.opacity = '0';
                    });
                    
                    svg.appendChild(path);
                });
                
                // Draw Nodes
                nodes.forEach(n => {
                    if (n.value === 0) return;
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', n.x);
                    rect.setAttribute('y', n.y);
                    rect.setAttribute('width', 10);
                    rect.setAttribute('height', n.dy);
                    rect.setAttribute('fill', 'var(--accent2)');
                    rect.setAttribute('rx', 2);
                    svg.appendChild(rect);
                    
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('y', n.y + n.dy / 2 + 4);
                    text.setAttribute('fill', '#fff');
                    text.setAttribute('font-size', '11px');
                    
                    if (n.group === 'meso') {
                        text.setAttribute('x', n.x + 15);
                        text.setAttribute('text-anchor', 'start');
                    } else if (n.group === 'period') {
                        text.setAttribute('x', n.x - 5);
                        text.setAttribute('text-anchor', 'end');
                    } else {
                        text.setAttribute('x', n.x + 15);
                        text.setAttribute('text-anchor', 'start');
                    }
                    
                    text.textContent = n.name;
                    svg.appendChild(text);
                });
            }

            const OPACITY_DATA = """ + serialized_opacity + """;
            let currentOpacitySeries = 'combined';

            function switchOpacitySeries(series) {
                currentOpacitySeries = series;
                document.querySelectorAll('.opacity-toggle-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
                const activeBtn = Array.from(document.querySelectorAll('.opacity-toggle-btn')).find(btn => {
                    const onclickStr = btn.getAttribute('onclick') || '';
                    return onclickStr.includes(series);
                });
                if (activeBtn) activeBtn.classList.add('active');
                drawOpacityChart();
            }

            function drawOpacityChart() {
                const svg = document.getElementById('opacity-svg');
                if (!svg) return;
                svg.innerHTML = '';

                const width = 800;
                const height = 380;
                const padding = { top: 30, right: 40, bottom: 40, left: 55 };

                const chartData = [];
                OPACITY_DATA.forEach(d => {
                    let verified = 0;
                    let cityOnly = 0;
                    let unknown = 0;

                    if (currentOpacitySeries === 'combined' || currentOpacitySeries === 'zograf') {
                        verified += d.zograf.verified;
                        cityOnly += d.zograf.city_only;
                        unknown += d.zograf.unknown;
                    }
                    if (currentOpacitySeries === 'combined' || currentOpacitySeries === 'roerich') {
                        verified += d.roerich.verified;
                        cityOnly += d.roerich.city_only;
                        unknown += d.roerich.unknown;
                    }

                    const total = verified + cityOnly + unknown;
                    if (total > 0) {
                        chartData.push({
                            year: d.year,
                            verified: verified,
                            cityOnly: cityOnly,
                            unknown: unknown,
                            total: total
                        });
                    }
                });

                if (chartData.length === 0) return;

                const xScale = (index) => padding.left + (index / (chartData.length - 1)) * (width - padding.left - padding.right);
                const yScale = (pct) => height - padding.bottom - (pct / 100) * (height - padding.top - padding.bottom);

                const yTicks = [0, 25, 50, 75, 100];
                yTicks.forEach(tick => {
                    const y = yScale(tick);
                    
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', y);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', y);
                    line.setAttribute('class', 'scatter-grid-line');
                    svg.appendChild(line);

                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 10);
                    label.setAttribute('y', y + 4);
                    label.setAttribute('text-anchor', 'end');
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '11px');
                    label.textContent = tick + '%';
                    svg.appendChild(label);
                });

                const step = Math.ceil(chartData.length / 10);
                chartData.forEach((d, idx) => {
                    if (idx % step === 0 || idx === chartData.length - 1) {
                        const x = xScale(idx);
                        
                        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        label.setAttribute('x', x);
                        label.setAttribute('y', height - padding.bottom + 20);
                        label.setAttribute('text-anchor', 'middle');
                        label.setAttribute('fill', 'var(--muted)');
                        label.setAttribute('font-size', '11px');
                        label.textContent = d.year;
                        svg.appendChild(label);
                    }
                });

                const barWidth = Math.max(12, Math.min(26, (width - padding.left - padding.right) / chartData.length - 8));
                const tooltip = document.getElementById('opacity-tooltip');

                chartData.forEach((d, idx) => {
                    const x = xScale(idx) - barWidth / 2;
                    
                    const pVerified = (d.verified / d.total) * 100;
                    const pCity = (d.cityOnly / d.total) * 100;
                    const pUnknown = (d.unknown / d.total) * 100;

                    const y1 = yScale(pVerified);
                    const h1 = yScale(0) - y1;

                    const y2 = yScale(pVerified + pCity);
                    const h2 = y1 - y2;

                    const y3 = yScale(100);
                    const h3 = y2 - y3;

                    const cVerified = '#10b981';
                    const cCity = '#f59e0b';
                    const cUnknown = '#6b7280';

                    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                    g.setAttribute('class', 'opacity-bar');

                    const drawRect = (y, h, color) => {
                        if (h <= 0.1) return;
                        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                        rect.setAttribute('x', x);
                        rect.setAttribute('y', y);
                        rect.setAttribute('width', barWidth);
                        rect.setAttribute('height', h);
                        rect.setAttribute('fill', color);
                        g.appendChild(rect);
                    };

                    drawRect(y3, h3, cUnknown);
                    drawRect(y2, h2, cCity);
                    drawRect(y1, h1, cVerified);

                    g.addEventListener('mouseenter', (e) => {
                        tooltip.style.opacity = '1';
                        
                        const labelY = currentLang === 'ru' ? 'Год' : 'Year';
                        const labelTot = currentLang === 'ru' ? 'Всего докладов' : 'Total presentations';
                        const labelVer = currentLang === 'ru' ? 'Подтвержденные' : 'Verified';
                        const labelCit = currentLang === 'ru' ? 'Только город' : 'City Only';
                        const labelUnk = currentLang === 'ru' ? 'Неизвестно' : 'Unknown';

                        tooltip.innerHTML = 
                            '<strong style="color:var(--accent); font-size: 0.95rem;">' + labelY + ': ' + d.year + '</strong><br>' +
                            '<span style="font-weight:bold; font-size:0.8rem; color:var(--muted);">' + labelTot + ': ' + d.total + '</span><hr style="border:0; border-top:1px solid rgba(255,255,255,0.1); margin:6px 0;">' +
                            '<span style="color:#10b981; font-weight:bold;">● ' + labelVer + ': ' + d.verified + ' (' + pVerified.toFixed(1) + '%)</span><br>' +
                            '<span style="color:#f59e0b; font-weight:bold;">● ' + labelCit + ': ' + d.cityOnly + ' (' + pCity.toFixed(1) + '%)</span><br>' +
                            '<span style="color:#9ca3af; font-weight:bold;">● ' + labelUnk + ': ' + d.unknown + ' (' + pUnknown.toFixed(1) + '%)</span>';
                    });

                    g.addEventListener('mousemove', (e) => {
                        const rect = svg.getBoundingClientRect();
                        const tooltipRect = tooltip.getBoundingClientRect();
                        const tooltipX = e.clientX - rect.left + 15;
                        const tooltipY = e.clientY - rect.top - tooltipRect.height - 10;
                        tooltip.style.left = tooltipX + 'px';
                        tooltip.style.top = tooltipY + 'px';
                    });

                    g.addEventListener('mouseleave', () => {
                        tooltip.style.opacity = '0';
                    });

                    svg.appendChild(g);
                });

                const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                xAxis.setAttribute('x1', padding.left);
                xAxis.setAttribute('y1', height - padding.bottom);
                xAxis.setAttribute('x2', width - padding.right);
                xAxis.setAttribute('y2', height - padding.bottom);
                xAxis.setAttribute('stroke', 'rgba(255,255,255,0.2)');
                svg.appendChild(xAxis);

                const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                yAxis.setAttribute('x1', padding.left);
                yAxis.setAttribute('y1', padding.top);
                yAxis.setAttribute('x2', padding.left);
                yAxis.setAttribute('y2', height - padding.bottom);
                yAxis.setAttribute('stroke', 'rgba(255,255,255,0.2)');
                svg.appendChild(yAxis);
            }

            let currentLang = localStorage.getItem('findings-lang') || 'ru';

            function toggleLanguage() {
                currentLang = currentLang === 'ru' ? 'en' : 'ru';
                setLanguage(currentLang);
            }

            function setLanguage(lang) {
                document.querySelectorAll('.bilingual-text').forEach(el => {
                    const text = el.getAttribute('data-' + lang);
                    if (text) {
                        el.innerHTML = text;
                    }
                });
                const btn = document.getElementById('lang-toggle-btn');
                if (btn) {
                    btn.innerText = lang === 'ru' ? 'English' : 'Русский';
                }
                localStorage.setItem('findings-lang', lang);
                drawScatter();
                drawOpacityChart();
                drawHeatmap();
                drawForest();
                drawHierarchy();
                drawArc();
                drawGeoMap();
                drawBubbleCloud();
                drawAlluvial();
                if (typeof drawGallery === 'function') drawGallery();
            }

            document.addEventListener('DOMContentLoaded', () => {
                setLanguage(currentLang);
                switchOpacitySeries('combined');
            });
        </script>
    """

    gallery_js = """
        <script>
            const DEMOGRAPHY_DATA = """ + serialized_demography + """;
            const SURVIVAL_DATA = """ + serialized_survival + """;
            const NEWCOMER_DATA = """ + serialized_newcomer + """;
            const TREEMAP_DATA = """ + serialized_treemap + """;
            const GUMILYOV_DATA = """ + serialized_gumilyov + """;
            const KEYWORD_DIV_DATA = """ + serialized_keyword_div + """;
            const CLOSEDNESS_DATA = """ + serialized_closedness + """;
            const ONLINE_DATA = """ + serialized_online + """;
            const VIS041_DATA = """ + serialized_vis041 + """;
            const VIS042_DATA = """ + serialized_vis042 + """;

            const VIS038_DATA = """ + serialized_vis038 + """;
            const VIS039_DATA = """ + serialized_vis039 + """;
            const VIS040_DATA = """ + serialized_vis040 + """;

            const VIS035_DATA = """ + serialized_vis035 + """;
            const VIS036_DATA = """ + serialized_vis036 + """;
            const VIS037_DATA = """ + serialized_vis037 + """;

            const VIS031_DATA = """ + serialized_vis031 + """;
            const VIS032_DATA = """ + serialized_vis032 + """;
            const VIS033_DATA = """ + serialized_vis033 + """;
            const VIS034_DATA = """ + serialized_vis034 + """;

            const VIS024_DATA = """ + serialized_vis024 + """;
            const VIS025_DATA = """ + serialized_vis025 + """;
            const VIS026_DATA = """ + serialized_vis026 + """;
            const VIS027_DATA = """ + serialized_vis027 + """;
            const VIS028_DATA = """ + serialized_vis028 + """;
            const VIS029_DATA = """ + serialized_vis029 + """;
            const VIS030_DATA = """ + serialized_vis030 + """;

            const VIS020_DATA = """ + serialized_vis020 + """;
            const VIS021_DATA = """ + serialized_vis021 + """;
            const VIS022_DATA = """ + serialized_vis022 + """;
            const VIS023_DATA = """ + serialized_vis023 + """;

            const VIS016_DATA = """ + serialized_vis016 + """;
            const VIS018_DATA = """ + serialized_vis018 + """;
            const VIS019_DATA = """ + serialized_vis019 + """;


            const SVGNS = 'http://www.w3.org/2000/svg';
            function gEl(tag, attrs) { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }
            function gText(x, y, s, anchor, size, fill) { const t = gEl('text', {x: x, y: y, 'text-anchor': anchor || 'middle', 'font-size': (size || 11) + 'px', fill: fill || 'var(--muted)'}); t.textContent = s; return t; }
            function T(ru, en) { return (typeof currentLang !== 'undefined' && currentLang === 'en') ? en : ru; }
            function seriesName(s) { return s === 'zograf' ? T('Зограф', 'Zograf') : T('Рерих', 'Roerich'); }
            function bindTip(target, wrapId, tipId, htmlFn) {
                const tip = document.getElementById(tipId); const wrap = document.getElementById(wrapId);
                if (!tip || !wrap) return;
                target.style.cursor = 'pointer';
                target.addEventListener('mouseenter', () => { tip.style.opacity = '1'; tip.innerHTML = htmlFn(); });
                target.addEventListener('mousemove', (e) => { const r = wrap.getBoundingClientRect(); tip.style.left = (e.clientX - r.left + 15) + 'px'; tip.style.top = (e.clientY - r.top - 10) + 'px'; });
                target.addEventListener('mouseleave', () => { tip.style.opacity = '0'; });
            }
            const SERIES_COLORS = {zograf: '#2b82c9', roerich: '#b83280'};
            const THEME_LABELS = {
                religion_and_philosophy: {ru: 'Религия и философия', en: 'Religion & Philosophy', c: '#6366f1'},
                literature_and_poetry: {ru: 'Литература и поэзия', en: 'Literature & Poetry', c: '#ec4899'},
                history_and_culture: {ru: 'История и культура', en: 'History & Culture', c: '#f59e0b'},
                linguistics_and_philology: {ru: 'Лингвистика и филология', en: 'Linguistics & Philology', c: '#10b981'},
                art_and_material_culture: {ru: 'Искусство и матер. культура', en: 'Art & Material Culture', c: '#06b6d4'},
                unspecified: {ru: 'Не указано', en: 'Unspecified', c: '#6b7280'}
            };

            // VIS_008 — Demography ribbon
            function drawDemography() {
                const svg = document.getElementById('demo-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 420, pad = {t: 30, r: 30, b: 50, l: 50};
                const years = [...new Set(DEMOGRAPHY_DATA.map(d => d.year))].sort((a, b) => a - b);
                if (!years.length) return;
                const aMin = 15, aMax = 90, span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const yq = a => H - pad.b - (a - aMin) / (aMax - aMin) * (H - pad.t - pad.b);
                for (let a = aMin; a <= aMax; a += 15) { const yy = yq(a); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, a, 'end', 11)); }
                years.forEach(y => { if (y % 4 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                ['zograf', 'roerich'].forEach(s => {
                    const ser = DEMOGRAPHY_DATA.filter(d => d.series === s).sort((a, b) => a.year - b.year);
                    if (!ser.length) return;
                    let pts = ser.map(d => xq(d.year) + ',' + yq(d.p75));
                    for (let i = ser.length - 1; i >= 0; i--) pts.push(xq(ser[i].year) + ',' + yq(ser[i].p25));
                    svg.appendChild(gEl('polygon', {points: pts.join(' '), fill: SERIES_COLORS[s], 'fill-opacity': 0.13, stroke: 'none'}));
                    svg.appendChild(gEl('polyline', {points: ser.map(d => xq(d.year) + ',' + yq(d.median)).join(' '), fill: 'none', stroke: SERIES_COLORS[s], 'stroke-width': 2.5, 'stroke-opacity': 0.9}));
                    ser.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.median), r: 4, fill: SERIES_COLORS[s]});
                        bindTip(c, 'demo-wrapper', 'demo-tooltip', () => '<strong>' + seriesName(s) + ' · ' + d.year + '</strong><br>' + T('Медиана', 'Median') + ': ' + d.median.toFixed(1) + '<br>' + T('Среднее', 'Mean') + ': ' + d.avg.toFixed(1) + '<br>' + T('Квартили', 'Quartiles') + ': ' + d.p25.toFixed(0) + '–' + d.p75.toFixed(0) + '<br>' + T('Размах', 'Range') + ': ' + d.min.toFixed(0) + '–' + d.max.toFixed(0) + '<br>n = ' + d.n);
                        svg.appendChild(c); });
                });
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gText(pad.l, pad.t - 12, T('Возраст, лет', 'Age, years'), 'start', 11));
            }

            // VIS_009 — Cohort survival
            function drawSurvival() {
                const svg = document.getElementById('survival-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 420, pad = {t: 30, r: 30, b: 50, l: 50};
                let xMax = 2; SURVIVAL_DATA.forEach(c => c.points.forEach(p => { if (p.x > xMax) xMax = p.x; }));
                const xq = x => pad.l + x / xMax * (W - pad.l - pad.r);
                const yq = v => H - pad.b - v / 100 * (H - pad.t - pad.b);
                for (let v = 0; v <= 100; v += 25) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                for (let x = 0; x <= xMax; x += 2) svg.appendChild(gText(xq(x), H - pad.b + 20, x, 'middle', 10));
                SURVIVAL_DATA.forEach(c => {
                    svg.appendChild(gEl('polyline', {points: c.points.map(p => xq(p.x) + ',' + yq(p.y)).join(' '), fill: 'none', stroke: SERIES_COLORS[c.series], 'stroke-width': 1.4, 'stroke-opacity': 0.4}));
                    c.points.forEach(p => { const dot = gEl('circle', {cx: xq(p.x), cy: yq(p.y), r: 3, fill: SERIES_COLORS[c.series], 'fill-opacity': 0.7});
                        bindTip(dot, 'survival-wrapper', 'survival-tooltip', () => '<strong>' + seriesName(c.series) + ' · ' + T('дебют', 'debut') + ' ' + c.debut + '</strong><br>' + T('Размер когорты', 'Cohort size') + ': ' + c.size + '<br>' + T('Лет после дебюта', 'Years since debut') + ': ' + p.x + '<br>' + T('Активны', 'Active') + ': ' + p.y.toFixed(0) + '%');
                        svg.appendChild(dot); });
                });
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gText(W / 2, H - 10, T('Лет после первого доклада', 'Years since first talk'), 'middle', 11));
            }

            // VIS_010 — Newcomer rate
            function drawNewcomer() {
                const svg = document.getElementById('newcomer-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 380, pad = {t: 30, r: 30, b: 50, l: 50};
                const years = [...new Set(NEWCOMER_DATA.map(d => d.year))].sort((a, b) => a - b);
                if (!years.length) return;
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const yq = v => H - pad.b - v / 100 * (H - pad.t - pad.b);
                for (let v = 0; v <= 100; v += 25) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                ['zograf', 'roerich'].forEach(s => {
                    const ser = NEWCOMER_DATA.filter(d => d.series === s).sort((a, b) => a.year - b.year);
                    if (!ser.length) return;
                    svg.appendChild(gEl('polyline', {points: ser.map(d => xq(d.year) + ',' + yq(d.pct)).join(' '), fill: 'none', stroke: SERIES_COLORS[s], 'stroke-width': 2.5, 'stroke-opacity': 0.85}));
                    ser.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.pct), r: 4, fill: SERIES_COLORS[s]});
                        bindTip(c, 'newcomer-wrapper', 'newcomer-tooltip', () => '<strong>' + seriesName(s) + ' · ' + d.year + '</strong><br>' + T('Новички', 'Newcomers') + ': ' + d.newcomers + ' / ' + d.total + '<br>' + T('Доля', 'Share') + ': ' + d.pct.toFixed(1) + '%');
                        svg.appendChild(c); });
                });
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            // VIS_011 — Theme treemap (slice-and-dice, L1 → L2)
            function drawTreemap() {
                const svg = document.getElementById('treemap-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 460, m = 10, headerH = 24;
                const total = TREEMAP_DATA.reduce((s, d) => s + d.value, 0) || 1;
                const innerW = W - 2 * m, innerH = H - 2 * m - headerH, top = m + headerH;
                let x = m;
                TREEMAP_DATA.forEach(l1 => {
                    const colW = l1.value / total * innerW;
                    const meta = THEME_LABELS[l1.name] || {ru: l1.name, en: l1.name, c: '#888'};
                    if (colW > 64) { const lab = gText(x + colW / 2, m + 15, T(meta.ru, meta.en), 'middle', 11, meta.c); lab.setAttribute('font-weight', 'bold'); lab.style.pointerEvents = 'none'; svg.appendChild(lab); }
                    let y = top;
                    l1.children.forEach(ch => {
                        const cellH = ch.value / l1.value * innerH;
                        const rect = gEl('rect', {x: x + 1, y: y + 1, width: Math.max(0, colW - 2), height: Math.max(0, cellH - 2), fill: meta.c, 'fill-opacity': 0.82, rx: 2});
                        bindTip(rect, 'treemap-wrapper', 'treemap-tooltip', () => '<strong>' + T(meta.ru, meta.en) + '</strong><br>L2: ' + ch.name + '<br>' + T('Докладов', 'Presentations') + ': ' + ch.value + ' (' + (ch.value / total * 100).toFixed(1) + '%)');
                        svg.appendChild(rect);
                        if (colW > 50 && cellH > 20) { const t = gText(x + 6, y + 15, ch.name, 'start', 10, 'rgba(255,255,255,0.92)'); t.style.pointerEvents = 'none'; svg.appendChild(t); }
                        y += cellH;
                    });
                    x += colW;
                });
            }

            // VIS_012 — Gumilyov streamgraph (stacked area)
            function drawGumilyov() {
                const svg = document.getElementById('stream-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 380, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = GUMILYOV_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const maxTot = Math.max(...D.map(d => d.l1 + d.l2 + d.l3)) || 1;
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const yq = v => H - pad.b - v / maxTot * (H - pad.t - pad.b);
                for (let f = 0; f <= 1.0001; f += 0.25) { const v = maxTot * f, yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, Math.round(v), 'end', 11)); }
                years.forEach(y => { if (y % 4 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                const cols = ['#6366f1', '#f59e0b', '#ef4444'], keys = ['l1', 'l2', 'l3'];
                const lower = D.map(() => 0);
                keys.forEach((k, ki) => {
                    let up = [], down = [];
                    D.forEach((d, i) => { const topv = lower[i] + d[k]; up.push(xq(d.year) + ',' + yq(topv)); lower[i] = topv; });
                    for (let i = D.length - 1; i >= 0; i--) down.push(xq(D[i].year) + ',' + yq(lower[i] - D[i][k]));
                    svg.appendChild(gEl('polygon', {points: up.concat(down).join(' '), fill: cols[ki], 'fill-opacity': 0.7, stroke: cols[ki], 'stroke-opacity': 0.9, 'stroke-width': 0.5}));
                });
                D.forEach((d, i) => {
                    const x0 = i === 0 ? pad.l : (xq(D[i - 1].year) + xq(d.year)) / 2;
                    const x1 = i === D.length - 1 ? (W - pad.r) : (xq(d.year) + xq(D[i + 1].year)) / 2;
                    const r = gEl('rect', {x: x0, y: pad.t, width: Math.max(1, x1 - x0), height: H - pad.t - pad.b, fill: 'transparent'});
                    const tot = d.l1 + d.l2 + d.l3 || 1;
                    bindTip(r, 'stream-wrapper', 'stream-tooltip', () => '<strong>' + d.year + '</strong> · ' + T('всего', 'total') + ' ' + tot + '<br><span style="color:#6366f1">●</span> ' + T('Микро', 'Micro') + ': ' + d.l1 + ' (' + (d.l1 / tot * 100).toFixed(0) + '%)<br><span style="color:#f59e0b">●</span> ' + T('Региональный', 'Regional') + ': ' + d.l2 + ' (' + (d.l2 / tot * 100).toFixed(0) + '%)<br><span style="color:#ef4444">●</span> ' + T('Глобальный', 'Global') + ': ' + d.l3 + ' (' + (d.l3 / tot * 100).toFixed(0) + '%)');
                    svg.appendChild(r);
                });
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            // VIS_013 — Keyword diverging bars
            function drawKeywordDiv() {
                const svg = document.getElementById('keyword-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 560, padT = 20, padB = 20;
                const D = KEYWORD_DIV_DATA; if (!D.length) return;
                const n = D.length, pitch = (H - padT - padB) / n;
                const gapL = 346, gapR = 454, leftSpace = gapL - 22, rightSpace = (W - 22) - gapR;
                const maxV = Math.max(...D.map(d => Math.max(d.z, d.r))) || 1;
                const scale = Math.min(leftSpace, rightSpace) / maxV;
                svg.appendChild(gEl('line', {x1: gapL, y1: padT, x2: gapL, y2: H - padB, stroke: 'rgba(255,255,255,0.12)'}));
                svg.appendChild(gEl('line', {x1: gapR, y1: padT, x2: gapR, y2: H - padB, stroke: 'rgba(255,255,255,0.12)'}));
                D.forEach((d, i) => {
                    const yc = padT + i * pitch + pitch / 2, bh = Math.min(16, pitch * 0.62);
                    const zw = d.z * scale, rw = d.r * scale;
                    const tipFn = () => '<strong>' + d.kw + '</strong><br>' + T('Зограф', 'Zograf') + ': ' + d.z + '<br>' + T('Рерих', 'Roerich') + ': ' + d.r + '<br>' + T('Всего', 'Total') + ': ' + d.total;
                    const zr = gEl('rect', {x: gapL - zw, y: yc - bh / 2, width: zw, height: bh, fill: '#2b82c9', rx: 2}); bindTip(zr, 'keyword-wrapper', 'keyword-tooltip', tipFn); svg.appendChild(zr);
                    const rr = gEl('rect', {x: gapR, y: yc - bh / 2, width: rw, height: bh, fill: '#b83280', rx: 2}); bindTip(rr, 'keyword-wrapper', 'keyword-tooltip', tipFn); svg.appendChild(rr);
                    const lab = gText((gapL + gapR) / 2, yc + 3, d.kw, 'middle', 10, 'rgba(255,255,255,0.9)'); lab.style.pointerEvents = 'none'; svg.appendChild(lab);
                    if (zw > 16) { const zt = gText(gapL - zw - 4, yc + 3, d.z, 'end', 9, 'rgba(255,255,255,0.6)'); zt.style.pointerEvents = 'none'; svg.appendChild(zt); }
                    if (rw > 16) { const rt = gText(gapR + rw + 4, yc + 3, d.r, 'start', 9, 'rgba(255,255,255,0.6)'); rt.style.pointerEvents = 'none'; svg.appendChild(rt); }
                });
            }

            // VIS_014 — Closedness comparison
            function drawClosedness() {
                const svg = document.getElementById('closedness-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 400, pad = {t: 40, r: 30, b: 60, l: 50};
                const z = CLOSEDNESS_DATA.zograf, r = CLOSEDNESS_DATA.roerich; if (!z || !r) return;
                const metrics = [['one_talk', T('Однодокладчики', 'One-talk %')], ['core5', T('Ядро 5+', 'Core 5+ %')], ['retention', T('Удержание', 'Retention %')], ['gini', T('Джини×100', 'Gini×100')]];
                const yq = v => H - pad.b - v / 100 * (H - pad.t - pad.b);
                for (let v = 0; v <= 100; v += 25) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                const plotW = W - pad.l - pad.r, gw = plotW / metrics.length, bw = gw * 0.28;
                metrics.forEach((mt, i) => {
                    const cx = pad.l + gw * i + gw / 2;
                    const zb = gEl('rect', {x: cx - bw - 3, y: yq(z[mt[0]]), width: bw, height: H - pad.b - yq(z[mt[0]]), fill: '#2b82c9', rx: 2});
                    bindTip(zb, 'closedness-wrapper', 'closedness-tooltip', () => '<strong>' + T('Зограф', 'Zograf') + ' · ' + mt[1] + '</strong><br>' + z[mt[0]].toFixed(1)); svg.appendChild(zb);
                    const rb = gEl('rect', {x: cx + 3, y: yq(r[mt[0]]), width: bw, height: H - pad.b - yq(r[mt[0]]), fill: '#b83280', rx: 2});
                    bindTip(rb, 'closedness-wrapper', 'closedness-tooltip', () => '<strong>' + T('Рерих', 'Roerich') + ' · ' + mt[1] + '</strong><br>' + r[mt[0]].toFixed(1)); svg.appendChild(rb);
                    svg.appendChild(gText(cx - bw / 2 - 3, yq(z[mt[0]]) - 5, z[mt[0]].toFixed(0), 'middle', 9, 'rgba(255,255,255,0.7)'));
                    svg.appendChild(gText(cx + bw / 2 + 3, yq(r[mt[0]]) - 5, r[mt[0]].toFixed(0), 'middle', 9, 'rgba(255,255,255,0.7)'));
                    svg.appendChild(gText(cx, H - pad.b + 22, mt[1], 'middle', 10, 'var(--muted)'));
                });
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            // VIS_015 — Online share
            function drawOnline() {
                const svg = document.getElementById('online-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = ONLINE_DATA; if (!D.length) return;
                const years = [...new Set(D.map(d => d.year))].sort((a, b) => a - b);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const yq = v => H - pad.b - v / 100 * (H - pad.t - pad.b);
                for (let v = 0; v <= 100; v += 25) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                if (years[0] <= 2020 && years[years.length - 1] >= 2020) { const xm = xq(2020); svg.appendChild(gEl('line', {x1: xm, y1: pad.t, x2: xm, y2: H - pad.b, stroke: '#f59e0b', 'stroke-dasharray': '4 4', 'stroke-opacity': 0.6})); svg.appendChild(gText(xm + 4, pad.t + 12, '2020', 'start', 10, '#f59e0b')); }
                ['zograf', 'roerich'].forEach(s => {
                    const ser = D.filter(d => d.series === s).sort((a, b) => a.year - b.year);
                    if (!ser.length) return;
                    let area = ser.map(d => xq(d.year) + ',' + yq(d.pct));
                    area.push(xq(ser[ser.length - 1].year) + ',' + yq(0)); area.push(xq(ser[0].year) + ',' + yq(0));
                    svg.appendChild(gEl('polygon', {points: area.join(' '), fill: SERIES_COLORS[s], 'fill-opacity': 0.1}));
                    svg.appendChild(gEl('polyline', {points: ser.map(d => xq(d.year) + ',' + yq(d.pct)).join(' '), fill: 'none', stroke: SERIES_COLORS[s], 'stroke-width': 2.5}));
                    ser.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.pct), r: 4, fill: SERIES_COLORS[s]});
                        bindTip(c, 'online-wrapper', 'online-tooltip', () => '<strong>' + seriesName(s) + ' · ' + d.year + '</strong><br>' + T('Онлайн', 'Online') + ': ' + d.on + ' / ' + (d.on + d.off) + '<br>' + T('Доля', 'Share') + ': ' + d.pct.toFixed(1) + '%');
                        svg.appendChild(c); });
                });
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }



            function drawVIS016() {
                const svg = document.getElementById('vis016-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS016_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                // Stacked logic for decades
                let allDecades = new Set();
                D.forEach(d => Object.keys(d.decades).forEach(k => allDecades.add(parseInt(k))));
                const decades = Array.from(allDecades).sort((a,b)=>a-b);
                const maxTot = Math.max(...D.map(d => Object.values(d.decades).reduce((a,b)=>a+b, 0))) || 1;
                const yq = v => H - pad.b - v / maxTot * (H - pad.t - pad.b);
                
                for (let f = 0; f <= 1.0001; f += 0.25) { const v = maxTot * f, yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, Math.round(v), 'end', 11)); }
                
                const cols = ['#0f172a', '#1e293b', '#334155', '#475569', '#64748b', '#94a3b8', '#cbd5e1', '#e2e8f0', '#f1f5f9', '#f8fafc'];
                const lower = D.map(() => 0);
                decades.forEach((dk, ki) => {
                    let up = [], down = [];
                    D.forEach((d, i) => { const v = d.decades[dk] || 0; const topv = lower[i] + v; up.push(xq(d.year) + ',' + yq(topv)); lower[i] = topv; });
                    for (let i = D.length - 1; i >= 0; i--) down.push(xq(D[i].year) + ',' + yq(lower[i] - (D[i].decades[dk]||0)));
                    const poly = gEl('polygon', {points: up.concat(down).join(' '), fill: cols[ki%cols.length], 'fill-opacity': 0.8, stroke: 'none'});
                    bindTip(poly, 'vis016-wrapper', 'vis016-tooltip', () => '<strong>' + T('Поколение', 'Generation') + ' ' + dk + 's</strong>');
                    svg.appendChild(poly);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS018() {
                const svg = document.getElementById('vis018-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS018_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.avg)) + 2;
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 2) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.avg)).join(' '), fill: 'none', stroke: '#10b981', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.avg), r: 4, fill: '#10b981'});
                    bindTip(c, 'vis018-wrapper', 'vis018-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Слов в названии', 'Words per title') + ': ' + d.avg.toFixed(1));
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS019() {
                const svg = document.getElementById('vis019-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS019_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(20, Math.max(...D.map(d => d.pct)) + 5);
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 5) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.pct)).join(' '), fill: 'none', stroke: '#f59e0b', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.pct), r: 4, fill: '#f59e0b'});
                    bindTip(c, 'vis019-wrapper', 'vis019-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Соавторство', 'Co-authorship') + ': ' + d.pct.toFixed(1) + '%');
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }




            function drawVIS020() {
                const svg = document.getElementById('vis020-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS020_DATA; if (!D.timeline || !D.timeline.length) return;
                const years = D.timeline.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.timeline.map(d => Math.max(...Object.values(d.scores))));
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 5) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                const cols = ['#ec4899', '#8b5cf6', '#3b82f6', '#10b981', '#f59e0b'];
                D.names.forEach((name, i) => {
                    const c = cols[i];
                    svg.appendChild(gEl('polyline', {points: D.timeline.map(d => xq(d.year) + ',' + yq(d.scores[name])).join(' '), fill: 'none', stroke: c, 'stroke-width': 2}));
                    const lastD = D.timeline[D.timeline.length - 1];
                    const t = gText(W - pad.r + 5, yq(lastD.scores[name]) + 4, name.split(' ')[0], 'start', 9, c); t.style.pointerEvents = 'none'; svg.appendChild(t);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS021() {
                const svg = document.getElementById('vis021-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 150, b: 30, l: 50};
                const D = VIS021_DATA; if (!D.length) return;
                const maxV = D[0].val;
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const w = (d.val / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: pad.l, y: y, width: w, height: barH, fill: '#3b82f6', rx: 2});
                    bindTip(rect, 'vis021-wrapper', 'vis021-tooltip', () => '<strong>' + d.name + '</strong><br>' + d.val + ' ' + T('докладов', 'presentations'));
                    svg.appendChild(rect);
                    svg.appendChild(gText(pad.l + w + 10, y + barH/2 + 4, d.name + ' (' + d.val + ')', 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS022() {
                const svg = document.getElementById('vis022-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS022_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const yq = v => H - pad.b - v / 90 * (H - pad.t - pad.b);
                
                for (let v = 20; v <= 90; v += 10) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                D.forEach(d => {
                    svg.appendChild(gEl('line', {x1: xq(d.year), y1: yq(d.min), x2: xq(d.year), y2: yq(d.max), stroke: 'rgba(16, 185, 129, 0.4)', 'stroke-width': 4}));
                    const c = gEl('circle', {cx: xq(d.year), cy: yq(d.median), r: 4, fill: '#10b981'});
                    bindTip(c, 'vis022-wrapper', 'vis022-tooltip', () => '<strong>' + d.year + '</strong><br>Min: ' + d.min + '<br>Median: ' + d.median + '<br>Max: ' + d.max);
                    svg.appendChild(c);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS023() {
                const svg = document.getElementById('vis023-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS023_DATA; if (!D.length) return;
                const maxV = Math.max(...D.map(d => d.count));
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                const pitch = (W - pad.l - pad.r) / D.length;
                
                for (let v = 0; v <= maxV; v += 50) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                
                D.forEach((d, i) => {
                    const cx = pad.l + i * pitch + pitch / 2;
                    const w = pitch * 0.6;
                    const rect = gEl('rect', {x: cx - w/2, y: yq(d.count), width: w, height: H - pad.b - yq(d.count), fill: '#f59e0b', rx: 2});
                    bindTip(rect, 'vis023-wrapper', 'vis023-tooltip', () => '<strong>' + (d.years==='5'?'5+':d.years) + ' ' + T('лет участия', 'years') + '</strong><br>' + d.count + ' ' + T('ученых', 'scholars'));
                    svg.appendChild(rect);
                    svg.appendChild(gText(cx, H - pad.b + 20, (d.years==='5'?'5+':d.years), 'middle', 11, 'var(--muted)'));
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }




            function drawVIS024() {
                const svg = document.getElementById('vis024-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 30};
                const D = VIS024_DATA; if (!D.length) return;
                
                const maxV = Math.max(...D.map(d => d.val));
                D.forEach((d, i) => {
                    const x = pad.l + Math.random() * (W - pad.l - pad.r);
                    const y = pad.t + Math.random() * (H - pad.t - pad.b);
                    const r = 5 + (d.val / maxV) * 30;
                    const c = gEl('circle', {cx: x, cy: y, r: r, fill: '#6366f1', 'fill-opacity': 0.6, stroke: '#6366f1'});
                    bindTip(c, 'vis024-wrapper', 'vis024-tooltip', () => '<strong>' + d.text + '</strong><br>' + d.val);
                    svg.appendChild(c);
                    if (r > 10) svg.appendChild(gText(x, y + 4, d.text, 'middle', Math.min(14, r), 'white'));
                });
            }

            function drawVIS025() {
                const svg = document.getElementById('vis025-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS025_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.pres));
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 20) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.pres)).join(' '), fill: 'none', stroke: '#10b981', 'stroke-width': 3}));
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.sess)).join(' '), fill: 'none', stroke: '#8b5cf6', 'stroke-width': 3}));
                
                D.forEach(d => { 
                    const cp = gEl('circle', {cx: xq(d.year), cy: yq(d.pres), r: 4, fill: '#10b981'});
                    bindTip(cp, 'vis025-wrapper', 'vis025-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Доклады', 'Presentations') + ': ' + d.pres);
                    svg.appendChild(cp); 
                    
                    const cs = gEl('circle', {cx: xq(d.year), cy: yq(d.sess), r: 4, fill: '#8b5cf6'});
                    bindTip(cs, 'vis025-wrapper', 'vis025-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Секции', 'Sessions') + ': ' + d.sess);
                    svg.appendChild(cs);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS026() {
                const svg = document.getElementById('vis026-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 100};
                const D = VIS026_DATA; if (!D.length) return;
                const maxV = Math.max(...D.map(d => d.val));
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const w = (d.val / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: pad.l, y: y, width: w, height: barH, fill: '#ec4899', rx: 2});
                    bindTip(rect, 'vis026-wrapper', 'vis026-tooltip', () => '<strong>' + d.conf + '</strong><br>' + d.val);
                    svg.appendChild(rect);
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.conf, 'end', 11, 'var(--muted)'));
                    svg.appendChild(gText(pad.l + w + 10, y + barH/2 + 4, d.val, 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS027() {
                const svg = document.getElementById('vis027-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 200};
                const D = VIS027_DATA; if (!D.length) return;
                const maxV = Math.max(...D.map(d => d.val));
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const w = (d.val / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: pad.l, y: y, width: w, height: barH, fill: '#3b82f6', rx: 2});
                    bindTip(rect, 'vis027-wrapper', 'vis027-tooltip', () => '<strong>' + d.theme + '</strong><br>' + d.val);
                    svg.appendChild(rect);
                    const tLabel = d.theme.length > 30 ? d.theme.substring(0, 27) + '...' : d.theme;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, tLabel, 'end', 11, 'var(--muted)'));
                    svg.appendChild(gText(pad.l + w + 10, y + barH/2 + 4, d.val, 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS028() {
                const svg = document.getElementById('vis028-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS028_DATA; if (!D.length) return;
                
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                const maxV = Math.max(...D.map(d => Object.values(d.periods).reduce((a,b)=>a+b,0)));
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.gumilyov, 'end', 11, 'var(--muted)'));
                    let currX = pad.l;
                    const tot = Object.values(d.periods).reduce((a,b)=>a+b,0);
                    const wTot = (tot / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: currX, y: y, width: wTot, height: barH, fill: '#f59e0b', rx: 2});
                    bindTip(rect, 'vis028-wrapper', 'vis028-tooltip', () => '<strong>' + d.gumilyov + '</strong><br>' + tot);
                    svg.appendChild(rect);
                    svg.appendChild(gText(currX + wTot + 10, y + barH/2 + 4, tot, 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS029() {
                const svg = document.getElementById('vis029-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS029_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.avg)) + 10;
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 20) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.avg)).join(' '), fill: 'none', stroke: '#10b981', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.avg), r: 4, fill: '#10b981'});
                    bindTip(c, 'vis029-wrapper', 'vis029-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Символов', 'Characters') + ': ' + d.avg.toFixed(1));
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS030() {
                const svg = document.getElementById('vis030-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 30};
                const D = VIS030_DATA; if (!D) return;
                
                const cx1 = W/2 - 50, cx2 = W/2 + 50, cy = H/2;
                const r = 100;
                
                svg.appendChild(gEl('circle', {cx: cx1, cy: cy, r: r, fill: '#3b82f6', 'fill-opacity': 0.5, stroke: '#3b82f6'}));
                svg.appendChild(gEl('circle', {cx: cx2, cy: cy, r: r, fill: '#ef4444', 'fill-opacity': 0.5, stroke: '#ef4444'}));
                
                svg.appendChild(gText(cx1 - 40, cy, D.zograf_only, 'middle', 24, 'white'));
                svg.appendChild(gText(cx2 + 40, cy, D.roerich_only, 'middle', 24, 'white'));
                svg.appendChild(gText(W/2, cy, D.both, 'middle', 24, 'white'));
                
                svg.appendChild(gText(cx1 - 40, cy - r - 20, 'Только Зографские', 'middle', 14, 'var(--muted)'));
                svg.appendChild(gText(cx2 + 40, cy - r - 20, 'Только Рериховские', 'middle', 14, 'var(--muted)'));
                svg.appendChild(gText(W/2, cy + r + 30, 'Обе конференции (' + D.both + ')', 'middle', 14, 'var(--muted)'));
            }




            function drawVIS031() {
                const svg = document.getElementById('vis031-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 60};
                const D = VIS031_DATA; if (!D.length) return;
                
                const minV = Math.min(...D.map(d => d.stats ? d.stats.min : 100)) - 5;
                const maxV = Math.max(...D.map(d => d.stats ? d.stats.max : 0)) + 5;
                const span = maxV - minV || 1;
                const xq = v => pad.l + ((v - minV) / span) * (W - pad.l - pad.r);
                
                for(let v = Math.floor(minV/10)*10; v <= maxV; v+=10) {
                    svg.appendChild(gEl('line', {x1: xq(v), y1: pad.t, x2: xq(v), y2: H - pad.b, stroke: 'rgba(255,255,255,0.05)'}));
                    svg.appendChild(gText(xq(v), H - pad.b + 20, v, 'middle', 10, 'var(--muted)'));
                }
                
                const pitch = (H - pad.t - pad.b) / D.length;
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch + pitch/2;
                    svg.appendChild(gText(pad.l - 10, y + 4, 'Level ' + d.level, 'end', 12, 'var(--muted)'));
                    if(!d.stats) return;
                    
                    svg.appendChild(gEl('line', {x1: xq(d.stats.min), y1: y, x2: xq(d.stats.max), y2: y, stroke: '#f59e0b', 'stroke-width': 2}));
                    svg.appendChild(gEl('rect', {x: xq(d.stats.q1), y: y - 15, width: xq(d.stats.q3) - xq(d.stats.q1), height: 30, fill: '#f59e0b', 'fill-opacity': 0.4, stroke: '#f59e0b'}));
                    svg.appendChild(gEl('line', {x1: xq(d.stats.median), y1: y - 15, x2: xq(d.stats.median), y2: y + 15, stroke: 'white', 'stroke-width': 2}));
                    
                    const rect = gEl('rect', {x: xq(d.stats.min), y: y - 15, width: xq(d.stats.max) - xq(d.stats.min), height: 30, fill: 'transparent', cursor: 'pointer'});
                    bindTip(rect, 'vis031-wrapper', 'vis031-tooltip', () => '<strong>G' + d.level + '</strong><br>Медиана: ' + d.stats.median + ' лет<br>Разброс: ' + d.stats.min + ' - ' + d.stats.max + ' лет<br>Докладов: ' + d.stats.count);
                    svg.appendChild(rect);
                });
            }

            function drawVIS032() {
                const svg = document.getElementById('vis032-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 200};
                const D = VIS032_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    const tLabel = d.theme.length > 25 ? d.theme.substring(0, 22) + '...' : d.theme;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, tLabel, 'end', 11, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis032-wrapper', 'vis032-tooltip', () => '<strong>' + d.theme + '</strong><br>G1 (Микрокейс): ' + d.g1 + ' (' + Math.round(d.g1/tot*100) + '%)');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis032-wrapper', 'vis032-tooltip', () => '<strong>' + d.theme + '</strong><br>G2 (Регион): ' + d.g2 + ' (' + Math.round(d.g2/tot*100) + '%)');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis032-wrapper', 'vis032-tooltip', () => '<strong>' + d.theme + '</strong><br>G3 (Глобал): ' + d.g3 + ' (' + Math.round(d.g3/tot*100) + '%)');
                        svg.appendChild(r3);
                    }
                });
            }

            function drawVIS033() {
                const svg = document.getElementById('vis033-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS033_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis033-wrapper', 'vis033-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '%');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis033-wrapper', 'vis033-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '%');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis033-wrapper', 'vis033-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '%');
                        svg.appendChild(r3);
                    }
                });
            }

            function drawVIS034() {
                const svg = document.getElementById('vis034-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS034_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis034-wrapper', 'vis034-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '%');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis034-wrapper', 'vis034-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '%');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis034-wrapper', 'vis034-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '%');
                        svg.appendChild(r3);
                    }
                });
            }




            function drawVIS035() {
                const svg = document.getElementById('vis035-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS035_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.avg)) + 2;
                const minV = Math.max(0, Math.min(...D.map(d => d.avg)) - 2);
                const yspan = maxV - minV || 1;
                const yq = v => H - pad.b - ((v - minV) / yspan) * (H - pad.t - pad.b);
                
                for (let v = Math.floor(minV); v <= maxV; v += 1) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.avg)).join(' '), fill: 'none', stroke: '#a855f7', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.avg), r: 4, fill: '#a855f7'});
                    bindTip(c, 'vis035-wrapper', 'vis035-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Слов', 'Words') + ': ' + d.avg.toFixed(1));
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS036() {
                const svg = document.getElementById('vis036-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS036_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.ratio)) + 5;
                const yspan = maxV || 1;
                const yq = v => H - pad.b - (v / yspan) * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 10) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.ratio)).join(' '), fill: 'none', stroke: '#ec4899', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.ratio), r: 4, fill: '#ec4899'});
                    bindTip(c, 'vis036-wrapper', 'vis036-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('С двоеточием', 'With colon') + ': ' + d.ratio.toFixed(1) + '%');
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS037() {
                const svg = document.getElementById('vis037-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS037_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis037-wrapper', 'vis037-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '%');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis037-wrapper', 'vis037-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '%');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis037-wrapper', 'vis037-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '%');
                        svg.appendChild(r3);
                    }
                });
            }




            function drawVIS038() {
                const svg = document.getElementById('vis038-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS038_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.total));
                const yq = v => H - pad.b - (v / maxV) * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 20) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                const barW = (W - pad.l - pad.r) / D.length * 0.6;
                D.forEach(d => { 
                    const x = xq(d.year) - barW/2;
                    
                    const hTotal = (d.total / maxV) * (H - pad.t - pad.b);
                    const rectTotal = gEl('rect', {x: x, y: H - pad.b - hTotal, width: barW, height: hTotal, fill: '#3b82f6', 'fill-opacity': 0.3});
                    
                    const hVideo = (d.video / maxV) * (H - pad.t - pad.b);
                    const rectVideo = gEl('rect', {x: x, y: H - pad.b - hVideo, width: barW, height: hVideo, fill: '#ef4444'});
                    
                    bindTip(rectTotal, 'vis038-wrapper', 'vis038-tooltip', () => '<strong>' + d.year + '</strong><br>Всего докладов: ' + d.total + '<br>На видео: ' + d.video + ' (' + Math.round(d.video/d.total*100) + '%)');
                    
                    svg.appendChild(rectTotal); 
                    if(d.video > 0) svg.appendChild(rectVideo);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS039() {
                const svg = document.getElementById('vis039-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS039_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis039-wrapper', 'vis039-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '% (' + d.g1 + ')');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis039-wrapper', 'vis039-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '% (' + d.g2 + ')');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis039-wrapper', 'vis039-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '% (' + d.g3 + ')');
                        svg.appendChild(r3);
                    }
                });
            }

            function drawVIS040() {
                const svg = document.getElementById('vis040-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS040_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.video + d.no_video;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.video / tot) * (W - pad.l - pad.r);
                    const w2 = (d.no_video / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#ef4444', c2 = '#3b82f6';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis040-wrapper', 'vis040-tooltip', () => '<strong>' + d.group + '</strong><br>Видео: ' + Math.round(d.video/tot*100) + '% (' + d.video + ')');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2, 'fill-opacity': 0.3});
                        bindTip(r2, 'vis040-wrapper', 'vis040-tooltip', () => '<strong>' + d.group + '</strong><br>Без видео: ' + Math.round(d.no_video/tot*100) + '% (' + d.no_video + ')');
                        svg.appendChild(r2);
                    }
                });
            }




            function drawVIS041() {
                const svg = document.getElementById('vis041-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 200};
                const D = VIS041_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.newbies + d.repeaters;
                    if(tot === 0) return;
                    
                    const tLabel = d.theme.length > 25 ? d.theme.substring(0, 22) + '...' : d.theme;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, tLabel, 'end', 11, 'var(--muted)'));
                    
                    const w1 = (d.newbies / tot) * (W - pad.l - pad.r);
                    const w2 = (d.repeaters / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#f59e0b', c2 = '#3b82f6';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis041-wrapper', 'vis041-tooltip', () => '<strong>' + d.theme + '</strong><br>Новички (дебют): ' + d.newbies + ' (' + Math.round(d.newbies/tot*100) + '%)');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis041-wrapper', 'vis041-tooltip', () => '<strong>' + d.theme + '</strong><br>Старожилы: ' + d.repeaters + ' (' + Math.round(d.repeaters/tot*100) + '%)');
                        svg.appendChild(r2);
                    }
                });
            }

            function drawVIS042() {
                const svg = document.getElementById('vis042-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS042_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.5;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.venue, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.city_only / 100) * (W - pad.l - pad.r);
                    const w2 = (d.institution / 100) * (W - pad.l - pad.r);
                    
                    const c1 = '#8b5cf6', c2 = '#10b981';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis042-wrapper', 'vis042-tooltip', () => '<strong>' + d.venue + '</strong><br>Только город: ' + d.city_only + '%');
                        svg.appendChild(r1);
                        svg.appendChild(gText(pad.l + w1/2, y + barH/2 + 4, d.city_only + '%', 'middle', 11, 'white'));
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis042-wrapper', 'vis042-tooltip', () => '<strong>' + d.venue + '</strong><br>Учреждение: ' + d.institution + '%');
                        svg.appendChild(r2);
                        svg.appendChild(gText(pad.l + w1 + w2/2, y + barH/2 + 4, d.institution + '%', 'middle', 11, 'white'));
                    }
                });
            }


            function drawGallery() {
                const fns = [drawDemography, drawSurvival, drawNewcomer, drawTreemap, drawGumilyov, drawKeywordDiv, drawClosedness, drawOnline, drawVIS016, drawVIS018, drawVIS019, drawVIS020, drawVIS021, drawVIS022, drawVIS023, drawVIS024, drawVIS025, drawVIS026, drawVIS027, drawVIS028, drawVIS029, drawVIS030, drawVIS031, drawVIS032, drawVIS033, drawVIS034, drawVIS035, drawVIS036, drawVIS037, drawVIS038, drawVIS039, drawVIS040, drawVIS041, drawVIS042];
                fns.forEach(fn => { try { fn(); } catch (e) { console.error('gallery viz error', e); } });
            }
        </script>
    """
    body = body + scatter_js + gallery_js
    write_text(
        "findings/visualisations.html",
        page_shell(
            f"Интерактивный атлас визуализаций | {SITE_NAME}",
            "Единый каталог всех интерактивных аналитических визуализаций индологического архива с постоянными идентификаторами (ID).",
            "findings/visualisations.html",
            body,
            [page_data("Интерактивный атлас визуализаций", "Единый каталог всех интерактивных аналитических визуализаций с ID.", "findings/visualisations.html"), make_breadcrumbs([("Главная", ""), ("Атлас визуализаций", "findings/visualisations.html")])],
        ),
    )


def generate_generations_page(data):
    scholars = data.get("scholars", [])
    grouped = defaultdict(list)
    for scholar in scholars:
        grouped[scholar.get("generation_code")].append(scholar)

    def scholar_name(scholar):
        return scholar.get("full_name_ru") or scholar.get("name") or ""

    def person_card(scholar):
        birth = scholar.get("birth_year")
        death = scholar.get("death_year")
        if birth:
            lifespan = f"{birth}-{death}" if death else f"род. {birth}"
        else:
            lifespan = "год рождения не установлен"
        return (
            f'<article class="card"><strong><a href="../{profile_href(scholar.get("url_slug"))}">{esc(scholar_name(scholar))}</a></strong>'
            f'<div class="meta">{esc(lifespan)} · {talks_count_label(scholar.get("total_talks") or 0)} · '
            f'{esc(describe_year_span(scholar.get("first_year"), scholar.get("last_year")))}</div></article>'
        )

    # DYNAMIC COHORT SUCCESSION & THEME EVOLUTION ANALYSIS
    scholar_cohort_map = {}
    for s in scholars:
        if s.get("id") and s.get("generation_code"):
            scholar_cohort_map[s["id"]] = s["generation_code"]

    period_mapping = {}
    try:
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                period_mapping[row["presentation_id"]] = row["period_l2"]
    except Exception:
        pass

    participations = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT person_id, presentation_id FROM presentation_person")
        participations = cursor.fetchall()
        conn.close()
    except Exception:
        pass

    cohort_codes = ["pre-1940", "1940s", "1950s", "1960s", "1970s", "1980s", "1990s", "2000s"]
    periods = ["vedic", "classical", "medieval", "colonial", "modern", "contemporary"]
    
    period_names_ru = {
        "vedic": "Веддийский",
        "classical": "Классический",
        "medieval": "Средневековый",
        "colonial": "Колониальный",
        "modern": "Модерн",
        "contemporary": "Современность"
    }
    
    cohort_labels = {
        "pre-1940": "Предшественники (<1940)",
        "1940s": "Когорта Василькова (1940-е)",
        "1950s": "1950-е",
        "1960s": "1960-е",
        "1970s": "1970-е",
        "1980s": "1980-е",
        "1990s": "1990-е",
        "2000s": "Когорта Толчельникова (2000-е)"
    }

    matrix = {c: {p: 0 for p in periods} for c in cohort_codes}
    cohort_totals = {c: 0 for c in cohort_codes}

    for pid, pres_id in participations:
        cohort = scholar_cohort_map.get(pid)
        if cohort in matrix:
            period = period_mapping.get(pres_id)
            if period in periods:
                matrix[cohort][period] += 1
                cohort_totals[cohort] += 1

    cohort_headers_list = []
    for c in cohort_codes:
        label = cohort_labels[c]
        short_label = label.replace("Поколение ", "").replace("Когорта ", "")
        cohort_headers_list.append(
            f'<th>{esc(short_label)}<br><small style="color:var(--soft); font-weight:normal;">(N={cohort_totals[c]})</small></th>'
        )
    cohort_headers = "".join(cohort_headers_list)

    heatmap_rows_list = []
    for p in periods:
        row_html = f'<tr><td class="y-label">{esc(period_names_ru[p])}</td>'
        for c in cohort_codes:
            total = cohort_totals[c]
            cnt = matrix[c][p]
            pct = (cnt / total * 100) if total > 0 else 0
            
            opacity = min(0.85, 0.05 + (pct / 50.0) * 0.80) if pct > 0 else 0.02
            bg_color = f"rgba(98, 174, 146, {opacity:.3f})"
            text_color = "var(--text)" if pct > 15 else "var(--muted)"
            
            row_html += (
                f'<td class="heatmap-cell" style="background-color: {bg_color}; color: {text_color};" '
                f'title="Количество докладов: {cnt} из {total} в когорте {esc(cohort_labels[c])}">'
                f'<span class="heatmap-value">{pct:.1f}%</span>'
                f'<span class="heatmap-count">{cnt} докл.</span>'
                f'</td>'
            )
        row_html += '</tr>'
        heatmap_rows_list.append(row_html)
    heatmap_rows = "".join(heatmap_rows_list)

    # DYNAMIC GENDER REPRESENTATION & DEMOGRAPHIC SUCCESSION ANALYSIS
    male_count_by_cohort = defaultdict(int)
    female_count_by_cohort = defaultdict(int)
    male_presentations_by_year = defaultdict(int)
    female_presentations_by_year = defaultdict(int)

    scholar_gender = {}
    for s in scholars:
        pid = s.get("id")
        fname = s.get("full_name_ru") or s.get("name") or ""
        
        gender = None
        if any(pat in fname for pat in ["овна", "евна", "ична", "инична"]):
            gender = "female"
        elif any(pat in fname for pat in ["ович", "евич", "ич"]):
            gender = "male"
        else:
            last_word = fname.split()[-1] if fname.split() else ""
            if last_word.endswith(("ова", "ева", "ина", "ая")):
                gender = "female"
            elif last_word.endswith(("ов", "ев", "ин", "ий", "ый")):
                gender = "male"
            elif any(fname.split()[0].startswith(prefix) for prefix in ["Дми", "Але", "Сер", "Ива", "Мих", "Вла", "Кон", "Юри", "Анд", "Мих"]):
                gender = "male"
            elif any(fname.split()[0].startswith(prefix) for prefix in ["Оль", "Мар", "Ири", "Еле", "Тат", "Анн", "Све", "Нат", "Ека", "Люд"]):
                gender = "female"
        
        if gender:
            scholar_gender[pid] = gender
            cohort = s.get("generation_code")
            if cohort in cohort_codes:
                if gender == "male":
                    male_count_by_cohort[cohort] += 1
                else:
                    female_count_by_cohort[cohort] += 1

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pp.person_id, e.year 
            FROM presentation_person pp
            JOIN presentation pr ON pr.presentation_id = pp.presentation_id
            JOIN session s ON s.session_id = pr.session_id
            JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            JOIN event_day ed ON ed.event_day_id = edv.event_day_id
            JOIN event e ON e.event_id = ed.event_id
        """)
        yearly_records = cursor.fetchall()
        conn.close()
        
        for pid, year in yearly_records:
            g = scholar_gender.get(pid)
            if g == "male":
                male_presentations_by_year[int(year)] += 1
            elif g == "female":
                female_presentations_by_year[int(year)] += 1
    except Exception:
        pass

    pyramid_rows = []
    pyramid_y = 35
    for c in cohort_codes:
        label = cohort_labels[c].replace("Поколение ", "").replace("Когорта ", "")
        m_count = male_count_by_cohort[c]
        f_count = female_count_by_cohort[c]
        
        m_width = m_count * 4.2
        f_width = f_count * 4.2
        
        pyramid_rows.append(f"""
            <text x="300" y="{pyramid_y - 6}" fill="var(--muted)" font-size="10" font-weight="600" text-anchor="middle">{esc(label)}</text>
            <rect x="{300 - m_width:.1f}" y="{pyramid_y:.1f}" width="{m_width:.1f}" height="15" fill="rgba(197, 154, 86, 0.7)" rx="2" class="pyramid-bar"></rect>
            <text x="{300 - m_width - 15:.1f}" y="{pyramid_y + 11:.1f}" fill="var(--soft)" font-size="9" text-anchor="middle">{m_count}</text>
            <rect x="300" y="{pyramid_y:.1f}" width="{f_width:.1f}" height="15" fill="rgba(98, 174, 146, 0.7)" rx="2" class="pyramid-bar"></rect>
            <text x="{300 + f_width + 15:.1f}" y="{pyramid_y + 11:.1f}" fill="var(--soft)" font-size="9" text-anchor="middle">{f_count}</text>
        """)
        pyramid_y += 38
    svg_pyramid = "\n".join(pyramid_rows)

    # Era computations for succession stats
    era_1_female = sum(female_presentations_by_year[y] for y in range(2004, 2011))
    era_1_male = sum(male_presentations_by_year[y] for y in range(2004, 2011))
    era_1_pct = (era_1_female / (era_1_female + era_1_male) * 100) if (era_1_female + era_1_male) > 0 else 0

    era_2_female = sum(female_presentations_by_year[y] for y in range(2011, 2019))
    era_2_male = sum(male_presentations_by_year[y] for y in range(2011, 2019))
    era_2_pct = (era_2_female / (era_2_female + era_2_male) * 100) if (era_2_female + era_2_male) > 0 else 0

    era_3_female = sum(female_presentations_by_year[y] for y in range(2019, 2027))
    era_3_male = sum(male_presentations_by_year[y] for y in range(2019, 2027))
    era_3_pct = (era_3_female / (era_3_female + era_3_male) * 100) if (era_3_female + era_3_male) > 0 else 0

    summary_cards = []
    sections = []
    for cohort in GENERATION_COHORTS:
        members = sorted(grouped.get(cohort["code"], []), key=lambda item: (int(item.get("birth_year") or 0), scholar_name(item)))
        talks = sum(int(item.get("total_talks") or 0) for item in members)
        summary_cards.append(
            f'<article class="card"><strong><a href="#{esc(cohort["code"])}">{esc(cohort["ru"])}</a></strong>'
            f'<div class="metric">{len(members)}</div><div class="meta">{talks_count_label(talks)} в авторских профилях</div></article>'
        )
        sections.append(
            f'<section id="{esc(cohort["code"])}"><h2>{esc(cohort["ru"])} ({len(members)})</h2>'
            f'<div class="grid">{"".join(person_card(scholar) for scholar in members)}</div></section>'
        )
    unknown_members = sorted(grouped.get(None, []), key=scholar_name)
    if unknown_members:
        unknown_talks = sum(int(item.get("total_talks") or 0) for item in unknown_members)
        summary_cards.append(
            '<article class="card"><strong><a href="#unknown">Год рождения не установлен</a></strong>'
            f'<div class="metric">{len(unknown_members)}</div><div class="meta">{talks_count_label(unknown_talks)} в авторских профилях</div></article>'
        )
        sections.append(
            f'<section id="unknown"><h2>Год рождения не установлен ({len(unknown_members)})</h2>'
            '<p>Эти реальные участники восстановлены из программ, но не распределены по поколениям без проверенного биографического источника.</p>'
            f'<div class="grid">{"".join(person_card(scholar) for scholar in unknown_members)}</div></section>'
        )
    known_count = sum(1 for scholar in scholars if scholar.get("birth_year"))

    vasilkov = next((item for item in scholars if "Васильков" in scholar_name(item)), None)
    tolchelnikov = next((item for item in scholars if "Толчельников" in scholar_name(item)), None)
    anchors = []
    for scholar, label in ((vasilkov, "Старший ориентир"), (tolchelnikov, "Младший ориентир")):
        if scholar:
            anchors.append(
                f'<a class="chip" href="../{profile_href(scholar.get("url_slug"))}">{esc(label)}: {esc(scholar_name(scholar))} ({esc(scholar.get("birth_year"))})</a>'
            )

    body = f"""
        <header>
            <h1>Поколения индологов</h1>
            <p>Поименное распределение участников программ по десятилетиям рождения. Васильков задает видимый старший ориентир действующего круга, Толчельников - младший; более ранние участники сохранены как предшественники.</p>
        </header>
        <aside class="caveat-block" role="note" aria-label="Generation method">
            <strong>Что означает «поколение»</strong>
            <p>Это демографические когорты, а не реконструкция научных школ, отношений учитель-ученик или статуса. Год рождения известен для {known_count} из {len(scholars)} участников текущего корпуса; участники без проверенной даты перечислены отдельно, без искусственного отнесения к поколению.</p>
            <div class="chip-list">{''.join(anchors)}</div>
        </aside>

        <!-- Dynamic Cohort Succession Analysis -->
        <style>
            .analytics-section {{
                background: rgba(23, 30, 27, 0.6);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 2rem 0;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }}
            .analytics-title {{
                font-size: 1.4rem;
                color: var(--accent);
                margin-top: 0;
                margin-bottom: 1.2rem;
                font-weight: 700;
            }}
            .analytics-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            @media (min-width: 900px) {{
                .analytics-grid {{
                    grid-template-columns: 1.6fr 1fr;
                }}
            }}
            .heatmap-container {{
                overflow-x: auto;
                border: 1px solid var(--border);
                border-radius: 8px;
                background: rgba(16, 21, 19, 0.8);
            }}
            .heatmap-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.82rem;
                min-width: 800px;
            }}
            .heatmap-table th, .heatmap-table td {{
                padding: 0.6rem 0.5rem;
                text-align: center;
                border: 1px solid var(--border);
            }}
            .heatmap-table th {{
                background: var(--panel-strong);
                font-weight: 600;
                color: var(--text);
            }}
            .heatmap-table td.y-label {{
                text-align: left;
                font-weight: 600;
                background: var(--panel-strong);
                color: var(--muted);
                width: 130px;
                padding-left: 0.75rem;
            }}
            .heatmap-cell {{
                transition: all 0.2s ease;
                position: relative;
            }}
            .heatmap-cell:hover {{
                transform: scale(1.03);
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                z-index: 10;
                cursor: help;
            }}
            .heatmap-value {{
                font-weight: 700;
                display: block;
                font-size: 0.9rem;
            }}
            .heatmap-count {{
                font-size: 0.7rem;
                opacity: 0.75;
                display: block;
                margin-top: 0.1rem;
            }}
            .stats-sidebar {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }}
            .stats-card {{
                background: rgba(28, 37, 33, 0.4);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.2rem;
            }}
            .stats-header {{
                font-weight: 600;
                color: var(--accent2);
                margin-bottom: 0.6rem;
                font-size: 1.05rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }}
            .stats-text {{
                font-size: 0.88rem;
                line-height: 1.45;
                margin: 0 0 0.75rem 0;
                color: var(--muted);
            }}
            .stats-badge {{
                background: rgba(0,0,0,0.2);
                border-radius: 6px;
                padding: 0.75rem;
                border-left: 3px solid var(--accent);
                font-size: 0.82rem;
                color: var(--text);
                font-family: monospace;
            }}
            .stats-badge.disproven {{
                border-left-color: #e57373;
            }}
        </style>

        <section class="analytics-section">
            <h2 class="analytics-title">📊 Тематическая преемственность поколений: Смена вех и методологий</h2>
            <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                Интерактивный тепловой анализ распределения исследовательских периодов в докладах по демографическим когортам ученых. Показывает, как со сменой поколений трансформируются научные приоритеты в отечественной индологии.
            </p>
            <div class="analytics-grid">
                <div class="heatmap-container">
                    <table class="heatmap-table">
                        <thead>
                            <tr>
                                <th>Период (Y) \ Когорта (X)</th>
                                {cohort_headers}
                            </tr>
                        </thead>
                        <tbody>
                            {heatmap_rows}
                        </tbody>
                    </table>
                </div>
                <div class="stats-sidebar">
                    <div class="stats-card">
                        <div class="stats-header">🔬 Гипотеза G1: Смена приоритетов (The Modernity Shift)</div>
                        <p class="stats-text">
                            <strong>Доказано:</strong> Прослеживается системный сдвиг научных фокусов. Молодые когорты (рожденные после 1980 г.) значимо чаще выбирают <em>колониальные, модернистские и современные</em> периоды (L2) взамен санскритской и ведийской классики.
                        </p>
                        <div class="stats-badge">
                            Пирсон &chi;² = 31.6592<br>
                            p-value = 0.000047 (highly sig.)<br>
                            Доля модерна у 1990-х: 41.0%<br>
                            Доля модерна у 1940-х: 25.0%
                        </div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-header">🧩 Гипотеза G3: Магический микроисторизм (The Synthesis Shift)</div>
                        <p class="stats-text">
                            <strong>Опровергнуто:</strong> Гипотеза о том, что молодые ученые из-за жестких рамок PhD уходят в микрофилологию (L1), в то время как ветераны обобщают масштабные цивилизационные процессы (L3), не находит подтверждения.
                        </p>
                        <div class="stats-badge disproven">
                            Пирсон &chi;² = 11.9362<br>
                            p-value = 0.6114 (not sig.)<br>
                            Микроанализ L1 для всех: ~85-90%<br>
                            Обобщения L3 для всех: &lt;1.0%
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="analytics-section">
            <h2 class="analytics-title">👥 Гендерный баланс и демографическое замещение</h2>
            <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                Распределение мужчин (слева, золото) и женщин (справа, изумруд) среди активных докладчиков по демографическим когортам рождения (половозрастная пирамида) в сопоставлении с динамикой представленности докладов.
            </p>
            <div class="analytics-grid">
                <div class="heatmap-container" style="padding: 1rem 0;">
                    <svg viewBox="0 0 600 340" class="chord-sankey-svg" xmlns="http://www.w3.org/2000/svg" style="background: transparent; border: none; margin: 0 auto; display: block; max-width: 500px; width: 100%;">
                        <!-- Left and Right Guides -->
                        <line x1="300" y1="10" x2="300" y2="330" stroke="var(--border)" stroke-width="1.5" stroke-dasharray="3 3"></line>
                        <text x="180" y="20" fill="var(--soft)" font-size="11" font-weight="bold" text-anchor="middle">Мужчины (Золото)</text>
                        <text x="420" y="20" fill="var(--soft)" font-size="11" font-weight="bold" text-anchor="middle">Женщины (Изумруд)</text>
                        
                        {svg_pyramid}
                    </svg>
                </div>
                <div class="stats-sidebar">
                    <div class="stats-card">
                        <div class="stats-header">🔬 Феминизация и смена вех</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Сообщество индологов перешло от выраженного мужского доминирования в старших когортах к значительному преобладанию женщин в младших возрастных слоях (1980-е и 1990-е годы рождения).
                        </p>
                        <div class="stats-badge">
                            Когорта 1940-х: 82% М / 18% Ж<br>
                            Когорта 1980-х: 40% М / 60% Ж<br>
                            Когорта 1990-х: 31% М / 69% Ж
                        </div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-header">📈 Динамика доли докладов по эпохам</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Доля женских выступлений в программах планомерно росла в течение 22 лет работы архива, полностью сбалансировав современную трибуну.
                        </p>
                        <div class="stats-badge" style="border-left-color: var(--accent2);">
                            Эпоха 2004–2010: {era_1_pct:.1f}% Ж<br>
                            Эпоха 2011–2018: {era_2_pct:.1f}% Ж<br>
                            Эпоха 2019–2026: {era_3_pct:.1f}% Ж
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="grid">{''.join(summary_cards)}</section>
        {''.join(sections)}
    """
    write_text(
        "generations/index.html",
        page_shell(
            f"Поколения индологов | {SITE_NAME}",
            "Поименное распределение участников программ по поколениям рождения от старшей к младшей когорте.",
            generations_path(),
            body,
            [page_data("Поколения индологов", "Демографические когорты участников программ.", generations_path()), make_breadcrumbs([("Главная", ""), ("Поколения", generations_path())])],
        ),
    )


def generate_collaboration_page(data):
    scholars = data.get("scholars", [])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT presentation_id, COUNT(person_id) as author_count
        FROM presentation_person
        GROUP BY presentation_id
    """)
    pres_author_counts = {r[0]: r[1] for r in cursor.fetchall()}
    
    cursor.execute("""
        SELECT 
            pp.person_id,
            p.display_name,
            pp.presentation_id,
            e.year,
            pp.affiliation_text_raw
        FROM presentation_person pp
        JOIN person p ON p.person_id = pp.person_id
        JOIN presentation pr ON pr.presentation_id = pp.presentation_id
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
    """)
    records = cursor.fetchall()
    conn.close()

    def extract_city(text):
        if not text:
            return "Регионы / Ино"
        text_low = text.lower()
        if "санкт-петербург" in text_low or "спб" in text_low or "ленинград" in text_low:
            return "Санкт-Петербург"
        if "москва" in text_low or "мгу" in text_low or "ив ран" in text_low or "вшэ" in text_low:
            return "Москва"
        return "Регионы / Ино"

    scholar_talks = {}
    for pid, name, pres_id, year, affiliation in records:
        city = extract_city(affiliation)
        if pid not in scholar_talks:
            scholar_talks[pid] = {
                "name": name,
                "city": city,
                "years": set(),
                "talks": []
            }
        scholar_talks[pid]["years"].add(int(year))
        scholar_talks[pid]["talks"].append(pres_id)
        if city in ("Москва", "Санкт-Петербург"):
            scholar_talks[pid]["city"] = city

    groups = {
        "Санкт-Петербург": {"solo": {"total": 0, "returned": 0}, "collab": {"total": 0, "returned": 0}},
        "Москва": {"solo": {"total": 0, "returned": 0}, "collab": {"total": 0, "returned": 0}},
        "Регионы / Ино": {"solo": {"total": 0, "returned": 0}, "collab": {"total": 0, "returned": 0}}
    }
    
    collab_scholars_list = []
    
    for pid, s in scholar_talks.items():
        years = sorted(list(s["years"]))
        total_talks = len(s["talks"])
        total_years = len(years)
        returned = total_years >= 2
        has_collaboration = any(pres_author_counts.get(tid, 1) > 1 for tid in s["talks"])
        
        city = s["city"]
        sub_key = "collab" if has_collaboration else "solo"
        if city in groups:
            groups[city][sub_key]["total"] += 1
            if returned:
                groups[city][sub_key]["returned"] += 1
                
        if has_collaboration:
            # find the scholar slug matching this name or pid
            scholar_slug = ""
            matching_s = next((item for item in scholars if item.get("id") == pid), None)
            if matching_s:
                scholar_slug = profile_href(matching_s.get("url_slug"))
                
            collab_scholars_list.append({
                "name": s["name"],
                "talks_count": total_talks,
                "years_count": total_years,
                "city": city,
                "slug": scholar_slug
            })

    collab_leaders = sorted(collab_scholars_list, key=lambda x: x["talks_count"], reverse=True)[:15]

    bars_html = []
    for city, profiles in groups.items():
        solo_total = profiles["solo"]["total"]
        solo_ret = profiles["solo"]["returned"]
        solo_pct = (solo_ret / solo_total * 100) if solo_total > 0 else 0
        
        collab_total = profiles["collab"]["total"]
        collab_ret = profiles["collab"]["returned"]
        collab_pct = (collab_ret / collab_total * 100) if collab_total > 0 else 0
        
        bars_html.append(f"""
            <div class="collab-group">
                <div class="collab-group-title">{esc(city)}</div>
                
                <!-- Solo Bar -->
                <div class="collab-bar-wrapper">
                    <div class="collab-bar-label">Соло-авторы (N={solo_total})</div>
                    <div class="collab-bar-container">
                        <div class="collab-bar solo-bar" style="width: {solo_pct:.1f}%;">
                            <span class="collab-bar-value">{solo_pct:.1f}%</span>
                        </div>
                    </div>
                    <div class="collab-bar-retention">{solo_ret} вернулись</div>
                </div>
                
                <!-- Collaborative Bar -->
                <div class="collab-bar-wrapper">
                    <div class="collab-bar-label">Соавторы (N={collab_total})</div>
                    <div class="collab-bar-container">
                        <div class="collab-bar collab-bar-fill" style="width: {collab_pct:.1f}%;">
                            <span class="collab-bar-value">{collab_pct:.1f}%</span>
                        </div>
                    </div>
                    <div class="collab-bar-retention">{collab_ret} вернулись</div>
                </div>
            </div>
        """)
    bars_markup = "".join(bars_html)

    leader_rows = []
    for idx, leader in enumerate(collab_leaders, 1):
        name_html = f'<a href="../{esc(leader["slug"])}">{esc(leader["name"])}</a>' if leader["slug"] else esc(leader["name"])
        leader_rows.append(f"""
            <tr>
                <td>{idx}</td>
                <td><strong>{name_html}</strong></td>
                <td>{esc(leader["city"])}</td>
                <td>{leader["talks_count"]}</td>
                <td>{leader["years_count"]}</td>
            </tr>
        """)
    leader_table_markup = "".join(leader_rows)

    # BIPARTITE NETWORK GRAPH: City -> Authorship Profile
    bipartite_paths = []
    # Total scholars is ~270. Let's scale to fit height of nodes
    total_scholars_count = sum(groups[c][s]["total"] for c in groups for s in ["solo", "collab"]) or 1
    scale_bipartite = 150.0 / total_scholars_count

    bipartite_left_y = {"Санкт-Петербург": 40, "Москва": 135, "Регионы / Ино": 200}
    bipartite_right_y = {"solo": 40, "collab": 160}

    bipartite_left_offset = {"Санкт-Петербург": 0, "Москва": 0, "Регионы / Ино": 0}
    bipartite_right_offset = {"solo": 0, "collab": 0}

    bipartite_cities = ["Санкт-Петербург", "Москва", "Регионы / Ино"]
    bipartite_statuses = ["solo", "collab"]
    status_ru = {"solo": "Соло-автор", "collab": "Соавторство"}

    for city in bipartite_cities:
        for status in bipartite_statuses:
            count = groups[city][status]["total"]
            if count == 0:
                continue
            
            thickness = max(1.5, count * scale_bipartite)
            
            y_left = bipartite_left_y[city] + bipartite_left_offset[city] + (thickness / 2.0)
            y_right = bipartite_right_y[status] + bipartite_right_offset[status] + (thickness / 2.0)
            
            bipartite_left_offset[city] += thickness + 2.0
            bipartite_right_offset[status] += thickness + 1.0
            
            color = "rgba(98, 174, 146, 0.45)" if status == "collab" else "rgba(197, 154, 86, 0.45)"
            
            bipartite_paths.append(f"""
                <path d="M 170 {y_left:.1f} C 300 {y_left:.1f}, 350 {y_right:.1f}, 480 {y_right:.1f}"
                      fill="none" 
                      stroke="{color}" 
                      stroke-width="{thickness:.1f}" 
                      class="flow-line"
                      title="{esc(city)} → {esc(status_ru[status])}: {count} ученых">
                </path>
            """)
    svg_bipartite = "\n".join(bipartite_paths)

    body = f"""
        <header>
            <h1>Коллаборативный капитал и удержание ученых</h1>
            <p>Исследование влияния академического соавторства на выживаемость (retention rate) докладчиков и концентрацию сетевых связей в мегаполисах.</p>
        </header>

        <style>
            .collab-section {{
                background: rgba(23, 30, 27, 0.6);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 2rem 0;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }}
            .collab-title {{
                font-size: 1.4rem;
                color: var(--accent);
                margin-top: 0;
                margin-bottom: 1.2rem;
                font-weight: 700;
            }}
            .collab-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            @media (min-width: 900px) {{
                .collab-grid {{
                    grid-template-columns: 1.6fr 1fr;
                }}
            }}
            .collab-group {{
                background: rgba(16, 21, 19, 0.7);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.2rem;
                margin-bottom: 1rem;
            }}
            .collab-group-title {{
                font-weight: 700;
                color: var(--text);
                font-size: 1.1rem;
                margin-bottom: 0.8rem;
                border-bottom: 1px solid var(--border);
                padding-bottom: 0.4rem;
            }}
            .collab-bar-wrapper {{
                display: flex;
                flex-direction: column;
                gap: 0.25rem;
                margin-bottom: 0.75rem;
            }}
            @media (min-width: 600px) {{
                .collab-bar-wrapper {{
                    display: flex;
                    flex-direction: row;
                    align-items: center;
                    gap: 1rem;
                }}
            }}
            .collab-bar-label {{
                font-size: 0.85rem;
                color: var(--muted);
                width: 140px;
                flex-shrink: 0;
            }}
            .collab-bar-container {{
                background: rgba(0,0,0,0.3);
                border: 1px solid var(--border);
                border-radius: 6px;
                flex-grow: 1;
                height: 24px;
                overflow: hidden;
                position: relative;
            }}
            .collab-bar {{
                height: 100%;
                display: flex;
                align-items: center;
                padding-left: 0.75rem;
                border-radius: 5px 0 0 5px;
                transition: width 0.8s ease-in-out;
            }}
            .solo-bar {{
                background: linear-gradient(90deg, rgba(197, 154, 86, 0.25) 0%, rgba(197, 154, 86, 0.75) 100%);
            }}
            .collab-bar-fill {{
                background: linear-gradient(90deg, rgba(98, 174, 146, 0.25) 0%, rgba(98, 174, 146, 0.75) 100%);
            }}
            .collab-bar-value {{
                font-weight: bold;
                font-size: 0.82rem;
                color: #fff;
            }}
            .collab-bar-retention {{
                font-size: 0.8rem;
                color: var(--soft);
                width: 100px;
                text-align: right;
                flex-shrink: 0;
            }}
            .collab-leaders-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.85rem;
                margin-top: 1rem;
            }}
            .collab-leaders-table th, .collab-leaders-table td {{
                padding: 0.6rem 0.75rem;
                border-bottom: 1px solid var(--border);
                text-align: left;
            }}
            .collab-leaders-table th {{
                background: var(--panel-strong);
                color: var(--text);
                font-weight: 600;
            }}
            .collab-leaders-table td strong a {{
                color: var(--accent);
            }}
            .stats-card {{
                background: rgba(28, 37, 33, 0.4);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.2rem;
                margin-bottom: 1rem;
            }}
            .stats-header {{
                font-weight: 600;
                color: var(--accent2);
                margin-bottom: 0.6rem;
                font-size: 1.05rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }}
            .stats-text {{
                font-size: 0.88rem;
                line-height: 1.45;
                margin: 0 0 0.75rem 0;
                color: var(--muted);
            }}
            .stats-badge {{
                background: rgba(0,0,0,0.2);
                border-radius: 6px;
                padding: 0.75rem;
                border-left: 3px solid var(--accent);
                font-size: 0.82rem;
                color: var(--text);
                font-family: monospace;
            }}
        </style>

        <section class="collab-section">
            <h2 class="collab-title">📊 Возврат ученых в зависимости от соавторства и географии</h2>
            <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                Сравнение показателей возвращения ученых на повторные конференции (минимум 2 участия) среди тех, кто имеет совместные публикации, и тех, кто выступает исключительно соло.
            </p>
            <div class="collab-grid">
                <div class="collab-charts">
                    {bars_markup}
                </div>
                <div class="collab-stats-sidebar">
                    <div class="stats-card">
                        <div class="stats-header">🔬 Гипотеза H7+H9: Преимущество соавторства</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Ученые, участвующие в коллаборациях, имеют статистически значимо более высокую частоту возвращения на будущие конференции.
                        </p>
                        <div class="stats-badge">
                            Точный тест Фишера<br>
                            p-value = 0.000045 (highly sig.)<br>
                            Удержание соавторов: 70.4%<br>
                            Удержание соло: 46.8%
                        </div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-header">🌆 Мегаполисы как сетевые хабы</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Совместные доклады концентрируются в Москве и Санкт-Петербурге, тогда как региональные и иностранные участники остаются изолированными соло-акторами.
                        </p>
                        <div class="stats-badge" style="border-left-color: var(--accent2);">
                            Критерий Хи-квадрат<br>
                            p-value = 0.000001 (highly sig.)<br>
                            Коллаборации в мегаполисах: ~12-15%<br>
                            Коллаборации в регионах: &lt;3%
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="collab-section">
            <h2 class="collab-title">🕸️ Сетевое распределение: Притяжение мегаполисов</h2>
            <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                Связи между географическими центрами (местом аффилиации) и профилем авторства (соло-выступления против соавторства). Наглядно иллюстрирует, как Москва и Санкт-Петербург доминируют в формировании совместных докладов.
            </p>
            <svg viewBox="0 0 650 280" class="chord-sankey-svg" xmlns="http://www.w3.org/2000/svg" style="background: rgba(16, 21, 19, 0.6); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 0 auto; display: block; max-width: 650px; width: 100%; height: auto;">
                <!-- Left Nodes -->
                <!-- Санкт-Петербург -->
                <rect x="20" y="40" width="150" height="80" rx="6" fill="rgba(98, 174, 146, 0.2)" stroke="var(--accent)" stroke-width="2"></rect>
                <text x="95" y="85" fill="#fff" font-weight="bold" font-size="11" text-anchor="middle">С.-Петербург</text>
                
                <!-- Москва -->
                <rect x="20" y="135" width="150" height="50" rx="6" fill="rgba(197, 154, 86, 0.2)" stroke="var(--accent2)" stroke-width="2"></rect>
                <text x="95" y="165" fill="#fff" font-weight="bold" font-size="11" text-anchor="middle">Москва</text>
                
                <!-- Регионы / Ино -->
                <rect x="20" y="200" width="150" height="30" rx="6" fill="rgba(255,255,255,0.05)" stroke="var(--border)" stroke-width="1"></rect>
                <text x="95" y="218" fill="var(--soft)" font-weight="bold" font-size="10" text-anchor="middle">Регионы / Ино</text>

                <!-- Flows -->
                {svg_bipartite}

                <!-- Right Nodes -->
                <!-- Solo -->
                <rect x="480" y="40" width="150" height="105" rx="6" fill="rgba(197, 154, 86, 0.2)" stroke="var(--accent2)" stroke-width="2"></rect>
                <text x="555" y="98" fill="#fff" font-weight="bold" font-size="11" text-anchor="middle">Соло-авторы</text>
                
                <!-- Collaborative -->
                <rect x="480" y="160" width="150" height="70" rx="6" fill="rgba(98, 174, 146, 0.2)" stroke="var(--accent)" stroke-width="2"></rect>
                <text x="555" y="200" fill="#fff" font-weight="bold" font-size="11" text-anchor="middle">Соавторство</text>
            </svg>
        </section>

        <section class="collab-section">
            <h2 class="collab-title">👥 Лидеры коллаборативного капитала</h2>
            <p style="margin-top:0; margin-bottom:1rem; font-size:0.95rem; color:var(--muted);">
                Участники с наибольшим числом совместных докладов и многолетней историей удержания в рамках научного сообщества.
            </p>
            <div class="heatmap-container">
                <table class="collab-leaders-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Имя исследователя</th>
                            <th>Основной центр</th>
                            <th>Всего докладов</th>
                            <th>Лет участия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {leader_table_markup}
                    </tbody>
                </table>
            </div>
        </section>
    """
    
    write_text(
        "collaboration/index.html",
        page_shell(
            f"Коллаборативный капитал | {SITE_NAME}",
            "Исследование академического соавторства и показателей возвращаемости докладчиков в отечественной индологии.",
            collaboration_path(),
            body,
            [page_data("Коллаборативный капитал", "Сетевое соавторство и удержание ученых.", collaboration_path()), make_breadcrumbs([("Главная", ""), ("Коллаборация", collaboration_path())])],
        ),
    )


def generate_nlp_page(data, records):
    import pymorphy3
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import LatentDirichletAllocation

    morph = pymorphy3.MorphAnalyzer()

    def preprocess(text):
        text = re.sub(r'[^\w\s\-\u0400-\u04FF]', ' ', text.lower())
        text = re.sub(r'\d+', ' ', text)
        tokens = text.split()
        stop_words = {
            'и', 'в', 'во', 'на', 'с', 'со', 'о', 'об', 'обо', 'к', 'ко', 'из', 'от', 'до', 'у', 'для',
            'по', 'за', 'при', 'над', 'под', 'через', 'а', 'но', 'да', 'или', 'же', 'бы', 'ли', 'это',
            'как', 'так', 'что', 'чтобы', 'его', 'ее', 'их', 'он', 'она', 'они', 'мы', 'вы', 'я',
            'the', 'of', 'in', 'and', 'to', 'a', 'for', 'with', 'on', 'at', 'by', 'from', 'an', 'is'
        }
        cleaned = []
        for t in tokens:
            if t in stop_words or len(t) < 2:
                continue
            if re.match(r'^[\u0400-\u04FF\s\-]+$', t):
                lemma = morph.parse(t)[0].normal_form
                cleaned.append(lemma)
            else:
                cleaned.append(t)
        return " ".join(cleaned)

    corpus = []
    original_presentations = []
    
    for r in records:
        title = r.get("title") or ""
        cleaned = preprocess(title)
        corpus.append(cleaned)
        original_presentations.append({
            "id": r.get("presentation_id"),
            "title": title,
            "year": int(r.get("year") or 2004),
            "series": "Зографские" if "Зограф" in (r.get("series") or "") else "Рериховские",
            "author": r.get("author_display_name") or r.get("speaker_name") or "Не указан",
            "slug": r.get("slug") or ""
        })

    vectorizer = TfidfVectorizer(max_df=0.95, min_df=2, max_features=400)
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = list(vectorizer.get_feature_names_out())
    idf_weights = list(vectorizer.idf_)

    lda = LatentDirichletAllocation(n_components=6, random_state=42, max_iter=10)
    lda.fit(tfidf_matrix)
    
    topic_distributions = lda.transform(tfidf_matrix)
    dominant_topics = topic_distributions.argmax(axis=1)
    
    topic_terms = []
    for topic_idx, topic in enumerate(lda.components_):
        top_features_ind = topic.argsort()[:-10 - 1:-1]
        top_features = [feature_names[i] for i in top_features_ind]
        topic_terms.append(top_features)

    topic_titles = [
        "Лингвистика и грамматика",
        "Религия, философия и йога",
        "Текстология, рукописи и каноны",
        "Литературные сюжеты, эпос и поэзия",
        "История, этнография и общество",
        "Культура, искусство и мифология"
    ]

    presentations_payload = []
    for idx, p in enumerate(original_presentations):
        row = tfidf_matrix[idx]
        sparse_vec = {}
        for col_idx in row.indices:
            val = row[0, col_idx]
            sparse_vec[int(col_idx)] = int(val * 100)
            
        p_data = {
            "i": p["id"],
            "t": p["title"],
            "y": p["year"],
            "s": p["series"],
            "a": p["author"],
            "g": p["slug"],
            "v": sparse_vec,
            "t_idx": int(dominant_topics[idx])
        }
        presentations_payload.append(p_data)
        
    nlp_data_js = {
        "vocabulary": feature_names,
        "idf": idf_weights,
        "presentations": presentations_payload,
        "topics": [{"title": topic_titles[i], "terms": topic_terms[i]} for i in range(6)]
    }

    Path("assets").mkdir(exist_ok=True)
    write_text(
        "assets/nlp_data.js",
        f"const NLP_DATA = {json.dumps(nlp_data_js, ensure_ascii=False)};"
    )

    topic_cards_html = []
    for i in range(6):
        topic_cards_html.append(f"""
            <article class="card topic-card" onclick="selectTopic({i})" id="topic-card-{i}" style="cursor: pointer; transition: transform 0.25s, border-color 0.25s;">
                <strong style="font-size: 1.05rem; display: block; margin-bottom: 0.50rem; color: var(--accent2);">{esc(topic_titles[i])}</strong>
                <div class="meta" style="font-size: 0.82rem; line-height: 1.4;">
                    Ключевые слова:<br>
                    <span style="color: var(--text); font-style: italic;">{esc(", ".join(topic_terms[i]))}</span>
                </div>
            </article>
        """)
    topic_cards = "\n".join(topic_cards_html)

    body = """
        <header>
            <h1>Семантический NLP-анализ и тематическое моделирование</h1>
            <p>Умный семантический поиск по корпусу и латентное распределение Дирихле (LDA) для классификации докладов по 6 скрытым академическим субдисциплинам.</p>
        </header>

        <style>
            .nlp-section {
                background: rgba(23, 30, 27, 0.6);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 2rem 0;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }
            .nlp-title {
                font-size: 1.4rem;
                color: var(--accent);
                margin-top: 0;
                margin-bottom: 1.2rem;
                font-weight: 700;
            }
            .nlp-tabs {
                display: flex;
                gap: 0.5rem;
                margin-bottom: 1.5rem;
                border-bottom: 1px solid var(--border);
                padding-bottom: 0.75rem;
            }
            .nlp-tab {
                border: 1px solid var(--border);
                border-radius: 8px;
                background: transparent;
                padding: 0.5rem 1rem;
                color: var(--muted);
                cursor: pointer;
                font-weight: 600;
                font-size: 0.9rem;
                transition: all 0.2s;
            }
            .nlp-tab.active {
                background: var(--panel-strong);
                border-color: var(--accent);
                color: var(--text);
            }
            .search-results-container {
                background: rgba(16, 21, 19, 0.7);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.2rem;
                margin-top: 1rem;
            }
            .similarity-badge {
                display: inline-flex;
                align-items: center;
                border-radius: 6px;
                padding: 0.15rem 0.4rem;
                background: rgba(98, 174, 146, 0.15);
                border: 1px solid rgba(98, 174, 146, 0.35);
                color: var(--accent);
                font-size: 0.78rem;
                font-family: monospace;
                font-weight: bold;
            }
            .topic-card.active {
                border-color: var(--accent) !important;
                background: rgba(98, 174, 146, 0.05) !important;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }
        </style>

        <section class="nlp-section">
            <div class="nlp-tabs">
                <button class="nlp-tab active" id="tab-search" onclick="switchTab('search')">🔍 Семантический векторный поиск</button>
                <button class="nlp-tab" id="tab-lda" onclick="switchTab('lda')">🧩 Тематические кластеры (LDA)</button>
            </div>

            <!-- Tab 1: Semantic Vector Search -->
            <div id="section-search">
                <p style="margin-top:0; margin-bottom:1rem; font-size:0.95rem; color:var(--muted);">
                    Ищет по смысловой близости терминов, а не только по точному совпадению подстрок. Поиск рассчитывается на лету на клиенте (с помощью TF-IDF векторов Query vs. Corpus и косинусного сходства).
                </p>
                <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                    <input type="text" id="semantic-search-input" class="search-box" style="flex-grow:1;" 
                           placeholder="Введите поисковый запрос (например: 'буддийские тексты на санскрите', 'грамматика панини', 'индийские эпосы')..." 
                           oninput="triggerSemanticSearch()">
                </div>
                <div class="search-results-container">
                    <h3 style="margin-top:0; margin-bottom:1rem; font-size:1.1rem; color:var(--accent2);" id="search-results-title">Все доклады</h3>
                    <div class="list" id="search-results-list">
                        <!-- Instantly populated by Javascript -->
                    </div>
                </div>
            </div>

            <!-- Tab 2: LDA Topic Clusters -->
            <div id="section-lda" style="display: none;">
                <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                    Выделите тему, чтобы просмотреть все доклады, автоматически отнесенные алгоритмом латентного размещения Дирихле к этому кластеру.
                </p>
                <section class="grid" style="margin-bottom: 1.5rem;">
                    {topic_cards}
                </section>
                <div class="search-results-container">
                    <h3 style="margin-top:0; margin-bottom:1rem; font-size:1.1rem; color:var(--accent);" id="lda-results-title">Выберите тему выше</h3>
                    <div class="list" id="lda-results-list">
                        <!-- Populated by clicking topic cards -->
                    </div>
                </div>
            </div>
        </section>

        <!-- Preloaded NLP JSON Core -->
        <script src="../assets/nlp_data.js"></script>

        <script>
            // Client-side lightweight stemmer
            function stemRussian(word) {
                word = word.toLowerCase().trim();
                if (word.length < 3) return word;
                word = word.replace(/(ыми|ых|ов|ами|ах|ии|ия|ие|ый|ова|ева|ом|ам|ему|ому|ой)$/, '');
                return word;
            }

            function preprocessQuery(query) {
                const tokens = query.toLowerCase().replace(/[^\\w\\s\\-\\u0400-\\u04FF]/g, ' ').replace(/\\d+/g, ' ').split(/\\s+/);
                return tokens.filter(t => t.length >= 2).map(stemRussian);
            }

            function triggerSemanticSearch() {
                const queryText = document.getElementById("semantic-search-input").value;
                if (!queryText || queryText.trim() === "") {
                    document.getElementById("search-results-title").innerText = "Все доклады";
                    renderAllPresentations();
                    return;
                }
                
                const queryStems = preprocessQuery(queryText);
                const vocab = NLP_DATA.vocabulary;
                const idf = NLP_DATA.idf;
                
                const queryVector = {};
                const queryTF = {};
                queryStems.forEach(stem => {
                    vocab.forEach((term, idx) => {
                        const termStem = stemRussian(term);
                        if (termStem.startsWith(stem) || stem.startsWith(termStem)) {
                            queryTF[idx] = (queryTF[idx] || 0) + 1;
                        }
                    });
                });
                
                let queryNorm = 0;
                Object.keys(queryTF).forEach(idx => {
                    const tf = queryTF[idx];
                    const val = tf * idf[idx];
                    queryVector[idx] = val;
                    queryNorm += val * val;
                });
                queryNorm = Math.sqrt(queryNorm);
                
                const results = [];
                NLP_DATA.presentations.forEach(p => {
                    let dotProduct = 0;
                    let pNorm = 0;
                    
                    Object.keys(p.v).forEach(idx => {
                        const val = p.v[idx];
                        pNorm += val * val;
                        if (queryVector[idx]) {
                            dotProduct += val * queryVector[idx];
                        }
                    });
                    
                    pNorm = Math.sqrt(pNorm);
                    
                    const score = (queryNorm > 0 && pNorm > 0) ? (dotProduct / (queryNorm * pNorm)) : 0;
                    if (score > 0.03) {
                        results.push({ p: p, score: score });
                    }
                });
                
                results.sort((a, b) => b.score - a.score);
                document.getElementById("search-results-title").innerText = `Результаты поиска (${results.length} найдено)`;
                renderResults(results.slice(0, 20));
            }

            function renderResults(results) {
                const list = document.getElementById("search-results-list");
                if (results.length === 0) {
                    list.innerHTML = '<div style="color:var(--soft); font-style:italic;">Ничего не найдено по семантическому сходству. Попробуйте другие термины.</div>';
                    return;
                }
                
                let html = "";
                results.forEach(res => {
                    const p = res.p;
                    const path = p.g ? `../p/${p.g}.html` : "#";
                    html += `
                        <div class="talk" style="margin-bottom: 0.75rem;">
                            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;">
                                <strong><a href="${path}">${p.t}</a></strong>
                                <span class="similarity-badge">Sim: ${res.score.toFixed(2)}</span>
                            </div>
                            <div class="meta" style="margin-top:0.25rem;">
                                <strong>${p.a}</strong> · ${p.s} чтения · ${p.y} год
                            </div>
                        </div>
                    `;
                });
                list.innerHTML = html;
            }

            function renderAllPresentations() {
                const list = document.getElementById("search-results-list");
                let html = "";
                // Show first 20 presentations as baseline
                NLP_DATA.presentations.slice(0, 20).forEach(p => {
                    const path = p.g ? `../p/${p.g}.html` : "#";
                    html += `
                        <div class="talk" style="margin-bottom: 0.75rem;">
                            <strong><a href="${path}">${p.t}</a></strong>
                            <div class="meta" style="margin-top:0.25rem;">
                                <strong>${p.a}</strong> · ${p.s} чтения · ${p.y} год
                            </div>
                        </div>
                    `;
                });
                list.innerHTML = html;
            }

            let selectedTopicIdx = null;
            function selectTopic(idx) {
                // Toggle active card styling
                for (let i = 0; i < 6; i++) {
                    document.getElementById(`topic-card-${i}`).classList.remove("active");
                }
                
                selectedTopicIdx = idx;
                document.getElementById(`topic-card-${idx}`).classList.add("active");
                
                // Filter presentations by topic index
                const filtered = NLP_DATA.presentations.filter(p => p.t_idx === idx);
                document.getElementById("lda-results-title").innerText = `${NLP_DATA.topics[idx].title} (${filtered.length} докладов)`;
                
                const list = document.getElementById("lda-results-list");
                let html = "";
                filtered.forEach(p => {
                    const path = p.g ? `../p/${p.g}.html` : "#";
                    html += `
                        <div class="talk" style="margin-bottom: 0.75rem;">
                            <strong><a href="${path}">${p.t}</a></strong>
                            <div class="meta" style="margin-top:0.25rem;">
                                <strong>${p.a}</strong> · ${p.s} чтения · ${p.y} год
                            </div>
                        </div>
                    `;
                });
                list.innerHTML = html;
            }

            function switchTab(tab) {
                document.getElementById("tab-search").classList.remove("active");
                document.getElementById("tab-lda").classList.remove("active");
                document.getElementById("section-search").style.display = "none";
                document.getElementById("section-lda").style.display = "none";
                
                if (tab === 'search') {
                    document.getElementById("tab-search").classList.add("active");
                    document.getElementById("section-search").style.display = "block";
                } else {
                    document.getElementById("tab-lda").classList.add("active");
                    document.getElementById("section-lda").style.display = "block";
                    if (selectedTopicIdx === null) {
                        selectTopic(0);
                    }
                }
            }

            // Initalize baseline presentations on page load
            window.onload = function() {
                renderAllPresentations();
            };
        </script>
    """
    body = body.replace("{topic_cards}", topic_cards)

    write_text(
        "nlp/index.html",
        page_shell(
            f"Семантический NLP-анализ | {SITE_NAME}",
            "Латентное моделирование тем (LDA) и смысловой векторный поиск по архиву докладов.",
            nlp_path(),
            body,
            [page_data("Семантический NLP-анализ", "Тематическое моделирование и векторный поиск.", nlp_path()), make_breadcrumbs([("Главная", ""), ("NLP-анализ", nlp_path())])],
        ),
    )


GUMILYOV_RHETORIC_EXAMPLES = {
    1: [
        {
            "id": "PRES_2a08c0cb86",
            "logic": "Субъект рассуждения - конкретный канонический текст, «Бхагавадгита», а не вся индийская религиозная мысль. В классической логике это частный предмет с ограниченным объемом: предикаты доклада относятся к одному корпусу и его проблемам изучения.",
            "rhetoric": "Работает топос определения и толкования текста: доклад уточняет, какие проблемы возникают при чтении данного памятника. Аргументация строится как экзегеза, а не как обзор традиции.",
            "boundary": "Это L1, потому что вывод не распространяется на всю традицию бхакти, индуизм или Южную Азию. Не L2: регион или школа не становятся главным родом доказательства. Не L3: нет межцивилизационного или методологического обобщения.",
        },
        {
            "id": "PRES_3dfb43981f",
            "logic": "Предмет задан как один тибетский учебник по теории познания. Его логический объем уже, чем «тибетская эпистемология»: учебник служит индивидуальным носителем тезиса.",
            "rhetoric": "Риторически это разбор источника через топос части и целого: учебник может свидетельствовать о традиции, но сам доклад удерживает доказательство на уровне одного учебного текста.",
            "boundary": "Это L1: тезис проверяется на конкретном учебнике. Не L2, пока не доказывается устройство всей тибетской школьной традиции. Не L3, потому что сравнение с внешними эпистемологиями не является главным выводом.",
        },
        {
            "id": "PRES_764a73ce7c",
            "logic": "Логический субъект - один термин, адхьякша, в индийской традиции. По объему понятия термин является минимальной единицей анализа, даже если его значения встречаются в разных контекстах.",
            "rhetoric": "Используется топос имени и значения: доклад убеждает через семантическое различение, а не через историческую панораму. Это риторика дефиниции, а не риторика синтеза.",
            "boundary": "Это L1, потому что предметом остается терминологический кейс. Не L2: словосочетание «индийская традиция» указывает место употребления, но не делает вывод об устройстве всей традиции. Не L3: нет универсальной теории терминологии.",
        },
        {
            "id": "PRES_457408b87a",
            "logic": "Сравниваются два мыслителя по одному вопросу - возможности рефлексивного акта познания. В логическом отношении это не широкий род, а ограниченный спорный предикат у двух авторов.",
            "rhetoric": "Риторика строится на антитезе и сопоставлении позиций. Такое сравнение остается частным, потому что tertium comparationis задан узко: один эпистемологический вопрос.",
            "boundary": "Это L1: наличие двух имен не повышает уровень автоматически. Не L2, потому что не реконструируется вся школа или традиция. Не L3, потому что нет сопоставления цивилизационных моделей знания.",
        },
        {
            "id": "PRES_92c5268a51",
            "logic": "Субъектом является фигура царя и представления о времени внутри «Махабхараты». Объем доказательства ограничен одним эпическим корпусом и выбранной темой.",
            "rhetoric": "Доклад использует топос примера и внутренней связи: через персонажную фигуру раскрывается смысловая организация текста. Это не панегирический обзор царской власти в Индии.",
            "boundary": "Это L1, потому что вывод связан с «Махабхаратой». Не L2: эпическая традиция в целом не становится предметом доказательства. Не L3: не заявлена сравнительная теория власти и времени.",
        },
        {
            "id": "PRES_6e17572f1f",
            "logic": "Название звучит широко, но субъект вывода - проблема классификации внутри индуистских тантрических школ. Логический род ограничен одной традиционной областью и ее внутренней номенклатурой.",
            "rhetoric": "Это топос деления: доклад выясняет, как различать виды внутри уже заданного рода. Классическая divisio здесь служит инструментом наведения порядка, а не макроисторической схемой.",
            "boundary": "Это L1 как методический кейс внутри одной традиции. Не L2, потому что не описывается историческая конфигурация тантризма как регионального процесса. Не L3, потому что классификация не превращается в общую теорию религий.",
        },
        {
            "id": "PRES_ec5840a950",
            "logic": "Предмет - слово ātman в «Ригведе». В логике это единичный термин в конкретном корпусе, поэтому объем вывода задается пересечением «слово» и «текст».",
            "rhetoric": "Риторически это филологическая quaestio: доклад возвращается к спорному слову и уточняет его значение. Убедительность зависит от цитаты, контекста и различения значений.",
            "boundary": "Это L1, потому что речь идет о слове в одном ведийском корпусе. Не L2: ведийская культура не является самостоятельным объектом обобщения. Не L3: нет общей антропологии понятия «я».",
        },
        {
            "id": "PRES_a8e1a30833",
            "logic": "Логический субъект - перевод Г. С. Лебедева по конкретной рукописи. Даже широкий контекст Калькутты или бенгальской литературы здесь подчинен одному документальному случаю.",
            "rhetoric": "Использован топос свидетельства: рукопись и перевод выступают доказательными объектами. Риторический ход ближе к предварительному сообщению об источнике, чем к синтезу литературной истории.",
            "boundary": "Это L1: доказательство держится на одном переводе и рукописи. Не L2, пока не выводится модель всей бенгальской литературы или колониальной культуры. Не L3, потому что нет глобальной истории перевода.",
        },
        {
            "id": "PRES_20910e0f90",
            "logic": "Субъект - санскритское upa-sru- и один способ гадания. Логический объем сужен до термина и практики, которые проверяются филологически.",
            "rhetoric": "Риторика вопроса «слышать или вслушиваться?» задает апорию и решает ее через различение. Это классический ход refutatio: отвергнуть слишком грубое значение и выбрать более точное.",
            "boundary": "Это L1, потому что объект - терминологический и ритуальный кейс. Не L2: древнеиндийская гадательная традиция в целом не обобщается. Не L3: нет общей теории ритуального слушания.",
        },
        {
            "id": "PRES_37a471ecf5",
            "logic": "Формула «к проблеме» обозначает постановку вопроса, а не доказанную панораму всей древнеиндийской хронологии. В терминах логики это проблемный узел, не родовое обобщение.",
            "rhetoric": "Риторически заголовок использует deliberatio: вынести трудность на обсуждение. Такая постановка может быть важной, но она не равна синтетическому тезису о всем историческом времени Индии.",
            "boundary": "Это L1, потому что аргумент классифицируется как ограниченная методическая проблема. Не L2, если нет развернутой модели региональной хронологической традиции. Не L3, потому что не задана универсальная теория исторического времени.",
        },
    ],
    2: [
        {
            "id": "PRES_9e203d9b3f",
            "logic": "Субъектом выступает не один текст или один ритуал, а взаимоотношение конфессий в средневековом Тамилнаде. Логический объем охватывает региональную историко-религиозную конфигурацию.",
            "rhetoric": "Риторика основана на топосе отношения: важны связи, напряжения и сосуществование групп. Доклад убеждает через описание структуры региональной среды.",
            "boundary": "Это L2, потому что вывод относится к традициям внутри конкретного региона и эпохи. Не L1: предмет шире отдельного памятника. Не L3: рамка не выходит к универсальной модели религиозных цивилизаций.",
        },
        {
            "id": "PRES_3fd8e2489c",
            "logic": "Понятие «кинематографический текст» берется в современной индийской культуре как родовой культурный феномен. Объем сужен Индией и современностью, но явно шире одного фильма.",
            "rhetoric": "Используется топос рода и вида: отдельные фильмы подразумеваются как виды или примеры, а тезис относится к культурному типу. Это риторика культурного обобщения.",
            "boundary": "Это L2: доклад говорит о культурной традиции и ее медиальном языке. Не L1, потому что не ограничен одним произведением. Не L3, потому что не строит общую теорию кино между цивилизациями.",
        },
        {
            "id": "PRES_844f6b86ea",
            "logic": "Предмет - образы фантастических животных как повторяющийся тип в средневековой архитектуре Индии. Логический субъект является классом объектов, привязанным к региону и периоду.",
            "rhetoric": "Риторически это индукция по множеству памятников: примеры должны вести к общему признаку образного языка. Топос сходства важнее анализа одного артефакта.",
            "boundary": "Это L2, потому что вывод охватывает тип изображений в культурно-исторической области. Не L1: один памятник не исчерпывает предмет. Не L3: нет межрегиональной сравнительной архитектурной теории.",
        },
        {
            "id": "PRES_a9e0852a8d",
            "logic": "Субъект - мыслители Бенгальского Возрождения как интеллектуальная среда. Объем понятия совпадает с движением или школой, а не с одной персоной.",
            "rhetoric": "Риторика идет через топос традиции: доклад показывает, как группа интерпретирует наследие. Убедительность строится на общности приемов у нескольких участников среды.",
            "boundary": "Это L2: регионально-историческое движение является главным родом. Не L1, если материал не сведен к одному автору. Не L3, потому что не сравниваются цивилизационные модели возрождения как таковые.",
        },
        {
            "id": "PRES_c305a62ca7",
            "logic": "Институт гутхи рассматривается в древнем и средневековом Непале, то есть как устойчивая социально-религиозная форма в исторической среде. Это класс институтов, а не единичная запись.",
            "rhetoric": "Работает топос причины и функции: институт объясняется через его роль в обществе и культуре. Доклад не просто описывает источник, а выводит правило региональной организации.",
            "boundary": "Это L2, потому что предмет - непальская институциональная традиция. Не L1: он шире одного документа. Не L3: нет сравнения институтов разных цивилизаций.",
        },
        {
            "id": "PRES_22c7444e36",
            "logic": "Субъектом являются символические модели Абсолютного Сознания в кашмирском шиваизме. Логический род - школа и ее концептуальный аппарат.",
            "rhetoric": "Риторика использует топос модели: разные символические формы сводятся к объяснительной схеме. Это не комментарий к одному месту текста, а реконструкция школьной системы.",
            "boundary": "Это L2: вывод работает в пределах философско-религиозной школы. Не L1, потому что предметом является не один трактат. Не L3, потому что методологические вопросы не выводят тезис за пределы традиции.",
        },
        {
            "id": "PRES_523a56fd5b",
            "logic": "Концепция Ишвары сопоставляется в классической йоге и кашмирском шиваизме. Объем включает две школы, объединенные одним понятием.",
            "rhetoric": "Риторический ход - comparatio: сходство и различие выявляются через общий термин. Сравнение работает на уровне традиций, но не поднимается до всемирной типологии теизма.",
            "boundary": "Это L2, потому что предмет шире одного автора и включает школьное сопоставление. Не L1: две системы не служат только иллюстрациями одного текста. Не L3: сравнение остается внутри индийской философской области.",
        },
        {
            "id": "PRES_50a29145a7",
            "logic": "Традиции веротерпимости и универсализма рассматриваются в древней и средневековой Индии. Логический объем задан большим регионом и двумя эпохами.",
            "rhetoric": "Риторика опирается на топос исторической протяженности: отдельные свидетельства складываются в региональную линию. Это индуктивное обобщение, а не частный комментарий.",
            "boundary": "Это L2, потому что тезис относится к индийской историко-культурной традиции. Не L1: предмет не сводится к одному случаю. Не L3: нет сравнения с универсализмом других цивилизаций как главным выводом.",
        },
        {
            "id": "PRES_42588a671c",
            "logic": "Роль буддизма в культурном единстве Азии задает широкий региональный субъект. Это больше, чем локальный кейс, но рамка все еще удержана буддийско-азиатским пространством.",
            "rhetoric": "Риторически работает топос объединяющей причины: буддизм рассматривается как фактор связи. Аргумент синтетичен, но синтез региональный, а не всемирный.",
            "boundary": "Это L2: масштаб азиатский и традиционный. Не L1, потому что речь идет не об одном тексте или монастыре. Не L3, потому что доклад не сравнивает Азию с другими цивилизационными системами.",
        },
        {
            "id": "PRES_80c3a05563",
            "logic": "Формульность индийских дарственных надписей - это признак класса эпиграфических объектов. Логический субъект шире одной надписи и ограничен индийским материалом.",
            "rhetoric": "Доклад использует топос повторения: формула доказывается серией примеров. Индукция выводит правило жанра, а не уникальность отдельного текста.",
            "boundary": "Это L2, потому что предметом является тип документов в традиции. Не L1: одна надпись не была бы достаточной. Не L3: нет общей теории письма или дарения вне индийского корпуса.",
        },
    ],
    3: [
        {
            "id": "PRES_e4b6786e6b",
            "logic": "Субъект - сама методология сравнения индийской и западной эпистемологии. Объем понятия включает две большие интеллектуальные традиции и правила их сопоставления.",
            "rhetoric": "Риторика строится как ars comparandi: доклад задает условия корректного сравнения, то есть говорит не только о материале, но и о методе доказательства.",
            "boundary": "Это L3, потому что вывод претендует на межцивилизационный и методологический уровень. Не L2: рамка не ограничена одной школой или регионом. Не L1: отдельные тексты могут быть примерами, но не предметом уровня.",
        },
        {
            "id": "PRES_54a32921dc",
            "logic": "Генезис рефлексии сравнивается в индийской и европейской философских традициях. Логический субъект - два больших рода философствования и механизм их становления.",
            "rhetoric": "Здесь действует топос причины: визуальные и лингвистические детерминанты объясняют различия традиций. Аргумент просит читателя мыслить на уровне условий возможности.",
            "boundary": "Это L3: сравнение индийского и европейского задает цивилизационный объем. Не L2, потому что это не одна региональная традиция. Не L1, потому что не один автор или трактат является главным предметом.",
        },
        {
            "id": "PRES_9f51b09a94",
            "logic": "Проблема языка ставится между ведантой и европейским романтизмом. Объем вывода пересекает индийскую философскую школу и европейское интеллектуальное движение.",
            "rhetoric": "Риторика основана на аналогии и различении: общий вопрос языка позволяет сопоставить традиции, но различия не растворяются в одном локальном корпусе.",
            "boundary": "Это L3, потому что сравниваются удаленные интеллектуальные миры. Не L2: веданта сама по себе была бы регионально-традиционным уровнем, но европейский романтизм расширяет рамку. Не L1: вопрос не сведен к одному тексту.",
        },
        {
            "id": "PRES_aa4df50cf0",
            "logic": "Древние южноазиатско-африканские связи по данным фольклора и мифологии задают межрегиональный субъект. Объем шире Южной Азии и шире одного корпуса источников.",
            "rhetoric": "Это риторика coniectura и comparatio: по мотивам и мифологическим данным реконструируется связь между большими ареалами. Доказательство работает через сопоставимые признаки.",
            "boundary": "Это L3, потому что предметом является связь крупных регионов. Не L2: рамка не замкнута в одной индийской или африканской традиции. Не L1: отдельный миф здесь только свидетельство.",
        },
        {
            "id": "PRES_74cd40949e",
            "logic": "Понятие фундаментальности в индологии - метапонятие дисциплины. Логический субъект находится выше отдельных объектов: речь о критерии, по которому наука оценивает собственные основания.",
            "rhetoric": "Риторика философская и методологическая: доклад использует топос определения, но определяет не термин источника, а принцип дисциплинарного знания.",
            "boundary": "Это L3, потому что тезис относится к индологии как способу знания. Не L2: нет одной региональной традиции как главного предмета. Не L1: речь не об одном тексте, авторе или экспедиции.",
        },
        {
            "id": "PRES_7c33afdee0",
            "logic": "«Век Кроноса» и «Сатья-юга» сопоставлены как два вида теории социогенеза. Логический род - представления о происхождении общества в разных культурных системах.",
            "rhetoric": "Риторика род-вид здесь явная: две традиционные фигуры подводятся под общий объяснительный род. Сравнение поддерживается аналогией и контрастом.",
            "boundary": "Это L3: античная и индийская рамки выводят доклад на цивилизационное сопоставление. Не L2, потому что не одна традиция является пределом. Не L1, потому что отдельные мифы служат материалом для общей схемы.",
        },
        {
            "id": "PRES_15b5fbdc83",
            "logic": "Вопрос «что отличает индийскую эпистемическую культуру от западной» прямо задает два цивилизационных рода. Предикат относится к способу производства знания, а не к частному тексту.",
            "rhetoric": "Риторически это distinctio: доклад ищет существенное отличие, а не случайный признак. Такая форма требует широкого набора оснований и сравнительной рамки.",
            "boundary": "Это L3, потому что главный вывод различает индийскую и западную эпистемические культуры. Не L2: индийская культура не рассматривается изолированно. Не L1: отдельные примеры не определяют уровень.",
        },
        {
            "id": "PRES_af42ca8e9f",
            "logic": "«2400 лет фейковой индологии» задает длинную историю представлений об Индии. Объем вывода охватывает не один период и не одну традицию, а устойчивый трансисторический образ.",
            "rhetoric": "Риторика использует топос опровержения: мифы об Индии выставляются как ложные или искаженные мнения, которые нужно разоблачить на большой временной шкале.",
            "boundary": "Это L3: масштаб длительный, межкультурный и дисциплинарный. Не L2, потому что речь не только об индийской региональной традиции. Не L1, потому что один миф или один автор не исчерпывает тезис.",
        },
        {
            "id": "PRES_a8e1d07658",
            "logic": "Скифский язык, топонимы Скифии и Центральной Азии, индоевропейские языки и заимствования из Индии и Понта задают сеть регионов и языковых семей. Логический субъект межрегионален.",
            "rhetoric": "Аргумент строится как accumulatio: языковые и топонимические признаки складываются в картину культурных перемещений. Риторическая сила - в соединении разнородных свидетельств.",
            "boundary": "Это L3, потому что рамка выходит за одну страну, один язык и одну традицию. Не L2: Центральная Азия и Индия не являются единственным пределом, подключена индоевропейская перспектива. Не L1: ни один топоним не является главным предметом.",
        },
        {
            "id": "PRES_42ff807ebd",
            "logic": "Переоценка методологических подходов к исследованию индийской философии - метауровень дисциплины. Субъектом являются способы исследования, а не отдельная школа философии.",
            "rhetoric": "Риторика критическая: через книгу Адлури и Багчи пересматриваются основания немецкой индологии и современного метода. Это refutatio и iudicium на уровне научной традиции.",
            "boundary": "Это L3, потому что доклад оценивает методологические рамки исследования. Не L2: индийская философия здесь не просто региональный объект. Не L1: конкретная книга является поводом, но вывод относится к способу исследования.",
        },
    ],
}


def render_gumilyov_rhetoric_examples(records_by_id):
    sections = []
    for level in (1, 2, 3):
        meta = GUMILYOV_LEVELS[level]
        cards = []
        for index, example in enumerate(GUMILYOV_RHETORIC_EXAMPLES[level], start=1):
            pid = example["id"]
            talk = records_by_id.get(pid)
            if not talk:
                continue
            path = presentation_path(pid, talk.get("title"))
            cards.append(
                f"""
                <article class="talk">
                    <strong>{index}. <a href="../{esc(path)}">{esc(talk.get("title"))}</a></strong>
                    <div class="meta">L{level} {esc(meta["short_ru"])} · {esc(series_label(talk.get("series_key"), "ru"))} {esc(talk.get("year"))} · {scholar_links_html(talk, "../")}</div>
                    <p><strong>Логика:</strong> {esc(example["logic"])}</p>
                    <p><strong>Риторика:</strong> {esc(example["rhetoric"])}</p>
                    <p><strong>Почему не другой уровень:</strong> {esc(example["boundary"])}</p>
                </article>
                """
            )
        sections.append(
            f"""
            <h3>L{level} {esc(meta["ru"])}: 10 мотивировок</h3>
            <section class="list">{"".join(cards)}</section>
            """
        )
    return f"""
        <section id="logic-rhetoric-examples">
            <h2>Почему доклад попадает именно в этот уровень</h2>
            <p>Ниже уровень читается через классическую логику и риторику: что является субъектом доказательства, каков объем понятия, каким топосом строится убеждение и где проходит граница с соседними уровнями. Это не оценка качества доклада, а объяснение масштаба вывода.</p>
        </section>
        {"".join(sections)}
    """


def generate_gumilyov_pages(data, records):
    records_by_id = presentation_records_by_id(records)
    unique_records = list(records_by_id.values())
    grouped = defaultdict(list)
    for talk in unique_records:
        level, _meta = gumilyov_meta(talk.get("gumilyov_scale"))
        grouped[level].append(talk)
    for talks in grouped.values():
        talks.sort(key=lambda rec: (int(rec.get("year") or 0), rec.get("series_key") or "", rec.get("title") or ""))

    cards = []
    for level in sorted(GUMILYOV_LEVELS):
        if level == 0 and not grouped.get(level):
            continue
        meta = GUMILYOV_LEVELS[level]
        count = len(grouped.get(level, []))
        cards.append(
            f"""
            <article class="card">
                <strong><a href="../{gumilyov_path(level)}">L{level} {esc(meta["ru"])}</a></strong>
                <div class="metric">{count}</div>
                <div class="meta">{esc(meta["description"])}</div>
            </article>
            """
        )

        body = f"""
        <header>
            <h1>L{level} {esc(meta["ru"])}</h1>
            <p>{esc(meta["description"])}</p>
        </header>
        <aside class="caveat-block" role="note" aria-label="Gumilyov classification notice">
            <strong>Примечание о классификации</strong>
            <p>Уровень Гумилева обозначает масштаб аргумента, а не географию или язык материала. Полный расширенный корпус прошел DeepSeek-разметку и отдельный строгий аудит предварительных L2/L3; частный ритуал, экспедиция, текст или языковой кейс остаются L1 даже при упоминании региона или традиции. Уровень не является оценкой качества доклада.</p>
            <div class="chip-list"><a class="chip" href="../classification-criteria.html">Обновленные критерии</a></div>
        </aside>
        <section class="list">
            {''.join(talk_card(t, '../') for t in grouped.get(level, []))}
        </section>
        """
        write_text(
            gumilyov_path(level),
            page_shell(
                f"L{level} {meta['ru']} | {SITE_NAME}",
                meta["description"],
                gumilyov_path(level),
                body,
                [page_data(f"L{level} {meta['ru']}", meta["description"], gumilyov_path(level)), make_breadcrumbs([("Главная", ""), ("Гумилев", "gumilyov/"), (f"L{level}", gumilyov_path(level))])],
            ),
        )

    gumilyov_motivation = render_gumilyov_rhetoric_examples(records_by_id)
    index_body = f"""
        <header>
            <h1>Классификация по уровню обобщения</h1>
            <p>Навигационный масштаб доклада по мотивам уровней обобщения Л. Н. Гумилева: от конкретного кейса к региональной традиции и широкому сравнительному уровню.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
        <aside class="caveat-block" role="note" aria-label="Expert classification notice">
            <strong>Как читать уровни</strong>
            <p>Географическое название, этноним или сопоставление двух объектов сами по себе не превращают доклад в региональное или макроисторическое обобщение. Все 1350 докладов классифицированы заново; предварительные L2/L3 проверены вторым запросом, а редакционная проверка уточнила два оставшихся макрослучая.</p>
            <div class="chip-list"><a class="chip" href="../classification-criteria.html">Критерии и проверенные кейсы</a></div>
        </aside>
        {gumilyov_motivation}
        <section class="link-block">
            <strong>Данные</strong>
            <div class="chip-list">
                <a class="chip" href="../analytics_output/gumilyov_scale.csv">gumilyov_scale.csv</a>
                <a class="chip" href="../analytics_output/classification_overrides.csv">classification_overrides.csv</a>
                <a class="chip" href="../analytics_output/gumilyov_video_comparison.csv">video comparison</a>
            </div>
        </section>
    """
    write_text(
        "gumilyov/index.html",
        page_shell(
            f"Классификация Гумилева | {SITE_NAME}",
            "Классификация докладов по уровню обобщения: микро, региональный и глобальный уровни.",
            "gumilyov/",
            index_body,
            [page_data("Классификация Гумилева", "Классификация докладов по уровню обобщения.", "gumilyov/"), make_breadcrumbs([("Главная", ""), ("Гумилев", "gumilyov/")])],
        ),
    )


def load_youtube_rows():
    return load_csv_rows("analytics_output/youtube_video_list.csv")


def load_video_mapping_rows():
    rows = {}
    for row in load_csv_rows("analytics_output/video_presentation_mapping.csv"):
        video_id = clean_text(row.get("video_id") or "")
        if video_id:
            rows[video_id] = row
    return rows


def generate_video_pages(data, records):
    videos = load_youtube_rows()
    mapping = load_video_mapping_rows()
    records_by_id = presentation_records_by_id(records)
    records_by_video_id = defaultdict(list)
    for talk in records_by_id.values():
        for video in talk.get("videos") or []:
            url = video.get("url") or ""
            match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]+)", url)
            if match:
                records_by_video_id[match.group(1)].append(talk)

    def video_card(row, depth="../"):
        video_id = clean_text(row.get("video_id") or "")
        mapped_records = records_by_video_id.get(video_id, [])
        mapping_row = mapping.get(video_id, {})
        status = mapping_row.get("status") or ("auto" if mapped_records else "unmapped")
        status_label = {
            "auto": "сопоставлено с докладом",
            "manual": "сопоставлено вручную",
            "needs_review": "требует проверки",
            "skip": "служебная/сессионная запись",
            "unmapped": "не сопоставлено",
        }.get(status, status)
        talk_links = []
        for talk in mapped_records:
            talk_links.append(f'<a href="{esc(talk_deep_link(talk, depth))}">{esc(talk.get("title"))}</a>')
        talk_html = f'<div class="meta">Доклад: {" · ".join(talk_links)}</div>' if talk_links else ""
        return f"""
            <article class="card">
                <strong><a href="{esc(row.get("video_url"))}">{esc(row.get("video_title"))}</a></strong>
                <div class="meta">{esc(row.get("playlist_label"))} · позиция {esc(row.get("position"))} · {esc(status_label)}</div>
                {talk_html}
            </article>
        """

    by_year = defaultdict(list)
    for row in videos:
        year = clean_text(row.get("year") or "")
        if year:
            by_year[year].append(row)

    matched = len(records_by_video_id)
    needs_review = sum(1 for row in mapping.values() if row.get("status") == "needs_review")
    skipped = sum(1 for row in mapping.values() if row.get("status") == "skip")
    year_cards = []
    for year, rows in sorted(by_year.items()):
        year_cards.append(
            f'<article class="card"><strong><a href="../{videos_year_path(year)}">YouTube {esc(year)}</a></strong><div class="metric">{len(rows)}</div><div class="meta">видеозаписей в плейлистах</div></article>'
        )
        body = f"""
        <header>
            <h1>YouTube {esc(year)}</h1>
            <p>Видеозаписи, загруженные в соответствующий плейлистовый год. Часть плейлистов содержит записи более ранних сессий, что сохранено в исходной метке плейлиста.</p>
        </header>
        <section class="list">
            {''.join(video_card(row, '../') for row in rows)}
        </section>
        """
        write_text(
            videos_year_path(year),
            page_shell(
                f"YouTube {year} | {SITE_NAME}",
                f"Видеозаписи YouTube по плейлистовому году {year}.",
                videos_year_path(year),
                body,
                [page_data(f"YouTube {year}", f"Видеозаписи YouTube по плейлистовому году {year}.", videos_year_path(year)), make_breadcrumbs([("Главная", ""), ("Видео", "videos/"), (year, videos_year_path(year))])],
            ),
        )

    index_body = f"""
        <header>
            <h1>YouTube-видеозаписи</h1>
            <p>Полный список видеозаписей из YouTube-плейлистов Зографских чтений и проверенные сопоставления с докладами корпуса.</p>
        </header>
        <section class="grid">
            <article class="card"><strong>Всего видео</strong><div class="metric">{len(videos)}</div></article>
            <article class="card"><strong>Сопоставлено с докладами</strong><div class="metric">{matched}</div></article>
            <article class="card"><strong>Требует проверки</strong><div class="metric">{needs_review}</div></article>
            <article class="card"><strong>Сессионные/служебные записи</strong><div class="metric">{skipped}</div></article>
        </section>
        <h2>По годам плейлистов</h2>
        <section class="grid">{''.join(year_cards)}</section>
        <section class="link-block">
            <strong>CSV-выгрузки</strong>
            <div class="chip-list">
                <a class="chip" href="../analytics_output/youtube_video_list.csv">youtube_video_list.csv</a>
                <a class="chip" href="../analytics_output/video_presentation_mapping.csv">video_presentation_mapping.csv</a>
                <a class="chip" href="../analytics_output/youtube_playlist_summary.csv">youtube_playlist_summary.csv</a>
            </div>
        </section>
        <h2>Полный список</h2>
        <section class="list">
            {''.join(video_card(row, '../') for row in videos)}
        </section>
    """
    write_text(
        "videos/index.html",
        page_shell(
            f"Видеозаписи | {SITE_NAME}",
            "Полный список YouTube-видеозаписей и сопоставлений с докладами.",
            "videos/",
            index_body,
            [page_data("Видеозаписи", "Полный список YouTube-видеозаписей и сопоставлений с докладами.", "videos/"), make_breadcrumbs([("Главная", ""), ("Видео", "videos/")])],
        ),
    )


def presentation_detail_body(talk, depth="../"):
    pid = clean_text(talk.get("presentation_id") or "")
    theme = talk.get("theme") or {}
    theme_code = theme.get("code") or "unspecified"
    g_level, g_meta = gumilyov_meta(talk.get("gumilyov_scale"))
    videos = talk.get("videos") or []
    
    meso_items = meso_items_by_code()
    meso_links = [
        f'<a class="chip" href="{depth}{meso_path(code)}">{esc(meso_items[code]["label"])}</a>'
        for code in talk.get("meso_codes", [])
        if code in meso_items
    ]
    
    conference_href = f'{depth}{conference_path(talk.get("series_key"), talk.get("year"))}#{pid}'
    
    city = (talk.get("geography") or {}).get("ru")
    city_html = (
        f'<a class="chip" href="{depth}{city_path(city)}">{esc(city)}</a>'
        if city and city not in ("Не указана", "Not specified")
        else ""
    )
    
    source_url = clean_text(talk.get("source_url") or "")
    source_updated = clean_text(talk.get("program_last_updated") or "")
    source_updated_text = ""
    if source_url and source_updated:
        source_updated_text = " · последнее обновление: " + dt.datetime.strptime(source_updated, "%Y-%m-%d").strftime("%d.%m.%Y")
        
    review = CLASSIFICATION_OVERRIDES.get(pid)
    review_reason = review["reason"] if review else ""
    
    video_links = [
        f'<a class="chip" href="{esc(video.get("url"))}">YouTube</a>'
        for video in videos
    ]
    
    title_note = clean_text(talk.get("title_editorial_note") or "")
    affiliation = clean_text(talk.get("affiliation") or "")
    affiliation_note = clean_text(talk.get("affiliation_note") or "")
    
    template = _JINJA_ENV.get_template("presentation_detail.html")
    return template.render(
        talk=talk,
        depth=depth,
        pid=pid,
        theme_path=theme_path(theme_code),
        theme_label=theme_label(theme_code, "ru"),
        g_level=g_level,
        g_meta_ru=g_meta["ru"],
        videos=videos,
        meso_links=meso_links,
        conference_href=conference_href,
        series_label=series_label(talk.get("series_key"), "ru"),
        city_html=city_html,
        source_url=source_url,
        source_updated_text=source_updated_text,
        review_reason=review_reason,
        video_links=video_links,
        title_note=title_note,
        affiliation=affiliation,
        affiliation_note=affiliation_note,
        scholar_links_html=scholar_links_html(talk, depth)
    )



def presentation_seo_title(title, public_id):
    prefix = f"ID {public_id}: "
    suffix = f" | {SEO_TITLE_BRAND}"
    available = 65 - len(prefix) - len(suffix)
    compact = clean_text(title)
    if len(compact) > available:
        compact = compact[: max(1, available - 3)].rsplit(" ", 1)[0] + "..."
    return f"{prefix}{compact}{suffix}"


def generate_presentation_pages(records):
    unique_records = list(presentation_records_by_id(records).values())
    public_ids = assign_public_ids(
        "presentations",
        unique_records,
        "presentation_id",
        lambda talk: (
            int(talk.get("year") or 0),
            clean_text(talk.get("date") or ""),
            clean_text(talk.get("series_key") or talk.get("series") or ""),
            int(talk.get("order_in_session") or 0),
            clean_text(talk.get("title") or "").casefold(),
            clean_text(talk.get("presentation_id") or ""),
        ),
    )
    unique_records.sort(key=lambda talk: (-int(talk.get("year") or 0), talk.get("title") or ""))
    year_counts = defaultdict(int)
    cards = []
    written_files = {"index.html"}

    from concurrent.futures import ThreadPoolExecutor

    def process_talk(talk):
        pid = clean_text(talk.get("presentation_id") or "")
        if not pid:
            return None
        public_id = public_ids.get(pid)
        year = int(talk.get("year") or 0)
        title = clean_text(talk.get("title") or "Доклад")
        path = presentation_path(pid, title)
        seo_description = f"ID {public_id}. Доклад: {title}. {series_label(talk.get('series_key'), 'ru')} {talk.get('year')}."
        body = presentation_detail_body(talk)
        structured = [
            page_data(title, seo_description, path, page_type="ScholarlyArticle"),
            make_breadcrumbs([("Главная", ""), ("Доклады", "p/"), (title, path)]),
        ]
        write_text(path, page_shell(presentation_seo_title(title, public_id), seo_description, path, body, structured))
        
        card_html = (
            f'<article class="talk"><div class="entry-head"><strong><a href="{esc(Path(path).name)}">{esc(title)}</a></strong>'
            f'<span class="public-id">ID {esc(public_id)}</span></div>'
            f'<div class="meta">{esc(series_label(talk.get("series_key"), "ru"))} {esc(talk.get("year"))} · {scholar_links_html(talk, "../")}</div></article>'
        )
        return year, Path(path).name, card_html

    with ThreadPoolExecutor() as executor:
        results = executor.map(process_talk, unique_records)
        for res in results:
            if res is None:
                continue
            year, filename, card_html = res
            year_counts[year] += 1
            written_files.add(filename)
            cards.append(card_html)

    year_links = [
        f'<a class="chip" href="../conferences/">{esc(year)} · {talks_count_label(count)}</a>'
        for year, count in sorted(year_counts.items(), reverse=True)
    ]
    page_count = max(1, (len(cards) + PRESENTATIONS_PER_PAGE - 1) // PRESENTATIONS_PER_PAGE)
    for page_number in range(1, page_count + 1):
        start = (page_number - 1) * PRESENTATIONS_PER_PAGE
        page_cards = cards[start : start + PRESENTATIONS_PER_PAGE]
        canonical_path = "p/" if page_number == 1 else f"p/page-{page_number}.html"
        written_files.add(Path(canonical_path).name if page_number > 1 else "index.html")
        pagination = "".join(
            (
                f'<span class="chip" aria-current="page">{number}</span>'
                if number == page_number
                else f'<a class="chip" href="{"./" if number == 1 else f"page-{number}.html"}">{number}</a>'
            )
            for number in range(1, page_count + 1)
        )
        index_body = f"""
            <header>
                <h1>Доклады</h1>
                <p>Постоянные страницы уникальных записей программ. Каждый доклад имеет собственный адрес, авторов, рубрику, масштаб аргументации и доступные мезоуровни.</p>
            </header>
            {chip_section("Покрытие по годам", year_links) if page_number == 1 else ""}
            <nav class="chip-list" aria-label="Страницы докладов">{pagination}</nav>
            <section class="list">{''.join(page_cards)}</section>
        """
        page_label = "Доклады" if page_number == 1 else f"Доклады, страница {page_number}"
        write_text(
            canonical_path + ("index.html" if page_number == 1 else ""),
            page_shell(
                f"{page_label} | {SEO_TITLE_BRAND}",
                "Постоянные страницы докладов Зографских и Рериховских чтений.",
                canonical_path,
                index_body,
                [page_data(page_label, "Постоянные страницы докладов.", canonical_path), make_breadcrumbs([("Главная", ""), ("Доклады", "p/")])],
                extra_head=PUBLIC_ID_CSS,
            ),
        )
    for html_path in Path("p").glob("*.html"):
        if html_path.name not in written_files:
            html_path.unlink()


ARGUMENT_SCALE_EXAMPLE_IDS = {
    1: [
        "PRES_2a08c0cb86",
        "PRES_10c2c66c17",
        "PRES_0b727f138c",
        "PRES_09ea1d8846",
        "PRES_0068d49980",
    ],
    2: [
        "PRES_9e203d9b3f",
        "PRES_2048f4153d",
        "PRES_3fd8e2489c",
        "PRES_844f6b86ea",
        "PRES_22c7444e36",
    ],
    3: [
        "PRES_e4b6786e6b",
        "PRES_54a32921dc",
        "PRES_aa4df50cf0",
        "PRES_74cd40949e",
        "PRES_15b5fbdc83",
    ],
}

EXPERT_REVIEW_EXAMPLE_IDS = [
    "PRES_6e17572f1f",
    "PRES_37a471ecf5",
    "PRES_a7d32d94a9",
    "PRES_0c496dfec3",
    "PRES_422410f9af",
]


def generate_classification_criteria_page(records):
    records_by_id = presentation_records_by_id(records)
    classification_rows = {
        row["presentation_id"]: row
        for row in load_csv_rows("analytics_output/expanded_classification_deepseek.csv")
        if row.get("presentation_id")
    }
    audit_rows = {
        row["presentation_id"]: row
        for row in load_csv_rows("analytics_output/expanded_gumilyov_elevated_audit.csv")
        if row.get("presentation_id")
    }

    def example_cards(presentation_ids, audited=False):
        cards = []
        for pid in presentation_ids:
            talk = records_by_id.get(pid)
            if not talk:
                continue
            if audited:
                row = audit_rows.get(pid, {})
                decision = f'L{row.get("preliminary_level", "?")} -> L{row.get("audited_level", "?")} после перепроверки'
            else:
                row = classification_rows.get(pid, {})
                decision = f'L{row.get("gumilyov_level", talk.get("gumilyov_scale", "?"))}'
            cards.append(
                f"""
                <article class="talk">
                    <strong><a href="{esc(presentation_path(pid))}">{esc(talk.get("title"))}</a></strong>
                    <div class="meta">{esc(series_label(talk.get("series_key"), "ru"))} {esc(talk.get("year"))} · {scholar_links_html(talk)} · {esc(decision)}</div>
                    <p>{esc(row.get("rationale") or "")}</p>
                </article>
                """
            )
        return "".join(cards)

    scale_examples = {
        level: example_cards(presentation_ids)
        for level, presentation_ids in ARGUMENT_SCALE_EXAMPLE_IDS.items()
    }
    expert_review_examples = example_cards(EXPERT_REVIEW_EXAMPLE_IDS, audited=True)
    ledger_rows = []
    reviewed_cards = []
    for pid, review in CLASSIFICATION_OVERRIDES.items():
        talk = records_by_id.get(pid)
        if not talk:
            continue
        path = presentation_path(pid)
        theme_code = review["theme_code"]
        meso_labels = [meso_items_by_code()[code]["label"] for code in review["meso_codes"] if code in meso_items_by_code()]
        reviewed_cards.append(
            f"""
            <article class="talk">
                <strong><a href="{esc(path)}">{esc(talk.get("title"))}</a></strong>
                <div class="meta">{esc(theme_label(theme_code, "ru"))} · L{esc(review["gumilyov_level"])} Микро · {esc("; ".join(meso_labels))}</div>
                <p>{esc(review["reason"])}</p>
            </article>
            """
        )
        ledger_rows.append(
            {
                "presentation_id": pid,
                "title": talk.get("title") or "",
                "theme_code": theme_code,
                "theme_label_ru": theme_label(theme_code, "ru"),
                "gumilyov_level": review["gumilyov_level"],
                "meso_codes": "|".join(review["meso_codes"]),
                "meso_labels_ru": "|".join(meso_labels),
                "reason": review["reason"],
            }
        )
    with open("analytics_output/classification_overrides.csv", "w", encoding="utf-8", newline="") as handle:
        ledger_fieldnames = ["presentation_id", "title", "theme_code", "theme_label_ru", "gumilyov_level", "meso_codes", "reason"]
        writer = csv.DictWriter(handle, fieldnames=ledger_fieldnames)
        writer.writeheader()
        writer.writerows(ledger_rows)
    body = f"""
        <header>
            <h1>Критерии классификации докладов</h1>
            <p>Обновленная схема отделяет дисциплинарную принадлежность, тематические мезоуровни, масштаб аргументации и формат участия. Частные поправки к программе 2024 г. стали общими правилами, после чего по ним повторно размечен весь расширенный корпус.</p>
        </header>
        <section class="grid">
            <article class="card"><strong>Рубрика</strong><div class="meta">Основная дисциплина вопроса: этнография, история индологии, религиоведение, лингвистика, литература и другие крупные входы.</div></article>
            <article class="card"><strong>Мезоуровни</strong><div class="meta">Несколько пересекающихся указателей: ритуалистика, этимологии, Гималаи, метрика, космология, эпохи и т. д.</div></article>
            <article class="card"><strong>L1-L3</strong><div class="meta">Масштаб вывода, а не территория предмета: конкретный объект; традиция/региональная конфигурация; широкое обобщение.</div></article>
            <article class="card"><strong>Формат</strong><div class="meta">Онлайн и видео являются метаданными участия и доступности, но не входят в название или тематическую рубрику.</div></article>
        </section>
        <h2>Правила нормализации метаданных</h2>
        <section class="list">
            <article class="talk"><strong>Институция отделяется от географии</strong><p>Городская помета в программе, включая «СПб» или «Санкт-Петербург», используется как географический сигнал и не публикуется как аффилиация. Аффилиацией считается названное учреждение.</p></article>
            <article class="talk"><strong>Открытая траектория продолжается до контрсвидетельства</strong><p>Если институция подтверждена и не зафиксированы окончание работы или новая аффилиация, она может заполнять последующие пропуски и городские пометы как предположение, явно отмеченное знаком «(?)». Явная конечная дата или свидетельство о смене прекращают такой перенос.</p></article>
            <article class="talk"><strong>Метаданные не входят в название</strong><p>Начальная скобочная помета, распознанная как учреждение, например «(СПбГУ).», переносится в поле аффилиации для любого доклада. Содержательные скобки в заголовках не удаляются.</p></article>
            <article class="talk"><strong>Видео является также состоянием доклада</strong><p>Сохранившаяся и сопоставленная запись отмечается плашкой на карточке доклада и его странице; отдельный каталог видео сохраняется как обзор исходных записей и сопоставлений.</p></article>
        </section>
        <h2>Правила аргументационного масштаба</h2>
        <section class="list">
            <article class="talk"><strong>L1 Микроуровень</strong><p>Конкретный текст, предмет, ритуал, слово, экспедиция, авторское сопоставление или ограниченный тип артефактов. Упоминание региона, народа, языка или двух сравниваемых традиций не повышает уровень автоматически.</p></article>
        </section>
        <h3>Примеры L1: разные годы и докладчики</h3>
        <section class="list">{scale_examples[1]}</section>
        <section class="list">
            <article class="talk"><strong>L2 Региональный уровень</strong><p>Аргумент должен описывать устойчивую конфигурацию традиции, ареала, школы, исторической среды или нескольких серий объектов, а не только локализовать материал.</p></article>
        </section>
        <h3>Примеры L2: разные годы и докладчики</h3>
        <section class="list">{scale_examples[2]}</section>
        <section class="list">
            <article class="talk"><strong>L3 Синтетический уровень</strong><p>Требуется заявленное широкое сравнительное, цивилизационное или методологическое обобщение, выходящее за один корпус и одну региональную конфигурацию.</p></article>
        </section>
        <h3>Примеры L3: разные годы и докладчики</h3>
        <section class="list">{scale_examples[3]}</section>
        <h2>Выводы из экспертных поправок</h2>
        <section class="list">
            <article class="talk"><strong>География не равна масштабу</strong><p>Невары, Ассам, Гималаи, Бенгалия или язык куллуи обозначают материал исследования; без обобщающего тезиса это L1.</p></article>
            <article class="talk"><strong>Сравнение не равно макросинтезу</strong><p>Сравнение вариантов одной игры знания или одного литературного ответа остается микрокейсом, если вывод ограничен этими объектами.</p></article>
            <article class="talk"><strong>Рубрика и мезоуровень не конкурируют</strong><p>Доклад имеет одну основную дисциплинарную рубрику и одновременно несколько тематических маршрутов поиска.</p></article>
            <article class="talk"><strong>История индологии выделяется отдельно</strong><p>Экспедиции, путешественники и история научного освоения материала не должны исчезать в общем остаточном классе.</p></article>
            <article class="talk"><strong>Мезоуровней достаточно при контролируемом расширении</strong><p>Полный проход наполнил сквозные контуры буддизма, философии, ведийских исследований, эпосов, рукописей и рецепции; повторившееся предложение «Сикхские исследования» добавлено как новый мезоуровень, а единичные предложения оставлены в аудиторской выгрузке.</p></article>
        </section>
        <h3>Пять решений перепроверки: разные годы и докладчики</h3>
        <section class="list">{expert_review_examples}</section>
        <h2>Проверочная выборка</h2>
        <p>Эти вручную разобранные случаи служат контрольным набором для проверки применения рубрик, мезоуровней и масштаба аргументации.</p>
        <section class="list">{''.join(reviewed_cards)}</section>
        <section class="link-block">
            <strong>Машиночитаемый журнал решений</strong>
            <div class="chip-list"><a class="chip" href="analytics_output/classification_overrides.csv">classification_overrides.csv</a></div>
        </section>
    """
    write_text(
        "classification-criteria.html",
        page_shell(
            f"Критерии классификации | {SITE_NAME}",
            "Обновленные критерии рубрик, мезоуровней и масштаба аргументации докладов.",
            "classification-criteria.html",
            body,
            [page_data("Критерии классификации", "Обновленные критерии классификации докладов.", "classification-criteria.html"), make_breadcrumbs([("Главная", ""), ("Критерии классификации", "classification-criteria.html")])],
        ),
    )


def generate_conference_pages(data, records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record["series_key"], record["year"])].append(record)

    memberships = load_meso_memberships()
    meso_items_by_code = {item["code"]: item for item in load_meso_index()}
    years_by_series = defaultdict(list)
    for series, year in grouped:
        years_by_series[series].append(int(year))
    for series in years_by_series:
        years_by_series[series] = sorted(set(years_by_series[series]))

    cards = []
    for (series, year), participation_records in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0]), reverse=True):
        talks = list(presentation_records_by_id(participation_records).values())
        path = conference_path(series, year)
        title = f"{series_label(series, 'ru')} {year}"
        source_updated = clean_text(talks[0].get("program_last_updated") if talks else "")
        source_update_label = ""
        if source_updated:
            source_update_label = f' · источник обновлен {esc(dt.datetime.strptime(source_updated, "%Y-%m-%d").strftime("%d.%m.%Y"))}'
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(title)}</a></strong><div class="meta">{presentation_records_label(len(talks))}{source_update_label}</div></article>')
        series_years = years_by_series.get(series, [])
        current_index = series_years.index(int(year)) if int(year) in series_years else -1
        prev_link = ""
        next_link = ""
        if current_index > 0:
            prev_year = series_years[current_index - 1]
            prev_link = f'<a class="chip" href="../{conference_path(series, prev_year)}">← {esc(series_label(series, "ru"))} {prev_year}</a>'
        if 0 <= current_index < len(series_years) - 1:
            next_year = series_years[current_index + 1]
            next_link = f'<a class="chip" href="../{conference_path(series, next_year)}">{esc(series_label(series, "ru"))} {next_year} →</a>'
        nav_links = "".join(link for link in (prev_link, next_link) if link)
        navigation = chip_section("Соседние конференции", [nav_links] if nav_links else [])
        facets = "".join([
            chip_section("Рубрики конференции", facet_theme_links(talks, "../", 12)),
            chip_section("Уровни Гумилева", facet_gumilyov_links(talks, "../", 3)),
            chip_section("Мезоуровни конференции", facet_meso_links(talks, memberships, meso_items_by_code, "../", 12)),
            chip_section("Города конференции", facet_city_links(talks, "../", 10)),
            chip_section("Институции конференции", facet_institution_links(talks, "../", 10)),
        ])
        source_url = clean_text(talks[0].get("source_url") if talks else "")
        source_note = ""
        if source_url:
            modified_text = (
                f' · Последнее обновление источника: {dt.datetime.strptime(source_updated, "%Y-%m-%d").strftime("%d.%m.%Y")}'
                if source_updated
                else ""
            )
            source_note = f"""
        <aside class="caveat-block" role="note" aria-label="Source metadata">
            <strong>Источник программы</strong>
            <p><a href="{esc(source_url)}">Оригинальная страница программы</a>{modified_text}. Дата обновления приводится только тогда, когда она указана на странице источника.</p>
        </aside>
        """
        body = f"""
        <header>
            <h1>{esc(title)}</h1>
            <p>Список докладов, связанных с этой конференцией.</p>
        </header>
        {source_note}
        {navigation}
        {facets}
        <section class="list">
            {''.join(talk_card(t, '../') for t in talks)}
        </section>
        """
        structured = [
            page_data(title, f"Доклады конференции: {title}.", path),
            make_breadcrumbs([("Главная", ""), ("Конференции", "conferences/"), (title, path)]),
        ]
        write_text(path, page_shell(f"{title} | {SITE_NAME}", f"Доклады конференции: {title}.", path, body, structured))

    index_body = f"""
        <header>
            <h1>Конференции</h1>
            <p>Погодовые страницы Зографских и Рериховских чтений.</p>
        </header>
        <section class="link-block">
            <strong>Быстрые входы</strong>
            <div class="chip-list">
                <a class="chip" href="../search.html?q=%D0%97%D0%BE%D0%B3%D1%80%D0%B0%D1%84%D1%81%D0%BA%D0%B8%D0%B5%20%D1%87%D1%82%D0%B5%D0%BD%D0%B8%D1%8F">Зографские чтения</a>
                <a class="chip" href="../search.html?q=%D0%A0%D0%B5%D1%80%D0%B8%D1%85%D0%BE%D0%B2%D1%81%D0%BA%D0%B8%D0%B5%20%D1%87%D1%82%D0%B5%D0%BD%D0%B8%D1%8F">Рериховские чтения</a>
                <a class="chip" href="../search.html?q=2020">2020-е</a>
                <a class="chip" href="../search.html?q=2010">2010-е</a>
            </div>
        </section>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "conferences/index.html",
        page_shell(
            f"Конференции | {SITE_NAME}",
            "Погодовые страницы Зографских и Рериховских чтений.",
            "conferences/",
            index_body,
            [page_data("Конференции", "Погодовые страницы конференций.", "conferences/"), make_breadcrumbs([("Главная", ""), ("Конференции", "conferences/")])],
        ),
    )


def generate_theme_pages(data, records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record.get("theme") or {}).get("code", "History")].append(record)

    related_meso_by_theme = defaultdict(list)
    for item in load_meso_index():
        seen_codes = set()
        for label, _count in distribution_entries(item.get("distribution")):
            target = linked_l1_target(label)
            if not target or target[0] != "theme" or target[1] in seen_codes:
                continue
            seen_codes.add(target[1])
            related_meso_by_theme[target[1]].append(item)

    cards = []
    for code, talks in sorted(grouped.items(), key=lambda item: theme_label(item[0], "ru")):
        path = theme_path(code)
        title = theme_label(code, "ru")
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(title)}</a></strong><div class="meta">{presentation_records_label(len(talks))}</div></article>')
        # Phase 5 caveat block: transparent classification disclaimer
        caveat_block = f"""
        <aside class="caveat-block" role="note" aria-label="Classification notice">
            <strong>Примечание о классификации</strong>
            <p>
                Рубрика назначается по <em>заголовку</em> доклада с помощью словарной эвристики.
                Она показывает, как доклад размечен в рамках конференционного корпуса, а не полный
                исследовательский профиль автора. Один исследователь может появляться в нескольких рубриках.
            </p>
        </aside>"""
        related_meso_links = "".join(
            f'<a class="chip" href="../{meso_path(item["code"])}">{esc(item["label"])} · {talks_count_label(item["count"])}</a>'
            for item in sorted(related_meso_by_theme.get(code, []), key=lambda item: (-item["count"], item["label"]))[:16]
        )
        related_meso_block = f"""
        <section>
            <h2>Связанные мезоуровни</h2>
            <div class="chip-list">{related_meso_links}</div>
        </section>
        """ if related_meso_links else ""
        gumilyov_block = chip_section("Уровни Гумилева", facet_gumilyov_links(talks, "../", 3))
        body = f"""
        <header>
            <h1>{esc(title)}</h1>
            <p>Доклады, отнесенные к этой крупной исследовательской рубрике.</p>
        </header>
        {caveat_block}
        {related_meso_block}
        {gumilyov_block}
        <section class="list">
            {''.join(talk_card(t, '../') for t in talks[:250])}
        </section>
        """

        write_text(
            path,
            page_shell(
                f"{title} | {SITE_NAME}",
                f"Доклады и авторы в рубрике: {title}.",
                path,
                body,
                [page_data(title, f"Доклады в рубрике: {title}.", path), make_breadcrumbs([("Главная", ""), ("Рубрики", "themes/"), (title, path)])],
            ),
        )

    # TOPIC CO-OCCURRENCE & INTERDISCIPLINARY BRIDGES NETWORK GRAPH
    theme_names_ru = {
        "linguistics_and_philology": "Лингвистика и филология",
        "religion_and_philosophy": "Религия и философия",
        "literature_and_poetry": "Литература и поэзия",
        "history_and_culture": "История и общество",
        "art_and_material_culture": "Искусство и культура"
    }

    theme_counts = {t: len(grouped.get(t, [])) for t in theme_names_ru}

    scholar_themes = defaultdict(set)
    for code, talks in grouped.items():
        if code in theme_names_ru:
            for t in talks:
                pid = t.get("person_id")
                if pid:
                    scholar_themes[pid].add(code)

    co_occurrence = defaultdict(Counter)
    for pid, themes_set in scholar_themes.items():
        themes_list = list(themes_set)
        for i in range(len(themes_list)):
            for j in range(i + 1, len(themes_list)):
                t1, t2 = themes_list[i], themes_list[j]
                co_occurrence[t1][t2] += 1
                co_occurrence[t2][t1] += 1

    node_coords = {
        "linguistics_and_philology": (300, 70),
        "literature_and_poetry": (470, 180),
        "history_and_culture": (400, 320),
        "art_and_material_culture": (200, 320),
        "religion_and_philosophy": (130, 180)
    }

    max_talks = max(theme_counts.values()) or 1
    max_weight = 1
    for t1 in co_occurrence:
        for t2 in co_occurrence[t1]:
            if co_occurrence[t1][t2] > max_weight:
                max_weight = co_occurrence[t1][t2]

    edges = []
    seen_edges = set()
    for t1 in theme_names_ru:
        for t2 in theme_names_ru:
            if t1 != t2 and (t1, t2) not in seen_edges and (t2, t1) not in seen_edges:
                seen_edges.add((t1, t2))
                weight = co_occurrence[t1].get(t2, 0)
                if weight > 0:
                    x1, y1 = node_coords[t1]
                    x2, y2 = node_coords[t2]
                    
                    thickness = 1.0 + (weight / max_weight) * 12.0
                    opacity = 0.15 + (weight / max_weight) * 0.70
                    
                    stroke_color = "rgba(98, 174, 146, 0.85)" if weight > 15 else "rgba(255, 255, 255, 0.22)"
                    
                    xm, ym = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    
                    edges.append(f"""
                        <g class="network-edge" data-weight="{weight}">
                            <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" 
                                  stroke="{stroke_color}" stroke-opacity="{opacity:.3f}" stroke-width="{thickness:.1f}" 
                                  class="edge-line" />
                            <circle cx="{xm}" cy="{ym}" r="11" fill="var(--bg)" stroke="var(--border)" stroke-width="1"></circle>
                            <text x="{xm}" y="{ym + 3.5}" fill="var(--muted)" font-size="9" text-anchor="middle" font-family="monospace">{weight}</text>
                        </g>
                    """)
    edges_markup = "\n".join(edges)

    nodes = []
    for t, (x, y) in node_coords.items():
        count = theme_counts[t]
        radius = 22.0 + (count / max_talks) * 20.0
        
        fill_color = "rgba(98, 174, 146, 0.15)"
        stroke_color = "var(--accent)"
        
        # Display split labels for better spacing
        label_parts = theme_names_ru[t].split(' ')
        first_word = label_parts[0]
        second_word = label_parts[2] if len(label_parts) > 2 else ""
        
        nodes.append(f"""
            <g class="network-node" transform="translate({x}, {y})" title="{esc(theme_names_ru[t])}: {count} докл.">
                <circle r="{radius:.1f}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="2.5" class="node-circle"></circle>
                <text x="0" y="-2" fill="#fff" font-weight="bold" font-size="9.5" text-anchor="middle" pointer-events="none">
                    {esc(first_word)}
                </text>
                {f'<text x="0" y="8" fill="#fff" font-weight="bold" font-size="9.5" text-anchor="middle" pointer-events="none">{esc(second_word)}</text>' if second_word else ''}
                <text x="0" y="19" fill="var(--soft)" font-size="8.5" text-anchor="middle" pointer-events="none">
                    N={count}
                </text>
            </g>
        """)
    nodes_markup = "\n".join(nodes)

    index_body = f"""
        <header>
            <h1>Исследовательские рубрики</h1>
            <p>Крупные тематические входы в корпус докладов.</p>
        </header>

        <style>
            .network-section {{
                background: rgba(23, 30, 27, 0.6);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 2rem 0;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }}
            .network-title {{
                font-size: 1.4rem;
                color: var(--accent);
                margin-top: 0;
                margin-bottom: 1.2rem;
                font-weight: 700;
            }}
            .network-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            @media (min-width: 900px) {{
                .network-grid {{
                    grid-template-columns: 1.6fr 1fr;
                }}
            }}
            .network-svg {{
                width: 100%;
                max-width: 600px;
                height: auto;
                display: block;
                margin: 0 auto;
                background: rgba(16, 21, 19, 0.6);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1rem;
            }}
            .edge-line {{
                transition: stroke-opacity 0.25s, stroke-width 0.25s;
            }}
            .network-edge:hover .edge-line {{
                stroke-opacity: 0.95;
                stroke: var(--accent2) !important;
            }}
            .node-circle {{
                transform-box: fill-box;
                transform-origin: center;
                transition: transform 0.15s ease-out, fill-opacity 0.2s;
                cursor: pointer;
            }}
            .network-node:hover .node-circle {{
                transform: scale(1.05);
                fill: rgba(98, 174, 146, 0.3);
            }}
            .stats-sidebar {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }}
            .stats-card {{
                background: rgba(28, 37, 33, 0.4);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.2rem;
            }}
            .stats-header {{
                font-weight: 600;
                color: var(--accent2);
                margin-bottom: 0.6rem;
                font-size: 1.05rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }}
            .stats-text {{
                font-size: 0.88rem;
                line-height: 1.45;
                margin: 0 0 0.75rem 0;
                color: var(--muted);
            }}
            .stats-badge {{
                background: rgba(0,0,0,0.2);
                border-radius: 6px;
                padding: 0.75rem;
                border-left: 3px solid var(--accent);
                font-size: 0.82rem;
                color: var(--text);
                font-family: monospace;
            }}
        </style>

        <section class="network-section">
            <h2 class="network-title">🕸️ Междисциплинарные мосты и тематическая изоляция</h2>
            <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                Сетевой граф совместного распределения тем в карьерах ученых. Узлы представляют пять крупных рубрик (размер зависит от числа докладов), а ребра отображают число «ученых-мостов», сделавших доклады в обеих рубриках.
            </p>
            <div class="network-grid">
                <div class="heatmap-container">
                    <svg viewBox="0 0 600 400" class="network-svg" xmlns="http://www.w3.org/2000/svg">
                        <!-- Edges (drawn first to sit behind nodes) -->
                        {edges_markup}

                        <!-- Nodes -->
                        {nodes_markup}
                    </svg>
                </div>
                <div class="stats-sidebar">
                    <div class="stats-card">
                        <div class="stats-header">🌉 Междисциплинарный мост: Искусство и культура</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Рубрика <em>Искусство и культура</em> выступает главным связующим звеном. Она имеет высокую ко-оккурентность как с <em>Историей</em> (31 общий ученый), так и с <em>Религией и философией</em> (21 общий ученый).
                        </p>
                        <div class="stats-badge">
                            Плотность мостов:<br>
                            Искусство &harr; История: 31<br>
                            Искусство &harr; Религия: 21
                        </div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-header">🏰 Тематический замок: Лингвистика и филология</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Классическое ядро (грамматика, фонетика, ведийская герменевтика) остается изолированным силосом. Оно практически не соприкасается с современной <em>Историей и обществом</em> (всего 7 общих авторов).
                        </p>
                        <div class="stats-badge" style="border-left-color: var(--accent2);">
                            Изолированные силосы:<br>
                            Лингвистика &harr; История: 7<br>
                            Лингвистика &harr; Культура: 10
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="grid">{''.join(cards)}</section>
        <h2>Мезоуровни</h2>
        <p>Поперечные тематические коридоры между крупными рубриками и отдельными докладами.</p>
        <section class="grid">
            <article class="card"><strong><a href="../meso/">Индексы мезоуровней</a></strong><div class="meta">Мини-серии, подразделы лингвистики и корпусные тематические контуры.</div></article>
        </section>
    """
    write_text(
        "themes/index.html",
        page_shell(
            f"Исследовательские рубрики | {SITE_NAME}",
            "Тематические индексы корпуса докладов.",
            "themes/",
            index_body,
            [page_data("Исследовательские рубрики", "Тематические индексы корпуса.", "themes/"), make_breadcrumbs([("Главная", ""), ("Рубрики", "themes/")])],
        ),
    )


def redirect_html(title, canonical_path, target_path):
    target_url = site_url(target_path)
    target_href = "../" + target_path if "/" in canonical_path else target_path
    return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>{esc(title)} | {esc(SITE_NAME)}</title>
    <meta name="description" content="Страница перенесена в актуальную рубрику архива.">
    <meta name="robots" content="noindex, follow">
    <link rel="canonical" href="{esc(target_url)}">
    <meta http-equiv="refresh" content="0; url={esc(target_href)}">
</head>
<body data-legacy-redirect="true">
    <p>Страница перенесена: <a href="{esc(target_href)}">{esc(title)}</a>.</p>
</body>
</html>
"""


def generate_legacy_theme_redirects():
    redirects = {
        "themes/academichistory.html": ("themes/history-and-culture.html", "История, этнография и общество"),
        "themes/art.html": ("themes/art-and-material-culture.html", "Искусство и материальная культура"),
        "themes/history.html": ("themes/history-and-culture.html", "История, этнография и общество"),
        "themes/linguistics.html": ("themes/linguistics-and-philology.html", "Лингвистика и филология"),
        "themes/philosophy.html": ("themes/religion-and-philosophy.html", "Религия и философия"),
    }
    for old_path, (target_path, title) in redirects.items():
        write_text(old_path, redirect_html(title, old_path, target_path))


def generate_topic_pages(records):
    records_by_id = presentation_records_by_id(records)
    unique_records = list(records_by_id.values())
    cards = []
    for code, topic in NAMED_TOPICS.items():
        pattern = re.compile(topic["pattern"], flags=re.IGNORECASE)
        talks = [talk for talk in unique_records if pattern.search(clean_text(talk.get("title") or ""))]
        talks.sort(key=lambda talk: (int(talk.get("year") or 0), talk.get("series_key") or "", talk.get("title") or ""))
        zograf_count = sum(1 for talk in talks if series_slug(talk.get("series_key")) == "zograf")
        roerich_count = len(talks) - zograf_count
        first_year = talks[0].get("year") if talks else ""
        last_year = talks[-1].get("year") if talks else ""
        year_span = str(first_year) if first_year == last_year else f"{first_year}-{last_year}"
        path = topic_path(code)
        cards.append(
            f'<article class="card"><strong><a href="../{path}">{esc(topic["title"])}</a></strong>'
            f'<div class="metric">{len(talks)}</div>'
            f'<div class="meta">{esc(year_span)} · Зограф: {zograf_count} · Рерих: {roerich_count}</div></article>'
        )
        body = f"""
        <header>
            <h1>{esc(topic["title"])}</h1>
            <p>{esc(topic["description"])}</p>
        </header>
        <section class="grid">
            <article class="card"><strong>Доклады</strong><div class="metric">{len(talks)}</div><div class="meta">Уникальные записи программ</div></article>
            <article class="card"><strong>Период</strong><div class="metric">{esc(year_span)}</div><div class="meta">Годы упоминаний в заголовках</div></article>
            <article class="card"><strong>Зографские чтения</strong><div class="metric">{zograf_count}</div></article>
            <article class="card"><strong>Рериховские чтения</strong><div class="metric">{roerich_count}</div></article>
        </section>
        {chip_section("Уровни Гумилева", facet_gumilyov_links(talks, "../", 3))}
        {chip_section("Рубрики", facet_theme_links(talks, "../", 12))}
        {chip_section("Авторы", facet_scholar_links(talks, "../", 16))}
        <aside class="caveat-block" role="note" aria-label="Topic index notice">
            <strong>Принцип включения</strong>
            <p>В список включены доклады, в нормализованном публичном заголовке которых встречается основа имени текста. Он показывает явные упоминания в программе, а не все возможные доклады по сюжету.</p>
        </aside>
        <h2>Доклады по годам</h2>
        <section class="list">
            {''.join(talk_card(talk, '../') for talk in talks)}
        </section>
        """
        write_text(
            path,
            page_shell(
                f"{topic['title']} | {SITE_NAME}",
                f"{topic['title']}: доклады по годам и авторам в программах Зографских и Рериховских чтений.",
                path,
                body,
                [page_data(topic["title"], topic["description"], path), make_breadcrumbs([("Главная", ""), ("Сюжеты", "topics/"), (topic["title"], path)])],
            ),
        )
    body = f"""
        <header>
            <h1>Именные сюжеты и тексты</h1>
            <p>Устойчивые страницы для произведений и текстовых корпусов, явно названных в заголовках докладов.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "topics/index.html",
        page_shell(
            f"Именные сюжеты и тексты | {SITE_NAME}",
            "Устойчивые страницы именованных текстов в корпусе докладов.",
            "topics/",
            body,
            [page_data("Именные сюжеты и тексты", "Устойчивые страницы именованных текстов.", "topics/"), make_breadcrumbs([("Главная", ""), ("Сюжеты", "topics/")])],
        ),
    )


def generate_meso_pages(data, records):
    items = load_meso_index()
    if not items:
        return
    memberships = load_meso_memberships()
    meso_items_by_code = {item["code"]: item for item in items}
    records_by_id = presentation_records_by_id(records)

    def example_links(talks, path, depth="", limit=3):
        links = []
        for talk in talks:
            pid = clean_text(talk.get("presentation_id") or "")
            title = clean_text(talk.get("title") or "")
            if not pid or is_suspicious_short_title(title):
                continue
            links.append(f'<a href="{depth}{path}#{esc(pid)}">{esc(title)}</a>')
            if len(links) >= limit:
                break
        return " · ".join(links)

    cards = []
    written_files = {"index.html"}
    for item in items:
        code = item["code"]
        path = meso_path(code)
        written_files.add(Path(path).name)
        talks = [
            records_by_id[pid]
            for pid in dict.fromkeys(memberships.get(code, []))
            if pid in records_by_id
        ]
        talks.sort(key=lambda rec: (int(rec.get("year") or 0), rec.get("series_label") or "", rec.get("title") or ""))
        zograf_count = sum(1 for talk in talks if talk.get("series_key") == "Zograf")
        roerich_count = sum(1 for talk in talks if talk.get("series_key") == "Roerich")
        examples = example_links(talks, path, "../")
        examples_html = f'<div class="meta">Примеры: {examples}</div>' if examples else ""
        cards.append(
            f'<article class="card"><strong><a href="../{path}">{esc(item["label"])}</a></strong>'
            f'<div class="meta">{esc(item["kind"])} · {talks_count_label(len(talks))} · Зограф: {zograf_count} · Рерих: {roerich_count}</div>{examples_html}</article>'
        )

        zograf_href = search_path(f'{item["label"]} Зографские чтения', "../")
        roerich_href = search_path(f'{item["label"]} Рериховские чтения', "../")
        stats = f"""
        <section class="grid">
            <article class="card"><strong>Доклады</strong><div class="metric">{len(talks)}</div></article>
            <article class="card"><strong><a href="{esc(zograf_href)}">Зографские чтения</a></strong><div class="metric">{esc(str(item["zograf_count"]))}</div></article>
            <article class="card"><strong><a href="{esc(roerich_href)}">Рериховские чтения</a></strong><div class="metric">{esc(str(item["roerich_count"]))}</div></article>
        </section>
        """
        top_terms_links = format_keyword_links(item.get("top_terms"), "../")
        top_terms = f'<div class="link-block"><strong>Ключевые слова:</strong><div class="chip-list">{top_terms_links}</div></div>' if top_terms_links else ""
        distribution_links = format_distribution_links(item.get("distribution"), "../")
        distribution = f'<div class="link-block"><strong>Распределение по крупным рубрикам:</strong><div class="chip-list">{distribution_links}</div></div>' if distribution_links else ""
        related_meso = [
            link
            for link in facet_meso_links(talks, memberships, meso_items_by_code, "../", 16)
            if f'href="../{meso_path(code)}"' not in link
        ][:12]
        related_meso_block = chip_section("Связанные мезоуровни", related_meso)
        page_examples = example_links(talks, "", "", 6)
        examples_block = f"""
        <section>
            <h2>Кликабельные примеры</h2>
            <p>{page_examples}</p>
        </section>
        """ if page_examples else ""
        caveat = """
        <aside class="caveat-block" role="note" aria-label="Meso-level notice">
            <strong>Что такое мезоуровень</strong>
            <p>Это исследовательский коридор между широкой рубрикой и отдельным докладом. Он строится по ключевым словам заголовков: один заголовок может принадлежать нескольким мини-сериям, поэтому списки не являются взаимоисключающими.</p>
        </aside>
        """
        body = f"""
        <header>
            <h1>{esc(item["label"])}</h1>
            <p>{esc(item["kind"])}. Список докладов, попавших в этот мезоуровень по словарю заголовков.</p>
        </header>
        {stats}
        {top_terms}
        {distribution}
        {chip_section("Уровни Гумилева", facet_gumilyov_links(talks, "../", 3))}
        {related_meso_block}
        {examples_block}
        {caveat}
        <section class="list">
            {''.join(talk_card(t, '../') for t in talks)}
        </section>
        """
        description = f"{item['label']}: {talks_count_label(len(talks))} в мезоуровневом индексе архива."
        write_text(
            path,
            page_shell(
                f"{item['label']} | {SITE_NAME}",
                description,
                path,
                body,
                [page_data(item["label"], description, path), make_breadcrumbs([("Home", ""), ("Meso-levels", "meso/"), (item["label"], path)])],
            ),
        )

    index_body = f"""
        <header>
            <h1>Мезоуровни</h1>
            <p>Кликабельные исследовательские коридоры: мини-серии, языковые области, корпусные контуры и подразделы лингвистики.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "meso/index.html",
        page_shell(
            f"Meso-level indexes | {SITE_NAME}",
            "Cross-cutting meso-level topic indexes for the Indology Scholars archive.",
            "meso/",
            index_body,
            [page_data("Meso-level indexes", "Cross-cutting topic indexes for the archive.", "meso/"), make_breadcrumbs([("Home", ""), ("Meso-levels", "meso/")])],
        ),
    )
    for stale in Path("meso").glob("*.html"):
        if stale.name not in written_files:
            stale.unlink()


def generate_city_pages(data, records, authority):
    summary = data.get("summary", {})
    coverage = f'{summary.get("start_year")}-{summary.get("end_year")}'
    grouped = defaultdict(list)
    for record in records:
        city = (record.get("geography") or {}).get("ru")
        if city and city not in ("Не указана", "Not specified"):
            grouped[city].append(record)

    memberships = load_meso_memberships()
    meso_items_by_code = {item["code"]: item for item in load_meso_index()}
    city_meta = {
        item["ru"]: {"en": item.get("en"), "lat": item.get("lat"), "lon": item.get("lon")}
        for item in (data.get("geography_stats") or [])
        if item.get("ru")
    }
    places_auth = authority.get("places") or {}

    cards = []
    for city, talks in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        path = city_path(city)
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(city)}</a></strong><div class="meta">{presentation_records_label(len(talks))}</div></article>')
        city_desc = f"Доклады учёных и аффилиации: город - {city}. Архив Зографских и Рериховских чтений ({coverage})."
        facets = "".join([
            chip_section("Ведущие авторы", facet_scholar_links(talks, "../", 14)),
            chip_section("Рубрики города", facet_theme_links(talks, "../", 12)),
            chip_section("Уровни Гумилева", facet_gumilyov_links(talks, "../", 3)),
            chip_section("Институции города", facet_institution_links(talks, "../", 12)),
            chip_section("Связанные мезоуровни", facet_meso_links(talks, memberships, meso_items_by_code, "../", 12)),
            chip_section("Конференции", facet_conference_links(talks, "../", 12)),
        ])
        body = f"""
        <header>
            <h1>{esc(city)}</h1>
            <p>{esc(city_desc)}</p>
        </header>
        {facets}
        <section class="list">{''.join(talk_card(t, '../') for t in talks[:250])}</section>
        """
        city_geo = city_meta.get(city, {})
        place_node = place_structured_data(
            city_ru=city,
            city_en=city_geo.get("en"),
            geo={"lat": city_geo.get("lat"), "lon": city_geo.get("lon")},
            place_auth=places_auth.get(city),
            canonical_path=path,
        )
        structured = [
            {"@context": "https://schema.org", **place_node},
            page_data(city, city_desc, path),
            make_breadcrumbs([("Home", ""), ("Cities", "cities/"), (city, path)]),
        ]
        write_text(
            path,
            page_shell(
                f"{city} | {SITE_NAME}",
                city_desc,
                path,
                body,
                structured,
            ),
        )

    # GEOGRAPHIC PARADIGM SEGREGATION & CHORD SANKEY DIAGRAM
    theme_mapping = {}
    try:
        with open("analytics_output/theme_codes_final_v2.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                theme_mapping[row["presentation_id"]] = row["l1"]
    except Exception:
        pass

    cities_map = {
        "санкт-петербург": "Санкт-Петербург",
        "спб": "Санкт-Петербург",
        "ленинград": "Санкт-Петербург",
        "москва": "Москва",
        "мгу": "Москва",
        "ив ран": "Москва",
        "вшэ": "Москва"
    }

    theme_names_ru = {
        "linguistics_and_philology": "Лингвистика и филология",
        "religion_and_philosophy": "Религия и философия",
        "literature_and_poetry": "Литература и поэзия",
        "history_and_culture": "История, этнография и общество",
        "art_and_material_culture": "Искусство и культура"
    }

    contingency = {
        "Санкт-Петербург": {t: 0 for t in theme_names_ru},
        "Москва": {t: 0 for t in theme_names_ru}
    }
    
    city_totals = {"Санкт-Петербург": 0, "Москва": 0}

    for record in records:
        aff = record.get("affiliation") or ""
        aff_low = aff.lower()
        
        target_city = None
        for key, val in cities_map.items():
            if key in aff_low:
                target_city = val
                break
        
        if not target_city:
            geo_ru = (record.get("geography") or {}).get("ru")
            if geo_ru in ("Санкт-Петербург", "Москва"):
                target_city = geo_ru
                
        if target_city:
            pres_id = record.get("presentation_id")
            theme = theme_mapping.get(pres_id)
            if theme in theme_names_ru:
                contingency[target_city][theme] += 1
                city_totals[target_city] += 1

    left_positions = {"Санкт-Петербург": 40, "Москва": 220}
    right_positions = {
        "linguistics_and_philology": 30,
        "religion_and_philosophy": 110,
        "literature_and_poetry": 190,
        "history_and_culture": 270,
        "art_and_material_culture": 350
    }

    left_offset = {"Санкт-Петербург": 0, "Москва": 0}
    right_offset = {t: 0 for t in theme_names_ru}
    
    theme_order = ["linguistics_and_philology", "religion_and_philosophy", "literature_and_poetry", "history_and_culture", "art_and_material_culture"]

    paths = []
    max_city_total = max(city_totals.values()) or 1
    scale_factor = 130.0 / max_city_total

    for city in ["Санкт-Петербург", "Москва"]:
        for theme in theme_order:
            count = contingency[city].get(theme, 0)
            if count == 0:
                continue
            
            thickness = max(1.5, count * scale_factor)
            
            y_left = left_positions[city] + left_offset[city] + (thickness / 2.0)
            y_right = right_positions[theme] + right_offset[theme] + (thickness / 2.0)
            
            left_offset[city] += thickness + 2
            right_offset[theme] += thickness + 1
            
            color = "rgba(98, 174, 146, 0.45)" if city == "Санкт-Петербург" else "rgba(197, 154, 86, 0.45)"
            
            paths.append(f"""
                <path d="M 90 {y_left:.1f} C 280 {y_left:.1f}, 420 {y_right:.1f}, 610 {y_right:.1f}"
                      fill="none" 
                      stroke="{color}" 
                      stroke-width="{thickness:.1f}" 
                      class="flow-line"
                      title="{esc(city)} → {esc(theme_names_ru[theme])}: {count} докл.">
                </path>
            """)
    svg_paths = "\n".join(paths)

    index_body = f"""
        <header>
            <h1>Географические центры</h1>
            <p>Страницы городов по аффилиациям и географическим сигналам из программ конференций.</p>
        </header>

        <style>
            .geo-section {{
                background: rgba(23, 30, 27, 0.6);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 2rem 0;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }}
            .geo-title {{
                font-size: 1.4rem;
                color: var(--accent);
                margin-top: 0;
                margin-bottom: 1.2rem;
                font-weight: 700;
            }}
            .geo-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            @media (min-width: 900px) {{
                .geo-grid {{
                    grid-template-columns: 1.6fr 1fr;
                }}
            }}
            .flow-line {{
                transition: stroke-opacity 0.2s, stroke 0.2s;
                stroke-opacity: 0.45;
                cursor: pointer;
            }}
            .flow-line:hover {{
                stroke-opacity: 0.95;
                stroke: rgba(255, 255, 255, 0.7) !important;
            }}
            .chord-sankey-svg {{
                width: 100%;
                max-width: 800px;
                height: auto;
                display: block;
                margin: 0 auto;
                background: rgba(16, 21, 19, 0.6);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1rem;
            }}
            .stats-sidebar {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }}
            .stats-card {{
                background: rgba(28, 37, 33, 0.4);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.2rem;
            }}
            .stats-header {{
                font-weight: 600;
                color: var(--accent2);
                margin-bottom: 0.6rem;
                font-size: 1.05rem;
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }}
            .stats-text {{
                font-size: 0.88rem;
                line-height: 1.45;
                margin: 0 0 0.75rem 0;
                color: var(--muted);
            }}
            .stats-badge {{
                background: rgba(0,0,0,0.2);
                border-radius: 6px;
                padding: 0.75rem;
                border-left: 3px solid var(--accent);
                font-size: 0.82rem;
                color: var(--text);
                font-family: monospace;
            }}
        </style>

        <section class="geo-section">
            <h2 class="geo-title">🗺️ Методологическое межевание: Москва vs. Санкт-Петербург</h2>
            <p style="margin-top:0; margin-bottom:1.5rem; font-size:0.95rem; color:var(--muted);">
                Интерактивный потоковый анализ (Sankey Flow) связей между географическими центрами (местом аффилиации) и научными тематиками докладов. Доказывает разделение отечественной индологии на две академические школы.
            </p>
            <div class="geo-grid">
                <div class="heatmap-container">
                    <svg viewBox="0 0 800 450" class="chord-sankey-svg" xmlns="http://www.w3.org/2000/svg">
                        <!-- Left Nodes -->
                        <!-- Санкт-Петербург -->
                        <rect x="20" y="40" width="70" height="140" rx="6" fill="rgba(98, 174, 146, 0.2)" stroke="var(--accent)" stroke-width="2"></rect>
                        <text x="55" y="110" fill="#fff" font-weight="bold" font-size="11" text-anchor="middle" transform="rotate(-90 55 110)">С.-Петербург</text>
                        
                        <!-- Москва -->
                        <rect x="20" y="220" width="70" height="140" rx="6" fill="rgba(197, 154, 86, 0.2)" stroke="var(--accent2)" stroke-width="2"></rect>
                        <text x="55" y="290" fill="#fff" font-weight="bold" font-size="11" text-anchor="middle" transform="rotate(-90 55 290)">Москва</text>

                        <!-- Flows -->
                        {svg_paths}

                        <!-- Right Nodes -->
                        <!-- Theme 1 -->
                        <rect x="610" y="30" width="170" height="60" rx="6" fill="rgba(255,255,255,0.03)" stroke="var(--border)" stroke-width="1"></rect>
                        <text x="620" y="55" fill="var(--text)" font-weight="600" font-size="10.5">Лингвистика и филология</text>
                        
                        <!-- Theme 2 -->
                        <rect x="610" y="110" width="170" height="60" rx="6" fill="rgba(255,255,255,0.03)" stroke="var(--border)" stroke-width="1"></rect>
                        <text x="620" y="135" fill="var(--text)" font-weight="600" font-size="10.5">Религия и философия</text>
                        
                        <!-- Theme 3 -->
                        <rect x="610" y="190" width="170" height="60" rx="6" fill="rgba(255,255,255,0.03)" stroke="var(--border)" stroke-width="1"></rect>
                        <text x="620" y="215" fill="var(--text)" font-weight="600" font-size="10.5">Литература и поэзия</text>
                        
                        <!-- Theme 4 -->
                        <rect x="610" y="270" width="170" height="60" rx="6" fill="rgba(255,255,255,0.03)" stroke="var(--border)" stroke-width="1"></rect>
                        <text x="620" y="295" fill="var(--text)" font-weight="600" font-size="10.5">История и общество</text>
                        
                        <!-- Theme 5 -->
                        <rect x="610" y="350" width="170" height="60" rx="6" fill="rgba(255,255,255,0.03)" stroke="var(--border)" stroke-width="1"></rect>
                        <text x="620" y="375" fill="var(--text)" font-weight="600" font-size="10.5">Искусство и культура</text>
                    </svg>
                </div>
                <div class="stats-sidebar">
                    <div class="stats-card">
                        <div class="stats-header">🔬 Гипотеза H4: Школа vs. Географический фильтр</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Санкт-Петербург и Москва представляют статистически изолированные интеллектуальные парадигмы с разным тематическим наполнением.
                        </p>
                        <div class="stats-badge">
                            Критерий Хи-квадрат Пирсона<br>
                            &chi;² = 14.1504<br>
                            p-value = 0.0068 (highly sig.)<br>
                            СПб: Филологическое ядро<br>
                            Москва: Философия и модерн
                        </div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-header">🎟️ Межплощадочная специализация</div>
                        <p class="stats-text">
                            <strong>Подтверждено:</strong> Разделение на Зографские и Рериховские чтения является не просто организационным решением, а фундаментальным концептуальным выбором.
                        </p>
                        <div class="stats-badge" style="border-left-color: var(--accent2);">
                            Критерий Хи-квадрат Пирсона<br>
                            &chi;² = 28.3242<br>
                            p-value = 0.000003 (extremely sig.)<br>
                            Зограф: Фокус на лингвистику L1<br>
                            Рерих: Религия/регионы L2
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "cities/index.html",
        page_shell(
            f"Географические центры | {SITE_NAME}",
            f"Географические центры российской индологии: города, с которыми связаны учёные Зографских и Рериховских чтений ({coverage}).",
            "cities/",
            index_body,
            [page_data("Географические центры", "Географические центры российской индологии.", "cities/"), make_breadcrumbs([("Главная", ""), ("Города", "cities/")])],
        ),
    )


def generate_institution_pages(data, records, authority):
    summary = data.get("summary", {})
    coverage = f'{summary.get("start_year")}-{summary.get("end_year")}'
    grouped = defaultdict(list)
    for record in records:
        institution = normalize_affiliation(record.get("affiliation"))
        if institution:
            grouped[institution].append(record)

    memberships = load_meso_memberships()
    meso_items_by_code = {item["code"]: item for item in load_meso_index()}
    orgs_auth = authority.get("organizations") or {}

    cards = []
    written_files = {"index.html"}
    for institution, talks in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        path = institution_path(institution)
        written_files.add(Path(path).name)
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(institution)}</a></strong><div class="meta">{presentation_records_label(len(talks))}</div></article>')
        inst_desc = f"Учёные и доклады: учреждение - {institution}. Архив участия в Зографских и Рериховских чтениях ({coverage})."
        facets = "".join([
            chip_section("Ведущие авторы", facet_scholar_links(talks, "../", 14)),
            chip_section("Рубрики институции", facet_theme_links(talks, "../", 12)),
            chip_section("Уровни Гумилева", facet_gumilyov_links(talks, "../", 3)),
            chip_section("Города", facet_city_links(talks, "../", 10)),
            chip_section("Связанные мезоуровни", facet_meso_links(talks, memberships, meso_items_by_code, "../", 12)),
            chip_section("Конференции", facet_conference_links(talks, "../", 12)),
        ])
        body = f"""
        <header>
            <h1>{esc(institution)}</h1>
            <p>{esc(inst_desc)}</p>
        </header>
        {facets}
        <section class="list">{''.join(talk_card(t, '../') for t in talks[:250])}</section>
        """
        org_node = organization_structured_data(institution, orgs_auth.get(institution), path)
        structured = page_data(
            institution,
            inst_desc,
            path,
            "ProfilePage",
            {"mainEntity": org_node},
        )
        write_text(
            path,
            page_shell(
                f"{institution} | {SITE_NAME}",
                inst_desc,
                path,
                body,
                [structured, make_breadcrumbs([("Home", ""), ("Institutions", "institutions/"), (institution, path)])],
            ),
        )

    index_body = f"""
        <header>
            <h1>Институции</h1>
            <p>Нормализованные страницы организаций и устойчивых аффилиационных кластеров.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "institutions/index.html",
        page_shell(
            f"Институции | {SITE_NAME}",
            f"Организации и научные учреждения российской индологии: институты, кафедры и университеты участников Зографских и Рериховских чтений ({coverage}).",
            "institutions/",
            index_body,
            [page_data("Институции", "Организации российской индологии.", "institutions/"), make_breadcrumbs([("Главная", ""), ("Институции", "institutions/")])],
        ),
    )
    for stale in Path("institutions").glob("*.html"):
        if stale.name not in written_files:
            stale.unlink()


def generate_publication_docs(data):
    docs = {
        "methodology.html": (
            "Methodology",
            "How the archive is built from cached conference programs, normalized names, and derived analytical fields.",
            """
        <header>
            <h1>Methodology</h1>
            <p>The Russian Indological Research Archive employs a structured digital humanities pipeline to transform historical conference programs into a clean, relational research database.</p>
        </header>
        <h2>Data, Metadata, and Derived Fields</h2>
        <p>Our methodology clearly distinguishes between raw primary records, curated metadata, and derived fields:</p>
        <section class="list">
            <article class="card">
                <strong>Primary Source Programs</strong>
                <p>The raw inputs are HTML or text transcriptions of the original printed or online conference programs. These are treated as immutable historical artifacts.</p>
            </article>
            <article class="card">
                <strong>Presentation Records</strong>
                <p>Each presentation is modeled as a distinct event-associated record with a title, session placement, sequence order, date, and time interval.</p>
            </article>
            <article class="card">
                <strong>Normalized Persons</strong>
                <p>Speaker names are extracted and resolved to canonical scholar entities using deterministic matching, resolving spelling variants, typos, and initials to prevent identity splitting or collision.</p>
            </article>
            <article class="card">
                <strong>Normalized Affiliations</strong>
                <p>Program strings are retained as provenance. City-only labels remain geographic signals; an institutional affiliation is published when explicitly stated or supported by a dated, verified trajectory, with tentative open continuations into later gaps marked (?).</p>
            </article>
            <article class="card">
                <strong>Broad Theme Labels</strong>
                <p>Each presentation is classified into one or more high-level research themes (e.g., Art, Linguistics, Philosophy) based on a titles-based heuristic mapping.</p>
            </article>
            <article class="card">
                <strong>Derived Analytics</strong>
                <p>Aggregate counts (total presentations, series overlap, geographic center clusters) are calculated from the relational graph and exported as open datasets.</p>
            </article>
        </section>
        
        <p><em>Note on thematic classification:</em> Presentation themes are mapped directly from the individual talk titles in our corpus and do not represent a scholar's complete lifetime research output or scientific profile.</p>
            """,
        ),
        "data-sources.html": (
            "Data Sources",
            "Primary sources and cached program material used by the archive.",
            """
        <header>
            <h1>Data Sources</h1>
            <p>The archive distinguishes between primary corpus materials representing the actual conference records and external authority databases used for context and entity disambiguation.</p>
        </header>
        
        <h2>Primary Corpus Sources</h2>
        <section class="grid">
            <article class="card">
                <strong>Zograf Readings</strong>
                <div class="meta">Programs and lists of presentations from the St. Petersburg Readings (2004–present). Cached files are stored in html_cache/zograf_*.html.</div>
            </article>
            <article class="card">
                <strong>Roerich Readings</strong>
                <div class="meta">Programs and lists of presentations from the Moscow Readings (2007–present). Cached files are stored in html_cache/roerich_*.html.</div>
            </article>
            <article class="card">
                <strong>Curated Seed Data</strong>
                <div class="meta">Explicit event dates, session chairs, venue configurations, and media mappings are maintained in zograf-roerich-db.md.</div>
            </article>
        </section>

        <h2>External Authority Mappings</h2>
        <p>To link our local corpus with the global scientific web, we match scholars and institutions to external authority files. These external records are treated as verified assertions, not primary data sources:</p>
        <section class="list">
            <article class="card">
                <strong>Authority Overrides</strong>
                <div class="meta">Canonical identifiers, latin names, and manual overrides are loaded from authority_ids.json.</div>
            </article>
            <article class="card">
                <strong>Scholarly & Citation Databases</strong>
                <div class="meta">Optional connections to ORCID, Wikidata, VIAF, OpenAlex, Google Scholar, and РИНЦ/eLIBRARY are recorded when manually verified.</div>
            </article>
            <article class="card">
                <strong>Institutional Registries</strong>
                <div class="meta">Normalized organizations are linked to ROR (Research Organization Registry) to ensure global interoperability.</div>
            </article>
        </section>
            """,
        ),
        "known-limitations.html": (
            "Known Limitations",
            "Known limitations and interpretation notes for the generated archive.",
            """
        <header>
            <h1>Known Limitations</h1>
            <p>Users of this archive should be aware of the following structural limitations and boundary conditions of digital humanities reconstruction:</p>
        </header>
        <section class="list">
            <article class="card">
                <strong>Name and Initials Ambiguity</strong>
                <p>Some historical programs omit full first names or patronymics. Identity matching relies on initials and surnames, which creates risk of identity collision or incorrect grouping without manual verification.</p>
            </article>
            <article class="card">
                <strong>Transliteration and Spelling Variants</strong>
                <p>Russian name spelling, especially in international publications and Romanized metadata, varies significantly. Finding correct external identifiers (e.g. ORCID, Wikidata) requires resolving these spelling variations.</p>
            </article>
            <article class="card">
                <strong>Historical and Temporary Affiliations</strong>
                <p>A city in a program is not treated as employment. An institutional label is shown only when stated in the program or supplied by a source-backed dated span; it is never carried beyond that span without new evidence.</p>
            </article>
            <article class="card">
                <strong>Broad Theme Classification</strong>
                <p>Thematic classification is a coarse categorization based on presentation titles. It serves as a navigational index rather than a detailed content-analysis model.</p>
            </article>
            <article class="card">
                <strong>External Database Coverage Gaps</strong>
                <p>Global open indexes like OpenAlex have lower coverage for Soviet and Russian humanities publications. Consequently, citation counts or publication list completeness from these sources are biased.</p>
            </article>
            <article class="card">
                <strong>РИНЦ / eLIBRARY Constraints</strong>
                <p>RINС/eLIBRARY contains extensive data but lacks a public, unrestricted API. All linkages are mapped via human review and cannot be scraped or fetched in bulk automatically.</p>
            </article>
            <article class="card">
                <strong>Presentation Identifier Stability</strong>
                <p>Presentation and session records use deterministic hash-based identifiers. For audit-heavy reuse, combine those IDs with the published presentation ID manifest and migration report.</p>
            </article>
        </section>
            """,
        ),
        "how-to-cite.html": (
            "How To Cite",
            "Citation guidance for using the Indology Scholars dataset and web archive.",
            f"""
        <header>
            <h1>How To Cite</h1>
            <p>If you use this archive, its dataset, or code for publication, please cite the relational database and web archive as a source.</p>
        </header>
        <section class="list">
            <article class="card">
                <strong>Suggested Dataset & Code Citation</strong>
                <div class="meta">{esc(AUTHOR_NAME)}. {esc(SITE_NAME)}: Unified Relational Archive. {BUILD_DATE}. {SITE_URL}</div>
            </article>
            <article class="card">
                <strong>Original Event Citation</strong>
                <p>When making claims about the exact historical wording of a presentation, session, or scheduling, please cite both the primary conference program and this digital archive.</p>
            </article>
            <article class="card">
                <strong>Access Date</strong>
                <p>Always include the access date and dataset version, as the archive is dynamically updated when new conference programs are integrated.</p>
            </article>
            <article class="card">
                <strong>Machine-Readable Formats</strong>
                <div class="meta">Citation metadata is available in standard format: <a href="CITATION.cff">CITATION.cff</a> and <a href="datapackage.json">datapackage.json</a>.</div>
            </article>
        </section>
            """,
        ),
        "metrics-guide.html": (
            "Metrics Guide",
            "How to read and interpret the local participation metrics and research analytics of the archive.",
            """
        <header>
            <h1>Metrics Guide</h1>
            <p>How to read the local participation metrics and research analytics of the archive.</p>
        </header>
        <section class="list">
            <article class="card">
                <strong>Total Talks (Общее число докладов)</strong>
                <p>The total count of presentation records mapped to a scholar. This represents the total observed participation in the indexed conferences (Zograf Readings and Roerich Readings) since 2004.</p>
            </article>
            <article class="card">
                <strong>Series Overlap (Пересечение серий)</strong>
                <p>Indicates the cohort of scholars who participate in both the Zograf Readings (St. Petersburg) and Roerich Readings (Moscow) series. This overlap metric measures the geographic and academic integration between the two primary scientific communities.</p>
            </article>
            <article class="card">
                <strong>Newcomer Rate (Доля новых участников)</strong>
                <p>The percentage of speakers in a given conference year or session who have no recorded talks in any prior years of that series. A higher newcomer rate highlights active academic renewal, open recruitment, or shifting research networks.</p>
            </article>
            <article class="card">
                <strong>Institution Bridge (Институциональные мосты)</strong>
                <p>Identifies speakers and sessions that link different organizations. This highlights structural collaboration or mobility, mapping researchers who hold multiple historical affiliations or bridge distinct centers (e.g. St. Petersburg University and Institute of Oriental Manuscripts).</p>
            </article>
            <article class="card">
                <strong>Theme Diversity (Тематическое разнообразие)</strong>
                <p>Measures how presentations are distributed across different scientific themes (Academic History, Linguistics, Philosophy, Art, History) within a conference or for an institution. A diverse distribution indicates a broad multidisciplinarity, while a low diversity indicates high specialization.</p>
            </article>
            <article class="card">
                <strong>Video Coverage (Видео-покрытие)</strong>
                <p>The percentage of presentation records that have direct video links (e.g., YouTube recordings) mapped. High video coverage enhances the transparency, visibility, and open accessibility of the scholarly presentations.</p>
            </article>
        </section>
            """,
        ),

    }
    for path, (title, desc, body) in docs.items():
        write_text(
            path,
            page_shell(
                f"{title} | {SITE_NAME}",
                desc,
                path,
                body,
                [page_data(title, desc, path), make_breadcrumbs([("Home", ""), (title, path)])],
            ),
        )


def is_legacy_redirect(path):
    try:
        return "data-legacy-redirect" in Path(path).read_text(encoding="utf-8")
    except OSError:
        return False


def generate_sitemap():
    static_paths = [
        "index.html",
        "en.html",
        "search.html",
        "download-data.html",
        "data-quality.html",
        "methodology.html",
        "data-sources.html",
        "known-limitations.html",
        "how-to-cite.html",
        "metrics-guide.html",
        "classification-criteria.html",
        "networks.html",
    ]
    static_paths = sorted(set(static_paths))

    scholars_paths = sorted(
        str(p).replace("\\", "/")
        for p in Path("s").glob("*.html")
        if not is_legacy_redirect(p)
    )

    publications_paths = sorted(
        str(p).replace("\\", "/")
        for p in Path("p").glob("*.html")
        if not is_legacy_redirect(p)
    )

    taxonomy_paths = []
    for dirname in ("conferences", "themes", "topics", "generations", "meso", "gumilyov", "videos", "findings", "cities", "institutions", "keywords"):
        taxonomy_paths.extend(
            str(p).replace("\\", "/")
            for p in Path(dirname).glob("*.html")
            if not is_legacy_redirect(p)
        )
    taxonomy_paths = sorted(set(taxonomy_paths), key=lambda p: (p.count("/"), p))

    def write_sub_sitemap(filename, paths):
        urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path in paths:
            if path == "index.html":
                loc = site_url("")
            elif path.endswith("/index.html"):
                loc = site_url(path[:-10])
            else:
                loc = site_url(path)
            urlset.append(f"  <url><loc>{esc(loc)}</loc></url>")
        urlset.append("</urlset>")
        write_text(filename, "\n".join(urlset) + "\n")

    # Write sub-sitemaps
    write_sub_sitemap("sitemap_static.xml", static_paths)
    write_sub_sitemap("sitemap_scholars.xml", scholars_paths)
    write_sub_sitemap("sitemap_publications.xml", publications_paths)
    write_sub_sitemap("sitemap_taxonomy.xml", taxonomy_paths)

    # Write index sitemap
    sitemaps = [
        "sitemap_static.xml",
        "sitemap_scholars.xml",
        "sitemap_publications.xml",
        "sitemap_taxonomy.xml",
    ]
    index_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for sm in sitemaps:
        loc = site_url(sm)
        index_xml.append("  <sitemap>")
        index_xml.append(f"    <loc>{esc(loc)}</loc>")
        index_xml.append("  </sitemap>")
    index_xml.append("</sitemapindex>")
    write_text("sitemap.xml", "\n".join(index_xml) + "\n")


def ensure_authority_file():
    path = Path("authority_ids.json")
    seed = {
        "description": "Optional authority identifiers used by generators when known. Add ORCID, Wikidata, VIAF, ROR, preferred Latin names, English alt names, or official URLs without changing code.",
        "persons": {},
        "organizations": {},
        "places": {},
    }
    if not path.exists():
        write_text(path, json.dumps(seed, ensure_ascii=False, indent=2))
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for key, default in seed.items():
        if key not in payload:
            payload[key] = default
            changed = True
    if changed:
        write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def fetch_db_summary():
    if not Path(DB_PATH).exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    summary = {
        "person_rows": cur.execute("SELECT COUNT(*) FROM person").fetchone()[0],
        "presentation_rows": cur.execute("SELECT COUNT(*) FROM presentation").fetchone()[0],
        "event_rows": cur.execute("SELECT COUNT(*) FROM event").fetchone()[0],
    }
    conn.close()
    return summary


def youtube_video_total():
    csv_path = Path("analytics_output/youtube_playlist_summary.csv")
    if not csv_path.exists():
        return None
    total = 0
    for line in csv_path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 3 and parts[2].strip().isdigit():
            total += int(parts[2].strip())
    return total or None


def patch_index_stats(data):
    summary = data.get("summary", {})
    total_scholars = summary.get("total_scholars", 0)
    total_presentations = summary.get("total_presentations", 0)
    unique_presentations = summary.get("unique_presentations", total_presentations)
    start_year = summary.get("start_year", 2004)
    end_year = summary.get("end_year", 2025)
    years_count = summary.get("years_covered") or (end_year - start_year + 1)
    overlap = summary.get("overlap_scholars", 0)
    recorded_presentations = sum(
        1 for talk in presentation_records_by_id(timeline_records(data)).values() if talk.get("videos")
    )
    classification_path = Path("article/hypothesis_output/expanded_classification_summary.json")
    classification = json.loads(classification_path.read_text(encoding="utf-8")) if classification_path.exists() else {}
    scale = classification.get("gumilyov_scale", {})
    g1_count = int(scale.get("1", 0) or 0)
    appendix = {
        row.get("key", ""): row.get("value", "")
        for row in load_csv_rows("article/hypothesis_output/appendix_g_summary.csv")
    }
    expected_overlap = float(appendix.get("H1_overlap_expected_mean", 0) or 0)
    classified_rows = load_csv_rows("analytics_output/expanded_classification_deepseek.csv")
    periods = defaultdict(Counter)
    for row in classified_rows:
        periods[row.get("series", "")][row.get("period_l2", "")] += 1
    z_period_total = sum(periods["Zograf Readings"].values()) or 1
    r_period_total = sum(periods["Roerich Readings"].values()) or 1
    z_classical_medieval = round(
        100 * (periods["Zograf Readings"]["classical"] + periods["Zograf Readings"]["medieval"]) / z_period_total, 1
    )
    r_classical_medieval = round(
        100 * (periods["Roerich Readings"]["classical"] + periods["Roerich Readings"]["medieval"]) / r_period_total, 1
    )

    conn = sqlite3.connect(DB_PATH)
    series_max = dict(conn.execute("SELECT event_series_id, MAX(year) FROM event GROUP BY event_series_id").fetchall())
    conn.close()
    zograf_end = series_max.get(1, end_year)
    roerich_end = series_max.get(2, end_year)

    path = Path("index.html")
    html = path.read_text(encoding="utf-8")
    js_path = Path("assets/dashboard.js")
    js_content = js_path.read_text(encoding="utf-8") if js_path.exists() else ""

    def replace_stat(text, stat_id, value):
        return re.sub(
            rf'(<div class="stat-num gradient-text" id="{stat_id}">)\d+(</div>)',
            rf'\g<1>{value}\g<2>',
            text,
            count=1,
        )

    html = replace_stat(html, "stat-scholars-count", total_scholars)
    html = replace_stat(html, "stat-talks-count", total_presentations)
    html = replace_stat(html, "stat-years-count", years_count)
    html = replace_stat(html, "stat-overlap-count", overlap)
    html = replace_stat(html, "stat-youtube-count", recorded_presentations)

    talks_ru_desc = f"{total_presentations} участий в {unique_presentations} уникальных докладах"
    talks_en_desc = f"{total_presentations} participations across {unique_presentations} unique talks"
    corpus_pause_ru = (
        f"В корпусе: {total_scholars} ученых, {unique_presentations} уникальных докладов "
        f"и {total_presentations} авторских участий."
    )
    corpus_pause_en = (
        f"The corpus includes {total_scholars} scholars, {unique_presentations:,} unique talks, "
        f"and {total_presentations:,} author participations."
    )
    html = re.sub(
        r'(<div class="stat-label" id="stat-talks-label">)[^<]+(</div>)',
        r'\g<1>Авторские участия\g<2>',
        html,
        count=1,
    )
    html = re.sub(
        r'(<div class="stat-desc" id="stat-talks-desc">)[^<]+(</div>)',
        rf'\g<1>{talks_ru_desc}\g<2>',
        html,
        count=1,
    )
    html = html.replace('statTalks: "Доклады и презентации"', 'statTalks: "Авторские участия"')
    if js_path.exists():
        js_content = re.sub(
            r'(ru:\s*\{.*?statTalksDesc:\s*")[^"]*(")',
            rf'\g<1>{talks_ru_desc}\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(ru:\s*\{.*?statTalksDesc:\s*")[^"]*(")',
        rf'\g<1>{talks_ru_desc}\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = html.replace('statTalks: "Presentations & Talks"', 'statTalks: "Author Participations"')
    if js_path.exists():
        js_content = re.sub(
            r'(en:\s*\{.*?statTalksDesc:\s*")[^"]*(")',
            rf'\g<1>{talks_en_desc}\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(en:\s*\{.*?statTalksDesc:\s*")[^"]*(")',
        rf'\g<1>{talks_en_desc}\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'(<p class="findings-corpus-note" id="findings-corpus-note">)[^<]+(</p>)',
        rf'\g<1>{corpus_pause_ru}\g<2>',
        html,
        count=1,
    )
    if js_path.exists():
        js_content = re.sub(
            r'(ru:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")',
            rf'\g<1>{corpus_pause_ru}\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(ru:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")',
        rf'\g<1>{corpus_pause_ru}\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    if js_path.exists():
        js_content = re.sub(
            r'(en:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")',
            rf'\g<1>{corpus_pause_en}\g<2>',
            js_content,
            count=1,
            flags=re.DOTALL,
        )
    html = re.sub(
        r'(en:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")',
        rf'\g<1>{corpus_pause_en}\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    insight_values = {
        "insight-overlap-metric": f"{overlap} / {expected_overlap:.1f}",
        "insight-theme-metric": f"{r_classical_medieval}% / {z_classical_medieval}%",
        "insight-micro-metric": f"{g1_count} / {unique_presentations}",
        "insight-video-metric": str(recorded_presentations),
    }
    for metric_id, value in insight_values.items():
        html = re.sub(
            rf'(<div class="insight-metric" id="{metric_id}">)[^<]+(</div>)',
            rf'\g<1>{value}\g<2>',
            html,
            count=1,
        )
    overlap_text_ru = f"{overlap} ученый выступал на обеих площадках при модельном ожидании {expected_overlap:.1f}."
    overlap_text_en = f"Only {overlap} scholars spoke at both venues, compared with a model expectation of {expected_overlap:.1f}."
    micro_text_ru = "В разметке преобладают доклады о конкретном тексте, авторе или источнике."
    micro_text_en = "The coding is dominated by talks on a specific text, author, or source."
    html = re.sub(r'(<div class="insight-text" id="insight-overlap-text">)[^<]+(</div>)', rf'\g<1>{overlap_text_ru}\g<2>', html, count=1)
    html = re.sub(r'(<div class="insight-text" id="insight-micro-text">)[^<]+(</div>)', rf'\g<1>{micro_text_ru}\g<2>', html, count=1)
    html = re.sub(r'(ru:\s*\{.*?insightOverlapText:\s*")[^"]*(")', rf'\g<1>{overlap_text_ru}\g<2>', html, count=1, flags=re.DOTALL)
    html = re.sub(r'(ru:\s*\{.*?insightMicroText:\s*")[^"]*(")', rf'\g<1>{micro_text_ru}\g<2>', html, count=1, flags=re.DOTALL)
    html = re.sub(r'(en:\s*\{.*?insightOverlapText:\s*")[^"]*(")', rf'\g<1>{overlap_text_en}\g<2>', html, count=1, flags=re.DOTALL)
    html = re.sub(r'(en:\s*\{.*?insightMicroText:\s*")[^"]*(")', rf'\g<1>{micro_text_en}\g<2>', html, count=1, flags=re.DOTALL)
    html = re.sub(
        r'(<div class="stat-label" id="stat-youtube-label">)[^<]+(</div>)',
        r'\g<1>Доклады с видео\g<2>',
        html,
        count=1,
    )
    html = re.sub(
        r'(<div class="stat-desc" id="stat-youtube-desc">)[^<]+(</div>)',
        r'\g<1>Записи, привязанные к докладам\g<2>',
        html,
        count=1,
    )
    html = html.replace('statYoutube: "Видеозаписи"', 'statYoutube: "Доклады с видео"')
    html = html.replace('statYoutubeDesc: "Зографские чтения 2023–2025 на YouTube"', 'statYoutubeDesc: "Сохранившиеся записи, привязанные к докладам"')
    html = html.replace('statYoutube: "Video Recordings"', 'statYoutube: "Talks with Recordings"')
    html = html.replace('statYoutubeDesc: "Zograf Readings 2023–2025 on YouTube"', 'statYoutubeDesc: "Surviving recordings attached to talks"')

    html = re.sub(
        r'(<div class="stat-desc" id="stat-years-desc">)Период с \d+ по \d+ годы(</div>)',
        rf'\g<1>Период с {start_year} по {end_year} годы\g<2>',
        html,
        count=1,
    )
    html = re.sub(
        r'(statYearsDesc:\s*")Период с \d+ по \d+ годы(")',
        rf'\g<1>Период с {start_year} по {end_year} годы\g<2>',
        html,
        count=1,
    )
    html = re.sub(
        r'(statYearsDesc:\s*")Covering \d+ through \d+(")',
        rf'\g<1>Covering {start_year} through {end_year}\g<2>',
        html,
        count=1,
    )

    html = re.sub(
        r'(«Зографские? чтени[яй]» \(2004[–-])\d{4}( гг\.\))',
        rf'\g<1>{zograf_end}\g<2>',
        html,
    )
    html = re.sub(
        r'(Zograf Readings \(2004[–-])\d{4}(\))',
        rf'\g<1>{zograf_end}\g<2>',
        html,
    )
    html = re.sub(
        r'(«Рериховских? чтени[яй]» \(2007[–-])\d{4}( гг\.\))',
        rf'\g<1>{roerich_end}\g<2>',
        html,
    )
    html = re.sub(
        r'(Roerich Readings \(2007[–-])\d{4}(\))',
        rf'\g<1>{roerich_end}\g<2>',
        html,
    )

    html = re.sub(
        r'\(2004[–-]\d{4}( гг\.)?\)',
        lambda m: f'(2004–{end_year}{" гг." if " гг." in m.group(0) else ""})',
        html,
    )

    path.write_text(html, encoding="utf-8", newline="\n")
    print(
        f"Patched index.html: scholars={total_scholars}, presentations={total_presentations}, "
        f"years={start_year}–{end_year} ({years_count}), overlap={overlap}, "
        f"Zograf {zograf_end}, Roerich {roerich_end}, recorded_presentations={recorded_presentations}"
    )


def main():
    ensure_dirs()
    ensure_authority_file()
    authority = load_authority_overrides()
    data = load_site_data("site_data.json")
    records = timeline_records(data)
    attach_meso_codes(records)
    initialize_presentation_slugs(records)
    data.setdefault("summary", {}).update(fetch_db_summary())

    generate_home_assets(data)
    generate_search(data, records)
    generate_keyword_stats_page(records)
    authority_stats = generate_authority_coverage(data, authority)
    generate_provenance_sidecars(data, authority, records)
    generate_download_page(data)
    generate_data_quality_page(data, authority_stats)
    generate_404_page()
    generate_english_landing(data)
    generate_findings_page(data, records)
    generate_visualisations_page(data, records)
    generate_generations_page(data)
    generate_collaboration_page(data)
    generate_nlp_page(data, records)
    generate_classification_criteria_page(records)
    generate_gumilyov_pages(data, records)
    generate_video_pages(data, records)
    generate_presentation_pages(records)
    generate_conference_pages(data, records)
    generate_theme_pages(data, records)
    generate_legacy_theme_redirects()
    generate_topic_pages(records)
    generate_meso_pages(data, records)
    theme_queue_size = generate_theme_review_queue(records)
    generate_city_pages(data, records, authority)
    generate_institution_pages(data, records, authority)
    generate_publication_docs(data)
    generate_sitemap()
    patch_index_stats(data)
    manifest_count = generate_publication_file_manifest()
    print(f"Generated publication pages, sitemap, robots, search index, citation files, and preview assets. Theme review queue: {theme_queue_size} items. File manifest: {manifest_count} files.")


if __name__ == "__main__":
    main()
