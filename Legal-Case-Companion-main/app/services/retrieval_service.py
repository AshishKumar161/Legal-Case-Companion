import logging
import math
import re
import uuid

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.authorization import authorize_case_access
from app.core.config import settings
from app.models.ai import DocumentChunk
from app.models.case import Case
from app.models.document import Document, DocumentSecurityStatus
from app.models.user import User
from app.schemas.ai import AIResearchRequest
from app.schemas.retrieval import RetrievedChunk
from app.schemas.search import (
    CaseSearchRequest,
    CaseSearchResponse,
    RetrievedEvidence,
    SearchMode,
)
from app.services.case_service import CaseService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: list[float] | None, vec2: list[float] | None) -> float:
    """Calculates cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    similarity = dot_product / (norm_a * norm_b)
    # Clamp to [0.0, 1.0] for normalized embeddings
    return max(0.0, min(1.0, similarity))


class RetrievalService:
    def __init__(self, db: Session):
        self.db = db
        self.case_service = CaseService(db)
        self.embedding_service = EmbeddingService()

    def search_case_evidence(
        self, user: User, case_id: uuid.UUID, req: CaseSearchRequest
    ) -> CaseSearchResponse:
        """Executes case-scoped hybrid, semantic, or lexical search across active SAFE document chunks.

        Enforces strict authorization, version isolation, and source provenance.
        """
        # 1. Strict Resource-Level Authorization
        authorize_case_access(self.db, user, case_id)

        # 2. Case-Scoped SQL Query (Defence in depth, never search globally)
        query = (
            self.db.query(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(Case, DocumentChunk.case_id == Case.id)
            .filter(
                and_(
                    DocumentChunk.case_id == case_id,
                    DocumentChunk.deleted_at.is_(None),
                    Document.deleted_at.is_(None),
                    Document.security_status == DocumentSecurityStatus.SAFE,
                    Case.deleted_at.is_(None),
                    Case.id == case_id,
                )
            )
        )

        # Optional filters
        if req.document_category:
            query = query.filter(Document.document_type == req.document_category)

        if req.document_id:
            query = query.filter(Document.id == req.document_id)

        chunk_doc_pairs = query.all()

        if not chunk_doc_pairs:
            return CaseSearchResponse(
                query=req.query,
                search_mode=req.search_mode.value,
                total_results=0,
                results=[],
            )

        # 3. Generate query embeddings if semantic / hybrid mode is active
        semantic_scores: dict[uuid.UUID, float] = {}
        if req.search_mode in (SearchMode.SEMANTIC, SearchMode.HYBRID):
            try:
                query_embeddings = self.embedding_service.generate_embeddings([req.query])
                if query_embeddings:
                    query_vec = query_embeddings[0]
                    for chunk, _ in chunk_doc_pairs:
                        if chunk.embedding:
                            semantic_scores[chunk.id] = cosine_similarity(query_vec, chunk.embedding)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Embedding generation failed during search for case {case_id}: {e}")

        # 4. Compute lexical scores and hybrid fusion
        alpha = getattr(settings, "HYBRID_SEARCH_ALPHA", 0.6)
        scored_candidates: list[RetrievedEvidence] = []

        for chunk, doc in chunk_doc_pairs:
            # Version isolation guard: Ensure chunk version matches active document version
            chunk_version = (
                chunk.metadata_.get("document_version")
                if chunk.metadata_ and isinstance(chunk.metadata_, dict)
                else doc.version
            )
            if chunk_version != doc.version:
                continue

            lex_score = self._compute_lexical_score(req.query, chunk.content)
            sem_score = semantic_scores.get(chunk.id)

            # Determine final score based on search mode
            if req.search_mode == SearchMode.LEXICAL:
                final_score = lex_score
            elif req.search_mode == SearchMode.SEMANTIC:
                final_score = sem_score if sem_score is not None else 0.0
            else:  # HYBRID
                if sem_score is not None:
                    final_score = (alpha * sem_score) + ((1.0 - alpha) * lex_score)
                else:
                    final_score = lex_score

            # Filter by threshold if requested
            min_score = req.min_score if req.min_score is not None else 0.05
            if final_score < min_score:
                continue

            # Provenance metadata extraction
            meta = chunk.metadata_ or {}
            page_start = meta.get("page_start", meta.get("page_number", 1))
            page_end = meta.get("page_end", page_start)
            doc_category_val = (
                doc.document_type.value
                if hasattr(doc.document_type, "value")
                else str(doc.document_type)
            )

            scored_candidates.append(
                RetrievedEvidence(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    case_id=case_id,
                    document_version=doc.version,
                    document_category=doc_category_val,
                    source_filename=doc.filename,
                    page_start=page_start,
                    page_end=page_end,
                    content=chunk.content,
                    score=round(final_score, 4),
                    lexical_score=round(lex_score, 4) if lex_score is not None else None,
                    semantic_score=round(sem_score, 4) if sem_score is not None else None,
                    metadata=meta,
                )
            )

        # 5. Sort candidates by score descending and slice top_k
        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        top_results = scored_candidates[: req.top_k]

        return CaseSearchResponse(
            query=req.query,
            search_mode=req.search_mode.value,
            total_results=len(top_results),
            results=top_results,
        )

    def _compute_lexical_score(self, query: str, text: str) -> float:
        """Computes a normalized lexical relevance score between query and document text.

        Accounts for exact phrase matching, content token coverage, and legal references.
        """
        if not query or not text:
            return 0.0

        q_clean = query.strip().lower()
        t_clean = text.strip().lower()

        # 1. Exact full query substring match
        if q_clean in t_clean:
            return 1.0

        # 2. Token overlap with stop word filtering and root prefix matching
        stop_words = {
            "what", "is", "the", "in", "of", "and", "to", "for", "a", "an",
            "under", "by", "on", "shall", "be", "this", "that", "it", "with",
            "as", "at", "from", "are", "was", "were", "does", "did", "how",
        }
        all_q_tokens = [w for w in re.findall(r"\w+", q_clean) if len(w) > 1]
        content_q_tokens = [w for w in all_q_tokens if w not in stop_words]
        q_tokens = content_q_tokens if content_q_tokens else all_q_tokens

        if not q_tokens:
            return 0.0

        t_tokens = set(re.findall(r"\w+", t_clean))
        matched_score = 0.0
        for qw in q_tokens:
            if qw in t_tokens:
                matched_score += 1.0
            elif any(
                (tw.startswith(qw[:5]) or qw.startswith(tw[:5]))
                for tw in t_tokens
                if len(tw) >= 5 and len(qw) >= 5
            ):
                matched_score += 0.8

        token_ratio = min(1.0, matched_score / len(q_tokens))

        # 3. Multi-word phrase matching bonus
        phrase_bonus = 0.0
        if len(all_q_tokens) > 1:
            for i in range(len(all_q_tokens) - 1):
                two_word_phrase = f"{all_q_tokens[i]} {all_q_tokens[i+1]}"
                if two_word_phrase in t_clean:
                    phrase_bonus += 0.2

        # 4. Legal citation and reference patterns (Section, Order, Rule, Act, Date, Amounts)
        legal_patterns = [
            r"section\s+\d+",
            r"order\s+\d+",
            r"rule\s+\d+",
            r"article\s+\d+",
            r"fir\s+no\.?\s*\d+",
            r"wp\(c\)\s*\d+",
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            r"rs\.?\s*\d+",
            r"inr\s*\d+",
        ]
        legal_bonus = 0.0
        for pattern in legal_patterns:
            matches = re.findall(pattern, q_clean)
            for m in matches:
                if m in t_clean:
                    legal_bonus += 0.25

        score = (0.7 * token_ratio) + phrase_bonus + legal_bonus
        return min(1.0, max(0.0, score))

    def retrieve_evidence(
        self, user: User, case_id: uuid.UUID, req: AIResearchRequest
    ) -> list[RetrievedChunk]:
        """Legacy helper for AI Research endpoint."""
        search_req = CaseSearchRequest(
            query=req.query,
            top_k=settings.RETRIEVAL_TOP_K,
            search_mode=SearchMode.HYBRID,
            min_score=settings.RETRIEVAL_SIMILARITY_THRESHOLD,
        )
        resp = self.search_case_evidence(user, case_id, search_req)
        return [
            RetrievedChunk(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                case_id=r.case_id,
                content=r.content,
                score=r.score,
                source_metadata=r.metadata,
            )
            for r in resp.results
        ]
