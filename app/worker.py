import signal
import sys
from app.queue import dequeue, queue_length
from app.orchestrator import run_pipeline
from app.nodes.retrieve import get_vectorstore

running = True


def shutdown(signum, frame):
    global running
    print("\nShutting down worker...")
    running = False


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


def main():
    print("Pre-loading embedding model...")
    get_vectorstore()
    print("Embedding model ready.")

    print("=" * 60)
    print("Pipeline Worker started")
    print("Polling Redis for jobs...")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    jobs_processed = 0
    jobs_failed = 0

    while running:
        ticket_input = dequeue(timeout=5)

        if ticket_input is None:
            continue

        pending = queue_length()
        print(f"\nJob received: {ticket_input.ticket_key} | {pending} more in queue")

        try:
            result = run_pipeline(ticket_input)
            jobs_processed += 1

            decision = result.gate.decision.value if result.gate else "unknown"
            posted = result.post.posted if result.post else False
            latency = result.meta.total_latency_ms if result.meta else 0

            print(f"Job complete: {ticket_input.ticket_key} | {decision} | posted={posted} | {latency}ms")

        except Exception as e:
            jobs_failed += 1
            print(f"Job failed: {ticket_input.ticket_key} | Error: {e}")

    print(f"\nWorker stopped. Processed: {jobs_processed}, Failed: {jobs_failed}")


if __name__ == "__main__":
    main()