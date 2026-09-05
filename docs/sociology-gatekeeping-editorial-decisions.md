_Created: 15-08-2026 · Last updated: 05-09-2026_

# Sociology and Gatekeeping Pages: Editorial Decisions

Updated: 2026-06-01

This document records the editorial and evidentiary decisions for `sociology.html`
and `gatekeeping.html`.

Russian version: `docs/sociology-gatekeeping-editorial-decisions-ru.md`.

## Audience

Primary audience: editors and peer reviewers.

Secondary audience: colleagues in Indology and adjacent humanities fields.

The pages should be readable for non-specialists, but claims must remain
traceable to corpus data, external sources, or explicitly labelled hypotheses.

## Claim Level

`gatekeeping.html` treats "institutional filtering" as a hypothesis, not as a
proven accusation.

Preferred wording:

- "This pattern is compatible with an institutional-filter hypothesis."
- "The archive cannot by itself prove motive."
- "Alternative explanations must be tested before a stronger claim is made."

Avoid:

- presenting motive as established fact;
- calling absence from one programme a career exit;
- treating conference co-presence as durable collaboration.

## Naming Policy

People may be named when the page uses public programme records or public
external sources.

For charged interpretations, the page should also offer grouped or structural
language: "network mediators", "senior-generation frequent participants",
"programme-level absence", "external activity after archive absence".

Names support auditability; structural labels reduce unnecessary personalization.
Both are needed.

## Two Mechanisms, Not One

The pages distinguish two absence mechanisms:

1. Post-2022 absence from the archive.

   This group is treated as potentially connected to the political and
   cross-border context around Russia after 2022. It should not be folded into
   the 2026 programme-filter claim.

2. Absence from the 2026 programme.

   This group is treated as a separate programme-level question, where local
   academic relationships, personal relations, and selection practices may be
   more relevant than geopolitical explanation.

The distinction is important for reviewers: mixing these mechanisms would make
the argument weaker.

## External Verification

External sources may be used for biographical and activity checks:

- official institutional profiles;
- eLIBRARY/RINC;
- OpenAlex;
- ORCID;
- Google Scholar profiles when identity is clear;
- university, academy, project, publisher, and personal sites.

External sources are not treated as primary evidence for the conference archive.
They are used to test alternative explanations: death, retirement, career exit,
activity outside the archive, or cross-border relocation.

The curated biographical source ledger is:

- `curation/senior_biographical_verification.csv`

Rows marked `needs_stronger_biographical_source` should not support public
living/death claims until reviewed manually.

## Persuasion vs. Formal Defensibility

The pages prioritize intelligibility for a non-specialist reader, because a
fully formal proof is not available for a contested programme-selection case.

This does not license overclaiming. The page design should make the hypothesis
visible, but every figure should carry a plain-language caveat about what the
data can and cannot show.

## Page Roles

`sociology.html`:

- broad field observatory;
- institutional ecology;
- generations and participation trajectories;
- review queues and known uncertainty;
- distinction between public programme data and full scholarly life.

`gatekeeping.html`:

- focused hypothesis case;
- network-mediated exclusion;
- typed network evidence;
- alternative explanations;
- external activity checks;
- careful wording around institutional filtering.

`known-relationships.html`:

- separate curated layer for relationships not inferable from coauthorship or shared sessions;
- reviewable source queue for advisor, spouse, teacher, student, and employment ties;
- interpretive support only after the row has a source and review status.

`curation/eastern_faculty_alumni.csv`:

- reproducible curated filter for Faculty of Asian and African Studies / Oriental Faculty alumni;
- generated candidates may be refreshed with `tools/extract_eastern_faculty_alumni.py`;
- affiliation at the faculty is a candidate signal, not proof of graduation.

## English Version

Both pages need English versions so reviewers can evaluate the method and claim
discipline without relying on Russian page text alone.

Planned public paths:

- `sociology-en.html`
- `gatekeeping-en.html`

## Visualization Policy

Visualizations should make the argument easier to inspect, not more opaque.

Required visual patterns:

- clear "what this shows" captions;
- explicit labels for observation, metric, hypothesis, and human review;
- no unlabeled centrality scores without interpretation;
- no single undifferentiated "network" when edge semantics differ.

Preferred Russian terms:

- "сетевой посредник";
- "участник-связка";
- "связующий участник";
- "сетевые сообщества".

Avoid using "брокер" as the main public-facing term.

_Dr. Mārcis Gasūns_
