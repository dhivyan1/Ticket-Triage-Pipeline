"""
QUEUE MODULE

Pushes ticket jobs to Redis and pulls them for processing.
Decouples the webhook receiver from the pipeline — webhook responds
instantly, pipeline runs in the background.

Redis key: "pipeline:jobs" (a Redis list used as a FIFO queue)
"""

import json
import hashlib
import redis

from app.config import REDIS_HOST, REDIS_PORT
from app.models.schemas import TicketInput


# ─── Redis connection ──────────────────────────────────────

def get_redis() -> redis.Redis:
    """Get a Redis connection."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_timeout=30,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )


QUEUE_KEY = "pipeline:jobs"
PROCESSED_KEY = "pipeline:processed"


# ─── Push a job ────────────────────────────────────────────

def enqueue(ticket_input: TicketInput) -> dict:
    """Push a ticket to the queue for background processing.
    
    Returns:
        {"status": "queued", "ticket": "KAN-5", "position": 3}
        {"status": "duplicate", "ticket": "KAN-5"}
    """
    r = get_redis()

    # Idempotency: check if already processed or queued
    event_hash = hashlib.md5(
        f"{ticket_input.ticket_id}:{ticket_input.ticket_key}".encode()
    ).hexdigest()

    if r.sismember(PROCESSED_KEY, event_hash):
        return {"status": "duplicate", "ticket": ticket_input.ticket_key}

    # Mark as seen
    r.sadd(PROCESSED_KEY, event_hash)
    # Expire after 1 hour (prevent set from growing forever)
    r.expire(PROCESSED_KEY, 3600)

    # Serialize and push to queue
    job = {
        "ticket_id": ticket_input.ticket_id,
        "ticket_key": ticket_input.ticket_key,
        "raw_subject": ticket_input.raw_subject,
        "raw_description": ticket_input.raw_description,
        "reporter_email": ticket_input.reporter_email,
        "priority": ticket_input.priority,
        "labels": ticket_input.labels,
        "triggered_at": ticket_input.triggered_at.isoformat(),
    }

    r.rpush(QUEUE_KEY, json.dumps(job))
    position = r.llen(QUEUE_KEY)

    return {"status": "queued", "ticket": ticket_input.ticket_key, "position": position}


# ─── Pull a job ────────────────────────────────────────────

def dequeue(timeout: int = 5) -> TicketInput | None:
    """Pull the next ticket from the queue. Blocks for `timeout` seconds.
    
    Returns TicketInput or None if queue is empty after timeout.
    """
    r = get_redis()

    # BLPOP blocks until a job is available (or timeout)
    result = r.blpop(QUEUE_KEY, timeout=timeout)

    if result is None:
        return None

    _, job_json = result
    job = json.loads(job_json)

    return TicketInput(
        ticket_id=job["ticket_id"],
        ticket_key=job["ticket_key"],
        raw_subject=job["raw_subject"],
        raw_description=job["raw_description"],
        reporter_email=job["reporter_email"],
        priority=job["priority"],
        labels=job["labels"],
    )


# ─── Queue info ────────────────────────────────────────────

def queue_length() -> int:
    """How many jobs are waiting."""
    r = get_redis()
    return r.llen(QUEUE_KEY)


def clear_queue():
    """Clear all pending jobs. Use for testing only."""
    r = get_redis()
    r.delete(QUEUE_KEY)
    r.delete(PROCESSED_KEY)


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    # Test push and pull
    print("Testing Redis queue...\n")

    clear_queue()
    print(f"Queue length: {queue_length()}")

    # Push a test job
    test_input = TicketInput(
        ticket_id="test-001",
        ticket_key="KAN-99",
        raw_subject="Test ticket",
        raw_description="Customer: test@test.com\n\nThis is a test.",
        reporter_email="test@test.com",
        priority="Medium",
        labels=["support-ticket"],
    )

    result = enqueue(test_input)
    print(f"Enqueue: {result}")
    print(f"Queue length: {queue_length()}")

    # Try duplicate
    result2 = enqueue(test_input)
    print(f"Duplicate: {result2}")
    print(f"Queue length: {queue_length()}")

    # Pull the job
    job = dequeue(timeout=1)
    if job:
        print(f"\nDequeued: {job.ticket_key} — {job.raw_subject}")
        print(f"Email: {job.reporter_email}")
    else:
        print("No job found")

    print(f"Queue length: {queue_length()}")

    clear_queue()
    print("\nDone.")