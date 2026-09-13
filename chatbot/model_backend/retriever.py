"""
Retriever Module for LCC AI/Model Backend.
Implements hybrid retrieval:
1. Dense semantic search via vector embeddings
2. Sparse keyword matching (especially critical for statutory sections e.g. 66D, 318, 420)
3. Reciprocal Rank Fusion (RRF) to merge candidate lists without score scaling bias

Guarantees:
- Returns real source IDs and full metadata.
- NEVER fabricates or synthesizes hallucinated source citations.
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .schemas import RetrievedSource
from .vector_store import BaseVectorStore
from .embeddings import BaseEmbeddings

logger = logging.getLogger("lcc.retriever")


class HybridRetriever:
    """
    Hybrid retriever combining dense vector similarity and sparse lexical matching.
    Queries both case law and statutory knowledge stores.
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_model: BaseEmbeddings,
        alpha: float = 0.5,        # Weight between dense (alpha) and sparse (1-alpha)
        rrf_k: int = 60,           # Reciprocal Rank Fusion constant
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.alpha = alpha
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        category_filter: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> List[RetrievedSource]:
        """
        Execute hybrid retrieval for a given query text.
        Applies Reciprocal Rank Fusion to synthesize dense and sparse hit lists.
        """
        filters: Dict[str, Any] = {}
        if category_filter and category_filter not in ("uncategorized", "other"):
            filters["crime_category"] = category_filter
        if source_type:
            filters["source_type"] = source_type

        # 1. Dense Semantic Retrieval
        query_vec = self.embedding_model.embed_query(query)
        dense_hits = self.vector_store.search_by_vector(
            query_vector=query_vec,
            top_k=top_k * 2,
            filters=filters or None,
        )

        # 2. Sparse Keyword Retrieval
        raw_keyword_hits = self.vector_store.search_by_keyword(
            query_text=query,
            top_k=top_k * 2,
            filters=filters or None,
        )

        # Filter out zero or noise relevance hits
        dense_hits = [h for h in dense_hits if h.relevance_score > 0.08]
        keyword_hits = [h for h in raw_keyword_hits if h.relevance_score > 0.0]

        if not dense_hits and not keyword_hits:
            return []

        # 3. Score-Weighted Reciprocal Rank Fusion (RRF)
        # score(d) = sum_{m in models} weight_m * score_m * (1 / (k + rank_m(d)))
        rrf_scores: Dict[str, float] = defaultdict(float)
        sources_by_id: Dict[str, RetrievedSource] = {}

        for rank, hit in enumerate(dense_hits):
            score_weight = min(1.0, max(0.1, hit.relevance_score))
            rrf_scores[hit.source_id] += self.alpha * score_weight * (1.0 / (self.rrf_k + rank + 1))
            sources_by_id[hit.source_id] = hit

        for rank, hit in enumerate(keyword_hits):
            score_weight = min(1.0, max(0.1, hit.relevance_score))
            rrf_scores[hit.source_id] += (1.0 - self.alpha) * score_weight * (1.0 / (self.rrf_k + rank + 1))
            if hit.source_id not in sources_by_id:
                sources_by_id[hit.source_id] = hit

        # Sort combined results by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda sid: rrf_scores[sid], reverse=True)

        merged_results: List[RetrievedSource] = []
        for sid in sorted_ids[:top_k]:
            source = sources_by_id[sid]
            # Normalize RRF score to 0.0 - 1.0 range
            norm_score = min(1.0, rrf_scores[sid] * (self.rrf_k + 1))
            source.relevance_score = round(norm_score, 4)
            merged_results.append(source)

        logger.info(
            f"Retrieved {len(merged_results)} hybrid sources for query '{query[:40]}...'. "
            f"Dense hits: {len(dense_hits)}, Keyword hits: {len(keyword_hits)}"
        )
        return merged_results

    def retrieve_multi_query(
        self,
        queries: List[str],
        top_k: int = 6,
        category_filter: Optional[str] = None,
    ) -> List[RetrievedSource]:
        """
        Execute multi-query retrieval across expanded legal search queries.
        Deduplicates sources across queries while accumulating relevance signals.
        """
        all_hits: Dict[str, RetrievedSource] = {}
        hit_counts: Dict[str, int] = defaultdict(int)

        for q in queries:
            hits = self.retrieve(q, top_k=top_k, category_filter=category_filter)
            for h in hits:
                hit_counts[h.source_id] += 1
                if h.source_id not in all_hits or h.relevance_score > all_hits[h.source_id].relevance_score:
                    all_hits[h.source_id] = h

        # Boost items retrieved by multiple queries
        for sid, count in hit_counts.items():
            if count > 1:
                boost = 1.0 + (count - 1) * 0.15
                all_hits[sid].relevance_score = min(1.0, round(all_hits[sid].relevance_score * boost, 4))

        sorted_results = sorted(all_hits.values(), key=lambda s: s.relevance_score, reverse=True)
        return sorted_results[:top_k]
