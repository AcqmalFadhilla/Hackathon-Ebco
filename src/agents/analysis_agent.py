"""Analysis Agent — single responsibility: sentiment + topic tagging (FR-003/FR-004/FR-005).

contracts/agent-interfaces.md: input {review} (status new), output {review_id, sentiment,
topics}. Runs for ID/EN reviews; best-effort (never errors) for other languages.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.logging import get_logger
from src.integrations.gemini_client import GeminiClient, GeminiUnavailableError, get_gemini_client
from src.models.review import Review, ReviewLanguage, Sentiment

logger = get_logger(__name__)


@dataclass
class AnalysisOutput:
    review_id: str
    sentiment: Sentiment
    topics: list[str]


class AnalysisAgent:
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self._gemini = gemini_client or get_gemini_client()

    def run(self, review: Review) -> AnalysisOutput:
        try:
            result = self._gemini.analyze_review(review_text=review.text, rating=review.rating)
            return AnalysisOutput(
                review_id=review.review_id,
                sentiment=Sentiment(result.sentiment),
                topics=result.topics,
            )
        except GeminiUnavailableError as exc:
            # Best-effort per FR-005/Assumptions: never error out ingestion for one review's
            # analysis failure — fall back to a rating-derived sentiment, no topics.
            logger.warning(
                "Analysis fallback for review %s (language=%s): %s",
                review.review_id,
                review.language.value,
                exc,
            )
            return AnalysisOutput(
                review_id=review.review_id,
                sentiment=_sentiment_from_rating(review.rating),
                topics=[],
            )


def _sentiment_from_rating(rating: int) -> Sentiment:
    if rating >= 4:
        return Sentiment.POSITIVE
    if rating == 3:
        return Sentiment.NEUTRAL
    return Sentiment.NEGATIVE


def detect_language(text: str) -> ReviewLanguage:
    """Lightweight heuristic — not a full language detector, just enough to record FR-005
    coverage. Common Indonesian function words vs. default to English/other."""
    id_markers = {"yang", "dengan", "tidak", "saya", "sangat", "nya", "dan", "untuk", "ini", "banget"}
    words = {w.strip(".,!?").lower() for w in text.split()}
    if words & id_markers:
        return ReviewLanguage.ID
    if text.strip() and all(ord(c) < 128 for c in text):
        return ReviewLanguage.EN
    return ReviewLanguage.OTHER
