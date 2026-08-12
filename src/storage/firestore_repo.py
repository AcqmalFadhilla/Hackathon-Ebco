"""Repository layer — data-model.md entities, CRUD.

`InMemoryRepository` is the default/testable implementation (no GCP dependency, used by
unit/integration tests and local dev without credentials). `FirestoreRepository` is the
production implementation, lazily importing `google.cloud.firestore` so importing this
module never requires live GCP credentials.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.branch import Branch
from src.models.branch_health import BranchHealthScore
from src.models.draft_reply import DraftReply
from src.models.manager import Manager
from src.models.review import Review, ReviewStatus


class Repository(ABC):
    """Storage contract used by every agent/UI — swap implementation, not call sites."""

    @abstractmethod
    def save_branch(self, branch: Branch) -> None: ...

    @abstractmethod
    def get_branch(self, branch_id: str) -> Branch | None: ...

    @abstractmethod
    def list_branches(self, manager_id: str | None = None) -> list[Branch]: ...

    @abstractmethod
    def save_review(self, review: Review) -> None: ...

    @abstractmethod
    def get_review(self, review_id: str) -> Review | None: ...

    @abstractmethod
    def list_reviews(
        self,
        branch_id: str | None = None,
        status: ReviewStatus | None = None,
        sentiment: str | None = None,
    ) -> list[Review]: ...

    @abstractmethod
    def save_draft(self, draft: DraftReply) -> None: ...

    @abstractmethod
    def get_active_draft(self, review_id: str) -> DraftReply | None: ...

    @abstractmethod
    def save_branch_health(self, score: BranchHealthScore) -> None: ...

    @abstractmethod
    def list_branch_health(self, branch_ids: list[str]) -> list[BranchHealthScore]: ...

    @abstractmethod
    def save_manager(self, manager: Manager) -> None: ...

    @abstractmethod
    def get_manager(self, manager_id: str) -> Manager | None: ...

    @abstractmethod
    def get_manager_by_email(self, email: str) -> Manager | None: ...

    @abstractmethod
    def list_managers(self) -> list[Manager]: ...


class InMemoryRepository(Repository):
    def __init__(self) -> None:
        self._branches: dict[str, Branch] = {}
        self._reviews: dict[str, Review] = {}
        self._drafts: dict[str, DraftReply] = {}
        self._drafts_by_review: dict[str, str] = {}
        self._branch_health: dict[str, BranchHealthScore] = {}
        self._managers: dict[str, Manager] = {}

    # Branch
    def save_branch(self, branch: Branch) -> None:
        self._branches[branch.branch_id] = branch

    def get_branch(self, branch_id: str) -> Branch | None:
        return self._branches.get(branch_id)

    def list_branches(self, manager_id: str | None = None) -> list[Branch]:
        vals = list(self._branches.values())
        if manager_id:
            vals = [b for b in vals if b.manager_id == manager_id]
        return vals

    # Review
    def save_review(self, review: Review) -> None:
        self._reviews[review.review_id] = review

    def get_review(self, review_id: str) -> Review | None:
        return self._reviews.get(review_id)

    def list_reviews(
        self,
        branch_id: str | None = None,
        status: ReviewStatus | None = None,
        sentiment: str | None = None,
    ) -> list[Review]:
        vals = list(self._reviews.values())
        if branch_id:
            vals = [r for r in vals if r.branch_id == branch_id]
        if status:
            vals = [r for r in vals if r.status == status]
        if sentiment:
            vals = [r for r in vals if r.sentiment and r.sentiment.value == sentiment]
        return sorted(vals, key=lambda r: r.posted_at, reverse=True)

    # Draft Reply
    def save_draft(self, draft: DraftReply) -> None:
        self._drafts[draft.draft_id] = draft
        self._drafts_by_review[draft.review_id] = draft.draft_id

    def get_active_draft(self, review_id: str) -> DraftReply | None:
        draft_id = self._drafts_by_review.get(review_id)
        return self._drafts.get(draft_id) if draft_id else None

    # Branch Health Score
    def save_branch_health(self, score: BranchHealthScore) -> None:
        self._branch_health[score.branch_id] = score

    def list_branch_health(self, branch_ids: list[str]) -> list[BranchHealthScore]:
        return [self._branch_health[b] for b in branch_ids if b in self._branch_health]

    # Manager
    def save_manager(self, manager: Manager) -> None:
        self._managers[manager.manager_id] = manager

    def get_manager(self, manager_id: str) -> Manager | None:
        return self._managers.get(manager_id)

    def get_manager_by_email(self, email: str) -> Manager | None:
        for m in self._managers.values():
            if m.google_identity_email == email:
                return m
        return None

    def list_managers(self) -> list[Manager]:
        return list(self._managers.values())


class FirestoreRepository(Repository):
    """Production repository backed by Firestore. Collections mirror data-model.md entities."""

    def __init__(self, project: str, database: str = "(default)") -> None:
        from google.cloud import firestore  # lazy import — no GCP dependency at module load

        self._client = firestore.Client(project=project, database=database)
        self._firestore = firestore

    def save_branch(self, branch: Branch) -> None:
        self._client.collection("branches").document(branch.branch_id).set(branch.to_dict())

    def get_branch(self, branch_id: str) -> Branch | None:
        doc = self._client.collection("branches").document(branch_id).get()
        return Branch.from_dict(doc.to_dict()) if doc.exists else None

    def list_branches(self, manager_id: str | None = None) -> list[Branch]:
        query = self._client.collection("branches")
        if manager_id:
            query = query.where("manager_id", "==", manager_id)
        return [Branch.from_dict(d.to_dict()) for d in query.stream()]

    def save_review(self, review: Review) -> None:
        self._client.collection("reviews").document(review.review_id).set(review.to_dict())

    def get_review(self, review_id: str) -> Review | None:
        doc = self._client.collection("reviews").document(review_id).get()
        return Review.from_dict(doc.to_dict()) if doc.exists else None

    def list_reviews(
        self,
        branch_id: str | None = None,
        status: ReviewStatus | None = None,
        sentiment: str | None = None,
    ) -> list[Review]:
        query = self._client.collection("reviews")
        if branch_id:
            query = query.where("branch_id", "==", branch_id)
        if status:
            query = query.where("status", "==", status.value)
        if sentiment:
            query = query.where("sentiment", "==", sentiment)
        return [Review.from_dict(d.to_dict()) for d in query.stream()]

    def save_draft(self, draft: DraftReply) -> None:
        self._client.collection("draft_replies").document(draft.draft_id).set(draft.to_dict())

    def get_active_draft(self, review_id: str) -> DraftReply | None:
        # Ordered by created_at, not draft_id — draft_id is a random UUID, not chronological,
        # so ordering by it would silently pick an arbitrary draft instead of the latest one.
        query = (
            self._client.collection("draft_replies")
            .where("review_id", "==", review_id)
            .order_by("created_at", direction=self._firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = list(query.stream())
        return DraftReply.from_dict(docs[0].to_dict()) if docs else None

    def save_branch_health(self, score: BranchHealthScore) -> None:
        self._client.collection("branch_health").document(score.branch_id).set(score.to_dict())

    def list_branch_health(self, branch_ids: list[str]) -> list[BranchHealthScore]:
        out = []
        for bid in branch_ids:
            doc = self._client.collection("branch_health").document(bid).get()
            if doc.exists:
                out.append(BranchHealthScore.from_dict(doc.to_dict()))
        return out

    def save_manager(self, manager: Manager) -> None:
        self._client.collection("managers").document(manager.manager_id).set(manager.to_dict())

    def get_manager(self, manager_id: str) -> Manager | None:
        doc = self._client.collection("managers").document(manager_id).get()
        return Manager.from_dict(doc.to_dict()) if doc.exists else None

    def get_manager_by_email(self, email: str) -> Manager | None:
        query = self._client.collection("managers").where(
            "google_identity_email", "==", email
        ).limit(1)
        docs = list(query.stream())
        return Manager.from_dict(docs[0].to_dict()) if docs else None

    def list_managers(self) -> list[Manager]:
        return [Manager.from_dict(d.to_dict()) for d in self._client.collection("managers").stream()]


_repo_singleton: Repository | None = None


def get_repo() -> Repository:
    """Returns the process-wide repository. Firestore if GCP_PROJECT is set, else in-memory
    (Principle IV — the app must still run for local/demo use without live credentials)."""
    global _repo_singleton
    if _repo_singleton is not None:
        return _repo_singleton

    from src.config.logging import get_logger
    from src.config.settings import SETTINGS

    if SETTINGS.gcp_project:
        try:
            _repo_singleton = FirestoreRepository(
                project=SETTINGS.gcp_project, database=SETTINGS.firestore_database
            )
            return _repo_singleton
        except Exception as exc:  # noqa: BLE001 — fall back rather than crash the whole app
            get_logger(__name__).warning(
                "Could not connect to Firestore, falling back to in-memory repo: %s", exc
            )
    _repo_singleton = InMemoryRepository()
    return _repo_singleton
