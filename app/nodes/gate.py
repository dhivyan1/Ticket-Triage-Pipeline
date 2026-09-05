"""
GATE NODE

Final checkpoint before anything gets posted to Jira.
Takes the route from Classify + guardrail results from Generate
and makes one decision:

- AUTO_POST: response goes directly to Jira (customer sees it)
- QUEUED_FOR_REVIEW: draft posted as internal comment for human approval
- ESCALATED: no response generated, just context passed to human

Gate can OVERRIDE Classify's decision. If Classify said AUTO_RESPOND
but guardrails failed or confidence is low, Gate downgrades to
QUEUED_FOR_REVIEW. Gate never upgrades — it only makes things safer.

No LLM involved. Pure decision logic.
"""

from app.config import GATE_CONFIDENCE_THRESHOLD
from app.models.schemas import (
    PipelineState,
    GateResult,
    GateDecision,
    Route,
)


def gate_decision(state: PipelineState) -> PipelineState:
    """Gate node — final decision: post, queue, or escalate."""

    route = state.classification.route if state.classification else Route.ESCALATE

    # ── ESCALATE: no response was generated ───────────────
    if route == Route.ESCALATE:
        state.gate = GateResult(
            decision=GateDecision.ESCALATED,
            reviewer=None,
        )
        return state

    # ── No generation output (shouldn't happen, but safe) ─
    if not state.generation:
        state.gate = GateResult(
            decision=GateDecision.ESCALATED,
            reviewer=None,
        )
        return state

    # ── Check if guardrails passed ────────────────────────
    guardrails_passed = state.guardrails.all_passed if state.guardrails else False

    # ── Check confidence ──────────────────────────────────
    confidence_ok = state.generation.confidence >= GATE_CONFIDENCE_THRESHOLD

    # ── Check if generation already flagged for review ────
    flagged = state.generation.needs_human_review

    # ── AUTO_RESPOND path ─────────────────────────────────
    if route == Route.AUTO_RESPOND:
        if guardrails_passed and confidence_ok and not flagged:
            state.gate = GateResult(
                decision=GateDecision.AUTO_POST,
                reviewer=None,
            )
        else:
            # Gate overrides — downgrade to review
            reasons = []
            if not guardrails_passed:
                reasons.append("guardrails failed")
            if not confidence_ok:
                reasons.append(f"confidence {state.generation.confidence:.2f} below {GATE_CONFIDENCE_THRESHOLD}")
            if flagged:
                reasons.append("flagged by generate node")

            state.gate = GateResult(
                decision=GateDecision.QUEUED_FOR_REVIEW,
                reviewer=f"Gate override: {', '.join(reasons)}",
            )
        return state

    # ── HUMAN_REVIEW path ─────────────────────────────────
    if route == Route.HUMAN_REVIEW:
        state.gate = GateResult(
            decision=GateDecision.QUEUED_FOR_REVIEW,
            reviewer=state.classification.route_reason if state.classification else "Unknown",
        )
        return state

    # ── Default: queue for review (safe fallback) ─────────
    state.gate = GateResult(
        decision=GateDecision.QUEUED_FOR_REVIEW,
        reviewer="No matching gate rule — defaulting to review",
    )
    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import (
        TicketInput, ParsedTicket, CustomerInfo, RetrievalResult,
        RetrievedChunk, ClassifyResult, GeneratedResponse,
        GuardrailResult, Intent, AccountTier, EnrichmentStatus,
    )

    test_cases = [
        {
            "name": "Auto-respond, all checks pass",
            "route": Route.AUTO_RESPOND,
            "confidence": 0.92,
            "guardrails_pass": True,
            "flagged": False,
            "expected": "AUTO_POST",
        },
        {
            "name": "Auto-respond, but guardrails failed",
            "route": Route.AUTO_RESPOND,
            "confidence": 0.92,
            "guardrails_pass": False,
            "flagged": False,
            "expected": "QUEUED_FOR_REVIEW",
        },
        {
            "name": "Auto-respond, but low confidence",
            "route": Route.AUTO_RESPOND,
            "confidence": 0.60,
            "guardrails_pass": True,
            "flagged": False,
            "expected": "QUEUED_FOR_REVIEW",
        },
        {
            "name": "Auto-respond, but flagged by generate",
            "route": Route.AUTO_RESPOND,
            "confidence": 0.92,
            "guardrails_pass": True,
            "flagged": True,
            "expected": "QUEUED_FOR_REVIEW",
        },
        {
            "name": "Human review route",
            "route": Route.HUMAN_REVIEW,
            "confidence": 0.95,
            "guardrails_pass": True,
            "flagged": False,
            "expected": "QUEUED_FOR_REVIEW",
        },
        {
            "name": "Escalate route",
            "route": Route.ESCALATE,
            "confidence": 0.0,
            "guardrails_pass": True,
            "flagged": False,
            "expected": "ESCALATED",
        },
    ]

    print("Running gate tests...\n")

    for tc in test_cases:
        state = PipelineState(
            input=TicketInput(
                ticket_id="test", ticket_key="KAN-0",
                raw_subject="Test", raw_description="Test",
                reporter_email="test@test.com", priority="Medium",
                labels=["support-ticket"],
            ),
            classification=ClassifyResult(
                route=tc["route"],
                route_reason="Test reason",
            ),
            generation=GeneratedResponse(
                response_text="Test response",
                sources_used=["test.md"],
                confidence=tc["confidence"],
                suggested_category="test",
                needs_human_review=tc["flagged"],
            ) if tc["route"] != Route.ESCALATE else None,
            guardrails=GuardrailResult(
                schema_valid=True,
                hallucination_detected=not tc["guardrails_pass"],
                pii_detected=False,
                injection_detected=False,
            ),
        )

        result = gate_decision(state)
        decision = result.gate.decision.value
        passed = "PASS" if decision == tc["expected"] else "FAIL"

        reviewer_info = f" | Reviewer: {result.gate.reviewer}" if result.gate.reviewer else ""
        print(f"  [{passed}] {tc['name']}")
        print(f"         Decision: {decision}{reviewer_info}")
        print()