import csv
import re
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
import jsonschema

from publication_helpers import clean_person_urls, is_public_authority_record, load_authority_overrides, load_site_data


def fail(errors, message):
    errors.append(message)


def read(path):
    return Path(path).read_text(encoding="utf-8")


def load_csv(path):
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


AUTHORITY_ID_FIELDS = {
    "orcid",
    "wikidata",
    "viaf",
    "openalex",
    "google_scholar",
    "wikipedia",
    "vk",
    "official_url",
    "url",
    "scopus_author_id",
    "researcher_id",
    "rinc_author_id",
}


def valid_wikidata(value):
    text = str(value or "").strip()
    text = re.sub(r"^https?://www\.wikidata\.org/wiki/", "", text)
    return bool(re.match(r"^Q\d+$", text))


def valid_ror(value):
    text = str(value or "").strip()
    text = re.sub(r"^https?://ror\.org/", "", text)
    return bool(re.match(r"^0[a-z0-9]{6}\d{2}$", text))


def valid_http_url(value):
    text = str(value or "").strip()
    return text.startswith("https://") or text.startswith("http://")


def normalized_authority_value(field, value):
    text = str(value or "").strip()
    if field == "orcid":
        return re.sub(r"^https?://orcid\.org/", "", text)
    if field == "wikidata":
        return re.sub(r"^https?://www\.wikidata\.org/wiki/", "", text)
    if field == "viaf":
        return re.sub(r"^https?://viaf\.org/viaf/", "", text).rstrip("/")
    if field == "openalex":
        return re.sub(r"^https?://openalex\.org/", "", text)
    if field == "rinc_author_id":
        return re.sub(r"^https?://www\.elibrary\.ru/author_profile\.asp\?id=", "", text)
    if field == "scopus_author_id":
        return re.sub(r"^https?://www\.scopus\.com/authid/detail\.uri\?authorId=", "", text)
    if field == "researcher_id":
        return re.sub(r"^https?://www\.webofscience\.com/wos/author/record/", "", text)
    return text


def main():
    errors = []
    data = load_site_data("site_data.json")
    summary = data.get("summary", {})
    scholars = data.get("scholars", [])
    authority = load_authority_overrides()

    if not data.get("schema_version"):
        fail(errors, "site_data.json missing schema_version")
    if not data.get("generated"):
        fail(errors, "site_data.json missing generated date")

    if Path("conferences.db").exists():
        conn = sqlite3.connect("conferences.db")
        cur = conn.cursor()
        db_persons = cur.execute("SELECT COUNT(DISTINCT person_id) FROM presentation_person").fetchone()[0]
        db_presenter_records = cur.execute("SELECT COUNT(*) FROM presentation_person").fetchone()[0]
        db_presentation_rows = cur.execute("SELECT COUNT(*) FROM presentation").fetchone()[0]
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

    try:
        schema = json.loads(read("authority_ids.schema.json"))
        jsonschema.validate(instance=authority, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        fail(errors, f"authority_ids.json schema validation failed: {e.message} at path {list(e.path)}")

    scholar_ids = {s["id"] for s in scholars}
    persons_auth = authority.get("persons") or {}
    duplicate_authority_ids = defaultdict(list)
    for person_id, person_auth in persons_auth.items():
        if person_id not in scholar_ids:
            fail(errors, f"authority_ids.json persons.{person_id} does not match a generated scholar")
        if not isinstance(person_auth, dict):
            fail(errors, f"authority_ids.json persons.{person_id} should be an object")
            continue
        raw_public_fields = {key: person_auth.get(key) for key in AUTHORITY_ID_FIELDS if person_auth.get(key)}
        normalized_public_urls = clean_person_urls(person_auth)
        for key, value in raw_public_fields.items():
            normalized_key = "official_url" if key == "url" else key
            if normalized_key not in normalized_public_urls:
                fail(errors, f"authority_ids.json persons.{person_id}.{key} has invalid semantic format: {value}")
            if normalized_key != "official_url":
                normalized_value = normalized_authority_value(key, value)
                duplicate_authority_ids[(normalized_key, normalized_value)].append(person_id)
        if raw_public_fields and is_public_authority_record(person_auth) and not person_auth.get("checked_at"):
            fail(errors, f"authority_ids.json persons.{person_id} is public but missing checked_at")
        if raw_public_fields and not is_public_authority_record(person_auth):
            # Candidate or unspecified authority IDs are allowed only if they remain internal.
            pass
    for (field, value), person_ids in sorted(duplicate_authority_ids.items()):
        if value and len(set(person_ids)) > 1:
            fail(errors, f"authority_ids.json duplicate {field}={value} for persons {sorted(set(person_ids))}")

    for org_key, org_auth in (authority.get("organizations") or {}).items():
        if not isinstance(org_auth, dict):
            fail(errors, f"authority_ids.json organizations.{org_key} should be an object")
            continue
        if org_auth.get("wikidata") and not valid_wikidata(org_auth.get("wikidata")):
            fail(errors, f"authority_ids.json organizations.{org_key}.wikidata has invalid format")
        if org_auth.get("ror") and not valid_ror(org_auth.get("ror")):
            fail(errors, f"authority_ids.json organizations.{org_key}.ror has invalid format")
        if org_auth.get("url") and not valid_http_url(org_auth.get("url")):
            fail(errors, f"authority_ids.json organizations.{org_key}.url has invalid format")

    for place_key, place_auth in (authority.get("places") or {}).items():
        if not isinstance(place_auth, dict):
            fail(errors, f"authority_ids.json places.{place_key} should be an object")
            continue
        if place_auth.get("wikidata") and not valid_wikidata(place_auth.get("wikidata")):
            fail(errors, f"authority_ids.json places.{place_key}.wikidata has invalid format")

    scholar_pages = []
    redirect_pages = []
    for page in Path("s").glob("PERS_*.html"):
        html = read(page)
        if "data-legacy-redirect" in html:
            redirect_pages.append((page, html))
        else:
            scholar_pages.append((page, html))

    canonical_re = re.compile(r'<link rel="canonical" href="https://gasyoun\.github\.io/IndologyScholars/s/([^"]+)\.html"')
    slug_to_target = {}
    for page, html in redirect_pages:
        match = canonical_re.search(html)
        if match:
            slug_to_target[page.stem] = match.group(1)

    slug_pages = {p.stem for p in Path("s").glob("*.html") if not p.name.startswith("PERS_") and p.name != "index.html"}

    page_ids = {p.stem for p, _ in scholar_pages}
    valid_ids = set(page_ids)
    valid_ids.update(pers_id for pers_id, slug in slug_to_target.items() if slug in slug_pages)
    missing = scholar_ids - valid_ids
    stale = valid_ids - scholar_ids
    if missing or stale:
        fail(errors, f"Scholar page mismatch: missing={sorted(missing)[:10]} stale={sorted(stale)[:10]}")

    for page, html in scholar_pages:
        if '<meta name="description"' not in html:
            fail(errors, f"{page} missing meta description")
        if 'rel="canonical"' not in html:
            fail(errors, f"{page} missing canonical")
        if 'application/ld+json' not in html:
            fail(errors, f"{page} missing JSON-LD")
        if "<script>" in html:
            fail(errors, f"{page} should not need inline runtime script")
        person_id = page.stem
        person_auth = persons_auth.get(person_id, {})
        if person_auth and not is_public_authority_record(person_auth) and '"sameAs"' in html:
            fail(errors, f"{page} exposes sameAs for non-public authority record")

    for page, html in redirect_pages:
        if 'meta name="robots" content="noindex,follow"' not in html:
            fail(errors, f"{page} legacy redirect should be noindex,follow")
        if 'rel="canonical"' not in html or 'http-equiv="refresh"' not in html:
            fail(errors, f"{page} legacy redirect missing canonical or refresh")

    index_html = read("index.html")
    for needle in ['rel="canonical"', 'og:image', 'twitter:image', 'application/ld+json', 'id="inst-table"', 'publication-links']:
        if needle not in index_html:
            fail(errors, f"index.html missing {needle}")
    for needle in ['rel="manifest"', 'apple-touch-icon', 'assets/pwa.js']:
        if needle not in index_html:
            fail(errors, f"index.html missing PWA integration {needle}")
    talks_ru_desc = f"{summary.get('total_presentations', 0)} участий в {summary.get('unique_presentations', 0)} уникальных докладах"
    talks_en_desc = f"{summary.get('total_presentations', 0)} participations across {summary.get('unique_presentations', 0)} unique talks"
    dashboard_js = read("assets/dashboard.js") if Path("assets/dashboard.js").exists() else ""
    combined_content = index_html + dashboard_js
    if combined_content.count(talks_ru_desc) < 2 or talks_en_desc not in combined_content:
        fail(errors, "index.html static and localized presentation counts are not synchronized with site_data summary")
    if "В корпусе:" not in combined_content:
        fail(errors, "index.html missing the public corpus summary")

    required = [
        "sitemap.xml",
        "robots.txt",
        "site.webmanifest",
        "offline.html",
        "service-worker.js",
        "404.html",
        "en.html",
        "search.html",
        "search-index.json",
        "download-data.html",
        "data-quality.html",
        "CITATION.cff",
        "datapackage.json",
        "data_dictionary.md",
        "conferences.db",
        "analytics_output/data_quality_report.json",
        "analytics_output/authority_coverage.csv",
        "analytics_output/authority_review_queue.csv",
        "analytics_output/presentation_id_manifest.csv",
        "analytics_output/id_stability_audit.json",
        "analytics_output/id_migration_presentation.csv",
        "analytics_output/id_migration_presentation.json",
        "analytics_output/field_provenance_biographical.csv",
        "analytics_output/field_provenance_authority.csv",
        "analytics_output/field_provenance_themes.csv",
        "analytics_output/expanded_classification_deepseek.csv",
        "analytics_output/expanded_gumilyov_elevated_audit.csv",
        "analytics_output/meso_codes_deepseek.csv",
        "curation/verified_affiliation_spans.csv",
        "analytics_output/network_nodes.csv",
        "analytics_output/network_edges.csv",
        "analytics_output/publication_file_manifest.csv",
        "analytics_output/publication_file_manifest.json",
        "assets/og-image.png",
        "assets/favicon.svg",
        "assets/icon-192.png",
        "assets/icon-512.png",
        "assets/apple-touch-icon.png",
        "assets/pwa.js",
        "s/index.html",
        "conferences/index.html",
        "p/index.html",
        "themes/index.html",
        "topics/index.html",
        "topics/ramayana.html",
        "topics/mahabharata.html",
        "generations/index.html",
        "cities/index.html",
        "institutions/index.html",
        "methodology.html",
        "data-sources.html",
        "known-limitations.html",
        "how-to-cite.html",
        "metrics-guide.html",
        "classification-criteria.html",
        "networks.html",
        "videos/index.html",
    ]
    for path in required:
        if not Path(path).exists():
            fail(errors, f"Missing generated publication asset: {path}")

    published_html = [Path(path) for path in required if path.endswith(".html") and Path(path).exists()]
    for dirname in ("s", "p", "conferences", "themes", "topics", "generations", "meso", "gumilyov", "videos", "findings", "cities", "institutions", "keywords"):
        published_html.extend(Path(dirname).glob("*.html"))
    for page in set(published_html):
        html = read(page)
        if "/IndologyScholars/scholars/" in html or "/IndologyScholars/presentations/" in html:
            fail(errors, f"{page} still links to a removed absolute route")
        if re.search(r'href="(?:\.\./)?(?:scholars|presentations)/', html):
            fail(errors, f"{page} still links to a removed relative route")

    if Path("p/index.html").exists():
        if Path("p/index.html").stat().st_size > 150000:
            fail(errors, "p/index.html should stay paginated and below 150 KB")
        if not Path("p/page-2.html").exists():
            fail(errors, "p/index.html is missing paginated continuation")

    if Path("site.webmanifest").exists():
        app_manifest = json.loads(read("site.webmanifest"))
        icon_sizes = {icon.get("sizes") for icon in app_manifest.get("icons", [])}
        if app_manifest.get("display") != "standalone" or app_manifest.get("scope") != "/IndologyScholars/":
            fail(errors, "site.webmanifest missing installable application scope or display mode")
        if not {"192x192", "512x512"}.issubset(icon_sizes):
            fail(errors, "site.webmanifest missing PNG installation icons")

    if Path("assets/pwa.js").exists():
        pwa_script = read("assets/pwa.js")
        if "navigator.serviceWorker" not in pwa_script or ".register(" not in pwa_script:
            fail(errors, "assets/pwa.js does not register the service worker")
    if Path("service-worker.js").exists():
        service_worker = read("service-worker.js")
        for needle in ["offline.html", "site_data.json", "search-index.json", "`${BASE}s/`", "`${BASE}p/`"]:
            if needle not in service_worker:
                fail(errors, f"service-worker.js missing cached application resource {needle}")

    if Path("analytics_output/expanded_classification_deepseek.csv").exists():
        classified = load_csv("analytics_output/expanded_classification_deepseek.csv")
        presentation_total = int(summary.get("unique_presentations", 0))
        if len(classified) != presentation_total:
            fail(errors, "expanded DeepSeek classification is not complete for all unique presentations")
        invalid_levels = [row for row in classified if row.get("gumilyov_level") not in {"1", "2", "3"}]
        if invalid_levels:
            fail(errors, "expanded DeepSeek classification contains an invalid Gumilyov level")

    if Path("sitemap.xml").exists():
        sitemap = read("sitemap.xml")
        if "<sitemapindex" in sitemap:
            # Recursively load sub-sitemaps mentioned in the sitemapindex
            sub_sitemaps = re.findall(r"<loc>(https://gasyoun\.github\.io/IndologyScholars/(sitemap_[^<]+))</loc>", sitemap)
            for _, filename in sub_sitemaps:
                if Path(filename).exists():
                    sitemap += "\n" + read(filename)
        for page in ["", "en.html", "search.html", "download-data.html", "data-quality.html", "s/", "conferences/", "p/", "themes/", "topics/", "topics/ramayana.html", "topics/mahabharata.html", "generations/", "cities/", "institutions/", "metrics-guide.html", "classification-criteria.html", "networks.html", "videos/"]:
            expected = "https://gasyoun.github.io/IndologyScholars/" + page
            if expected not in sitemap:
                fail(errors, f"sitemap.xml missing {expected}")
        if "https://gasyoun.github.io/IndologyScholars/404.html" in sitemap:
            fail(errors, "sitemap.xml should not include 404.html")
        if "<lastmod>" in sitemap or "<priority>" in sitemap:
            fail(errors, "sitemap.xml should not claim synthetic modification dates or priorities")
        for old_prefix in ("scholars/", "presentations/"):
            if f"https://gasyoun.github.io/IndologyScholars/{old_prefix}" in sitemap:
                fail(errors, f"sitemap.xml should not include removed route {old_prefix}")
        for page, _ in redirect_pages:
            expected = f"https://gasyoun.github.io/IndologyScholars/s/{page.name}"
            if expected in sitemap:
                fail(errors, f"sitemap.xml should not include legacy redirect {expected}")
        sample_profiles = sorted(scholar_ids)[:5]
        for scholar_id in sample_profiles:
            slug = slug_to_target.get(scholar_id, scholar_id)
            expected = f"https://gasyoun.github.io/IndologyScholars/s/{slug}.html"
            if expected not in sitemap:
                fail(errors, f"sitemap.xml missing {expected}")

    if Path("search-index.json").exists():
        content = read("search-index.json")
        if len(re.findall(r'"type":"Scholar"', content)) != len(scholars):
            fail(errors, "search-index.json scholar count does not match site_data.json")
        if '"type":"Video"' not in content:
            fail(errors, "search-index.json should retain the standalone video catalogue entries")
        if '"url":"scholars/' in content or '"url":"presentations/' in content:
            fail(errors, "search-index.json still exposes removed public routes")

    for removed_dir in ("scholars", "presentations"):
        if Path(removed_dir).exists():
            fail(errors, f"Removed public route directory still exists: {removed_dir}/")

    tavastsherna = next((s for s in scholars if s.get("id") == "PERS_11da326d"), None)
    if tavastsherna and tavastsherna.get("all_affiliations") != ["СПбГУ, Восточный факультет"]:
        fail(errors, "Tavastsherna public affiliations should collapse to the verified SPbU faculty trajectory")
    timeline_talks = [
        talk
        for years in data.get("timeline", {}).values()
        for talks in years.values()
        for talk in talks
    ]
    dialect_talk = next((talk for talk in timeline_talks if talk.get("presentation_id") == "PRES_10c2c66c17"), None)
    if dialect_talk and str(dialect_talk.get("title") or "").startswith("(СПбГУ)"):
        fail(errors, "Institutional parenthetical leaked into the public dialect presentation title")
    dhatu_talk = next((talk for talk in timeline_talks if talk.get("presentation_id") == "PRES_5b0c00b805"), None)
    if dhatu_talk and "Дхатупатхе" not in str(dhatu_talk.get("title") or ""):
        fail(errors, "Dhatupatha public title has not been editorially normalized")

    if Path("404.html").exists():
        not_found = read("404.html")
        if 'name="robots" content="noindex, follow"' not in not_found:
            fail(errors, "404.html should be noindex, follow")

    if Path("analytics_output/data_quality_report.json").exists():
        report = read("analytics_output/data_quality_report.json")
        report_json = json.loads(report)
        if not report_json.get("schema_version"):
            fail(errors, "data_quality_report.json missing schema_version")
        if '"dangling_sessions"' not in report or '"checks"' not in report:
            fail(errors, "data_quality_report.json missing expected checks")

    if Path("datapackage.json").exists():
        datapackage = json.loads(read("datapackage.json"))
        if not datapackage.get("schema_version"):
            fail(errors, "datapackage.json missing schema_version")
        resources = {item.get("name"): item for item in datapackage.get("resources", [])}
        for resource_name in [
            "site-data",
            "data-dictionary",
            "data-quality-report",
            "presentation-id-manifest",
            "id-stability-audit",
            "field-provenance-biographical",
            "field-provenance-authority",
            "field-provenance-themes",
            "verified-affiliation-spans",
            "network-nodes",
            "network-edges",
            "publication-file-manifest",
        ]:
            if resource_name not in resources:
                fail(errors, f"datapackage.json missing resource {resource_name}")
        for resource_name in ["site-data", "data-quality-report", "presentation-id-manifest", "network-nodes", "network-edges", "publication-file-manifest"]:
            if resource_name in resources and "schema" not in resources[resource_name]:
                fail(errors, f"datapackage.json resource {resource_name} missing schema")

    if Path("data_dictionary.md").exists():
        dictionary = read("data_dictionary.md")
        for needle in [
            "Stable Identifier Policy",
            "Provenance Sidecars",
            "Network Exports",
            "presentation_id_manifest.csv",
            "network_edges.csv",
            "publication_file_manifest.csv",
        ]:
            if needle not in dictionary:
                fail(errors, f"data_dictionary.md missing {needle}")

    if Path("analytics_output/presentation_id_manifest.csv").exists() and Path("conferences.db").exists():
        manifest_rows = max(0, len(read("analytics_output/presentation_id_manifest.csv").splitlines()) - 1)
        if manifest_rows != db_presentation_rows:
            fail(errors, f"presentation_id_manifest.csv has {manifest_rows} rows but DB presentation rows={db_presentation_rows}")

    for provenance_path in [
        "analytics_output/field_provenance_biographical.csv",
        "analytics_output/field_provenance_authority.csv",
        "analytics_output/field_provenance_themes.csv",
    ]:
        if Path(provenance_path).exists():
            lines = read(provenance_path).splitlines()
            if len(lines) < 2:
                fail(errors, f"{provenance_path} has no provenance rows")

    if Path("analytics_output/network_nodes.csv").exists():
        with open("analytics_output/network_nodes.csv", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            node_types = {row.get("node_type") for row in reader}
        expected_node_types = {"person", "event", "organization", "theme"}
        if not node_types:
            fail(errors, "network_nodes.csv has no node rows")
        if not node_types.issubset(expected_node_types):
            fail(errors, f"network_nodes.csv has unexpected node types: {sorted(node_types - expected_node_types)}")

    if Path("analytics_output/network_edges.csv").exists():
        with open("analytics_output/network_edges.csv", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            edge_types = {row.get("edge_type") for row in reader}
        expected_edge_types = {
            "person_event",
            "person_organization",
            "person_theme",
            "organization_theme",
            "person_person_copresentation",
            "person_person_same_session",
        }
        if not edge_types:
            fail(errors, "network_edges.csv has no edge rows")
        if not edge_types.issubset(expected_edge_types):
            fail(errors, f"network_edges.csv has unexpected edge types: {sorted(edge_types - expected_edge_types)}")

    if Path("analytics_output/publication_file_manifest.csv").exists():
        with open("analytics_output/publication_file_manifest.csv", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            manifest_rows = list(reader)
        if not manifest_rows:
            fail(errors, "publication_file_manifest.csv has no file rows")
        manifest_paths = {row.get("path") for row in manifest_rows}
        for path in ["index.html", "datapackage.json", "analytics_output/network_edges.csv"]:
            if path not in manifest_paths:
                fail(errors, f"publication_file_manifest.csv missing {path}")
        for row in manifest_rows:
            digest = row.get("sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                fail(errors, f"publication_file_manifest.csv has invalid sha256 for {row.get('path')}")
                break

    if Path("analytics_output/publication_file_manifest.json").exists():
        manifest_json = json.loads(read("analytics_output/publication_file_manifest.json"))
        if not manifest_json.get("schema_version"):
            fail(errors, "publication_file_manifest.json missing schema_version")
        if manifest_json.get("file_count", 0) < 1:
            fail(errors, "publication_file_manifest.json has no files")

    if Path("analytics_output/id_stability_audit.json").exists():
        audit = json.loads(read("analytics_output/id_stability_audit.json"))
        audit_summary = audit.get("summary", {})
        if audit_summary.get("changed_ids_for_same_stable_key") != 0:
            fail(errors, "id_stability_audit.json reports changed presentation IDs for matching stable keys")
        if audit_summary.get("missing_stable_keys_after") != 0 or audit_summary.get("new_stable_keys_after") != 0:
            fail(errors, "id_stability_audit.json reports stable-key drift")
        if audit_summary.get("after_duplicate_stable_key_rows") != 0:
            fail(errors, "id_stability_audit.json reports duplicate stable-key rows")

    if errors:
        print("Publication validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Publication validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
