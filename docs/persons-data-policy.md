# Personal Data Policy

[Русская версия](persons-data-policy-ru.md) | [Reuse rights](reuse-rights.md) | [Development notes](development-en.md)

This archive describes living and recently deceased scholars. This page
states what personal information the archive publishes, on what basis, and
how a person named in it can have records corrected or removed.

## What the archive publishes

| Category | Source | Nature |
| --- | --- | --- |
| Name, talk titles, year, venue | Published conference programmes | Reproduced source facts |
| Affiliation and city | Programmes + dated, source-backed trajectories in `curation/` | Curated facts; open continuations are explicitly tentative (`(?)`) |
| Thematic and argument-scale codes | Editorial classification of talk **titles** | Editorial interpretation of a text, not of a person |
| Gender | Inferred from Russian name morphology | Probabilistic attribution, **not** self-identification; undecidable names are reported as "unknown" |
| Birth year, external identifiers (ORCID, Wikidata, OpenAlex) | Public registries and bibliographic databases | Linked only after human review; unconfirmed matches stay internal |
| Advisor/student and other documented ties | `curation/` files with per-row evidence requirements | A tie marked `verified` requires a supporting `evidence_url` |

## Basis and principles

1. **Public-record basis.** The archive is a scholarly prosopography built
   from published conference programmes and other public scholarly records,
   processed for research and historiographic documentation purposes.
2. **No sensitive categories.** The archive does not collect or publish
   health, political, religious-belief, or other special-category data about
   the persons it describes. (Talks *about* religion are subject
   classifications of texts, not statements about a speaker's beliefs.)
3. **Derived inferences are flagged.** Anything the pipeline infers rather
   than reproduces (gender, tentative affiliation continuations, candidate
   identifier matches) is marked as such in the data model and documented in
   `data_dictionary.md`. Inferences about persons are never silently
   promoted to facts.
4. **Interpretive claims are editorial.** Pages discussing patterns
   (gender balance, mobility, gatekeeping, genealogy) interpret the corpus
   as a whole under the editorial policy in
   `sociology-gatekeeping-editorial-decisions.md`; claim strength is
   deliberately bounded there.

## Correction and objection

If you are named in the archive and a record about you is wrong, outdated,
or you object to a derived inference (for example the gender attribution or
a tentative affiliation):

1. Open an issue at
   <https://github.com/gasyoun/IndologyScholars/issues>, or
2. Write to the maintainer (contact on the profile pages and in
   `CITATION.cff`).

State the page or record concerned and, for corrections, the preferred
value with a verifiable source if available. Corrections are applied to the
curated source files (never silently to generated pages), take effect at
the next rebuild, and are recorded in the changelog. Requests to remove a
derived inference are honoured; requests to remove reproduced public-record
facts (a published programme listing) are assessed individually, weighing
the scholarly documentation purpose against the objection, and the outcome
is documented.

Frozen snapshots already deposited for citation (DOI) are immutable by
design; corrections are carried by subsequent versions, with the erratum
noted in the version history.
