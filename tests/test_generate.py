from app.models.schemas import DraftResponse
from app.nodes import generate
from tests.conftest import FakeLLM


def test_returns_draft(monkeypatch, state, draft):
    monkeypatch.setattr(generate, "get_llm", lambda *a, **k: FakeLLM(response=draft))

    assert generate.run(state)["draft"].body == draft.body


def test_invented_citations_are_stripped(monkeypatch, state):
    invented = DraftResponse(
        body="Reset links expire after 60 minutes.",
        citations=["auth-password-reset.md", "does-not-exist.md"],
    )
    monkeypatch.setattr(generate, "get_llm", lambda *a, **k: FakeLLM(response=invented))

    result = generate.run(state)["draft"]

    assert result.citations == ["auth-password-reset.md"]


def test_prompt_states_when_nothing_was_retrieved(monkeypatch, state, draft):
    state["docs"] = []
    fake = FakeLLM(response=draft)
    monkeypatch.setattr(generate, "get_llm", lambda *a, **k: fake)

    generate.run(state)

    assert "no knowledge base articles matched" in fake.calls[0]


def test_prompt_omits_crm_details_for_unknown_reporter(monkeypatch, state, draft):
    state["customer"] = None
    fake = FakeLLM(response=draft)
    monkeypatch.setattr(generate, "get_llm", lambda *a, **k: fake)

    generate.run(state)

    assert "no CRM record" in fake.calls[0]


def test_llm_failure_produces_no_draft(monkeypatch, state):
    monkeypatch.setattr(
        generate, "get_llm", lambda *a, **k: FakeLLM(error=RuntimeError("timeout"))
    )

    result = generate.run(state)

    assert "draft" not in result
    assert result["errors"]
