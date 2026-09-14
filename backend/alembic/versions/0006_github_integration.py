"""github integration tables

Revision ID: 0006_github_integration
Revises: 0005_rag_improvements
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_github_integration"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. github_connections
    op.create_table(
        "github_connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("github_login", sa.String(length=255), nullable=False),
        sa.Column("github_user_id", sa.Integer(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("token_scope", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_github_connections_user_id", "github_connections", ["user_id"], unique=True)

    # 2. github_repositories
    op.create_table(
        "github_repositories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("github_repo_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(length=100), nullable=False, server_default="main"),
        sa.Column("primary_language", sa.String(length=100), nullable=True),
        sa.Column("languages_json", sa.JSON(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("files_indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["github_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_github_repositories_user_id", "github_repositories", ["user_id"], unique=False)

    # 3. code_analysis_reports
    op.create_table(
        "code_analysis_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("llm_review_included", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("total_files_analysed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["github_repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_analysis_reports_repository_id", "code_analysis_reports", ["repository_id"], unique=False)
    op.create_index("ix_code_analysis_reports_user_id", "code_analysis_reports", ["user_id"], unique=False)

    # 4. code_findings
    op.create_table(
        "code_findings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("pattern_id", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("line_end", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False, server_default=""),
        sa.Column("code_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("llm_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["code_analysis_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["github_repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_findings_category", "code_findings", ["category"], unique=False)
    op.create_index("ix_code_findings_report_id", "code_findings", ["report_id"], unique=False)
    op.create_index("ix_code_findings_repository_id", "code_findings", ["repository_id"], unique=False)
    op.create_index("ix_code_findings_severity", "code_findings", ["severity"], unique=False)
    op.create_index("ix_code_findings_user_id", "code_findings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("code_findings")
    op.drop_table("code_analysis_reports")
    op.drop_table("github_repositories")
    op.drop_table("github_connections")
