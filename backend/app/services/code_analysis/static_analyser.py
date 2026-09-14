"""
Static Code Analyser — Phase 6.

Scans source code files using rule-based pattern matching and (for Python) AST inspection.
Produces raw candidate findings with file path, line numbers, pattern metadata, and code evidence.
"""
import ast

from app.models.github import FindingCategory, FindingSeverity
from app.services.code_analysis.patterns import PATTERN_LIBRARY, CodePattern


class RawFinding:
    def __init__(
        self,
        pattern_id: str,
        category: FindingCategory,
        severity: FindingSeverity,
        title: str,
        file_path: str,
        line_start: int,
        line_end: int,
        suggestion: str,
        code_evidence: str,
    ):
        self.pattern_id = pattern_id
        self.category = category
        self.severity = severity
        self.title = title
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.suggestion = suggestion
        self.code_evidence = code_evidence


class StaticCodeAnalyser:
    """Scans code contents line by line or pattern by pattern."""

    def analyse_file(self, file_path: str, content: str) -> list[RawFinding]:
        findings: list[RawFinding] = []
        lines = content.splitlines()
        ext = self._get_extension(file_path)

        # 1. Regex Pattern Matching
        for pattern in PATTERN_LIBRARY:
            if pattern.file_extensions and ext not in pattern.file_extensions:
                continue

            matches = pattern.regex.finditer(content)
            for m in matches:
                start_char, end_char = m.span()
                line_start = content[:start_char].count("\n") + 1
                line_end = content[:end_char].count("\n") + 1

                # Extract verbatim evidence around the finding (up to 3 context lines)
                ev_start = max(0, line_start - 2)
                ev_end = min(len(lines), line_end + 1)
                evidence = "\n".join(lines[ev_start:ev_end])

                findings.append(
                    RawFinding(
                        pattern_id=pattern.pattern_id,
                        category=pattern.category,
                        severity=pattern.severity,
                        title=pattern.title,
                        file_path=file_path,
                        line_start=line_start,
                        line_end=line_end,
                        suggestion=pattern.suggestion,
                        code_evidence=evidence,
                    )
                )

        # 2. Python AST Analysis (if Python file)
        if ext == ".py":
            ast_findings = self._analyse_python_ast(file_path, content, lines)
            findings.extend(ast_findings)

        return findings

    @staticmethod
    def _get_extension(file_path: str) -> str:
        idx = file_path.rfind(".")
        return file_path[idx:].lower() if idx != -1 else ""

    def _analyse_python_ast(self, file_path: str, content: str, lines: list[str]) -> list[RawFinding]:
        findings: list[RawFinding] = []
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            # If code can't be parsed as AST, skip AST checks
            return findings

        for node in ast.walk(tree):
            # AST Check 1: Mutable default argument in function definition
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        line_no = node.lineno
                        ev_start = max(0, line_no - 1)
                        ev_end = min(len(lines), line_no + 2)
                        evidence = "\n".join(lines[ev_start:ev_end])
                        findings.append(
                            RawFinding(
                                pattern_id="BUG-AST-001",
                                category=FindingCategory.BUG,
                                severity=FindingSeverity.MEDIUM,
                                title="Mutable default argument in function definition",
                                file_path=file_path,
                                line_start=line_no,
                                line_end=line_no,
                                suggestion="Use None as default value and initialize the mutable object inside the function body.",
                                code_evidence=evidence,
                            )
                        )
        return findings
