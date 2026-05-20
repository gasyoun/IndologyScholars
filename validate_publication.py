import re
import sqlite3
import sys
from pathlib import Path

from publication_helpers import load_site_data


def fail(errors, message):
    errors.append(message)


def read(path):
    return Path(path).read_text(encoding="utf-8")


def main():
    errors = []
    data = load_site_data("site_data.json")
    summary = data.get("summary", {})
    scholars = data.get("scholars", [])

    if Path("conferences.db").exists():
        conn = sqlite3.connect("conferences.db")
        cur = conn.cursor()
        db_persons = cur.execute("SELECT COUNT(DISTINCT person_id) FROM presentation_person").fetchone()[0]
        db_presenter_records = cur.execute("SELECT COUNT(*) FROM presentation_person").fetchone()[0]
        dangling_sessions = cur.execute("""
            SELECT COUNT(*)
            FROM session s
            LEFT JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
            WHERE edv.event_day_venue_id IS NULL
        """).fetchone()[0]
        conn.close()
        if summary.get("total_scholars") != db_persons:
            fail(errors, f"summary.total_scholars={summary.get('total_scholars')} but DB presenter persons={db_persons}")
        if summary.get("total_presentations") != db_presenter_records:
            fail(errors, f"summary.total_presentations={summary.get('total_presentations')} but DB presenter records={db_presenter_records}")
        if dangling_sessions:
            fail(errors, f"DB has {dangling_sessions} sessions without a joinable event_day_venue")

    scholar_ids = {s["id"] for s in scholars}
    scholar_pages = []
    redirect_pages = []
    for page in Path("scholars").glob("PERS_*.html"):
        html = read(page)
        if "data-legacy-redirect" in html:
            redirect_pages.append((page, html))
        else:
            scholar_pages.append((page, html))

    page_ids = {p.stem for p, _ in scholar_pages}
    if scholar_ids != page_ids:
        fail(errors, f"Scholar page mismatch: missing={sorted(scholar_ids - page_ids)[:10]} stale={sorted(page_ids - scholar_ids)[:10]}")

    for page, html in scholar_pages:
        if '<meta name="description"' not in html:
            fail(errors, f"{page} missing meta description")
        if 'rel="canonical"' not in html:
            fail(errors, f"{page} missing canonical")
        if 'application/ld+json' not in html:
            fail(errors, f"{page} missing JSON-LD")
        if "<script>" in html:
            fail(errors, f"{page} should not need inline runtime script")

    for page, html in redirect_pages:
        if 'meta name="robots" content="noindex,follow"' not in html:
            fail(errors, f"{page} legacy redirect should be noindex,follow")
        if 'rel="canonical"' not in html or 'http-equiv="refresh"' not in html:
            fail(errors, f"{page} legacy redirect missing canonical or refresh")

    index_html = read("index.html")
    for needle in ['rel="canonical"', 'og:image', 'twitter:image', 'application/ld+json', 'id="inst-table"', 'publication-links']:
        if needle not in index_html:
            fail(errors, f"index.html missing {needle}")

    required = [
        "sitemap.xml",
        "robots.txt",
        "404.html",
        "en.html",
        "search.html",
        "search-index.json",
        "download-data.html",
        "data-quality.html",
        "CITATION.cff",
        "datapackage.json",
        "conferences.db",
        "analytics_output/data_quality_report.json",
        "assets/og-image.png",
        "assets/favicon.svg",
        "scholars/index.html",
        "conferences/index.html",
        "themes/index.html",
        "cities/index.html",
        "institutions/index.html",
        "methodology.html",
        "data-sources.html",
        "known-limitations.html",
        "how-to-cite.html",
    ]
    for path in required:
        if not Path(path).exists():
            fail(errors, f"Missing generated publication asset: {path}")

    if Path("sitemap.xml").exists():
        sitemap = read("sitemap.xml")
        for page in ["", "en.html", "search.html", "download-data.html", "data-quality.html", "scholars/", "conferences/", "themes/", "cities/", "institutions/"]:
            expected = "https://gasyoun.github.io/IndologyScholars/" + page
            if expected not in sitemap:
                fail(errors, f"sitemap.xml missing {expected}")
        if "https://gasyoun.github.io/IndologyScholars/404.html" in sitemap:
            fail(errors, "sitemap.xml should not include 404.html")
        for page, _ in redirect_pages:
            expected = f"https://gasyoun.github.io/IndologyScholars/scholars/{page.name}"
            if expected in sitemap:
                fail(errors, f"sitemap.xml should not include legacy redirect {expected}")
        sample_profiles = sorted(scholar_ids)[:5]
        for scholar_id in sample_profiles:
            expected = f"https://gasyoun.github.io/IndologyScholars/scholars/{scholar_id}.html"
            if expected not in sitemap:
                fail(errors, f"sitemap.xml missing {expected}")

    if Path("search-index.json").exists():
        content = read("search-index.json")
        if len(re.findall(r'"type":"Scholar"', content)) != len(scholars):
            fail(errors, "search-index.json scholar count does not match site_data.json")

    if Path("404.html").exists():
        not_found = read("404.html")
        if 'name="robots" content="noindex, follow"' not in not_found:
            fail(errors, "404.html should be noindex, follow")

    if Path("analytics_output/data_quality_report.json").exists():
        report = read("analytics_output/data_quality_report.json")
        if '"dangling_sessions"' not in report or '"checks"' not in report:
            fail(errors, "data_quality_report.json missing expected checks")

    if errors:
        print("Publication validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Publication validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
