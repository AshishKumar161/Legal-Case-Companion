"""
Embeddings Module for LCC Legal AI Backend.
Provides an extensible embedding interface:
- SentenceTransformerEmbeddings (InLegalBERT / all-MiniLM-L6-v2) when sentence-transformers is installed.
- LocalTFIDFEmbeddings using scikit-learn (already installed in environment) as a robust,
  fast, zero-download local embedder.
"""

from __future__ import annotations
import os
import re
import math
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import Normalizer

logger = logging.getLogger("lcc.embeddings")


class BaseEmbeddings(ABC):
    """Abstract Base Class for text embeddings."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of document texts into dense vectors."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Encode a single query string into a dense vector."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass


class SentenceTransformerEmbeddings(BaseEmbeddings):
    """
    HuggingFace / sentence-transformers dense embedding model.
    Defaults to law-ai/InLegalBERT or sentence-transformers/all-MiniLM-L6-v2.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model_name = model_name
            self._model = SentenceTransformer(model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Loaded SentenceTransformer: {model_name} (dim={self._dim})")
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install with `pip install sentence-transformers` or use LocalTFIDFEmbeddings."
            ) from e

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()

    @property
    def dimension(self) -> int:
        return self._dim


class LocalTFIDFEmbeddings(BaseEmbeddings):
    """
    Robust local embedding model using scikit-learn TfidfVectorizer + TruncatedSVD.
    Runs 100% locally with zero external network downloads or GPU dependencies.
    Produces L2-normalized dense embeddings suitable for cosine similarity search.
    """

    # Domain vocabulary to ensure high semantic separation for legal concepts
    SEED_LEGAL_CORPUS = [
        "cyber fraud digital arrest customs police impersonation upi money transfer phishing online banking otp",
        "cheating forgery 318 bns 420 ipc dishonest inducement valuable security falsification signature",
        "crimes against women domestic violence assault 354 ipc 74 bns modesty harassment stalking",
        "theft burglary stolen property vehicle house breaking 379 ipc 303 bns trespass apprehension",
        "crimes against senior citizens maintenance parents senior citizens act property dispossession elder abuse neglect",
        "information technology act 66d identity theft computer resource cybercrime reporting portal 1930 helpline",
        "district sessions court magistrate bail conviction acquittal disposal sentence fine imprisonment",
        "first information report fir police complaint evidence transaction slip utr call records chat logs",
    ]

    def __init__(self, dimension: int = 128):
        self._dim = dimension
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=2000,
            token_pattern=r"(?u)\b\w[\w-]*\w\b|\b\w+\b",
        )
        self.svd = TruncatedSVD(n_components=min(dimension, 64), random_state=42)
        self.normalizer = Normalizer(copy=False)
        self._fitted = False

        # Fit initially on domain corpus so it can immediately embed queries
        self._fit(self.SEED_LEGAL_CORPUS)

    def _fit(self, texts: List[str]):
        combined = list(set(self.SEED_LEGAL_CORPUS + texts))
        tfidf_matrix = self.vectorizer.fit_transform(combined)
        n_samples, n_features = tfidf_matrix.shape
        n_comp = min(self._dim, n_samples - 1, n_features - 1)
        if n_comp < 2:
            n_comp = 2
        self.svd = TruncatedSVD(n_components=n_comp, random_state=42)
        self.svd.fit(tfidf_matrix)
        self._fitted = True

    def fit_documents(self, texts: List[str]):
        """Refits the vectorizer over the complete indexed case corpus."""
        self._fit(texts)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        tfidf = self.vectorizer.transform(texts)
        reduced = self.svd.transform(tfidf)
        # Pad to self._dim if n_components was smaller than requested dimension
        if reduced.shape[1] < self._dim:
            pad_width = ((0, 0), (0, self._dim - reduced.shape[1]))
            reduced = np.pad(reduced, pad_width, mode="constant")
        normed = self.normalizer.transform(reduced)
        return normed.tolist()

    def embed_query(self, text: str) -> List[float]:
        docs = self.embed_documents([text])
        return docs[0] if docs else [0.0] * self._dim

    @property
    def dimension(self) -> int:
        return self._dim


def get_embedding_model(
    model_type: Optional[str] = None,
    model_name: Optional[str] = None,
) -> BaseEmbeddings:
    """
    Factory function to obtain the appropriate embedding model.
    If 'sentence_transformers' is requested and available, it loads it;
    otherwise falls back smoothly to LocalTFIDFEmbeddings.
    """
    val = model_type or os.getenv("LCC_EMBEDDING_TYPE", "auto")
    model_type = val.lower() if val is not None else "auto"

    if model_type in ("sentence_transformers", "huggingface"):
        try:
            return SentenceTransformerEmbeddings(
                model_name=model_name or "sentence-transformers/all-MiniLM-L6-v2"
            )
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer ({e}). Falling back to LocalTFIDFEmbeddings.")
            return LocalTFIDFEmbeddings()

    elif model_type == "local_tfidf":
        return LocalTFIDFEmbeddings()

    # 'auto': Try sentence-transformers first if available, else LocalTFIDFEmbeddings
    try:
        import sentence_transformers
        return SentenceTransformerEmbeddings(
            model_name=model_name or "sentence-transformers/all-MiniLM-L6-v2"
        )
    except ImportError:
        logger.info("SentenceTransformers not installed; initializing fast LocalTFIDFEmbeddings.")
        return LocalTFIDFEmbeddings()


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
