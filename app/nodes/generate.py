"""
GENERATE NODE

Takes everything gathered so far:
- Ticket subject + description (from Parse)
- Customer name, tier, history (from Enrich)
- Relevant doc chunks (from Retrieve)
- Route decision (from Classify)

Drafts a response using the LLM with strict constraints:
- ONLY use info from the retrieved docs
- Match tone to customer tier
- Output structured JSON (response_text, sources_used, confidence)

Then runs guardrail checks on the output:
- Schema validation
- Hallucination check
- PII detection
- Prompt injection detection

Skipped entirely if route = ESCALATE (nothing to generate).
"""

import re
from app.config import get_llm
from app.models.schemas import (
    PipelineState,
    GeneratedResponse,
    GuardrailResult,
    Route,
)


GENERATE_SYSTEM_PROMPT = """You are a support agent for CloudDash, a project management and analytics dashboard SaaS product.

Draft a response to the customer's support ticket using ONLY the provided documentation.

## Rules:
1. ONLY use information from the "Relevant documentation" section below. Do not make up information.
2. If the docs don't fully answer the question, say "I'll connect you with a team member who can help further."
3. Be concise — under 200 words.
4. Do NOT mention internal systems, ticket IDs, or pipeline details.
5. Do NOT promise refunds, account changes, or any action — only provide information and steps.
6. Address the customer by first name.

## Tone:
- Enterprise customers: professional, formal
- Pro customers: friendly but professional
- Starter/Free customers: casual, friendly

Respond ONLY with valid JSON. No markdown, no extra text."""

GENERATE_USER_PROMPT = """Customer info:
  Name: {customer_name}
  Company: {company}
  Plan: {tier}
  Past tickets: {past_tickets}

Ticket:
  Subject: {subject}
  Description: {description}

Relevant documentation:
{docs_context}

Respond as JSON: {{"response_text": "...", "sources_used": ["source1.md", ...], "confidence": 0.0, "suggested_category": "..."}}"""


def build_docs_context(state: PipelineState) -> str:
    """Format retrieved chunks for the prompt."""
    if not state.retrieval or not state.retrieval.chunks:
        return "  No relevant documentation found."

    parts = []
    for i, chunk in enumerate(state.retrieval.chunks):
        parts.append(f"  [{i+1}] Source: {chunk.source}\n  {chunk.content}")

    return "\n\n".join(parts)


def check_hallucination(response_text: str, chunks: list) -> bool:
    """Basic hallucination check — flag if response mentions specifics not in any chunk.
    
    Returns True if hallucination detected.
    """
    if not chunks:
        return True  # no docs = any specific claim is hallucinated

    # Combine all chunk content
    all_docs = " ".join(c.content.lower() for c in chunks)

    # Check for common hallucination patterns:
    # prices, timeframes, guarantees not in the docs
    price_pattern = re.findall(r'\$[\d,]+(?:\.\d{2})?', response_text)
    for price in price_pattern:
        if price not in all_docs:
            return True

    return False


def check_pii(response_text: str) -> bool:
    """Check for PII patterns that shouldn't be in the response.
    
    Returns True if PII detected.
    """
    patterns = [
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # credit card
        r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b',                  # SSN
        r'\b\d{10,}\b',                                      # long number (account ID)
    ]

    for pattern in patterns:
        if re.search(pattern, response_text):
            return True

    return False


def check_injection(response_text: str) -> bool:
    """Check if the response indicates the LLM followed injected instructions.
    
    Returns True if injection detected.
    """
    injection_signals = [
        "refund approved",
        "refund processed",
        "account deleted",
        "password changed",
        "i have approved",
        "i have processed",
        "action completed",
        "i will now",
    ]

    response_lower = response_text.lower()
    for signal in injection_signals:
        if signal in response_lower:
            return True

    return False


def generate_response(state: PipelineState) -> PipelineState:
    """Generate node — draft response using LLM with all context."""

    # Skip if route is ESCALATE — nothing to generate
    if state.classification and state.classification.route == Route.ESCALATE:
        state.generation = None
        state.guardrails = GuardrailResult(
            guardrail_notes="Skipped — ticket routed to ESCALATE",
        )
        return state

    llm = get_llm()

    # Build the prompt
    customer_name = state.customer.customer_name if state.customer else "Customer"
    company = state.customer.company if state.customer else "Unknown"
    tier = state.customer.account_tier.value if state.customer else "unknown"
    past_tickets = state.customer.past_ticket_count if state.customer else 0

    docs_context = build_docs_context(state)

    prompt = GENERATE_USER_PROMPT.format(
        customer_name=customer_name,
        company=company,
        tier=tier,
        past_tickets=past_tickets,
        subject=state.input.raw_subject,
        description=state.input.raw_description,
        docs_context=docs_context,
    )

    # Call LLM with structured output
    try:
        structured_llm = llm.with_structured_output(GeneratedResponse)
        generated = structured_llm.invoke(
            [
                {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        state.generation = generated

    except Exception as e:
        print(f"  Generate failed: {e}")
        state.generation = GeneratedResponse(
            response_text="I apologize for the inconvenience. Let me connect you with a team member who can assist you directly.",
            sources_used=[],
            confidence=0.0,
            suggested_category="unknown",
            needs_human_review=True,
        )
        state.guardrails = GuardrailResult(
            schema_valid=False,
            guardrail_notes=f"LLM output failed to parse: {str(e)[:100]}",
        )
        return state

    # ─── Run guardrail checks ────────────────────────────

    chunks = state.retrieval.chunks if state.retrieval else []
    response_text = state.generation.response_text

    hallucination = check_hallucination(response_text, chunks)
    pii = check_pii(response_text)
    injection = check_injection(response_text)

    notes = []
    if hallucination:
        notes.append("Possible hallucination: price/detail not found in source docs")
    if pii:
        notes.append("PII detected in response")
    if injection:
        notes.append("Prompt injection detected: response contains action language")

    state.guardrails = GuardrailResult(
        schema_valid=True,
        hallucination_detected=hallucination,
        pii_detected=pii,
        injection_detected=injection,
        guardrail_notes="; ".join(notes) if notes else "All checks passed",
    )

    # If any guardrail fails, flag for human review
    if not state.guardrails.all_passed:
        state.generation.needs_human_review = True

    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import (
        TicketInput, ParsedTicket, CustomerInfo, RetrievalResult,
        RetrievedChunk, ClassifyResult, Intent, AccountTier,
        EnrichmentStatus, Route,
    )

    # Test: PDF export issue from a Pro customer
    test_state = PipelineState(
        input=TicketInput(
            ticket_id="12345",
            ticket_key="KAN-14",
            raw_subject="PDF export not working - just spins forever",
            raw_description="Customer: sam.wilson@northwind.io\n\nWhen I click Export > PDF on my dashboard, the spinner just runs and never stops. I've waited 10 minutes. Using Chrome on macOS.",
            reporter_email="sam.wilson@northwind.io",
            priority="High",
            labels=["support-ticket", "bug"],
        ),
        parsed=ParsedTicket(
            intent=Intent.BUG_REPORT_KNOWN,
            sub_intent="pdf_export_hanging",
            product_area="export",
            key_details="PDF export spinner runs forever, Chrome, macOS",
            parse_confidence=0.92,
        ),
        customer=CustomerInfo(
            customer_name="Sam Wilson",
            company="Northwind Labs",
            account_tier=AccountTier.PRO,
            subscription_status="active",
            past_ticket_count=3,
            enrichment_status=EnrichmentStatus.FULL,
        ),
        retrieval=RetrievalResult(
            chunks=[
                RetrievedChunk(
                    source="known-issues.md",
                    content="## PDF export timeout on Chrome (reported August 2026)\n**Status**: Fix in progress, expected within 48 hours.\n**Affected**: Chrome browser on all operating systems.\n**Symptoms**: Clicking \"Export as PDF\" causes the spinner to run indefinitely.\n**Workaround**: Clear your browser cache (Settings > Privacy > Clear browsing data), then retry. Alternatively, use Firefox or Safari.",
                    score=0.77,
                ),
                RetrievedChunk(
                    source="feature-export.md",
                    content="## Troubleshooting export issues\n- **PDF export hangs or spins**: Clear your browser cache and retry. If the issue persists, try a different browser. This is a known issue with Chrome when the dashboard has more than 20 widgets.",
                    score=0.55,
                ),
            ],
            retrieval_confident=True,
            query_used="export pdf_export_hanging PDF export spinner Chrome macOS",
        ),
        classification=ClassifyResult(
            route=Route.AUTO_RESPOND,
            route_reason="Known bug from pro customer, docs found",
        ),
    )

    print("Testing Generate node...\n")
    result = generate_response(test_state)

    print(f"Response:\n{result.generation.response_text}\n")
    print(f"Sources:    {result.generation.sources_used}")
    print(f"Confidence: {result.generation.confidence}")
    print(f"Category:   {result.generation.suggested_category}")
    print(f"Needs review: {result.generation.needs_human_review}")
    print()
    print(f"Guardrails:")
    print(f"  Schema valid:    {result.guardrails.schema_valid}")
    print(f"  Hallucination:   {result.guardrails.hallucination_detected}")
    print(f"  PII detected:    {result.guardrails.pii_detected}")
    print(f"  Injection:       {result.guardrails.injection_detected}")
    print(f"  All passed:      {result.guardrails.all_passed}")
    print(f"  Notes:           {result.guardrails.guardrail_notes}")