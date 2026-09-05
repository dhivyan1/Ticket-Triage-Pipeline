"""Scoring functions for the eval harness.

Two families of metric here, and they are deliberately different in kind:

- **Routing accuracy** is exact-match against the golden label. It is cheap,
  deterministic, and the number that actually matters — a mis-route sends a
  billing dispute to a bot.
- **Response quality** is judged by an LLM. It is slow and noisy, so it runs
  only in eval, never in the request path.
"""

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.config import get_llm
from app.prompts import render


@dataclass
class RoutingScore:
    total: int = 0
    correct: int = 0
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def add(self, expected: str, actual: str) -> None:
        self.total += 1
        if expected == actual:
            self.correct += 1
        key = (expected, actual)
        self.confusion[key] = self.confusion.get(key, 0) + 1

    def unsafe_auto_rate(self) -> float:
        """Fraction of tickets auto-answered that should have had a human.

        The asymmetric error. Routing something to review that could have
        been automated costs a few minutes of an agent's time; auto-posting
        something that needed escalation costs a customer.
        """
        unsafe = sum(
            count
            for (expected, actual), count in self.confusion.items()
            if actual == "auto" and expected in ("review", "escalate")
        )
        return unsafe / self.total if self.total else 0.0


def score_routing(pairs: Iterable[tuple[str, str]]) -> RoutingScore:
    score = RoutingScore()
    for expected, actual in pairs:
        score.add(expected, actual)
    return score


# --- response quality ------------------------------------------------------


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def keyword_recall(response: str, expected_points: list[str]) -> float:
    """How many of the golden answer's key points the response covers.

    Crude on purpose — it is a floor, not a ceiling. A response scoring 0
    here is definitely wrong; a response scoring 1.0 might still be badly
    written, which is what the LLM judge is for.
    """
    if not expected_points:
        return 1.0
    body = _tokens(response)
    hit = sum(1 for point in expected_points if _tokens(point) & body)
    return hit / len(expected_points)


def citation_precision(citations: list[str], allowed_sources: list[str]) -> float:
    """Fraction of cited sources that were actually retrieved."""
    if not citations:
        return 1.0  # nothing claimed, nothing to get wrong
    allowed = set(allowed_sources)
    return sum(1 for c in citations if c in allowed) / len(citations)


def judge_hallucinations(response: str, docs: list[str]) -> list[str]:
    """Ask an LLM which claims in the response are unsupported.

    Returns the list of ungrounded claims; empty means clean. The judge runs
    at temperature 0 and sees only the retrieved documents, so it cannot
    ratify a claim using its own world knowledge.
    """
    from pydantic import BaseModel, Field

    class Verdict(BaseModel):
        ungrounded_claims: list[str] = Field(default_factory=list)

    llm = get_llm(temperature=0.0).with_structured_output(Verdict)
    prompt = render(
        "grounding_judge",
        response=response,
        docs="\n\n---\n\n".join(docs) if docs else "(no sources retrieved)",
    )
    try:
        return llm.invoke(prompt).ungrounded_claims
    except Exception:
        # A judge failure must not be scored as a pass.
        return ["<judge unavailable>"]


def hallucination_rate(results: list[list[str]]) -> float:
    """Fraction of responses with at least one ungrounded claim."""
    if not results:
        return 0.0
    return sum(1 for claims in results if claims) / len(results)
