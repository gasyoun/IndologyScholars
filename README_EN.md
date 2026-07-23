# IndologyScholars: Archive of Talks in Russian Indology

_Created: 24-04-2026 · Last updated: 23-07-2026_

[Русская версия](https://github.com/gasyoun/IndologyScholars/blob/main/README.md) | [Developer documentation](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development-en.md)

**IndologyScholars** is an open navigation archive of programmes from two
Russian Indological forums: the Zograf Readings in St Petersburg and the
Roerich Readings in Moscow. It connects speakers, talk titles, participation
years, recorded affiliations, thematic categories, and available video records.
Sibling subsystems cover the closed Google Group of the Sanskrit Zealots Society
(`nagari/`), its public VK wall (`vk-ors/`), and the spun-out INDOLOGY-L atlas.

[Open the site](https://gasyoun.github.io/IndologyScholars/)

## Archive Coverage

The published speaker collection (`site_data.json` summary, current as of
23 July 2026) contains:

| Measure | Value |
| --- | ---: |
| Speaker profiles | 268 |
| Unique talks | 1362 |
| Author participations | 1388 |
| Programme years | 22, from 2004 to 2026 |
| Speakers found at both series | 41 |
| Zograf Readings only | 163 |
| Roerich Readings only | 64 |

The archive covers the Zograf Readings for 2004-2026 and the Roerich Readings
for 2007-2025. The 2026 Zograf programme is included as a preliminarily
published programme. A separate **historical prosopographical layer** (26
figures; `person_kind = historical`) is tracked outside the speaker counts.

## What You Can Explore

- The [main catalogue](https://gasyoun.github.io/IndologyScholars/) with
  searches by name, talk, city, and institution.
- [Scientific Hypotheses Registry](https://gasyoun.github.io/IndologyScholars/hypotheses.html) — an interactive multi-dimensional registry of 35 hypotheses with a 7-metric schema and glassmorphic UI.
- [Interactive Visualizations](https://gasyoun.github.io/IndologyScholars/findings/visualisations.html) —
  visual dashboard with stable IDs: Zograf × Roerich cohort overlaps, affiliation opacity timelines, and heatmaps.
- [Conference pages](https://gasyoun.github.io/IndologyScholars/conferences/)
  leading to individual years and programmes.
- [Thematic collections](https://gasyoun.github.io/IndologyScholars/themes/)
  and [generation cohorts](https://gasyoun.github.io/IndologyScholars/generations/).
- A [network map](https://gasyoun.github.io/IndologyScholars/networks.html) of
  co-authorship and programme co-presence.
- [Collection search](https://gasyoun.github.io/IndologyScholars/search.html),
  including individual talk pages and video links where recordings are known.
- [Non-participant indologist registry](https://gasyoun.github.io/IndologyScholars/indologists.html) —
  scholars outside the conference programmes, linked via roster enrichment.
- [«20 years of the Sanskrit Zealots Society»](https://gasyoun.github.io/IndologyScholars/nagari/) —
  retrospective of the closed Google Group (`nagari/`; source is rights-gated).
- [VK wall archive](https://github.com/gasyoun/IndologyScholars/tree/main/vk-ors) —
  public VK page posts with SQLite+FTS5 and a four-layer analysis (`vk-ors/`).
- [INDOLOGY Archive Atlas](https://gasyoun.github.io/IndologyArchiveAtlas/) —
  atlas of the public INDOLOGY-L mailing list, **spun out** to
  [`gasyoun/IndologyArchiveAtlas`](https://github.com/gasyoun/IndologyArchiveAtlas)
  (H460). The legacy path
  […/IndologyScholars/IndologyArchive/](https://gasyoun.github.io/IndologyScholars/IndologyArchive/)
  redirects there; this repo keeps only a one-way feed for Renou comparison
  (`tools/fetch_indology_feed.py`).

## Reading the Records

- An affiliation is reported from an official programme or a separately
  verified source. A city marker alone is not treated as an institution.
- When a verified affiliation has no documented end date and a later programme
  supplies no new institution, its continuation is displayed as a tentative
  inference marked `(?)`. A stated end date or an explicit new affiliation
  stops that continuation.
- Levels `L1`-`L3` describe the scale of the argument stated in a talk title,
  not the quality of the work, the standing of its speaker, or the importance
  of its subject. See the
  [classification criteria](https://gasyoun.github.io/IndologyScholars/classification-criteria.html).
- Lifespan dates, degrees, and external authority identifiers are shown only
  when supported by a verifiable source; unknown values remain unfilled.

## Data and Citation

Downloadable datasets, file formats, and restrictions are collected on the
[data download page](https://gasyoun.github.io/IndologyScholars/download-data.html).
See the [methodology](https://gasyoun.github.io/IndologyScholars/methodology.html)
and [known limitations](https://gasyoun.github.io/IndologyScholars/known-limitations.html)
pages for interpretive context.

To cite the project, use the
[citation guidance](https://gasyoun.github.io/IndologyScholars/how-to-cite.html)
or [CITATION.cff](CITATION.cff).

## Documentation

- [Разработка и воспроизводимость, на русском](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development.md)
- [Development and reproducibility, in English](https://github.com/gasyoun/IndologyScholars/blob/main/docs/development-en.md)
- [Technical classification audit](https://github.com/gasyoun/IndologyScholars/blob/main/docs/classification-audit-en.md)
- [Data dictionary](https://github.com/gasyoun/IndologyScholars/blob/main/data_dictionary.md)
- [Documentation index](https://github.com/gasyoun/IndologyScholars/blob/main/docs/README.md)

Historical analytical documents and manuscripts in this repository may refer
to earlier corpus snapshots; the published pages and data exports describe the
current site collection.

## Licence

Code, templates, and validators are released under [Apache-2.0](https://github.com/gasyoun/IndologyScholars/blob/main/LICENSE).
Normalized metadata and derived CSV/JSON/SQLite exports are reusable under
CC-BY-4.0 with archive attribution. Cached conference programmes, source
quotations, and third-party material remain under their original rightsholders;
see [reuse rights](https://github.com/gasyoun/IndologyScholars/blob/main/docs/reuse-rights.md).

_Dr. Mārcis Gasūns_
