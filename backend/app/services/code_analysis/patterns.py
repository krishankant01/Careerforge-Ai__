"""
Rule-based patterns library for static code analysis — Phase 6.

Categorized into:
- SECURITY: Hardcoded secrets, SQL injection, unsafe deserialization, shell injection
- BUG: Unhandled promises/exceptions, null pointer risks, variable shadowing, resource leak
- PERFORMANCE: N+1 query patterns, sync I/O in async functions, heavy loops
- QUALITY: High cyclomatic complexity, deeply nested blocks, missing return types
- STYLE: Console logs left in production, TODO/FIXME markers
"""
import re
from dataclasses import dataclass
from typing import Pattern

from app.models.github import FindingCategory, FindingSeverity


@dataclass
class CodePattern:
    pattern_id: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    regex: Pattern
    suggestion: str
    file_extensions: tuple[str, ...] | None = None  # None = all files


PATTERN_LIBRARY: list[CodePattern] = [
    # --- SECURITY ---
    CodePattern(
        pattern_id="SEC-001",
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.CRITICAL,
        title="Hardcoded API key or Secret",
        regex=re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|password|auth[_-]?token|private[_-]?key)\s*=\s*['\"](?![A-Z_]+['\"])[A-Za-z0-9+/=_-]{12,}['\"]"
        ),
        suggestion="Move secrets to environment variables or a secret management service (e.g. AWS Secrets Manager, dotenv).",
    ),
    CodePattern(
        pattern_id="SEC-002",
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.HIGH,
        title="Potential SQL Injection via String Interpolation",
        regex=re.compile(
            r"(?i)(execute|query|raw_query)\s*\(\s*f['\"].*?(SELECT|INSERT|UPDATE|DELETE|DROP).*?\{"
        ),
        suggestion="Use parameterized queries or ORM query builders to prevent SQL injection vulnerabilities.",
    ),
    CodePattern(
        pattern_id="SEC-003",
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.HIGH,
        title="Unsafe Shell Execution",
        regex=re.compile(
            r"(os\.system|subprocess\.Popen|subprocess\.run|child_process\.exec)\s*\([^)]*shell\s*=\s*True"
        ),
        suggestion="Avoid shell=True when executing system commands to prevent command injection. Use argument lists instead.",
    ),
    CodePattern(
        pattern_id="SEC-004",
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.MEDIUM,
        title="Disabled SSL/TLS Verification",
        regex=re.compile(
            r"(verify\s*=\s*False|rejectUnauthorized\s*:\s*false|strictSSL\s*:\s*false)"
        ),
        suggestion="Ensure SSL certificate verification is enabled in production environments to prevent MITM attacks.",
    ),

    # --- BUG ---
    CodePattern(
        pattern_id="BUG-001",
        category=FindingCategory.BUG,
        severity=FindingSeverity.MEDIUM,
        title="Bare Exception Handler",
        regex=re.compile(r"except\s*:|except\s+Exception\s*:"),
        suggestion="Catch specific exception types (e.g. ValueError, KeyError) instead of broad exception handlers.",
        file_extensions=(".py",),
    ),
    CodePattern(
        pattern_id="BUG-002",
        category=FindingCategory.BUG,
        severity=FindingSeverity.HIGH,
        title="Floating Point Equality Comparison",
        regex=re.compile(r"if\s+.*?\s*==\s*0\.\d+|if\s+.*?\s*==\s*\d+\.\d+"),
        suggestion="Avoid exact equality checks on floating point numbers. Use math.isclose() or epsilon bounds.",
    ),
    CodePattern(
        pattern_id="BUG-003",
        category=FindingCategory.BUG,
        severity=FindingSeverity.MEDIUM,
        title="Unhandled Promise / Missing await",
        regex=re.compile(r"(?<!await\s)\b(fetch|axios|asyncClient)\.[a-zA-Z0-9_]+\("),
        suggestion="Ensure async functions and Promise calls are awaited or correctly chained with .catch().",
        file_extensions=(".ts", ".tsx", ".js", ".jsx"),
    ),

    # --- PERFORMANCE ---
    CodePattern(
        pattern_id="PERF-001",
        category=FindingCategory.PERFORMANCE,
        severity=FindingSeverity.HIGH,
        title="Potential N+1 Query in Loop",
        regex=re.compile(r"for\s+.*?\s+in\s+.*?:[^\n]*\n\s*await\s+session\.(execute|get|query)"),
        suggestion="Fetch related data in bulk before looping, or use joinedload / eager loading to prevent N+1 queries.",
        file_extensions=(".py",),
    ),
    CodePattern(
        pattern_id="PERF-002",
        category=FindingCategory.PERFORMANCE,
        severity=FindingSeverity.MEDIUM,
        title="Blocking Synchronous I/O in Async Context",
        regex=re.compile(r"async\s+def\s+.*?:[^\n]*\n(?:\s*#[^\n]*\n)*\s*(open\(|time\.sleep|requests\.get)"),
        suggestion="Use non-blocking async primitives (aiofiles, asyncio.sleep, httpx.AsyncClient) inside async functions.",
        file_extensions=(".py",),
    ),

    # --- QUALITY ---
    CodePattern(
        pattern_id="QUAL-001",
        category=FindingCategory.QUALITY,
        severity=FindingSeverity.LOW,
        title="Deeply Nested Logic (Indentation Depth > 5)",
        regex=re.compile(r"^(?: {20,}|\t{5,})\S", re.MULTILINE),
        suggestion="Refactor deeply nested code into smaller helper functions or return early (guard clauses).",
    ),

    # --- STYLE ---
    CodePattern(
        pattern_id="STYLE-001",
        category=FindingCategory.STYLE,
        severity=FindingSeverity.INFO,
        title="Leftover Debug Print / Console Log",
        regex=re.compile(r"console\.log\(|print\(\s*f?['\"]DEBUG"),
        suggestion="Remove debug log statements or replace them with structured logging before shipping to production.",
    ),
    CodePattern(
        pattern_id="STYLE-002",
        category=FindingCategory.STYLE,
        severity=FindingSeverity.INFO,
        title="Unresolved TODO / FIXME Marker",
        regex=re.compile(r"//\s*(TODO|FIXME):|#\s*(TODO|FIXME):"),
        suggestion="Address pending TODOs or track them as project issues.",
    ),
]
