import re

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add MANIFEST dictionaries and write_bytes
if "MANIFEST_HASHES =" not in content:
    content = re.sub(
        r'LEGACY_REDIRECT_PATHS = set\(\)\n',
        r'LEGACY_REDIRECT_PATHS = set()\nMANIFEST_HASHES = {}\nMANIFEST_SIZES = {}\n',
        content
    )

old_write_text = '''def write_text(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8", newline="\\n")'''

new_write_text = '''def write_text(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    byte_content = content.encode("utf-8")
    rel_path = str(path).replace("\\\\", "/")
    MANIFEST_HASHES[rel_path] = hashlib.sha256(byte_content).hexdigest()
    MANIFEST_SIZES[rel_path] = len(byte_content)
    Path(path).write_text(content, encoding="utf-8", newline="\\n")

def write_bytes(path, byte_content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rel_path = str(path).replace("\\\\", "/")
    MANIFEST_HASHES[rel_path] = hashlib.sha256(byte_content).hexdigest()
    MANIFEST_SIZES[rel_path] = len(byte_content)
    Path(path).write_bytes(byte_content)'''

content = content.replace(old_write_text, new_write_text)

# 2. Update write_app_icon and write_og_image to use write_bytes instead of write_bytes
content = content.replace("Path(path).write_bytes(png)", "write_bytes(path, png)")

# 3. Update generate_publication_file_manifest
old_manifest = '''def generate_publication_file_manifest():
    rows = []
    for path in generated_manifest_paths():
        rel = str(path).replace("\\\\", "/")
        rows.append({
            "path": rel,
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        })'''

new_manifest = '''def generate_publication_file_manifest():
    rows = []
    for path in generated_manifest_paths():
        rel = str(path).replace("\\\\", "/")
        if rel in MANIFEST_HASHES:
            sha = MANIFEST_HASHES[rel]
            size = MANIFEST_SIZES[rel]
        else:
            sha = file_sha256(path)
            size = path.stat().st_size
        rows.append({
            "path": rel,
            "size_bytes": size,
            "sha256": sha,
        })'''

content = content.replace(old_manifest, new_manifest)

# 4. Update generate_nlp_page
old_nlp = '''    vectorizer = TfidfVectorizer(max_df=0.95, min_df=2, max_features=400)
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = list(vectorizer.get_feature_names_out())
    idf_weights = list(vectorizer.idf_)

    lda = LatentDirichletAllocation(n_components=6, random_state=42, max_iter=10)
    lda.fit(tfidf_matrix)
    
    topic_distributions = lda.transform(tfidf_matrix)
    dominant_topics = topic_distributions.argmax(axis=1)
    
    topic_terms = []
    for topic_idx, topic in enumerate(lda.components_):
        top_features_ind = topic.argsort()[:-10 - 1:-1]
        top_features = [feature_names[i] for i in top_features_ind]
        topic_terms.append(top_features)'''

new_nlp = '''    import numpy as np
    from scipy import sparse

    corpus_hash = hashlib.sha256(json.dumps(corpus).encode("utf-8")).hexdigest()
    cache_dir = Path("analytics_output")
    cache_npz = cache_dir / "nlp_cache.npz"
    cache_tfidf = cache_dir / "nlp_tfidf.npz"
    cache_meta = cache_dir / "nlp_cache_meta.json"

    def _nlp_cache_load():
        # Non-executable cache only: .npz arrays (allow_pickle=False) + JSON
        # meta. Any failure or hash mismatch falls back to a fresh fit.
        try:
            meta = json.loads(cache_meta.read_text(encoding="utf-8"))
            if meta.get("corpus_hash") != corpus_hash:
                return None
            arrays = np.load(cache_npz, allow_pickle=False)
            return {
                "tfidf_matrix": sparse.load_npz(cache_tfidf),
                "topic_distributions": arrays["topic_distributions"],
                "topic_terms": meta["topic_terms"],
                "feature_names": meta["feature_names"],
                "idf_weights": list(arrays["idf_weights"]),
            }
        except Exception:
            return None

    def _nlp_cache_save(fit):
        cache_dir.mkdir(parents=True, exist_ok=True)
        sparse.save_npz(cache_tfidf, fit["tfidf_matrix"])
        np.savez_compressed(
            cache_npz,
            topic_distributions=np.asarray(fit["topic_distributions"]),
            idf_weights=np.asarray(fit["idf_weights"], dtype=float),
        )
        cache_meta.write_text(json.dumps({
            "corpus_hash": corpus_hash,
            "topic_terms": fit["topic_terms"],
            "feature_names": list(fit["feature_names"]),
        }, ensure_ascii=False), encoding="utf-8")

    lda_fit = False
    cached = _nlp_cache_load()
    if cached is not None:
        tfidf_matrix = cached["tfidf_matrix"]
        topic_distributions = cached["topic_distributions"]
        topic_terms = cached["topic_terms"]
        feature_names = cached["feature_names"]
        idf_weights = cached["idf_weights"]
        dominant_topics = topic_distributions.argmax(axis=1)
        lda_fit = True
            
    if not lda_fit:
        vectorizer = TfidfVectorizer(max_df=0.95, min_df=2, max_features=400)
        tfidf_matrix = vectorizer.fit_transform(corpus)
        feature_names = list(vectorizer.get_feature_names_out())
        idf_weights = list(vectorizer.idf_)

        lda = LatentDirichletAllocation(n_components=6, random_state=42, max_iter=10)
        lda.fit(tfidf_matrix)
        
        topic_distributions = lda.transform(tfidf_matrix)
        dominant_topics = topic_distributions.argmax(axis=1)
        
        topic_terms = []
        for topic_idx, topic in enumerate(lda.components_):
            top_features_ind = topic.argsort()[:-10 - 1:-1]
            top_features = [feature_names[i] for i in top_features_ind]
            topic_terms.append(top_features)
            
        _nlp_cache_save({
            "tfidf_matrix": tfidf_matrix,
            "topic_distributions": topic_distributions,
            "topic_terms": topic_terms,
            "feature_names": feature_names,
            "idf_weights": idf_weights,
        })'''

if "corpus_hash = hashlib" not in content:
    content = content.replace(old_nlp, new_nlp)

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Phase 2 Patch applied successfully.")
