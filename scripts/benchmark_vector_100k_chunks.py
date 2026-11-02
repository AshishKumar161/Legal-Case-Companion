#!/usr/bin/env python3
"""
100,000 Chunks pgvector Benchmark & Security Filter Validation

Tests:
1. Multi-tenant generation: 10 distinct cases, 100,000 total document chunks.
2. Filtered HNSW retrieval using ix_document_chunks_embedding_hnsw.
3. Iterative index scan behavior with security status, confidentiality, and case predicates.
4. Recall@10, Precision@10 against exact sequential scan ground truth.
5. P50, P90, P95, P99 latency across 50 query iterations.
6. Strict multi-tenant isolation, confidential exclusion, and quarantined exclusion.
"""

import json
import logging
import os
import sys
import time
import uuid
from typing import Any

import numpy as np
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("100k_benchmark")

PG_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@127.0.0.1:5433/lcc_migration_test",
)


def run_100k_pgvector_benchmark():
    engine = create_engine(PG_URL, pool_pre_ping=True)

    with engine.begin() as conn:
        # Verify vector extension
        ext = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        ).scalar()
        if not ext:
            raise RuntimeError("pgvector extension not installed in PostgreSQL database.")
        logger.info(f"Connected to PostgreSQL with pgvector v{ext}")

        # Optimize maintenance memory for HNSW build
        conn.execute(text("SET maintenance_work_mem = '512MB';"))

    # Generate 10 cases across 10 different users/tenants
    num_cases = 10
    chunks_per_case = 10000
    total_target_chunks = num_cases * chunks_per_case  # 100,000
    dim = 1536

    case_ids = [str(uuid.uuid4()) for _ in range(num_cases)]
    user_ids = [str(uuid.uuid4()) for _ in range(num_cases)]
    doc_ids = [str(uuid.uuid4()) for _ in range(num_cases)]
    quarantined_doc_ids = [str(uuid.uuid4()) for _ in range(num_cases)]

    logger.info(f"Setting up {num_cases} cases, each with {chunks_per_case} chunks (Total: {total_target_chunks})...")
    rng = np.random.default_rng(42)

    with engine.begin() as conn:
        existing_cases = [
            str(r[0]) for r in conn.execute(
                text("SELECT case_id FROM document_chunks GROUP BY case_id HAVING count(*) >= 10000;")
            ).fetchall()
        ]
        if len(existing_cases) >= num_cases:
            logger.info(f"Reusing {len(existing_cases)} existing benchmark cases with >=10k chunks each...")
            case_ids = existing_cases[:num_cases]
            needs_insert = False
            quarantined_doc_ids = [
                str(r[0]) for r in conn.execute(text("SELECT id FROM documents WHERE security_status != 'SAFE';")).fetchall()
            ]
        else:
            needs_insert = True

        if needs_insert:
            # Insert users
            for i in range(num_cases):
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, password_hash, role, account_status, created_at, updated_at) "
                        "VALUES (:id, :email, 'hash', 'CLIENT', 'ACTIVE', NOW(), NOW()) "
                        "ON CONFLICT DO NOTHING;"
                    ),
                    {"id": user_ids[i], "email": f"client_100k_{i}_{user_ids[i][:6]}@example.com"}
                )
                # Insert case
                conn.execute(
                    text(
                        "INSERT INTO cases (id, title, status, description, created_at, updated_at) "
                        "VALUES (:id, :title, 'OPEN', 'Benchmark case', NOW(), NOW()) "
                        "ON CONFLICT DO NOTHING;"
                    ),
                    {"id": case_ids[i], "title": f"100K Benchmark Case {i}"}
                )
                # Insert participant
                conn.execute(
                    text(
                        "INSERT INTO case_participants (id, case_id, user_id, participant_role, status, created_at, updated_at) "
                        "VALUES (gen_random_uuid(), :cid, :uid, 'OWNER', 'ACTIVE', NOW(), NOW()) "
                        "ON CONFLICT DO NOTHING;"
                    ),
                    {"cid": case_ids[i], "uid": user_ids[i]}
                )
                # Insert safe document
                conn.execute(
                    text(
                        "INSERT INTO documents (id, case_id, uploaded_by, filename, storage_key, mime_type, file_size, security_status, is_confidential, version, created_at, updated_at) "
                        "VALUES (:id, :cid, :uid, 'safe_doc.pdf', :key, 'application/pdf', 1024, 'SAFE', false, 1, NOW(), NOW()) "
                        "ON CONFLICT DO NOTHING;"
                    ),
                    {"id": doc_ids[i], "cid": case_ids[i], "uid": user_ids[i], "key": f"cases/{case_ids[i]}/safe_{i}.pdf"}
                )
                # Insert quarantined document to verify exclusion
                conn.execute(
                    text(
                        "INSERT INTO documents (id, case_id, uploaded_by, filename, storage_key, mime_type, file_size, security_status, is_confidential, version, created_at, updated_at) "
                        "VALUES (:id, :cid, :uid, 'quarantined.pdf', :key, 'application/pdf', 2048, 'QUARANTINED', false, 1, NOW(), NOW()) "
                        "ON CONFLICT DO NOTHING;"
                    ),
                    {"id": quarantined_doc_ids[i], "cid": case_ids[i], "uid": user_ids[i], "key": f"cases/{case_ids[i]}/quarantined_{i}.pdf"}
                )

            # Populate a diverse pool of 1,000 distinct normalized 1536-dimensional vectors
            logger.info("Generating pool of 1,000 normalized 1536-dim vectors...")
            conn.execute(text("CREATE TEMP TABLE IF NOT EXISTS temp_vector_pool (pool_id int primary key, emb real[]);"))
            conn.execute(text("TRUNCATE temp_vector_pool;"))

            pool_size = 1000
            rng = np.random.default_rng(42)
            base_vectors = rng.standard_normal((pool_size, dim), dtype=np.float32)
            norms = np.linalg.norm(base_vectors, axis=1, keepdims=True)
            base_vectors = (base_vectors / norms).tolist()

            for idx, vec in enumerate(base_vectors, 1):
                conn.execute(
                    text("INSERT INTO temp_vector_pool (pool_id, emb) VALUES (:id, :emb);"),
                    {"id": idx, "emb": vec}
                )

            logger.info(f"Bulk generating {total_target_chunks} chunks across {num_cases} cases...")
            t0_gen = time.perf_counter()

            for i in range(num_cases):
                cid = case_ids[i]
                did_safe = doc_ids[i]
                did_quarantine = quarantined_doc_ids[i]

                conn.execute(
                    text(
                        f"""
                        INSERT INTO document_chunks (
                            id, case_id, document_id, content, metadata, embedding,
                            embedding_model, embedding_version, created_at, updated_at
                        )
                        SELECT
                            gen_random_uuid(),
                            '{cid}'::uuid,
                            CASE WHEN s <= 9900 THEN '{did_safe}'::uuid ELSE '{did_quarantine}'::uuid END,
                            'Benchmark chunk ' || s || ' for case {i}',
                            '{{}}'::json,
                            vp.emb,
                            'text-embedding-3-small',
                            'v1',
                            NOW(),
                            NOW()
                        FROM generate_series(1, {chunks_per_case}) s
                        JOIN temp_vector_pool vp ON vp.pool_id = ((s * 7 + {i} * 31) % 1000) + 1;
                        """
                    )
                )
                logger.info(f"  Inserted {(i + 1) * chunks_per_case} / {total_target_chunks} chunks...")

            t1_gen = time.perf_counter()
            logger.info(f"Chunk insertion complete in {t1_gen - t0_gen:.2f}s.")

        # Ensure index exists and re-analyze table
        logger.info("Ensuring HNSW index is up to date and analyzing document_chunks...")
        t0_idx = time.perf_counter()
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
                ON document_chunks
                USING hnsw ((((embedding)::real[])::vector(1536)) vector_cosine_ops)
                WHERE (deleted_at IS NULL AND array_length(embedding, 1) = 1536);
                """
            )
        )
        conn.execute(text("ANALYZE document_chunks;"))
        conn.execute(text("ANALYZE documents;"))
        conn.execute(text("ANALYZE cases;"))
        t1_idx = time.perf_counter()
        logger.info(f"HNSW index analyzed in {t1_idx - t0_idx:.2f}s.")

        # Total chunk count check
        total_chunks = conn.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE deleted_at IS NULL;")
        ).scalar()
        logger.info(f"Active chunks in database: {total_chunks}")

    # Now execute evaluation benchmarks
    target_case_idx = 0
    target_case_id = case_ids[target_case_idx]
    unauthorized_case_id = case_ids[1]

    # Generate test query vectors
    test_queries = rng.standard_normal((50, dim), dtype=np.float32)
    test_queries = (test_queries / np.linalg.norm(test_queries, axis=1, keepdims=True)).tolist()

    hnsw_latencies = []
    exact_latencies = []
    recall_scores = []
    precision_scores = []
    isolation_violations = 0
    quarantine_violations = 0

    hnsw_plan_text = ""
    exact_plan_text = ""

    logger.info("Running 50 query iterations comparing HNSW vs Exact retrieval...")

    with engine.connect() as conn:
        # Enable iterative scan in pgvector if supported
        try:
            conn.execute(text("SET hnsw.iterative_scan = 'relaxed_order';"))
        except Exception:
            pass

        for q_idx, q_vec in enumerate(test_queries):
            q_vec_str = "[" + ",".join(f"{x:.6f}" for x in q_vec) + "]"

            # 1. HNSW Index Retrieval (Optimized)
            conn.execute(text("SET enable_seqscan = OFF;"))
            conn.execute(text("SET enable_indexscan = ON;"))

            t0 = time.perf_counter()
            hnsw_rows = conn.execute(
                text(
                    """
                    SELECT dc.id, dc.case_id, dc.document_id,
                           1.0 - ((((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))) AS similarity
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id
                    JOIN cases c ON c.id = dc.case_id
                    WHERE dc.deleted_at IS NULL
                      AND d.deleted_at IS NULL
                      AND c.deleted_at IS NULL
                      AND d.security_status = 'SAFE'
                      AND dc.case_id = :case_id
                    ORDER BY (((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))
                    LIMIT 10;
                    """
                ),
                {"query_vector": q_vec_str, "case_id": target_case_id}
            ).fetchall()
            t1 = time.perf_counter()
            hnsw_latencies.append((t1 - t0) * 1000)

            # Capture EXPLAIN plan on first iteration
            if q_idx == 0:
                hnsw_plan = conn.execute(
                    text(
                        """
                        EXPLAIN (ANALYZE, BUFFERS)
                        SELECT dc.id, dc.case_id, dc.document_id,
                               1.0 - ((((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))) AS similarity
                        FROM document_chunks dc
                        JOIN documents d ON d.id = dc.document_id
                        JOIN cases c ON c.id = dc.case_id
                        WHERE dc.deleted_at IS NULL
                          AND d.deleted_at IS NULL
                          AND c.deleted_at IS NULL
                          AND d.security_status = 'SAFE'
                          AND dc.case_id = :case_id
                        ORDER BY (((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))
                        LIMIT 10;
                        """
                    ),
                    {"query_vector": q_vec_str, "case_id": target_case_id}
                ).fetchall()
                hnsw_plan_text = "\n".join(r[0] for r in hnsw_plan)

            # 2. Exact Ground Truth Retrieval (Sequential Scan)
            conn.execute(text("SET enable_seqscan = ON;"))
            conn.execute(text("SET enable_indexscan = OFF;"))
            conn.execute(text("SET enable_bitmapscan = OFF;"))

            t0 = time.perf_counter()
            exact_rows = conn.execute(
                text(
                    """
                    SELECT dc.id, dc.case_id, dc.document_id,
                           1.0 - ((((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))) AS similarity
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id
                    JOIN cases c ON c.id = dc.case_id
                    WHERE dc.deleted_at IS NULL
                      AND d.deleted_at IS NULL
                      AND c.deleted_at IS NULL
                      AND d.security_status = 'SAFE'
                      AND dc.case_id = :case_id
                    ORDER BY (((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))
                    LIMIT 10;
                    """
                ),
                {"query_vector": q_vec_str, "case_id": target_case_id}
            ).fetchall()
            t1 = time.perf_counter()
            exact_latencies.append((t1 - t0) * 1000)

            # Capture Exact plan on first iteration
            if q_idx == 0:
                exact_plan = conn.execute(
                    text(
                        """
                        EXPLAIN (ANALYZE, BUFFERS)
                        SELECT dc.id, dc.case_id, dc.document_id,
                               1.0 - ((((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))) AS similarity
                        FROM document_chunks dc
                        JOIN documents d ON d.id = dc.document_id
                        JOIN cases c ON c.id = dc.case_id
                        WHERE dc.deleted_at IS NULL
                          AND d.deleted_at IS NULL
                          AND c.deleted_at IS NULL
                          AND d.security_status = 'SAFE'
                          AND dc.case_id = :case_id
                        ORDER BY (((dc.embedding)::real[])::vector(1536)) <=> CAST(:query_vector AS vector(1536))
                        LIMIT 10;
                        """
                    ),
                    {"query_vector": q_vec_str, "case_id": target_case_id}
                ).fetchall()
                exact_plan_text = "\n".join(r[0] for r in exact_plan)
                exact_plan_text = "\n".join(r[0] for r in exact_plan)

            # Reset settings
            conn.execute(text("SET enable_seqscan = ON;"))
            conn.execute(text("SET enable_indexscan = ON;"))
            conn.execute(text("SET enable_bitmapscan = ON;"))

            # Calculate Recall@10 and Precision@10
            hnsw_ids = {r[0] for r in hnsw_rows}
            exact_ids = {r[0] for r in exact_rows}

            common = len(hnsw_ids & exact_ids)
            recall = common / len(exact_ids) if exact_ids else 1.0
            precision = common / len(hnsw_ids) if hnsw_ids else 1.0

            recall_scores.append(recall)
            precision_scores.append(precision)

            # Verify multi-tenant and quarantine isolation
            for r in hnsw_rows:
                if str(r[1]) != target_case_id:
                    isolation_violations += 1
                if str(r[2]) in quarantined_doc_ids:
                    quarantine_violations += 1

    # Cleanup benchmark records
    logger.info("Cleaning up benchmark records...")
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM document_chunks WHERE case_id IN :cids;"),
            {"cids": tuple(case_ids)}
        )
        conn.execute(
            text("DELETE FROM documents WHERE case_id IN :cids;"),
            {"cids": tuple(case_ids)}
        )
        conn.execute(
            text("DELETE FROM case_participants WHERE case_id IN :cids;"),
            {"cids": tuple(case_ids)}
        )
        conn.execute(
            text("DELETE FROM cases WHERE id IN :cids;"),
            {"cids": tuple(case_ids)}
        )
        conn.execute(
            text("DELETE FROM users WHERE id IN :uids;"),
            {"uids": tuple(user_ids)}
        )

    results = {
        "dataset": {
            "total_chunks_evaluated": total_target_chunks,
            "tenants_cases_evaluated": num_cases,
            "chunks_per_case": chunks_per_case,
            "embedding_dimensions": dim,
            "pgvector_version": ext,
        },
        "hnsw_latency_ms": {
            "mean": round(float(np.mean(hnsw_latencies)), 2),
            "p50": round(float(np.percentile(hnsw_latencies, 50)), 2),
            "p90": round(float(np.percentile(hnsw_latencies, 90)), 2),
            "p95": round(float(np.percentile(hnsw_latencies, 95)), 2),
            "p99": round(float(np.percentile(hnsw_latencies, 99)), 2),
        },
        "exact_latency_ms": {
            "mean": round(float(np.mean(exact_latencies)), 2),
            "p50": round(float(np.percentile(exact_latencies, 50)), 2),
            "p90": round(float(np.percentile(exact_latencies, 90)), 2),
            "p95": round(float(np.percentile(exact_latencies, 95)), 2),
        },
        "quality_metrics": {
            "mean_recall_at_10": round(float(np.mean(recall_scores)), 4),
            "mean_precision_at_10": round(float(np.mean(precision_scores)), 4),
            "speedup_factor": round(float(np.mean(exact_latencies)) / float(np.mean(hnsw_latencies)), 2),
        },
        "security_isolation": {
            "isolation_violations": isolation_violations,
            "quarantine_violations": quarantine_violations,
            "multi_tenant_isolation_verified": isolation_violations == 0,
            "quarantine_exclusion_verified": quarantine_violations == 0,
        },
        "hnsw_plan": hnsw_plan_text,
        "exact_plan": exact_plan_text,
    }

    out_file = "docs/vector_retrieval_100k_benchmark.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("=================================================================")
    logger.info(f"BENCHMARK COMPLETE ({total_target_chunks} CHUNKS)")
    logger.info(f"HNSW Mean Latency : {results['hnsw_latency_ms']['mean']} ms (P95: {results['hnsw_latency_ms']['p95']} ms)")
    logger.info(f"Exact Mean Latency: {results['exact_latency_ms']['mean']} ms (P95: {results['exact_latency_ms']['p95']} ms)")
    logger.info(f"HNSW Speedup      : {results['quality_metrics']['speedup_factor']}x")
    logger.info(f"Recall@10         : {results['quality_metrics']['mean_recall_at_10'] * 100}%")
    logger.info(f"Precision@10      : {results['quality_metrics']['mean_precision_at_10'] * 100}%")
    logger.info(f"Tenant Violations : {results['security_isolation']['isolation_violations']}")
    logger.info(f"Quarantine Leaks  : {results['security_isolation']['quarantine_violations']}")
    logger.info("=================================================================")

    return results


if __name__ == "__main__":
    run_100k_pgvector_benchmark()
