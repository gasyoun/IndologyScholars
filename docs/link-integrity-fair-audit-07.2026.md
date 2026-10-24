# Internal link/anchor integrity + FAIR metadata audit — July 2026 (H718)

_Created: 12-07-2026 · Last updated: 12-07-2026_

Audit of the archive's internal integrity — links between records, pages and data
files inside the repository and the generated site — plus stable-ID consistency and
FAIR-metadata completeness per record type. Executed by Fable 5 (`claude-fable-5`)
under handoff
[H718](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H718-Fable_IndologyScholars_archive-link-integrity-fair-pass_11.07.26.md).
External-link liveness was deliberately **not** probed (only enwiki is reachable
from this host; outages are the outage board's business).

## Method

New read-only auditor:
[tools/audit_archive_integrity.py](https://github.com/gasyoun/IndologyScholars/blob/main/tools/audit_archive_integrity.py)
(`python tools/audit_archive_integrity.py`; full defect rows land in
`scratch/link_integrity_defects.csv`, not published). It complements — does not
duplicate —
[validate_publication.py](https://github.com/gasyoun/IndologyScholars/blob/main/validate_publication.py),
which already covers canonical-link tags, removed routes and authority-value
formats but not the full link+anchor graph.

Inventory: **2,504 published HTML pages** (root site + `p/` presentations + `s/`
scholars + taxonomy dirs + `Indology/dashboard/`), **196,786 internal link
occurrences**, 4 stable-ID registries (`person_ids.json`, `public_ids.json`,
`slug_redirects.json`, `authority_ids.json`), 2 datapackages, 2 `CITATION.cff`
files, `data_dictionary.md`, 5 sitemaps. Excluded as non-published surface:
`html_cache/`, `scratch/`, `templates/`, `archive/`, `mockups/`,
`gemini_handoff/`, `philology-research-agents/`.

The checker encodes two deploy-time facts to avoid false positives:
`IndologyArchive/…` is the public alias of source `Indology/…` (written by
[prepare_pages_artifact.py](https://github.com/gasyoun/IndologyScholars/blob/main/prepare_pages_artifact.py)),
and GitHub Pages serves extensionless URLs from `<name>.html`.

## Findings (pre-fix baseline, per defect class)

| Defect class | Count | Verdict | Root cause |
|---|---:|---|---|
| broken-internal-link | 14 | **real, fixed** | `gumilyov/level-0.html` was a stale orphan (last written 01-06-2026): the generator skips level 0 when the group is empty but had no stale-file cleanup for `gumilyov/`, so the June page kept linking 7 removed greeting-talk `p/` pages and 5 removed non-scholar `s/` pages |
| self-perpetuating sitemap row | 1 | **real, fixed** | `sitemap_taxonomy.xml` globs `gumilyov/*.html` on disk, so the orphan re-advertised itself on every rebuild |
| dangling-slug-redirect | 5 | **real, fixed** | 5 rows in [slug_redirects.json](https://github.com/gasyoun/IndologyScholars/blob/main/slug_redirects.json) pointed at merged-away `PERS_` ids with no public id; the generator silently skips such rows, so the published old URLs 404ed |
| dynamic-anchor deep links | 33 | **real, fixed** | 33 `hypotheses.html#H16`-style links (from `findings/visualisations.html` etc.) target card ids that exist only after the client-side render — the browser's fragment scroll had already failed by then, and the page had no hash-restore handler |
| incomplete-citation-metadata | 2 | **real, fixed** | `Indology/CITATION.cff` lacked `version` and any author ORCID (authors listed only the pipeline) |
| wrong-org repository URL | 2 | **real, fixed** (found during fix) | `REPOSITORY_URL` in [public_metadata.py](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/indology_archive_research/public_metadata.py) said `sanskrit-lexicon/IndologyScholars`; the repo is `gasyoun/IndologyScholars` — propagated into both `CITATION.cff` and `datapackage.json` |
| stale datapackage stats | — | **real, fixed** | `Indology/datapackage.json` byte/row counts had drifted from the on-disk files since 01-07-2026 (e.g. `search_authors.json` 1,168,397 → 1,762,389 bytes); regenerated |
| legacy-retained-public-id | 27 | informational | 27 `public_ids.json` scholar numbers whose persons left the corpus (dedup merges / roster changes); assignments are retained forever **by design** ("Existing assignments are retained when the site is rebuilt") |
| malformed IDs / duplicate IDs | 0 | clean | all `PERS_` ids well-formed and unique; Wikidata/ORCID/OpenAlex values in `authority_ids.json` all well-formed; confidence vocabulary consistent with `PUBLIC_AUTHORITY_CONFIDENCE` |
| missing scholar pages | 0 | clean | all 268 live + 26 historical scholars have profile pages |
| missing datapackage resources | 0 | clean | all 40 root + all Indology resources exist on disk with name/description/format |
| undocumented resources | 0 | clean | every root datapackage resource is described in [data_dictionary.md](https://github.com/gasyoun/IndologyScholars/blob/main/data_dictionary.md) |
| broken sitemap URLs | 0 | clean | after the deploy-alias correction, all 5 sitemaps resolve |

**Post-fix audit: 60 rows remain, all informational** — the 27 by-design legacy
ids and the 33 hypothesis deep links, which are now functionally restored
client-side but remain statically invisible to a parser (reported under a
separate `dynamic-anchor-page` class so future runs don't re-flag them as
broken).

## Fixes landed (all count-safe)

None of these touch classification data, corpus records, or any number the A26
data paper cites; presentation/scholar/talk counts are byte-identical.

1. **Deleted stale `gumilyov/level-0.html`** and added a stale-level-page
   cleanup to `generate_gumilyov_pages()` in
   [generate_publication_pages.py](https://github.com/gasyoun/IndologyScholars/blob/main/generate_publication_pages.py)
   (mirrors the cleanup `s/` already had), plus removed the orphan's
   self-perpetuating row from `sitemap_taxonomy.xml` (the regenerated sitemap
   drops it identically).
2. **Remapped the 5 dangling slug redirects** to the live merged-into persons,
   following the file's own existing convention (`mekhakyan-fef030` →
   canonical id): `kogan`→`PERS_3009a9e0`, `mekhakyan-6e2007`→`PERS_f2fef030`,
   `shrestkha`→`PERS_b8bade8d`, `v-m-shelkovich`→`PERS_8a8c5d8b`,
   `yuditskaya-c4d444`→`PERS_8e117242`. Old published URLs become redirects
   again on the next rebuild instead of 404s.
3. **Hash-restore for dynamic anchors** in
   [hypotheses.html](https://github.com/gasyoun/IndologyScholars/blob/main/hypotheses.html):
   after the card render, `location.hash` is scrolled to manually. Verified
   end-to-end on a local server: `hypotheses.html#H16` lands the H16 card at
   viewport top (`getBoundingClientRect().top == 0`).
4. **FAIR completion of the Indology atlas metadata** via its generator
   (`write_citation` in `public_metadata.py`, then regenerated
   `Indology/CITATION.cff` + `Indology/datapackage.json`): added
   `version: "0.1.0"` (from `indology_archive_research.__version__`), added the
   human author with ORCID (`Gasūns, Mārcis` — 0000-0003-4513-884X, per the
   sole-authorship ruling for the data paper), corrected `repository-code` /
   `repository` to `gasyoun/IndologyScholars`, and refreshed the drifted
   byte/row statistics.

## Verification

`python validate_publication.py` — passed. `python -m pytest` — 147/147 passed.
`python -m py_compile` on all touched modules — clean.
`python tools/audit_archive_integrity.py` — 0 remaining defects outside the two
informational classes.

## Observations left for a human (mirrored to GTD)

- **`url_slug` "vladimir" for Шелкович Владимир Михайлович** — the canonical
  scholar URL `s/vladimir.html` is a bare first name, the only such slug in the
  corpus. Renaming to `vladimir-shelkovich` would break a published URL (needs a
  `slug_redirects.json` row minted in the same change). A human should decide
  whether the URL persistence cost is worth the cleaner identifier.
- Known limitations reported, not re-fixed here (fenced to their own handoffs):
  the Renou rule-table substring defect is
  [H459](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H459-Sonnet_IndologyScholars_renou-rules-anchor-fix-and-dedupe_10.07.26.md)'s
  scope; the `Indology/` repo split + DOI is
  [H460](https://github.com/gasyoun/Uprava/blob/main/handoffs/H460-Sonnet_IndologyScholars_indology-atlas-repo-split-doi_10.07.26.md)'s;
  Zenodo DOI deposition remains frozen org-wide until after 15-07-2026.

_Dr. Mārcis Gasūns_
