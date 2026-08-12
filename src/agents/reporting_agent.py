"""Reporting Agent — single responsibility: cross-branch health digest (FR-015/FR-016).

contracts/agent-interfaces.md: input {branch_ids, period}, output {rankings:
BranchHealthScore[]}. Read-only over already-persisted data — no ingestion/analysis side
effects (Principle II).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.models.branch_health import BranchHealthScore
from src.models.review import Review, Sentiment, Severity
from src.storage.firestore_repo import Repository

_SENTIMENT_WEIGHT = {Sentiment.POSITIVE: 1.0, Sentiment.NEUTRAL: 0.0, Sentiment.NEGATIVE: -1.0}


@dataclass
class DigestOutput:
    rankings: list[BranchHealthScore]  # worst health first


class ReportingAgent:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def run(self, branch_ids: list[str], period_days: int = 30) -> DigestOutput:
        cutoff = datetime.now(UTC) - timedelta(days=period_days)
        scores: list[BranchHealthScore] = []
        for branch_id in branch_ids:
            reviews = [
                r for r in self._repo.list_reviews(branch_id=branch_id) if r.posted_at >= cutoff
            ]
            scores.append(_score_branch(branch_id, reviews))
            self._repo.save_branch_health(scores[-1])

        ranked = sorted(scores, key=lambda s: s.score)  # ascending: worst health first
        return DigestOutput(rankings=ranked)


def _score_branch(branch_id: str, reviews: list[Review]) -> BranchHealthScore:
    if not reviews:
        return BranchHealthScore(branch_id=branch_id, score=0.0, top_topics=[], urgent_count=0)

    sentiment_sum = sum(_SENTIMENT_WEIGHT.get(r.sentiment, 0.0) for r in reviews)
    sentiment_avg = sentiment_sum / len(reviews)

    urgent_count = sum(1 for r in reviews if r.severity == Severity.URGENT)
    urgent_penalty = urgent_count / max(len(reviews), 1)

    published = sum(1 for r in reviews if r.status.value == "published")
    respondable = sum(1 for r in reviews if r.status.value != "already_answered")
    response_rate = (published / respondable) if respondable else 1.0

    # 0-100 scale: sentiment (-1..1 -> 0..1) + response rate, minus urgent penalty.
    score = max(
        0.0,
        min(100.0, ((sentiment_avg + 1) / 2 * 60 + response_rate * 40 - urgent_penalty * 20)),
    )

    topic_counts: Counter[str] = Counter()
    for r in reviews:
        topic_counts.update(r.topics)
    top_topics = [t for t, _ in topic_counts.most_common(3)]

    return BranchHealthScore(
        branch_id=branch_id, score=round(score, 1), top_topics=top_topics, urgent_count=urgent_count
    )
