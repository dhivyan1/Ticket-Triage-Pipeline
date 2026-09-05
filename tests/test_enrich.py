import httpx
import pytest

from app.nodes import enrich


def test_missing_email_is_not_an_error(state):
    state["ticket"].reporter_email = None

    result = enrich.run(state)

    assert result["customer"].found is False
    assert "errors" not in result


def test_maps_hubspot_properties(monkeypatch, state):
    monkeypatch.setattr(
        enrich,
        "_search_contact",
        lambda email: {
            "id": "42",
            "properties": {
                "company": "Bluesky Data",
                "plan": "Starter",
                "mrr": "190",
                "seats": "6",
                "lifetime_tickets": "4",
            },
        },
    )

    customer = enrich.run(state)["customer"]

    assert customer.found is True
    assert customer.contact_id == "42"
    assert customer.mrr == 190.0
    assert customer.seats == 6


def test_unparseable_numeric_property_becomes_none(monkeypatch, state):
    monkeypatch.setattr(
        enrich,
        "_search_contact",
        lambda email: {"id": "42", "properties": {"mrr": "", "seats": "n/a"}},
    )

    customer = enrich.run(state)["customer"]

    assert customer.mrr is None
    assert customer.seats is None


def test_crm_miss_still_returns_a_customer(monkeypatch, state):
    monkeypatch.setattr(enrich, "_search_contact", lambda email: None)

    assert enrich.run(state)["customer"].found is False


def test_api_failure_is_recorded_but_not_fatal(monkeypatch, state):
    def boom(email):
        raise httpx.ConnectError("hubspot unreachable")

    monkeypatch.setattr(enrich, "_search_contact", boom)

    result = enrich.run(state)

    assert result["customer"].found is False
    assert any("enrich" in e for e in result["errors"])
