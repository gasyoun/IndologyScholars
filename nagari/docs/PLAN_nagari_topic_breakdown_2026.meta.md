_Created: 22-07-2026 · Last updated: 22-07-2026_

# Metadoc — PLAN_nagari_topic_breakdown_2026

Companion record for
[PLAN_nagari_topic_breakdown_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/PLAN_nagari_topic_breakdown_2026.md).

- **Purpose.** Execution-ready spec for replacing the surface-level 8-tag topic layer of the
  nagari retrospective with a multi-layer topic/entity breakdown. Drives an unattended build.
- **Audience.** The wave-1 execution agent (H1518) and any future session tuning the taxonomy.
- **Provenance.** Authored via `/ask` (heavy up-front interview → layered plan). Interview: 3
  rounds — goal/scope, hard constraints (deps/privacy/LLM), plus a privacy re-confirmation
  round that walked back two ⚠-flagged picks (external DeepSeek export → local-only; public
  body quotes → human-gated). Model: Opus 4.8 (`claude-opus-4-8`). Executor for the build:
  Sonnet 5 (`claude-sonnet-5`).
- **Improvement backlog (ranked).**
  1. Fold `reports/topic_gaps.md` back into `taxonomy.py` after the first offline run — the
     taxonomy children are seeded, not final.
  2. Tune entity gazetteers from the review-sheet false-positive/negative feedback.
  3. Decide the phrase-vs-single-word display balance after seeing real `phrases.csv`.
  4. Wave 2: design the redacted quote-snippet format for the publish-safety review.
- **Limitations.** Taxonomy content, entity gazetteers, and the misc-<15 % target are
  hypotheses until the corpus is run; the offline embedding step depends on a one-time model
  download that may fail on some hosts (handled by the autonomy contract's stop/skip rules).
- **Related.** [[project-nagari-group-archive]] · [[project_indologyscholars]] ·
  sibling atlas [`Indology/indology_archive_research`](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/README.md).
- **Revision history.** 22-07-2026 — created with the PLAN (Opus 4.8, `claude-opus-4-8`).

_Dr. Mārcis Gasūns_
