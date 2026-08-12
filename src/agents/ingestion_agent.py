"""Ingestion Agent — single responsibility: pull reviews for a branch (FR-002/FR-017).

contracts/agent-interfaces.md: input {branch_id}, output {reviews: Review[]} (status=new).
On GBP error, falls back to seed data (handled inside gbp_client) and MUST surface a sync
error distinctly from "zero new reviews" (Edge Cases) — see T029 in tasks.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.logging import get_logger
from src.integrations.gbp_client import GbpApiError, GbpClient, RawReview, get_gbp_client
from src.models.branch import Branch, ConnectionStatus
from src.models.review import Review, ReviewLanguage, ReviewStatus
from src.storage.firestore_repo import Repository

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    branch_id: str
    reviews: list[Review]
    sync_error: str | None  # non-None distinguishes a failed sync from a genuinely empty one


class IngestionAgent:
    def __init__(self, repo: Repository, gbp_client: GbpClient | None = None) -> None:
        self._repo = repo
        self._gbp = gbp_client or get_gbp_client()

    def run(self, branch: Branch) -> IngestionResult:
        try:
            raw_reviews = self._gbp.list_reviews_since(
                branch_id=branch.branch_id,
                gbp_location_id=branch.gbp_location_id,
                oauth_credential_ref=branch.oauth_credential_ref,
                since=branch.last_ingested_at,
            )
        except GbpApiError as exc:
            logger.error("Ingestion sync error for branch %s: %s", branch.branch_id, exc)
            branch.connection_status = ConnectionStatus.ERROR
            self._repo.save_branch(branch)
            return IngestionResult(branch_id=branch.branch_id, reviews=[], sync_error=str(exc))

        new_reviews: list[Review] = []
        for raw in raw_reviews:
            if self._repo.get_review(raw.review_id) is not None:
                continue  # already ingested — dedupe, don't reset an in-progress review
            review = _raw_to_review(raw, branch_id=branch.branch_id)
            self._repo.save_review(review)
            new_reviews.append(review)

        branch.connection_status = ConnectionStatus.CONNECTED
        self._repo.save_branch(branch)

        if new_reviews:
            logger.info(
                "Ingested %d new review(s) for branch %s", len(new_reviews), branch.branch_id
            )
        else:
            logger.info("No new reviews for branch %s (zero new, not an error)", branch.branch_id)

        return IngestionResult(branch_id=branch.branch_id, reviews=new_reviews, sync_error=None)


def _raw_to_review(raw: RawReview, branch_id: str) -> Review:
    return Review(
        review_id=raw.review_id,
        branch_id=branch_id,
        rating=raw.rating,
        text=raw.text,
        reviewer_name=raw.reviewer_name,
        posted_at=raw.posted_at,
        language=_safe_language(raw.language),
        existing_owner_reply=raw.existing_owner_reply,
        status=ReviewStatus.NEW,
    )


def _safe_language(value: str) -> ReviewLanguage:
    try:
        return ReviewLanguage(value)
    except ValueError:
        return ReviewLanguage.OTHER
