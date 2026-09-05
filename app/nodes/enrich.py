"""
ENRICH NODE

Takes the reporter email from the parsed ticket and queries HubSpot CRM.
Returns customer info: name, company, account tier, past ticket count.

This data drives:
- Classify node: enterprise customers → HUMAN_REVIEW, free → AUTO_RESPOND
- Generate node: response tone matches customer tier

No LLM involved. Pure API call + field parsing.
Degrades gracefully — if HubSpot is down, pipeline continues with defaults.
"""

import re
import requests
from app.config import HUBSPOT_ACCESS_TOKEN
from app.models.schemas import (
    PipelineState,
    CustomerInfo,
    AccountTier,
    EnrichmentStatus,
)

HUBSPOT_SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def parse_message_field(message: str) -> dict:
    """Parse the message field where we stored tier, status, and ticket count.
    
    Format: 'Plan: pro | Status: active | Past tickets: 7'
    """
    result = {"tier": "unknown", "status": "unknown", "past_tickets": 0}

    if not message:
        return result

    # Extract plan/tier
    tier_match = re.search(r"Plan:\s*(\w+)", message)
    if tier_match:
        result["tier"] = tier_match.group(1).lower()

    # Extract status
    status_match = re.search(r"Status:\s*(\w+)", message)
    if status_match:
        result["status"] = status_match.group(1).lower()

    # Extract past ticket count
    tickets_match = re.search(r"Past tickets:\s*(\d+)", message)
    if tickets_match:
        result["past_tickets"] = int(tickets_match.group(1))

    return result


def enrich_customer(state: PipelineState) -> PipelineState:
    """Enrich node — fetch customer data from HubSpot by email."""

    email = state.input.reporter_email

    if not email:
        print("  Enrich: No reporter email found, skipping")
        state.customer = CustomerInfo(enrichment_status=EnrichmentStatus.FAILED)
        return state

    # Search HubSpot by email
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }
                ]
            }
        ],
        "properties": [
            "email", "firstname", "lastname", "company",
            "jobtitle", "message", "createdate",
        ],
    }

    try:
        response = requests.post(
            HUBSPOT_SEARCH_URL,
            headers=HEADERS,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        print(f"  Enrich: HubSpot timeout for {email}")
        state.customer = CustomerInfo(enrichment_status=EnrichmentStatus.FAILED)
        return state

    except requests.exceptions.RequestException as e:
        print(f"  Enrich: HubSpot error for {email}: {e}")
        state.customer = CustomerInfo(enrichment_status=EnrichmentStatus.FAILED)
        return state

    # No contact found
    results = data.get("results", [])
    if not results:
        print(f"  Enrich: No HubSpot contact found for {email}")
        state.customer = CustomerInfo(enrichment_status=EnrichmentStatus.FAILED)
        return state

    # Extract properties from first match
    props = results[0].get("properties", {})

    # Parse the message field for tier/status/ticket count
    message_data = parse_message_field(props.get("message", ""))

    # Map tier string to AccountTier enum
    tier_map = {
        "free": AccountTier.FREE,
        "starter": AccountTier.STARTER,
        "pro": AccountTier.PRO,
        "enterprise": AccountTier.ENTERPRISE,
    }
    account_tier = tier_map.get(message_data["tier"], AccountTier.UNKNOWN)

    state.customer = CustomerInfo(
        customer_name=f"{props.get('firstname', '')} {props.get('lastname', '')}".strip() or "Unknown",
        company=props.get("company", "Unknown"),
        account_tier=account_tier,
        subscription_status=message_data["status"],
        past_ticket_count=message_data["past_tickets"],
        signup_date=props.get("createdate", None),
        enrichment_status=EnrichmentStatus.FULL,
    )

    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import TicketInput

    # Test with an email that exists in HubSpot
    test_state = PipelineState(
        input=TicketInput(
            ticket_id="12345",
            ticket_key="KAN-1",
            raw_subject="Test ticket",
            raw_description="Test description",
            reporter_email="priya.sharma@acmecorp.com",
            priority="High",
            labels=["support-ticket"],
        )
    )

    result = enrich_customer(test_state)

    print(f"Name:        {result.customer.customer_name}")
    print(f"Company:     {result.customer.company}")
    print(f"Tier:        {result.customer.account_tier}")
    print(f"Status:      {result.customer.subscription_status}")
    print(f"Tickets:     {result.customer.past_ticket_count}")
    print(f"Signup:      {result.customer.signup_date}")
    print(f"Enrichment:  {result.customer.enrichment_status}")