# SIGNOFF A26 — author-voice pass

_Created: 06-09-2026 · Last updated: 06-09-2026_

## Scope

Manuscript: [article/data_paper_draft.md](https://github.com/gasyoun/IndologyScholars/blob/main/article/data_paper_draft.md) (A26, data paper, *Research Data Journal for the Humanities and Social Sciences*). Handoff: [H3857](https://github.com/gasyoun/Uprava/blob/main/handoffs/H3857-Fable_Uprava_all-articles-author-voice-pass-workflow_01.09.26.md). Pass by Fable 5.1 (`claude-fable-5-1`), 06-09-2026. Voice, register and framing only; no number, claim or citation altered; mechanical drift gate CLEAN (`voice_drift_check.py --git origin/main`: numbers 133/133, URLs 3/3, DOIs 4/4, IAST 9/9, headings 29/29, table rows 29/29). Data-paper register kept; `PENDING`/"submission pending" markers and the DOI slots left as they stand.

## 1. Voice calls made — each may be vetoed

| # | Location | Call | Rationale |
|---|----------|------|-----------|
| 1 | Abstract, first sentence | "We present the IndologyScholars corpus" → "I present the IndologyScholars corpus" | Single-author paper; RDJ accepts first-person singular. The editorial "we" was the only plural in the text. |
| 2 | §1, para 1, first sentence | "a uniquely structured source" → "a structured source of its own kind" | ~~Drops the intensifier adverb.~~ **Reverted after adversarial verify:** "of its own kind" weakened the uniqueness claim (substance); original "uniquely structured source for the sociology of scholarship" restored. |
| 3 | §1, para 1, last sentence | "offers a systematic window into disciplinary self-representation" → "offers systematic evidence of disciplinary self-representation" | ~~Decorative metaphor replaced by the literal noun.~~ **Reverted after adversarial verify:** "evidence" is a stronger epistemic claim than "window" (substance + meaning); original wording restored. |
| 4 | §1, para 3 | "This paper describes …" → "In this paper I describe …" | First person in the outline sentence kept. **Partly reverted after adversarial verify:** the added "My one contribution here is the infrastructure: what I built, how I built it …" narrowed the scope statement to a single contribution (meaning); original "The present work focuses on the infrastructure: what was built, how it was built …" restored. |
| 5 | §2.3, first sentence | "Speaker names were normalized … into deterministic person identifiers" → "I normalized speaker names … into deterministic person identifiers" | Agent is the author; passive hid it. Other passives in §2 were left because their agent is a script or a model, which the sentence names. |
| 6 | §6, item "Name-heuristic false positives" | "false positives — for example, surnames ending in *-вич*" → "false positives. For example, surnames ending in *-вич*" | Em-dash carrying a full example sentence; split. |
| 7 | §8 Acknowledgments | "The author thanks" → "I thank" | Third-person self-reference in a first-person paper. |
| 8 | Header | `Last updated` 05-09-2026 → 06-09-2026 | Mandatory bump. |
| 9 | Closing status paragraph | Appended "author-voice pass 06-09-2026 ([SIGNOFF_A26_author_pass.md](https://github.com/gasyoun/IndologyScholars/blob/main/article/SIGNOFF_A26_author_pass.md))" to the revision trail | Where the paper already lists its prior passes; nowhere else. |

Left deliberately unchanged: the byline block ("Independent researcher, Obninsk, Russia" + ORCID) — equivalent to the standard EN byline, no email added because that is an author decision; the four-item reuse list in the abstract and the six/four-item lists in §4 — enumerations of real outputs, not rhythm; "fully deterministic and reproducible" in §2.2 — a testable claim, not an intensifier; all §6 "X, not Y" sentences — they are the substantive corrections the limitations exist to make.

## 2. Substance flags carried (not fixed)

1. **§6 list numbering.** Two consecutive items are both numbered "7." ("Birth-year coverage" and "Name-heuristic false positives"). A renderer will auto-number them 7 and 8, but the source text and any plain-text or DOCX export will not. Not touched because it is a number token. A human should decide to renumber the second to "8." (and check that no cross-reference elsewhere cites "limitation 7").
2. **§7 citation block, stray backslashes.** The second citation reads "version \1.6.7\ = https://doi.org/10.5281/zenodo.21847873" — the backslashes look like a regex back-reference artefact from an earlier scripted replace (`\1`). Inside a citation, so left alone; should read "version 1.6.7" or "v1.6.7".
3. **§4.3 "human-labeled gold standard for L1/G1".** §6.4 states that L1 and argument-scale codes were assigned by a single coder with LLM assistance and that the human second-coder statistics are still to come. "Gold standard" may promise more than the reliability packet currently delivers; also "L1/G1" pairs a discipline axis with one argument level, where "L1/argument level" seems intended.
4. **§4.4 vs §3.4 on Wikidata coverage.** §4.4 opens "With Wikidata Q-ID coverage, the corpus becomes part of the linked open data cloud" in the present tense, while §3.4 reports 3 of 268 profiles (1.1%) mapped, 2 of them unverified candidates. A conditional ("Once Wikidata Q-ID coverage grows …") would match the numbers; hedging strength is substance, so flagged only.
5. **§6.4 "a single coder".** The coder is presumably the author; the paper never says so. Naming it is a one-word factual addition a human should make or refuse.
6. **§6.7 cites "Kaplan-Meier analyses" and "age-at-debut"** as affected analyses. Those analyses belong to the companion analytical article, not to this data paper; a reader of A26 alone has no referent. Cross-reference or trim — author's call.
7. **§3.4 coverage table is dated 2026-07-11** while the snapshot and DOI narrative in §5.4 are dated 2026-07-17 / 2026-08-08. `check_data_paper_numbers.py` presumably re-verifies these; the "as of" stamp may deserve a refresh before deposit.
8. **§1 "first machine-readable normalization … across all available years"** — a priority claim. Left exactly as written; worth a one-line prior-art check (e.g. no earlier orientalstudies.ru scrape) before a referee asks.
9. **No conclusion section.** The data-paper template (§6 Limitations → §7 Citation) has no place where the introduction's framing ("a systematic source for the sociology of scholarship") is closed. Acceptable for RDJ's format; noted because the voice contract asks that the opening question be answered somewhere, and here it is answered only implicitly by §4.
10. **Byline.** No email in the header block; the standard form carries `gasyoun@ya.ru`. Author decision.

## 3. Read-and-sign

About 30 minutes: read §1 and §8 in full (the only paragraphs whose register changed), skim §2.3 and the split sentence in §6, then rule on the ten flags above (flags 1 and 2 are mechanical and can be fixed in one minute; flags 3 and 4 are the ones a referee would raise).

Proposed readiness: 4/5 (propose only — deposit-ready once flags 1–4 are ruled on and the human second-coder κ promised in §6.4 is either reported or its sentence rephrased as a stated gap). Venue: no change recommended; *Research Data Journal for the Humanities and Social Sciences* (Brill) remains the right home for a data paper of this shape.

_Dr. Mārcis Gasūns_
