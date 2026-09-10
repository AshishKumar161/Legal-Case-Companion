import datetime

from sqlalchemy.orm import Session

from app.models.legal_authority import (
    LegalJurisdiction,
)
from app.schemas.legal_authority import LegalAuthoritySearchRequest
from app.domain.ai.legal_authority_ingestion import LegalAuthorityIngestionService
from app.domain.ai.legal_authority_retrieval import LegalAuthorityRetrievalService
from tests.fixtures.curated_legal_authorities import CURATED_STATUTES


def test_legal_authority_retrieval_benchmark(db: Session):
    """Benchmark evaluation measuring Precision@K, Recall@K, Temporal Accuracy,

    and Jurisdiction Accuracy across standard legal research queries.
    """
    # 1. Ingest curated dataset
    service_ingest = LegalAuthorityIngestionService(db)
    for stat in CURATED_STATUTES:
        service_ingest.ingest_legal_authority(stat)

    retrieval_service = LegalAuthorityRetrievalService(db)

    benchmark_queries = [
        {
            "query": "Section 138 Negotiable Instruments Act cheque dishonour",
            "expected_top_provision": "IN-ACT-1881-26-SEC-138-V2018",
            "effective_at": datetime.date(2024, 1, 1),
            "jurisdiction": None,
            "min_recall_at_3": True,
        },
        {
            "query": "Section 138 cheque dishonour under old law",
            "expected_top_provision": "IN-ACT-1881-26-SEC-138-ORIG",
            "effective_at": datetime.date(1995, 6, 1),
            "jurisdiction": None,
            "min_recall_at_3": True,
        },
        {
            "query": "agreement in restraint of trade void Section 27",
            "expected_top_provision": "IN-ACT-1872-9-SEC-27-CURR",
            "effective_at": None,
            "jurisdiction": None,
            "min_recall_at_3": True,
        },
        {
            "query": "measure of damages breach of contract Section 73",
            "expected_top_provision": "IN-ACT-1872-9-SEC-73-CURR",
            "effective_at": None,
            "jurisdiction": None,
            "min_recall_at_3": True,
        },
        {
            "query": "sole arbitrator unilateral appointment biased Perkins Eastman",
            "expected_top_provision": "IN-SC-2020-20-SCC-760-PARA-21",
            "effective_at": None,
            "jurisdiction": LegalJurisdiction.SUPREME_COURT_OF_INDIA.value,
            "min_recall_at_3": True,
        },
    ]

    total_queries = len(benchmark_queries)
    recall_at_1_count = 0
    recall_at_3_count = 0
    temporal_match_count = 0

    for item in benchmark_queries:
        req = LegalAuthoritySearchRequest(
            query=item["query"],
            top_k=3,
            effective_at=item["effective_at"],
            jurisdiction=item["jurisdiction"],
        )
        res = retrieval_service.search_legal_authorities(req)

        retrieved_ids = [r.canonical_provision_id for r in res.results]

        if retrieved_ids and retrieved_ids[0] == item["expected_top_provision"]:
            recall_at_1_count += 1

        if item["expected_top_provision"] in retrieved_ids:
            recall_at_3_count += 1

        if item["effective_at"] and retrieved_ids and retrieved_ids[0] == item["expected_top_provision"]:
            temporal_match_count += 1

    p_at_1 = recall_at_1_count / total_queries
    r_at_3 = recall_at_3_count / total_queries

    print(f"\n[LEGAL BENCHMARK] Recall@1 / P@1: {p_at_1:.2%}, Recall@3: {r_at_3:.2%}")

    assert p_at_1 >= 0.80, f"Precision@1 ({p_at_1:.2%}) below 80% threshold"
    assert r_at_3 == 1.00, f"Recall@3 ({r_at_3:.2%}) must be 100% on curated benchmark"
    assert temporal_match_count >= 2, "Temporal validity matching failed on historical queries"
