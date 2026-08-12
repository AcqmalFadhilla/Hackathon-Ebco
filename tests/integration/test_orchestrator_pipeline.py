"""Integration tests for the Orchestrator pipeline — tasks.md T038, plus the approval-gate
guarantee quickstart.md's "Approval-gate check" describes (Principle I must never fail).

Uses InMemoryRepository and fake Gemini/GBP clients — no live GCP credentials needed, so
this suite runs the same way in CI as it does locally.
"""

from datetime import UTC, datetime

import pytest

from src.agents.analysis_agent import AnalysisAgent
from src.agents.draft_agent import DraftAgent
from src.agents.orchestrator import ApprovalRequiredError, Orchestrator
from src.agents.triage_agent import TriageAgent
from src.integrations.gbp_client import GbpApiError, PublishResult, RawReview
from src.models.branch import Branch, ConnectionStatus
from src.models.review import ReviewStatus, Severity
from src.storage.firestore_repo import InMemoryRepository


class _FakeGemini:
    """One fake serving analyze_review / score_severity / draft_reply — keyword-driven so
    tests stay readable without a real LLM call."""

    def analyze_review(self, review_text, rating):
        from src.integrations.gemini_client import AnalysisResult

        sentiment = "negative" if rating <= 2 else "positive"
        topics = ["service"] if "lambat" in review_text.lower() else []
        return AnalysisResult(sentiment=sentiment, topics=topics)

    def score_severity(self, review_text, rating, sentiment, topics):
        from src.integrations.gemini_client import SeverityResult

        severity = "urgent" if "bahaya" in review_text.lower() else "routine"
        return SeverityResult(severity=severity, reason="test heuristic")

    def draft_reply(self, review_text, rating, sentiment, topics, severity):
        return f"Terima kasih atas review Anda ({sentiment})."


class _FakeGbpClient:
    def __init__(self, reviews_by_branch: dict[str, list[RawReview]]) -> None:
        self._reviews_by_branch = reviews_by_branch
        self.publish_calls: list[tuple[str, str]] = []
        self.publish_result = PublishResult(publication_state="approved")
        self.raise_on_publish: Exception | None = None

    def list_reviews_since(self, branch_id, gbp_location_id, oauth_credential_ref, since):
        return self._reviews_by_branch.get(branch_id, [])

    def publish_reply(self, gbp_location_id, oauth_credential_ref, review_id, content):
        self.publish_calls.append((review_id, content))
        if self.raise_on_publish:
            raise self.raise_on_publish
        return self.publish_result


def _make_orchestrator(fake_gbp: _FakeGbpClient) -> tuple[Orchestrator, InMemoryRepository]:
    repo = InMemoryRepository()
    fake_gemini = _FakeGemini()
    orchestrator = Orchestrator(
        repo=repo,
        analysis_agent=AnalysisAgent(gemini_client=fake_gemini),
        triage_agent=TriageAgent(gemini_client=fake_gemini),
        draft_agent=DraftAgent(gemini_client=fake_gemini),
        gbp_client=fake_gbp,  # also used internally by the default IngestionAgent
    )
    return orchestrator, repo


def _raw(review_id, rating, text, existing_owner_reply=False) -> RawReview:
    return RawReview(
        review_id=review_id,
        rating=rating,
        text=text,
        reviewer_name="Test User",
        posted_at=datetime.now(UTC),
        language="id",
        existing_owner_reply=existing_owner_reply,
    )


def _make_branch(branch_id="b1", manager_id="m1") -> Branch:
    return Branch(
        branch_id=branch_id,
        name="Demo Branch",
        address="Jl. Demo",
        gbp_location_id=f"loc:{branch_id}",
        manager_id=manager_id,
        oauth_credential_ref="",
        connection_status=ConnectionStatus.CONNECTED,
    )


def test_ingestion_cycle_analyzes_triages_and_drafts_routine_reviews():
    fake_gbp = _FakeGbpClient({"b1": [_raw("r-routine", 4, "Pelayanan lambat tapi ramah")]})
    orchestrator, repo = _make_orchestrator(fake_gbp)
    branch = _make_branch()

    orchestrator.run_ingestion_cycle([branch])

    review = repo.get_review("r-routine")
    assert review is not None
    assert review.status == ReviewStatus.DRAFTED
    assert review.sentiment is not None
    assert review.severity == Severity.ROUTINE
    draft = repo.get_active_draft("r-routine")
    assert draft is not None
    assert draft.status.value == "pending"


def test_urgent_review_flagged_and_reported_separately_from_routine():
    fake_gbp = _FakeGbpClient(
        {
            "b1": [
                _raw("r-urgent", 1, "Ada bahaya kebakaran di lokasi ini!"),
                _raw("r-routine", 4, "Biasa saja, cukup baik"),
            ]
        }
    )
    orchestrator, repo = _make_orchestrator(fake_gbp)
    branch = _make_branch()

    report = orchestrator.run_ingestion_cycle([branch])

    assert report.newly_urgent_review_ids == ["r-urgent"]
    urgent_review = repo.get_review("r-urgent")
    routine_review = repo.get_review("r-routine")
    assert urgent_review.severity == Severity.URGENT
    assert routine_review.severity == Severity.ROUTINE
    # Both still flow through the normal draft-and-approve path (US3 AS3):
    assert urgent_review.status == ReviewStatus.DRAFTED
    assert routine_review.status == ReviewStatus.DRAFTED


def test_existing_owner_reply_skips_draft_agent_entirely():
    fake_gbp = _FakeGbpClient(
        {"b1": [_raw("r-answered", 5, "Sudah dijawab manual", existing_owner_reply=True)]}
    )
    orchestrator, repo = _make_orchestrator(fake_gbp)
    branch = _make_branch()

    orchestrator.run_ingestion_cycle([branch])

    review = repo.get_review("r-answered")
    assert review.status == ReviewStatus.ALREADY_ANSWERED
    assert repo.get_active_draft("r-answered") is None


def test_approve_draft_publishes_and_records_authenticated_approver():
    fake_gbp = _FakeGbpClient({"b1": [_raw("r1", 4, "Pelayanan baik")]})
    orchestrator, repo = _make_orchestrator(fake_gbp)
    orchestrator.run_ingestion_cycle([_make_branch()])
    draft = repo.get_active_draft("r1")

    outcome = orchestrator.approve_draft(draft.draft_id, "manager@example.com")

    assert outcome.publication_state.value == "approved"
    assert fake_gbp.publish_calls, "publish MUST have been called after approval"
    updated_draft = repo.get_active_draft("r1")
    assert updated_draft.approved_by == "manager@example.com"
    assert updated_draft.status.value == "published"
    assert repo.get_review("r1").status == ReviewStatus.PUBLISHED


def test_approve_draft_requires_authenticated_approver_email():
    """Principle I / quickstart.md Approval-gate check: publish must be unreachable without
    a real approver identity — this is the code-level guarantee, not just a UI affordance."""
    fake_gbp = _FakeGbpClient({"b1": [_raw("r1", 4, "Pelayanan baik")]})
    orchestrator, repo = _make_orchestrator(fake_gbp)
    orchestrator.run_ingestion_cycle([_make_branch()])
    draft = repo.get_active_draft("r1")

    with pytest.raises(ApprovalRequiredError):
        orchestrator.approve_draft(draft.draft_id, "")

    assert fake_gbp.publish_calls == [], "publish must never be called without an approver"
    assert repo.get_review("r1").status == ReviewStatus.DRAFTED  # unchanged


def test_reject_draft_generates_new_draft_without_publishing():
    fake_gbp = _FakeGbpClient({"b1": [_raw("r1", 2, "Pelayanan lambat")]})
    orchestrator, repo = _make_orchestrator(fake_gbp)
    orchestrator.run_ingestion_cycle([_make_branch()])
    original_draft = repo.get_active_draft("r1")

    new_draft = orchestrator.reject_draft(original_draft.draft_id)

    assert fake_gbp.publish_calls == []
    assert new_draft.draft_id != original_draft.draft_id
    assert new_draft.status.value == "pending"
    assert repo.get_review("r1").status == ReviewStatus.DRAFTED


def test_publish_failure_surfaces_error_without_marking_published():
    fake_gbp = _FakeGbpClient({"b1": [_raw("r1", 4, "Pelayanan baik")]})
    fake_gbp.raise_on_publish = GbpApiError("simulated outage")
    orchestrator, repo = _make_orchestrator(fake_gbp)
    orchestrator.run_ingestion_cycle([_make_branch()])
    draft = repo.get_active_draft("r1")

    outcome = orchestrator.approve_draft(draft.draft_id, "manager@example.com")

    assert outcome.error is not None
    assert repo.get_review("r1").status == ReviewStatus.APPROVED  # not PUBLISHED
