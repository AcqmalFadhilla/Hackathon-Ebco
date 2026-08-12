"""Branch Health Score entity — data-model.md § Branch Health Score."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class BranchHealthScore:
    branch_id: str
    score: float
    top_topics: list[str] = field(default_factory=list)
    urgent_count: int = 0
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "score": self.score,
            "top_topics": self.top_topics,
            "urgent_count": self.urgent_count,
            "computed_at": self.computed_at,
        }

    @staticmethod
    def from_dict(data: dict) -> BranchHealthScore:
        return BranchHealthScore(
            branch_id=data["branch_id"],
            score=data["score"],
            top_topics=list(data.get("top_topics", [])),
            urgent_count=int(data.get("urgent_count", 0)),
            computed_at=data.get("computed_at") or datetime.now(UTC),
        )
