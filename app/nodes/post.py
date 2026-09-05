"""
POST NODE

Posts the pipeline output back to Jira as a comment.
Behavior depends on Gate decision:

- AUTO_POST: posts response as a visible comment (customer sees it)
  Tagged: [AI-Assisted Response]

- QUEUED_FOR_REVIEW: posts response as an internal note (customer can't see it)
  Tagged: [AI Draft — Pending Review]

- ESCALATED: posts gathered context as an internal note
  Tagged: [AI Context — Needs Human]

Also adds labels to the ticket (ai-triaged, suggested category).

No LLM involved. Pure Jira API calls.
Retries with backoff if Jira API fails.
"""

import time
import requests
from requests.auth import HTTPBasicAuth

from app.config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
from app.models.schemas import (
    PipelineState,
    PostResult,
    GateDecision,
)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

MAX_RETRIES = 3


def format_auto_post(state: PipelineState) -> str:
    """Format response for auto-posting (customer-visible)."""
    response = state.generation.response_text

    sources = ""
    if state.generation.sources_used:
        sources = "\n\nSources: " + ", ".join(state.generation.sources_used)

    trace = ""
    if state.meta and state.meta.trace_id:
        trace = f"\nTrace: {state.meta.trace_id}"

    return f"[AI-Assisted Response]\n\n{response}{sources}{trace}"


def format_review_draft(state: PipelineState) -> str:
    """Format response for human review (internal note)."""
    response = state.generation.response_text

    review_reason = state.gate.reviewer if state.gate and state.gate.reviewer else "Routed to human review"

    guardrail_notes = ""
    if state.guardrails and state.guardrails.guardrail_notes:
        guardrail_notes = f"\nGuardrail notes: {state.guardrails.guardrail_notes}"

    sources = ""
    if state.generation.sources_used:
        sources = "\nSources: " + ", ".join(state.generation.sources_used)

    return (
        f"[AI Draft — Pending Review]\n\n"
        f"Review reason: {review_reason}\n"
        f"Confidence: {state.generation.confidence:.2f}"
        f"{guardrail_notes}"
        f"{sources}\n\n"
        f"--- Draft response ---\n\n"
        f"{response}"
    )


def format_escalation(state: PipelineState) -> str:
    """Format context dump for escalated tickets (internal note)."""
    customer_info = "Unknown customer"
    if state.customer and state.customer.customer_name != "Unknown":
        customer_info = (
            f"{state.customer.customer_name} | {state.customer.company} | "
            f"{state.customer.account_tier.value} plan | "
            f"{state.customer.past_ticket_count} past tickets"
        )

    intent_info = "Unknown"
    if state.parsed:
        intent_info = f"{state.parsed.intent.value} / {state.parsed.sub_intent}"

    retrieval_info = "No relevant docs found"
    if state.retrieval and state.retrieval.chunks:
        doc_sources = [c.source for c in state.retrieval.chunks]
        retrieval_info = f"Docs found: {', '.join(doc_sources)}"

    escalate_reason = "Unknown"
    if state.classification:
        escalate_reason = state.classification.route_reason

    return (
        f"[AI Context — Needs Human]\n\n"
        f"This ticket could not be auto-resolved.\n\n"
        f"Customer: {customer_info}\n"
        f"Parsed intent: {intent_info}\n"
        f"Retrieval: {retrieval_info}\n"
        f"Escalation reason: {escalate_reason}"
    )


def post_comment(ticket_id: str, body: str) -> dict:
    """Post a comment to a Jira ticket with retry logic."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}/comment"

    payload = {
        "body": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": body,
                        }
                    ],
                }
            ],
        }
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=HEADERS, auth=AUTH, json=payload, timeout=15)

            if response.status_code == 201:
                return {"success": True, "comment_id": response.json().get("id")}
            else:
                print(f"  Post attempt {attempt + 1} failed ({response.status_code}): {response.text[:100]}")

        except requests.exceptions.RequestException as e:
            print(f"  Post attempt {attempt + 1} error: {e}")

        # Exponential backoff
        if attempt < MAX_RETRIES - 1:
            wait = 2 ** attempt
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)

    return {"success": False, "comment_id": None}


def add_labels(ticket_id: str, labels: list[str]) -> bool:
    """Add labels to a Jira ticket."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}"

    payload = {
        "update": {
            "labels": [{"add": label} for label in labels],
        }
    }

    try:
        response = requests.put(url, headers=HEADERS, auth=AUTH, json=payload, timeout=10)
        return response.status_code == 204
    except requests.exceptions.RequestException as e:
        print(f"  Failed to add labels: {e}")
        return False


def post_to_jira(state: PipelineState) -> PipelineState:
    """Post node — post response or context to Jira ticket."""

    decision = state.gate.decision if state.gate else GateDecision.ESCALATED
    ticket_key = state.input.ticket_key

    # Format the comment based on gate decision
    if decision == GateDecision.AUTO_POST:
        comment_body = format_auto_post(state)
    elif decision == GateDecision.QUEUED_FOR_REVIEW:
        comment_body = format_review_draft(state)
    else:
        comment_body = format_escalation(state)

    # Post the comment
    result = post_comment(ticket_key, comment_body)

    if result["success"]:
        print(f"  Posted comment to {ticket_key} ({decision.value})")
    else:
        print(f"  Failed to post comment to {ticket_key}")

    # Add labels
    labels = ["ai-triaged"]
    if state.generation and state.generation.suggested_category:
        labels.append(state.generation.suggested_category.lower().replace(" ", "-"))
    if decision == GateDecision.ESCALATED:
        labels.append("needs-human")

    labels_added = add_labels(ticket_key, labels)

    state.post = PostResult(
        posted=result["success"],
        jira_comment_id=result.get("comment_id"),
        post_error=None if result["success"] else "Failed after max retries",
    )

    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import (
        TicketInput, ParsedTicket, CustomerInfo, RetrievalResult,
        RetrievedChunk, ClassifyResult, GeneratedResponse,
        GuardrailResult, GateResult, Intent, AccountTier,
        EnrichmentStatus, Route,
    )

    # Test: Post an auto-response to a real Jira ticket
    # Change KAN-1 to an actual ticket key in your Jira project
    test_state = PipelineState(
        input=TicketInput(
            ticket_id="test",
            ticket_key="KAN-35",       # ← change to a real ticket key
            raw_subject="PDF export not working",
            raw_description="Test",
            reporter_email="sam.wilson@northwind.io",
            priority="High",
            labels=["support-ticket"],
        ),
        parsed=ParsedTicket(
            intent=Intent.BUG_REPORT_KNOWN,
            sub_intent="pdf_export_hanging",
            product_area="export",
            key_details="PDF export spinner",
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
        classification=ClassifyResult(
            route=Route.AUTO_RESPOND,
            route_reason="Known bug, pro customer, docs found",
        ),
        generation=GeneratedResponse(
            response_text="Hi Sam,\n\nThis is a known issue affecting PDF exports on Chrome. Our team is working on a fix, expected within 48 hours.\n\nWorkaround: Clear your browser cache (Settings > Privacy > Clear browsing data), then retry the export. You can also try Firefox or Safari.\n\nLet me know if you need anything else!",
            sources_used=["known-issues.md", "feature-export.md"],
            confidence=0.92,
            suggested_category="bug_report",
            needs_human_review=False,
        ),
        guardrails=GuardrailResult(
            schema_valid=True,
            hallucination_detected=False,
            pii_detected=False,
            injection_detected=False,
        ),
        gate=GateResult(
            decision=GateDecision.AUTO_POST,
            reviewer=None,
        ),
    )

    print("Testing Post node — posting to Jira...\n")
    result = post_to_jira(test_state)

    print(f"\nPosted:     {result.post.posted}")
    print(f"Comment ID: {result.post.jira_comment_id}")
    print(f"Error:      {result.post.post_error}")
    print(f"\nCheck Jira: {JIRA_BASE_URL}/browse/{test_state.input.ticket_key}")