"""
WEBHOOK RECEIVER

FastAPI app that receives Jira webhooks and pushes jobs to Redis.
The pipeline runs in the background via the worker process.

Flow:
  Jira webhook → FastAPI → push to Redis queue → respond instantly
  Worker (separate process) → pull from Redis → run pipeline → post to Jira

Run:
  Terminal 1: ollama serve
  Terminal 2: uvicorn app.main:app --reload --port 8000
  Terminal 3: npx localtunnel --port 8000 --subdomain tickettriage
  Terminal 4: python -m app.worker
"""
from app.feedback import log_feedback, feedback_stats, read_feedback, top_missing_topics
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from app.feedback import log_feedback, feedback_stats, read_feedback, top_missing_topics

from app.models.schemas import TicketInput
from app.queue import enqueue, queue_length
from app.orchestrator import run_pipeline
from app.nodes.parse import extract_customer_email



import requests
from requests.auth import HTTPBasicAuth
from app.config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN


def fetch_ticket_description(ticket_key: str) -> str:
    """Fetch ticket description directly from Jira API instead of parsing webhook ADF."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_key}"
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    
    try:
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract plain text from ADF
        description_adf = data.get("fields", {}).get("description", {})
        return extract_description_text(description_adf)
    except Exception as e:
        print(f"  Failed to fetch ticket: {e}")
        return ""





# ─── App setup ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Pipeline webhook receiver started")
    print("Waiting for Jira webhooks on POST /webhook/jira")
    print(f"Redis queue length: {queue_length()}")
    yield
    print("Shutting down")


app = FastAPI(
    title="Agent Ticket Triage Pipeline",
    description="Receives Jira webhooks and queues them for AI triage",
    lifespan=lifespan,
)

@app.post("/feedback")
async def submit_feedback(
    ticket_key: str,
    action: str,
    ai_response: str = "",
    corrected_response: str = "",
    agent_notes: str = "",
):
    if action not in ("approved", "rejected", "edited"):
        return {"error": "action must be 'approved', 'rejected', or 'edited'"}

    entry = log_feedback(
        ticket_key=ticket_key,
        action=action,
        ai_response=ai_response,
        corrected_response=corrected_response,
        agent_notes=agent_notes,
    )
    return {"status": "logged", "entry": entry}


@app.get("/feedback/stats")
async def get_feedback_stats():
    return feedback_stats()


@app.get("/feedback/history")
async def get_feedback_history(limit: int = 20):
    entries = read_feedback()
    return {"total": len(entries), "entries": entries[-limit:]}


@app.get("/missing-articles")
async def get_missing_articles():
    return {
        "top_missing": top_missing_topics(10),
        "action": "Write knowledge base articles for these topics to improve auto-resolve rate",
    }

# ─── Health check ──────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "agent-ticket-triage-pipeline",
        "queue_length": queue_length(),
    }


# ─── Jira webhook endpoint ─────────────────────────────────

@app.post("/webhook/jira")
async def jira_webhook(request: Request):
    """Receive a Jira webhook and push to queue.
    
    Responds instantly — pipeline runs in the background via worker.
    """
    payload = await request.json()

    # ── Extract event type ────────────────────────────────
    webhook_event = payload.get("webhookEvent", "")

    if webhook_event not in ("jira:issue_created",):
        return {"status": "ignored", "reason": f"Event type '{webhook_event}' not handled"}

    # ── Extract issue data ────────────────────────────────
    issue = payload.get("issue", {})
    if not issue:
        raise HTTPException(status_code=400, detail="No issue data in webhook payload")

    issue_id = issue.get("id", "")
    issue_key = issue.get("key", "")
    fields = issue.get("fields", {})

    # ── Extract ticket fields ─────────────────────────────
    summary = fields.get("summary", "")

    description = fetch_ticket_description(issue_key)

    priority_obj = fields.get("priority", {})
    priority = priority_obj.get("name", "Medium") if priority_obj else "Medium"

    labels = fields.get("labels", [])

    reporter_email = extract_customer_email(description)

    # ── Build ticket input and queue it ───────────────────
    ticket_input = TicketInput(
        ticket_id=issue_id,
        ticket_key=issue_key,
        raw_subject=summary,
        raw_description=description,
        reporter_email=reporter_email,
        priority=priority,
        labels=labels,
    )

    result = enqueue(ticket_input)
    print(f"Webhook: {issue_key} — {summary} → {result['status']}")

    return result


def extract_description_text(adf: dict) -> str:
    """Extract plain text from Jira's Atlassian Document Format."""
    if not adf or not isinstance(adf, dict):
        return ""

    text_parts = []
    content = adf.get("content", [])
    for block in content:
        if block.get("type") == "paragraph":
            for inline in block.get("content", []):
                if inline.get("type") == "text":
                    text_parts.append(inline.get("text", ""))
        elif block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return "\n".join(text_parts)


# ─── Manual trigger (runs pipeline directly, skips queue) ──

@app.post("/trigger")
async def manual_trigger(ticket_key: str, subject: str, description: str, priority: str = "Medium"):
    """Manually trigger the pipeline without queue.
    
    Usage:
      curl -X POST "http://localhost:8000/trigger?ticket_key=KAN-3&subject=Test&description=Test"
    """
    reporter_email = extract_customer_email(description)

    ticket_input = TicketInput(
        ticket_id="manual",
        ticket_key=ticket_key,
        raw_subject=subject,
        raw_description=description,
        reporter_email=reporter_email,
        priority=priority,
        labels=["support-ticket"],
    )

    result = run_pipeline(ticket_input)

    return {
        "status": "processed",
        "ticket": ticket_key,
        "route": result.classification.route.value if result.classification else "unknown",
        "decision": result.gate.decision.value if result.gate else "unknown",
        "posted": result.post.posted if result.post else False,
        "latency_ms": result.meta.total_latency_ms if result.meta else 0,
    }


# ─── Queue status endpoint ────────────────────────────────

@app.get("/queue")
async def get_queue_status():
    """Check how many jobs are waiting."""
    return {"queue_length": queue_length()}