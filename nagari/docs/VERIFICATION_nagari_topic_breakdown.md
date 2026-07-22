_Created: 22-07-2026 · Last updated: 22-07-2026_

# VERIFICATION — nagari topic/entity breakdown

Acceptance criteria, the exact command that proves each, and the risk register. Indexed by
[PLAN_nagari_topic_breakdown_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/PLAN_nagari_topic_breakdown_2026.md).

## Acceptance criteria per deliverable

| # | Deliverable | Acceptance bar | Proof |
|---|---|---|---|
| 1 | Misc-audit | current & post-expansion `разное` share recorded | `data/processed/misc_audit.csv`; before/after in `.ai_state.md` |
| 2 | Lemma dict | `lemma_map.json` covers ≥ 90 % of RU tokens ≥ 4 chars | count in `build_lemma_dict.py` log |
| 3 | Taxonomy | ≥ 30 topics in ≥ 5 parents, 2 levels; **misc bucket < 15 %** of messages | `topics_by_year.csv` distinct tags; misc % |
| 4 | Entities | ≥ 4 types populated; each entity trend non-empty; a 30-row manual spot-check ≥ 85 % correct | `entities_by_type.csv` + `/review-sheet` |
| 5 | Phrases | phrase list is multi-word & lemmatized (no bare `re/fwd`, no single tokens) | `phrases.csv` head |
| 6 | Thread topics | every non-empty thread has a primary topic; distribution sums to 100 % | `thread_topics.csv` |
| 7 | Page | all new sections render; charts non-blank; light/dark OK; no CDN | DOM introspection (screenshots time out on this SVG-heavy page — known) |
| 8 | Dataset | `datapackage.json` validates; `CITATION.cff` parses | frictionless validate; cffconvert |
| 9 | Privacy | **zero** third-party addresses in page/CSV/dataset output | `scripts/audit_publish_surface.py` + `redact.py` |
| 10 | Repo gate | tests + publication validator green | `python -m pytest` && `python validate_publication.py` |
| 11 | Reproducibility | live pipeline stdlib-only; CSV byte-stable across two runs | `pip`-free run; `diff` two `--skip-ingest` runs |

## The "fuller than surface" gate (the point of the task)

All must hold, else the breakdown is not meaningfully fuller:

- Misc bucket **< 15 %** (measure the baseline first — currently unknown).
- Topic count **≥ 30** (was 8), in a real 2-level hierarchy.
- An **entity layer exists** with ≥ 4 populated types (was none).
- "Top terms" are **phrases**, not raw single words.
- At least the topic co-occurrence + topic×entity views are on the page (relationships, not
  just per-year counts).

## Human spot-check (the one un-automatable check)

Generate a `/review-sheet` over a random sample of **100 thread classifications**
(subject + assigned primary topic + matched entities — **no bodies**). Owner votes
approve/reject; **≥ 85 % approve** to pass. Deferred rows feed a taxonomy-tuning follow-up.

## Risks & spikes

| Risk | Mitigation |
|---|---|
| Offline embedding model unfetchable on the build host | Step 2 is skippable; seed taxonomy from misc-audit terms; log and continue (do not stall). |
| pymorphy2/natasha Python-version friction on Windows | Try natasha first (pure-Py wheels); if both fail, ship a smaller hand-built stem map + log the coverage gap. |
| Misc bucket stays > 40 % after expansion | Stop condition — the taxonomy needs a rethink; halt and report rather than shipping a still-hollow breakdown. |
| Multi-label inflates topic totals vs message count | Report **primary-topic** distribution for the misc %/hierarchy bars; keep multi-label only for co-occurrence. |
| Entity false positives (e.g. «гита» inside a name) | Word-boundary + lemma match; manual spot-check gate (criterion 4) catches drift. |
| A new aggregate accidentally embeds a body snippet | Criterion 9 (surface audit) is the backstop; `site_data.json` carries counts/subjects only. |
| Screenshots time out (SVG-heavy page) | Verify via JS DOM introspection, per the existing `.ai_state.md` note — not a page bug. |

## Out of scope for this gate (Wave 2, human-gated)

Quote-surface correctness and any deploy/publish are **not** verified here — they are gated on
`/publish-safety-check` + the owner's manual GO and never run unattended.

_Dr. Mārcis Gasūns_
