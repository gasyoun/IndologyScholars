# Scientometrics And Sociology Of Science Layer

[Documentation index](README.md) | [Data dictionary](../data_dictionary.md) | [Human review index](../analytics_output/human_review_index.csv)

This note defines how scientometric and sociology-of-science claims should be
added to the archive without turning conference metadata into unsupported
career rankings.

## Responsible Metrics Stance

The archive follows a conservative responsible-metrics stance:

- conference visibility is not a proxy for scholarly quality;
- raw counts are descriptive signals, not evaluations of individuals;
- citation, publication, and authority-ID signals must be field-aware and
  language-aware before they support claims;
- missingness is an empirical object, not noise to hide;
- all high-impact identity, affiliation, classification, and authority matches
  require a human review trail.

This follows the spirit of the Leiden Manifesto for research metrics,
the San Francisco Declaration on Research Assessment (DORA), and current
science-of-science practice: indicators should support expert interpretation
rather than replace it.

## Human Review Index

`analytics_output/human_review_index.csv` is the single curator-facing inbox.
It aggregates open items from authority, RINC, OpenAlex, Wikipedia, identity
disambiguation, birth-year gaps, theme/classification reliability, spacetime
indexing, affiliation scope, lineage candidates, and data-quality samples.

Minimum review fields:

| Field | Meaning |
| --- | --- |
| `domain` | Review area, such as `authority_identity` or `theme_classification`. |
| `priority` | Lower number means earlier human review. |
| `source_file` | Original queue or audit file. |
| `record_id` | Local person, presentation, or external-candidate identifier. |
| `label` | Human-readable name or title. |
| `status` | Current review state. |
| `reason` | Why this row is in the queue. |
| `evidence_url` | First source URL or search result to inspect. |
| `reviewer`, `checked_at`, `note` | Fields for manual review workflow. |

The index is intentionally an open-work register. A large row count is not a
failure; it makes the remaining human labor auditable.

## Recommended Additions

### 1. Author Disambiguation Dossier

For each high-activity scholar, keep a local evidence bundle:

- local name variants and initials-only forms;
- RINC/eLIBRARY candidate or rejection;
- ORCID, OpenAlex, Wikidata/VIAF, Wikipedia when source-backed;
- affiliation and topic evidence used in author disambiguation;
- reviewer, date, and rejection reason for false positives.

Use this dossier before any individual-level productivity or collaboration
claim.

### 2. Field-Normalized Publication Signals

If publication/citation data are added from OpenAlex, RINC, or another index,
store raw counts separately from normalized indicators. Recommended fields:

- works count by document type and source index;
- citations by publication year and field;
- field-normalized citation percentile when available;
- Russian-language and humanities coverage caveat;
- matched-author confidence and false-positive risk.

Do not compare scholars across fields or generations using raw works or raw
citations.

### 3. Network Sociology

The archive can support sociology-of-science questions with network measures:

- co-presence at the same conference year;
- repeated co-participation across years;
- bipartite person-event and person-theme networks;
- bridge roles between Zograf and Roerich series;
- modularity communities and k-core layers;
- lineage or advisor/student edges when manually sourced.

Report these as positions in the observed conference archive, not as complete
maps of Russian Indology.

### 4. Cohort And Career-Stage Dynamics

Useful additions:

- first observed presentation year;
- last observed presentation year;
- return after absence;
- cohort survival curves;
- academic-age proxy based on first publication year, when manually verified;
- entry and exit by theme, city label, and series.

Always distinguish observed archive participation from employment or career
continuity.

### 5. Topic And Field Evolution

Recommended topic layers:

- title keyword bursts by decade;
- co-word networks;
- meso-level transitions over time;
- theme drift by cohort;
- uncertainty/confusion matrix from the classification reliability sample.

Topic outputs should remain navigation and hypothesis support until a larger
manual adjudication sample exists.

### 6. Missingness And Coverage

Publish missingness as a first-class appendix:

- missing birth years;
- city-only vs institution-labelled affiliation strings;
- absent or unverified authority IDs;
- talks without video;
- titles that cannot support period/place inference;
- source pages with weak or changed programme formatting.

This is essential for fair interpretation of field structure.

## Claims To Avoid

- "Scholar X is more important because they have more presentations."
- "Institution Y dominates the field" when the input is city labels or partial
  programme affiliation strings.
- "OpenAlex/RINC absence means low scientific productivity."
- "A theme code is a full content analysis of the paper."
- "A conference network is the whole discipline."

## Source Anchors

- Leiden Manifesto for Research Metrics: https://leidenmanifesto.org/
- DORA: https://sfdora.org/read/
- Fortunato et al., "Science of science": https://doi.org/10.1126/science.aao0185
- OpenAlex author disambiguation documentation: https://help.openalex.org/hc/en-us/articles/24347048891543-Author-disambiguation
