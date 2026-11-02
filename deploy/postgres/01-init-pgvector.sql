-- Legal Case Companion (LCC) — Production PostgreSQL + pgvector Initialization
-- Executed on database container bootstrap

\connect legal_db;

-- 1. Enable standard UUID generator
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Enable native vector extension for legal RAG embeddings (1536-dim)
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. Verify installed extension versions
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL initialized with pgvector version: %', (SELECT extversion FROM pg_extension WHERE extname = 'vector');
END $$;
