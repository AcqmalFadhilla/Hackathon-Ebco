"""Triage Agent — single responsibility: severity scoring (FR-006/FR-007).

contracts/agent-interfaces.md: input {review_id, sentiment, topics}, output
{review_id, severity}. Shared Foundational capability — both the draft flow (US2) and the
urgent-escalation flow (US3) build on this agent's output.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.integrations.gemini_client import GeminiClient, get_gemini_client
from src.models.review import Review, Severity


@dataclass
class TriageOutput:
    review_id: str
    severity: Severity
    reason: str


class TriageAgent:
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self._gemini = gemini_client or get_gemini_client()

    def run(self, review: Review) -> TriageOutput:
        if review.sentiment is None:
            raise ValueError(f"Review {review.review_id} must be analyzed before triage")

        result = self._gemini.score_severity(
            review_text=review.text,
            rating=review.rating,
            sentiment=review.sentiment.value,
            topics=review.topics,
        )
        severity = Severity(result.severity)
        return TriageOutput(review_id=review.review_id, severity=severity, reason=result.reason)
