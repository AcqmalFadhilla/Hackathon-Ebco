"""Seed/sample review dataset fallback — constitution Principle IV.

Used when the live Google Business Profile API is unavailable/slow, or when
`USE_SEED_DATA=true` for local/demo runs without real OAuth-connected branches.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.config.logging import get_logger
from src.config.settings import SETTINGS

logger = get_logger(__name__)


def load_seed_reviews(branch_id: str) -> list[dict]:
    """Returns raw review dicts (same shape the GBP client would return) for a branch."""
    path = Path(SETTINGS.seed_data_path)
    if not path.exists():
        logger.warning("Seed data file not found at %s", path)
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            all_seed = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load seed data: %s", exc)
        return []

    raw_reviews = all_seed.get(branch_id, [])
    out = []
    for r in raw_reviews:
        out.append(
            {
                "review_id": r["review_id"],
                "rating": r["rating"],
                "text": r["text"],
                "reviewer_name": r["reviewer_name"],
                "posted_at": datetime.fromisoformat(r["posted_at"]),
                "language": r.get("language", "other"),
                "existing_owner_reply": bool(r.get("existing_owner_reply", False)),
            }
        )
    return out


def has_seed_data(branch_id: str) -> bool:
    path = Path(SETTINGS.seed_data_path)
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            all_seed = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    return branch_id in all_seed
