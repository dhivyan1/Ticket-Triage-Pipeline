"""Routing is the highest-stakes decision in the pipeline, so these tests
assert on the real rules file rather than a fixture."""

import pytest

from app.models.schemas import CustomerInfo, Route, Urgency
from app.nodes import classify


def route(state):
    return classify.run(state)["classification"]


def test_security_label_escalates_even_when_well_documented(state):
    state["ticket"].labels = ["security"]

    result = route(state)

    assert result.route is Route.ESCALATE
    assert result.matched_rule == "security_or_data_loss"


def test_critical_urgency_escalates(state):
    state["parse"].urgency = Urgency.CRITICAL

    assert route(state).route is Route.ESCALATE


def test_enterprise_mrr_escalates_an_easy_question(state):
    state["customer"] = CustomerInfo(found=True, plan="Enterprise", mrr=8400.0)

    result = route(state)

    assert result.route is Route.ESCALATE
    assert result.matched_rule == "enterprise_account"


def test_documented_password_reset_is_automated(state):
    assert route(state).route is Route.AUTO


def test_thin_retrieval_goes_to_review(state):
    state["docs"] = []

    result = route(state)

    assert result.route is Route.REVIEW
    assert result.matched_rule == "thin_retrieval"


def test_unknown_reporter_goes_to_review(state):
    state["customer"] = CustomerInfo(found=False)
    state["parse"].product_area = "dashboards"
    state["parse"].intent = "how-to"

    assert route(state).route is Route.REVIEW


def test_rule_order_escalate_beats_auto(state):
    """A password reset from an Enterprise account is still escalated."""
    state["customer"] = CustomerInfo(found=True, plan="Enterprise", mrr=9000.0)

    assert route(state).route is Route.ESCALATE


def test_unmatched_ticket_defaults_to_human(monkeypatch, state):
    monkeypatch.setattr(classify, "load_rules", lambda: [])

    result = route(state)

    assert result.route is Route.REVIEW
    assert result.matched_rule is None


@pytest.mark.parametrize(
    "condition,facts,expected",
    [
        ({"urgency": "high"}, {"urgency": "high"}, True),
        ({"urgency": "high"}, {"urgency": "low"}, False),
        ({"mrr__gte": 5000}, {"mrr": 5000.0}, True),
        ({"mrr__gte": 5000}, {"mrr": 4999.0}, False),
        ({"doc_count__lt": 1}, {"doc_count": 0}, True),
        ({"plan__in": ["growth", "starter"]}, {"plan": "starter"}, True),
        ({"labels__contains_any": ["security"]}, {"labels": ["billing"]}, False),
        ({"labels__contains_any": ["security"]}, {"labels": ["security", "api"]}, True),
        ({"mrr__gte": 100}, {"mrr": None}, False),
    ],
)
def test_operators(condition, facts, expected):
    assert classify._matches(condition, facts) is expected
