"""
Reranker Module for LCC AI/Model Backend.
Re-scores retrieved candidate chunks for true semantic relevance before the drafter sees them.
Supports:
1. CrossEncoderReranker (using BAAI/bge-reranker-base or similar via sentence-transformers)
2. HeuristicLexicalReranker (fast, pure-Python lexical-semantic cross-matching)
"""

from __future__ import annotations
import os
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

from .schemas import RetrievedSource, RerankedCandidate

logger = logging.getLogger("lcc.reranker")


class BaseReranker(ABC):
    """Abstract interface for rerankers."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: List[RetrievedSource],
        top_n: int = 5,
    ) -> List[RerankedCandidate]:
        """Rerank candidates based on query relevance and return top_n."""
        pass


class CrossEncoderReranker(BaseReranker):
    """
    Reranker powered by sentence-transformers CrossEncoder.
    E.g. BAAI/bge-reranker-base.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        try:
            from sentence_transformers import CrossEncoder
            self.model_name = model_name
            self.model = CrossEncoder(model_name)
            logger.info(f"Loaded CrossEncoder reranker: {model_name}")
        except ImportError as e:
            raise ImportError(
                f"sentence-transformers is not installed in the environment ({e}). "
                f"To use neural reranking, run 'pip install sentence-transformers torch', "
                f"or use the zero-dependency HeuristicLexicalReranker."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Could not load CrossEncoder model '{model_name}': {e}") from e

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedSource],
        top_n: int = 5,
    ) -> List[RerankedCandidate]:
        if not candidates:
            return []

        pairs = [(query, f"{c.title}. {c.citation}. {c.text}") for c in candidates]
        raw_scores = self.model.predict(pairs)

        # Sigmoid normalization if scores are unbounded logits
        import numpy as np
        raw_array = np.atleast_1d(np.array(raw_scores, dtype=np.float32))
        scores = (1.0 / (1.0 + np.exp(-raw_array))).tolist()

        scored = list(zip(candidates, scores, strict=False))
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (cand, score) in enumerate(scored[:top_n], start=1):
            cand.relevance_score = float(round(score, 4))
            results.append(RerankedCandidate(
                source=cand,
                rerank_score=float(round(score, 4)),
                ranking=rank,
            ))
        return results


class HeuristicLexicalReranker(BaseReranker):
    """
    High-precision lexical-semantic cross-matcher.
    Re-scores candidates based on:
    - Stopword-filtered conceptual overlap
    - Domain legal concept clusters across the 5 shortlisted crime categories
    - Exact section/statute matches (e.g. 66D, 318, 420)
    - Prior dense/hybrid retrieval score
    """

    STOPWORDS = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by",
        "of", "from", "is", "was", "are", "were", "be", "been", "being", "have",
        "has", "had", "do", "does", "did", "my", "me", "i", "we", "you", "your",
        "he", "she", "it", "they", "them", "his", "her", "their", "into", "some",
        "someone", "something", "can", "could", "should", "would", "what", "how",
        "who", "which", "when", "where", "why", "overnight", "right", "now", "outside"
    }

    CONCEPT_CLUSTERS = {
        "cyber_fraud": [
            "customs", "impersonat", "digital arrest", "upi", "transfer", "scam",
            "phishing", "computer", "phone", "mule", "cyber", "otp", "66d", "deceiv"
        ],
        "theft_burglary": [
            "theft", "stolen", "burglary", "motorcycle", "bike", "vehicle", "car",
            "two-wheeler", "movable", "303", "379", "possession", "parked"
        ],
        "crimes_against_senior_citizens": [
            "senior", "elderly", "father", "mother", "parents", "maintenance",
            "gift", "deed", "property", "abandon", "reclaim", "amenities", "void", "23"
        ],
        "crimes_against_women": [
            "woman", "women", "female", "commute", "stalking", "following", "followed",
            "modesty", "assault", "criminal force", "harass", "outrage", "354"
        ],
        "cheating_forgery": [
            "forg", "fake", "appointment", "letter", "seal", "stamp", "railway",
            "cheat", "deceiv", "induc", "420", "318", "468", "lakh", "rupees"
        ],
    }

    def __init__(self):
        logger.info("Using Calibrated HeuristicLexicalReranker.")

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedSource],
        top_n: int = 5,
    ) -> List[RerankedCandidate]:
        if not candidates:
            return []

        query_lower = query.lower()
        raw_words = re.findall(r"\b\w+\b", query_lower)
        query_words = set(w for w in raw_words if w not in self.STOPWORDS and len(w) > 2)
        query_sections = set(re.findall(r"\b\d+[a-zA-Z]?\b", query_lower))

        scored_candidates = []
        for cand in candidates:
            cand_text = f"{cand.title} {cand.citation} {cand.text} {' '.join(cand.metadata.get('keywords', []))}".lower()
            cand_raw_words = re.findall(r"\b\w+\b", cand_text)
            cand_words = set(w for w in cand_raw_words if w not in self.STOPWORDS and len(w) > 2)

            # 1. Base score from previous retriever stage
            base_score = cand.relevance_score

            # 2. Informative token overlap ratio
            if query_words:
                overlap = len(query_words.intersection(cand_words)) / len(query_words)
            else:
                overlap = 0.0

            # 3. Exact statute section bonus
            section_bonus = 0.15 if any(sec in cand_text for sec in query_sections) else 0.0

            # 4. Domain concept cluster matching with word boundaries
            cluster_match = False
            cluster_score = 0.0
            for terms in self.CONCEPT_CLUSTERS.values():
                q_has = any(re.search(r"\b" + re.escape(t) + r"\b", query_lower) for t in terms)
                c_has = any(re.search(r"\b" + re.escape(t) + r"\b", cand_text) for t in terms)
                if q_has and c_has:
                    cluster_match = True
                    common = sum(
                        1 for t in terms
                        if re.search(r"\b" + re.escape(t) + r"\b", query_lower)
                        and re.search(r"\b" + re.escape(t) + r"\b", cand_text)
                    )
                    cluster_score = max(cluster_score, min(0.30, 0.15 + common * 0.05))

            # Calibrated combined score
            if cluster_match:
                combined_score = (
                    (0.40 * base_score) +
                    (0.30 * overlap) +
                    cluster_score +
                    section_bonus +
                    0.15
                )
            else:
                combined_score = (
                    (0.35 * base_score) +
                    (0.25 * overlap) +
                    section_bonus
                )

            final_score = min(0.96, max(0.10, round(combined_score, 4)))
            scored_candidates.append((cand, final_score))

        # Sort descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (cand, score) in enumerate(scored_candidates[:top_n], start=1):
            cand.relevance_score = score
            results.append(RerankedCandidate(
                source=cand,
                rerank_score=score,
                ranking=rank,
            ))

        return results


def get_reranker(reranker_type: Optional[str] = None) -> BaseReranker:
    """Factory to load configured reranker."""
    val = reranker_type or os.getenv("LCC_RERANKER_TYPE", "auto")
    reranker_type = val.lower() if val is not None else "auto"

    if reranker_type == "cross_encoder":
        try:
            return CrossEncoderReranker()
        except Exception as e:
            logger.warning(f"Failed to load CrossEncoder ({e}). Falling back to HeuristicLexicalReranker.")
            return HeuristicLexicalReranker()

    # 'auto' or 'heuristic'
    try:
        if reranker_type == "auto":
            # Check if sentence-transformers is available and user didn't disable it
            import sentence_transformers
            return CrossEncoderReranker()
    except Exception:
        pass

    return HeuristicLexicalReranker()
