"""Internal link/anchor, stable-ID, and FAIR-metadata integrity audit (H718).

Read-only over the tracked publication surface: it never edits anything and it
never touches the network (external-link liveness is out of scope by design —
only enwiki is reachable from CI, and outages are SERVER_OUTAGES.md business).

Checks:
  1. Internal links in tracked HTML pages resolve to files in the repo.
  2. Fragment links (#anchor) point at an existing id/name in the target page.
  3. Stable IDs are well-formed and unique (person_ids, public_ids,
     slug_redirects, authority_ids).
  4. FAIR metadata: datapackage.json resources exist on disk and carry
     name/description/format; CITATION.cff basics; data_dictionary.md covers
     every root datapackage resource; sitemap <loc> URLs map to real files.

Output: per-defect-class counts + examples on stdout, full defect rows in
scratch/link_integrity_defects.csv (scratch/ per repo rule 5 — not published).

Usage: python tools/audit_archive_integrity.py
"""

import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
SITE_BASE = 'https://gasyoun.github.io/IndologyScholars/'

# Directories that are not part of the published surface.
EXCLUDED_PREFIXES = (
    'html_cache/',    # raw scraped inputs
    'scratch/',       # experiments and logs (repo rule 5)
    'templates/',     # page fragments, not standalone pages
    'archive/',       # frozen historical snapshots
    '_site/',         # derived Pages artifact
    'gemini_handoff/',
    'philology-research-agents/',
    'mockups/',      # design mockups; links are aspirational by design
)

SKIP_SCHEMES = ('http:', 'https:', 'mailto:', 'tel:', 'data:', 'javascript:', 'ftp:')

DEPLOY_ALIASES = {}

# Files that exist only in the deployed artifact (written by
# prepare_pages_artifact.py), not in the source tree. IndologyArchive/index.html
# is a redirect stub to gasyoun/IndologyArchiveAtlas's own Pages site (H460
# split) kept for old inbound links; the archive itself no longer lives here.
DEPLOY_SYNTHESIZED = {'IndologyArchive/index.html'}

# Pages whose anchors are attached client-side (JS render); fragments into
# them are invisible to a static parse and are reported separately.
DYNAMIC_ANCHOR_PAGES = {'hypotheses.html'}


class PageParser(HTMLParser):
    """Collect anchor ids and outgoing links from one HTML page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []  # (attr, value)

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get('id'):
            self.ids.add(d['id'])
        if tag == 'a' and d.get('name'):
            self.ids.add(d['name'])
        if tag in ('a', 'area', 'link') and d.get('href'):
            self.links.append(('href', d['href']))
        elif tag in ('img', 'script', 'iframe', 'source', 'audio', 'video') and d.get('src'):
            self.links.append(('src', d['src']))


def tracked_files():
    out = subprocess.run(
        ['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True,
        encoding='utf-8', check=True)
    return [line for line in out.stdout.splitlines() if line]


def is_published_html(path):
    if not path.endswith('.html'):
        return False
    return not path.startswith(EXCLUDED_PREFIXES)


def resolve_internal(page, raw):
    """Return (repo_relative_path or None, fragment) for one raw link value.

    None path means the link is external / non-file and should be skipped.
    """
    value = raw.strip()
    if not value or value.startswith(SKIP_SCHEMES) or value.startswith('//'):
        # Site-internal absolute URLs are still checkable.
        if value.startswith(SITE_BASE):
            value = '/' + 'IndologyScholars/' + value[len(SITE_BASE):]
        else:
            return None, ''
    split = urlsplit(value)
    fragment = unquote(split.fragment)
    path = unquote(split.path)
    if not path:  # pure fragment: same-page anchor
        return page, fragment
    if path.startswith('/IndologyScholars/'):
        rel = path[len('/IndologyScholars/'):]
    elif path.startswith('/'):
        rel = path[1:]
    else:
        rel = (Path(page).parent / path).as_posix()
    # normalize ../ segments
    parts = []
    for seg in rel.split('/'):
        if seg == '..':
            if parts:
                parts.pop()
        elif seg not in ('', '.'):
            parts.append(seg)
    if parts and parts[0] in DEPLOY_ALIASES:
        parts[0] = DEPLOY_ALIASES[parts[0]]
    rel = '/'.join(parts)
    if rel.endswith('/') or rel == '':
        rel += 'index.html'
    return rel, fragment


def main():
    defects = []  # (defect_class, location, detail)

    def defect(cls, location, detail):
        defects.append((cls, location, detail))

    tracked = set(tracked_files())
    pages = sorted(p for p in tracked if is_published_html(p))

    # ---- parse all pages ------------------------------------------------
    page_ids = {}
    page_links = {}
    for page in pages:
        parser = PageParser()
        try:
            parser.feed((ROOT / page).read_text(encoding='utf-8', errors='replace'))
        except Exception as exc:  # malformed page is itself a defect
            defect('unparseable-page', page, repr(exc))
            continue
        page_ids[page] = parser.ids
        page_links[page] = parser.links

    # ---- 1+2: link and anchor resolution --------------------------------
    exists_cache = {}

    def target_exists(rel):
        if rel not in exists_cache:
            # GitHub Pages serves extensionless URLs from <name>.html
            exists_cache[rel] = (rel in tracked or (ROOT / rel).exists()
                                 or f'{rel}.html' in tracked
                                 or rel in DEPLOY_SYNTHESIZED)
        return exists_cache[rel]

    for page, links in page_links.items():
        for attr, raw in links:
            rel, fragment = resolve_internal(page, raw)
            if rel is None:
                continue
            if not target_exists(rel):
                # A directory link without trailing slash?
                if not (ROOT / rel).is_dir():
                    defect('broken-internal-link', page, f'{attr}="{raw}" -> {rel}')
                    continue
            if fragment:
                target = rel if rel in page_ids else None
                if target is None:
                    # fragment into a non-audited file (css/js/csv) — skip
                    if rel.endswith('.html') and rel in tracked:
                        # published page outside audit set — parse on demand
                        parser = PageParser()
                        try:
                            parser.feed((ROOT / rel).read_text(encoding='utf-8', errors='replace'))
                            page_ids[rel] = parser.ids
                            target = rel
                        except Exception:
                            continue
                    else:
                        continue
                if fragment not in page_ids[target] and fragment != 'top':
                    cls = ('dynamic-anchor-page' if rel in DYNAMIC_ANCHOR_PAGES
                           else 'missing-anchor')
                    defect(cls, page, f'{attr}="{raw}" -> {rel}#{fragment}')

    # ---- 3: stable-ID consistency ---------------------------------------
    pers_re = re.compile(r'^PERS_[0-9a-f]{8}$')

    person_ids = json.loads((ROOT / 'person_ids.json').read_text(encoding='utf-8'))
    for key, pid in person_ids.get('normalized_keys', {}).items():
        if not pers_re.match(pid):
            defect('malformed-person-id', 'person_ids.json', f'{key}: {pid}')

    public_ids = json.loads((ROOT / 'public_ids.json').read_text(encoding='utf-8'))
    scholars = public_ids.get('scholars', {})
    for pid in scholars:
        if not pers_re.match(pid):
            defect('malformed-person-id', 'public_ids.json', pid)
    nums = Counter(scholars.values())
    for num, count in nums.items():
        if count > 1:
            dupes = [k for k, v in scholars.items() if v == num]
            defect('duplicate-public-id', 'public_ids.json', f'{num}: {dupes}')

    slug_redirects = json.loads((ROOT / 'slug_redirects.json').read_text(encoding='utf-8'))
    for slug, pid in slug_redirects.items():
        if not pers_re.match(pid):
            defect('malformed-person-id', 'slug_redirects.json', f'{slug}: {pid}')
        elif pid not in scholars:
            defect('dangling-slug-redirect', 'slug_redirects.json',
                   f'{slug} -> {pid} (no public id)')

    authority = json.loads((ROOT / 'authority_ids.json').read_text(encoding='utf-8'))
    wd_re = re.compile(r'^Q[1-9][0-9]*$')
    orcid_re = re.compile(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')
    openalex_re = re.compile(r'^A[1-9][0-9]*$')
    for pid, rec in authority.get('persons', {}).items():
        if not pers_re.match(pid):
            defect('malformed-person-id', 'authority_ids.json persons', pid)
        for field, pattern in (('wikidata', wd_re), ('orcid', orcid_re),
                               ('openalex', openalex_re)):
            value = rec.get(field)
            if value and not pattern.match(str(value)):
                defect('malformed-authority-value', 'authority_ids.json',
                       f'{pid}.{field} = {value}')
        # vocabulary: stored values + PUBLIC_AUTHORITY_CONFIDENCE gate
        # (publication_helpers.py) which publishes confirmed/manual/high
        if rec.get('confidence') not in (None, 'candidate', 'confirmed',
                                         'verified', 'manual', 'high'):
            defect('malformed-authority-value', 'authority_ids.json',
                   f'{pid}.confidence = {rec.get("confidence")}')

    # scholar profile pages exist for every public id; assignments are
    # retained forever by design, so ids absent from the current corpus are
    # informational, not defects
    live_ids = set()
    site_data = json.loads((ROOT / 'site_data.json').read_text(encoding='utf-8'))
    for group in ('scholars', 'historical_scholars'):
        live_ids.update(s.get('id') for s in site_data.get(group, []))
    for pid in scholars:
        rel = f's/{pid}.html'
        if rel not in tracked:
            cls = ('missing-scholar-page' if pid in live_ids
                   else 'legacy-retained-public-id')
            defect(cls, 'public_ids.json', f'{pid} -> {rel}')

    # ---- 4: FAIR metadata ------------------------------------------------
    # Indology/ split into gasyoun/IndologyArchiveAtlas (H460) — its FAIR
    # metadata is audited there now, not here.
    for dp_path in ('datapackage.json',):
        full = ROOT / dp_path
        if not full.exists():
            defect('missing-fair-file', dp_path, 'datapackage.json absent')
            continue
        dp = json.loads(full.read_text(encoding='utf-8'))
        base = full.parent
        names = Counter()
        for res in dp.get('resources', []):
            name = res.get('name', '<unnamed>')
            names[name] += 1
            for field in ('name', 'path', 'description', 'format'):
                if not res.get(field):
                    defect('incomplete-resource-metadata', dp_path,
                           f'{name}: missing {field}')
            rp = res.get('path')
            if rp and not rp.startswith(('http://', 'https://')):
                if not (base / rp).exists():
                    defect('missing-resource-file', dp_path, f'{name}: {rp}')
        for name, count in names.items():
            if count > 1:
                defect('duplicate-resource-name', dp_path, f'{name} x{count}')
        for field in ('name', 'title', 'description', 'licenses'):
            if not dp.get(field):
                defect('incomplete-package-metadata', dp_path, f'missing {field}')

    for cff_path in ('CITATION.cff',):
        full = ROOT / cff_path
        if not full.exists():
            defect('missing-fair-file', cff_path, 'CITATION.cff absent')
            continue
        text = full.read_text(encoding='utf-8')
        for field in ('cff-version', 'title', 'authors', 'version',
                      'date-released', 'license'):
            if not re.search(rf'^{re.escape(field)}\s*:', text, re.M):
                defect('incomplete-citation-metadata', cff_path, f'missing {field}')
        if 'orcid' not in text.lower():
            defect('incomplete-citation-metadata', cff_path, 'no author ORCID')

    dd_text = (ROOT / 'data_dictionary.md').read_text(encoding='utf-8')
    root_dp = json.loads((ROOT / 'datapackage.json').read_text(encoding='utf-8'))
    for res in root_dp.get('resources', []):
        rp = res.get('path', '')
        if rp == 'data_dictionary.md':  # the dictionary need not describe itself
            continue
        base_name = rp.rsplit('/', 1)[-1]
        if base_name and base_name not in dd_text and res.get('name', '') not in dd_text:
            defect('undocumented-resource', 'data_dictionary.md',
                   f'{res.get("name")} ({rp})')

    loc_re = re.compile(r'<loc>([^<]+)</loc>')
    for sm in sorted(p for p in tracked if re.match(r'^sitemap[^/]*\.xml$', p)):
        for loc in loc_re.findall((ROOT / sm).read_text(encoding='utf-8')):
            if not loc.startswith(SITE_BASE):
                defect('foreign-sitemap-url', sm, loc)
                continue
            rel = unquote(urlsplit(loc[len(SITE_BASE):]).path)
            first = rel.split('/', 1)[0]
            if first in DEPLOY_ALIASES:
                rel = DEPLOY_ALIASES[first] + rel[len(first):]
            if rel.endswith('/') or rel == '':
                rel += 'index.html'
            if (rel not in tracked and not (ROOT / rel).exists()
                    and f'{rel}.html' not in tracked
                    and rel not in DEPLOY_SYNTHESIZED):
                defect('broken-sitemap-url', sm, loc)

    # ---- report -----------------------------------------------------------
    out_csv = ROOT / 'scratch' / 'link_integrity_defects.csv'
    out_csv.parent.mkdir(exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['defect_class', 'location', 'detail'])
        writer.writerows(sorted(defects))

    n_links = sum(len(v) for v in page_links.values())
    print(f'pages audited: {len(pages)}')
    print(f'links inspected: {n_links}')
    print(f'defects: {len(defects)} -> {out_csv.relative_to(ROOT)}')
    by_class = Counter(cls for cls, _, _ in defects)
    examples = defaultdict(list)
    for cls, loc, detail in defects:
        if len(examples[cls]) < 3:
            examples[cls].append(f'{loc}: {detail}')
    for cls, count in by_class.most_common():
        print(f'\n{cls}: {count}')
        for ex in examples[cls]:
            print(f'  e.g. {ex}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
