import sqlite3
import re
from pathlib import Path
from collections import defaultdict
import pymorphy3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "conferences.db"
OUT_MD = ROOT / "analytics_output" / "keyword_clusters.md"

def load_titles():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT presentation_id, title FROM presentation")
    data = cur.fetchall()
    conn.close()
    return data

# Stop words specific to Russian academia/conference context
STOP_WORDS = {
    "к", "в", "с", "и", "на", "по", "о", "об", "для", "из", "за", "от",
    "не", "что", "как", "это", "как", "его", "ее", "их", "он", "она", "они",
    "быть", "был", "была", "были", "год", "век", "вв", "гг", "проблема", "особенности",
    "некоторые", "вопрос", "вопросы", "тема", "роль", "значение", "анализ", "исследование",
    "а", "у", "же", "то", "но", "да", "или", "ли", "бы", "ни", "до", "со", "при"
}

def preprocess_titles(data):
    morph = pymorphy3.MorphAnalyzer()
    processed = []
    
    for pid, title in data:
        # Tokenize (extract cyrillic words length >= 3)
        words = re.findall(r'[а-яёА-ЯЁ]{3,}', title.lower())
        lemmas = []
        for w in words:
            if w in STOP_WORDS:
                continue
            p = morph.parse(w)[0]
            lemma = p.normal_form
            if lemma not in STOP_WORDS and len(lemma) > 2:
                lemmas.append(lemma)
        processed.append((pid, title, " ".join(lemmas)))
        
    return processed

def run_nmf_clustering(texts, n_topics=6, n_top_words=20):
    tfidf_vectorizer = TfidfVectorizer(max_df=0.90, min_df=2, use_idf=True)
    tfidf_matrix = tfidf_vectorizer.fit_transform(texts)
    
    nmf_model = NMF(n_components=n_topics, random_state=42, max_iter=500)
    nmf_model.fit(tfidf_matrix)
    
    tfidf_feature_names = tfidf_vectorizer.get_feature_names_out()
    
    topics = []
    for topic_idx, topic in enumerate(nmf_model.components_):
        top_features_ind = topic.argsort()[:-n_top_words - 1:-1]
        top_features = [tfidf_feature_names[i] for i in top_features_ind]
        topics.append({
            "topic_idx": topic_idx + 1,
            "keywords": top_features
        })
    return topics

def main():
    print("Loading titles from DB...")
    data = load_titles()
    
    print("Lemmatizing titles...")
    processed_data = preprocess_titles(data)
    texts = [item[2] for item in processed_data if item[2]]
    
    print(f"Extracted {len(texts)} valid processed titles.")
    
    n_topics = 6
    print(f"Running NMF for {n_topics} clusters...")
    topics = run_nmf_clustering(texts, n_topics=n_topics, n_top_words=25)
    
    OUT_MD.parent.mkdir(exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# Keyword Clusters (TF-IDF + NMF)\n\n")
        f.write(f"Based on `{len(texts)}` presentation titles, analyzed via pymorphy3.\n\n")
        
        for t in topics:
            f.write(f"### Cluster {t['topic_idx']}\n")
            f.write(f"- **Keywords:** {', '.join(t['keywords'])}\n\n")
            
    print(f"Wrote clusters to {OUT_MD}")

if __name__ == "__main__":
    main()
