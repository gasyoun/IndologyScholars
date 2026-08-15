# H1898 — reviewed cross-lens identities and exact-quote evidence

_Created: 05-08-2026 · Last updated: 05-08-2026_

Executor: Fable 5 (`claude-fable-5`), 2026-08-05, worktree `IndologyScholars-h1898-1193884`
off `origin/codex/community-lenses-ask-plan`. Local-only per H1898 scope: nothing committed,
pushed, or published. Reviewer of record for every manual decision below:
Fable 5 (`claude-fable-5`).

## Inputs and coverage

| Corpus | Snapshot | Coverage | Records | Source-local identity mentions |
|---|---|---|---|---|
| conferences | conferences:2026-08-05 | complete | 1362 | 1388 (all pre-linked to `conferences:PERS_*`) |
| vk_ors | vk_ors:2026-07-24 | complete | 7608 | 7608 (single broadcast page account) |
| nagari | nagari:pilot:2026-08-05 | **pilot** | 18727 (2 duplicates dropped, see below) | 18725 |
| bvp | bvp:none | unavailable | — | slice STOPPED: input dataset destroyed with the former ask-worktree (FINDINGS §314); no paraphrase substitution |
| indology_l | indology_l:none | unavailable | — | slice STOPPED: blocked on H1894 (no atomic snapshot); adapter refuses by design |

Duplicate-record handling: the full `nagari.db` carries 2 duplicated Message-IDs, which
`community_lenses.build` (correctly) refuses with UNIQUE violations — the known
full-nagari.db crash class of IndologyScholars#169. `identity.build_reviewed_database()`
drops the LATER duplicate of each and reports it:
`nagari:<1b223956-5244-4ce3-ac1d-600959c95433@40g2000prx.googlegroups.com>`,
`nagari:<002b01c9627a$efc09e40$160513ac@acerd29f329b82>`. With the full db present, 2
pre-existing adapter tests fail on exactly this defect; the db copy is therefore not left
in the worktree, and the canonical db stays at `IndologyScholars/nagari/data/nagari.db`.

## A. Reviewed identity links

Candidate generation: 719 distinct (corpus, attested display name) pairs inventoried;
matching methods are string/authority evidence only (normalized token-set equality and
subset, small Cyrillic→Latin comparison table). **Auto-accept path (authority-exact): 0
rows fired.** 13 attested-identity candidates surfaced, all nagari→conferences; every one
was manually adjudicated — none auto-accepted.

| Decision | Count | Notes |
|---|---|---|
| accepted | 8 | 7 distinct persons (Титлин appears under Latin + Cyrillic spellings, same masked account) |
| ambiguous | 5 | candidate preserved, `person_id` NOT applied; each carries a written insufficiency rationale |
| rejected | 0 | — |
| auto-accepted | 0 | invariant: only `authority_exact` may ever auto-accept |

Applied links: **641 `record_name` mentions** linked across the 7 accepted persons
(426 Уланский, 188 Титлин, 18 Гасунс, 4 Толчельников, 3 Ерченков, 1 Хмуркин,
1 Корнеева Н.А. — the surname homonym Корнеева Т.Г. was explicitly ruled out by given
name). Source-local displays and masked account ids are preserved unchanged; decisions
live at the attested-identity grain (corpus + exact spelling + masked account) in
`curation/community_person_links.csv`; the annotated queue is
`analytics_output/community_lenses/review/person_match_candidates.csv` (0 open items).

Every row is marked `exportable=no`: the links derive from a CLOSED Google Group's
membership, so publishing a named cross-membership claim awaits the nagari rights gate.
**`curation/community_person_links.csv` and `curation/community_quotes.csv` must not be
committed to the public repo until that approval exists** — they are deliverables of a
local-only pass.

Author-supplied named Russian INDOLOGY-L cases and BVP cross-membership hypotheses:
**unverifiable this pass** — both corpora unavailable (above); recorded as evidence gaps,
not as census rows.

## B. Exact quotation register

3 quotes registered in `curation/community_quotes.csv` (+ mirrored into the shared-contract
`quote` table); each verified character-for-character against its pinned source text, with
before/after context SHA-256 hashes, thread subject, retrieval date, an observable-action
behaviour label, and an `article_claim_id`. 0 paraphrases; 0 quotes with unresolvable
context (none had to be omitted this pass; the omission path is test-covered).

| Quote | Corpus | Behaviour | Rights state | Aggregate evidence |
|---|---|---|---|---|
| Q-VK-22289 | vk_ors | announced | **exportable_approved** | 313 / 7608 posts self-tagged `#bookzealots` (unit: wall posts; complete; vk_ors:2026-07-24) |
| Q-NG-PANINI-ASK | nagari | asked | **exportable_approved** | 426 / 18727 messages from the accepted ulanskiy@… identity (unit: messages; **pilot** — no population claim) |
| Q-NG-PANINI-ANSWER | nagari | answered | **exportable_approved** | `aggregate_evidence_unavailable`: H1897 froze no answer-type scheme for nagari; no denominator exists |

Counts by source and export state: vk_ors 1 (exportable_approved) · nagari 2 (exportable_approved) ·
exportable_approved 3. The mechanical gate now returns **3** rows — all three carry a
complete approval record (approver / scope / 2026-08-07 / permitted use) from
[PR #183](https://github.com/gasyoun/IndologyScholars/pull/183); H2771 flipped
`rights_review_status` from the H2573 fail-closed park to `exportable_approved`.
Contact data: none present in any
registered quote (regex-checked); context review notes are in
`analytics_output/community_lenses/review/quote_context_review.csv`.

## Verification

- `tests/test_community_lenses_identity.py` — 16 passed
- `tests/test_community_lenses_quotes.py` — 19 passed
- full battery (identity + quotes + taxonomy + adapters): 93 passed, 2 pre-existing
  nagari-adapter failures ONLY while the full `nagari.db` copy sits in the worktree
  (duplicate Message-IDs, IndologyScholars#169); green after the copy is removed
- `python -m py_compile community_lenses/identity.py community_lenses/quotes.py` — OK
- `git diff --check` over all owned files — OK

## Limitations

- nagari snapshot is **pilot** coverage: no population-share claims; aggregates carry the
  pilot flag.
- bvp and indology_l slices stopped (inputs unavailable); their identity/quote layers are
  explicit gaps, not zeros.
- vk_ors contributes no personal identities (one broadcast page account by construction).
- Ambiguous identity rows await message-content review; they are excluded from every
  overlap count.
- All aggregate numerators/denominators are snapshot-bound; re-running against a newer
  db changes snapshot ids and must re-register.

_Dr. Mārcis Gasūns_
