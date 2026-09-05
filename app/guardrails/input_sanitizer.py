"""Prompt injection detection on inbound ticket text.

Ticket bodies are attacker-controlled. This does not try to be a perfect
classifier — it strips the obvious instruction-shaped content and flags
the ticket so the gate can refuse to auto-post it.
"""

import re

from app.models.schemas import GuardrailReport

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(the\s+)?(system|above|previous)",
    r"you\s+are\s+now\s+(a|an)\b",
    r"\bnew\s+(system\s+)?(prompt|instructions?)\b",
    r"</?(system|assistant|user)>",
    r"\bBEGIN\s+SYSTEM\b",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"print\s+(your\s+)?(instructions|prompt|api[_ ]?key)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# Ticket bodies past this length are almost always pasted logs; truncating
# both saves tokens and limits how much injected text can fit.
MAX_CHARS = 8000


def check(text: str) -> GuardrailReport:
    findings = [p.pattern for p in _COMPILED if p.search(text)]
    return GuardrailReport(
        name="input_sanitizer",
        passed=not findings,
        severity="warn" if findings else "info",
        findings=findings,
    )


def sanitize(text: str) -> str:
    """Neutralize instruction-shaped content and clamp length.

    Matches are replaced rather than removed so the human reviewer can
    still see that something was there.
    """
    cleaned = text[:MAX_CHARS]
    for pattern in _COMPILED:
        cleaned = pattern.sub("[redacted: possible injection]", cleaned)
    return cleaned
