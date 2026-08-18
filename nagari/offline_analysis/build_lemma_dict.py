"""Build the static form->lemma map for the nagari live pipeline (H1518 Step 1).

Runs OFFLINE ONLY, once per data refresh. Reads ``nagari.db`` subjects+bodies,
lemmatizes every distinct Russian token (>=3 chars) with natasha, and writes
``data/lemma_map.json``. The live pipeline (``nagari_group_archive._lemma``)
only ever *reads* that JSON file and never imports natasha/pymorphy2 -- the
stdlib-only contract for the reproducible pipeline stays intact.

Usage (from ``nagari/``):
    python offline_analysis/build_lemma_dict.py --db data/nagari.db
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

RU_TOKEN = re.compile(r"[а-яёА-ЯЁ]{3,}")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "nagari.db"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "lemma_map.json"


def configure_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")


def collect_tokens(db_path: Path) -> set[str]:
    db = sqlite3.connect(db_path)
    forms: set[str] = set()
    for subj, body in db.execute("SELECT subject_clean, body_text FROM messages"):
        blob = f"{subj or ''}\n{body or ''}"
        forms.update(m.group(0).casefold() for m in RU_TOKEN.finditer(blob))
    db.close()
    return forms


def lemmatize_forms(forms: set[str]) -> dict[str, str]:
    from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter

    segmenter = Segmenter()
    embedding = NewsEmbedding()
    morph_tagger = NewsMorphTagger(embedding)
    morph_vocab = MorphVocab()

    lemma_map: dict[str, str] = {}
    batch_size = 2000
    ordered = sorted(forms)
    for i in range(0, len(ordered), batch_size):
        batch = ordered[i : i + batch_size]
        text = " ".join(batch)
        doc = Doc(text)
        doc.segment(segmenter)
        doc.tag_morph(morph_tagger)
        for token in doc.tokens:
            token.lemmatize(morph_vocab)
            key = token.text.casefold()
            if key and token.lemma:
                lemma_map[key] = token.lemma
        print(f"  lemmatized {min(i + batch_size, len(ordered))}/{len(ordered)}", flush=True)
    return lemma_map


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    print("collecting distinct RU tokens...", flush=True)
    forms = collect_tokens(args.db)
    print(f"  {len(forms)} distinct forms", flush=True)

    print("lemmatizing (natasha)...", flush=True)
    lemma_map = lemmatize_forms(forms)

    covered = sum(1 for f in forms if f in lemma_map)
    coverage = covered / len(forms) if forms else 0.0
    print(f"coverage: {covered}/{len(forms)} = {coverage:.1%}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(lemma_map, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8",
    )
    print(f"wrote {args.out} ({len(lemma_map)} entries)", flush=True)


if __name__ == "__main__":
    main()
