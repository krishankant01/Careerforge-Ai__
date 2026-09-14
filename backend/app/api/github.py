"""
GitHub Integration and Code Intelligence API endpoints — Phase 6.
"""
import uuid
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.integrations.github_client import GitHubClient, decrypt_token, encrypt_token
from app.models.github import (
    CodeAnalysisReport,
    CodeFinding,
    FindingCategory,
    FindingSeverity,
    GitHubConnection,
    GitHubRepository,
    RepoStatus,
)
from app.models.user import User
from app.rag.pipeline import RAGPipeline
from app.schemas.github import (
    AnalyzeRepoRequest,
    CodeAnalysisReportResponse,
    CodebaseQAQuery,
    CodebaseQAResponse,
    CodeFindingResponse,
    GitHubConnectionResponse,
    GitHubConnectOAuthRequest,
    GitHubConnectPATRequest,
    GitHubRepositoryResponse,
)
from app.workers.github_worker import sync_and_analyze_repository

router = APIRouter(prefix="/github", tags=["GitHub Integration"])


# 1. CONNECT PAT
@router.post("/connect/pat", response_model=GitHubConnectionResponse, status_code=status.HTTP_201_CREATED)
async def connect_pat(
    payload: GitHubConnectPATRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a GitHub account using a Personal Access Token."""
    token = payload.personal_access_token.strip()
    client = GitHubClient(access_token=token)

    try:
        profile = await client.get_user_profile()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GitHub PAT or network error: {e}",
        )

    # Check for existing connection
    stmt = select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    enc_token = encrypt_token(token)

    if existing:
        existing.github_login = profile["login"]
        existing.github_user_id = profile["id"]
        existing.avatar_url = profile.get("avatar_url")
        existing.encrypted_token = enc_token
        existing.token_scope = "pat"
        connection = existing
    else:
        connection = GitHubConnection(
            user_id=current_user.id,
            github_login=profile["login"],
            github_user_id=profile["id"],
            avatar_url=profile.get("avatar_url"),
            encrypted_token=enc_token,
            token_scope="pat",
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)
    return connection


# 2. CONNECT OAUTH
@router.post("/connect/oauth", response_model=GitHubConnectionResponse, status_code=status.HTTP_201_CREATED)
async def connect_oauth(
    payload: GitHubConnectOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange GitHub OAuth code for access token and connect account."""
    try:
        token_data = await GitHubClient.exchange_code_for_token(payload.code)
        access_token = token_data["access_token"]
        scope = token_data.get("scope", "")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    client = GitHubClient(access_token=access_token)
    profile = await client.get_user_profile()

    stmt = select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    enc_token = encrypt_token(access_token)

    if existing:
        existing.github_login = profile["login"]
        existing.github_user_id = profile["id"]
        existing.avatar_url = profile.get("avatar_url")
        existing.encrypted_token = enc_token
        existing.token_scope = scope
        connection = existing
    else:
        connection = GitHubConnection(
            user_id=current_user.id,
            github_login=profile["login"],
            github_user_id=profile["id"],
            avatar_url=profile.get("avatar_url"),
            encrypted_token=enc_token,
            token_scope=scope,
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)
    return connection


# 3. GET CONNECTION
@router.get("/connection", response_model=GitHubConnectionResponse)
async def get_connection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get connected GitHub account info."""
    stmt = select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    connection = res.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No GitHub account connected.")
    return connection


# 4. DISCONNECT
@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_github(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect GitHub account and delete synced repos."""
    stmt = select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    connection = res.scalar_one_or_none()
    if connection:
        await db.delete(connection)
        await db.commit()
    return None


# 5. FETCH REMOTE REPOS FROM GITHUB
@router.get("/repos/remote", response_model=list[dict[str, Any]])
async def fetch_remote_repos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List accessible repositories from GitHub API."""
    stmt = select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    connection = res.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub not connected.")

    token = decrypt_token(connection.encrypted_token)
    client = GitHubClient(access_token=token)
    try:
        repos = await client.list_repositories()
        return [
            {
                "github_repo_id": r["id"],
                "full_name": r["full_name"],
                "name": r["name"],
                "description": r.get("description"),
                "default_branch": r.get("default_branch", "main"),
                "primary_language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "is_private": r.get("private", False),
                "html_url": r["html_url"],
            }
            for r in repos
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 6. SELECT REPO TO TRACK
@router.post("/repos/select", response_model=GitHubRepositoryResponse, status_code=status.HTTP_201_CREATED)
async def select_repository(
    github_repo_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Select a repository to track and sync."""
    conn_stmt = select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    conn_res = await db.execute(conn_stmt)
    connection = conn_res.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub not connected.")

    # Check if already tracked
    stmt = select(GitHubRepository).where(
        GitHubRepository.user_id == current_user.id,
        GitHubRepository.github_repo_id == github_repo_id,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    token = decrypt_token(connection.encrypted_token)
    client = GitHubClient(access_token=token)

    remote_repos = await client.list_repositories()
    target = next((r for r in remote_repos if r["id"] == github_repo_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found on GitHub.")

    repo = GitHubRepository(
        user_id=current_user.id,
        connection_id=connection.id,
        github_repo_id=target["id"],
        full_name=target["full_name"],
        name=target["name"],
        description=target.get("description"),
        default_branch=target.get("default_branch", "main"),
        primary_language=target.get("language"),
        languages_json={},
        stars=target.get("stargazers_count", 0),
        is_private=target.get("private", False),
        html_url=target["html_url"],
        status=RepoStatus.IDLE,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo


# 7. LIST TRACKED REPOS
@router.get("/repos", response_model=list[GitHubRepositoryResponse])
async def list_tracked_repos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tracked repositories for current user."""
    stmt = (
        select(GitHubRepository)
        .where(GitHubRepository.user_id == current_user.id)
        .order_by(desc(GitHubRepository.created_at))
    )
    res = await db.execute(stmt)
    return res.scalars().all()


# 8. GET TRACKED REPO DETAILS
@router.get("/repos/{repo_id}", response_model=GitHubRepositoryResponse)
async def get_tracked_repo(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get tracked repository status and info."""
    stmt = select(GitHubRepository).where(
        GitHubRepository.id == repo_id, GitHubRepository.user_id == current_user.id
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    return repo


# 9. TRIGGER REPO ANALYSIS
@router.post("/repos/{repo_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    repo_id: uuid.UUID,
    payload: AnalyzeRepoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger sync, static analysis, code RAG indexing, and optional LLM review."""
    stmt = select(GitHubRepository).where(
        GitHubRepository.id == repo_id, GitHubRepository.user_id == current_user.id
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    repo.status = RepoStatus.SYNCING
    await db.commit()

    background_tasks.add_task(
        sync_and_analyze_repository,
        db=db,
        repo_id=repo.id,
        user_id=current_user.id,
        include_llm=payload.include_llm_review,
    )
    return {"message": "Repository analysis started.", "repository_id": repo.id}


# 10. GET LATEST REPORT
@router.get("/repos/{repo_id}/reports/latest", response_model=CodeAnalysisReportResponse | None)
async def get_latest_report(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest analysis report for a repository."""
    stmt = (
        select(CodeAnalysisReport)
        .where(CodeAnalysisReport.repository_id == repo_id, CodeAnalysisReport.user_id == current_user.id)
        .order_by(desc(CodeAnalysisReport.created_at))
        .limit(1)
    )
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    return report


# 11. LIST FINDINGS
@router.get("/repos/{repo_id}/findings", response_model=list[CodeFindingResponse])
async def list_findings(
    repo_id: uuid.UUID,
    category: FindingCategory | None = Query(None),
    severity: FindingSeverity | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List code findings for a repository with optional filters."""
    # Find latest report
    rep_stmt = (
        select(CodeAnalysisReport)
        .where(CodeAnalysisReport.repository_id == repo_id, CodeAnalysisReport.user_id == current_user.id)
        .order_by(desc(CodeAnalysisReport.created_at))
        .limit(1)
    )
    rep_res = await db.execute(rep_stmt)
    report = rep_res.scalar_one_or_none()
    if not report:
        return []

    stmt = select(CodeFinding).where(
        CodeFinding.report_id == report.id, CodeFinding.user_id == current_user.id
    )
    if category:
        stmt = stmt.where(CodeFinding.category == category)
    if severity:
        stmt = stmt.where(CodeFinding.severity == severity)

    stmt = stmt.order_by(desc(CodeFinding.severity))
    res = await db.execute(stmt)
    return res.scalars().all()


# 12. CODEBASE QA (RAG CHAT)
@router.post("/qa", response_model=CodebaseQAResponse)
async def query_codebase(
    payload: CodebaseQAQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query ingested codebase using RAG vector similarity search."""
    pipeline = RAGPipeline()
    chunks = await pipeline.search(
        db=db,
        user_id=current_user.id,
        question=payload.query,
        source_types=["codebase"],
        top_k=5,
    )

    if not chunks:
        return CodebaseQAResponse(
            answer="No relevant code sections found in your indexed repositories.",
            citations=[],
        )

    context_parts = []
    citations = []
    for idx, c in enumerate(chunks, 1):
        file_path = c.document.metadata_json.get("file_path", c.document.title)
        context_parts.append(f"[Source {idx}: {file_path}]\n{c.chunk.content}")
        citations.append({
            "source": file_path,
            "snippet": c.chunk.content[:200],
            "score": round(c.score, 3),
        })

    full_context = "\n\n".join(context_parts)
    answer = await pipeline._call_llm(payload.query, full_context, history="")
    return CodebaseQAResponse(answer=answer, citations=citations)
