_Created: 18-08-2026 · Last updated: 18-08-2026_

# offline_analysis — run locally once per data refresh

These scripts have their own [`requirements.txt`](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/offline_analysis/requirements.txt)
(natasha, sentence-transformers, hdbscan, indic_transliteration) and are **not**
imported by the live pipeline (`nagari_group_archive/`, `scripts/run_pipeline.py`).
The live pipeline only reads the static data files these scripts commit —
`data/lemma_map.json`, `reports/topic_gaps.md`, `data/phrases.csv` — so a clean
`pip install`-free checkout still reproduces the page byte-for-byte.

Run after any `nagari.db` refresh (new mbox ingest):

```bash
pip install -r offline_analysis/requirements.txt
python offline_analysis/build_lemma_dict.py --db data/nagari.db
python offline_analysis/discover_topics.py --db data/nagari.db   # optional; skips cleanly if the embedding model can't be fetched
python offline_analysis/build_phrases.py --db data/nagari.db
```

No message body or subject ever leaves the machine — the sentence-transformer
model download is the only network call, and it fetches model weights, not
data.

_Dr. Mārcis Gasūns_
