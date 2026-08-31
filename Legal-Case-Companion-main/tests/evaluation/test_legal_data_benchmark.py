import datetime

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.legal_authority import LegalAuthoritySearchRequest
from app.schemas.search import SearchMode
from app.services.legal_authority_retrieval import LegalAuthorityRetrievalService
from app.services.legal_data_pipeline import LegalDataPipeline


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def test_legal_data_operations_and_retrieval_benchmark(db: Session):
    """Evaluates recall, precision, citation resolution, and temporal accuracy across curated Indian legal data."""
    # 1. Sync authoritative fixtures
    pipeline = LegalDataPipeline(db)
    pipeline.sync_curated_fixtures()

    retrieval_svc = LegalAuthorityRetrievalService(db)

    # 2. Benchmark Cases
    benchmark_cases = [
        {
            "query": "Section 138 Negotiable Instruments Act cheque bounce penalty",
            "expected_canonical": "IN-ACT-1881-26",
            "expected_provision": "IN-ACT-1881-26-SEC-138-V2018",
            "search_mode": SearchMode.HYBRID,
            "effective_at": None,
        },
        {
            "query": "cheque dishonour imprisonment term in 2010",
            "expected_canonical": "IN-ACT-1881-26",
            "expected_provision": "IN-ACT-1881-26-SEC-138-V1988",
            "search_mode": SearchMode.HYBRID,
            "effective_at": datetime.date(2010, 5, 1),
        },
        {
            "query": "Section 9 Arbitration Act interim measures by court",
            "expected_canonical": "IN-ACT-1996-26",
            "expected_provision": "IN-ACT-1996-26-SEC-9-V2015",
            "search_mode": SearchMode.HYBRID,
            "effective_at": None,
        },
        {
            "query": "Section 318 Bharatiya Nyaya Sanhita cheating punishment",
            "expected_canonical": "IN-ACT-2023-45",
            "expected_provision": "IN-ACT-2023-45-SEC-318",
            "search_mode": SearchMode.HYBRID,
            "effective_at": None,
        },
        {
            "query": "Article 21 protection of life and personal liberty",
            "expected_canonical": "IN-CONST-1950",
            "expected_provision": "IN-CONST-1950-ART-21",
            "search_mode": SearchMode.HYBRID,
            "effective_at": None,
        },
        {
            "query": "Vidya Drolia landlord tenant disputes arbitrability test",
            "expected_canonical": "IN-SC-2020-VIDYA-DROLIA",
            "expected_provision": "IN-SC-2020-VIDYA-DROLIA-HOLDING-1",
            "search_mode": SearchMode.HYBRID,
            "effective_at": None,
        },
        {
            "query": "P Mohanraj Section 138 proceedings moratorium under Section 14 IBC",
            "expected_canonical": "IN-SC-2021-6-SCC-258",
            "expected_provision": "IN-SC-2021-6-SCC-258-HOLDING-1",
            "search_mode": SearchMode.HYBRID,
            "effective_at": None,
        },
    ]

    recall_hits = 0
    top_1_hits = 0
    temporal_hits = 0

    for b_case in benchmark_cases:
        req = LegalAuthoritySearchRequest(
            query=b_case["query"],
            search_mode=b_case["search_mode"],
            effective_at=b_case["effective_at"],
            limit=5,
        )
        res = retrieval_svc.search_legal_authorities(req)
        results = res.results

        assert len(results) > 0, f"No results for query: {b_case['query']}"

        # Check Recall@5
        matched = any(
            r.canonical_identifier == b_case["expected_canonical"]
            and r.canonical_provision_id == b_case["expected_provision"]
            for r in results
        )
        if matched:
            recall_hits += 1

        # Check Top-1 Precision
        if results[0].canonical_identifier == b_case["expected_canonical"]:
            top_1_hits += 1

        # Check Temporal Accuracy for historical query
        if (
            b_case["effective_at"] is not None
            and results[0].canonical_provision_id == b_case["expected_provision"]
        ):
            temporal_hits += 1

    total_cases = len(benchmark_cases)
    recall_at_5 = recall_hits / total_cases
    top_1_precision = top_1_hits / total_cases

    assert recall_at_5 >= 0.85, f"Recall@5 ({recall_at_5}) below threshold 0.85"
    assert top_1_precision >= 0.85, f"Top-1 Precision ({top_1_precision}) below threshold 0.85"
    assert temporal_hits >= 1, "Temporal boundary query failed"
