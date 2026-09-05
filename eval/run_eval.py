"""Run the pipeline against the golden dataset and score the results.

    python eval/run_eval.py                       # full run
    python eval/run_eval.py --limit 10            # smoke test
    python eval/run_eval.py --no-judge            # skip the LLM judge (fast, CI-safe)
    python eval/run_eval.py --fail-under 0.85     # exit 1 if routing accuracy drops

The `--fail-under` flag is what CI uses. Everything else is for iterating
locally.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Posting to Jira from an eval run would be a very bad afternoon.
os.environ.setdefault("ITRE_DRY_RUN", "true")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.schemas import Ticket  # noqa: E402
from app.orchestrator import run_pipeline  # noqa: E402
from eval import metrics  # noqa: E402

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_dataset.json")


def load_golden(limit: int | None) -> list[dict]:
    with open(GOLDEN_PATH, encoding="utf-8") as fh:
        cases = json.load(fh)["cases"]
    return cases[:limit] if limit else cases


def run_case(case: dict, use_judge: bool) -> dict:
    ticket = Ticket(
        ticket_id=case["ticket_id"],
        summary=case["summary"],
        description=case["description"],
        reporter_email=case.get("reporter_email"),
        labels=case.get("labels", []),
    )

    state = run_pipeline(ticket)

    classification = state.get("classification")
    draft = state.get("draft")
    docs = state.get("docs", [])

    actual_route = classification.route.value if classification else "error"
    body = draft.body if draft else ""

    result = {
        "ticket_id": case["ticket_id"],
        "expected_route": case["expected_route"],
        "actual_route": actual_route,
        "route_correct": actual_route == case["expected_route"],
        "matched_rule": classification.matched_rule if classification else None,
        "keyword_recall": metrics.keyword_recall(body, case.get("expected_points", [])),
        "citation_precision": metrics.citation_precision(
            draft.citations if draft else [], [d.source for d in docs]
        ),
        "retrieved": [d.source for d in docs],
        "gate_action": state["gate"].action if state.get("gate") else None,
        "errors": state.get("errors", []),
        "response": body,
    }

    if use_judge and body:
        claims = metrics.judge_hallucinations(body, [d.content for d in docs])
        result["ungrounded_claims"] = claims
    else:
        result["ungrounded_claims"] = []

    return result


def summarize(results: list[dict], use_judge: bool) -> dict:
    routing = metrics.score_routing(
        (r["expected_route"], r["actual_route"]) for r in results
    )
    scored = [r for r in results if r["response"]]

    summary = {
        "cases": len(results),
        "routing_accuracy": round(routing.accuracy, 4),
        "unsafe_auto_rate": round(routing.unsafe_auto_rate(), 4),
        "mean_keyword_recall": round(
            sum(r["keyword_recall"] for r in scored) / len(scored), 4
        )
        if scored
        else 0.0,
        "mean_citation_precision": round(
            sum(r["citation_precision"] for r in scored) / len(scored), 4
        )
        if scored
        else 0.0,
        "error_count": sum(1 for r in results if r["errors"]),
        "confusion": {f"{e}->{a}": n for (e, a), n in sorted(routing.confusion.items())},
    }

    if use_judge:
        summary["hallucination_rate"] = round(
            metrics.hallucination_rate([r["ungrounded_claims"] for r in scored]), 4
        )

    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM grounding judge")
    ap.add_argument("--fail-under", type=float, default=None, help="min routing accuracy")
    ap.add_argument("--out", default="eval/results.json")
    args = ap.parse_args()

    use_judge = not args.no_judge
    cases = load_golden(args.limit)

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['ticket_id']}", flush=True)
        results.append(run_case(case, use_judge))

    summary = summarize(results, use_judge)

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "summary": summary,
        "results": results,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print("\n--- summary ---")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\nwrote {args.out}")

    if args.fail_under is not None and summary["routing_accuracy"] < args.fail_under:
        print(
            f"\nFAIL: routing accuracy {summary['routing_accuracy']} "
            f"below threshold {args.fail_under}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
