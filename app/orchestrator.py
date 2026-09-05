"""
ORCHESTRATOR

Wires all nodes into a LangGraph state machine with Langfuse v4 tracing.
Every node gets a span — full step-by-step replay in Langfuse.

Usage:
  from app.orchestrator import run_pipeline
  result = run_pipeline(ticket_input)
"""

import time
from typing import TypedDict
from langgraph.graph import StateGraph, END

from app.logger import log_pipeline_run
from app.feedback import log_missing_article
from app.models.schemas import (
    TicketInput,
    PipelineState,
    PipelineMeta,
    Route,
)



from app.nodes.parse import parse_ticket
from app.nodes.enrich import enrich_customer
from app.nodes.retrieve import retrieve_docs
from app.nodes.classify import classify_ticket
from app.nodes.generate import generate_response
from app.nodes.gate import gate_decision
from app.nodes.post import post_to_jira
from app.observability import get_langfuse


# ─── LangGraph state ───────────────────────────────────────

class GraphState(TypedDict):
    pipeline: PipelineState
    langfuse: object  # Langfuse client for creating spans


# ─── Node wrappers with tracing ────────────────────────────

def parse_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="parse") as span:
        span.update(input={
            "subject": state["pipeline"].input.raw_subject,
            "description": state["pipeline"].input.raw_description[:200],
        })

        start = time.time()
        state["pipeline"] = parse_ticket(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["parse"] = elapsed

        intent = state["pipeline"].parsed.intent.value if state["pipeline"].parsed else "failed"
        confidence = state["pipeline"].parsed.parse_confidence if state["pipeline"].parsed else 0

        span.update(output={
            "intent": intent,
            "confidence": confidence,
            "sub_intent": state["pipeline"].parsed.sub_intent if state["pipeline"].parsed else "",
            "product_area": state["pipeline"].parsed.product_area if state["pipeline"].parsed else "",
            "latency_ms": elapsed,
        })

        # Log the LLM call as a generation
        with lf.start_as_current_observation(
            as_type="generation", name="parse-llm", model="qwen2.5:7b"
        ) as gen:
            gen.update(
                input=f"Parse: {state['pipeline'].input.raw_subject}",
                output=f"intent={intent}, confidence={confidence}",
            )

    print(f"  [PARSE]    {elapsed}ms | intent={intent}")
    return state


def enrich_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="enrich") as span:
        span.update(input={"email": state["pipeline"].input.reporter_email})

        start = time.time()
        state["pipeline"] = enrich_customer(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["enrich"] = elapsed

        tier = state["pipeline"].customer.account_tier.value if state["pipeline"].customer else "unknown"

        span.update(output={
            "customer_name": state["pipeline"].customer.customer_name if state["pipeline"].customer else "Unknown",
            "tier": tier,
            "enrichment_status": state["pipeline"].customer.enrichment_status.value if state["pipeline"].customer else "failed",
            "latency_ms": elapsed,
        })

    print(f"  [ENRICH]   {elapsed}ms | tier={tier}")
    return state


def retrieve_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="retrieve") as span:
        span.update(input={
            "intent": state["pipeline"].parsed.intent.value if state["pipeline"].parsed else "unknown",
            "product_area": state["pipeline"].parsed.product_area if state["pipeline"].parsed else "unknown",
        })

        start = time.time()
        state["pipeline"] = retrieve_docs(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["retrieve"] = elapsed

        chunks = len(state["pipeline"].retrieval.chunks) if state["pipeline"].retrieval else 0
        confident = state["pipeline"].retrieval.retrieval_confident if state["pipeline"].retrieval else False
        sources = [c.source for c in state["pipeline"].retrieval.chunks] if state["pipeline"].retrieval else []

        span.update(output={
            "chunks_found": chunks,
            "retrieval_confident": confident,
            "sources": sources,
            "query": state["pipeline"].retrieval.query_used if state["pipeline"].retrieval else "",
            "latency_ms": elapsed,
        })


    print(f"  [RETRIEVE] {elapsed}ms | chunks={chunks} confident={confident}")

    retrieval = state["pipeline"].retrieval
    if retrieval and not retrieval.retrieval_confident:
            parsed = state["pipeline"].parsed
            log_missing_article(
                ticket_key=state["pipeline"].input.ticket_key,
                query=retrieval.query_used,
                intent=parsed.intent.value if parsed else "unknown",
                product_area=parsed.product_area if parsed else "unknown",
                subject=state["pipeline"].input.raw_subject,
            )

    return state
    


def classify_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="classify") as span:
        span.update(input={
            "intent": state["pipeline"].parsed.intent.value if state["pipeline"].parsed else "unknown",
            "tier": state["pipeline"].customer.account_tier.value if state["pipeline"].customer else "unknown",
            "retrieval_confident": state["pipeline"].retrieval.retrieval_confident if state["pipeline"].retrieval else False,
        })

        start = time.time()
        state["pipeline"] = classify_ticket(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["classify"] = elapsed

        route = state["pipeline"].classification.route.value if state["pipeline"].classification else "unknown"
        reason = state["pipeline"].classification.route_reason if state["pipeline"].classification else ""

        span.update(output={
            "route": route,
            "reason": reason,
            "latency_ms": elapsed,
        })

    print(f"  [CLASSIFY] {elapsed}ms | route={route} | {reason}")
    return state


def generate_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="generate") as span:
        span.update(input={
            "route": state["pipeline"].classification.route.value if state["pipeline"].classification else "unknown",
        })

        start = time.time()
        state["pipeline"] = generate_response(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["generate"] = elapsed

        if state["pipeline"].generation:
            conf = state["pipeline"].generation.confidence
            review = state["pipeline"].generation.needs_human_review
            response_preview = state["pipeline"].generation.response_text[:200]

            span.update(output={
                "confidence": conf,
                "needs_human_review": review,
                "response_preview": response_preview,
                "sources_used": state["pipeline"].generation.sources_used,
                "guardrails": {
                    "schema_valid": state["pipeline"].guardrails.schema_valid if state["pipeline"].guardrails else None,
                    "hallucination": state["pipeline"].guardrails.hallucination_detected if state["pipeline"].guardrails else None,
                    "pii": state["pipeline"].guardrails.pii_detected if state["pipeline"].guardrails else None,
                    "injection": state["pipeline"].guardrails.injection_detected if state["pipeline"].guardrails else None,
                },
                "latency_ms": elapsed,
            })

            # Log LLM call as generation
            with lf.start_as_current_observation(
                as_type="generation", name="generate-llm", model="qwen2.5:7b"
            ) as gen:
                gen.update(
                    input=f"Generate response for: {state['pipeline'].input.raw_subject}",
                    output=response_preview,
                )

            print(f"  [GENERATE] {elapsed}ms | confidence={conf:.2f} needs_review={review}")
        else:
            span.update(output={"skipped": True, "latency_ms": elapsed})
            print(f"  [GENERATE] {elapsed}ms | skipped (escalate)")

    return state


def gate_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="gate") as span:
        start = time.time()
        state["pipeline"] = gate_decision(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["gate"] = elapsed

        decision = state["pipeline"].gate.decision.value if state["pipeline"].gate else "unknown"

        span.update(output={
            "decision": decision,
            "reviewer": state["pipeline"].gate.reviewer if state["pipeline"].gate else None,
            "latency_ms": elapsed,
        })

    print(f"  [GATE]     {elapsed}ms | decision={decision}")
    return state


def post_node(state: GraphState) -> GraphState:
    lf = state["langfuse"]

    with lf.start_as_current_observation(as_type="span", name="post") as span:
        span.update(input={
            "decision": state["pipeline"].gate.decision.value if state["pipeline"].gate else "unknown",
        })

        start = time.time()
        state["pipeline"] = post_to_jira(state["pipeline"])
        elapsed = int((time.time() - start) * 1000)
        state["pipeline"].meta.tool_latencies["post"] = elapsed

        posted = state["pipeline"].post.posted if state["pipeline"].post else False

        span.update(output={
            "posted": posted,
            "comment_id": state["pipeline"].post.jira_comment_id if state["pipeline"].post else None,
            "error": state["pipeline"].post.post_error if state["pipeline"].post else None,
            "latency_ms": elapsed,
        })

    print(f"  [POST]     {elapsed}ms | posted={posted}")
    return state


# ─── Routing logic ─────────────────────────────────────────

def route_after_classify(state: GraphState) -> str:
    route = state["pipeline"].classification.route if state["pipeline"].classification else Route.ESCALATE
    if route == Route.ESCALATE:
        return "post"
    return "generate"


# ─── Build the graph ───────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("parse", parse_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("classify", classify_node)
    graph.add_node("generate", generate_node)
    graph.add_node("gate", gate_node)
    graph.add_node("post", post_node)

    graph.set_entry_point("parse")

    graph.add_edge("parse", "enrich")
    graph.add_edge("enrich", "retrieve")
    graph.add_edge("retrieve", "classify")

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"generate": "generate", "post": "post"},
    )

    graph.add_edge("generate", "gate")
    graph.add_edge("gate", "post")
    graph.add_edge("post", END)

    return graph


# ─── Public API ────────────────────────────────────────────

_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


def run_pipeline(ticket_input: TicketInput) -> PipelineState:
    """Run the full pipeline for one ticket with Langfuse tracing."""
    pipeline_start = time.time()

    langfuse = get_langfuse()

    state = PipelineState(
        input=ticket_input,
        meta=PipelineMeta(),
    )

    print(f"\n{'='*60}")
    print(f"Pipeline started: {ticket_input.ticket_key}")
    print(f"Subject: {ticket_input.raw_subject}")
    print(f"{'='*60}")

    # Root span wraps the entire pipeline
    with langfuse.start_as_current_observation(
        as_type="span",
        name="pipeline-run",
    ) as root:
        root.update(input={
            "ticket_key": ticket_input.ticket_key,
            "subject": ticket_input.raw_subject,
            "reporter_email": ticket_input.reporter_email,
            "priority": ticket_input.priority,
        })

        graph = get_graph()
        result = graph.invoke({"pipeline": state, "langfuse": langfuse})

        # Calculate total latency
        total_ms = int((time.time() - pipeline_start) * 1000)
        result["pipeline"].meta.total_latency_ms = total_ms

        # Store trace ID
        trace_id = getattr(root, 'trace_id', None) or getattr(root, 'id', 'unknown')
        result["pipeline"].meta.trace_id = str(trace_id)

        root.update(output={
            "ticket_key": ticket_input.ticket_key,
            "route": result["pipeline"].classification.route.value if result["pipeline"].classification else "unknown",
            "decision": result["pipeline"].gate.decision.value if result["pipeline"].gate else "unknown",
            "posted": result["pipeline"].post.posted if result["pipeline"].post else False,
            "total_latency_ms": total_ms,
        })

    # Flush traces to Langfuse
    langfuse.flush()
    log_entry = log_pipeline_run(result["pipeline"])
    print(f"{'='*60}")
    print(f"Pipeline complete: {total_ms}ms total")
    if result["pipeline"].gate:
        print(f"Decision: {result['pipeline'].gate.decision.value}")
    if result["pipeline"].post:
        print(f"Posted: {result['pipeline'].post.posted}")
    print(f"Trace ID: {result['pipeline'].meta.trace_id}")
    print(f"{'='*60}\n")

    return result["pipeline"]


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    test_input = TicketInput(
        ticket_id="test-trace",
        ticket_key="KAN-2",
        raw_subject="How do I export my dashboard as PDF?",
        raw_description="Customer: nina.patel@initech.co\n\nI need to send a weekly report to my manager. How can I export the dashboard as a PDF file?",
        reporter_email="nina.patel@initech.co",
        priority="Medium",
        labels=["support-ticket"],
    )

    result = run_pipeline(test_input)

    print("\n--- Final State Summary ---")
    print(f"Intent:      {result.parsed.intent.value if result.parsed else 'N/A'}")
    print(f"Customer:    {result.customer.customer_name if result.customer else 'N/A'}")
    print(f"Route:       {result.classification.route.value if result.classification else 'N/A'}")
    print(f"Gate:        {result.gate.decision.value if result.gate else 'N/A'}")
    print(f"Posted:      {result.post.posted if result.post else False}")
    print(f"Latency:     {result.meta.total_latency_ms}ms")
    print(f"Trace ID:    {result.meta.trace_id}")