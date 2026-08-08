# Russian Indological Research Archive: A Conference Corpus for Prosopography

**Mārcis Gasūns**  
Independent researcher, Obninsk, Russia  
ORCID: 0000-0003-4513-884X  

## Abstract

We present the IndologyScholars corpus: a structured, open-access dataset
of 1,362 conference presentations, 268 scholar profiles, and 1,388 author
participations drawn from published programs of the Zograf Readings (St.
Petersburg) and Roerich Readings (Moscow) between 2004 and 2026. The dataset
includes normalized speaker identities, institutional affiliations with
explicit provenance tagging, thematic classification (L1/L2), a three-level
argument-scale coding (G1–G3), video-record mapping, and external authority
identifiers (Wikidata, ORCID, VIAF, OpenAlex). All data are published as
SQLite, CSV, JSON, and RDF/Turtle under open licenses (CC BY 4.0 for the
derived metadata, Apache-2.0 for the pipeline code) with a Frictionless
Data Package manifest. The dataset supports prosopographic research,
scientometric studies of conference-based scholarly communities, digital
humanities methodology development, and cross-venue comparison of
intellectual traditions.

**Keywords:** Indology, conference proceedings, prosopography, digital
humanities, knowledge graph, linked open data, Russian academia

---

## 1. Introduction

The public conference program is a uniquely structured source for the
sociology of scholarship. Unlike curated bibliographies or citation indexes,
a conference program records the community's own selection of who may
present, what topic is considered relevant, and how the speaker's
institutional identity is described. For the humanities, where publication
formats are diverse and citation-based metrics are sparse, the conference
program offers a systematic window into disciplinary self-representation.

The Zograf Readings (St. Petersburg, 2004–2026) and Roerich Readings
(Moscow, 2007–2025) are the two longest-running public Indological forums in
Russia. Their programs have been publicly distributed as printed booklets,
PDFs, and web pages. This corpus is the first machine-readable normalization
of those programs across all available years, including the 2026 Zograf
program as a preliminary snapshot.

This paper describes the corpus construction, data model, and reuse
potential. A companion analytical article (Gasūns, submitted) discusses the
sociological findings derived from the dataset. The present work focuses on
the infrastructure: what was built, how it was built, and how international
scholars can access and extend it.

## 2. Corpus Construction

### 2.1 Source material

The primary sources are the published conference programs for 40 event
records (22 program years): the Zograf Readings (2004–2026, 22 events) and
the Roerich Readings (2007–2025, 18 events). Programs were preserved as
HTML in `html_cache/`. Five supplementary data layers are manually curated:

- `authority_ids.json` — external person identifiers with per-record confidence
- `curation/verified_affiliation_spans.csv` — dated institutional trajectories
- `curation/teacher_student.csv` — advisor/student relationships
- `curation/historical_persons.csv` — pre-Soviet and Soviet-era historical Indologists (see §3.1)
- `assets/data/geography.json` — city name aliases, coordinates, and Wikidata Q-IDs

### 2.2 Pipeline

The build pipeline is fully deterministic and reproducible:

1. `build_and_populate_db.py` — parses cached HTML programs into a normalized SQLite database (persons, presentations, sessions, events, venues)
2. `generate_analytics.py` — produces statistical reports, network CSV exports, and coauthorship review queues
3. `generate_site_data.py` — compiles the master JavaScript/JSON dataset with scholar profiles, timeline data, and thematic classification
4. `generate_publication_pages.py` — generates static HTML pages with JSON-LD structured data, sitemaps, and search indexes
5. `generate_lod.py` — exports the RDF/Turtle knowledge graph (`indology_knowledge_graph.ttl`)

All scripts are Python 3.11+ with dependencies in `requirements.txt`.
A full rebuild runs in under 2 minutes on consumer hardware.

### 2.3 Identity resolution

Speaker names were normalized from program-level variants (initials,
abbreviated first names, inconsistent Latin transliterations) into
deterministic person identifiers (`PERS_XXXX`). The normalization pipeline
uses patronymic matching, Cyrillic-to-Latin transliteration, and manual
override rules in `curation/person_aliases.csv`. Stable presentation
identifiers (`PRES_XXXX`) are derived from series, year, normalized title,
and speaker.

### 2.4 Thematic classification

Each presentation receives two independent classifications:

| Axis | Levels | Description |
|------|--------|-------------|
| Discipline (L1) | history_and_culture, religion_and_philosophy, literature_and_poetry, linguistics_and_philology, art_and_material_culture, unspecified | Primary disciplinary field |
| Historical period (L2) | vedic, classical, medieval, colonial, modern, contemporary, atemporal | Temporal scope |
| Argument scale (G1–G3) | G1=micro-case, G2=tradition/school, G3=civilizational/methodological | Scale of generalization |

L1/L2 codes were assigned by a rule-based classifier with LLM-assisted
review and manual expert overrides. The LLM pass used the DeepSeek
chat-completion API (`deepseek-chat` alias; prompt version
`expanded-corpus-v1-2026-05-25`, temperature 0; from the 2026-06 pipeline
revision onward the resolved model snapshot returned by the API is logged
per record in the `model_id` column). Argument-scale coding (canonical
column `argument_level`; G1=micro-case, G2=tradition/school,
G3=civilizational/methodological) follows a strict written protocol:
single-text/author/term studies are G1, broad traditions or schools are G2,
and inter-civilizational or methodological syntheses are G3.

All preliminary G2/G3 assignments passed a second, stricter audit pass.
This audit was performed by the same model under a different adjudication
prompt (`scale-audit-v2-2026-05-25`); it is a same-model consistency check,
not an independent rating, and is reported here as such. Independent
verification rests on the human inter-rater reliability study (blind coding
of a stratified sample with all rare G3 items included; agreement reported
as Cohen's κ with bootstrap confidence intervals, Krippendorff's α, and
Gwet's AC1, the latter because the heavily skewed level distribution makes
raw κ prevalence-sensitive).

### 2.5 Affiliation provenance

The dataset distinguishes between *reported affiliation* (the text as it
appears in the program) and *public affiliation* (the displayed value after
curation). A city-only marker (e.g., "Moscow") is not treated as an
institutional affiliation. Verified institutional trajectories use
externally sourced date intervals; open-ended continuations are marked `(?)`
until a new institution or end date is documented.

## 3. Data Model

### 3.1 Database schema

The SQLite database (`conferences.db`) uses a normalized relational schema
with 19 tables. The event/program core comprises `person`, `presentation`,
`presentation_person`, `session`, `event_day_venue`, `event_day`, `event`,
`event_series`, `venue`, and `media`; a curated knowledge layer adds
`organization`, `place`, `discipline`, `person_discipline`, `work`,
`work_discipline`, `person_role`, `relation`, and `data_assertion` (the
last stores per-fact provenance for curated assertions). The
`presentation_person` table supports multi-author presentations with role
labeling (`speaker`, `coauthor`).

The `person` table carries a `person_kind` discriminator separating the 268
conference participants from a curated historical prosopographical layer of
26 pre-contemporary Russian Indologists (`historical`), seeded from
`curation/historical_persons.csv` with Wikidata-sourced dates and
identifiers. All presentation-level counts reported in this paper (and all
published aggregate statistics) are computed over conference participants
only, via the `presentation_person` join.

### 3.2 Public dataset

The master public dataset (`site_data.json`) is a single JavaScript payload
containing:

| Section | Contents |
|---------|----------|
| `scholars` | 268 profiles with talks, affiliations, themes, external IDs |
| `timeline` | Year-by-year presentation grids per series |
| `summary` | Aggregate statistics |
| `stats` | Year-over-year talk counts |
| `geography_stats` | City-level participation heatmap |
| `network` | Co-occurrence nodes and edges |

### 3.3 Linked Open Data

The RDF/Turtle graph (`indology_knowledge_graph.ttl`) models scholars as
`foaf:Person`, presentations as `schema:PresentationDigitalDocument`,
conferences as `schema:Event`, and affiliations as
`schema:Organization`. Wikidata Q-IDs are published via `sameAs` links
where available. The graph is importable into standard triple stores
(Blazegraph, Virtuoso, Apache Jena).

### 3.4 External identifiers

Public authority records in `authority_ids.json` carry a per-record
confidence field (`manual`/`confirmed` vs. `candidate`); machine-suggested
matches enter the file only as `candidate` and are excluded from verified
counts until a human confirms them. Coverage over the 268 scholar profiles:

| Identifier | Coverage (as of 2026-07-11) | Of which unverified `candidate` |
|------------|------------------------------|---------------------------------|
| Wikidata | 3 (1.1%) | 2 |
| ORCID | 7 (2.6%) | 6 |
| OpenAlex | 14 (5.2%) | 13 |
| VIAF | 0 | — |
| RINC/eLIBRARY | 0 | — |
| Google Scholar | tracked but not yet mapped | — |

Coverage is low because the mapping requires human verification. OpenAlex
API-based candidate matching has been run (181 scholars returned at least
one candidate, 496 candidate rows in
`analytics_output/openalex_author_candidates.csv`), and all rows currently
await manual review. Once Wikidata items are created, VIAF harvesting
follows automatically.

## 4. Reuse Potential

### 4.1 Prosopography

The dataset supports quantitative prosopography of an academic community:
participation trajectories, institutional mobility, generational cohorts,
and inter-venue permeability. All 268 scholars have standardized Latin
transliterations, birth years (87.3% coverage), and talk-level thematic
classification.

### 4.2 Network analysis

Six network edge types are exported (`analytics_output/network_edges.csv`):
- `person_event` — participation traces
- `person_organization` — affiliation links
- `person_theme` — thematic engagement
- `organization_theme` — institutional thematic profiles
- `person_person_copresentation` — co-authorship (reviewed)
- `person_person_same_session` — session co-presence

Nodes and edges are available as CSV and as a JSON payload for D3.js/vis.js
visualization.

### 4.3 Text analysis

The corpus contains 1,362 Russian-language presentation titles suitable for:
- Keyword extraction and co-occurrence analysis
- Topic modeling (LDA)
- Diachronic vocabulary tracking
- Thematic classification benchmarking (human-labeled gold standard for L1/G1)

### 4.4 Knowledge graph integration

With Wikidata Q-ID coverage, the corpus becomes part of the linked open data
cloud. Researchers can write SPARQL queries joining Indological scholars
with co-authorship networks, institutional affiliations, and geographic
data from Wikidata.

### 4.5 Comparative methodology

The pipeline demonstrates a reproducible approach for converting
humanities conference programs into structured, queryable data. The same
method can be applied to other Indological forums (International Indology
Graduate Research Symposium, World Sanskrit Conference, European Conference
on South Asian Studies) for cross-venue comparison.

## 5. Data Access

### 5.1 Live site

https://gasyoun.github.io/IndologyScholars/

The site provides scholar profiles, presentation pages, conference
year-books, thematic indexes, network visualizations, a search interface,
and a download page.

### 5.2 Machine-readable outputs

| Format | Path | Description |
|--------|------|-------------|
| SQLite | `conferences.db` | Normalized relational database |
| JSON | `site_data.json` | Master public dataset |
| CSV | `analytics_output/*.csv` | 100+ statistical and review exports |
| RDF/Turtle | `indology_knowledge_graph.ttl` | Linked data graph |
| Data Package | `datapackage.json` | Frictionless manifest (40 curated resources) |
| CFF | `CITATION.cff` | Citation metadata |

### 5.3 Licensing and reuse conditions

The repository is dual-licensed, following the split declared in
`datapackage.json`:

- **Code** (the build pipeline, generators, validators, and tools) is
  licensed under **Apache License 2.0** (`LICENSE`).
- **Derived metadata** (the normalized dataset: `conferences.db`,
  `site_data.json`, analytics CSV exports, and the RDF graph) is licensed
  under **Creative Commons Attribution 4.0 International (CC BY 4.0)**.

The underlying conference programs are short factual listings that were
publicly distributed by the organizers; the dataset reproduces normalized
factual metadata (names, titles, dates, venues, affiliations), not the
prose of any copyrighted publication. Reusers should cite the dataset as
described in §7. Data about living persons are limited to public
professional facts; correction and objection procedures are documented in
`docs/persons-data-policy.md`.

### 5.4 Archived snapshot and data availability

A citable version of the dataset is archived at Zenodo (GitHub↔Zenodo integration):

**Gasūns, M. (2026).** *IndologyScholars: Russian Indological Research
Archive — Zograf and Roerich Readings Conference Corpus (2004–2026)*
[Data set]. Zenodo. Concept DOI: `10.5281/zenodo.21360652` (all versions);
version DOI: `10.5281/zenodo.21847873` (GitHub release `v1.6.7`, 2026-08-08). Both DOIs were
minted automatically by the Zenodo↔GitHub integration on release publish.

The frozen paper snapshot `article/snapshots/2026-07-17/` (produced by
`tools/freeze_article_data.py`) remains the scholarly freeze for A26 numbers;
it includes `conferences.db`, `site_data.json`, analytics CSVs, curation
files, and a SHA-256 manifest. The live Zenodo record archives the GitHub
release tree via the webhook (software/dataset bundle). Metadata template:
`article/zenodo_metadata.json`. Cite the **concept DOI** for the dataset
family; pin the **version DOI** when a specific release must be reproducible.

## 6. Limitations

1. **Source bias.** The corpus captures published programs, not actual
   attendance. Scheduled talks that were cancelled or substituted are
   retained as listed. Online presentations are tagged but not
   distinguished in the main count.

2. **Affiliation opacity.** 70.3% of Zograf participant entries list only
   a city, not an institution. This reflects the program's editorial
   format, not the absence of institutional employment. Researchers should
   not treat city-only labels as evidence of independent or
   non-institutional status.

3. **Geographic scope.** The corpus covers two St. Petersburg/Moscow
   forums. Other Russian Indological venues (Oriental Faculty seminars,
   regional conferences) and international participation are not included.

4. **Classification subjectivity.** L1 and argument-scale codes were
   assigned by a single coder with LLM assistance, and the strict G2/G3
   audit pass was a same-model check rather than an independent rating.
   A blind, stratified inter-rater sample (all G3 items, oversampled G2,
   n=100) has been prepared. A cross-model sanity check (a second LLM
   family coding the blind sample from title/year/series only) yielded
   Cohen's κ = 0.670 [95% CI 0.554–0.776] for L1 and κ = 0.553
   [0.400–0.694] for the argument level, with the G2/G3 boundary the
   weakest region (`docs/classification-reliability-packet.md`). This is
   cross-model agreement, not human inter-rater reliability; the human
   second-coder statistics on the same blind sheet will be reported before
   final deposition.

5. **Gender attribution.** Gender is inferred from Russian name morphology
   (patronymic, given name, surname declension), not self-identification.
   Names that do not permit reliable inference are reported as an explicit
   "unknown" category, and a manually verified validation sample with a
   published error rate accompanies the dataset
   (`tools/validate_gender_inference.py`). Correction and objection
   procedures for living persons are described in
   `docs/persons-data-policy.md`.

6. **Identifier coverage.** Wikidata, ORCID, VIAF, and OpenAlex mappings
   are minimal (§3.4), and most existing mappings are machine-suggested
   `candidate` records awaiting human confirmation. This limits
   cross-dataset linking and international discoverability. A
   candidate-matching pipeline exists and results are under human review.

7. **Birth-year coverage.** 34 of 268 scholars (12.7%) lack a birth year.
   This is a genuine source gap, not a name-matching failure: a Wikidata +
   `ru.wikipedia` identity pass and a further hand-curation search over
   institutional/dissertation sources resolved 0 of 34. The gap is
   concentrated among one-time presenters (29 of 34); the remaining 5
   recurring names (2-3 appearances each) were targeted directly and still
   yielded no verifiable birth year, since most are lower-profile
   researchers from `orientalstudies.ru` conference programmes with no
   biographical page. This inflates the missing-data share slightly in the
   age, generational-cohort, age-at-debut, and Kaplan-Meier analyses;
   affected rows are excluded rather than imputed.

7. **Name-heuristic false positives.** Identity resolution and roster
   expansion rely on heuristics over Russian name morphology (patronymic
   detection, transliteration matching, name-order parsing), and these
   heuristics are known to produce occasional false positives — for
   example, surnames ending in *-вич* were at one point mis-parsed as
   patronymics, creating a spurious person entry that was later detected
   and removed. All counts in this paper are therefore re-derived from the
   committed data files by an automated gate
   (`article/check_data_paper_numbers.py`) rather than quoted from earlier
   prose, machine-suggested identity links are quarantined behind the
   `candidate` confidence status until verified, and the person-alias
   override table (`curation/person_aliases.csv`) records manual
   corrections. Residual undetected merge or split errors in low-frequency
   names cannot be excluded.

## 7. Citation

When using this dataset, please cite both the data paper and the archived
snapshot:

> Gasūns, M. (2026). Russian Indological Research Archive: A Conference
> Corpus for Prosopography. *Research Data Journal for the Humanities and
> Social Sciences* (submission pending).
>
> Gasūns, M. (2026). *IndologyScholars: Russian Indological Research
> Archive — Zograf and Roerich Readings Conference Corpus (2004–2026)*
> [Data set]. Zenodo. https://doi.org/10.5281/zenodo.21360652
> (concept DOI; version \1.6.7\ = https://doi.org/10.5281/zenodo.21847873).

## 8. Acknowledgments

The author thanks the organizers of the Zograf and Roerich Readings for
decades of publicly distributed programs, and the open-source digital
humanities community for the tools that made this corpus possible.

## References

- Gasūns, M. (submitted). Двадцать лет российской индологии: Зографские и
  Рериховские чтения (2004–2026). *Письменные памятники Востока*.
- Wilkinson, M. D., et al. (2016). The FAIR Guiding Principles for
  scientific data management and stewardship. *Scientific Data*, 3, 160018.
- Schreibman, S., Siemens, R., & Unsworth, J. (Eds.). (2004). *A Companion
  to Digital Humanities*. Blackwell.

---

*Draft: 2026-06-03. Revised: 2026-07-11 (all derivable figures re-verified
against the committed data by `article/check_data_paper_numbers.py`);
2026-07-17 (snapshot re-frozen, cross-model κ re-derived from
`analytics_output/interrater_crossmodel_claude.csv`, dataset title
harmonized across §5.4/§7, `article/zenodo_metadata.json`, and
`CITATION.cff`, DOI slots split into concept/version; backfilled 2026-08-08 from live Zenodo record after GitHub integration confirmed).
Target journal: Research Data Journal for the Humanities and Social
Sciences (Brill). Word count target: 3,000–4,000.*
