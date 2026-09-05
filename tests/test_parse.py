from app.models.schemas import TicketParse, Urgency
from app.nodes import parse as parse_node
from tests.conftest import FakeLLM


def test_extracts_structured_fields(monkeypatch, state):
    expected = TicketParse(
        intent="password-reset",
        product_area="authentication",
        urgency=Urgency.LOW,
    )
    fake = FakeLLM(response=expected)
    monkeypatch.setattr(parse_node, "get_llm", lambda *a, **k: fake)

    result = parse_node.run(state)

    assert result["parse"] == expected


def test_prompt_uses_sanitized_text_not_raw(monkeypatch, state):
    state["sanitized_description"] = "[redacted: possible injection]"
    fake = FakeLLM(response=TicketParse(intent="x", product_area="other", urgency=Urgency.LOW))
    monkeypatch.setattr(parse_node, "get_llm", lambda *a, **k: fake)

    parse_node.run(state)

    assert "[redacted: possible injection]" in fake.calls[0]
    assert "Clicked the link" not in fake.calls[0]


def test_llm_failure_degrades_instead_of_raising(monkeypatch, state):
    fake = FakeLLM(error=RuntimeError("model refused to emit valid JSON"))
    monkeypatch.setattr(parse_node, "get_llm", lambda *a, **k: fake)

    result = parse_node.run(state)

    assert result["parse"].intent == "unknown"
    assert result["errors"]
