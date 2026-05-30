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

new_nlp = '''    import pickle
    
    corpus_hash = hashlib.sha256(json.dumps(corpus).encode("utf-8")).hexdigest()
    cache_path = Path("analytics_output/nlp_cache.pkl")
    
    lda_fit = False
    if cache_path.exists():
        try:
            cached = pickle.loads(cache_path.read_bytes())
            if cached.get("corpus_hash") == corpus_hash:
                tfidf_matrix = cached["tfidf_matrix"]
                topic_distributions = cached["topic_distributions"]
                topic_terms = cached["topic_terms"]
                dominant_topics = topic_distributions.argmax(axis=1)
                lda_fit = True
        except Exception:
            pass
            
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
            
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(pickle.dumps({
            "corpus_hash": corpus_hash,
            "tfidf_matrix": tfidf_matrix,
            "topic_distributions": topic_distributions,
            "topic_terms": topic_terms,
        }))'''

if "corpus_hash = hashlib" not in content:
    content = content.replace(old_nlp, new_nlp)

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Phase 2 Patch applied successfully.")
