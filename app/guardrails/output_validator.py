"""Checks on the generated draft before it can be posted."""

import re

from app.models.schemas import DraftResponse, GuardrailReport, RetrievedDoc

# Phrases that mean the model is speculating rather than citing.
HEDGE_PATTERNS = [
    r"\bI (think|believe|assume)\b",
    r"\bprobably\b",
    r"\bshould be able to\b",
    r"\bas far as I know\b",
]

# Things we must never promise on the company's behalf.
FORBIDDEN_PATTERNS = [
    r"\bfull refund\b",
    r"\bwe will (definitely|certainly) (fix|resolve)\b",
    r"\bguarantee[ds]?\b",
    r"\bby (tomorrow|end of day|EOD)\b",
    r"\bSLA\b.*\b\d+\s*(hour|minute)s?\b",
]

MIN_OVERLAP = 0.30  # fraction of content words the draft shares with its sources


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def check_grounding(draft: DraftResponse, docs: list[RetrievedDoc]) -> GuardrailReport:
    """Cheap lexical grounding check.

    Not a substitute for an LLM judge — that runs in eval, where latency
    does not matter. This catches the loud failure: a confident answer
    written with no retrieved support at all.
    """
    findings = []

    if not docs and not draft.needs_customer_input:
        findings.append("Draft asserts an answer with zero retrieved documents.")

    if docs:
        source_words = set().union(*(_words(d.content) for d in docs))
        draft_words = _words(draft.body)
        if draft_words:
            overlap = len(draft_words & source_words) / len(draft_words)
            if overlap < MIN_OVERLAP:
                findings.append(f"Low overlap with sources ({overlap:.0%}).")

    for pattern in HEDGE_PATTERNS:
        if re.search(pattern, draft.body, re.IGNORECASE):
            findings.append(f"Hedging language: {pattern}")

    return GuardrailReport(
        name="grounding",
        passed=not findings,
        severity="block" if findings else "info",
        findings=findings,
    )


def check_schema(draft: DraftResponse) -> GuardrailReport:
    """Structural sanity plus commitments we are not allowed to make."""
    findings = []

    if not draft.body.strip():
        findings.append("Empty draft body.")
    if len(draft.body) > 4000:
        findings.append("Draft exceeds the 4000-character comment limit.")
    if "{" in draft.body and "}" in draft.body:
        findings.append("Unrendered template placeholder left in the body.")

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, draft.body, re.IGNORECASE):
            findings.append(f"Forbidden commitment: {pattern}")

    return GuardrailReport(
        name="schema",
        passed=not findings,
        severity="block" if findings else "info",
        findings=findings,
    )
