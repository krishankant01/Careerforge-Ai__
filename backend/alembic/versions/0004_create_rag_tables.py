"""create RAG documents, chunks, conversations, and chat messages

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("rag_documents", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("source_type", sa.String(30), nullable=False), sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_rag_documents_user_id", "rag_documents", ["user_id"])
    op.create_table("rag_chunks", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False), sa.Column("chunk_index", sa.Integer(), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("embedding", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    # Native pgvector column and index are maintained for production similarity search.
    op.execute("ALTER TABLE rag_chunks ADD COLUMN embedding_vector vector(384)")
    op.execute("CREATE INDEX ix_rag_chunks_embedding_vector ON rag_chunks USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100)")
    op.create_index("ix_rag_chunks_user_id", "rag_chunks", ["user_id"])
    op.create_table("conversations", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_table("chat_messages", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(12), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("citations", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])

def downgrade() -> None:
    op.drop_table("chat_messages"); op.drop_table("conversations"); op.drop_table("rag_chunks"); op.drop_table("rag_documents")
