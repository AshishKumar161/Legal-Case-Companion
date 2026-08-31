import datetime
import logging
import re
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.legal_authority import LegalSource, LegalSourceVersion
from app.schemas.legal_authority import (
    LegalAuthoritySearchRequest,
    LegalAuthoritySearchResponse,
    RetrievedLegalAuthority,
)
from app.schemas.search import SearchMode
from app.services.citation_normalizer import LegalCitationNormalizer
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import cosine_similarity

logger = logging.getLogger(__name__)


class LegalAuthorityRetrievalService:
    """Service for searching, retrieving, and ranking authoritative Indian legal materials

    (statutes, rules, and binding judicial precedents) independently from case evidence.
    """

    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    def search_legal_authorities(
        self, req: LegalAuthoritySearchRequest
    ) -> LegalAuthoritySearchResponse:
        """Searches authoritative Indian legal provisions and judgments with

        exact citation recognition, temporal validity filtering, jurisdiction filtering, and authority ranking.
        """
        # 1. Base query joining versions and active sources
        query = (
            self.db.query(LegalSourceVersion, LegalSource)
            .join(LegalSource, LegalSourceVersion.source_id == LegalSource.id)
            .filter(LegalSource.is_active.is_(True))
        )

        # 2. Jurisdiction filter
        if req.jurisdiction:
            jurisdiction_upper = req.jurisdiction.upper()
            query = query.filter(
                or_(
                    LegalSource.jurisdiction == jurisdiction_upper,
                    LegalSource.jurisdiction == "INDIA_CENTRAL",
                    LegalSource.jurisdiction == "ALL_INDIA",
                )
            )

        # 3. Source type filter
        if req.source_type:
            query = query.filter(LegalSource.source_type == req.source_type)

        # 4. Minimum authority level filter
        if req.min_authority_level is not None:
            query = query.filter(LegalSource.authority_level >= req.min_authority_level)

        # 5. Temporal validity filter
        if req.effective_at:
            cutoff: datetime.date = req.effective_at
            query = query.filter(
                and_(
                    or_(
                        LegalSourceVersion.effective_from.is_(None),
                        LegalSourceVersion.effective_from <= cutoff,
                    ),
                    or_(
                        LegalSourceVersion.effective_to.is_(None),
                        LegalSourceVersion.effective_to >= cutoff,
                    ),
                )
            )
        else:
            # Default to current versions if no temporal cutoff specified
            query = query.filter(LegalSourceVersion.is_current.is_(True))

        prov_source_pairs = query.all()
        if not prov_source_pairs:
            return LegalAuthoritySearchResponse(
                query=req.query,
                search_mode=req.search_mode.value,
                total_results=0,
                results=[],
            )

        # 6. Citation Normalization & Query Intent
        normalized_citations = LegalCitationNormalizer.extract_all_citations(req.query)
        detected_sections = [c.section_or_article.replace("Section ", "").replace("Article ", "").strip().upper() for c in normalized_citations if c.section_or_article]
        detected_acts = [c.act_or_court.lower() for c in normalized_citations if c.act_or_court]

        # 7. Semantic Embeddings for Query
        semantic_scores: dict[UUID, float] = {}
        if req.search_mode in (SearchMode.SEMANTIC, SearchMode.HYBRID):
            try:
                embeddings = self.embedding_service.generate_embeddings([req.query])
                if embeddings:
                    query_vec = embeddings[0]
                    for prov, _ in prov_source_pairs:
                        if prov.embedding:
                            semantic_scores[prov.id] = cosine_similarity(query_vec, prov.embedding)
            except Exception as emb_err:  # noqa: BLE001
                logger.warning("Embedding generation failed during legal authority retrieval: %s", emb_err)

        # 8. Compute Lexical, Semantic, and Authority Ranking Scores
        alpha = getattr(settings, "HYBRID_SEARCH_ALPHA", 0.6)
        scored_results: list[RetrievedLegalAuthority] = []

        for prov, source in prov_source_pairs:
            # Lexical score
            lex_score = self._compute_authority_lexical_score(req.query, prov, source)
            sem_score = semantic_scores.get(prov.id)

            if req.search_mode == SearchMode.LEXICAL:
                base_score = lex_score
            elif req.search_mode == SearchMode.SEMANTIC:
                base_score = sem_score if sem_score is not None else 0.0
            else:  # HYBRID
                if sem_score is not None:
                    base_score = (alpha * sem_score) + ((1.0 - alpha) * lex_score)
                else:
                    base_score = lex_score

            # Citation Match Boost: Direct match on section/article
            citation_boost = 0.0
            p_sec_clean = prov.section_number.strip().upper()
            if any(sec == p_sec_clean for sec in detected_sections):
                citation_boost += 0.35
            if any(act in source.name.lower() or (source.short_title and act in source.short_title.lower()) for act in detected_acts):
                citation_boost += 0.25

            # Authority Level Weighting (e.g. Primary Statute 90 -> 0.09 bonus, Subordinate 60 -> 0.06 bonus)
            authority_weight = (source.authority_level / 1000.0)

            final_score = min(1.0, max(0.0, base_score + citation_boost + authority_weight))

            min_score = req.min_score if req.min_score is not None else 0.05
            if final_score < min_score:
                continue

            scored_results.append(
                RetrievedLegalAuthority(
                    source_id=source.id,
                    version_id=prov.id,
                    canonical_identifier=source.canonical_identifier,
                    canonical_provision_id=prov.canonical_provision_id,
                    name=source.name,
                    short_title=source.short_title,
                    section_number=prov.section_number,
                    version_label=prov.version_label,
                    title=prov.title,
                    content=prov.content,
                    source_type=source.source_type,
                    authority_level=source.authority_level,
                    jurisdiction=source.jurisdiction,
                    citation_standard=source.citation_standard,
                    effective_from=prov.effective_from,
                    effective_to=prov.effective_to,
                    is_current=prov.is_current,
                    score=round(final_score, 4),
                    lexical_score=round(lex_score, 4) if lex_score is not None else None,
                    semantic_score=round(sem_score, 4) if sem_score is not None else None,
                    metadata_=prov.metadata_,
                )
            )

        # 9. Sort by final score descending
        scored_results.sort(key=lambda x: x.score, reverse=True)
        top_results = scored_results[: req.top_k]

        return LegalAuthoritySearchResponse(
            query=req.query,
            search_mode=req.search_mode.value,
            total_results=len(top_results),
            results=top_results,
        )

    def _compute_authority_lexical_score(
        self, query: str, prov: LegalSourceVersion, source: LegalSource
    ) -> float:
        combined_text = f"{source.name} {source.short_title or ''} Section {prov.section_number} {prov.title} {prov.content}".lower()
        q_clean = query.strip().lower()

        # 1. Exact query match in text
        if q_clean in combined_text:
            return 1.0

        # 2. Content token overlap
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

        t_tokens = set(re.findall(r"\w+", combined_text))
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

        # 3. Exact Section / Title matching bonus
        sec_bonus = 0.0
        if f"section {prov.section_number.lower()}" in q_clean or f"sec {prov.section_number.lower()}" in q_clean:
            sec_bonus = 0.3

        return min(1.0, (0.7 * token_ratio) + sec_bonus)
