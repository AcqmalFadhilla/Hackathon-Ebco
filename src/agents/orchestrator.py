"""Orchestrator — sequences the 5 agents and enforces the two rules that MUST be code, not
agent discretion (constitution Principle I and FR-020):

1. A reply is NEVER published without a recorded, authenticated manager approval.
2. Draft Agent is NEVER invoked for a review that already has an existing owner reply.

Deliberately plain, deterministic Python (not an LLM-driven control loop) — the pipeline's
sequencing and the approval gate must be verifiable by reading the code, not trusted to an
agent's judgment. See docs: contracts/agent-interfaces.md, plan.md Constitution Check.
"""

from __future__ import annotations

import difflib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.agents.analysis_agent import AnalysisAgent
from src.agents.draft_agent import DraftAgent
from src.agents.ingestion_agent import IngestionAgent, IngestionResult
from src.agents.reporting_agent import DigestOutput, ReportingAgent
from src.agents.triage_agent import TriageAgent
from src.config.logging import get_logger
from src.integrations.gbp_client import GbpApiError, GbpClient, get_gbp_client
from src.models.branch import Branch
from src.models.draft_reply import DraftReply, DraftStatus, PublicationState
from src.models.review import Review, ReviewStatus
from src.storage.firestore_repo import Repository

logger = get_logger(__name__)


class ApprovalRequiredError(RuntimeError):
    """Raised if publish is ever attempted without a valid approval. This exists so the
    invariant is enforced in code, not just in review — see tests/integration/
    test_orchestrator_pipeline.py and quickstart.md's Approval-gate check."""


@dataclass
class PublishOutcome:
    review_id: str
    publication_state: PublicationState
    error: str | None = None
    simulated: bool = False  # True only under SIMULATE_PUBLISH_FOR_DEMO (see gbp_client.py)


@dataclass
class CycleReport:
    ingestion_results: list[IngestionResult] = field(default_factory=list)
    newly_urgent_review_ids: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(
        self,
        repo: Repository,
        ingestion_agent: IngestionAgent | None = None,
        analysis_agent: AnalysisAgent | None = None,
        triage_agent: TriageAgent | None = None,
        draft_agent: DraftAgent | None = None,
        reporting_agent: ReportingAgent | None = None,
        gbp_client: GbpClient | None = None,
    ) -> None:
        self._repo = repo
        self._gbp = gbp_client or get_gbp_client()
        self._ingestion = ingestion_agent or IngestionAgent(repo, self._gbp)
        self._analysis = analysis_agent or AnalysisAgent()
        self._triage = triage_agent or TriageAgent()
        self._draft = draft_agent or DraftAgent()
        self._reporting = reporting_agent or ReportingAgent(repo)

    # ---- User Story 1: ingestion -> analysis -> triage --------------------------------

    def run_ingestion_cycle(self, branches: list[Branch]) -> CycleReport:
        report = CycleReport()
        for branch in branches:
            result = self._ingestion.run(branch)
            result.reviews = [self._process_new_review(r) for r in result.reviews]
            report.ingestion_results.append(result)
            if result.sync_error is None:
                # Only advance the watermark on a successful sync — on error, the next
                # attempt must still cover the gap (Edge Cases: GBP rate-limited/unavailable).
                branch.last_ingested_at = datetime.now(UTC)
                self._repo.save_branch(branch)
            report.newly_urgent_review_ids.extend(
                r.review_id for r in result.reviews if r.severity and r.severity.value == "urgent"
            )
        return report

    def _process_new_review(self, review: Review) -> Review:
        analysis = self._analysis.run(review)
        review.sentiment = analysis.sentiment
        review.topics = analysis.topics
        review.transition_to(ReviewStatus.ANALYZED)

        triage = self._triage.run(review)
        review.severity = triage.severity
        self._repo.save_review(review)

        if review.existing_owner_reply:
            # FR-020: Draft Agent MUST NOT be invoked for already-answered reviews.
            review.transition_to(ReviewStatus.ALREADY_ANSWERED)
            self._repo.save_review(review)
            logger.info("Review %s already has an owner reply — skipping draft", review.review_id)
            return review

        self._generate_draft(review)
        return review

    def _generate_draft(self, review: Review) -> DraftReply:
        draft_output = self._draft.run(review)
        draft = DraftReply(
            draft_id=f"draft-{uuid.uuid4().hex[:12]}",
            review_id=review.review_id,
            content=draft_output.draft_content,
            status=DraftStatus.PENDING,
        )
        self._repo.save_draft(draft)
        review.transition_to(ReviewStatus.DRAFTED)
        self._repo.save_review(review)
        return draft

    # ---- User Story 2: approve / reject / publish --------------------------------------

    def approve_draft(
        self, draft_id: str, approved_by_email: str, edited_content: str | None = None
    ) -> PublishOutcome:
        """Publish is reachable ONLY through this method, and ONLY with a non-empty
        `approved_by_email` resolved from an authenticated session (src/integrations/auth.py)
        — never a client-supplied/free-text value (FR-019, Principle I)."""
        if not approved_by_email:
            raise ApprovalRequiredError("approve_draft called without an authenticated approver")

        draft = self._get_draft_or_raise(draft_id)
        review = self._repo.get_review(draft.review_id)
        if review is None:
            raise ValueError(f"Review {draft.review_id} not found for draft {draft_id}")

        final_content = edited_content if edited_content is not None else draft.content
        draft.edit_distance = _edit_distance(draft.content, final_content)
        draft.content = final_content
        draft.status = DraftStatus.APPROVED
        draft.approved_by = approved_by_email
        draft.approved_at = datetime.now(UTC)
        self._repo.save_draft(draft)

        review.transition_to(ReviewStatus.APPROVED)
        self._repo.save_review(review)

        branch = self._repo.get_branch(review.branch_id)
        if branch is None:
            raise ValueError(f"Branch {review.branch_id} not found for review {review.review_id}")

        try:
            result = self._gbp.publish_reply(
                gbp_location_id=branch.gbp_location_id,
                oauth_credential_ref=branch.oauth_credential_ref,
                review_id=review.review_id,
                content=final_content,
            )
            pub_state = PublicationState(result.publication_state)
            draft.publication_state = pub_state
            if pub_state == PublicationState.APPROVED:
                draft.status = DraftStatus.PUBLISHED
                review.transition_to(ReviewStatus.PUBLISHED)
            self._repo.save_draft(draft)
            self._repo.save_review(review)
            return PublishOutcome(
                review_id=review.review_id, publication_state=pub_state, simulated=result.simulated
            )
        except GbpApiError as exc:
            logger.error("Publish failed for review %s: %s", review.review_id, exc)
            draft.publication_state = PublicationState.PENDING
            self._repo.save_draft(draft)
            return PublishOutcome(
                review_id=review.review_id,
                publication_state=PublicationState.PENDING,
                error=str(exc),
            )

    def reject_draft(self, draft_id: str) -> DraftReply:
        """No reply is published; a new draft is generated (spec.md US2 AS3)."""
        draft = self._get_draft_or_raise(draft_id)
        draft.status = DraftStatus.REJECTED
        self._repo.save_draft(draft)

        review = self._repo.get_review(draft.review_id)
        if review is None:
            raise ValueError(f"Review {draft.review_id} not found for draft {draft_id}")
        review.transition_to(ReviewStatus.REJECTED)
        self._repo.save_review(review)

        # _generate_draft transitions REJECTED -> DRAFTED once the new draft is saved.
        return self._generate_draft(review)

    def _get_draft_or_raise(self, draft_id: str) -> DraftReply:
        for review in self._repo.list_reviews():
            draft = self._repo.get_active_draft(review.review_id)
            if draft and draft.draft_id == draft_id:
                return draft
        raise ValueError(f"Draft {draft_id} not found")

    # ---- User Story 4: digest -----------------------------------------------------------

    def request_digest(self, branch_ids: list[str], period_days: int = 30) -> DigestOutput:
        return self._reporting.run(branch_ids, period_days=period_days)


def _edit_distance(original: str, edited: str) -> int:
    """Approximate character-level edit distance for SC-006 instrumentation — not published
    anywhere, just recorded on the DraftReply for later analysis of draft quality."""
    if original == edited:
        return 0
    matcher = difflib.SequenceMatcher(a=original, b=edited)
    distance = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            distance += max(i2 - i1, j2 - j1)
    return distance
