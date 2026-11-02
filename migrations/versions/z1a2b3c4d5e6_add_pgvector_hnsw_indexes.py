"""add pgvector extension and document chunk hnsw index

Revision ID: z1a2b3c4d5e6
Revises: y1a2b3c4d5e6
Create Date: 2026-11-02 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'z1a2b3c4d5e6'
down_revision: Union[str, None] = 'y1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
            DO $$
            BEGIN
                BEGIN
                    CREATE EXTENSION IF NOT EXISTS vector;
                EXCEPTION WHEN undefined_file OR feature_not_supported THEN
                    RAISE NOTICE 'pgvector extension not installed on this PostgreSQL host; skipping HNSW index.';
                END;

                IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'document_chunks' AND column_name = 'embedding'
                    ) THEN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE indexname = 'ix_document_chunks_embedding_hnsw'
                        ) THEN
                            BEGIN
                                CREATE INDEX ix_document_chunks_embedding_hnsw 
                                ON document_chunks 
                                USING hnsw ((embedding::real[]::vector(1536)) vector_cosine_ops)
                                WHERE array_length(embedding, 1) = 1536;
                            EXCEPTION WHEN OTHERS THEN
                                NULL;
                            END;
                        END IF;
                    END IF;
                END IF;
            END $$;
        """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;"))
