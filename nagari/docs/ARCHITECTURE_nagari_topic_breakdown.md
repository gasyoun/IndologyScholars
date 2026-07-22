_Created: 22-07-2026 · Last updated: 22-07-2026_

# ARCHITECTURE — nagari topic/entity breakdown

Component boundaries, data model, and the build-vs-reuse verdicts for the fuller topic
breakdown. Indexed by
[PLAN_nagari_topic_breakdown_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/PLAN_nagari_topic_breakdown_2026.md).

## The load-bearing split: stdlib live pipeline vs deps-bearing offline layer

The project's contract is **stdlib-only, reproducible on a clean machine**. That contract is
kept by drawing a hard line:

```
  offline_analysis/  (own requirements.txt — pymorphy2/natasha, sentence-transformers, hdbscan)
      build_lemma_dict.py  ─► data/lemma_map.json        (committed static artifact)
      discover_topics.py   ─► reports/topic_gaps.md      (human folds into taxonomy.py)
      build_phrases.py     ─► data/phrases.csv           (committed static artifact)
                                     │
                                     ▼  (plain data files, no imports)
  nagari_group_archive/  (stdlib-only — the live, reproducible pipeline)
      taxonomy.py          curated 2-level topic rules over lemmatized text
      entities.py          gazetteer matcher over lemmatized text
      gazetteers/*.tsv     curated entity name+alias lists
      insights.py          consumes lemma_map.json + phrases.csv + taxonomy + entities
      _template.py/page.py new page views
```

The offline layer runs **locally, once per data refresh**, and commits its outputs as static
data. The live pipeline (`scripts/run_pipeline.py`) imports **only** the standard library and
reads those static files — so `pip install`-free reproduction and byte-stable CSV output are
preserved. No body or subject ever leaves the machine.

## Data model

### Taxonomy (`taxonomy.py`)

Two levels, replacing the flat `TOPICS` dict. A structured mapping
`parent → {child → compiled regex}` over **lemmatized** subject+body:

- Parents (indicative, finalize from misc-audit + gap report): `Тексты и корпусы`,
  `Лексикография`, `Грамматика и язык`, `Инструменты и цифра`, `Организация группы`,
  `Переводы и издания`, `Астрология и джьотиша`, `История и культура`.
- ~30–40 children total. `classify(text) -> (primary, all_labels, parent)` — adopt the
  sibling's **primary-first** rule and `clean_subject`/`is_noisy_subject` preprocessing
  (strip `Re:/Fwd:/[list]`, drop digest/test noise) before matching. `разное` stays the
  fallback but is now expected to be small and is itself audited.

### Entities (`gazetteers/*.tsv` + `entities.py`)

One TSV per type; columns `canonical<TAB>type<TAB>aliases(|-sep, RU/IAST/Latin)<TAB>qid(optional)`:

| File | Type | Example row |
|---|---|---|
| `texts.tsv` | text/corpus | `Махабхарата⇥text⇥mahābhārata\|mahabharata\|MBh⇥Q184665` |
| `scholars.tsv` | person | `Bühler⇥person⇥бюлер\|georg bühler` |
| `dictionaries.tsv` | reference | `Monier-Williams⇥dict⇥mw\|монье-вильямс\|monier` |
| `tools_places.tsv` | tool/place | `Velthuis⇥tool⇥велтхаус\|velthuis` |

`entities.py`: `match(text) -> list[(canonical, type)]`, matching lemmatized/normalized text
with alias folding (IAST↔ASCII via `indic_transliteration.sanscript`, done **offline** when
building the alias column so the live matcher stays stdlib).

### Thread topic (`insights.py`)

`thread_topic(thread) = mode(primary tag of each message in the gm_thrid)`, tie-broken by
child-specificity then earliest message. Emits `thread_topics.csv`
(`gm_thrid, primary, parent, entities, n_messages, year`).

### Aggregates (all subject-/count-level → safe for the public page)

`topic_cooccurrence` (undirected, per thread), `topic_authors` (topic→top authors),
`topic_representative_subjects` (topic→top-N thread subjects by size), `topic_entity_matrix`,
`entities_by_type` + `entity_trends`, `phrases` (from `phrases.csv`), `misc_audit`.

## Page (`_template.py`) surface

- `#temy` upgraded: parent-total bars with child drill-down + topics-by-year retained;
  topic co-occurrence graph; topic×entity heatmap.
- New `#sushchnosti`: top texts / scholars / dictionaries / tools, each with a trend line.
- Phrase layer replaces the raw single-word "top terms".
- **Quote block**: rendered only when a build flag `SHOW_QUOTES` is true (default **false**).
  Wave-1 ships it wired but disabled; enabling is a Wave-2 human-gated action.

## Build-vs-reuse verdicts (prior-art checked)

| Piece | Verdict | Source |
|---|---|---|
| Subject cleaning + primary-first classify | **Reuse pattern** | [`Indology/.../topics.py`](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/indology_archive_research/topics.py) `clean_subject`/`is_noisy_subject`/`classify_subject` |
| RU lemmatization | **Reuse lib** | pymorphy2 / natasha (offline) — do not write a morphology engine |
| Latent-topic clustering | **Reuse lib** | sentence-transformers multilingual + HDBSCAN (offline, local) |
| IAST↔ASCII alias folding | **Reuse lib** | `indic_transliteration.sanscript` (offline, alias-build time) |
| Dictionary/text name lists | **Reuse data** | [SHARED_CODE.md](https://github.com/gasyoun/github-spine/blob/main/SHARED_CODE.md), SanskritLexicography `FEATURES_INDEX.md`, IndologyScholars `assets/data/geography.json` (theme Q-IDs) |
| PMI / log-likelihood collocations | **Build (stdlib)** | standard formula, pure counting — implement, cite it |
| Curated taxonomy content, RU alias layer | **Build** | new domain work — the actual deliverable |

## Interpretive guardrails (carried from the atlas, unchanged)

Reply edge ≠ influence; co-participation ≠ collaboration; message count ≠ scholarship;
archive visibility ≠ field representativeness; distinct handles of one person are **not**
merged here.

_Dr. Mārcis Gasūns_
