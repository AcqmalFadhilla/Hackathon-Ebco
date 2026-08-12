"""Unit tests for Analysis Agent — FR-003/FR-004/FR-005. tasks.md T021."""

from datetime import UTC, datetime

from src.agents.analysis_agent import AnalysisAgent, detect_language
from src.integrations.gemini_client import AnalysisResult, GeminiUnavailableError
from src.models.review import Review, ReviewLanguage, Sentiment


class _FakeGemini:
    def __init__(self, sentiment="positive", topics=None, raise_error=False) -> None:
        self._sentiment = sentiment
        self._topics = topics or []
        self._raise_error = raise_error

    def analyze_review(self, review_text, rating):
        if self._raise_error:
            raise GeminiUnavailableError("simulated outage")
        return AnalysisResult(sentiment=self._sentiment, topics=self._topics)


def _make_review(text: str, rating: int) -> Review:
    return Review(
        review_id="r1",
        branch_id="b1",
        rating=rating,
        text=text,
        reviewer_name="Test User",
        posted_at=datetime.now(UTC),
    )


def test_run_returns_sentiment_and_topics_for_indonesian_review():
    agent = AnalysisAgent(gemini_client=_FakeGemini(sentiment="negative", topics=["layanan"]))
    review = _make_review("Pelayanannya lambat sekali", rating=2)

    output = agent.run(review)

    assert output.sentiment == Sentiment.NEGATIVE
    assert output.topics == ["layanan"]


def test_run_returns_sentiment_and_topics_for_english_review():
    agent = AnalysisAgent(gemini_client=_FakeGemini(sentiment="positive", topics=["service"]))
    review = _make_review("Great service, friendly staff", rating=5)

    output = agent.run(review)

    assert output.sentiment == Sentiment.POSITIVE
    assert output.topics == ["service"]


def test_run_falls_back_to_rating_derived_sentiment_when_gemini_unavailable():
    agent = AnalysisAgent(gemini_client=_FakeGemini(raise_error=True))
    review = _make_review("Some review in an unsupported language", rating=1)

    output = agent.run(review)

    assert output.sentiment == Sentiment.NEGATIVE  # rating=1 -> negative fallback
    assert output.topics == []


def test_detect_language_identifies_indonesian():
    assert detect_language("Pelayanan yang sangat ramah dan cepat") == ReviewLanguage.ID


def test_detect_language_identifies_english():
    assert detect_language("Great service and friendly staff") == ReviewLanguage.EN
