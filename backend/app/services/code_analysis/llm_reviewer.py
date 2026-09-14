"""
LLM-assisted Code Reviewer — Phase 6.

Sends code snippets or key repository files to LLM to detect non-obvious design flaws,
potential security flaws, and performance bottlenecks that static rules cannot catch.

Requirements:
- Always label findings as potential issues.
- Provide exact line range and evidence snippet.
"""
import logging
from app.models.github import FindingCategory, FindingSeverity
from app.services.ai import get_ai_provider
from app.services.code_analysis.static_analyser import RawFinding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert static code reviewer and software security auditor.
Your job is to review source code and identify potential security risks, bugs, performance bottlenecks, or quality issues.

RULES:
1. NEVER claim an issue is definitely exploitable or guaranteed to fail. Always label findings as "Potential issue: ...".
2. Only output JSON matching the requested structure.
3. Every finding MUST include line_start, line_end, category, severity, description, suggestion, and code_evidence.
4. Categories allowed: "security", "bug", "performance", "quality", "style".
5. Severities allowed: "critical", "high", "medium", "low", "info".
"""

USER_PROMPT_TEMPLATE = """Review the following source code file and identify potential issues.

File Path: {file_path}

Source Code:
```
{content}
```

Return a JSON object:
{{
  "findings": [
    {{
      "pattern_id": "LLM-REVIEW",
      "category": "security | bug | performance | quality | style",
      "severity": "critical | high | medium | low | info",
      "title": "Short title",
      "line_start": 1,
      "line_end": 5,
      "description": "Potential issue: ...",
      "suggestion": "Recommended fix...",
      "code_evidence": "Verbatim lines of code from snippet"
    }}
  ]
}}
If no potential issues are found, return {{"findings": []}}.
"""


class LLMCodeReviewer:
    """Uses LLM to perform deep semantic review of source files."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def review_file(self, file_path: str, content: str) -> list[RawFinding]:
        """Review file content using LLM provider."""
        if not self.ai_provider or not content.strip() or len(content) > 15000:
            return []

        user_prompt = USER_PROMPT_TEMPLATE.format(file_path=file_path, content=content[:12000])

        try:
            data = await self.ai_provider.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=1500,
            )
            return self._parse_findings(file_path, data)
        except Exception as e:
            logger.warning(f"LLM code review failed for {file_path}: {e}")
            return []

    def _parse_findings(self, file_path: str, data: dict) -> list[RawFinding]:
        findings: list[RawFinding] = []
        try:
            items = data.get("findings", [])
            for item in items:
                cat_str = item.get("category", "quality").lower()
                sev_str = item.get("severity", "medium").lower()

                category = FindingCategory(cat_str) if cat_str in FindingCategory._value2member_map_ else FindingCategory.QUALITY
                severity = FindingSeverity(sev_str) if sev_str in FindingSeverity._value2member_map_ else FindingSeverity.MEDIUM

                desc = item.get("description", "")
                if not desc.startswith("Potential issue:"):
                    desc = f"Potential issue: {desc}"

                findings.append(
                    RawFinding(
                        pattern_id=item.get("pattern_id", "LLM-REVIEW"),
                        category=category,
                        severity=severity,
                        title=item.get("title", "LLM Detected Issue"),
                        file_path=file_path,
                        line_start=int(item.get("line_start", 1)),
                        line_end=int(item.get("line_end", 1)),
                        suggestion=item.get("suggestion", ""),
                        code_evidence=item.get("code_evidence", ""),
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to parse LLM code review output for {file_path}: {e}")

        return findings
