"""Draft Agent — single responsibility: personalized draft reply generation (FR-009).

contracts/agent-interfaces.md: input {review_id, sentiment, topics, severity}, output
{review_id, draft_content}. Precondition (FR-020): the Orchestrator MUST NOT invoke this
agent for a review with `existing_owner_reply = true` — enforced in orchestrator.py, not
here, so this agent stays a pure "given a review, draft a reply" unit.

Output is NEVER sent to the GBP reply endpoint directly (Principle I) — it is only ever
written as a DraftReply with status=pending by the Orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.integrations.gemini_client import GeminiClient, get_gemini_client
from src.models.review import Review


@dataclass
class DraftOutput:
    review_id: str
    draft_content: str


class DraftAgent:
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self._gemini = gemini_client or get_gemini_client()

    def run(self, review: Review) -> DraftOutput:
        if review.sentiment is None or review.severity is None:
            raise ValueError(
                f"Review {review.review_id} must be analyzed and triaged before drafting"
            )
        content = self._gemini.draft_reply(
            review_text=review.text,
            rating=review.rating,
            sentiment=review.sentiment.value,
            topics=review.topics,
            severity=review.severity.value,
        )
        return DraftOutput(review_id=review.review_id, draft_content=content)
