from app.nodes import retrieve


class FakeStore:
    def __init__(self, hits):
        self.hits = hits
        self.queries = []

    def similarity_search_with_relevance_scores(self, query, k):
        self.queries.append(query)
        return self.hits[:k]


class FakeDoc:
    def __init__(self, content, metadata):
        self.page_content = content
        self.metadata = metadata


def _hit(content, source, score):
    return (
        FakeDoc(content, {"source": source, "title": source, "chunk_id": f"{source}#0"}),
        score,
    )


def test_query_is_built_from_parse_not_raw_ticket(monkeypatch, state):
    store = FakeStore([_hit("reset links last 60 minutes", "auth-password-reset.md", 0.8)])
    monkeypatch.setattr(retrieve, "_store", lambda: store)

    retrieve.run(state)

    query = store.queries[0]
    assert "password-reset" in query
    assert "authentication" in query


def test_low_scoring_chunks_are_dropped(monkeypatch, state):
    store = FakeStore(
        [
            _hit("relevant", "auth-password-reset.md", 0.8),
            _hit("unrelated noise", "billing-plans.md", 0.05),
        ]
    )
    monkeypatch.setattr(retrieve, "_store", lambda: store)

    docs = retrieve.run(state)["docs"]

    assert [d.source for d in docs] == ["auth-password-reset.md"]


def test_store_failure_returns_no_docs(monkeypatch, state):
    def boom():
        raise RuntimeError("chroma directory missing")

    monkeypatch.setattr(retrieve, "_store", boom)

    result = retrieve.run(state)

    assert result["docs"] == []
    assert result["errors"]
