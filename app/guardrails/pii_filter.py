"""Redact PII before anything is written back to Jira.

Ticket comments are visible to everyone on the project, and the model
happily echoes whatever the customer pasted in — card numbers, tokens,
other people's addresses. This strips them on the way out.
"""

import re

from app.models.schemas import GuardrailReport

PATTERNS: dict[str, str] = {
    "email": r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b",
    "phone": r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "api_key": r"\b(?:sk|pat|ghp|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b",
    "bearer_token": r"\bBearer\s+[A-Za-z0-9._-]{20,}\b",
    "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
}

_COMPILED = {name: re.compile(p) for name, p in PATTERNS.items()}


def check(text: str) -> GuardrailReport:
    findings = [name for name, p in _COMPILED.items() if p.search(text)]
    return GuardrailReport(
        name="pii_filter",
        passed=not findings,
        # Not blocking: redact() runs on the way out, so a hit is
        # recorded for the audit trail rather than held for a human.
        severity="warn" if findings else "info",
        findings=findings,
    )


def redact(text: str) -> str:
    for name, pattern in _COMPILED.items():
        text = pattern.sub(f"[{name} redacted]", text)
    return text
