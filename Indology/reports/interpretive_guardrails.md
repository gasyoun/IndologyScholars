# Interpretive Guardrails

These guardrails keep public claims close to the evidence produced by the metadata pipeline.

## direct_reply_network

- Allowed claim: A source message can be linked to a target message by header evidence or documented inference.
- Forbidden overclaim: A reply edge proves influence, agreement, mentorship, or scholarly dependence.
- Required evidence: `reply_edges.csv` confidence, source URL, target URL, and spot-checks for interpreted examples.
- Current artifact: `data/processed/reply_edges.csv; data/processed/named_reply_network_summary.csv`

## co_participation_network

- Allowed claim: Two normalized author labels appear in the same public thread.
- Forbidden overclaim: Co-participation proves collaboration, friendship, institutional school, or shared views.
- Required evidence: `network_edges.csv` or `named_coparticipation_network_summary.csv` plus thread context.
- Current artifact: `data/processed/network_edges.csv; data/processed/named_coparticipation_network_summary.csv`

## message_volume

- Allowed claim: The archive contains a counted number of messages or threads matching the parser output.
- Forbidden overclaim: High message count means importance, expertise, centrality, or field dominance.
- Required evidence: `messages_clean.csv`, `threads.csv`, and validation notes about archive coverage.
- Current artifact: `data/processed/messages_clean.csv; reports/validation.md`

## archive_representativeness

- Allowed claim: The atlas describes visible public INDOLOGY-L archive activity.
- Forbidden overclaim: The archive represents all Indology, all Sanskrit studies, or all scholarly communication in the field.
- Required evidence: Explicit source scope and caveats in report/dashboard/data dictionary.
- Current artifact: `data_dictionary.md; reports/research_report.md`

## author_normalization

- Allowed claim: Raw author strings are grouped conservatively for metadata analysis and marked with confidence/evidence.
- Forbidden overclaim: Normalized labels are authoritative identities or complete biographical records.
- Required evidence: `author_aliases.csv`, `authors_needing_review.csv`, and manual review for public claims.
- Current artifact: `data/processed/author_aliases.csv; data/processed/authors_needing_review.csv`

## case_study_candidates

- Allowed claim: A thread was selected automatically as a candidate because it matches recorded evidence fields.
- Forbidden overclaim: Generated candidates are curated examples or definitive major debates before human review.
- Required evidence: `case_study_candidates.csv`, `case_review_queue.csv`, and reviewed `curated_case_studies.csv` rows.
- Current artifact: `data/processed/case_study_candidates.csv; data/processed/curated_case_studies.csv`

## renou_subject_layer

- Allowed claim: A message or thread subject clearly matches a Renou state/register rule adapted from RENOU.md.
- Forbidden overclaim: A blank Renou field proves irrelevance, or a subject match is equivalent to dictionary headword/sense tagging.
- Required evidence: `renou_subject_rules.csv`, matched term, confidence, archive URL, and thread context for interpreted examples.
- Current artifact: `data/processed/renou_messages.csv; data/processed/renou_message_matches.csv; data/curation/renou_subject_rules.csv`
