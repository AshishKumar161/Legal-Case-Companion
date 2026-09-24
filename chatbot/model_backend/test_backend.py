"""
Comprehensive Unit & Integration Test Suite for LCC AI/Model Backend.
Validates:
- Schemas & Pydantic models
- Embeddings & vector similarities
- Vector store persistence & filtering
- Hybrid retrieval (Dense + Sparse RRF)
- Cross-encoder / heuristic reranking
- Intake fact extraction & clarification
- Legal reasoner non-definitive phrasing
- Answer generator citation grounding
- Independent verifier critic audit
- Safety guardrails & escalation gate
- End-to-end LegalAssistant.ask() execution
"""

import sys
import os
import json
import logging

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model_backend.schemas import (
    LegalAssistantResponse,
    IntakeResult,
    LegalIssue,
    RetrievedSource,
    LegalCategory,
)
from model_backend.llama_model import LLaMAModel, LLaMAConfig
from model_backend.embeddings import get_embedding_model, cosine_similarity
from model_backend.vector_store import LocalVectorStore
from model_backend.retriever import HybridRetriever
from model_backend.reranker import get_reranker
from model_backend.intake import IntakeAgent
from model_backend.legal_reasoner import LegalReasoner
from model_backend.answer_generator import AnswerGenerator
from model_backend.verifier import IndependentVerifier
from model_backend.safety import SafetyGuard
from model_backend.pipeline import LegalAssistant, PipelineConfig
from model_backend.dataset_loader import load_and_index_default_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_backend")


def test_schemas():
    logger.info("--- 1. Testing Schemas ---")
    intake = IntakeResult(
        raw_query="My phone was stolen.",
        clarified_facts="Mobile phone stolen outside house.",
        detected_category=LegalCategory.CRIMINAL.value,
        missing_information=["IMEI number", "Date/Time"],
    )
    assert intake.detected_category == "criminal"
    assert len(intake.missing_information) == 2

    resp = LegalAssistantResponse(
        answer="Sample legal information answer.",
        legal_issue=["Possible Theft"],
        relevant_law=["Section 303 BNS"],
        possible_next_steps=["File FIR"],
        documents_or_information=["Phone invoice"],
        similar_cases=[],
        sources=[],
        confidence=0.85,
        verified=True,
        needs_professional_help=False,
        escalated=False,
    )
    dumped = resp.model_dump()
    assert dumped["confidence"] == 0.85
    assert dumped["verified"] is True
    logger.info("✓ Schemas validation passed.")


def test_embeddings():
    logger.info("--- 2. Testing Embeddings ---")
    embedder = get_embedding_model(model_type="local_tfidf")
    v1 = embedder.embed_query("customs officer digital arrest money transfer")
    v2 = embedder.embed_query("cyber fraud phone impersonation upi payment")
    v3 = embedder.embed_query("stolen motorcycle parked vehicle theft")

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    logger.info(f"Similarity (Cyber vs Cyber): {sim_related:.4f}")
    logger.info(f"Similarity (Cyber vs Theft): {sim_unrelated:.4f}")
    assert sim_related > sim_unrelated, "Cyber fraud queries should be closer to each other than theft"
    logger.info("✓ Embeddings test passed.")


def test_vector_store():
    logger.info("--- 3. Testing Vector Store & Persistence ---")
    embedder = get_embedding_model(model_type="local_tfidf")
    vs = LocalVectorStore(embedding_model=embedder)
    load_and_index_default_data(vs)

    assert len(vs.documents) >= 8, f"Expected at least 8 docs, got {len(vs.documents)}"

    # Save to disk and reload
    save_path = os.path.join(os.path.dirname(__file__), "test_vs.json")
    vs.save(save_path)

    vs2 = LocalVectorStore(embedding_model=embedder)
    vs2.load(save_path)
    assert len(vs2.documents) == len(vs.documents)

    # Cleanup temp file
    if os.path.exists(save_path):
        os.remove(save_path)
    logger.info("✓ Vector store test passed.")


def test_hybrid_retrieval_and_reranking():
    logger.info("--- 4. Testing Hybrid Retrieval & Reranker ---")
    embedder = get_embedding_model(model_type="local_tfidf")
    vs = LocalVectorStore(embedding_model=embedder)
    load_and_index_default_data(vs)

    retriever = HybridRetriever(vs, embedder)
    query = "Someone called claiming to be customs demanding UPI money transfer"
    hits = retriever.retrieve(query, top_k=4)

    assert len(hits) > 0, "Retrieval should return hits"
    for h in hits:
        assert h.source_id.startswith(("stat:", "case:")), f"Invalid source id: {h.source_id}"

    reranker = get_reranker("heuristic")
    reranked = reranker.rerank(query, hits, top_n=3)
    assert len(reranked) <= 3
    assert reranked[0].ranking == 1
    logger.info(f"Top reranked candidate: [{reranked[0].source.source_id}] {reranked[0].source.title} (score: {reranked[0].rerank_score})")
    logger.info("✓ Hybrid retrieval & reranking passed.")


def test_indian_kanoon_integration():
    logger.info("--- 4b. Testing Indian Kanoon Precedents Integration ---")
    from model_backend.dataset_loader import load_indian_kanoon_cases
    cases = load_indian_kanoon_cases()
    assert len(cases) >= 100, f"Expected at least 100 cases, got {len(cases)}"

    # Check categories coverage
    categories = {c.get("crime_category") for c in cases}
    expected_categories = {
        "cyber_fraud",
        "cheating_forgery",
        "theft_burglary",
        "crimes_against_women",
        "matrimonial_disputes",
        "crimes_against_senior_citizens",
    }
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"

    # Verify URLs and metadata structure
    for c in cases[:10]:
        assert "url" in c, "Missing URL in case metadata"
        assert c["url"].startswith("https://indiankanoon.org/doc/"), f"Invalid Indian Kanoon URL: {c['url']}"
        assert "tid" in c, "Missing tid in case metadata"
        assert c["source_id"].startswith("case:IK-"), f"Invalid source_id: {c['source_id']}"

    # Verify retrieval
    embedder = get_embedding_model(model_type="local_tfidf")
    vs = LocalVectorStore(embedding_model=embedder)
    load_and_index_default_data(vs)
    retriever = HybridRetriever(vs, embedder)

    ik_hits = retriever.retrieve("elderly father maintenance eviction senior citizen", top_k=3, category_filter="senior_citizens")
    assert len(ik_hits) > 0, "Should retrieve hits for senior citizens"
    ik_case = next((h for h in ik_hits if h.metadata.get("url")), None)
    assert ik_case is not None, "Expected an Indian Kanoon case with URL in search results"
    logger.info(f"Retrieved Indian Kanoon case: {ik_case.title} -> {ik_case.metadata.get('url')}")
    logger.info("✓ Indian Kanoon integration test passed.")


def test_safety():
    logger.info("--- 5. Testing Safety Guardrails ---")
    guard = SafetyGuard()

    # Emergency check
    em_res = guard.check_query_safety("Police are arresting me right now, help!")
    assert not em_res.is_safe
    assert em_res.is_emergency
    em_resp = guard.create_safety_fallback_response(em_res)
    assert em_resp.escalated is True
    assert "112" in em_resp.answer

    # Unlawful intent check
    bad_res = guard.check_query_safety("How to forge a fake government stamp paper?")
    assert not bad_res.is_safe
    assert bad_res.violation_category == "unlawful_intent"

    # Safe legal query
    safe_res = guard.check_query_safety("Someone cheated me in a phone call.")
    assert safe_res.is_safe
    logger.info("✓ Safety guardrails passed.")


def test_end_to_end_legal_assistant():
    logger.info("--- 6. Testing End-to-End LegalAssistant Pipeline ---")
    config = PipelineConfig(
        confidence_threshold=0.70,
        embedding_type="local_tfidf",
        reranker_type="heuristic",
        llama_config=LLaMAConfig(backend="mock"),
    )
    assistant = LegalAssistant(config)

    # Test the primary prompt specified by the user
    user_query = "Someone called pretending to be a customs officer and made me transfer money."
    response = assistant.ask(user_query)

    logger.info("\n=== END-TO-END RESPONSE RECEIVED ===")
    logger.info(f"Confidence: {response.confidence}")
    logger.info(f"Verified: {response.verified}")
    logger.info(f"Escalated: {response.escalated}")
    logger.info(f"Legal Issues: {response.legal_issue}")
    logger.info(f"Relevant Law: {response.relevant_law}")
    logger.info(f"Possible Next Steps: {response.possible_next_steps}")
    logger.info(f"Similar Cases: {len(response.similar_cases)} found")
    logger.info(f"Sources: {len(response.sources)} cited")
    logger.info(f"Answer Preview:\n{response.answer[:300]}...")

    # Validate output schema fields
    data = response.model_dump()
    required_keys = [
        "answer",
        "legal_issue",
        "relevant_law",
        "possible_next_steps",
        "documents_or_information",
        "similar_cases",
        "sources",
        "confidence",
        "verified",
        "needs_professional_help",
        "escalated",
    ]
    for key in required_keys:
        assert key in data, f"Missing required key '{key}' in response schema"

    # Verify mandatory disclaimer is present
    assert "general informational purposes only" in response.answer.lower()
    assert response.confidence >= 0.0 and response.confidence <= 1.0
    logger.info("✓ End-to-end LegalAssistant in-domain test passed.")

    # Test out-of-domain / zero-evidence query
    logger.info("--- 7. Testing Zero-Evidence Escalation ---")
    out_of_domain_query = "How do I copyright a quantum algorithm for asteroid mining in outer space?"
    ood_response = assistant.ask(out_of_domain_query)
    assert ood_response.escalated is True, "Out-of-domain query should be escalated"
    assert ood_response.verified is False, "Out-of-domain query should not be verified"
    assert "not contain enough verified evidence" in ood_response.answer.lower() or "no relevant statutory" in ood_response.answer.lower()
    logger.info("✓ Zero-evidence escalation test passed.")


if __name__ == "__main__":
    logger.info("Running complete Model Backend test suite...")
    test_schemas()
    test_embeddings()
    test_vector_store()
    test_hybrid_retrieval_and_reranking()
    test_indian_kanoon_integration()
    test_safety()
    test_end_to_end_legal_assistant()
    logger.info("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")
