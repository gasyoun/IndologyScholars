import sqlite3
import re
import sys
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity
import pymorphy3

# Reconfigure stdout to force UTF-8 printing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def preprocess_text(text, morph):
    # Remove punctuation and digits, lowercase
    text = re.sub(r'[^\w\s\-\u0400-\u04FF]', ' ', text.lower())
    text = re.sub(r'\d+', ' ', text)
    tokens = text.split()
    
    # Simple stop words (Russian + English)
    stop_words = {
        'и', 'в', 'во', 'на', 'с', 'со', 'о', 'об', 'обо', 'к', 'ко', 'из', 'от', 'до', 'у', 'для',
        'по', 'за', 'при', 'над', 'под', 'через', 'а', 'но', 'да', 'или', 'же', 'бы', 'ли', 'это',
        'как', 'так', 'что', 'чтобы', 'его', 'ее', 'их', 'он', 'она', 'они', 'мы', 'вы', 'я',
        'the', 'of', 'in', 'and', 'to', 'a', 'for', 'with', 'on', 'at', 'by', 'from', 'an', 'is'
    }
    
    cleaned = []
    for t in tokens:
        if t in stop_words or len(t) < 2:
            continue
        # Lemmatize Cyrillic tokens using pymorphy3
        if re.match(r'^[\u0400-\u04FF\s\-]+$', t):
            parsed = morph.parse(t)[0]
            lemma = parsed.normal_form
            cleaned.append(lemma)
        else:
            cleaned.append(t)
            
    return " ".join(cleaned)

def main():
    print("=== NLP & SEMANTIC TOPIC MODELING PROTOTYPE ===")
    
    # 1. Load data from the database
    conn = sqlite3.connect("conferences.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.presentation_id, p.title, e.year, e.event_series_id
        FROM presentation p
        JOIN session s ON p.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    """)
    presentations = cursor.fetchall()
    conn.close()
    
    num_docs = len(presentations)
    print(f"Loaded {num_docs} presentations from conferences.db.")
    
    if num_docs == 0:
        print("No presentations found. Exiting.")
        return

    # Initialize Russian Morphological Analyzer
    morph = pymorphy3.MorphAnalyzer()
    
    # Preprocess all titles
    print("Preprocessing text corpora (lemmatizing and removing stop words)...")
    corpus = []
    original_titles = []
    pres_meta = []
    
    for pid, title, year, series in presentations:
        cleaned = preprocess_text(title, morph)
        corpus.append(cleaned)
        original_titles.append(title)
        pres_meta.append((pid, title, year, "Zograf" if series == 1 else "Roerich"))
        
    # 2. Compute TF-IDF matrix
    print("Extracting features with TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(max_df=0.95, min_df=2, max_features=1000)
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()
    print(f"TF-IDF Matrix shape: {tfidf_matrix.shape} (Vocabulary size: {len(feature_names)})")

    # 3. Unsupervised Latent Dirichlet Allocation (LDA) Topic Modeling
    n_topics = 6
    print(f"Fitting LDA model with {n_topics} latent semantic topics...")
    lda = LatentDirichletAllocation(n_components=n_topics, random_state=42, max_iter=15)
    lda.fit(tfidf_matrix)
    
    print("\n=== IDENTIFIED ACADEMIC TOPICS (LDA) ===")
    for topic_idx, topic in enumerate(lda.components_):
        top_features_ind = topic.argsort()[:-10 - 1:-1]
        top_features = [feature_names[i] for i in top_features_ind]
        print(f"Topic #{topic_idx + 1}: {', '.join(top_features)}")

    # 4. Dense Semantic Similarity Search Prototype (Vector Cosine Similarity)
    print("\n=== SEMANTIC SIMILARITY SEARCH DEMONSTRATION ===")
    # Define a conceptual query (not necessarily sharing exact words with the titles)
    test_queries = [
        "буддийские сутры и тексты на санскрите",
        "индийская философия и учения",
        "грамматика панини и языковедческий анализ"
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        # Clean and vectorize query
        cleaned_query = preprocess_text(query, morph)
        query_vector = vectorizer.transform([cleaned_query])
        
        # Calculate cosine similarity with all papers
        similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
        
        # Get top 3 most semantically similar presentations
        top_indices = similarities.argsort()[:-4:-1]
        
        print("Top matches:")
        for idx in top_indices:
            score = similarities[idx]
            if score > 0.0:
                pid, title, year, series = pres_meta[idx]
                print(f"  - [{score:.3f}] {title} ({series} {year})")
            else:
                print("  - No relevant matches above 0.0 threshold.")

if __name__ == "__main__":
    main()
