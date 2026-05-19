import datetime as dt
import json
import re
import sqlite3
import struct
import zlib
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from publication_helpers import (
    AUTHOR_NAME,
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
)


DB_PATH = "conferences.db"
BUILD_DATE = dt.date.today().isoformat()
PUBLIC_DIRS = ["assets", "conferences", "themes", "cities", "institutions"]


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


def series_label(series):
    return "Zograf Readings" if series_slug(series) == "zograf" else "Roerich Readings"


def conference_path(series, year):
    return f"conferences/{series_slug(series)}-{year}.html"


def theme_path(code):
    return f"themes/{slugify(code, 'theme')}.html"


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


def scholar_by_id(data):
    return {s["id"]: s for s in data.get("scholars", [])}


def talk_card(talk, depth=""):
    speaker_slug = talk.get("speaker_slug")
    speaker = esc(talk.get("speaker") or talk.get("speaker_original") or "Unknown")
    scholar_link = f'<a href="{profile_href(speaker_slug, depth)}">{speaker}</a>' if speaker_slug else speaker
    city = (talk.get("geography") or {}).get("ru")
    city_link = ""
    if city and city not in ("Не указана", "Not specified"):
        city_link = f' · <a href="{depth}{city_path(city)}">{esc(city)}</a>'
    theme = talk.get("theme") or {}
    theme_code = theme.get("code", "History")
    return f"""
        <article class="talk">
            <strong>{esc(talk.get("title"))}</strong>
            <div class="meta">
                {scholar_link} · <a href="{depth}{conference_path(talk.get("series_key"), talk.get("year"))}">{esc(talk.get("series_label"))} {esc(talk.get("year"))}</a>
                · <a href="{depth}{theme_path(theme_code)}">{esc(theme_label(theme_code))}</a>{city_link}
            </div>
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
        "name": "indology-scholars",
        "title": SITE_NAME,
        "description": "Normalized archive of Russian Indological conference presentations and scholar profiles.",
        "homepage": SITE_URL,
        "created": BUILD_DATE,
        "licenses": [{"name": "Apache-2.0", "path": "LICENSE"}],
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
                "path": "site_data.js",
                "format": "js",
                "mediatype": "application/javascript",
                "description": "Browser payload with scholars, presentations, charts, and network data.",
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

    robots = f"""User-agent: *
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
    for talk in records:
        index.append(
            {
                "type": "Presentation",
                "title": talk.get("title"),
                "url": conference_path(talk.get("series_key"), talk.get("year")),
                "text": " ".join([talk.get("speaker") or "", talk.get("affiliation") or "", theme_label((talk.get("theme") or {}).get("code"))]),
            }
        )
    write_text("search-index.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))

    body = """
        <header>
            <h1>Search the archive</h1>
            <p>Search scholar names, presentation titles, affiliations, cities, and themes across the generated static pages.</p>
        </header>
        <input class="search-box" id="q" type="search" placeholder="Type a name, topic, city, or institution" autofocus>
        <section id="results" class="list" style="margin-top:1rem;"></section>
        <script>
        const results = document.getElementById('results');
        const input = document.getElementById('q');
        let docs = [];
        const initialQuery = new URLSearchParams(location.search).get('q') || '';
        input.value = initialQuery;
        fetch('search-index.json').then(r => r.json()).then(data => { docs = data; render(input.value); });
        function score(doc, query) {
            if (!query) return 0;
            const hay = `${doc.title} ${doc.text}`.toLowerCase();
            return query.split(/\\s+/).filter(Boolean).reduce((sum, token) => sum + (hay.includes(token) ? 1 : 0), 0);
        }
        function render(query) {
            const q = query.trim().toLowerCase();
            const items = docs.map(d => ({...d, score: score(d, q)})).filter(d => q ? d.score > 0 : d.type === 'Scholar').sort((a,b) => b.score - a.score || a.title.localeCompare(b.title)).slice(0, 50);
            results.innerHTML = items.map(d => `<article class="card"><strong><a href="${d.url}">${escapeHtml(d.title || '')}</a></strong><div class="meta">${d.type}</div></article>`).join('');
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
            "Search the Indology Scholars archive",
            "Search scholar profiles, presentations, affiliations, cities, and thematic groups in the Indology Scholars archive.",
            "search.html",
            body,
            page_data("Search the Indology Scholars archive", "Static search across generated archive pages.", "search.html", "SearchResultsPage"),
        ),
    )


def generate_download_page(data):
    summary = data.get("summary", {})
    resources = [
        ("SQLite database", "conferences.db", "Normalized relational source of events, sessions, presentations, people, venues, and affiliation strings."),
        ("Dashboard payload", "site_data.js", "Generated browser data used by the interactive dashboard and static scholar pages."),
        ("Static search index", "search-index.json", "Compact JSON index for generated scholar and presentation pages."),
        ("Citation metadata", "CITATION.cff", "Machine-readable citation record for dataset/software reuse."),
        ("Frictionless datapackage", "datapackage.json", "Dataset metadata, resource list, license, and source notes."),
        ("Data quality report", "analytics_output/data_quality_report.json", "Machine-readable quality checks and review samples."),
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
        "generated": BUILD_DATE,
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


def generate_data_quality_page(data):
    report = collect_data_quality(data)
    write_text("analytics_output/data_quality_report.json", json.dumps(report, ensure_ascii=False, indent=2))
    rows = []
    for check in report["checks"]:
        rows.append(
            f"""
            <article class="card">
                <strong>{esc(check["label"])}</strong>
                <div class="meta">Status: {esc(check["status"])} В· Severity: {esc(check["severity"])} В· Count: {esc(check["count"])}</div>
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
            <article class="card"><strong><a href="scholars/">Scholar Profiles</a></strong><div class="meta">Canonical generated pages with presentations, affiliations, themes, and related scholars.</div></article>
            <article class="card"><strong><a href="conferences/">Conference Indexes</a></strong><div class="meta">Year-by-year Zograf Readings and Roerich Readings pages.</div></article>
            <article class="card"><strong><a href="search.html">Search</a></strong><div class="meta">Static search across people, talks, cities, institutions, and themes.</div></article>
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


def generate_conference_pages(data, records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record["series_key"], record["year"])].append(record)

    cards = []
    for (series, year), talks in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0]), reverse=True):
        path = conference_path(series, year)
        title = f"{series_label(series)} {year}"
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(title)}</a></strong><div class="meta">{len(talks)} presentation records</div></article>')
        body = f"""
        <header>
            <h1>{esc(title)}</h1>
            <p>Static index of presentation records connected to {esc(title)}.</p>
        </header>
        <section class="list">
            {''.join(talk_card(t, '../') for t in talks)}
        </section>
        """
        structured = [
            page_data(title, f"Presentation records for {title}.", path),
            make_breadcrumbs([("Home", ""), ("Conferences", "conferences/"), (title, path)]),
        ]
        write_text(path, page_shell(f"{title} | {SITE_NAME}", f"Presentation records for {title}.", path, body, structured))

    index_body = f"""
        <header>
            <h1>Conference indexes</h1>
            <p>Year-by-year static landing pages for the Zograf Readings and Roerich Readings.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "conferences/index.html",
        page_shell(
            f"Conference indexes | {SITE_NAME}",
            "Static conference landing pages for Zograf Readings and Roerich Readings.",
            "conferences/",
            index_body,
            [page_data("Conference indexes", "Static conference landing pages.", "conferences/"), make_breadcrumbs([("Home", ""), ("Conferences", "conferences/")])],
        ),
    )


def generate_theme_pages(data, records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record.get("theme") or {}).get("code", "History")].append(record)

    cards = []
    for code, talks in sorted(grouped.items(), key=lambda item: theme_label(item[0])):
        path = theme_path(code)
        title = theme_label(code)
        ru_title = theme_label(code, "ru")
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(title)}</a></strong><div class="meta">{esc(ru_title)} · {len(talks)} presentation records</div></article>')
        body = f"""
        <header>
            <h1>{esc(title)}</h1>
            <p>{esc(ru_title)}. Presentations classified under this broad research theme.</p>
        </header>
        <section class="list">
            {''.join(talk_card(t, '../') for t in talks[:250])}
        </section>
        """
        write_text(
            path,
            page_shell(
                f"{title} | {SITE_NAME}",
                f"Presentation records and scholar links for the {title} theme.",
                path,
                body,
                [page_data(title, f"Presentation records for {title}.", path), make_breadcrumbs([("Home", ""), ("Themes", "themes/"), (title, path)])],
            ),
        )

    index_body = f"""
        <header>
            <h1>Research themes</h1>
            <p>Broad thematic entry points into the archive.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "themes/index.html",
        page_shell(
            f"Research themes | {SITE_NAME}",
            "Thematic indexes for the Indology Scholars presentation archive.",
            "themes/",
            index_body,
            [page_data("Research themes", "Thematic indexes for the archive.", "themes/"), make_breadcrumbs([("Home", ""), ("Themes", "themes/")])],
        ),
    )


def generate_city_pages(data, records, authority):
    grouped = defaultdict(list)
    for record in records:
        city = (record.get("geography") or {}).get("ru")
        if city and city not in ("Не указана", "Not specified"):
            grouped[city].append(record)

    city_meta = {
        item["ru"]: {"en": item.get("en"), "lat": item.get("lat"), "lon": item.get("lon")}
        for item in (data.get("geography_stats") or [])
        if item.get("ru")
    }
    places_auth = authority.get("places") or {}

    cards = []
    for city, talks in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        path = city_path(city)
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(city)}</a></strong><div class="meta">{len(talks)} presentation records</div></article>')
        body = f"""
        <header>
            <h1>{esc(city)}</h1>
            <p>Scholar affiliations and presentation records associated with {esc(city)}.</p>
        </header>
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
            page_data(city, f"Archive records associated with {city}.", path),
            make_breadcrumbs([("Home", ""), ("Cities", "cities/"), (city, path)]),
        ]
        write_text(
            path,
            page_shell(
                f"{city} | {SITE_NAME}",
                f"Presentation records and scholar affiliations associated with {city}.",
                path,
                body,
                structured,
            ),
        )

    index_body = f"""
        <header>
            <h1>Geographic centers</h1>
            <p>Static city pages for affiliation and mobility signals extracted from conference programs.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "cities/index.html",
        page_shell(
            f"Geographic centers | {SITE_NAME}",
            "City-level indexes for scholar affiliations in the Indology Scholars archive.",
            "cities/",
            index_body,
            [page_data("Geographic centers", "City-level archive indexes.", "cities/"), make_breadcrumbs([("Home", ""), ("Cities", "cities/")])],
        ),
    )


def generate_institution_pages(data, records, authority):
    grouped = defaultdict(list)
    for record in records:
        institution = normalize_affiliation(record.get("affiliation"))
        if institution:
            grouped[institution].append(record)

    orgs_auth = authority.get("organizations") or {}

    cards = []
    for institution, talks in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        path = institution_path(institution)
        cards.append(f'<article class="card"><strong><a href="../{path}">{esc(institution)}</a></strong><div class="meta">{len(talks)} presentation records</div></article>')
        body = f"""
        <header>
            <h1>{esc(institution)}</h1>
            <p>Normalized institution landing page built from historical affiliation strings.</p>
        </header>
        <section class="list">{''.join(talk_card(t, '../') for t in talks[:250])}</section>
        """
        org_node = organization_structured_data(institution, orgs_auth.get(institution), path)
        structured = page_data(
            institution,
            f"Archive records associated with {institution}.",
            path,
            "ProfilePage",
            {"mainEntity": org_node},
        )
        write_text(
            path,
            page_shell(
                f"{institution} | {SITE_NAME}",
                f"Presentation records and scholar links associated with {institution}.",
                path,
                body,
                [structured, make_breadcrumbs([("Home", ""), ("Institutions", "institutions/"), (institution, path)])],
            ),
        )

    index_body = f"""
        <header>
            <h1>Institutions</h1>
            <p>Normalized institution pages for recurring affiliation clusters.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "institutions/index.html",
        page_shell(
            f"Institutions | {SITE_NAME}",
            "Institution-level indexes for the Indology Scholars archive.",
            "institutions/",
            index_body,
            [page_data("Institutions", "Institution-level archive indexes.", "institutions/"), make_breadcrumbs([("Home", ""), ("Institutions", "institutions/")])],
        ),
    )


def generate_publication_docs(data):
    docs = {
        "methodology.html": (
            "Methodology",
            "How the archive is built from cached conference programs, normalized names, and derived analytical fields.",
            """
        <header><h1>Methodology</h1><p>The archive is generated by a reproducible pipeline that parses cached program pages, normalizes scholar identities, and compiles a relational SQLite database.</p></header>
        <section class="grid">
            <article class="card"><strong>Input</strong><p>Historical HTML program pages and curated seed metadata for venues, events, organizations, and media records.</p></article>
            <article class="card"><strong>Normalization</strong><p>Names, affiliations, dates, sessions, venues, cities, and broad research themes are normalized before the browser payload and static pages are generated.</p></article>
            <article class="card"><strong>Outputs</strong><p>The pipeline emits SQLite, CSV analytics, a dashboard payload, static scholar profiles, collection pages, sitemap, and search index.</p></article>
        </section>
            """,
        ),
        "data-sources.html": (
            "Data Sources",
            "Primary sources and cached program material used by the archive.",
            """
        <header><h1>Data Sources</h1><p>The archive works from local cached copies of public conference program pages so that rebuilds are reproducible even if upstream pages change.</p></header>
        <section class="list">
            <article class="card"><strong>Zograf Readings</strong><div class="meta">IOM RAS / St. Petersburg program materials represented in html_cache/zograf_*.html.</div></article>
            <article class="card"><strong>Roerich Readings</strong><div class="meta">IAS RAS / Moscow program materials represented in html_cache/roerich_*.html.</div></article>
            <article class="card"><strong>Curated seed data</strong><div class="meta">zograf-roerich-db.md provides stable event, venue, media, and organization seed records.</div></article>
        </section>
            """,
        ),
        "known-limitations.html": (
            "Known Limitations",
            "Known limitations and interpretation notes for the generated archive.",
            """
        <header><h1>Known Limitations</h1><p>This is a structured research aid, not a final authority file. Each derived field should be read together with its source program record.</p></header>
        <section class="list">
            <article class="card"><strong>Name matching</strong><div class="meta">Identity matching is deterministic and may require manual review for ambiguous initials, transliteration variants, or shared surnames.</div></article>
            <article class="card"><strong>Affiliations</strong><div class="meta">Institution pages use normalized clusters derived from raw affiliation strings; historical forms may be broader than formal employment relationships.</div></article>
            <article class="card"><strong>Themes</strong><div class="meta">Theme labels are broad heuristic classes based on presentation titles and should be treated as navigational aids.</div></article>
        </section>
            """,
        ),
        "how-to-cite.html": (
            "How To Cite",
            "Citation guidance for using the Indology Scholars dataset and web archive.",
            f"""
        <header><h1>How To Cite</h1><p>Use the repository citation file for software and dataset references. Include the access date for web page citations.</p></header>
        <section class="list">
            <article class="card"><strong>Suggested citation</strong><div class="meta">{esc(AUTHOR_NAME)}. {esc(SITE_NAME)}: Unified Relational Archive. {BUILD_DATE}. {SITE_URL}</div></article>
            <article class="card"><strong>Machine-readable citation</strong><div class="meta"><a href="CITATION.cff">CITATION.cff</a> · <a href="datapackage.json">datapackage.json</a></div></article>
            <article class="card"><strong>Dataset outputs</strong><div class="meta"><a href="analytics_output/">analytics_output/</a> · <a href="site_data.js">site_data.js</a></div></article>
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
    ]
    html_paths.extend(str(p).replace("\\", "/") for p in Path("scholars").glob("*.html") if not is_legacy_redirect(p))
    for dirname in ("conferences", "themes", "cities", "institutions"):
        html_paths.extend(str(p).replace("\\", "/") for p in Path(dirname).glob("*.html"))
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


def main():
    ensure_dirs()
    ensure_authority_file()
    authority = load_authority_overrides()
    data = load_site_data("site_data.js")
    records = timeline_records(data)
    data.setdefault("summary", {}).update(fetch_db_summary())

    generate_home_assets(data)
    generate_search(data, records)
    generate_download_page(data)
    generate_data_quality_page(data)
    generate_404_page()
    generate_english_landing(data)
    generate_conference_pages(data, records)
    generate_theme_pages(data, records)
    generate_city_pages(data, records, authority)
    generate_institution_pages(data, records, authority)
    generate_publication_docs(data)
    generate_sitemap()
    print("Generated publication pages, sitemap, robots, search index, citation files, and preview assets.")


if __name__ == "__main__":
    main()
