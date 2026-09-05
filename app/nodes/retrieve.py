"""
RETRIEVE NODE

Takes the parsed intent and key details from the Parse node,
builds a search query, and finds the most relevant knowledge
base chunks from Chroma vector DB.

These chunks get passed to the Generate node, which uses them
as the ONLY source of truth for drafting the response.

No LLM involved. Embedding model + vector similarity search.
"""

import os
import re
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, MAX_RETRIEVAL_CHUNKS
from app.models.schemas import (
    PipelineState,
    RetrievalResult,
    RetrievedChunk,
)

# Load once, reuse across calls
_vectorstore = None

# Chroma returns L2 distance — lower = better match.
# With all-MiniLM-L6-v2, relevant docs typically score < 1.5.
# Anything above this is noise.
MAX_DISTANCE = 1.4


def get_vectorstore():
    """Load Chroma vector store from disk. Cached after first call."""
    global _vectorstore

    if _vectorstore is None:
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
        )
        _vectorstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embeddings,
            collection_name="knowledge_base",
        )

    return _vectorstore


def build_search_query(state: PipelineState) -> str:
    """Build a search query from parsed ticket fields.

    Combines product area, sub-intent, and key details.
    Removes email addresses from key details to avoid polluting the search.
    """
    parts = []

    if state.parsed:
        if state.parsed.product_area and state.parsed.product_area != "unknown":
            parts.append(state.parsed.product_area)
        if state.parsed.sub_intent:
            parts.append(state.parsed.sub_intent)
        if state.parsed.key_details:
            # Remove email addresses from key details
            cleaned = re.sub(r'\S+@\S+', '', state.parsed.key_details).strip()
            if cleaned:
                parts.append(cleaned)

    # Fallback: use the raw subject if parsing gave nothing useful
    if not parts:
        parts.append(state.input.raw_subject)

    return " ".join(parts)


def retrieve_docs(state: PipelineState) -> PipelineState:
    """Retrieve node — search vector DB for relevant knowledge base chunks."""

    vectorstore = get_vectorstore()
    query = build_search_query(state)

    # Search with scores (lower distance = closer match in Chroma)
    results = vectorstore.similarity_search_with_score(query, k=MAX_RETRIEVAL_CHUNKS + 2)

    # Filter by distance threshold and build chunks
    chunks = []
    for doc, distance in results:
        if distance <= MAX_DISTANCE and len(chunks) < MAX_RETRIEVAL_CHUNKS:
            source = os.path.basename(doc.metadata.get("source", "unknown"))
            chunks.append(
                RetrievedChunk(
                    source=source,
                    content=doc.page_content,
                    score=round(distance, 3),  # raw distance, lower = better
                )
            )

    # Determine confidence
    retrieval_confident = len(chunks) > 0

    state.retrieval = RetrievalResult(
        chunks=chunks,
        retrieval_confident=retrieval_confident,
        query_used=query,
    )

    return state


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    from app.models.schemas import TicketInput, ParsedTicket, Intent

    test_cases = [
        {
            "name": "PDF export issue",
            "subject": "PDF export not working",
            "description": "Export hangs on Chrome",
            "intent": Intent.BUG_REPORT_KNOWN,
            "sub_intent": "pdf_export_hanging",
            "product_area": "export",
            "key_details": "PDF export spinner runs forever on Chrome macOS",
        },
        {
            "name": "Password reset",
            "subject": "Can't log in",
            "description": "Password reset not working",
            "intent": Intent.HOW_TO,
            "sub_intent": "password_reset",
            "product_area": "authentication",
            "key_details": "password reset email not arriving, locked out",
        },
        {
            "name": "Billing dispute",
            "subject": "I was charged twice this month",
            "description": "Two charges of $49.99",
            "intent": Intent.BILLING_DISPUTE,
            "sub_intent": "duplicate_charge",
            "product_area": "billing",
            "key_details": "two charges of $49.99 for August, duplicate charge",
        },
    ]

    for tc in test_cases:
        print(f"--- {tc['name']} ---")

        test_state = PipelineState(
            input=TicketInput(
                ticket_id="test",
                ticket_key="KAN-0",
                raw_subject=tc["subject"],
                raw_description=tc["description"],
                reporter_email="test@test.com",
                priority="High",
                labels=["support-ticket"],
            ),
            parsed=ParsedTicket(
                intent=tc["intent"],
                sub_intent=tc["sub_intent"],
                product_area=tc["product_area"],
                key_details=tc["key_details"],
                parse_confidence=0.92,
            ),
        )

        result = retrieve_docs(test_state)

        print(f"Query:     \"{result.retrieval.query_used}\"")
        print(f"Confident: {result.retrieval.retrieval_confident}")
        print(f"Chunks:    {len(result.retrieval.chunks)}")

        for i, chunk in enumerate(result.retrieval.chunks):
            print(f"  [{i+1}] Distance: {chunk.score} | Source: {chunk.source}")
            print(f"      {chunk.content[:80]}...")

        print()