"""
STRUCTURED LOGGER

Writes one JSON line per pipeline run to logs/pipeline.jsonl.
Each line contains everything needed for metrics and debugging.

This is separate from Langfuse (which stores traces for replay).
This file is for local analytics, dashboards, and alerting.
"""

import os
import json
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOGS_DIR, "pipeline.jsonl")


def log_pipeline_run(state) -> dict:
    """Write a structured log entry for a completed pipeline run.

    Returns the log entry dict.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Ticket info
        "ticket_id": state.input.ticket_id,
        "ticket_key": state.input.ticket_key,
        "subject": state.input.raw_subject,
        "reporter_email": state.input.reporter_email,
        "priority": state.input.priority,

        # Parse results
        "intent": state.parsed.intent.value if state.parsed else "unknown",
        "sub_intent": state.parsed.sub_intent if state.parsed else "unknown",
        "product_area": state.parsed.product_area if state.parsed else "unknown",
        "parse_confidence": state.parsed.parse_confidence if state.parsed else 0.0,

        # Customer info
        "customer_name": state.customer.customer_name if state.customer else "Unknown",
        "company": state.customer.company if state.customer else "Unknown",
        "account_tier": state.customer.account_tier.value if state.customer else "unknown",
        "past_ticket_count": state.customer.past_ticket_count if state.customer else 0,
        "enrichment_status": state.customer.enrichment_status.value if state.customer else "failed",

        # Retrieval
        "chunks_found": len(state.retrieval.chunks) if state.retrieval else 0,
        "retrieval_confident": state.retrieval.retrieval_confident if state.retrieval else False,
        "retrieval_sources": [c.source for c in state.retrieval.chunks] if state.retrieval else [],
        "retrieval_query": state.retrieval.query_used if state.retrieval else "",

        # Classification
        "route": state.classification.route.value if state.classification else "unknown",
        "route_reason": state.classification.route_reason if state.classification else "",

        # Generation
        "response_confidence": state.generation.confidence if state.generation else 0.0,
        "sources_used": state.generation.sources_used if state.generation else [],
        "suggested_category": state.generation.suggested_category if state.generation else "",
        "needs_human_review": state.generation.needs_human_review if state.generation else False,

        # Guardrails
        "guardrails_passed": state.guardrails.all_passed if state.guardrails else False,
        "schema_valid": state.guardrails.schema_valid if state.guardrails else False,
        "hallucination_detected": state.guardrails.hallucination_detected if state.guardrails else False,
        "pii_detected": state.guardrails.pii_detected if state.guardrails else False,
        "injection_detected": state.guardrails.injection_detected if state.guardrails else False,
        "guardrail_notes": state.guardrails.guardrail_notes if state.guardrails else "",

        # Gate
        "decision": state.gate.decision.value if state.gate else "unknown",

        # Post
        "posted": state.post.posted if state.post else False,
        "jira_comment_id": state.post.jira_comment_id if state.post else None,
        "post_error": state.post.post_error if state.post else None,

        # Latency & cost
        "total_latency_ms": state.meta.total_latency_ms if state.meta else 0,
        "tool_latencies": state.meta.tool_latencies if state.meta else {},
        "trace_id": state.meta.trace_id if state.meta else "",
    }

    # Append to JSONL file (one JSON object per line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def read_logs() -> list[dict]:
    """Read all log entries from the log file."""
    if not os.path.exists(LOG_FILE):
        return []

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    return entries


def clear_logs():
    """Clear the log file. Use for testing only."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)