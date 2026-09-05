"""
CLASSIFY NODE

Decides the ticket's routing path based on all gathered signals:
- Parsed intent and confidence
- Customer tier and history
- Retrieval confidence

Returns one of three routes:
- AUTO_RESPOND: safe to auto-reply (simple question + high confidence + docs found)
- HUMAN_REVIEW: needs human sign-off (billing dispute, VIP, low confidence)
- ESCALATE: pipeline can't handle it (unknown intent, no docs, legal, deletion)

NO LLM involved. Pure rules from config/routing_rules.yaml.
This is intentional — routing decisions must be deterministic and auditable.
"""

from app.models.schemas import (
    PipelineState,
    ClassifyResult,
    Route,
    Intent,
    AccountTier,
)


# ─── Escalate rules (highest priority, checked first) ─────

ESCALATE_INTENTS = {
    Intent.ACCOUNT_DELETION,
    Intent.LEGAL_THREAT,
    Intent.UNKNOWN,
}

# ─── Human review rules ───────────────────────────────────

HUMAN_REVIEW_INTENTS = {
    Intent.BILLING_DISPUTE,
    Intent.REFUND_REQUEST,
}

HUMAN_REVIEW_TIERS = {
    AccountTier.ENTERPRISE,
}

HUMAN_REVIEW_PRIORITIES = {
    "Highest",
    "Critical",
}

FRUSTRATED_CUSTOMER_TICKET_THRESHOLD = 10

# ─── Auto-respond rules ──────────────────────────────────

AUTO_RESPOND_INTENTS = {
    Intent.HOW_TO,
    Intent.FEATURE_QUESTION,
    Intent.BILLING_FAQ,
    Intent.BUG_REPORT_KNOWN,
}

AUTO_RESPOND_TIERS = {
    AccountTier.FREE,
    AccountTier.STARTER,
    AccountTier.PRO,
}

AUTO_RESPOND_PRIORITIES = {
    "Low",
    "Medium",
    "High",
}

PARSE_CONFIDENCE_THRESHOLD = 0.5


def classify_ticket(state: PipelineState) -> PipelineState:
    """Classify node — route ticket based on deterministic rules."""

    intent = state.parsed.intent if state.parsed else Intent.UNKNOWN
    confidence = state.parsed.parse_confidence if state.parsed else 0.0
    tier = state.customer.account_tier if state.customer else AccountTier.UNKNOWN
    past_tickets = state.customer.past_ticket_count if state.customer else 0
    priority = state.input.priority
    retrieval_confident = state.retrieval.retrieval_confident if state.retrieval else False

    # ── Rule 1: Always escalate certain intents ───────────
    if intent in ESCALATE_INTENTS:
        state.classification = ClassifyResult(
            route=Route.ESCALATE,
            route_reason=f"Intent '{intent.value}' always requires human handling",
        )
        return state

    # ── Rule 2: Escalate if no relevant docs found ────────
    if not retrieval_confident:
        state.classification = ClassifyResult(
            route=Route.ESCALATE,
            route_reason="No relevant knowledge base docs found — cannot generate grounded response",
        )
        return state

    # ── Rule 3: Escalate if parse confidence too low ──────
    if confidence < PARSE_CONFIDENCE_THRESHOLD:
        state.classification = ClassifyResult(
            route=Route.ESCALATE,
            route_reason=f"Parse confidence {confidence:.2f} below threshold {PARSE_CONFIDENCE_THRESHOLD}",
        )
        return state

    # ── Rule 4: Human review for sensitive intents ────────
    if intent in HUMAN_REVIEW_INTENTS:
        state.classification = ClassifyResult(
            route=Route.HUMAN_REVIEW,
            route_reason=f"Intent '{intent.value}' requires human sign-off",
        )
        return state

    # ── Rule 5: Human review for VIP customers ────────────
    if tier in HUMAN_REVIEW_TIERS:
        state.classification = ClassifyResult(
            route=Route.HUMAN_REVIEW,
            route_reason=f"Enterprise customer — requires human review per SLA",
        )
        return state

    # ── Rule 6: Human review for critical priority ────────
    if priority in HUMAN_REVIEW_PRIORITIES:
        state.classification = ClassifyResult(
            route=Route.HUMAN_REVIEW,
            route_reason=f"Priority '{priority}' requires human review",
        )
        return state

    # ── Rule 7: Human review for frustrated customers ─────
    if past_tickets > FRUSTRATED_CUSTOMER_TICKET_THRESHOLD:
        state.classification = ClassifyResult(
            route=Route.HUMAN_REVIEW,
            route_reason=f"Customer has {past_tickets} past tickets — possible frustration, needs human touch",
        )
        return state

    # ── Rule 8: Auto-respond if all conditions met ────────
    if (
        intent in AUTO_RESPOND_INTENTS
        and tier in AUTO_RESPOND_TIERS
        and priority in AUTO_RESPOND_PRIORITIES
        and retrieval_confident
        and confidence >= PARSE_CONFIDENCE_THRESHOLD
    ):
        state.classification = ClassifyResult(
            route=Route.AUTO_RESPOND,
            route_reason=f"Simple '{intent.value}' from {tier.value} customer, docs found, confidence {confidence:.2f}",
        )
        return state

    # ── Default: human review (safe fallback) ─────────────
    state.classification = ClassifyResult(
        route=Route.HUMAN_REVIEW,
        route_reason="No auto-respond rule matched — defaulting to human review",
    )
    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import (
        TicketInput, ParsedTicket, CustomerInfo,
        RetrievalResult, RetrievedChunk,
        AccountTier, EnrichmentStatus,
    )

    test_cases = [
        {
            "name": "Simple how-to from Pro customer",
            "parsed": ParsedTicket(
                intent=Intent.HOW_TO, sub_intent="export_pdf",
                product_area="export", key_details="how to export PDF",
                parse_confidence=0.92,
            ),
            "customer": CustomerInfo(
                customer_name="Sam Wilson", company="Northwind Labs",
                account_tier=AccountTier.PRO, subscription_status="active",
                past_ticket_count=3, enrichment_status=EnrichmentStatus.FULL,
            ),
            "retrieval": RetrievalResult(
                chunks=[RetrievedChunk(source="feature-export.md", content="...", score=0.65)],
                retrieval_confident=True, query_used="export pdf",
            ),
            "priority": "Medium",
            "expected": "AUTO_RESPOND",
        },
        {
            "name": "Billing dispute from Enterprise customer",
            "parsed": ParsedTicket(
                intent=Intent.BILLING_DISPUTE, sub_intent="charged_twice",
                product_area="billing", key_details="duplicate charge",
                parse_confidence=0.95,
            ),
            "customer": CustomerInfo(
                customer_name="Priya Sharma", company="Acme Corp",
                account_tier=AccountTier.ENTERPRISE, subscription_status="active",
                past_ticket_count=5, enrichment_status=EnrichmentStatus.FULL,
            ),
            "retrieval": RetrievalResult(
                chunks=[RetrievedChunk(source="billing-refund-policy.md", content="...", score=0.7)],
                retrieval_confident=True, query_used="billing duplicate charge",
            ),
            "priority": "High",
            "expected": "HUMAN_REVIEW",
        },
        {
            "name": "Account deletion request",
            "parsed": ParsedTicket(
                intent=Intent.ACCOUNT_DELETION, sub_intent="gdpr_request",
                product_area="account", key_details="delete all data",
                parse_confidence=0.98,
            ),
            "customer": CustomerInfo(
                customer_name="Alex Chen", company="Contoso Ltd",
                account_tier=AccountTier.PRO, subscription_status="active",
                past_ticket_count=1, enrichment_status=EnrichmentStatus.FULL,
            ),
            "retrieval": RetrievalResult(
                chunks=[RetrievedChunk(source="data-security.md", content="...", score=0.5)],
                retrieval_confident=True, query_used="delete account gdpr",
            ),
            "priority": "High",
            "expected": "ESCALATE",
        },
        {
            "name": "Unknown intent, no docs found",
            "parsed": ParsedTicket(
                intent=Intent.UNKNOWN, sub_intent="parse_failure",
                product_area="unknown", key_details="unclear request",
                parse_confidence=0.2,
            ),
            "customer": CustomerInfo(
                customer_name="Unknown", company="Unknown",
                account_tier=AccountTier.UNKNOWN,
                enrichment_status=EnrichmentStatus.FAILED,
            ),
            "retrieval": RetrievalResult(
                chunks=[], retrieval_confident=False, query_used="unclear",
            ),
            "priority": "Medium",
            "expected": "ESCALATE",
        },
        {
            "name": "Simple question from frustrated customer (15 past tickets)",
            "parsed": ParsedTicket(
                intent=Intent.HOW_TO, sub_intent="invite_members",
                product_area="account", key_details="how to add team members",
                parse_confidence=0.90,
            ),
            "customer": CustomerInfo(
                customer_name="Dev Kumar", company="Umbrella Corp",
                account_tier=AccountTier.STARTER, subscription_status="active",
                past_ticket_count=15, enrichment_status=EnrichmentStatus.FULL,
            ),
            "retrieval": RetrievalResult(
                chunks=[RetrievedChunk(source="account-getting-started.md", content="...", score=0.6)],
                retrieval_confident=True, query_used="invite team members",
            ),
            "priority": "Low",
            "expected": "HUMAN_REVIEW",
        },
    ]

    print("Running classify tests...\n")

    for tc in test_cases:
        state = PipelineState(
            input=TicketInput(
                ticket_id="test", ticket_key="KAN-0",
                raw_subject="Test", raw_description="Test",
                reporter_email="test@test.com", priority=tc["priority"],
                labels=["support-ticket"],
            ),
            parsed=tc["parsed"],
            customer=tc["customer"],
            retrieval=tc["retrieval"],
        )

        result = classify_ticket(state)
        route = result.classification.route.value
        passed = "PASS" if route == tc["expected"] else "FAIL"

        print(f"  [{passed}] {tc['name']}")
        print(f"         Route: {route} | Reason: {result.classification.route_reason}")
        print()