"""H5538 — nlp_cache round-trip: write → read → delete → re-fit → corrupt → re-fit.

Drives the EXACT cache block shipped in generate_publication_pages.py
(generate_nlp_page) by slicing it out of the real source and exec'ing it in a
controlled namespace, so the test cannot drift from the shipped code.
"""

import hashlib
import json
import textwrap
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "generate_publication_pages.py"

START = "    import numpy as _np_cache"
END_ANCHOR = "_np_cache.array(idf_weights, dtype=float),"


def _extract_block() -> str:
    src = SRC.read_text(encoding="utf-8")
    i = src.index(START)
    j = src.index(END_ANCHOR, i)
    j = src.index("\n        )", j) + len("\n        )")
    return textwrap.dedent(src[i:j])


def _run_block(corpus, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ns = {
        "corpus": list(corpus),
        "hashlib": hashlib,
        "json": json,
        "Path": Path,
        "TfidfVectorizer": TfidfVectorizer,
        "LatentDirichletAllocation": LatentDirichletAllocation,
    }
    exec(compile(_extract_block(), str(SRC), "exec"), ns)  # noqa: S102
    return ns


CORPUS_A = [
    "sanskrit grammar verb morphology panini roots",
    "vedic hymns rigveda ritual indology texts",
    "buddhist philosophy texts sanskrit manuscripts canon",
    "epic mahabharata ramayana poetry sanskrit literature",
    "tantra mantras ritual practice shastra traditions",
    "inscription copper plate land grants medieval india",
    "dictionary lexicon lexicography monier williams entries",
    "commentary bhashya shankara vedanta upanishads",
] * 3

CORPUS_B = [
    "astronomy jyotisha planetary calculations sanskrit tables",
    "mathematics sulba sutras geometry altars measurements",
    "medicine ayurveda charaka samhita herbs diagnosis",
    "architecture vastu shastra temple plans proportions",
    "music sangita ragas talas treatise theory",
    "law dharmashastra varna duties courts inheritance",
    "statecraft arthashastra kautilya governance spies",
    "poetics alamkara rasa drama aesthetics theory",
] * 3


def test_block_present_and_pickle_free():
    block = _extract_block()
    assert "import pickle" not in block
    assert "pickle.load" not in block
    assert "pickle.dump" not in block
    assert "allow_pickle=False" in block
    assert "nlp_cache.npz" in block


def test_write_read_roundtrip_identical(tmp_path, monkeypatch):
    block = _extract_block()
    cache = tmp_path / "analytics_output" / "nlp_cache.npz"

    fit = _run_block(CORPUS_A, tmp_path, monkeypatch)          # write
    assert cache.exists()
    with np.load(cache, allow_pickle=False) as saved:           # non-executable load works
        assert str(saved["corpus_hash"]) == hashlib.sha256(
            json.dumps(CORPUS_A).encode("utf-8")).hexdigest()

    hit = _run_block(CORPUS_A, tmp_path, monkeypatch)          # read (cache hit)
    a, b = fit["tfidf_matrix"], hit["tfidf_matrix"]
    assert a.shape == b.shape
    assert np.array_equal(a.data, b.data)
    assert np.array_equal(a.indices, b.indices)
    assert np.array_equal(a.indptr, b.indptr)
    assert np.array_equal(fit["topic_distributions"], hit["topic_distributions"])
    assert np.array_equal(fit["dominant_topics"], hit["dominant_topics"])
    assert fit["topic_terms"] == hit["topic_terms"]
    assert fit["feature_names"] == hit["feature_names"]
    assert fit["idf_weights"] == hit["idf_weights"]


def test_corpus_hash_gate_refits_on_change(tmp_path, monkeypatch):
    cache = tmp_path / "analytics_output" / "nlp_cache.npz"
    first = _run_block(CORPUS_A, tmp_path, monkeypatch)
    assert cache.exists()

    second = _run_block(CORPUS_B, tmp_path, monkeypatch)       # stale hash → re-fit
    want = hashlib.sha256(json.dumps(CORPUS_B).encode("utf-8")).hexdigest()
    with np.load(cache, allow_pickle=False) as saved:
        assert str(saved["corpus_hash"]) == want
    assert second["feature_names"] != first["feature_names"]   # different corpus refit
    assert second["topic_terms"] is not None


def test_delete_then_refit_recreates(tmp_path, monkeypatch):
    cache = tmp_path / "analytics_output" / "nlp_cache.npz"
    _run_block(CORPUS_A, tmp_path, monkeypatch)
    cache.unlink()
    assert not cache.exists()
    _run_block(CORPUS_A, tmp_path, monkeypatch)                # re-fit
    assert cache.exists()
    with np.load(cache, allow_pickle=False) as saved:
        assert str(saved["corpus_hash"]) == hashlib.sha256(
            json.dumps(CORPUS_A).encode("utf-8")).hexdigest()


def test_corrupt_cache_refits_never_raises(tmp_path, monkeypatch):
    cache = tmp_path / "analytics_output" / "nlp_cache.npz"
    _run_block(CORPUS_A, tmp_path, monkeypatch)

    cache.write_bytes(b"NOT AN NPZ FILE \x00\x01\x02 garbage")  # corrupt
    ns = _run_block(CORPUS_A, tmp_path, monkeypatch)            # must re-fit, no escape
    assert "tfidf_matrix" in ns and "topic_terms" in ns
    with np.load(cache, allow_pickle=False) as saved:           # valid cache rewritten
        assert str(saved["corpus_hash"]) == hashlib.sha256(
            json.dumps(CORPUS_A).encode("utf-8")).hexdigest()

    cache.write_bytes(b"")                                      # empty file too
    ns = _run_block(CORPUS_A, tmp_path, monkeypatch)
    assert "topic_terms" in ns
