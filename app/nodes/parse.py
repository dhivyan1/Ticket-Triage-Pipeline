"""
PARSE NODE

Takes raw ticket data (subject + description) and extracts structured fields:
- intent (what the customer wants)
- sub_intent (specific variation)
- product_area (which part of CloudDash)
- key_details (extracted specifics)
- parse_confidence (how confident the LLM is)

Uses LLM for the free-text description only.
Structured fields (email, priority, labels) come directly from Jira.
"""

import re
from app.config import get_llm
from app.models.schemas import (
    PipelineState,
    ParsedTicket,
    Intent,
)


PARSE_SYSTEM_PROMPT = """You are a support ticket classifier for CloudDash, a project management and analytics dashboard SaaS product.

Given a support ticket (subject + description), extract the following fields.

## Intent categories (pick exactly one):
- how_to: Customer asking how to do something in the product
- feature_question: Customer asking if a feature exists or what's included in a plan
- billing_faq: General billing question (invoice dates, payment method, plan changes, cancellation process)
- billing_dispute: Customer claims they were incorrectly charged (duplicate charge, charged after cancellation)
- refund_request: Customer explicitly requesting money back
- bug_report_known: Customer reporting a problem that matches a known issue (PDF export, slow dashboards, Salesforce sync)
- bug_report_unknown: Customer reporting a problem that does NOT match any known issue
- account_deletion: Customer requesting account or data deletion
- legal_threat: Customer mentions legal action, lawyers, or regulatory complaints
- unknown: Cannot determine intent

## Product areas:
billing, export, dashboard, authentication, integrations, api, account, security, general

## Rules:
- If the ticket mentions being charged twice or after cancellation → billing_dispute, NOT billing_faq
- If the ticket asks for a refund → refund_request, NOT billing_dispute
- If the ticket mentions deleting account or GDPR → account_deletion
- If the ticket mentions legal, lawyers, or breach → legal_threat
- parse_confidence should reflect how clear the intent is (0.0 to 1.0)

Respond ONLY with valid JSON. No explanation, no markdown, no extra text."""

PARSE_USER_PROMPT = """Subject: {subject}
Description: {description}

Extract: {{"intent": "...", "sub_intent": "...", "product_area": "...", "key_details": "...", "parse_confidence": 0.0}}"""


def extract_customer_email(description: str) -> str:
    """Pull customer email from ticket description.
    
    seed_jira.py prepends 'Customer: email@domain.com' to every ticket.
    """
    match = re.search(r"Customer:\s*(\S+@\S+)", description)
    if match:
        return match.group(1)
    return ""


def parse_ticket(state: PipelineState) -> PipelineState:
    """Parse node — extract structured intent from raw ticket."""

    llm = get_llm()

    # Build prompt
    prompt = PARSE_USER_PROMPT.format(
        subject=state.input.raw_subject,
        description=state.input.raw_description,
    )

    # Call LLM with structured output
    try:
        structured_llm = llm.with_structured_output(ParsedTicket)
        parsed = structured_llm.invoke(
            [
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        state.parsed = parsed

    except Exception as e:
        # If LLM fails or returns invalid output, default to unknown
        print(f"  Parse failed: {e}")
        state.parsed = ParsedTicket(
            intent=Intent.UNKNOWN,
            sub_intent="parse_failure",
            product_area="unknown",
            key_details=state.input.raw_subject,
            parse_confidence=0.0,
        )

    # Extract customer email from description (not LLM — just regex)
    email = extract_customer_email(state.input.raw_description)
    if email:
        state.input.reporter_email = email

    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import TicketInput

    # Test with a sample ticket
    test_state = PipelineState(
        input=TicketInput(
            ticket_id="12345",
            ticket_key="KAN-1",
            raw_subject="I was charged twice this month",
            raw_description="Customer: priya.sharma@acmecorp.com\n\nI checked my bank statement and I see two charges of $49.99 from CloudDash for August. This is clearly a duplicate charge. I need this resolved ASAP.",
            reporter_email="",
            priority="High",
            labels=["support-ticket", "billing"],
        )
    )

    result = parse_ticket(test_state)

    print(f"Intent:      {result.parsed.intent}")
    print(f"Sub-intent:  {result.parsed.sub_intent}")
    print(f"Product:     {result.parsed.product_area}")
    print(f"Details:     {result.parsed.key_details}")
    print(f"Confidence:  {result.parsed.parse_confidence}")
    print(f"Email:       {result.input.reporter_email}")