import datetime as dt
import csv
import hashlib
import json
import re
import sqlite3
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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
    clean_person_urls,
)


DB_PATH = "conferences.db"
BUILD_DATE = dt.date.today().isoformat()
DATA_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "2026-05-21"
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
        "metrics-guide.html",
        "networks.html",
        "robots.txt",
        "search.html",
        "search-index.json",
        "site.webmanifest",
        "site_data.json",
        "sitemap.xml",
    ]
    directories = ["analytics_output", "assets", "cities", "conferences", "institutions", "scholars", "themes"]
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
        ("Dashboard payload", "site_data.json", "Generated browser data used by the interactive dashboard and static scholar pages."),
        ("Static search index", "search-index.json", "Compact JSON index for generated scholar and presentation pages."),
        ("Citation metadata", "CITATION.cff", "Machine-readable citation record for dataset/software reuse."),
        ("Frictionless datapackage", "datapackage.json", "Dataset metadata, resource list, license, and source notes."),
        ("Data dictionary", "data_dictionary.md", "Human-readable field guide for reusable CSV, JSON, SQLite, and generated publication outputs."),
        ("Data quality report", "analytics_output/data_quality_report.json", "Machine-readable quality checks and review samples."),
        ("Biographical provenance", "analytics_output/field_provenance_biographical.csv", "Field-level provenance for curated person names and life dates."),
        ("Authority provenance", "analytics_output/field_provenance_authority.csv", "Field-level provenance for external identifiers and organization authority records."),
        ("Theme provenance", "analytics_output/field_provenance_themes.csv", "Field-level provenance for generated presentation theme labels."),
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
    for rec in records:
        title = rec.get("title") or ""
        theme = rec.get("theme") or {}
        l1, l1_conf = _score_rules(title, _THEME_L1_RULES)
        l3, l3_conf = _score_rules(title, _THEME_L3_RULES)
        theme_rows.append({
            "entity_type": "presentation",
            "entity_id": rec.get("presentation_id") or "",
            "field_name": "theme.code",
            "field_value": theme.get("code") or "",
            "source_type": "generate_site_data.classify_theme",
            "confidence": "heuristic",
            "checked_at": BUILD_DATE,
            "title": title,
            "l1_review_candidate": l1 or "",
            "l1_confidence": l1_conf,
            "l3_review_candidate": l3 or "",
            "l3_confidence": l3_conf,
            "notes": "Theme labels are navigational aids derived from presentation titles.",
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
    for rec in records:
        title = rec.get("title") or ""
        pres_id = rec.get("presentation_id") or ""
        year = rec.get("year", "")
        series = rec.get("series_label") or rec.get("series_key", "")
        theme_code = (rec.get("theme") or {}).get("code") or ""

        l1, l1_conf = _score_rules(title, _THEME_L1_RULES)
        l3, l3_conf = _score_rules(title, _THEME_L3_RULES)

        min_conf = min(l1_conf, l3_conf)
        needs_review = (l1 is None or l3 is None or min_conf < 0.5)

        if needs_review:
            queue.append({
                "presentation_id": pres_id,
                "year": year,
                "series": series,
                "title": title,
                "existing_theme_code": theme_code,
                "l1_baseline": l1 or "",
                "l1_conf": l1_conf,
                "l3_baseline": l3 or "",
                "l3_conf": l3_conf,
                "review_status": "todo",
                "notes": "",
            })

    # Sort: unclassified (l1 None) first, then by l1_conf ascending
    queue.sort(key=lambda r: (0 if not r["l1_baseline"] else 1, r["l1_conf"]))

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
            <article class="card"><strong><a href="scholars/">Scholar Profiles</a></strong><div class="meta">Canonical generated pages with presentations, affiliations, themes, and related scholars.</div></article>
            <article class="card"><strong><a href="conferences/">Conference Indexes</a></strong><div class="meta">Year-by-year Zograf Readings and Roerich Readings pages.</div></article>
            <article class="card"><strong><a href="search.html">Search</a></strong><div class="meta">Static search across people, talks, cities, institutions, and themes.</div></article>
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
        # Phase 5 caveat block: transparent classification disclaimer
        caveat_block = f"""
        <aside class="caveat-block" role="note" aria-label="Classification notice">
            <strong>&#x1F4CB; Classification note</strong>
            <p>
                This theme is assigned based on the <em>title</em> of each presentation using a
                keyword heuristic. It reflects how the talk was <em>labelled at this conference</em>,
                not the scholar's complete research profile or lifetime specialisation.
                A single researcher may appear across multiple themes. Multi-topic presentations
                may be simplified or placed in the most prominent category.
                See <a href="../methodology.html#theme-classification">Methodology &rsaquo; Thematic Classification</a>
                for full details.
            </p>
        </aside>"""
        body = f"""
        <header>
            <h1>{esc(title)}</h1>
            <p>{esc(ru_title)}. Presentations classified under this broad research theme.</p>
        </header>
        {caveat_block}
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
        city_desc = f"Доклады учёных и аффилиации, связанные с {city}. Архив Зографских и Рериховских чтений (2004–2025)."
        body = f"""
        <header>
            <h1>{esc(city)}</h1>
            <p>{esc(city_desc)}</p>
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
            <h1>Geographic centers</h1>
            <p>Static city pages for affiliation and mobility signals extracted from conference programs.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "cities/index.html",
        page_shell(
            f"Geographic centers | {SITE_NAME}",
            "Географические центры российской индологии: города, с которыми связаны учёные Зографских и Рериховских чтений (2004–2025).",
            "cities/",
            index_body,
            [page_data("Geographic centers", "Географические центры российской индологии.", "cities/"), make_breadcrumbs([("Home", ""), ("Cities", "cities/")])],
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
        inst_desc = f"Учёные и доклады, связанные с {institution}: архив участия в Зографских и Рериховских чтениях (2004–2025)."
        body = f"""
        <header>
            <h1>{esc(institution)}</h1>
            <p>{esc(inst_desc)}</p>
        </header>
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
            <h1>Institutions</h1>
            <p>Normalized institution pages for recurring affiliation clusters.</p>
        </header>
        <section class="grid">{''.join(cards)}</section>
    """
    write_text(
        "institutions/index.html",
        page_shell(
            f"Institutions | {SITE_NAME}",
            "Организации и научные учреждения российской индологии: институты, кафедры и университеты участников Зографских и Рериховских чтений (2004–2025).",
            "institutions/",
            index_body,
            [page_data("Institutions", "Организации российской индологии.", "institutions/"), make_breadcrumbs([("Home", ""), ("Institutions", "institutions/")])],
        ),
    )


def generate_publication_docs(data):
    docs = {
        "networks.html": (
            "Network Analysis",
            "Co-presence and institutional networks of Russian Indology scholars.",
            """
        <header>
            <h1>Network Analysis</h1>
            <p>We analyze the structure of Russian Indological conferences through the lens of participation networks.</p>
        </header>
        <h2>Participation Networks vs Citation Networks</h2>
        <p>Unlike traditional bibliometric networks (which map who cites whom), our networks map <strong>co-presence and shared scholarly context</strong>. They answer questions such as:</p>
        <ul>
            <li>Who presents in the same sessions?</li>
            <li>Which institutions are most strongly connected to specific themes?</li>
            <li>Who serves as a "bridge" between different conference series or cities?</li>
        </ul>
        
        <h2>Available Network Exports</h2>
        <p>You can download our raw network exports to run your own analyses in Gephi, Cytoscape, or Python NetworkX.</p>
        <section class="grid">
            <article class="card">
                <strong><a href="analytics_output/network_nodes.csv">network_nodes.csv</a></strong>
                <p>Contains typed nodes for all Persons, Organizations, Events, and Themes.</p>
            </article>
            <article class="card">
                <strong><a href="analytics_output/network_edges.csv">network_edges.csv</a></strong>
                <p>Contains weighted edges specifying the exact type of relationship (e.g., <code>person_person_same_session</code>, <code>person_theme</code>).</p>
            </article>
        </section>
            """,
        ),
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
                <p>Raw affiliation strings listed in the programs are cleaned and mapped to canonical organization entities (e.g. "СПбГУ", "ИВР РАН") to track institutional participation trajectories.</p>
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
                <p>Affiliations represent the institutional connection reported by the scholar at the time of the conference. They do not capture permanent employment history, retirements, or multiple simultaneous affiliations.</p>
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
        "networks.html": (
            "Network Exports",
            "How to interpret the participation network CSV exports in the Indology Scholars archive.",
            """
        <header>
            <h1>Network Exports</h1>
            <p>Typed network files for studying participation, affiliation, thematic proximity, and conference co-presence.</p>
        </header>
        <section class="grid">
            <article class="card">
                <strong>Nodes</strong>
                <div class="meta"><a href="analytics_output/network_nodes.csv">analytics_output/network_nodes.csv</a></div>
                <p>Contains person, event, organization, and theme nodes. The `weight` column counts observed participation or assignment frequency within the generated archive.</p>
            </article>
            <article class="card">
                <strong>Edges</strong>
                <div class="meta"><a href="analytics_output/network_edges.csv">analytics_output/network_edges.csv</a></div>
                <p>Contains weighted relations with `source`, `target`, `edge_type`, `year`, `series`, and `weight` columns.</p>
            </article>
        </section>
        <h2>Edge Types</h2>
        <section class="list">
            <article class="card">
                <strong>person_event</strong>
                <p>A scholar is attached to a conference event through one or more presentation records.</p>
            </article>
            <article class="card">
                <strong>person_organization</strong>
                <p>A scholar is linked to a normalized affiliation observed in a conference program. This is historical participation metadata, not a permanent employment claim.</p>
            </article>
            <article class="card">
                <strong>person_theme</strong>
                <p>A scholar is linked to a broad generated theme inferred from presentation titles.</p>
            </article>
            <article class="card">
                <strong>person_person_copresentation</strong>
                <p>Two scholars appear on the same presentation record.</p>
            </article>
            <article class="card">
                <strong>person_person_same_session</strong>
                <p>Two scholars appear in the same conference session. This is a co-presence relation and should not be interpreted as collaboration by itself.</p>
            </article>
        </section>
        <h2>Interpretation Notes</h2>
        <section class="list">
            <article class="card">
                <strong>Participation Network</strong>
                <p>The export models observed conference participation. It is not a citation network, publication network, or comprehensive institutional history.</p>
            </article>
            <article class="card">
                <strong>Stable Identifiers</strong>
                <p>Edges use stable local IDs from the current database build. Presentation-level stability can be audited through <a href="analytics_output/presentation_id_manifest.csv">presentation_id_manifest.csv</a>.</p>
            </article>
            <article class="card">
                <strong>Reusable Package</strong>
                <p>The network CSV schemas are declared in <a href="datapackage.json">datapackage.json</a> and listed on the <a href="download-data.html">download page</a>.</p>
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
        "networks.html",
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
    start_year = summary.get("start_year", 2004)
    end_year = summary.get("end_year", 2025)
    years_count = end_year - start_year + 1
    overlap = summary.get("overlap_scholars", 0)
    youtube_total = youtube_video_total()

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
    if youtube_total:
        html = replace_stat(html, "stat-youtube-count", youtube_total)

    html = re.sub(
        r'(<div class="stat-desc" id="stat-years-desc">)Период с \d+ по \d+ годы(</div>)',
        rf'\g<1>Период с {start_year} по {end_year} годы\g<2>',
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
        f"Zograf {zograf_end}, Roerich {roerich_end}, youtube={youtube_total or 'n/a'}"
    )


def main():
    ensure_dirs()
    ensure_authority_file()
    authority = load_authority_overrides()
    data = load_site_data("site_data.json")
    records = timeline_records(data)
    data.setdefault("summary", {}).update(fetch_db_summary())

    generate_home_assets(data)
    generate_search(data, records)
    authority_stats = generate_authority_coverage(data, authority)
    generate_provenance_sidecars(data, authority, records)
    generate_download_page(data)
    generate_data_quality_page(data, authority_stats)
    generate_404_page()
    generate_english_landing(data)
    generate_conference_pages(data, records)
    generate_theme_pages(data, records)
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
