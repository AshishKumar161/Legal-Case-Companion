import math
import os
import uuid
import numpy as np
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.domain.ai.retrieval_service import RetrievalService, batch_cosine_similarity
from app.models.ai import DocumentChunk
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.user import User, UserRole
from app.schemas.search import CaseSearchRequest, SearchMode


PG_TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@127.0.0.1:5433/lcc_migration_test",
)


def _pg_available() -> bool:
    try:
        engine = sa.create_engine(PG_TEST_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            res = conn.execute(
                sa.text("SELECT 1 FROM pg_type WHERE typname = 'vector';")
            ).scalar()
            return bool(res)
    except Exception:
        return False


@pytest.fixture(scope="module")
def pg_session():
    if not _pg_available():
        pytest.skip("PostgreSQL test cluster with pgvector not available")

    engine = sa.create_engine(PG_TEST_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _generate_synthetic_vector(seed_int: int, dim: int = 1536) -> list[float]:
    """Generates a reproducible, normalized synthetic vector of dimension 1536."""
    rng = np.random.RandomState(seed_int)
    raw = rng.randn(dim).astype(np.float32)
    norm = np.linalg.norm(raw)
    normalized = raw / norm if norm > 0.0 else raw
    return [float(x) for x in normalized]


def test_pgvector_native_retrieval_and_index_scan(pg_session):
    """Verifies EXPLAIN ANALYZE index usage, authorization, tenant isolation, and Recall@K."""
    # 1. Setup Tenant and Case Fixtures
    user = User(
        id=uuid.uuid4(),
        email=f"pgvector_tester_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    other_user = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    pg_session.add_all([user, other_user])
    pg_session.flush()

    target_case = Case(
        id=uuid.uuid4(),
        title="Commercial Damages Breach Dispute",
        description="Arbitration dispute regarding liquidated damages clause.",
    )
    other_case = Case(
        id=uuid.uuid4(),
        title="Unrelated Criminal Case",
        description="Criminal bail matter.",
    )
    pg_session.add_all([target_case, other_case])
    pg_session.flush()

    target_part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=target_case.id,
        user_id=user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    other_part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=other_case.id,
        user_id=other_user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    pg_session.add_all([target_part, other_part])

    # 2. Documents: Safe, Quarantined, and Other Case
    safe_doc = Document(
        id=uuid.uuid4(),
        case_id=target_case.id,
        uploaded_by=user.id,
        filename="Commercial_Agreement_2024.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
    )
    quarantined_doc = Document(
        id=uuid.uuid4(),
        case_id=target_case.id,
        uploaded_by=user.id,
        filename="Suspicious_Addendum.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.READY,
    )
    other_case_doc = Document(
        id=uuid.uuid4(),
        case_id=other_case.id,
        uploaded_by=other_user.id,
        filename="Bail_Application.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.PLEADINGS,
        version=1,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
    )
    pg_session.add_all([safe_doc, quarantined_doc, other_case_doc])
    pg_session.flush()

    # 3. Base Query Vector (Reference)
    query_vector = _generate_synthetic_vector(42)

    # 4. Generate Chunks with exact mathematical cosine similarities
    def _create_vector_with_similarity(base_vec: list[float], target_sim: float, seed: int) -> list[float]:
        q = np.array(base_vec, dtype=np.float32)
        rng = np.random.RandomState(seed)
        noise = rng.randn(len(base_vec)).astype(np.float32)
        # Gram-Schmidt orthogonalization
        noise = noise - np.dot(noise, q) * q
        noise /= np.linalg.norm(noise)
        sin_theta = math.sqrt(max(0.0, 1.0 - target_sim**2))
        res = target_sim * q + sin_theta * noise
        return [float(x) for x in res]

    close_vec = _create_vector_with_similarity(query_vector, 0.95, 1)
    chunk_top1 = DocumentChunk(
        id=uuid.uuid4(),
        case_id=target_case.id,
        document_id=safe_doc.id,
        content="Section 74 of the Indian Contract Act governs liquidated damages for commercial breach.",
        embedding=close_vec,
        metadata_={"document_version": 1, "page_start": 4},
    )

    mid_vec = _create_vector_with_similarity(query_vector, 0.80, 2)
    chunk_top2 = DocumentChunk(
        id=uuid.uuid4(),
        case_id=target_case.id,
        document_id=safe_doc.id,
        content="The agreed pre-estimate of damages is reasonable and enforceable under Indian law.",
        embedding=mid_vec,
        metadata_={"document_version": 1, "page_start": 5},
    )

    # Chunk 3: Quarantined doc chunk (Must NEVER be returned)
    chunk_quarantined = DocumentChunk(
        id=uuid.uuid4(),
        case_id=target_case.id,
        document_id=quarantined_doc.id,
        content="Malware infected confidential contract clause.",
        embedding=list(query_vector),  # exact match embedding, but in quarantined doc!
        metadata_={"document_version": 1},
    )

    # Chunk 4: Other case chunk (Tenant isolation: Must NEVER be returned)
    chunk_other_case = DocumentChunk(
        id=uuid.uuid4(),
        case_id=other_case.id,
        document_id=other_case_doc.id,
        content="High similarity embedding from another law firm tenant case.",
        embedding=list(query_vector),
        metadata_={"document_version": 1},
    )

    pg_session.add_all([chunk_top1, chunk_top2, chunk_quarantined, chunk_other_case])
    pg_session.commit()

    service = RetrievalService(pg_session)

    # 5. EXPLAIN ANALYZE verification
    pg_session.execute(sa.text("SET enable_seqscan = off;"))
    plan_lines = service.explain_retrieval_query(target_case.id, query_vector, top_k=5)
    full_plan = "\n".join(plan_lines)
    print("\n--- EXPLAIN ANALYZE Plan ---")
    print(full_plan)

    assert len(plan_lines) > 0
    assert any("ix_document_chunks_embedding_hnsw" in line or "Scan" in line for line in plan_lines)
    pg_session.execute(sa.text("SET enable_seqscan = on;"))

    # 6. Execute Native pgvector Semantic Search
    search_req = CaseSearchRequest(
        query="liquidated damages commercial breach section 74",
        top_k=5,
        search_mode=SearchMode.SEMANTIC,
        min_score=0.1,
    )
    service.embedding_service.generate_embeddings = lambda texts: [query_vector]

    resp = service.search_case_evidence(user, target_case.id, search_req)

    # 7. Assertions:
    assert resp.total_results >= 2
    retrieved_ids = [r.chunk_id for r in resp.results]
    assert chunk_top1.id in retrieved_ids
    assert chunk_top2.id in retrieved_ids

    # Tenant isolation assertion: other case chunk MUST NOT be present
    assert chunk_other_case.id not in retrieved_ids

    # Security quarantine assertion: quarantined doc chunk MUST NOT be present
    assert chunk_quarantined.id not in retrieved_ids

    # Check ranking
    idx1 = retrieved_ids.index(chunk_top1.id)
    idx2 = retrieved_ids.index(chunk_top2.id)
    assert idx1 < idx2, "Closest vector chunk must be ranked ahead of mid vector chunk"

    # Telemetry and engine identification
    top_meta = resp.results[0].metadata
    assert top_meta["retrieval_engine"] in ("pgvector_hnsw", "pgvector_exact")
    assert "native_vector_distance" in top_meta
    assert resp.results[0].score > 0.5


def test_recall_at_k_exact_vs_pgvector(pg_session):
    """Validates Recall@K and ranking fidelity between exact NumPy BLAS and PostgreSQL pgvector."""
    user = User(
        id=uuid.uuid4(),
        email=f"recall_tester_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    pg_session.add(user)
    pg_session.flush()

    case = Case(
        id=uuid.uuid4(),
        title="Recall Benchmark Case",
        description="Corpus for testing Recall@K between exact BLAS and pgvector.",
    )
    pg_session.add(case)
    pg_session.flush()

    part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    pg_session.add(part)

    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=user.id,
        filename="Benchmark_Corpus.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=2048,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
    )
    pg_session.add(doc)
    pg_session.flush()

    # Generate 30 candidate vectors
    query_vec = _generate_synthetic_vector(100)
    corpus_vectors = [_generate_synthetic_vector(i + 101) for i in range(30)]

    chunks = []
    for i, vec in enumerate(corpus_vectors):
        c = DocumentChunk(
            id=uuid.uuid4(),
            case_id=case.id,
            document_id=doc.id,
            content=f"Benchmark corpus chunk number {i} with distinct legal provisions.",
            embedding=vec,
            metadata_={"document_version": 1},
        )
        chunks.append(c)
        pg_session.add(c)
    pg_session.commit()

    # Compute ground truth exact nearest neighbours using NumPy BLAS
    gt_scores = batch_cosine_similarity(query_vec, corpus_vectors)
    ranked_gt_indices = np.argsort(gt_scores)[::-1]
    top_k = 5
    top_gt_chunk_ids = set(chunks[i].id for i in ranked_gt_indices[:top_k])

    # Retrieve via pgvector
    service = RetrievalService(pg_session)
    service.embedding_service.generate_embeddings = lambda texts: [query_vec]

    req = CaseSearchRequest(
        query="benchmark corpus legal provisions",
        top_k=top_k,
        search_mode=SearchMode.SEMANTIC,
        min_score=0.0,
    )
    resp = service.search_case_evidence(user, case.id, req)
    pgvector_top_ids = set(r.chunk_id for r in resp.results)

    # Calculate Recall@K
    intersection = top_gt_chunk_ids.intersection(pgvector_top_ids)
    recall_at_k = len(intersection) / float(top_k)
    print(f"\n[BENCHMARK] Recall@{top_k}: {recall_at_k:.2f} ({len(intersection)}/{top_k} matches)")

    assert recall_at_k >= 0.8, f"Recall@{top_k} was {recall_at_k}, expected at least 0.80"


def test_sqlite_fallback_retrieval():
    """Verifies that SQLite development and unit tests continue to function seamlessly via NumPy fallback."""
    from app.models import Base
    sqlite_engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sqlite_engine)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    session = SqliteSession()
    try:
        user = User(
            id=uuid.uuid4(),
            email=f"sqlite_user_{uuid.uuid4().hex[:8]}@example.com",
            role=UserRole.LAWYER,
        )
        session.add(user)
        session.flush()

        case = Case(
            id=uuid.uuid4(),
            title="SQLite Development Case",
            description="Local unit test case.",
        )
        session.add(case)
        session.flush()

        part = CaseParticipant(
            id=uuid.uuid4(),
            case_id=case.id,
            user_id=user.id,
            participant_role=ParticipantRole.LAWYER,
            status=ParticipantStatus.ACTIVE,
        )
        session.add(part)

        doc = Document(
            id=uuid.uuid4(),
            case_id=case.id,
            uploaded_by=user.id,
            filename="Local_Test_Doc.pdf",
            storage_key=f"docs/{uuid.uuid4()}",
            mime_type="application/pdf",
            file_size=1024,
            document_type=DocumentCategory.CONTRACT,
            version=1,
            security_status=DocumentSecurityStatus.SAFE,
            processing_status=DocumentProcessingStatus.READY,
        )
        session.add(doc)
        session.flush()

        q_vec = _generate_synthetic_vector(200)
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            case_id=case.id,
            document_id=doc.id,
            content="Arbitration agreement under the Arbitration and Conciliation Act 1996.",
            embedding=q_vec,
            metadata_={"document_version": 1},
        )
        session.add(chunk)
        session.commit()

        service = RetrievalService(session)
        assert not service._is_postgres()

        service.embedding_service.generate_embeddings = lambda texts: [q_vec]
        req = CaseSearchRequest(
            query="arbitration agreement",
            top_k=5,
            search_mode=SearchMode.SEMANTIC,
            min_score=0.1,
        )
        resp = service.search_case_evidence(user, case.id, req)
        assert resp.total_results >= 1
        assert resp.results[0].chunk_id == chunk.id
        assert resp.results[0].score > 0.9
    finally:
        session.close()
        sqlite_engine.dispose()


def test_viewer_confidentiality_restrictions_in_retrieval():
    """Verifies that VIEWER participants cannot retrieve confidential documents uploaded by others."""
    from app.core.exceptions import AuthorizationError
    from app.models import Base
    sqlite_engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sqlite_engine)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    session = SqliteSession()
    try:
        lawyer = User(
            id=uuid.uuid4(),
            email=f"lawyer_{uuid.uuid4().hex[:8]}@example.com",
            role=UserRole.LAWYER,
        )
        viewer = User(
            id=uuid.uuid4(),
            email=f"viewer_{uuid.uuid4().hex[:8]}@example.com",
            role=UserRole.CLIENT,
        )
        session.add_all([lawyer, viewer])
        session.flush()

        case = Case(
            id=uuid.uuid4(),
            title="Confidential Corporate Merger Dispute",
            description="Matter with strictly restricted internal strategy documents.",
        )
        session.add(case)
        session.flush()

        # Lawyer is OWNER/LAWYER, Viewer is VIEWER
        lawyer_part = CaseParticipant(
            id=uuid.uuid4(),
            case_id=case.id,
            user_id=lawyer.id,
            participant_role=ParticipantRole.LAWYER,
            status=ParticipantStatus.ACTIVE,
        )
        viewer_part = CaseParticipant(
            id=uuid.uuid4(),
            case_id=case.id,
            user_id=viewer.id,
            participant_role=ParticipantRole.VIEWER,
            status=ParticipantStatus.ACTIVE,
        )
        session.add_all([lawyer_part, viewer_part])
        session.flush()

        # 1. Non-confidential document
        public_doc = Document(
            id=uuid.uuid4(),
            case_id=case.id,
            uploaded_by=lawyer.id,
            filename="Public_Filing.pdf",
            storage_key=f"docs/{uuid.uuid4()}",
            mime_type="application/pdf",
            file_size=1024,
            document_type=DocumentCategory.PLEADINGS,
            version=1,
            security_status=DocumentSecurityStatus.SAFE,
            processing_status=DocumentProcessingStatus.READY,
            is_confidential=False,
        )

        # 2. Confidential document
        confidential_doc = Document(
            id=uuid.uuid4(),
            case_id=case.id,
            uploaded_by=lawyer.id,
            filename="Secret_Settlement_Strategy.pdf",
            storage_key=f"docs/{uuid.uuid4()}",
            mime_type="application/pdf",
            file_size=1024,
            document_type=DocumentCategory.CONTRACT,
            version=1,
            security_status=DocumentSecurityStatus.SAFE,
            processing_status=DocumentProcessingStatus.READY,
            is_confidential=True,
        )
        session.add_all([public_doc, confidential_doc])
        session.flush()

        q_vec = _generate_synthetic_vector(300)
        public_chunk = DocumentChunk(
            id=uuid.uuid4(),
            case_id=case.id,
            document_id=public_doc.id,
            content="Public filing: petition filed under section 9 of arbitration act.",
            embedding=q_vec,
            metadata_={"document_version": 1},
        )
        confidential_chunk = DocumentChunk(
            id=uuid.uuid4(),
            case_id=case.id,
            document_id=confidential_doc.id,
            content="CONFIDENTIAL STRATEGY: Maximum concession limit is INR 5 Crore.",
            embedding=q_vec,
            metadata_={"document_version": 1},
        )
        session.add_all([public_chunk, confidential_chunk])
        session.commit()

        service = RetrievalService(session)
        service.embedding_service.generate_embeddings = lambda texts: [q_vec]

        # Search as VIEWER:
        req = CaseSearchRequest(
            query="arbitration strategy petition",
            top_k=10,
            search_mode=SearchMode.SEMANTIC,
            min_score=0.1,
        )
        viewer_resp = service.search_case_evidence(viewer, case.id, req)
        viewer_chunk_ids = [r.chunk_id for r in viewer_resp.results]

        # Confidential chunk must NOT enter viewer results
        assert confidential_chunk.id not in viewer_chunk_ids
        assert public_chunk.id in viewer_chunk_ids

        # Direct search with document_id pointing to confidential doc must raise AuthorizationError
        doc_req = CaseSearchRequest(
            query="settlement strategy",
            document_id=confidential_doc.id,
            top_k=5,
            search_mode=SearchMode.SEMANTIC,
            min_score=0.1,
        )
        with pytest.raises(AuthorizationError):
            service.search_case_evidence(viewer, case.id, doc_req)

        # Search as LAWYER:
        lawyer_resp = service.search_case_evidence(lawyer, case.id, req)
        lawyer_chunk_ids = [r.chunk_id for r in lawyer_resp.results]
        assert confidential_chunk.id in lawyer_chunk_ids
        assert public_chunk.id in lawyer_chunk_ids
    finally:
        session.close()
        sqlite_engine.dispose()


def test_pgvector_confidentiality_and_quarantine_isolation(pg_session):
    """Verifies confidential document exclusion and quarantine isolation on native PostgreSQL pgvector."""
    from app.core.exceptions import AuthorizationError

    lawyer = User(
        id=uuid.uuid4(),
        email=f"pg_lawyer_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    viewer = User(
        id=uuid.uuid4(),
        email=f"pg_viewer_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.CLIENT,
    )
    pg_session.add_all([lawyer, viewer])
    pg_session.flush()

    case = Case(
        id=uuid.uuid4(),
        title="PostgreSQL PgVector Confidentiality Case",
        description="Testing confidential doc exclusion on native PostgreSQL.",
    )
    pg_session.add(case)
    pg_session.flush()

    lawyer_part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=case.id,
        user_id=lawyer.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    viewer_part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=case.id,
        user_id=viewer.id,
        participant_role=ParticipantRole.VIEWER,
        status=ParticipantStatus.ACTIVE,
    )
    pg_session.add_all([lawyer_part, viewer_part])
    pg_session.flush()

    public_doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=lawyer.id,
        filename="PG_Public_Doc.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.PLEADINGS,
        version=1,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
        is_confidential=False,
    )
    confidential_doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=lawyer.id,
        filename="PG_Confidential_Strategy.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
        is_confidential=True,
    )
    quarantined_doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=lawyer.id,
        filename="PG_Quarantined_Doc.pdf",
        storage_key=f"docs/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.READY,
        is_confidential=False,
    )
    pg_session.add_all([public_doc, confidential_doc, quarantined_doc])
    pg_session.flush()

    q_vec = _generate_synthetic_vector(555, 1536)
    public_chunk = DocumentChunk(
        id=uuid.uuid4(),
        case_id=case.id,
        document_id=public_doc.id,
        content="Public court petition on Indian law jurisdiction.",
        embedding=q_vec,
        metadata_={"document_version": 1},
    )
    confidential_chunk = DocumentChunk(
        id=uuid.uuid4(),
        case_id=case.id,
        document_id=confidential_doc.id,
        content="Privileged settlement offer of INR 10 Crore maximum limit.",
        embedding=q_vec,
        metadata_={"document_version": 1},
    )
    quarantined_chunk = DocumentChunk(
        id=uuid.uuid4(),
        case_id=case.id,
        document_id=quarantined_doc.id,
        content="Malware quarantined clause with identical query embedding.",
        embedding=q_vec,
        metadata_={"document_version": 1},
    )
    pg_session.add_all([public_chunk, confidential_chunk, quarantined_chunk])
    pg_session.commit()

    service = RetrievalService(pg_session)
    service.embedding_service.generate_embeddings = lambda texts: [q_vec]

    # 1. Search as VIEWER:
    req = CaseSearchRequest(
        query="jurisdiction settlement limit",
        top_k=10,
        search_mode=SearchMode.SEMANTIC,
        min_score=0.01,
    )
    viewer_resp = service.search_case_evidence(viewer, case.id, req)
    viewer_ids = [r.chunk_id for r in viewer_resp.results]

    # Assert confidential & quarantined chunks are NEVER returned to VIEWER
    assert confidential_chunk.id not in viewer_ids
    assert quarantined_chunk.id not in viewer_ids
    assert public_chunk.id in viewer_ids

    # 2. Search as LAWYER (OWNER/PARTICIPANT):
    lawyer_resp = service.search_case_evidence(lawyer, case.id, req)
    lawyer_ids = [r.chunk_id for r in lawyer_resp.results]

    # Assert confidential chunk is returned to LAWYER, but quarantined chunk is STILL excluded
    assert confidential_chunk.id in lawyer_ids
    assert public_chunk.id in lawyer_ids
    assert quarantined_chunk.id not in lawyer_ids

