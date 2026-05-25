import datetime as dt
import csv
import hashlib
import json
import re
import sqlite3
import struct
import sys
import zlib
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
    build_presentation_slug_map,
    GENERATION_COHORTS,
    OG_IMAGE_PATH,
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
PUBLIC_DIRS = ["assets", "conferences", "presentations", "themes", "topics", "generations", "meso", "gumilyov", "videos", "findings", "cities", "institutions", "keywords"]
PRESENTATION_SLUG_BY_ID = {}
MIN_PUBLIC_MESO_PRESENTATIONS = 2


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
        "robots.txt",
        "search.html",
        "search-index.json",
        "site.webmanifest",
        "site_data.json",
        "sitemap.xml",
    ]
    directories = ["analytics_output", "assets", "cities", "conferences", "presentations", "findings", "generations", "gumilyov", "institutions", "keywords", "meso", "scholars", "themes", "topics", "videos", "curation"]
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
        writer = csv.DictWriter(f, fieldnames=["path", "size_bytes", "sha256"])
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
    return f"presentations/{slug or pid}.html"


def theme_path(code):
    return f"themes/{slugify(code, 'theme')}.html"


def topic_path(code):
    return f"topics/{slugify(code, 'topic')}.html"


def generations_path():
    return "generations/"


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
    return f"{depth}scholars/{slug}.html"


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
        "start_url": "/IndologyScholars/",
        "display": "standalone",
        "background_color": "#0a0e1a",
        "theme_color": "#0a0e1a",
        "icons": [{"src": "/IndologyScholars/assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}],
    }
    write_text("site.webmanifest", json.dumps(manifest, ensure_ascii=False, indent=2))

    favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="12" fill="#0a0e1a"/>
<path d="M14 44h36M18 38h28M22 18h20v20H22z" fill="none" stroke="#c4b5fd" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M25 25h14M25 31h10" stroke="#ec4899" stroke-width="3" stroke-linecap="round"/>
</svg>
"""
    write_text("assets/favicon.svg", favicon)
    write_og_image("assets/og-image.png")


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
                "url": f"scholars/{scholar['url_slug']}.html",
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
        <input class="search-box" id="q" type="search" placeholder="Введите имя, тему, город или организацию" autofocus>
        <section id="results" class="list" style="margin-top:1rem;"></section>
        <script>
        const results = document.getElementById('results');
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
            results.innerHTML = items.map(d => `<article class="card"><strong><a href="${d.url}">${escapeHtml(d.title || '')}</a></strong><div class="meta">${escapeHtml(d.meta || typeLabels[d.type] || d.type)}</div></article>`).join('');
        }
        function escapeHtml(value) {
            return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
        }
        input.addEventListener('input', () => render(input.value));
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
        ("Verified affiliation spans", "curation/verified_affiliation_spans.csv", "Dated, source-backed institutional trajectories used only within their verified intervals."),
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
    total_rinc = 0
    total_google_scholar = 0
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
        has_rinc = 1 if "rinc_author_id" in urls_dict else 0
        has_google = 1 if "google_scholar" in urls_dict else 0
        has_official = 1 if "official_url" in urls_dict else 0

        has_any = 1 if (has_orcid or has_wikidata or has_viaf or has_openalex or has_rinc or has_google or has_official) else 0

        confidence = person_auth.get("confidence", "")
        checked_at = person_auth.get("checked_at", "")

        if has_any:
            scholars_with_any += 1
        total_orcid += has_orcid
        total_wikidata += has_wikidata
        total_viaf += has_viaf
        total_openalex += has_openalex
        total_rinc += has_rinc
        total_google_scholar += has_google
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
            "has_rinc": has_rinc,
            "has_google_scholar": has_google,
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
                "review_status": "todo"
            })

    review_queue.sort(key=lambda r: (r["priority_rank"], -r["total_talks"], r["display_name"]))

    Path("analytics_output").mkdir(exist_ok=True)

    with open("analytics_output/authority_coverage.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "person_id", "display_name", "full_name_ru", "preferred_latin_name", "total_talks",
            "has_orcid", "has_wikidata", "has_viaf", "has_openalex", "has_rinc", "has_google_scholar",
            "has_official_url", "has_any_external_id", "authority_confidence", "checked_at"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in coverage_rows:
            writer.writerow(r)

    with open("analytics_output/authority_review_queue.csv", "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "priority_rank", "person_id", "display_name", "full_name_ru", "total_talks",
            "reason", "suggested_query", "rinc_search_url", "openalex_search_url",
            "review_status"
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
        "total_rinc": total_rinc,
        "total_google_scholar": total_google_scholar,
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
    rinc_pct = round(authority_stats["total_rinc"] * 100 / t, 1)
    google_pct = round(authority_stats["total_google_scholar"] * 100 / t, 1)
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
                РИНЦ/eLIBRARY: {authority_stats["total_rinc"]} ({rinc_pct}%) &middot;
                Google Scholar: {authority_stats["total_google_scholar"]} ({google_pct}%) &middot;
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
            <article class="card"><strong><a href="/IndologyScholars/scholars/">Browse scholars</a></strong><div class="meta">Canonical generated profile index.</div></article>
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
            <article class="card"><strong><a href="scholars/">Scholar Profiles</a></strong><div class="meta">Canonical generated pages with presentations, affiliations, themes, and related scholars.</div></article>
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

    body = f"""
        <header>
            <h1>Главные выводы статьи</h1>
            <p>Эта страница переводит последнюю версию статьи из режима доказательства в режим чтения сайта: что означают базовые числа архива и куда на сайте идти, чтобы проверить каждый вывод.</p>
        </header>
        <aside class="caveat-block" role="note" aria-label="Article corpus pause">
            <strong>Корпус и статья пересчитаны</strong>
            <p>Показатели статьи рассчитаны для текущего расширенного каталога: {esc(total_scholars)} ученых, {esc(unique_presentations)} уникальных докладов и {esc(author_participations)} авторских участий. Классификация масштаба аргумента выполнена по всем докладам и повторно проверена для предварительных L2/L3.</p>
        </aside>
        <section class="grid">
            {''.join(card_html)}
        </section>

        <h2>Как читать эти числа</h2>
        <section class="list">
            <article class="talk">
                <strong>Не превращать компактность в обвинение</strong>
                <div class="meta">Программы показывают публичный итог отбора, но не заявки, отказы и внутренние решения. Поэтому статья говорит о наблюдаемой компактности, возвращаемости и проницаемости, а не о доказанной закрытости.</div>
            </article>
            <article class="talk">
                <strong>Не читать город как биографию</strong>
                <div class="meta">Зографский формат часто дает город, а не учреждение. Региональный или периферийный маркер - начало вопроса о траектории участника, а не готовый ответ о его месте работы.</div>
            </article>
            <article class="talk">
                <strong>Не считать микрокейс слабостью</strong>
                <div class="meta">Для филологической, текстологической и историко-религиоведческой работы микрокейс часто является основной формой надежной аргументации. Неожиданность не в его наличии, а в почти полном отсутствии публичного жанра больших синтезов.</div>
            </article>
        </section>

        <h2>Проверить на сайте</h2>
        <section class="link-block">
            <strong>Входы в данные</strong>
            <div class="chip-list">
                <a class="chip" href="../gumilyov/">Шкала Гумилева</a>
                <a class="chip" href="../generations/">Поколения</a>
                <a class="chip" href="../videos/">Видеоархив</a>
                <a class="chip" href="../conferences/">Годы и программы</a>
                <a class="chip" href="../themes/">Тематические рубрики</a>
                <a class="chip" href="../search.html">Поиск по докладам</a>
                <a class="chip" href="../download-data.html">CSV, JSON, SQLite</a>
            </div>
        </section>

        <h2>Что считать следующими гипотезами</h2>
        <section class="grid">
            <article class="card"><strong>Authority-слой для городов</strong><div class="meta">Связать городские метки программ с реальными биографическими и институциональными траекториями, чтобы проверить, где региональность является местом работы, а где - режимом публикации.</div></article>
            <article class="card"><strong>Публикационная конверсия</strong><div class="meta">Проверить, какие доклады стали статьями, сборниками или устойчивыми исследовательскими сериями. Это отделит конференционную видимость от долговременного научного следа.</div></article>
            <article class="card"><strong>Возрастная гипотеза G3</strong><div class="meta">Проверка расширенного корпуса не подтвердила преимущественно старший возраст авторов широких обобщений. Этот отрицательный результат важен для будущего пополнения authority-слоя.</div></article>
        </section>

        <aside class="caveat-block" role="note" aria-label="Scope note">
            <strong>Объем расширенного каталога</strong>
            <p>Текущий каталог сайта и численные гипотезы статьи используют одну расширенную базу: {esc(total_scholars)} ученых, {esc(unique_presentations)} уникальных докладов, {esc(author_participations)} авторских участий. Программа Зографских чтений 2026 г. учитывается как предварительная.</p>
        </aside>
    """
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
            f'<section id="{esc(cohort["code"])}"><h2>{esc(cohort["ru"])}</h2>'
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
            '<section id="unknown"><h2>Год рождения не установлен</h2>'
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
    online_badge = '<span class="badge badge-online">Онлайн</span>' if talk.get("is_online") else ""
    videos = talk.get("videos") or []
    video_badge = '<span class="badge badge-video">Видео</span>' if videos else ""
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
    source_html = ""
    if source_url:
        update = ""
        if source_updated:
            update = " · последнее обновление: " + dt.datetime.strptime(source_updated, "%Y-%m-%d").strftime("%d.%m.%Y")
        source_html = f'<p><a href="{esc(source_url)}">Официальная программа</a>{esc(update)}</p>'
    review = CLASSIFICATION_OVERRIDES.get(pid)
    rationale = ""
    if review:
        rationale = f"""
        <aside class="caveat-block" role="note" aria-label="Expert classification">
            <strong>Экспертно проверенная классификация</strong>
            <p>{esc(review["reason"])}</p>
        </aside>
        """
    video_links = [
        f'<a class="chip" href="{esc(video.get("url"))}">YouTube</a>'
        for video in videos
    ]
    title_note = clean_text(talk.get("title_editorial_note") or "")
    title_note_html = ""
    if title_note:
        title_note_html = f"""
        <aside class="caveat-block" role="note" aria-label="Title normalization">
            <strong>Редакционная нормализация названия</strong>
            <p>{esc(title_note)}</p>
        </aside>
        """
    affiliation = clean_text(talk.get("affiliation") or "")
    affiliation_html = ""
    if affiliation:
        affiliation_html = (
            f'<article class="card"><strong>Аффилиация</strong><div class="meta">{esc(affiliation)}</div></article>'
        )
    affiliation_note = clean_text(talk.get("affiliation_note") or "")
    affiliation_note_html = ""
    if affiliation_note:
        affiliation_note_html = f"""
        <aside class="caveat-block" role="note" aria-label="Affiliation provenance">
            <strong>Основание аффилиации</strong>
            <p>{esc(affiliation_note)}</p>
        </aside>
        """
    return f"""
        <header>
            <h1>{esc(talk.get("title"))}</h1>{online_badge}{video_badge}
            <p>{scholar_links_html(talk, depth)} · <a href="{conference_href}">{esc(series_label(talk.get("series_key"), "ru"))} {esc(talk.get("year"))}</a></p>
        </header>
        <section class="grid">
            <article class="card"><strong>Рубрика</strong><div class="meta"><a href="{depth}{theme_path(theme_code)}">{esc(theme_label(theme_code, "ru"))}</a></div></article>
            <article class="card"><strong>Уровень аргументации</strong><div class="meta"><a href="{depth}{gumilyov_path(g_level)}">L{g_level} {esc(g_meta["ru"])}</a></div></article>
            <article class="card"><strong>Идентификатор</strong><div class="meta">{esc(pid)}</div></article>
            <article class="card"><strong>Формат</strong><div class="meta">{"Онлайн" if talk.get("is_online") else "Очное / не обозначено как онлайн"}</div></article>
            {affiliation_html}
            <article class="card"><strong>Видеозапись</strong><div class="meta">{"Есть сохранившаяся запись" if videos else "Не привязана"}</div></article>
        </section>
        {title_note_html}
        {affiliation_note_html}
        {rationale}
        {chip_section("Мезоуровни", meso_links)}
        {chip_section("Город в программе", [city_html] if city_html else [])}
        {chip_section("Сохранившаяся видеозапись", video_links)}
        <section class="link-block">
            <strong>Источник</strong>
            {source_html or "<p>Ссылка на исходную страницу программы не сохранена.</p>"}
        </section>
        <section class="link-block">
            <strong>Как читается классификация</strong>
            <div class="chip-list"><a class="chip" href="../classification-criteria.html">Критерии рубрик, мезоуровней и L1-L3</a></div>
        </section>
    """


def generate_presentation_pages(records):
    unique_records = list(presentation_records_by_id(records).values())
    unique_records.sort(key=lambda talk: (-int(talk.get("year") or 0), talk.get("title") or ""))
    year_counts = defaultdict(int)
    cards = []
    written_files = {"index.html"}
    for talk in unique_records:
        pid = clean_text(talk.get("presentation_id") or "")
        if not pid:
            continue
        year_counts[int(talk.get("year") or 0)] += 1
        title = clean_text(talk.get("title") or "Доклад")
        path = presentation_path(pid, title)
        body = presentation_detail_body(talk)
        structured = [
            page_data(title, f"Доклад: {title}.", path, page_type="ScholarlyArticle"),
            make_breadcrumbs([("Главная", ""), ("Доклады", "presentations/"), (title, path)]),
        ]
        write_text(path, page_shell(f"{title} | {SITE_NAME}", f"Доклад: {title}.", path, body, structured))
        written_files.add(Path(path).name)
        cards.append(
            f'<article class="talk"><strong><a href="../{path}">{esc(title)}</a></strong>'
            f'<div class="meta">{esc(series_label(talk.get("series_key"), "ru"))} {esc(talk.get("year"))} · {scholar_links_html(talk, "../")}</div></article>'
        )
    year_links = [
        f'<a class="chip" href="../conferences/">{esc(year)} · {talks_count_label(count)}</a>'
        for year, count in sorted(year_counts.items(), reverse=True)
    ]
    index_body = f"""
        <header>
            <h1>Доклады</h1>
            <p>Постоянные страницы уникальных записей программ. Каждый доклад имеет собственный адрес, авторов, рубрику, масштаб аргументации и доступные мезоуровни.</p>
        </header>
        {chip_section("Покрытие по годам", year_links)}
        <section class="list">{''.join(cards)}</section>
    """
    write_text(
        "presentations/index.html",
        page_shell(
            f"Доклады | {SITE_NAME}",
            "Постоянные страницы докладов Зографских и Рериховских чтений.",
            "presentations/",
            index_body,
            [page_data("Доклады", "Постоянные страницы докладов.", "presentations/"), make_breadcrumbs([("Главная", ""), ("Доклады", "presentations/")])],
        ),
    )
    for html_path in Path("presentations").glob("*.html"):
        if html_path.name not in written_files:
            html_path.unlink()


def generate_classification_criteria_page(records):
    records_by_id = presentation_records_by_id(records)
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
        writer = csv.DictWriter(handle, fieldnames=list(ledger_rows[0].keys()))
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
            <article class="talk"><strong>Подтвержденная траектория имеет временные границы</strong><p>Если источник подтверждает одну институцию на интервале участия, она может заполнить пропуски и городские пометы только в пределах этого интервала. После даты окончания запись не переносится автоматически на новые выступления.</p></article>
            <article class="talk"><strong>Метаданные не входят в название</strong><p>Начальная скобочная помета, распознанная как учреждение, например «(СПбГУ).», переносится в поле аффилиации для любого доклада. Содержательные скобки в заголовках не удаляются.</p></article>
            <article class="talk"><strong>Видео является также состоянием доклада</strong><p>Сохранившаяся и сопоставленная запись отмечается плашкой на карточке доклада и его странице; отдельный каталог видео сохраняется как обзор исходных записей и сопоставлений.</p></article>
        </section>
        <h2>Правила аргументационного масштаба</h2>
        <section class="list">
            <article class="talk"><strong>L1 Микроуровень</strong><p>Конкретный текст, предмет, ритуал, слово, экспедиция, авторское сопоставление или ограниченный тип артефактов. Упоминание региона, народа, языка или двух сравниваемых традиций не повышает уровень автоматически.</p></article>
            <article class="talk"><strong>L2 Региональный уровень</strong><p>Аргумент должен описывать устойчивую конфигурацию традиции, ареала, школы, исторической среды или нескольких серий объектов, а не только локализовать материал.</p></article>
            <article class="talk"><strong>L3 Синтетический уровень</strong><p>Требуется заявленное широкое сравнительное, цивилизационное или методологическое обобщение, выходящее за один корпус и одну региональную конфигурацию.</p></article>
            <article class="talk"><strong>Полный аудит DeepSeek</strong><p>Все 1350 уникальных докладов получили тематические коды, мезоуровни и L1-L3 по контролируемым перечням. Все предварительные L2/L3 были отправлены на отдельную строгую перепроверку; 81 повышенный уровень понижен, а два G3 затем редакционно отнесены к G2. Необработанная запись не получает L2 по умолчанию.</p></article>
        </section>
        <h2>Выводы из экспертных поправок</h2>
        <section class="list">
            <article class="talk"><strong>География не равна масштабу</strong><p>Невары, Ассам, Гималаи, Бенгалия или язык куллуи обозначают материал исследования; без обобщающего тезиса это L1.</p></article>
            <article class="talk"><strong>Сравнение не равно макросинтезу</strong><p>Сравнение вариантов одной игры знания или одного литературного ответа остается микрокейсом, если вывод ограничен этими объектами.</p></article>
            <article class="talk"><strong>Рубрика и мезоуровень не конкурируют</strong><p>Доклад имеет одну основную дисциплинарную рубрику и одновременно несколько тематических маршрутов поиска.</p></article>
            <article class="talk"><strong>История индологии выделяется отдельно</strong><p>Экспедиции, путешественники и история научного освоения материала не должны исчезать в общем остаточном классе.</p></article>
            <article class="talk"><strong>Мезоуровней достаточно при контролируемом расширении</strong><p>Полный проход наполнил сквозные контуры буддизма, философии, ведийских исследований, эпосов, рукописей и рецепции; повторившееся предложение «Сикхские исследования» добавлено как новый мезоуровень, а единичные предложения оставлены в аудиторской выгрузке.</p></article>
        </section>
        <h2>Проверенная выборка</h2>
        <section class="list">{''.join(reviewed_cards)}</section>
        <section class="link-block">
            <strong>Машиночитаемый журнал решений</strong>
            <div class="chip-list"><a class="chip" href="analytics_output/classification_overrides.csv">classification_overrides.csv</a><a class="chip" href="analytics_output/expanded_classification_deepseek.csv">expanded_classification_deepseek.csv</a><a class="chip" href="analytics_output/expanded_gumilyov_elevated_audit.csv">expanded_gumilyov_elevated_audit.csv</a></div>
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

    index_body = f"""
        <header>
            <h1>Исследовательские рубрики</h1>
            <p>Крупные тематические входы в корпус докладов.</p>
        </header>
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
    <link rel="canonical" href="{esc(target_url)}">
    <meta http-equiv="refresh" content="0; url={esc(target_href)}">
</head>
<body>
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

    index_body = f"""
        <header>
            <h1>Географические центры</h1>
            <p>Страницы городов по аффилиациям и географическим сигналам из программ конференций.</p>
        </header>
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
    for institution, talks in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        path = institution_path(institution)
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
                <p>Program strings are retained as provenance. City-only labels remain geographic signals, while institutional affiliations are published only when explicitly stated or supported by a dated, verified trajectory.</p>
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
    html_paths = [
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
    html_paths.extend(str(p).replace("\\", "/") for p in Path("scholars").glob("*.html") if not is_legacy_redirect(p))
    for dirname in ("conferences", "presentations", "themes", "topics", "generations", "meso", "gumilyov", "videos", "findings", "cities", "institutions", "keywords"):
        html_paths.extend(
            str(p).replace("\\", "/")
            for p in Path(dirname).glob("*.html")
            if not (dirname == "presentations" and p.name.startswith("PRES_"))
        )
    html_paths = sorted(set(html_paths), key=lambda p: (p.count("/"), p))
    urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in html_paths:
        if path == "index.html":
            loc = site_url("")
        elif path.endswith("/index.html"):
            loc = site_url(path[:-10])
        else:
            loc = site_url(path)
        priority = "1.0" if path == "index.html" else ("0.8" if path.startswith("scholars/") else "0.7")
        urlset.append(f"  <url><loc>{esc(loc)}</loc><lastmod>{BUILD_DATE}</lastmod><priority>{priority}</priority></url>")
    urlset.append("</urlset>")
    write_text("sitemap.xml", "\n".join(urlset) + "\n")


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
        f"Статья и сайт синхронизированы с расширенным корпусом: {total_scholars} ученых / "
        f"{unique_presentations} уникальных докладов / {total_presentations} авторских участий. "
        "Шкала обобщения повторно проверена для всех докладов."
    )
    corpus_pause_en = (
        f"The article and site are synchronized to the expanded corpus: {total_scholars} scholars / "
        f"{unique_presentations:,} unique talks / {total_presentations:,} author participations. "
        "Argument scale was re-audited across all presentations."
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
    html = re.sub(
        r'(ru:\s*\{.*?statTalksDesc:\s*")[^"]*(")',
        rf'\g<1>{talks_ru_desc}\g<2>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = html.replace('statTalks: "Presentations & Talks"', 'statTalks: "Author Participations"')
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
    html = re.sub(
        r'(ru:\s*\{.*?findingsCorpusNote:\s*")[^"]*(")',
        rf'\g<1>{corpus_pause_ru}\g<2>',
        html,
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
    overlap_text_ru = f"Только {overlap} ученых выступали на обеих площадках при модельном ожидании {expected_overlap:.1f}."
    overlap_text_en = f"Only {overlap} scholars spoke at both venues, compared with a model expectation of {expected_overlap:.1f}."
    micro_text_ru = "После полного аудита шкала Гумилева показывает доминирование докладов о конкретном тексте, авторе или источнике."
    micro_text_en = "After a full audit, the Gumilyov scale shows the dominance of talks on a specific text, author, or source."
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
        r'\g<1>Сохранившиеся записи, привязанные к докладам\g<2>',
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
    generate_generations_page(data)
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
