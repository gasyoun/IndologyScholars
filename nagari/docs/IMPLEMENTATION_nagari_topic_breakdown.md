_Created: 22-07-2026 · Last updated: 22-07-2026_

# IMPLEMENTATION — nagari topic/entity breakdown (Wave 1)

File-level, dependency-ordered build sequence for the unattended agent. Indexed by
[PLAN_nagari_topic_breakdown_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/PLAN_nagari_topic_breakdown_2026.md);
architecture in
[ARCHITECTURE_nagari_topic_breakdown.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/ARCHITECTURE_nagari_topic_breakdown.md).

All paths are under `nagari/`. Work in a session-unique worktree off `origin/main`
(IndologyScholars main-tree is a hard-block repo). Commit after each step with `ai-wip:`.
Edit generators, never derived artifacts; rebuild with `python scripts/run_pipeline.py --skip-ingest`.

## Step 0 — Baseline & misc-audit  *(depends on: nothing; needs `data/nagari.db`)*

- Add `misc_audit()` to [insights.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/insights.py):
  report current `разное` share (message- and thread-level) and the top-300 unmatched
  subject+body lemmas.
- Write `data/processed/misc_audit.csv` and print the misc %.
- **This number is the before/after evidence.** Record it in `.ai_state.md` Dev Notes.

## Step 1 — Offline lemma dictionary  *(depends on: 0)*

- New `offline_analysis/` with its own `requirements.txt` (pymorphy2 **or** natasha).
- `build_lemma_dict.py`: over all distinct tokens in subjects+bodies, emit
  `data/lemma_map.json` = `{form: lemma}` for RU tokens (≥3 chars). Deterministic; commit it.
- `offline_analysis/README.md`: "run locally once per data refresh; the live pipeline only
  reads `lemma_map.json` and never imports these deps."
- Add a stdlib `lemmatize(text, lemma_map)` helper in `nagari_group_archive/_lemma.py`
  (dict lookup + fallback to the token). Used by taxonomy, entities, phrases, misc-audit.

## Step 2 — Offline topic-discovery (gap report)  *(depends on: 1; local only, no export)*

- `offline_analysis/discover_topics.py`: multilingual sentence-transformer embeddings +
  HDBSCAN over bodies (seeded); c-TF-IDF keywords per cluster → `reports/topic_gaps.md`
  listing clusters **not** covered by the current 8 tags (focus: what falls in `разное`).
- **No network beyond the one-time model download; no body leaves the machine.** If the model
  cannot be fetched, skip this step, log it, and seed the taxonomy from Step 0's misc-audit
  terms alone (do not stall — autonomy contract).

## Step 3 — Curated 2-level taxonomy  *(depends on: 0, 2)*

- New `nagari_group_archive/taxonomy.py`: `PARENTS: dict[str, dict[str, re.Pattern]]`,
  ~30–40 children in ≥5 parents. Port `clean_subject`/`is_noisy_subject` from the sibling
  [`topics.py`](https://github.com/gasyoun/IndologyScholars/blob/main/Indology/indology_archive_research/topics.py).
  `classify(text, lemma_map) -> (primary, all_labels, parent)`; patterns match lemmatized text.
- Seed children from misc-audit terms + `topic_gaps.md`. Keep the original 8 tags as children
  under the right parents so nothing regresses.

## Step 4 — Entity gazetteers + matcher  *(depends on: 1)*

- `nagari_group_archive/gazetteers/`: `texts.tsv`, `scholars.tsv`, `dictionaries.tsv`,
  `tools_places.tsv` (schema in ARCHITECTURE). Seed dictionaries from the org lists
  (SanskritLexicography `FEATURES_INDEX.md`), texts/scholars from `geography.json` themes +
  corpus frequency, alias columns folded IAST↔ASCII offline via `indic_transliteration`.
- `nagari_group_archive/entities.py`: `match(text, lemma_map) -> list[(canonical, type)]`.

## Step 5 — Phrase tables  *(depends on: 1)*

- `offline_analysis/build_phrases.py` (may stay stdlib): PMI + log-likelihood bigram
  collocations and TF-IDF over lemmatized subjects+bodies → `data/phrases.csv`
  (`phrase, score, method, n`). Commit it. Cite the PMI/LLR formula in a docstring.

## Step 6 — Wire the new insights layers  *(depends on: 3, 4, 5)*

In [insights.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/insights.py):
- Replace the `TOPICS`/`topic_tables` path with `taxonomy.classify` (parent+child, primary
  + multi-label). Emit `topics_by_year.csv` (now parent+child), `thread_topics.csv`.
- New tables: `topic_cooccurrence.csv`, `topic_authors.csv`,
  `topic_representative_subjects.csv`, `topic_entity_matrix.csv`, `entities_by_type.csv`,
  `entity_trends.csv`, `phrases.csv` (passthrough), refreshed `misc_audit.csv`.
- Extend `site_data.json` with the new aggregates (subjects/counts only — **no bodies**).

## Step 7 — Page views  *(depends on: 6)*

In [_template.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/_template.py)
+ [page.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/nagari_group_archive/page.py):
- Upgrade `#temy`: parent bars → child drill-down; keep topics-by-year; add co-occurrence
  graph + topic×entity heatmap (reuse the existing self-contained SVG/JS helpers — no CDN).
- New `#sushchnosti` section: top entities per type + trend lines.
- Swap the raw single-word "top terms" for the phrase layer.
- Add the **disabled** quote block behind `SHOW_QUOTES=False` (Wave-2 gate). Do not enable.
- Keep light/dark + the validated data-viz palette.

## Step 8 — Citable dataset  *(depends on: 6)*

- Ensure `topics_by_year.csv`, `thread_topics.csv`, `entities_by_type.csv`, `phrases.csv`
  are clean release tables. Add `data/datapackage.json` (frictionless schema) + `CITATION.cff`.
  Follow [/data-release](https://github.com/gasyoun/claude-config/blob/main/commands/data-release.md)
  structure; **do not** submit to Zenodo (human `@DO`).

## Step 9 — Verify & land  *(depends on: all)*

- Run the full [VERIFICATION](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/VERIFICATION_nagari_topic_breakdown.md)
  gate. Rebuild the page, re-run `scripts/audit_publish_surface.py` + `redact.py` → zero
  third-party addresses. `python -m pytest` + `python validate_publication.py` green.
- Commit, push, open PR, enable auto-merge + delete branch. Update
  [.ai_state.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/.ai_state.md)
  Next Steps to point at the Wave-2 human gates. Remove the worktree.

## Ordering summary

`0 → 1 → {2, 4, 5} → 3 → 6 → {7, 8} → 9`. Steps 2/4/5 are independent once the lemma dict
(1) exists; 3 needs the gap report (2); 6 needs 3/4/5; 7/8 need 6.

_Dr. Mārcis Gasūns_
