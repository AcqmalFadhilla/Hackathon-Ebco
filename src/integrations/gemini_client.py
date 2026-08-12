"""Gemini/Vertex AI adapter — sentiment, topic tagging, severity scoring, draft generation.

Wrapped with tenacity retry/backoff per constitution Principle IV. Lazily creates the
`google-genai` client so importing this module never requires live credentials (tests can
monkeypatch `GeminiClient.generate_json` / `.generate_text` directly).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.logging import get_logger
from src.config.settings import SETTINGS

logger = get_logger(__name__)

_RETRY = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=8),
    "reraise": True,
}


@dataclass
class AnalysisResult:
    sentiment: str  # "positive" | "neutral" | "negative"
    topics: list[str]


@dataclass
class SeverityResult:
    severity: str  # "routine" | "urgent"
    reason: str


class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini can't be reached after retries — callers MUST have a fallback
    (Principle IV), never let this crash the whole ingestion/draft pipeline."""


class GeminiClient:
    def __init__(self, model: str | None = None) -> None:
        self._model_name = model or SETTINGS.gemini_model
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            from google import genai  # lazy import — no credentials needed until first call

            self._client = genai.Client()
        return self._client

    @retry(**_RETRY)
    def _generate(self, prompt: str, *, response_mime_type: str = "text/plain") -> str:
        client = self._get_client()
        response = client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config={"response_mime_type": response_mime_type} if response_mime_type else None,
        )
        text = getattr(response, "text", None)
        if not text:
            raise GeminiUnavailableError("Empty response from Gemini")
        return text

    def analyze_review(self, review_text: str, rating: int) -> AnalysisResult:
        """FR-003/FR-004: sentiment + topic tags. ID/EN supported (FR-005)."""
        prompt = (
            "You are analyzing a customer review for a local business (Indonesian or English "
            "text). Classify sentiment and extract complaint/topic tags.\n\n"
            f'Rating: {rating}/5\nReview: "{review_text}"\n\n'
            'Respond as strict JSON: {"sentiment": "positive|neutral|negative", '
            '"topics": ["service", "cleanliness", "price", ...]} (topics: 0-4 short lowercase '
            "tags, empty list if none apply, no extra keys, no prose)."
        )
        try:
            raw = self._generate(prompt, response_mime_type="application/json")
            data: dict[str, Any] = json.loads(raw)
            sentiment = str(data.get("sentiment", "neutral")).lower()
            if sentiment not in {"positive", "neutral", "negative"}:
                sentiment = "neutral"
            topics = [str(t).lower() for t in data.get("topics", []) if str(t).strip()][:4]
            return AnalysisResult(sentiment=sentiment, topics=topics)
        except Exception as exc:
            logger.warning("Gemini analyze_review failed after retries: %s", exc)
            raise GeminiUnavailableError(str(exc)) from exc

    def score_severity(
        self, review_text: str, rating: int, sentiment: str, topics: list[str]
    ) -> SeverityResult:
        """FR-006/FR-007: severity/urgency, combining rule-based keywords + Gemini judgment."""
        keyword_hit = any(k.lower() in review_text.lower() for k in SETTINGS.urgent_severity_keywords)
        if keyword_hit and rating <= 2:
            return SeverityResult(severity="urgent", reason="keyword+rating heuristic")

        prompt = (
            "You triage a customer review for urgency. 'urgent' means it signals a serious, "
            "safety-relevant, or reputation-critical issue (e.g. safety, health, "
            "discrimination, major service failure) that needs a manager's immediate "
            "attention — not just a routine complaint.\n\n"
            f'Rating: {rating}/5\nSentiment: {sentiment}\nTopics: {topics}\nReview: "{review_text}"\n\n'
            'Respond as strict JSON: {"severity": "routine|urgent", "reason": "short reason"}.'
        )
        try:
            raw = self._generate(prompt, response_mime_type="application/json")
            data = json.loads(raw)
            severity = str(data.get("severity", "routine")).lower()
            if severity not in {"routine", "urgent"}:
                severity = "routine"
            return SeverityResult(severity=severity, reason=str(data.get("reason", "")))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini score_severity failed, defaulting to routine: %s", exc)
            return SeverityResult(severity="routine", reason=f"fallback after error: {exc}")

    def draft_reply(
        self, review_text: str, rating: int, sentiment: str, topics: list[str], severity: str
    ) -> str:
        """FR-009: personalized draft reply. Never auto-published (Principle I)."""
        prompt = (
            "Draft a short, warm, professional owner reply to this customer review, in the "
            "same language the review was written in (Indonesian or English). Acknowledge "
            "specifics from the review, do not make promises the business can't keep, and "
            "keep it under 80 words. This is a DRAFT for a human manager to review/edit "
            "before it is ever published — do not include placeholders like [Name].\n\n"
            f'Rating: {rating}/5\nSentiment: {sentiment}\nTopics: {topics}\nReview: "{review_text}"\n\n'
            "Reply with only the reply text, no preamble."
        )
        try:
            return self._generate(prompt, response_mime_type="text/plain").strip()
        except Exception as exc:
            logger.warning("Gemini draft_reply failed after retries: %s", exc)
            raise GeminiUnavailableError(str(exc)) from exc


_client_singleton: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = GeminiClient()
    return _client_singleton
