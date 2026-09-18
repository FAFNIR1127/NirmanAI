import os
import json
from pathlib import Path
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
import joblib

EMBEDDING_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "embeddings"
EMBEDDING_DIR.mkdir(parents=True, exist_ok=True)
FALLBACK_MODEL_PATH = EMBEDDING_DIR / "tfidf_svd_encoder.joblib"


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dimension: int = 384):
        self.dimension = dimension
        self.st_model = None
        self.tfidf_vectorizer = None
        self.svd_model = None
        self.mode = None

        if HAS_SENTENCE_TRANSFORMERS:
            try:
                # Load pre-trained MiniLM sentence transformer
                self.st_model = SentenceTransformer(model_name)
                self.mode = "sentence_transformer"
                print(f"[EmbeddingService] Loaded SentenceTransformer model: {model_name}")
            except Exception as e:
                print(f"[EmbeddingService] Could not load SentenceTransformer ({e}). Falling back to TFIDF-SVD.")
        
        if not self.mode:
            if FALLBACK_MODEL_PATH.exists():
                saved_models = joblib.load(FALLBACK_MODEL_PATH)
                self.tfidf_vectorizer = saved_models["tfidf"]
                self.svd_model = saved_models["svd"]
                self.mode = "tfidf_svd"
                print(f"[EmbeddingService] Loaded fallback TFIDF-SVD encoder from {FALLBACK_MODEL_PATH}")
            else:
                self.mode = "unfitted_tfidf_svd"
                print(f"[EmbeddingService] Initialized unfitted TFIDF-SVD encoder. Call fit_fallback() to train on corpus.")

    def fit_fallback(self, texts: list[str]):
        """Fit TF-IDF + TruncatedSVD on the corpus for fallback dense embeddings."""
        print(f"[EmbeddingService] Fitting TF-IDF + TruncatedSVD ({self.dimension} dims) on {len(texts)} texts...")
        self.tfidf_vectorizer = TfidfVectorizer(max_features=20000, stop_words='english', ngram_range=(1, 2))
        tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
        
        n_components = min(self.dimension, tfidf_matrix.shape[1] - 1, len(texts) - 1)
        self.svd_model = TruncatedSVD(n_components=n_components, random_state=42)
        self.svd_model.fit(tfidf_matrix)
        
        joblib.dump({"tfidf": self.tfidf_vectorizer, "svd": self.svd_model}, FALLBACK_MODEL_PATH)
        self.mode = "tfidf_svd"
        print(f"[EmbeddingService] TFIDF-SVD encoder fitted and saved to {FALLBACK_MODEL_PATH}")

    def encode(self, texts: list[str] | str) -> np.ndarray:
        """Encode text or list of texts into dense floating point vectors."""
        is_single = isinstance(texts, str)
        text_list = [texts] if is_single else texts

        if self.mode == "sentence_transformer" and self.st_model:
            embeddings = self.st_model.encode(text_list, show_progress_bar=False, normalize_embeddings=True)
            embeddings = np.array(embeddings, dtype=np.float32)
        elif self.mode == "tfidf_svd" and self.tfidf_vectorizer and self.svd_model:
            tfidf_mat = self.tfidf_vectorizer.transform(text_list)
            svd_mat = self.svd_model.transform(tfidf_mat)
            # Normalize to unit length
            norms = np.linalg.norm(svd_mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings = (svd_mat / norms).astype(np.float32)
            # Pad if dimension < requested dimension
            if embeddings.shape[1] < self.dimension:
                pad_width = self.dimension - embeddings.shape[1]
                embeddings = np.pad(embeddings, ((0, 0), (0, pad_width)), mode='constant')
        else:
            # Fallback zero/random normalized embedding
            print("[EmbeddingService WARNING] Model not fitted. Using dummy normalized vectors.")
            embeddings = np.random.randn(len(text_list), self.dimension).astype(np.float32)
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms

        if is_single:
            return embeddings[0]
        return embeddings
