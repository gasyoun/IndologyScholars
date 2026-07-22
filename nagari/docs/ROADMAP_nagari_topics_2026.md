_Created: 22-07-2026 · Last updated: 22-07-2026_

# ROADMAP — nagari fuller topic/entity breakdown (2026)

Replaces the surface-level 8-tag topic layer of the «Общество ревнителей санскрита»
retrospective ([live page](https://gasyoun.github.io/IndologyScholars/nagari/)) with a
multi-layer breakdown. Part of the layered plan indexed by
[PLAN_nagari_topic_breakdown_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/PLAN_nagari_topic_breakdown_2026.md).

## Why

The current `#temy` section is one linear "topics-by-year" chart built from **8 hardcoded
keyword tags** in [insights.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/insights.py)
(`словарь, учебник, книга, pdf, сайт, шрифт, астрология, текст`), with everything unmatched
falling into a single `разное` catch-all of unknown size, plus a raw single-word subject
frequency list. It is a priori, semantically blind, message-level only, and has no entity
layer — the most valuable dimension for an indology group ("*which* texts, scholars,
dictionaries, tools were discussed").

## Waves

### Wave 1 — the unattended build (this roadmap's core)

Buildable end-to-end by one autonomous agent from the layered plan, with zero human contact.
Delivers everything except the two human-gated items in Wave 2.

1. **Misc-audit baseline** — measure the current `разное` share and the top unmatched
   subject/body terms; this both proves the "fuller" claim and seeds taxonomy expansion.
2. **Offline lemma dictionary** — `build_lemma_dict.py` (pymorphy2/natasha) emits a static
   `data/lemma_map.json` (form→lemma) that the stdlib live pipeline reads. Deps stay offline.
3. **Curated 2-level taxonomy** — ~30–40 topics in ≥5 parents (Тексты / Лексикография /
   Грамматика / Инструменты / Организация группы / …), seeded by the misc-audit and the
   offline topic-discovery gap report.
4. **Entity gazetteers + matcher** — four types (texts & corpora; scholars & authors;
   dictionaries & reference works; tools, fonts, software & places/institutions), reusing
   org name-lists, with an RU/IAST/Latin alias layer.
5. **Key-phrase layer** — PMI / log-likelihood collocations + TF-IDF over subjects **and**
   bodies (computed offline/locally; only aggregate phrases+weights reach the page).
6. **New insights layers** — thread-level topic assignment, topic co-occurrence, topic→top
   authors, topic→representative subjects, topic×entity matrix, entity trends, phrases,
   misc-audit table.
7. **Page views** — upgraded 2-level `#temy`, a new `#sushchnosti` (entities) section,
   phrase cloud, topic co-occurrence graph, topic×entity heatmap.
8. **Citable dataset** — `topics.csv`, `thread_topics.csv`, `entities.csv`, `phrases.csv` +
   `datapackage.json` + `CITATION.cff`, for the data-paper track already queued in
   [.ai_state.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/.ai_state.md).
9. **Verification** — `pytest` + `validate_publication.py` green; misc bucket < 15 %;
   `/review-sheet` spot-check ≥ 85 % agreement; zero new third-party addresses.

**Offline topic-discovery** (local sentence-transformers + HDBSCAN over bodies, no export)
is a Wave-1 *input*, run once to produce a gap report the agent folds into the curated
taxonomy — it is **not** a live pipeline dependency.

### Wave 2 — human-gated (NOT part of the unattended run)

- **Representative body-quote surface** — off-by-default feature: a short redacted snippet
  per topic/entity. Built (disabled) in Wave 1; **enabled only** after
  [/publish-safety-check](https://github.com/gasyoun/claude-config/blob/main/commands/publish-safety-check.md)
  GO + owner's manual sign-off, because it exposes 604 third parties' words from a closed list.
- **Deploy** of the enriched page to Pages / samskrtam.ru — human publish gate, per the
  standing `MG @DECIDE` in [.ai_state.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/.ai_state.md).

## Non-goals

- No external LLM/API over bodies or subjects (local models only).
- No attachment-blob extraction (blocked on the open rights `@DECIDE`).
- No author-identity merging (separate task; the guardrail stands).
- No hand-editing of derived artifacts — edit generators + rebuild.
- No change to the ingest/redaction privacy layer.

_Dr. Mārcis Gasūns_
