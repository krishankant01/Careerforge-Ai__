"""
Report Builder — Phase 6.

Aggregates raw findings from static analysis and LLM reviews into a structured
CodeAnalysisReport and CodeFinding records. Calculates summary statistics,
severity breakdowns, category breakdowns, and top affected files.
"""
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github import (
    CodeAnalysisReport,
    CodeFinding,
    FindingCategory,
    FindingSeverity,
)
from app.services.code_analysis.static_analyser import RawFinding


class ReportBuilder:
    """Consolidates findings and persists CodeAnalysisReport + CodeFinding records."""

    @staticmethod
    async def build_and_save_report(
        db: AsyncSession,
        user_id: uuid.UUID,
        repository_id: uuid.UUID,
        raw_findings: list[RawFinding],
        total_files_analysed: int,
        llm_review_included: bool = False,
    ) -> CodeAnalysisReport:
        """Deduplicate findings, calculate summary JSON, save report & findings."""

        # 1. Deduplicate findings (same file, line, pattern)
        seen_keys: set[tuple[str, int, str]] = set()
        unique_raw: list[RawFinding] = []

        for f in raw_findings:
            key = (f.file_path, f.line_start, f.pattern_id)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_raw.append(f)

        # 2. Build breakdown counts
        by_severity = {sev.value: 0 for sev in FindingSeverity}
        by_category = {cat.value: 0 for cat in FindingCategory}
        file_counts: dict[str, int] = {}

        for f in unique_raw:
            by_severity[f.severity.value] += 1
            by_category[f.category.value] += 1
            file_counts[f.file_path] = file_counts.get(f.file_path, 0) + 1

        top_files = sorted(
            [{"file_path": k, "count": v} for k, v in file_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        summary_json = {
            "by_severity": by_severity,
            "by_category": by_category,
            "top_files": top_files,
        }

        # 3. Create Report entity
        report = CodeAnalysisReport(
            user_id=user_id,
            repository_id=repository_id,
            llm_review_included=llm_review_included,
            total_files_analysed=total_files_analysed,
            total_findings=len(unique_raw),
            summary_json=summary_json,
        )
        db.add(report)
        await db.flush()  # assign report.id

        # 4. Create CodeFinding entities
        db_findings: list[CodeFinding] = []
        for rf in unique_raw:
            desc = rf.title if rf.title else "Code issue"
            if not desc.startswith("Potential issue:"):
                desc = f"Potential issue: {desc}"

            finding = CodeFinding(
                user_id=user_id,
                report_id=report.id,
                repository_id=repository_id,
                pattern_id=rf.pattern_id,
                category=rf.category,
                severity=rf.severity,
                file_path=rf.file_path,
                line_start=rf.line_start,
                line_end=rf.line_end,
                description=desc,
                suggestion=rf.suggestion,
                code_evidence=rf.code_evidence,
            )
            db_findings.append(finding)

        db.add_all(db_findings)
        await db.commit()
        await db.refresh(report)

        return report
