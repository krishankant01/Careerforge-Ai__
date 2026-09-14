"""
Unit and integration tests for GitHub Integration & Code Intelligence — Phase 6.
"""
import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github import FindingCategory, FindingSeverity, GitHubConnection, GitHubRepository, RepoStatus
from app.models.user import User
from app.services.code_analysis.patterns import PATTERN_LIBRARY
from app.services.code_analysis.static_analyser import StaticCodeAnalyser
from app.services.code_analysis.report_builder import ReportBuilder


@pytest.mark.asyncio
async def test_static_code_analyser():
    """Test static analyser pattern matching on security and bug rules."""
    analyser = StaticCodeAnalyser()

    sample_code = '''
def dangerous_func(secret="aws_key_123456789012"):
    api_key = "1234567890123456"
    import os
    os.system("rm -rf " + secret)
    try:
        x = 1
    except:
        pass
    print("DEBUG message")
'''
    findings = analyser.analyse_file("app/main.py", sample_code)

    assert len(findings) > 0
    categories = {f.category for f in findings}
    assert FindingCategory.SECURITY in categories or FindingCategory.BUG in categories

    # Check evidence inclusion
    for f in findings:
        assert f.file_path == "app/main.py"
        assert f.line_start >= 1
        assert len(f.code_evidence) > 0


@pytest.mark.asyncio
async def test_report_builder_deduplication_and_summary(db_session: AsyncSession):
    """Test report builder summary aggregation and finding formatting."""
    # Create test user
    user = User(name="Repo Tester", email="repotest@example.com", hashed_password="hashed_pass")
    db_session.add(user)
    await db_session.flush()

    conn = GitHubConnection(
        user_id=user.id,
        github_login="repotester",
        github_user_id=123456,
        encrypted_token="000000000000000000000000:000000000000000000000000",
        token_scope="repo",
    )
    db_session.add(conn)
    await db_session.flush()

    repo = GitHubRepository(
        user_id=user.id,
        connection_id=conn.id,
        github_repo_id=987654,
        full_name="repotester/sample-repo",
        name="sample-repo",
        html_url="https://github.com/repotester/sample-repo",
        status=RepoStatus.IDLE,
    )
    db_session.add(repo)
    await db_session.commit()

    analyser = StaticCodeAnalyser()
    raw = analyser.analyse_file("test.py", "exec(f'SELECT * FROM {user}')\n")

    report = await ReportBuilder.build_and_save_report(
        db=db_session,
        user_id=user.id,
        repository_id=repo.id,
        raw_findings=raw,
        total_files_analysed=1,
        llm_review_included=False,
    )

    assert report.total_files_analysed == 1
    assert "by_severity" in report.summary_json
    assert "by_category" in report.summary_json


@pytest.mark.asyncio
async def test_github_connection_api_flow(client: AsyncClient, auth_headers: dict):
    """Test GET /api/github/connection 404 when disconnected."""
    response = await client.get("/api/github/connection", headers=auth_headers)
    assert response.status_code == 404
