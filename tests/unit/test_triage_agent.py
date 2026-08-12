"""Unit tests for Triage Agent — FR-006/FR-007. tasks.md T018."""

from datetime import UTC, datetime

import pytest

from src.agents.triage_agent import TriageAgent
from src.integrations.gemini_client import SeverityResult
from src.models.review import Review, ReviewStatus, Sentiment, Severity


class _FakeGemini:
    def __init__(self, severity: str = "routine", reason: str = "fake") -> None:
        self._severity = severity
        self._reason = reason

    def score_severity(self, review_text, rating, sentiment, topics):
        return SeverityResult(severity=self._severity, reason=self._reason)


def _make_review(text: str = "Biasa saja", rating: int = 3, sentiment=Sentiment.NEUTRAL) -> Review:
    review = Review(
        review_id="r1",
        branch_id="b1",
        rating=rating,
        text=text,
        reviewer_name="Test User",
        posted_at=datetime.now(UTC),
    )
    review.sentiment = sentiment
    review.topics = []
    review.status = ReviewStatus.ANALYZED
    return review


def test_run_returns_severity_from_gemini():
    agent = TriageAgent(gemini_client=_FakeGemini(severity="urgent"))
    review = _make_review()

    output = agent.run(review)

    assert output.review_id == "r1"
    assert output.severity == Severity.URGENT


def test_run_defaults_to_routine_when_gemini_says_routine():
    agent = TriageAgent(gemini_client=_FakeGemini(severity="routine"))
    review = _make_review()

    output = agent.run(review)

    assert output.severity == Severity.ROUTINE


def test_run_raises_if_review_not_yet_analyzed():
    agent = TriageAgent(gemini_client=_FakeGemini())
    review = Review(
        review_id="r2",
        branch_id="b1",
        rating=3,
        text="x",
        reviewer_name="y",
        posted_at=datetime.now(UTC),
    )  # sentiment is None — not analyzed yet

    with pytest.raises(ValueError):
        agent.run(review)


def test_run_carries_reason_through_from_client():
    agent = TriageAgent(gemini_client=_FakeGemini(severity="urgent", reason="safety keyword hit"))
    review = _make_review(text="Saya keracunan makanan di sini!", rating=1)

    output = agent.run(review)

    assert output.reason == "safety keyword hit"
