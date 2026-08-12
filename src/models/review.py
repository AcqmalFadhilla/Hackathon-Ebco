"""Review entity — data-model.md § Review, including the status state machine.

State machine (data-model.md § Review status state machine):
    new -> analyzed -> already_answered (existing_owner_reply, FR-020)
    new -> analyzed -> drafted -> approved -> published
                          `-> rejected -> drafted (new draft generated)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Severity(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"


class ReviewLanguage(str, Enum):
    ID = "id"
    EN = "en"
    OTHER = "other"


class ReviewStatus(str, Enum):
    NEW = "new"
    ANALYZED = "analyzed"
    DRAFTED = "drafted"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ALREADY_ANSWERED = "already_answered"  # FR-020


VALID_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.NEW: {ReviewStatus.ANALYZED},
    ReviewStatus.ANALYZED: {ReviewStatus.DRAFTED, ReviewStatus.ALREADY_ANSWERED},
    ReviewStatus.DRAFTED: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.APPROVED: {ReviewStatus.PUBLISHED},
    ReviewStatus.REJECTED: {ReviewStatus.DRAFTED},
    ReviewStatus.PUBLISHED: set(),
    ReviewStatus.ALREADY_ANSWERED: set(),
}


def assert_valid_transition(current: ReviewStatus, target: ReviewStatus) -> None:
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid Review status transition: {current.value} -> {target.value}")


@dataclass
class Review:
    review_id: str
    branch_id: str
    rating: int
    text: str
    reviewer_name: str
    posted_at: datetime
    language: ReviewLanguage = ReviewLanguage.OTHER
    sentiment: Sentiment | None = None
    topics: list[str] = field(default_factory=list)
    severity: Severity | None = None
    status: ReviewStatus = ReviewStatus.NEW
    existing_owner_reply: bool = False
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, target: ReviewStatus) -> None:
        assert_valid_transition(self.status, target)
        self.status = target

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "branch_id": self.branch_id,
            "rating": self.rating,
            "text": self.text,
            "reviewer_name": self.reviewer_name,
            "posted_at": self.posted_at,
            "language": self.language.value,
            "sentiment": self.sentiment.value if self.sentiment else None,
            "topics": self.topics,
            "severity": self.severity.value if self.severity else None,
            "status": self.status.value,
            "existing_owner_reply": self.existing_owner_reply,
            "ingested_at": self.ingested_at,
        }

    @staticmethod
    def from_dict(data: dict) -> Review:
        return Review(
            review_id=data["review_id"],
            branch_id=data["branch_id"],
            rating=data["rating"],
            text=data.get("text", ""),
            reviewer_name=data.get("reviewer_name", ""),
            posted_at=data["posted_at"],
            language=ReviewLanguage(data.get("language", "other")),
            sentiment=Sentiment(data["sentiment"]) if data.get("sentiment") else None,
            topics=list(data.get("topics", [])),
            severity=Severity(data["severity"]) if data.get("severity") else None,
            status=ReviewStatus(data.get("status", "new")),
            existing_owner_reply=bool(data.get("existing_owner_reply", False)),
            ingested_at=data.get("ingested_at") or datetime.now(UTC),
        )
