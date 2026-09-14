"""Phase 5 — RAG schema improvements.

Revision ID: 0005
Revises: 0004

Changes:
- chat_messages: add user_id column (denormalised for fast auth checks)
- chat_messages: add index on user_id
- conversations:  add metadata_json column
- rag_chunks:     add composite btree index on (user_id, id) to support
                  efficient per-user chunk lookups separate from the ANN index.

Why add user_id to chat_messages?
  The pipeline needs to verify "this message belongs to this user" without
  always joining through conversations. Denormalising user_id makes that a
  single-column WHERE clause backed by a btree index.

Why composite index on rag_chunks(user_id, chunk_index)?
  The IVFFlat index on embedding_vector already scopes the ANN search, but
  a btree on user_id lets the planner pre-filter by user before hitting the
  vector index, which is important once a deployment has many users.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id to chat_messages for direct per-user authorization
    op.add_column(
        "chat_messages",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,  # nullable so existing rows aren't rejected
        ),
    )
    # Back-fill user_id from conversations.user_id for existing rows
    op.execute(
        """
        UPDATE chat_messages cm
        SET    user_id = c.user_id
        FROM   conversations c
        WHERE  c.id = cm.conversation_id
        """
    )
    # Now make it NOT NULL
    op.alter_column("chat_messages", "user_id", nullable=False)
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])

    # Add metadata_json to conversations
    op.add_column(
        "conversations",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    )

    # Composite btree on rag_chunks for per-user pre-filtering
    op.create_index(
        "ix_rag_chunks_user_chunk",
        "rag_chunks",
        ["user_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_rag_chunks_user_chunk", "rag_chunks")
    op.drop_column("conversations", "metadata_json")
    op.drop_index("ix_chat_messages_user_id", "chat_messages")
    op.drop_column("chat_messages", "user_id")
