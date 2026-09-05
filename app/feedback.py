"""
FEEDBACK MODULE

Captures two types of data:

1. Agent feedback — when a human approves, rejects, or edits an AI draft.
   Rejected/edited responses become negative eval examples.
   Over time, this builds the golden dataset automatically.

2. Missing KB articles — when retrieval fails (confident=false),
   logs the query. The most frequent failing queries tell you
   which help articles to write next.

Files:
  logs/feedback.jsonl        — agent feedback entries
  logs/missing_articles.jsonl — retrieval failures
"""

import os
import json
from datetime import datetime, timezone
from collections import Counter

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
FEEDBACK_FILE = os.path.join(LOGS_DIR, "feedback.jsonl")
MISSING_ARTICLES_FILE = os.path.join(LOGS_DIR, "missing_articles.jsonl")


# ─── Agent Feedback ───────────────────────────────────────

def log_feedback(
    ticket_key: str,
    action: str,
    ai_response: str = "",
    corrected_response: str = "",
    agent_notes: str = "",
) -> dict:
    """Log agent feedback on a pipeline response.

    action: "approved" | "rejected" | "edited"
    - approved: agent sent the AI draft as-is
    - edited: agent modified the draft before sending
    - rejected: agent discarded the draft and wrote from scratch
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_key": ticket_key,
        "action": action,
        "ai_response": ai_response,
        "corrected_response": corrected_response,
        "agent_notes": agent_notes,
    }

    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def read_feedback() -> list[dict]:
    """Read all feedback entries."""
    if not os.path.exists(FEEDBACK_FILE):
        return []

    entries = []
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def feedback_stats() -> dict:
    """Calculate feedback statistics."""
    entries = read_feedback()
    if not entries:
        return {"total": 0, "approved": 0, "edited": 0, "rejected": 0, "approval_rate": 0}

    total = len(entries)
    approved = sum(1 for e in entries if e["action"] == "approved")
    edited = sum(1 for e in entries if e["action"] == "edited")
    rejected = sum(1 for e in entries if e["action"] == "rejected")
    approval_rate = ((approved + edited) / total * 100) if total > 0 else 0

    return {
        "total": total,
        "approved": approved,
        "edited": edited,
        "rejected": rejected,
        "approval_rate": round(approval_rate, 1),
    }


# ─── Missing KB Articles ─────────────────────────────────

def log_missing_article(
    ticket_key: str,
    query: str,
    intent: str,
    product_area: str,
    subject: str,
) -> dict:
    """Log a retrieval failure — no relevant docs found.

    Call this from the orchestrator when retrieval_confident = false.
    Aggregating these over time reveals which articles are missing.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_key": ticket_key,
        "query": query,
        "intent": intent,
        "product_area": product_area,
        "subject": subject,
    }

    with open(MISSING_ARTICLES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def read_missing_articles() -> list[dict]:
    """Read all missing article entries."""
    if not os.path.exists(MISSING_ARTICLES_FILE):
        return []

    entries = []
    with open(MISSING_ARTICLES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def top_missing_topics(n: int = 10) -> list[tuple[str, int]]:
    """Find the most frequently missed topics.

    Returns list of (product_area, count) sorted by frequency.
    These are the articles you should write next.
    """
    entries = read_missing_articles()
    if not entries:
        return []

    # Count by product_area
    area_counts = Counter(e["product_area"] for e in entries)
    return area_counts.most_common(n)


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    print("Testing feedback module...\n")

    # Test feedback logging
    log_feedback(
        ticket_key="KAN-99",
        action="edited",
        ai_response="Original AI response here",
        corrected_response="Agent's corrected version",
        agent_notes="Changed tone, added specific link",
    )
    log_feedback(
        ticket_key="KAN-100",
        action="approved",
        ai_response="AI response was good",
    )
    log_feedback(
        ticket_key="KAN-101",
        action="rejected",
        ai_response="AI response was wrong",
        agent_notes="Completely wrong article referenced",
    )

    stats = feedback_stats()
    print(f"Feedback stats: {stats}")

    # Test missing article logging
    log_missing_article(
        ticket_key="KAN-102",
        query="mobile app crash android",
        intent="bug_report_unknown",
        product_area="mobile",
        subject="App crashes on Android",
    )
    log_missing_article(
        ticket_key="KAN-103",
        query="mobile app login failed",
        intent="bug_report_unknown",
        product_area="mobile",
        subject="Can't log in on mobile",
    )

    top_missing = top_missing_topics()
    print(f"\nTop missing topics: {top_missing}")
    print("\nDone.")