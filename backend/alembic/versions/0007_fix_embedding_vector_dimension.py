"""fix embedding_vector dimension from 384 to 768 (nomic-embed-text actual output)

Revision ID: 0007
Revises: 0006
"""
from alembic import op

revision = "0007"
down_revision = "0006_github_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old IVFFlat index (required before altering the column type)
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_vector")
    # Truncate any existing chunks with wrong-dimension vectors
    op.execute("TRUNCATE TABLE rag_chunks")
    # Alter column to correct dimension
    op.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding_vector TYPE vector(768)")
    # Recreate the IVFFlat index with the correct dimension
    # lists=100 is appropriate for up to ~1M vectors; lower for small datasets
    op.execute(
        "CREATE INDEX ix_rag_chunks_embedding_vector "
        "ON rag_chunks USING ivfflat (embedding_vector vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_vector")
    op.execute("TRUNCATE TABLE rag_chunks")
    op.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding_vector TYPE vector(384)")
    op.execute(
        "CREATE INDEX ix_rag_chunks_embedding_vector "
        "ON rag_chunks USING ivfflat (embedding_vector vector_cosine_ops) "
        "WITH (lists = 100)"
    )
