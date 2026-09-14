"""
GitHub Background Sync & Analysis Worker — Phase 6.

Handles repository structure ingestion, static code analysis, optional LLM review,
and vector database indexing asynchronously.
"""
import asyncio
import uuid
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github import GitHubConnection, GitHubRepository, RepoStatus
from app.integrations.github_client import GitHubClient, decrypt_token
from app.services.code_analysis.static_analyser import StaticCodeAnalyser, RawFinding
from app.services.code_analysis.llm_reviewer import LLMCodeReviewer
from app.services.code_analysis.report_builder import ReportBuilder
from app.services.code_analysis.code_ingestion import CodeIngestionService
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# File extensions to include for analysis & ingestion
ALLOWED_EXTENSIONS = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".c", ".cpp", ".h", ".cs",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sql", ".sh", ".yaml", ".yml", ".md"
)

# Directories to skip (framework assets, migrations, builds, vendor libs)
SKIP_DIRS = (
    "node_modules/", "vendor/", ".git/", "__pycache__/", "dist/", "build/",
    ".next/", "venv/", ".venv/", "target/", "static/", "assets/", "media/",
    "migrations/", "public/", "coverage/", ".github/", ".idea/", ".vscode/",
    "site-packages/", "htmlcov/", "out/", "bin/", "obj/"
)

# File patterns to skip
SKIP_FILE_PATTERNS = (
    ".min.js", ".min.css", ".map", ".bundle.js", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "LICENSE", "CHANGELOG"
)


async def sync_and_analyze_repository(
    db: AsyncSession,
    repo_id: uuid.UUID,
    user_id: uuid.UUID,
    include_llm: bool = False,
) -> None:
    """Background task to fetch tree, analyze code, index vectors, and save report."""
    settings = get_settings()
    logger.info(f"Starting sync & analysis for repo {repo_id} (user {user_id})")

    # 1. Fetch Repository and Connection
    stmt = (
        select(GitHubRepository)
        .where(GitHubRepository.id == repo_id, GitHubRepository.user_id == user_id)
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        logger.error(f"Repository {repo_id} not found for sync.")
        return

    conn_stmt = select(GitHubConnection).where(GitHubConnection.user_id == user_id)
    conn_res = await db.execute(conn_stmt)
    connection = conn_res.scalar_one_or_none()
    if not connection:
        repo.status = RepoStatus.FAILED
        repo.error_message = "GitHub connection not found."
        await db.commit()
        return

    # Update status to SYNCING
    repo.status = RepoStatus.SYNCING
    repo.error_message = None
    await db.commit()

    try:
        # Decrypt token
        plain_token = decrypt_token(connection.encrypted_token)
        client = GitHubClient(access_token=plain_token)

        owner, repo_name = repo.full_name.split("/", 1)

        # 2. Fetch Repository Tree
        tree = await client.get_tree(owner=owner, repo=repo_name, branch=repo.default_branch)

        # 3. Filter files
        max_size_bytes = settings.CODE_ANALYSIS_MAX_FILE_KB * 1024
        code_files = []
        for item in tree:
            if item.get("type") == "blob":
                path = item.get("path", "")
                # Skip non-source directories
                if any(d in path for d in SKIP_DIRS):
                    continue
                # Skip minified / lock files
                if any(pat in path for pat in SKIP_FILE_PATTERNS):
                    continue
                if path.endswith(ALLOWED_EXTENSIONS):
                    size = item.get("size", 0)
                    if size <= max_size_bytes:
                        code_files.append(path)

        # Cap files per sync for fast response (max 60 core files)
        max_files = min(settings.CODE_ANALYSIS_MAX_REPO_FILES, 60)
        code_files = code_files[:max_files]
        logger.info(f"Selected {len(code_files)} code files for analysis in {repo.full_name}")

        # 4. Fetch file contents concurrently (up to 8 requests at once)
        semaphore = asyncio.Semaphore(8)

        async def fetch_file(path: str):
            async with semaphore:
                try:
                    content = await client.get_file_content(owner=owner, repo=repo_name, path=path, branch=repo.default_branch)
                    return path, content
                except Exception as ex:
                    logger.warning(f"Error fetching {path}: {ex}")
                    return path, None

        fetched_results = await asyncio.gather(*(fetch_file(path) for path in code_files))
        valid_files = [(path, content) for path, content in fetched_results if content]

        # 5. Analyze & Ingest
        analyser = StaticCodeAnalyser()
        llm_reviewer = LLMCodeReviewer() if include_llm else None
        ingestion_service = CodeIngestionService(db)

        all_raw_findings: list[RawFinding] = []
        files_indexed = 0

        # LLM review candidates: limit to top 8 key source files to maintain speed
        llm_files_set = set()
        if llm_reviewer:
            llm_candidates = [
                path for path, _ in valid_files
                if path.endswith((".py", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cpp", ".cs"))
                and not any(k in path.lower() for k in ["test", "spec", "config", "d.ts"])
            ][:8]
            llm_files_set = set(llm_candidates)

        for file_path, content in valid_files:
            try:
                # Run static pattern analysis
                static_findings = analyser.analyse_file(file_path, content)
                all_raw_findings.extend(static_findings)

                # Run optional LLM review on key files only
                if llm_reviewer and file_path in llm_files_set:
                    llm_findings = await llm_reviewer.review_file(file_path, content)
                    all_raw_findings.extend(llm_findings)

                # RAG Codebase Ingestion
                await ingestion_service.ingest_code_file(
                    user_id=user_id,
                    repo_id=repo_id,
                    repo_name=repo.full_name,
                    file_path=file_path,
                    content=content,
                )
                files_indexed += 1
            except Exception as fe:
                logger.warning(f"Error processing file {file_path} in {repo.full_name}: {fe}")

        # 6. Build Report & Findings
        report = await ReportBuilder.build_and_save_report(
            db=db,
            user_id=user_id,
            repository_id=repo_id,
            raw_findings=all_raw_findings,
            total_files_analysed=files_indexed,
            llm_review_included=include_llm,
        )

        # Update repo status
        repo.status = RepoStatus.INDEXED
        repo.files_indexed = files_indexed
        await db.commit()

        logger.info(f"Completed analysis for {repo.full_name}: {len(all_raw_findings)} findings across {files_indexed} files.")
    except Exception as e:
        logger.exception(f"Repository sync failed for {repo_id}: {e}")
        repo.status = RepoStatus.FAILED
        repo.error_message = str(e)
        await db.commit()
