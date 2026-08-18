"""Key-phrase layer: PMI + log-likelihood bigram collocations + TF-IDF (H1518 Step 5).

Stays stdlib (no natasha import here -- only reads ``data/lemma_map.json`` via
``nagari_group_archive._lemma``), but lives under ``offline_analysis/`` per the
architecture doc's grouping (it is a batch/offline artifact-producer, run once
per data refresh and committed as a static ``data/phrases.csv``).

Method (cited):
    PMI(w1, w2)  = log( P(w1,w2) / (P(w1) * P(w2)) )
    LLR(w1, w2)  = 2 * sum( O_ij * log(O_ij / E_ij) )   over the 2x2 contingency
                   table of (w1 present, w2 present) x (bigram present, absent)
                   -- Dunning (1993) log-likelihood ratio for collocations.
    TF-IDF        standard term-frequency x inverse-document-frequency over
                   lemmatized subjects+bodies, document = one message.

Usage (from ``nagari/``):
    python offline_analysis/build_phrases.py --db data/nagari.db
"""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "nagari.db"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "phrases.csv"
MIN_BIGRAM_COUNT = 5
MIN_TERM_LEN = 4


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def load_lemmatized_docs(db_path: Path) -> list[list[str]]:
    from nagari_group_archive._lemma import tokens as lemma_tokens, strip_footer_and_quotes

    db = sqlite3.connect(db_path)
    docs: list[list[str]] = []
    for subj, body in db.execute("SELECT subject_clean, body_text FROM messages"):
        text = f"{subj or ''}\n{strip_footer_and_quotes(body)[:3000]}"
        docs.append(lemma_tokens(text, min_len=MIN_TERM_LEN))
    db.close()
    return docs


def pmi_and_llr(docs: list[list[str]]) -> list[tuple[str, str, float, float, int]]:
    unigram = Counter()
    bigram = Counter()
    total_unigrams = 0
    for toks in docs:
        unigram.update(toks)
        total_unigrams += len(toks)
        for a, b in zip(toks, toks[1:]):
            bigram[(a, b)] += 1
    total_bigrams = sum(bigram.values()) or 1

    results = []
    for (w1, w2), c12 in bigram.items():
        if c12 < MIN_BIGRAM_COUNT:
            continue
        c1, c2 = unigram[w1], unigram[w2]
        p12 = c12 / total_bigrams
        p1 = c1 / total_unigrams
        p2 = c2 / total_unigrams
        pmi = math.log(p12 / (p1 * p2)) if p1 > 0 and p2 > 0 and p12 > 0 else 0.0

        # Dunning (1993) log-likelihood ratio over the 2x2 contingency table.
        n = total_unigrams
        o11, o12, o21, o22 = c12, c1 - c12, c2 - c12, n - c1 - c2 + c12
        llr = 0.0
        for o, e in (
            (o11, (c1 * c2) / n if n else 0),
            (o12, (c1 * (n - c2)) / n if n else 0),
            (o21, ((n - c1) * c2) / n if n else 0),
            (o22, ((n - c1) * (n - c2)) / n if n else 0),
        ):
            if o > 0 and e > 0:
                llr += o * math.log(o / e)
        llr *= 2
        results.append((w1, w2, pmi, llr, c12))
    return results


def tfidf_terms(docs: list[list[str]], top_n: int = 400) -> list[tuple[str, float]]:
    df = Counter()
    for toks in docs:
        df.update(set(toks))
    n_docs = len(docs) or 1
    tf = Counter()
    for toks in docs:
        tf.update(toks)
    scored = []
    for term, count in tf.items():
        idf = math.log(n_docs / (1 + df[term]))
        scored.append((term, count * idf))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    print("loading + lemmatizing corpus...", flush=True)
    docs = load_lemmatized_docs(args.db)
    print(f"  {len(docs)} documents", flush=True)

    print("computing bigram PMI/LLR...", flush=True)
    bigrams = pmi_and_llr(docs)
    bigrams.sort(key=lambda x: x[3], reverse=True)  # rank by LLR
    print(f"  {len(bigrams)} bigrams above min count", flush=True)

    print("computing TF-IDF single-term scores...", flush=True)
    unigrams = tfidf_terms(docs)

    rows = []
    for w1, w2, pmi, llr, n in bigrams[:400]:
        rows.append({"phrase": f"{w1} {w2}", "score": round(llr, 2), "method": "llr", "n": n})
    for term, score in unigrams:
        rows.append({"phrase": term, "score": round(score, 3), "method": "tfidf", "n": ""})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["phrase", "score", "method", "n"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out} ({len(rows)} rows)", flush=True)


if __name__ == "__main__":
    main()
