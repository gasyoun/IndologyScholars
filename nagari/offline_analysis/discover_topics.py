"""Offline latent-topic gap report for the nagari taxonomy (H1518 Step 2).

Embeds message bodies with a multilingual sentence-transformer, clusters with
HDBSCAN, and reports clusters whose messages are NOT already covered by the
current curated taxonomy (``nagari_group_archive.taxonomy``) -- i.e. what is
falling into "разное". Runs locally; embeddings and cluster keywords never
leave the machine, and no body text is written to the output report (only
c-TF-IDF keywords + counts).

Per the plan's autonomy contract: if the embedding model cannot be fetched,
skip cleanly (log it) rather than stall -- the taxonomy is then seeded from
the misc-audit term list alone.

Usage (from ``nagari/``):
    python offline_analysis/discover_topics.py --db data/nagari.db
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "nagari.db"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "reports" / "topic_gaps.md"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
RANDOM_SEED = 42
MAX_DOCS = 6000  # cap for tractable local clustering on the full corpus


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def load_docs(db_path: Path, limit: int) -> list[tuple[int, str, str]]:
    """Return (message_id, subject, body_snippet) for messages classified as misc."""
    from nagari_group_archive.taxonomy import classify
    from nagari_group_archive._lemma import strip_footer_and_quotes

    db = sqlite3.connect(db_path)
    rows = db.execute("SELECT id, subject_clean, body_text FROM messages").fetchall()
    db.close()
    docs: list[tuple[int, str, str]] = []
    for _id, subj, body in rows:
        clean_body = strip_footer_and_quotes(body)
        text = f"{subj or ''}\n{clean_body[:2000]}"
        cl = classify(text)
        if cl.primary != "разное":
            continue
        snippet = clean_body[:600]
        docs.append((_id, subj or "", snippet))
        if len(docs) >= limit:
            break
    return docs


def embed_and_cluster(docs: list[tuple[int, str, str]]) -> tuple[list[int], object]:
    from sentence_transformers import SentenceTransformer
    import hdbscan

    model = SentenceTransformer(MODEL_NAME)
    texts = [f"{subj}\n{body}" for _, subj, body in docs]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5)
    labels = clusterer.fit_predict(embeddings)
    return list(labels), clusterer


RU_TOKEN = re.compile(r"[а-яёА-ЯЁ]{4,}")
STOP = set("""это как для что при чтобы если так там весь была было были быть будет
может можно надо нужно есть очень уже или его ему них они она оно этот эта эти тот все
всех всем чем том тем тому кто когда где куда пока ещё еще либо тоже также этого этому
этих такой такие таких себя свои своих речь слово слова написал пишет сообщение группу
подписку отменить отправьте пользователь googlegroups адресу nagari gmail unsubscribe
optout получили письмо получать подписаны сообщения ревнителей общество санскрита""".split())


def c_tf_idf_keywords(docs: list[tuple[int, str, str]], labels: list[int], top_n: int = 8) -> dict[int, list[str]]:
    """Per-cluster keyword extraction via a simple class-based TF-IDF over lemmas."""
    from nagari_group_archive._lemma import tokens as lemma_tokens

    cluster_docs: dict[int, list[str]] = {}
    for (_, subj, body), label in zip(docs, labels):
        if label < 0:
            continue
        toks = [t for t in lemma_tokens(f"{subj}\n{body}", min_len=4) if t not in STOP]
        cluster_docs.setdefault(label, []).extend(toks)

    df = Counter()
    for toks in cluster_docs.values():
        df.update(set(toks))
    n_clusters = max(len(cluster_docs), 1)

    keywords: dict[int, list[str]] = {}
    for label, toks in cluster_docs.items():
        tf = Counter(toks)
        scored = []
        for term, count in tf.items():
            idf = n_clusters / (1 + df[term])
            scored.append((term, count * idf))
        scored.sort(key=lambda x: x[1], reverse=True)
        keywords[label] = [t for t, _ in scored[:top_n]]
    return keywords


def write_report(out_path: Path, docs: list[tuple[int, str, str]], labels: list[int], keywords: dict[int, list[str]]) -> None:
    counts = Counter(labels)
    lines = [
        "_Created: 18-08-2026 · Last updated: 18-08-2026_",
        "",
        "# Topic-discovery gap report (H1518 Step 2)",
        "",
        f"Offline HDBSCAN clustering over {len(docs)} messages currently classified as "
        "«разное» by the curated taxonomy (`nagari_group_archive/taxonomy.py`). Each row is "
        "a discovered cluster with its top c-TF-IDF keywords (lemmatized) — no message body "
        "text is included, counts and keywords only. Fold clusters that represent a real "
        "topic (not noise/boilerplate) into `taxonomy.py` as new children.",
        "",
        f"Noise (unclustered, label -1): {counts.get(-1, 0)} messages.",
        "",
        "| cluster | n messages | top keywords |",
        "|---|---|---|",
    ]
    for label, n in counts.most_common():
        if label < 0:
            continue
        kw = ", ".join(keywords.get(label, []))
        lines.append(f"| {label} | {n} | {kw} |")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=MAX_DOCS)
    args = ap.parse_args(argv)

    print("loading misc-bucket messages...", flush=True)
    docs = load_docs(args.db, args.limit)
    print(f"  {len(docs)} messages currently classified as misc", flush=True)
    if not docs:
        print("nothing to cluster; skipping.", flush=True)
        return

    try:
        print(f"loading {MODEL_NAME} and clustering (this fetches model weights once)...", flush=True)
        labels, _ = embed_and_cluster(docs)
    except Exception as exc:  # noqa: BLE001 - autonomy contract: skip cleanly, do not stall
        print(f"SKIPPED: embedding model unfetchable ({exc}); seed taxonomy from misc_audit.csv terms alone.", flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            "_Created: 18-08-2026 · Last updated: 18-08-2026_\n\n"
            "# Topic-discovery gap report (H1518 Step 2)\n\n"
            f"SKIPPED — offline embedding model unfetchable ({exc}). Taxonomy expansion "
            "(Step 3) was seeded from `data/processed/misc_audit.csv` terms alone, per the "
            "plan's autonomy contract (risk: \"Offline embedding model unfetchable\").\n",
            encoding="utf-8",
        )
        return

    print("extracting per-cluster keywords...", flush=True)
    keywords = c_tf_idf_keywords(docs, labels, top_n=8)
    write_report(args.out, docs, labels, keywords)
    n_clusters = len({l for l in labels if l >= 0})
    print(f"wrote {args.out} ({n_clusters} clusters)", flush=True)


if __name__ == "__main__":
    main()
