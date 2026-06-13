# Russian Indological Research Archive: A Conference Corpus for Prosopography

**Marcis Gasuns**  
Independent researcher, Obninsk, Russia  
ORCID: 0000-0003-4513-884X  

## Abstract

We present the IndologyScholars corpus: a structured, open-access dataset
of 1,362 conference presentations, 270 scholar profiles, and 1,388 author
participations drawn from published programs of the Zograf Readings (St.
Petersburg) and Roerich Readings (Moscow) between 2004 and 2026. The dataset
includes normalized speaker identities, institutional affiliations with
explicit provenance tagging, thematic classification (L1/L2), a three-level
argument-scale coding (G1–G3), video-record mapping, and external authority
identifiers (Wikidata, ORCID, VIAF, OpenAlex). All data are published as
SQLite, CSV, JSON, and RDF/Turtle under open licenses with a Frictionless
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
records (22 program years). Programs were preserved as HTML in
`html_cache/`. Three supplementary data layers are manually curated:

- `authority_ids.json` — verified external person identifiers
- `curation/verified_affiliation_spans.csv` — dated institutional trajectories
- `curation/teacher_student.csv` — advisor/student relationships
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
with 10 tables: `person`, `presentation`, `presentation_person`, `session`,
`event_day_venue`, `event_day`, `event`, `event_series`, `venue`, and
`media`. The `presentation_person` table supports multi-author presentations
with role labeling (`speaker`, `coauthor`).

### 3.2 Public dataset

The master public dataset (`site_data.json`) is a single JavaScript payload
containing:

| Section | Contents |
|---------|----------|
| `scholars` | 270 profiles with talks, affiliations, themes, external IDs |
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

Public authority records in `authority_ids.json` include:

| Identifier | Coverage (as of 2026-06-03) |
|------------|------------------------------|
| Wikidata | 0.4% |
| ORCID | 0.4% |
| VIAF | 0% |
| OpenAlex | 0% |
| RINC/eLIBRARY | 0% |
| Google Scholar | tracked but not yet mapped |

Coverage is low because the mapping requires human verification. OpenAlex
API-based candidate matching has been run (122 scholars returned at least
one candidate), and human review is ongoing. Once Wikidata items are
created, VIAF harvesting follows automatically.

## 4. Reuse Potential

### 4.1 Prosopography

The dataset supports quantitative prosopography of an academic community:
participation trajectories, institutional mobility, generational cohorts,
and inter-venue permeability. All 270 scholars have standardized Latin
transliterations, birth years (85.6% coverage), and talk-level thematic
classification.

### 4.2 Network analysis

Five network edge types are exported:
- `person_event` — participation traces
- `person_organization` — affiliation links
- `person_theme` — thematic engagement
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
| CSV | `analytics_output/*.csv` | 40+ statistical and review exports |
| RDF/Turtle | `indology_knowledge_graph.ttl` | Linked data graph |
| Data Package | `datapackage.json` | Frictionless metadata manifest |
| CFF | `CITATION.cff` | Citation metadata |

### 5.3 Archived snapshot

A frozen version of the dataset used for publication is archived at:

**Gasūns, M. (2026).** *IndologyScholars: Archive of Talks in Russian
Indology* [Data set]. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX
(Replace XXXXXXX with actual Zenodo ID after upload.)

The snapshot includes `conferences.db`, `site_data.json`, all analytics
CSVs, curation files, and a SHA-256 manifest.

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
   A blind, stratified inter-rater sample (all G3 items, oversampled G2)
   has been prepared; agreement statistics (Cohen's κ with bootstrap CIs,
   Krippendorff's α, Gwet's AC1) will be reported before final deposition.

5. **Gender attribution.** Gender is inferred from Russian name morphology
   (patronymic, given name, surname declension), not self-identification.
   Names that do not permit reliable inference are reported as an explicit
   "unknown" category, and a manually verified validation sample with a
   published error rate accompanies the dataset
   (`tools/validate_gender_inference.py`). Correction and objection
   procedures for living persons are described in
   `docs/persons-data-policy.md`.

6. **Identifier coverage.** Wikidata, ORCID, VIAF, and OpenAlex mappings
   are minimal. This limits cross-dataset linking and international
   discoverability. A candidate-matching pipeline exists and results are
   under human review.

## 7. Citation

When using this dataset, please cite both the data paper and the archived
snapshot:

> Gasūns, M. (2026). Russian Indological Research Archive: A Conference
> Corpus for Prosopography. *[Journal name, pending submission]*.
>
> Gasūns, M. (2026). *IndologyScholars: Archive of Talks in Russian
> Indology* [Data set]. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX
> (Update after Zenodo upload.)

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

*Draft: 2026-06-03. Target journal: Journal of Open Humanities Data
(Ubiquity Press). Word count target: 3,000–4,000.*
