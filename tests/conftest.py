"""Shared fixtures.

Every test here runs without network access: no Ollama, no Jira, no
HubSpot. Nodes that call an LLM are tested by injecting a fake, which is
why get_llm() is a module-level function and not a global client.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.schemas import (  # noqa: E402
    ClassificationResult,
    CustomerInfo,
    DraftResponse,
    RetrievedDoc,
    Route,
    Ticket,
    TicketParse,
    Urgency,
)


class FakeStructuredLLM:
    """Stands in for `get_llm().with_structured_output(Model)`."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def invoke(self, prompt):
        self.calls.append(prompt)
        if self.error:
            raise self.error
        return self.response


class FakeLLM:
    def __init__(self, response=None, error=None):
        self._structured = FakeStructuredLLM(response, error)

    def with_structured_output(self, _model):
        return self._structured

    @property
    def calls(self):
        return self._structured.calls


@pytest.fixture
def ticket():
    return Ticket(
        ticket_id="SUP-1",
        summary="Reset password link expired",
        description="Clicked the link two hours later and it says expired.",
        reporter_email="nina@bluesky-data.dev",
        labels=["authentication"],
    )


@pytest.fixture
def parse():
    return TicketParse(
        intent="password-reset",
        product_area="authentication",
        urgency=Urgency.LOW,
        details=["link expired after two hours"],
        missing_info=[],
    )


@pytest.fixture
def customer():
    return CustomerInfo(
        contact_id="123",
        company="Bluesky Data",
        plan="Starter",
        mrr=190.0,
        seats=6,
        lifetime_tickets=4,
        found=True,
    )


@pytest.fixture
def docs():
    return [
        RetrievedDoc(
            doc_id="auth-password-reset.md#0",
            source="auth-password-reset.md",
            title="Resetting a password",
            content=(
                "The reset link is valid for 60 minutes and can be used once. "
                "Members reset their own password from the login screen."
            ),
            score=0.82,
        ),
        RetrievedDoc(
            doc_id="auth-password-reset.md#1",
            source="auth-password-reset.md",
            title="Resetting a password",
            content="Accounts with SSO enforced cannot use password reset.",
            score=0.64,
        ),
    ]


@pytest.fixture
def state(ticket, parse, customer, docs):
    return {
        "ticket": ticket,
        "sanitized_description": ticket.description,
        "parse": parse,
        "customer": customer,
        "docs": docs,
        "errors": [],
        "trace": {},
    }


@pytest.fixture
def draft():
    return DraftResponse(
        body=(
            "The password reset link is valid for 60 minutes and can only be "
            "used once, so a link opened two hours later will always show as "
            "expired. Request a fresh one from the login screen."
        ),
        citations=["auth-password-reset.md"],
        tone="informative",
        needs_customer_input=False,
    )


@pytest.fixture
def auto_classification():
    return ClassificationResult(
        route=Route.AUTO, reason="Standard recovery flow", matched_rule="known_password_reset"
    )
