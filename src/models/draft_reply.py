"""Draft Reply entity — data-model.md § Draft Reply."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class PublicationState(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class DraftReply:
    draft_id: str
    review_id: str
    content: str
    status: DraftStatus = DraftStatus.PENDING
    approved_by: str | None = None  # Manager.google_identity_email, never free text (FR-019)
    approved_at: datetime | None = None
    publication_state: PublicationState = PublicationState.NOT_SUBMITTED
    edit_distance: int | None = None  # SC-006 instrumentation

    def to_dict(self) -> dict:
        return {
            "draft_id": self.draft_id,
            "review_id": self.review_id,
            "content": self.content,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "publication_state": self.publication_state.value,
            "edit_distance": self.edit_distance,
        }

    @staticmethod
    def from_dict(data: dict) -> DraftReply:
        return DraftReply(
            draft_id=data["draft_id"],
            review_id=data["review_id"],
            content=data.get("content", ""),
            status=DraftStatus(data.get("status", "pending")),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            publication_state=PublicationState(data.get("publication_state", "not_submitted")),
            edit_distance=data.get("edit_distance"),
        )
