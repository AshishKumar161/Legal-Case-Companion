"""
Pipeline Module for LCC AI/Model Backend.
Implements the end-to-end agentic architecture:
Safety Check -> Intake -> Legal Reasoner -> Hybrid Retrieve -> Rerank -> Draft -> Verify -> Escalate

Exposes the clean Python interface:
    assistant = LegalAssistant()
    response = assistant.ask("Someone called pretending to be a customs officer...")
"""

from __future__ import annotations
import os
import re
import logging
from typing import List, Dict, Any, Optional

from .schemas import (
    LegalAssistantResponse,
    IntakeResult,
    LegalReasoningResult,
    RetrievedSource,
    RerankedCandidate,
    GeneratedAnswer,
    VerificationResult,
    SafetyCheckResult,
)
from .prompts import LEGAL_DISCLAIMER, PERSONALIZED_REPLIES_BY_CATEGORY
from .llama_model import LLaMAModel, LLaMAConfig
from .embeddings import BaseEmbeddings, get_embedding_model
from .vector_store import BaseVectorStore, LocalVectorStore
from .retriever import HybridRetriever
from .reranker import BaseReranker, get_reranker
from .intake import IntakeAgent
from .legal_reasoner import LegalReasoner
from .answer_generator import AnswerGenerator
from .verifier import IndependentVerifier
from .safety import SafetyGuard
from .dataset_loader import load_and_index_default_data

logger = logging.getLogger("lcc.pipeline")


class PipelineConfig:
    """
    Configuration parameters for the LegalAssistant pipeline.
    Thresholds and model parameters can be configured or tuned via eval harness.
    """
    def __init__(
        self,
        confidence_threshold: float = 0.75,
        min_retrieval_score: float = 0.20,
        min_grounding_score: float = 0.70,
        min_citation_validity: float = 0.85,
        top_k_retrieve: int = 6,
        top_n_rerank: int = 4,
        llama_config: Optional[LLaMAConfig] = None,
        embedding_type: Optional[str] = None,
        reranker_type: Optional[str] = None,
        data_dir: Optional[str] = None,
        auto_index: bool = True,
    ):
        # Configurable confidence threshold (must be tuned using eval.py dataset)
        self.confidence_threshold = confidence_threshold
        self.min_retrieval_score = min_retrieval_score
        self.min_grounding_score = min_grounding_score
        self.min_citation_validity = min_citation_validity
        self.top_k_retrieve = top_k_retrieve
        self.top_n_rerank = top_n_rerank

        self.llama_config = llama_config or LLaMAConfig()
        self.embedding_type = embedding_type
        self.reranker_type = reranker_type
        self.data_dir = data_dir
        self.auto_index = auto_index


class LegalAssistant:
    """
    AI-Powered Legal Assistant Engine.
    Exposes a unified Python interface for general legal information, case similarity,
    statutory explanation, next steps guidance, and escalation gating.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()

        # 1. Model & Embedding Layer
        self.llm = LLaMAModel(self.config.llama_config)
        self.embeddings: BaseEmbeddings = get_embedding_model(self.config.embedding_type)

        # 2. Vector Store & Indexing
        self.vector_store: BaseVectorStore = LocalVectorStore(embedding_model=self.embeddings)

        # 3. Retrieval & Reranking Layer
        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            embedding_model=self.embeddings,
        )
        self.reranker: BaseReranker = get_reranker(self.config.reranker_type)

        # 4. Cognitive Reasoning & Audit Nodes
        self.safety_guard = SafetyGuard()
        self.intake_agent = IntakeAgent(self.llm)
        self.legal_reasoner = LegalReasoner(self.llm)
        self.answer_generator = AnswerGenerator(self.llm)
        self.verifier = IndependentVerifier(self.llm)

        # 5. Auto-index dataset if requested
        if self.config.auto_index:
            raw_dir = self.config.data_dir or self._discover_raw_cases_dir()
            load_and_index_default_data(self.vector_store, raw_dir=raw_dir)

    def _discover_raw_cases_dir(self) -> Optional[str]:
        """Locates raw_cases directory if present in working directory or package."""
        candidates = [
            "raw_cases",
            "../raw_cases",
            "lcc_starter/raw_cases",
            os.path.join(os.path.dirname(__file__), "..", "raw_cases"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return None

    def index_dataset(self, raw_dir: Optional[str] = None):
        """Manually trigger case and statute indexing."""
        load_and_index_default_data(self.vector_store, raw_dir=raw_dir)

    def ask(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> LegalAssistantResponse:
        """
        Main entry point. Executes the full 11-step pipeline:
        1. Safety Check
        2. Intake & Fact Extraction
        3. Legal Issue Identification
        4. Query Transformation
        5. Hybrid Retrieval
        6. Reranking
        7. Grounded Answer Generation
        8. Independent Verification
        9. Calibrated Confidence Calculation
        10. Escalation Gate
        11. Structured Response Delivery
        """
        logger.info(f"Processing query: '{query[:60]}...'")

        # -------------------------------------------------------------
        # Stage 1: Safety Check
        # -------------------------------------------------------------
        safety_result: SafetyCheckResult = self.safety_guard.check_query_safety(query)
        if not safety_result.is_safe:
            logger.warning(f"Safety violation flagged: {safety_result.violation_category}")
            return self.safety_guard.create_safety_fallback_response(safety_result)

        # -------------------------------------------------------------
        # Stage 1.5: Greeting / Small Talk Short-Circuit
        # -------------------------------------------------------------
        if self.safety_guard.is_greeting_only(query):
            return self.safety_guard.create_greeting_response()

        # -------------------------------------------------------------
        # Stage 2: Intake & Fact Extraction
        # -------------------------------------------------------------
        intake_result: IntakeResult = self.intake_agent.process(
            query=query,
            conversation_history=conversation_history,
        )

        if intake_result.needs_clarification:
            cat = intake_result.detected_category
            pers_reply = PERSONALIZED_REPLIES_BY_CATEGORY.get(cat)
            if pers_reply:
                intake_result.clarification_questions = [pers_reply]

        # -------------------------------------------------------------
        # Stage 2.5: Conversational Bypass
        # -------------------------------------------------------------
        if getattr(intake_result, "is_conversational", False):
            logger.info("Conversational query detected, bypassing legal retrieval.")
            prompt = f"The user said: '{query}'. Respond formally, politely, and briefly as Lex, a Legal AI Advisor. Do not give legal advice. If it is a greeting, greet them back and ask how you can help with their legal issue."
            sys_prompt = "You are Lex, a formal Legal AI Advisor. Provide a polite, professional, and helpful response."
            response_text = self.llm.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.3, json_mode=False)
            
            return LegalAssistantResponse(
                answer=response_text,
                legal_issue=[],
                relevant_law=[],
                possible_next_steps=[],
                documents_or_information=[],
                similar_cases=[],
                sources=[],
                confidence=1.0,
                verified=True,
                needs_professional_help=False,
                escalated=False,
                clarification_needed=False,
                clarification_questions=[]
            )

        # -------------------------------------------------------------
        # Stage 3 & 4: Legal Reasoning & Search Query Expansion
        # -------------------------------------------------------------
        reasoning_result: LegalReasoningResult = self.legal_reasoner.analyze(intake_result)

        # -------------------------------------------------------------
        # Stage 5: Hybrid Retrieval (Dense + Sparse with RRF)
        # -------------------------------------------------------------
        retrieval_queries = reasoning_result.search_queries
        if intake_result.clarified_facts not in retrieval_queries:
            retrieval_queries.append(intake_result.clarified_facts)

        retrieved_sources: List[RetrievedSource] = self.retriever.retrieve_multi_query(
            queries=retrieval_queries,
            top_k=self.config.top_k_retrieve,
            category_filter=intake_result.detected_category,
        )

        # Evidence Sufficiency Gate: If no sources were found or relevance is below threshold, refuse to guess
        max_score = max((s.relevance_score for s in retrieved_sources), default=0.0)
        if not retrieved_sources or max_score < self.config.min_retrieval_score:
            logger.info(
                f"Insufficient retrieval evidence (max score {max_score:.4f} < {self.config.min_retrieval_score}). "
                "Triggering safe insufficient evidence fallback."
            )
            # Use LLM to write a polite contextual response instead of a rigid fallback
            sys_prompt = "You are Lex, a formal Legal AI Advisor."
            prompt = f"The user queried: '{query}'. However, you could not find any specific laws or cases in your database to answer this accurately. Respond formally and politely, stating that you need more context or that they should consult a human advocate, as you cannot verify the legal information for this specific query. Do not give legal advice."
            response_text = self.llm.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.3, json_mode=False)
            
            return LegalAssistantResponse(
                answer=f"{response_text}\n\n---\n{LEGAL_DISCLAIMER}",
                legal_issue=["Unverified / Insufficient Evidence"],
                relevant_law=[],
                possible_next_steps=[
                    "Consult a licensed advocate specializing in the relevant jurisdiction.",
                    "Provide more specific details about the situation."
                ],
                documents_or_information=[],
                similar_cases=[],
                sources=[],
                confidence=0.25,
                verified=False,
                needs_professional_help=True,
                escalated=True,
                clarification_needed=True,
                clarification_questions=["Could you please provide more context about your situation?"]
            )

        # -------------------------------------------------------------
        # Stage 6: Reranking (Cross-encoder / Heuristic)
        # -------------------------------------------------------------
        reranked_candidates: List[RerankedCandidate] = self.reranker.rerank(
            query=intake_result.clarified_facts,
            candidates=retrieved_sources,
            top_n=self.config.top_n_rerank,
        )

        # -------------------------------------------------------------
        # Stage 7: Grounded Answer Generation (Drafter)
        # -------------------------------------------------------------
        draft_answer: GeneratedAnswer = self.answer_generator.generate(
            intake_result=intake_result,
            reasoning_result=reasoning_result,
            reranked_candidates=reranked_candidates,
        )

        # -------------------------------------------------------------
        # Stage 8: Independent Verification (Critic)
        # -------------------------------------------------------------
        verification: VerificationResult = self.verifier.verify(
            generated_answer=draft_answer,
            reranked_candidates=reranked_candidates,
        )

        # -------------------------------------------------------------
        # Stage 9: Calibrated Confidence Calculation
        # -------------------------------------------------------------
        # Confidence integrates:
        # - Verifier Grounding Score (55%)
        # - Citation Validity Score (25%)
        # - Relevance of Primary Supporting Evidence (20%)
        all_cited_ids = set(draft_answer.cited_source_ids)
        inline_tags = set(re.findall(r"\[(stat:[^\]]+|case:[^\]]+|doc-[^\]]+)\]", draft_answer.raw_answer_text))
        active_cited_ids = all_cited_ids.union(inline_tags)

        cited_cands = [
            c for c in reranked_candidates
            if c.source.source_id in active_cited_ids
        ]
        active_candidates = cited_cands if cited_cands else reranked_candidates[:2]

        # Rank-weighted evidence relevance (emphasizing primary cited authority)
        if len(active_candidates) >= 2:
            evidence_score = (0.70 * active_candidates[0].rerank_score) + (0.30 * active_candidates[1].rerank_score)
        elif active_candidates:
            evidence_score = active_candidates[0].rerank_score
        else:
            evidence_score = 0.0

        raw_confidence = (
            (0.55 * verification.grounding_score) +
            (0.25 * verification.citation_validity_score) +
            (0.20 * evidence_score)
        )

        # Severe penalty if hallucination detected or citations are fabricated
        if verification.hallucination_detected or verification.citation_validity_score < 0.6:
            raw_confidence = min(raw_confidence, 0.35)

        confidence = round(float(min(1.0, max(0.1, raw_confidence))), 2)

        # -------------------------------------------------------------
        # Stage 10: Escalation Gate
        # -------------------------------------------------------------
        # An answer passes ONLY if confidence meets the configurable threshold,
        # verification succeeded, and no emergency/high-risk flags exist.
        should_escalate = (
            confidence < self.config.confidence_threshold
            or not verification.verified
            or safety_result.requires_immediate_advocate
        )

        final_answer_text = draft_answer.raw_answer_text
        if should_escalate:
            escalation_notice = (
                f"\n\n> [!NOTE]\n"
                f"> **Advocate Review Recommended**: The calibrated confidence score for this response is {confidence:.2f} "
                f"(below system threshold {self.config.confidence_threshold:.2f}) or involves complex legal nuances. "
                f"This matter has been flagged for in-person advocate review."
            )
            final_answer_text = final_answer_text + escalation_notice

        # -------------------------------------------------------------
        # Stage 11: Final Structured Response
        # -------------------------------------------------------------
        # Assemble sources payload
        sources_payload = [
            {
                "source_id": c.source.source_id,
                "type": c.source.source_type,
                "title": c.source.title,
                "citation": c.source.citation,
                "score": c.rerank_score,
            }
            for c in reranked_candidates
        ]

        # Extract structured fields
        legal_issue_list = [i.title for i in reasoning_result.possible_issues]
        relevant_law_list = draft_answer.relevant_laws_identified
        next_steps_list = draft_answer.possible_next_steps
        docs_list = draft_answer.documents_or_information
        similar_cases_list = draft_answer.similar_cases_mentioned

        return LegalAssistantResponse(
            answer=final_answer_text,
            legal_issue=legal_issue_list,
            relevant_law=relevant_law_list,
            possible_next_steps=next_steps_list,
            documents_or_information=docs_list,
            similar_cases=similar_cases_list,
            sources=sources_payload,
            confidence=confidence,
            verified=verification.verified,
            needs_professional_help=(should_escalate or safety_result.requires_immediate_advocate),
            escalated=should_escalate,
            clarification_needed=intake_result.needs_clarification,
            clarification_questions=intake_result.clarification_questions,
        )
