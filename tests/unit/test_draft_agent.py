"""Unit tests for Draft Agent — FR-009. tasks.md T030."""

from datetime import UTC, datetime

import pytest

from src.agents.draft_agent import DraftAgent
from src.models.review import Review, Sentiment, Severity


class _FakeGemini:
    def __init__(self, content: str = "Terima kasih atas review-nya!") -> None:
        self._content = content

    def draft_reply(self, review_text, rating, sentiment, topics, severity):
        return self._content


def _make_analyzed_review() -> Review:
    review = Review(
        review_id="r1",
        branch_id="b1",
        rating=4,
        text="Pelayanan baik, cuma agak lama",
        reviewer_name="Test User",
        posted_at=datetime.now(UTC),
    )
    review.sentiment = Sentiment.POSITIVE
    review.topics = ["service"]
    review.severity = Severity.ROUTINE
    return review


def test_run_returns_draft_content_for_analyzed_and_triaged_review():
    agent = DraftAgent(gemini_client=_FakeGemini(content="Terima kasih atas masukannya!"))
    review = _make_analyzed_review()

    output = agent.run(review)

    assert output.review_id == "r1"
    assert output.draft_content == "Terima kasih atas masukannya!"


def test_run_raises_if_review_not_yet_triaged():
    agent = DraftAgent(gemini_client=_FakeGemini())
    review = _make_analyzed_review()
    review.severity = None  # not triaged yet

    with pytest.raises(ValueError):
        agent.run(review)


def test_run_raises_if_review_not_yet_analyzed():
    agent = DraftAgent(gemini_client=_FakeGemini())
    review = _make_analyzed_review()
    review.sentiment = None  # not analyzed yet

    with pytest.raises(ValueError):
        agent.run(review)
