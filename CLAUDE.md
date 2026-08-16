# CLAUDE.md

_Created: 19-05-2026 · Last updated: 16-08-2026_

`IndologyScholars` is an open **navigation archive of two Russian Indology
forums** — Зографские чтения (St Petersburg) and Рериховские чтения (Moscow) —
linking speakers, talk titles, years, affiliations, themes, and video.
Live site: [gasyoun.github.io/IndologyScholars](https://gasyoun.github.io/IndologyScholars/).

Org conventions live in [`../CLAUDE.md`](https://github.com/gasyoun/github-spine/blob/main/CLAUDE.md).
Before encodings or corpus data, read the
[Sanskrit context primer](https://github.com/gasyoun/github-spine/blob/main/SANSKRIT_CONTEXT_PRIMER.md).
Engineering instructions:
[docs/development-en.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development-en.md)
(RU: [docs/development.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development.md)).
[README.md](https://github.com/gasyoun/IndologyScholars/blob/main/README.md)
is the user-facing Russian description only.

## How to run

```bash
make all
python validate_publication.py
python -m pytest
```

Manual pipeline (if `make` is missing) is listed in
[docs/development-en.md](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development-en.md)
§ Build — `build_and_populate_db.py` → analytics → `generate_site_data.py` →
page generators. Requirements: Python 3.11+ and
[`requirements.txt`](https://github.com/gasyoun/IndologyScholars/blob/main/requirements.txt).

Before any Pages upload: `python scripts/publish_safety_gate.py` (fails
closed on gated H1899 files without a
[`curation/rights_approvals.json`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/rights_approvals.json)
record).

Frozen DOI snapshot: `python tools/freeze_article_data.py` →
`article/snapshots/`. Inter-rater: `tools/build_interrater_sample.py` +
`tools/compute_interrater_agreement.py`.

## Conventions

- Treat `site_data.json` and generated HTML/CSV/JSON as **derived**. Edit
  source or generator and rebuild.
- Preserve uncertainty: a continued open affiliation is `(?)`; an unvalidated
  classification is never published as `L2`.
- Geography (city aliases, coordinates, Wikidata Q-IDs) lives in
  [`assets/data/geography.json`](https://github.com/gasyoun/IndologyScholars/blob/main/assets/data/geography.json).
  Shared helpers such as `normalize_affiliation` belong in
  [`publication_helpers.py`](https://github.com/gasyoun/IndologyScholars/blob/main/publication_helpers.py)
  — do not duplicate them.
- Birth years: source of truth is `pipeline/biography.py` →
  `BIOGRAPHICAL_DATA` (keyed by `normalized_key`). Never treat
  `UPDATE person SET birth_year` as durable — rebuild reseeds `person`.
- Historical figures (`person_kind=historical`, from
  `curation/historical_persons.csv`) must **not** mix into published speaker
  counts (268).
- Sibling subsystems are **not** produced by `generate_publication_pages.py`:
  `nagari/` (closed Google Group), `vk-ors/` (VK wall). The INDOLOGY-L atlas
  lives in `gasyoun/IndologyArchiveAtlas`; this repo only fetches a small
  feed and redirects `/IndologyArchive/`.

## Do not touch

- Derived artifacts: `conferences.db`, `site_data.json`, `search-index.json`,
  `analytics_output/`, generated trees (`s/`, `p/`, `conferences/`, `themes/`,
  `cities/`, `institutions/`, `generations/`, `findings/`), generated HTML
  (`known-relationships.html`, `gender.html`, `mobility.html`, `voting.html`).
- `scratch/` — experiments only; never publish from it.
- `article/snapshots/` — freeze via the tool, do not hand-patch.

Danger facts:
[Uprava DANGER_FACTS.md](https://github.com/gasyoun/Uprava/blob/main/DANGER_FACTS.md)
and the generated block of
[AGENTS.md](https://github.com/gasyoun/IndologyScholars/blob/main/AGENTS.md).

_Dr. Mārcis Gasūns_
