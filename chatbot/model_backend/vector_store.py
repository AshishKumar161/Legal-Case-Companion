"""
Vector Store Module for LCC AI/Model Backend.
Implements a modular, local in-memory vector index with disk persistence.
Preserves rich case metadata:
(case_id, court_name, crime_category, state, district, year, statutes, facts, outcome, keywords).
Designed around BaseVectorStore interface so it can be swapped for Qdrant or Weaviate later.
"""

from __future__ import annotations
import json
import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from .schemas import RetrievedSource, LegalCaseRecord, StatuteRecord
from .embeddings import BaseEmbeddings, cosine_similarity

logger = logging.getLogger("lcc.vector_store")


class BaseVectorStore(ABC):
    """
    Abstract interface for Vector Stores.
    Facilitates swapping the local prototype store with Qdrant, Milvus, or Weaviate.
    """

    @abstractmethod
    def add_documents(
        self,
        docs: List[Dict[str, Any]],
        vectors: Optional[List[List[float]]] = None,
    ):
        """Add documents and optional pre-computed vectors."""
        pass

    @abstractmethod
    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedSource]:
        """Dense similarity search."""
        pass

    @abstractmethod
    def search_by_keyword(
        self,
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedSource]:
        """Keyword / BM25 search."""
        pass

    @abstractmethod
    def save(self, filepath: str):
        """Persist index and metadata."""
        pass

    @abstractmethod
    def load(self, filepath: str):
        """Load index and metadata from disk."""
        pass


class LocalVectorStore(BaseVectorStore):
    """
    Local vector store implementation preserving full case & statute metadata.
    Stores records and normalized NumPy vectors in memory with JSON/NPY serialization.
    """

    def __init__(self, embedding_model: Optional[BaseEmbeddings] = None):
        self.embedding_model = embedding_model
        self.documents: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None
        self._doc_id_map: Dict[str, int] = {}

    def add_documents(
        self,
        docs: List[Dict[str, Any]],
        vectors: Optional[List[List[float]]] = None,
    ):
        """
        Add documents with optional pre-computed embeddings.
        If vectors are omitted and an embedding_model is configured, generates them.
        """
        if not docs:
            return

        texts_to_embed = []
        new_docs: list[Dict[str, Any]] = []

        for doc in docs:
            doc_id = doc.get("source_id") or doc.get("case_id") or doc.get("statute_id")
            if not doc_id:
                doc_id = f"doc-{len(self.documents) + len(new_docs)}"
            doc["source_id"] = doc_id

            # If already exists, update
            if doc_id in self._doc_id_map:
                idx = self._doc_id_map[doc_id]
                self.documents[idx] = doc
                continue

            new_docs.append(doc)
            # Embedding text extraction
            text = doc.get("embedding_text") or doc.get("text") or doc.get("fact_summary") or ""
            texts_to_embed.append(text)

        if not new_docs:
            return

        # Compute embeddings if not provided
        if vectors is None:
            if self.embedding_model is None:
                raise ValueError("Embedding model must be provided if vectors are not supplied.")
            computed_vectors = self.embedding_model.embed_documents(texts_to_embed)
            new_vectors_np = np.array(computed_vectors, dtype=np.float32)
        else:
            new_vectors_np = np.array(vectors, dtype=np.float32)

        # Normalize vectors for fast dot-product cosine similarity
        norms = np.linalg.norm(new_vectors_np, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        new_vectors_np = new_vectors_np / norms

        start_idx = len(self.documents)
        for i, doc in enumerate(new_docs):
            self._doc_id_map[doc["source_id"]] = start_idx + i
            self.documents.append(doc)

        if self.vectors is None:
            self.vectors = new_vectors_np
        else:
            self.vectors = np.vstack([self.vectors, new_vectors_np])

        logger.info(f"Indexed {len(new_docs)} documents into LocalVectorStore. Total count: {len(self.documents)}")

    def _matches_filters(self, doc: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        if not filters:
            return True
        for key, val in filters.items():
            if key == "crime_category":
                doc_cat = doc.get("crime_category") or doc.get("metadata", {}).get("crime_category")
                if isinstance(val, (list, tuple, set)):
                    if doc_cat and doc_cat not in val:
                        return False
                elif doc_cat and doc_cat != val:
                    return False
            elif key == "source_type":
                if doc.get("source_type") != val:
                    return False
            elif key == "year_min":
                doc_year = doc.get("year") or doc.get("metadata", {}).get("year", 0)
                if doc_year < val:
                    return False
            elif key == "state":
                doc_state = doc.get("state") or doc.get("metadata", {}).get("state")
                if doc_state and doc_state.lower() != val.lower():
                    return False
        return True

    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedSource]:
        """
        Dense vector cosine similarity search over indexed documents.
        """
        if self.vectors is None or len(self.documents) == 0:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # Cosine similarity via matrix multiplication
        scores = np.dot(self.vectors, q_vec)

        # Apply filters and sort
        ranked_indices = np.argsort(scores)[::-1]
        results: List[RetrievedSource] = []

        for idx in ranked_indices:
            if len(results) >= top_k:
                break
            doc = self.documents[idx]
            if not self._matches_filters(doc, filters):
                continue

            score = float(scores[idx])
            results.append(self._doc_to_retrieved_source(doc, score))

        return results

    def search_by_keyword(
        self,
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedSource]:
        """
        Lexical keyword search using token-frequency scoring.
        Particularly effective for specific statute numbers (e.g. 66D, 318, 420).
        """
        if not self.documents:
            return []

        query_tokens = set(query_text.lower().replace("-", " ").split())
        results = []

        for doc in self.documents:
            if not self._matches_filters(doc, filters):
                continue

            # Text to match against
            searchable_text = " ".join([
                doc.get("embedding_text", ""),
                doc.get("text", ""),
                doc.get("fact_summary", ""),
                " ".join(doc.get("keywords", [])),
                doc.get("title", ""),
                doc.get("citation", ""),
            ]).lower().replace("-", " ")

            doc_tokens = searchable_text.split()
            if not doc_tokens:
                continue

            # Calculate match score: exact keyword hits with bonus for statute sections
            overlap = query_tokens.intersection(set(doc_tokens))
            score = 0.0
            for token in overlap:
                # Bonus if token looks like a section (e.g. 66d, 318, 420)
                if any(char.isdigit() for char in token):
                    score += 2.0
                else:
                    score += 1.0

            # Normalize by query length
            score = score / (len(query_tokens) + 1e-5)
            if score > 0:
                results.append((score, doc))

        results.sort(key=lambda x: x[0], reverse=True)
        return [self._doc_to_retrieved_source(doc, score) for score, doc in results[:top_k]]

    def _doc_to_retrieved_source(self, doc: Dict[str, Any], score: float) -> RetrievedSource:
        """Converts internal document dictionary to standardized RetrievedSource."""
        source_id = doc.get("source_id", "")
        source_type = doc.get("source_type", "case" if "case_id" in doc else "statute")

        if source_type == "case":
            title = doc.get("court_name", "District Court Case")
            citation = f"{doc.get('court_name', '')} ({doc.get('year', '')}) - {doc.get('case_id', '')}"
            text = doc.get("fact_summary") or doc.get("embedding_text") or ""
            metadata = {
                "case_id": doc.get("case_id"),
                "court_name": doc.get("court_name"),
                "state": doc.get("state"),
                "district": doc.get("district"),
                "year": doc.get("year"),
                "crime_category": doc.get("crime_category"),
                "outcome": doc.get("outcome"),
                "statute_sections": doc.get("statute_sections", []),
                "keywords": doc.get("keywords", []),
                "url": doc.get("url"),
                "tid": doc.get("tid"),
            }
        else:
            title = doc.get("title") or f"{doc.get('act', '')} Section {doc.get('section', '')}"
            citation = f"{doc.get('act', '')} Section {doc.get('section', '')}"
            text = doc.get("text") or doc.get("explanation") or ""
            metadata = {
                "act": doc.get("act"),
                "section": doc.get("section"),
                "crime_category": doc.get("crime_category"),
                "keywords": doc.get("keywords", []),
                "explanation": doc.get("explanation"),
            }

        return RetrievedSource(
            source_id=source_id,
            source_type=source_type,
            title=title,
            citation=citation,
            text=text,
            metadata=metadata,
            relevance_score=score,
        )

    def save(self, filepath: str):
        """Save vector store state to a single JSON file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "documents": self.documents,
            "vectors": self.vectors.tolist() if self.vectors is not None else [],
            "_doc_id_map": self._doc_id_map,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info(f"Saved vector store ({len(self.documents)} docs) to {filepath}")

    def load(self, filepath: str):
        """Load vector store state from disk."""
        if not os.path.exists(filepath):
            logger.warning(f"Vector store file {filepath} not found.")
            return False

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.documents = data.get("documents", [])
        vec_list = data.get("vectors", [])
        self.vectors = np.array(vec_list, dtype=np.float32) if vec_list else None
        self._doc_id_map = data.get("_doc_id_map", {})
        logger.info(f"Loaded vector store ({len(self.documents)} docs) from {filepath}")
        return True
